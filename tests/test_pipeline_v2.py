"""Phase 2 behaviour with offline model stubs (no API key, no network)."""
import hashlib
import io
import json
import shutil
import types as pytypes
from pathlib import Path

import numpy as np
import pytest
from PIL import Image
from pydantic import ValidationError

import src.analyse as analyse
import src.pipeline as pipeline
from src.contracts import Observation
from src.intake import intake_images
from src.kb.retrieve import make_embedder, open_retriever
from src.schemas import Damage, ImageResult, VehicleIdentity, normalised_box
from src.service import run_live_assessment

VEH = {"make": "Hyundai", "model": "i20", "year": 2021}


def _img(path, seed):
    rng = np.random.default_rng(seed)
    Image.fromarray(rng.integers(0, 255, (480, 640, 3), dtype=np.uint8)).save(path)
    return Path(path)


def D(comp, typ, sev, conf, loc="front", box=(100, 100, 400, 500)):
    return Damage(component=comp, damage_type=typ, severity=sev, location=loc, confidence=conf,
                  evidence=f"{typ} visible", severity_rationale="test", box_2d=list(box) if box else None)


def R(view, *damages, color="white", body="hatchback", is_vehicle=True):
    return ImageResult(view=view, damages=list(damages), notes="", is_vehicle=is_vehicle,
                       vehicle_identity=VehicleIdentity(color=color, body_type=body, make_model_guess="Hyundai i20"))


@pytest.fixture
def stub(monkeypatch):
    """Map image (by file order) -> ImageResult. Keyed by processed-bytes hash."""
    table = {}

    def fake(jpeg_bytes, view_hint=None, use_cache=True):
        key = hashlib.sha256(jpeg_bytes).hexdigest()
        res = table[key]
        if isinstance(res, Exception):
            raise res
        return res

    monkeypatch.setattr(pipeline, "analyse_image", fake)

    def register(paths_and_results):
        for p, r in paths_and_results:
            table[intake_images([p]).images[0].sha256] = r
    return register


@pytest.fixture
def retr(tmp_path):
    return open_retriever(index_dir=tmp_path / "idx", embedder=make_embedder("stub_test"))


@pytest.fixture
def three(tmp_path, stub):
    paths = [_img(tmp_path / f"{n}.jpg", i) for i, n in enumerate(("front", "left", "rear"))]
    stub([(paths[0], R("front", D("front_bumper", "dent", "moderate", 0.9), D("front_bumper", "scratch", "minor", 0.8))),
          (paths[1], R("left", D("front_bumper", "dent", "moderate", 0.85, loc="front"),
                       D("side_mirror_left", "missing_part", "severe", 0.9, loc="left"))),
          (paths[2], R("rear", D("taillight_right", "lamp_broken", "severe", 0.95, loc="rear", box=None)))])
    return paths


# ---------------------------------------------------------------- duplicates
def test_duplicate_input_changes_nothing(three, tmp_path, retr):
    base = run_live_assessment(three, VEH, retriever=retr).assessment
    dup = tmp_path / "front_copy.jpg"
    shutil.copy(three[0], dup)
    again = run_live_assessment(three + [dup], VEH, retriever=retr).assessment
    assert again.damage_map["images_analysed"] == base.damage_map["images_analysed"] == 3
    assert [o.model_dump() for o in again.observations] == [o.model_dump() for o in base.observations]
    assert again.totals.observed_low == base.totals.observed_low
    assert again.totals.observed_high == base.totals.observed_high
    assert again.damage_map["images_duplicate"][0]["duplicate_of"] == "front.jpg"
    bumper = next(o for o in again.observations if o.component == "front_bumper" and o.damage_type == "dent")
    assert bumper.views_supporting == 2 and bumper.confidence == 0.88        # mean, no bonus


def test_end_to_end_live_stub_with_overlays(three, retr):
    res = run_live_assessment(three, VEH, retriever=retr, accident_description="Front collision at a junction")
    a = res.assessment
    assert a.mode == "live" and a.damage_map["schema_version"] == "damage-map-2.0"
    fb = next(p for p in a.component_plans if p.component_instance == "front_bumper")
    assert fb.operation == "repair" and len(fb.damage_ids) == 2               # dent + scratch -> one plan
    mirror = next(p for p in a.component_plans if p.component_instance == "side_mirror_left")
    assert mirror.action == "replace" and mirror.rule_id == "M-1"
    assert set(res.overlays) == {m["image_id"] for m in a.damage_map["image_manifest"]}
    rear_id = a.damage_map["image_manifest"][2]["image_id"]
    assert any("taillight_right" in u for u in res.unboxed[rear_id])          # null box -> listed, not drawn
    Image.open(io.BytesIO(res.overlays[rear_id])).verify()
    assert "_processed_images" not in a.damage_map
    assert a.totals.status == "complete"
    assert json.loads(a.model_dump_json())["totals"]["observed_low"] == str(a.totals.observed_low)


# ---------------------------------------------------------------- identity / sides / severity
def test_mixed_vehicles_blocked_until_confirmed(tmp_path, stub, retr):
    p = [_img(tmp_path / f"{i}.jpg", 10 + i) for i in range(3)]
    stub([(p[0], R("front", D("hood", "dent", "moderate", 0.9), color="white")),
          (p[1], R("left", D("left_front_door", "dent", "moderate", 0.9, loc="left"), color="red", body="sedan")),
          (p[2], R("rear", color="white"))])
    with pytest.raises(pipeline.VehicleMismatchError) as e:
        run_live_assessment(p, VEH, retriever=retr)
    assert e.value.consistency["status"] == "conflict"
    a = run_live_assessment(p, VEH, retriever=retr, confirm_same_vehicle=True).assessment
    assert any("User confirmed" in w for w in a.warnings)
    assert any("Same-vehicle check" in r for r in a.uncertainty.reasons)


def test_opposite_side_components_not_merged(tmp_path, stub, retr):
    p = [_img(tmp_path / f"{i}.jpg", 20 + i) for i in range(3)]
    stub([(p[0], R("left", D("side_mirror_left", "crack", "severe", 0.9, loc="left"),
                   D("wheel_tire_front_left", "tire_flat", "severe", 0.9, loc="left"))),
          (p[1], R("right", D("side_mirror_right", "crack", "severe", 0.9, loc="right"),
                   D("wheel_tire_rear_right", "tire_flat", "severe", 0.9, loc="right"))),
          (p[2], R("front"))])
    a = run_live_assessment(p, VEH, retriever=retr).assessment
    inst = sorted(pl.component_instance for pl in a.component_plans)
    assert inst == ["side_mirror_left", "side_mirror_right", "wheel_tire_front_left", "wheel_tire_rear_right"]
    tyres = [pl for pl in a.component_plans if pl.component_class == "wheel_tire"]
    assert all(pl.cost is not None for pl in tyres)                              # one tyre charge each


def test_weak_severe_does_not_override_strong_moderate(tmp_path, stub, retr):
    p = [_img(tmp_path / f"{i}.jpg", 30 + i) for i in range(3)]
    stub([(p[0], R("front", D("hood", "dent", "moderate", 0.92))),
          (p[1], R("front", D("hood", "dent", "severe", 0.45))),
          (p[2], R("left", D("left_fender", "dent", "minor", 0.9, loc="left"),)),])
    dm = pipeline.analyse_case(p, VEH)
    hood = next(o for o in dm["observations"] if o["component"] == "hood")
    assert hood["severity"] == "moderate"
    c = next(c for c in dm["conflicts"] if c["type"] == "severity_conflict")
    assert c["chosen"] == "moderate" and not c["unresolved"] and "not used" in c["detail"]


def test_strong_disagreement_left_unresolved(tmp_path, stub, retr):
    p = [_img(tmp_path / f"{i}.jpg", 40 + i) for i in range(3)]
    stub([(p[0], R("front", D("hood", "dent", "minor", 0.9))),
          (p[1], R("front", D("hood", "dent", "severe", 0.85))),
          (p[2], R("rear"))])
    a = run_live_assessment(p, VEH, retriever=retr).assessment
    hood = next(pl for pl in a.component_plans if pl.component_instance == "hood")
    assert hood.action == "inspect" and hood.cost is None


# ---------------------------------------------------------------- validation
def test_invalid_scores_and_boxes_rejected():
    with pytest.raises(ValidationError):
        Damage(component="hood", damage_type="dent", severity="minor", location="front", confidence=1.4)
    assert normalised_box([100, 200, 300, 400]) == ([0.2, 0.1, 0.4, 0.3], "approximate VLM localisation (not segmentation)")
    for bad in ([300, 200, 100, 400], [0, 0, 1200, 10], [1, 2, 3], ["a", 1, 2, 3], [0, 0, float("nan"), 5]):
        box, reason = normalised_box(bad)
        assert box is None and "rejected" in reason
    with pytest.raises(ValidationError):
        Observation(damage_id="O1", component="hood", component_reported="hood", damage_type="dent",
                    severity="minor", location="front", confidence=0.9, image_ids=["IMG-a"],
                    bbox_by_image={"IMG-b": [0.1, 0.1, 0.2, 0.2]})
    with pytest.raises(ValidationError):
        Observation(damage_id="O1", component="hood", component_reported="hood", damage_type="dent",
                    severity="minor", location="front", confidence=0.9, image_ids=["IMG-a"],
                    bbox_by_image={"IMG-a": [0.5, 0.1, 0.2, 0.2]})


def test_non_vehicle_and_undamaged(tmp_path, stub, retr):
    p = [_img(tmp_path / f"{i}.jpg", 50 + i) for i in range(3)]
    stub([(p[0], R("unknown", is_vehicle=False)), (p[1], R("front")), (p[2], R("rear"))])
    a = run_live_assessment(p, VEH, retriever=retr).assessment
    assert a.damage_map["images_analysed"] == 2 and len(a.damage_map["images_not_vehicle"]) == 1
    assert a.totals.status == "no_damage" and "No visible damage detected." in a.damage_map["warnings"]
    q = [_img(tmp_path / f"n{i}.jpg", 60 + i) for i in range(2)]
    stub([(q[0], R("unknown", is_vehicle=False)), (q[1], R("unknown", is_vehicle=False))])
    with pytest.raises(analyse.AnalysisError, match="No image could be analysed"):
        run_live_assessment(q, VEH, retriever=retr)                      # error, never "no damage"


def test_partial_image_failure_and_coverage_warning(tmp_path, stub, retr):
    p = [_img(tmp_path / f"{i}.jpg", 70 + i) for i in range(2)]
    bad = tmp_path / "broken.jpg"
    bad.write_bytes(b"not an image")
    stub([(p[0], R("front", D("hood", "dent", "moderate", 0.9))),
          (p[1], analyse.AnalysisError("quota exhausted after retries"))])
    a = run_live_assessment(p + [bad], VEH, retriever=retr).assessment
    dm = a.damage_map
    assert dm["images_analysed"] == 1
    assert dm["images_rejected"][0]["file"] == "broken.jpg"
    assert dm["images_analysis_failed"][0]["error"].startswith("quota")
    assert any("Insufficient coverage" in w for w in dm["warnings"])
    assert any("Image coverage" in r for r in a.uncertainty.reasons)


def test_narrative_is_context_not_evidence(three, retr):
    a = run_live_assessment(three, VEH, retriever=retr,
                            accident_description="Another car hit my rear and roof while parked").assessment
    nc = a.damage_map["narrative_check"]
    assert nc["provided"] and "rear" in nc["areas_mentioned"]
    assert not any(p.component_instance == "roof" for p in a.component_plans)      # never adds damage
    b = run_live_assessment(three, VEH, retriever=retr, accident_description="I reversed into a pole").assessment
    assert b.damage_map["narrative_check"]["not_mentioned"]                        # front/left damage unmentioned


# ---------------------------------------------------------------- analyse.py runtime behaviour
class FakeClient:
    def __init__(self, behaviours):
        self.behaviours = list(behaviours)
        self.calls = 0
        self.models = self

    def generate_content(self, **kw):
        self.calls += 1
        b = self.behaviours.pop(0)
        if isinstance(b, Exception):
            raise b
        return pytypes.SimpleNamespace(parsed=None, text=b)


class ApiErr(Exception):
    def __init__(self, code, msg):
        super().__init__(f"{code} {msg}")
        self.code = code


@pytest.fixture
def live(monkeypatch, tmp_path):
    monkeypatch.setattr(analyse, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(analyse, "MIN_INTERVAL_S", 0)
    monkeypatch.setattr(analyse.time, "sleep", lambda s: None)

    def use(*behaviours):
        client = FakeClient(behaviours)
        monkeypatch.setattr(analyse, "_client", client)
        return client
    return use


GOOD = R("front", D("hood", "dent", "minor", 0.9)).model_dump_json()


def test_missing_key_fails_fast(monkeypatch, tmp_path):
    monkeypatch.setattr(analyse, "CACHE_DIR", tmp_path / "c")
    monkeypatch.setattr(analyse, "_client", None)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(analyse.FatalAnalysisError, match="GEMINI_API_KEY is not set"):
        analyse.analyse_image(b"\xff\xd8fake", use_cache=False)


def test_malformed_then_valid_and_cache_provenance(live):
    client = live("this is not json", '{"view": "front", "damages": [{"component": "hood"}]}', GOOD)
    r = analyse.analyse_image(b"img-1")
    assert client.calls == 3 and analyse.result_provenance(r)["source"] == "fresh"
    r2 = analyse.analyse_image(b"img-1")
    assert client.calls == 3 and analyse.result_provenance(r2)["source"] == "cache"


def test_malformed_forever_raises(live):
    live(*["nope"] * 10)
    with pytest.raises(analyse.AnalysisError, match="failed after"):
        analyse.analyse_image(b"img-2", max_retries=3)


def test_quota_retried_then_reported(live):
    c = live(ApiErr(429, "RESOURCE_EXHAUSTED"), ApiErr(429, "RESOURCE_EXHAUSTED"), GOOD)
    analyse.analyse_image(b"img-3")
    assert c.calls == 3
    c = live(*[ApiErr(503, "UNAVAILABLE")] * 5)
    with pytest.raises(analyse.AnalysisError):
        analyse.analyse_image(b"img-4", max_retries=3)
    assert c.calls == 3


def test_auth_error_not_retried(live):
    c = live(ApiErr(400, "API key not valid. API_KEY_INVALID"), GOOD)
    with pytest.raises(analyse.FatalAnalysisError):
        analyse.analyse_image(b"img-5")
    assert c.calls == 1


def test_corrupt_and_out_of_range_cache_entries_discarded(live):
    path = analyse._cache_path(b"img-6", None)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"view": "front", "damages": [{"component": "hood", "damage_type": "dent", '
                    '"severity": "minor", "location": "front", "confidence": 7}], "notes": ""}')
    c = live(GOOD)
    r = analyse.analyse_image(b"img-6")
    assert c.calls == 1 and analyse.result_provenance(r)["source"] == "fresh"
    assert ImageResult.model_validate_json(path.read_text()).damages[0].confidence == 0.9


def test_cache_key_versioned(monkeypatch):
    k1 = analyse._cache_path(b"x", None)
    assert k1 != analyse._cache_path(b"x", "front")                 # view hint
    assert k1 != analyse._cache_path(b"y", None)                    # image
    monkeypatch.setattr(analyse, "PROMPT_VERSION", "v999")
    assert k1 != analyse._cache_path(b"x", None)                    # prompt version
    monkeypatch.setattr(analyse, "PROMPT_VERSION", "v3")
    monkeypatch.setattr(analyse, "MODEL", "some-other-model")
    assert k1 != analyse._cache_path(b"x", None)                    # model


def test_fatal_error_stops_pipeline(tmp_path, monkeypatch):
    p = [_img(tmp_path / f"{i}.jpg", 80 + i) for i in range(3)]
    calls = []

    def boom(b, view_hint=None, use_cache=True):
        calls.append(1)
        raise analyse.FatalAnalysisError("GEMINI_API_KEY is not set")
    monkeypatch.setattr(pipeline, "analyse_image", boom)
    with pytest.raises(analyse.FatalAnalysisError):
        pipeline.analyse_case(p, VEH)
    assert len(calls) == 1
