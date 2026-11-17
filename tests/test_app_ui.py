"""Headless Streamlit checks of app.py (AppTest): no browser, no network, stub retrieval.

Live-mode tests replace only the Gemini call (src.pipeline.analyse_image) with a stub; intake,
fusion, rules, retrieval, costing, overlays, JSON and PDF all run for real.
"""
import hashlib
import html
import io
import os

import numpy as np
import pytest
from PIL import Image

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

import src.pipeline as pipeline  # noqa: E402
from src import service  # noqa: E402
from src.analyse import AnalysisError  # noqa: E402
from src.intake import inspect_image_bytes  # noqa: E402
from src.schemas import Damage, ImageResult, VehicleIdentity  # noqa: E402

from .conftest import ROOT  # noqa: E402


# --------------------------------------------------------------------------- fixtures/helpers
def _ok(at):
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state._render_error is None, at.session_state._render_error


@pytest.fixture
def app(monkeypatch, retriever):
    import streamlit as st
    st.cache_resource.clear()
    st.cache_data.clear()
    monkeypatch.setattr(service, "_retriever", retriever)      # stub embeddings, temp index
    for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120)
    at.run()
    _ok(at)
    return at


def _jpeg(seed: int) -> bytes:
    rng = np.random.default_rng(seed)
    buf = io.BytesIO()
    Image.fromarray(rng.integers(0, 255, (480, 640, 3), dtype=np.uint8)).save(buf, format="JPEG", quality=92)
    return buf.getvalue()


def _result(view, color, *damages):
    return ImageResult(view=view, damages=list(damages), notes="", is_vehicle=True,
                       vehicle_identity=VehicleIdentity(color=color, body_type="hatchback",
                                                        make_model_guess="Hyundai i20"))


def _dmg(comp, typ, sev, loc="front", box=(100, 100, 400, 500)):
    return Damage(component=comp, damage_type=typ, severity=sev, location=loc, confidence=0.9,
                  evidence=f"{typ} visible", severity_rationale="test", box_2d=list(box))


@pytest.fixture
def live(app, monkeypatch):
    """App with a (fake) key and a Gemini stub keyed by the processed image hash."""
    monkeypatch.setenv("GEMINI_API_KEY", "offline-test-key-not-real")
    table, calls = {}, []

    def fake(jpeg_bytes, view_hint=None, use_cache=True):
        calls.append(hashlib.sha256(jpeg_bytes).hexdigest())
        res = table[calls[-1]]
        if isinstance(res, Exception):
            raise res
        return res

    monkeypatch.setattr(pipeline, "analyse_image", fake)

    def add(name, data, res):
        table[inspect_image_bytes(name, data).sha256] = res
        return (name, data, "image/jpeg")

    app.run()
    _ok(app)
    return app, add, calls


def _upload(at, files):
    at.file_uploader[0].set_value(files).run()
    _ok(at)


def _vehicle(at, prefix="live", make="Hyundai", model="i20", year=2023):
    at.selectbox(key=f"{prefix}_make").set_value(make).run()
    at.selectbox(key=f"{prefix}_model").set_value(model).run()
    at.selectbox(key=f"{prefix}_year").set_value(year).run()
    _ok(at)


def _three_same_car(add):
    return [add("front.jpg", _jpeg(1), _result("front", "white", _dmg("front_bumper", "dent", "moderate"),
                                               _dmg("headlight_left", "lamp_broken", "severe"))),
            add("left.jpg", _jpeg(2), _result("left", "white", _dmg("left_front_door", "scratch", "minor", "left"))),
            add("rear.jpg", _jpeg(3), _result("rear", "white"))]


def _text(at) -> str:
    """Visible text: markdown + alerts + HTML blocks (entities decoded, as a browser shows them)."""
    parts = [m.value for m in at.markdown] + [html.unescape(str(h.proto.body)) for h in at.get("html")]
    parts += [a.value for kind in ("warning", "error", "info", "success") for a in getattr(at, kind)]
    return " ".join(parts)


def _run_sample(at):
    at.button(key="sample_run").click().run()
    _ok(at)
    w = at.session_state.ws_sample
    assert w["view"] == "results" and w["error"] is None
    return w["result"].assessment


def _to_samples(at):
    at.segmented_control(key="nav").set_value("samples").run()
    _ok(at)


# --------------------------------------------------------------------------- default / key state
def test_default_view_is_new_assessment_with_uploader(app):
    assert app.session_state.nav == "new"
    assert len(app.file_uploader) == 1
    assert app.button(key="live_analyze").disabled          # nothing uploaded yet
    assert app.session_state.ws_sample["result"] is None    # sample mode never auto-runs


def test_live_mode_without_key_is_explicit(app):
    blob = _text(app)
    assert "Gemini key missing" in blob and "not configured" in blob
    assert "connected" not in blob.lower().replace("not connected", "")
    assert app.button(key="live_analyze").disabled
    assert os.environ.get("GEMINI_API_KEY") is None


# --------------------------------------------------------------------------- sample mode
def test_sample_flow_produces_matching_exports(app):
    _to_samples(app)
    a = _run_sample(app)
    assert a.mode == "sample_fixture"
    # the fixture's own vehicle is used (2021 is outside the 2022-2026 catalog -> manual entry),
    # not silently replaced by the newest catalog year (which would leave everything unpriced)
    assert (a.vehicle.make, a.vehicle.model, a.vehicle.year) == ("Hyundai", "i20", 2021)
    assert a.totals.status != "insufficient_pricing_data" and a.totals.observed_low is not None
    ex = app.session_state.ws_sample["exports"]
    assert ex["assessment_id"] == a.assessment_id and ex["pdf"].startswith(b"%PDF")
    assert '"mode": "sample_fixture"' in ex["json"]
    assert ex["pdf_check"] == "match"
    assert "Sample fixture" in _text(app) and a.pricing_label in _text(app)   # labels stay visible


def test_new_run_after_back_never_reuses_old_downloads(app):
    _to_samples(app)
    first = _run_sample(app)
    app.button(key="sample_edit_inputs").click().run()
    app.radio(key="sample_fixture").set_value("sample_minor.json").run()
    _ok(app)
    assert app.session_state.ws_sample["result"] is None and app.session_state.ws_sample["exports"] is None
    second = _run_sample(app)
    assert second.assessment_id != first.assessment_id
    assert second.vehicle.model == "Swift"
    assert app.session_state.ws_sample["exports"]["assessment_id"] == second.assessment_id


def test_unchanged_inputs_reuse_result_without_rerunning(app, monkeypatch):
    runs = []
    real = service.run_sample_assessment
    monkeypatch.setattr(service, "run_sample_assessment", lambda *a, **k: runs.append(1) or real(*a, **k))
    _to_samples(app)
    first = _run_sample(app)
    app.button(key="sample_edit_inputs").click().run()
    _ok(app)
    assert app.button(key="sample_run").disabled               # same inputs: no second run offered
    app.button(key="sample_view_results").click().run()
    _ok(app)
    assert app.session_state.ws_sample["result"].assessment.assessment_id == first.assessment_id
    assert len(runs) == 1


# --------------------------------------------------------------------------- live mode (stubbed Gemini)
def test_live_flow_end_to_end_and_no_repeated_inference(live):
    at, add, calls = live
    _upload(at, _three_same_car(add))
    assert len(at.session_state.photos) == 3
    _vehicle(at)
    at.button(key="live_analyze").click().run()
    _ok(at)
    w = at.session_state.ws_live
    assert w["view"] == "results" and w["error"] is None, w["error"]
    a = w["result"].assessment
    assert a.mode == "live" and a.damage_map["images_analysed"] == 3
    assert len(w["result"].overlays) == 3
    assert w["exports"]["assessment_id"] == a.assessment_id and w["exports"]["pdf_check"] == "match"
    stages = [label for label, _ in w["timings"]]
    assert any(s.startswith("Vision analysis: Photo 1") for s in stages)        # real pipeline stages
    assert stages[-1] == "Rendering PDF and JSON report"
    n = len(calls)
    assert n == 3

    # ordinary interactions never call the model again
    at.segmented_control(key="viewer_layer").set_value("Original").run()
    second_image = list(w["result"].overlays)[1]
    at.button(key=f"vthumb_{second_image}").click().run()
    assert at.session_state.viewer_image == second_image
    at.button(key="live_edit_inputs").click().run()
    assert at.button(key="live_analyze").disabled                          # result is current
    at.button(key="live_view_results").click().run()
    _ok(at)
    assert at.session_state.ws_live["result"].assessment.assessment_id == a.assessment_id
    assert len(calls) == n


def test_changing_inputs_discards_result_and_downloads(live):
    at, add, _ = live
    _upload(at, _three_same_car(add))
    _vehicle(at)
    at.button(key="live_analyze").click().run()
    assert at.session_state.ws_live["result"] is not None
    at.button(key="live_edit_inputs").click().run()
    at.selectbox(key="live_year").set_value(2022).run()
    _ok(at)
    w = at.session_state.ws_live
    assert w["result"] is None and w["exports"] is None
    assert not at.button(key="live_analyze").disabled


def test_duplicate_and_unreadable_uploads_are_flagged(live):
    at, add, _ = live
    front = add("front.jpg", _jpeg(1), _result("front", "white"))
    _upload(at, [front, ("copy.jpg", front[1], "image/jpeg"), ("broken.jpg", b"\xff\xd8 not an image", "image/jpeg")])
    blob = _text(at)
    assert "3 of 5 added · 1 unique" in blob
    assert "Duplicate" in blob and "Can't be used" in blob
    at.button(key=f"rm_{at.session_state.photos[2]['uid']}").click().run()
    _ok(at)
    assert len(at.session_state.photos) == 2


def test_identity_conflict_blocks_until_photo_removed(live):
    at, add, _ = live
    files = [add("a.jpg", _jpeg(1), _result("front", "white", _dmg("front_bumper", "dent", "minor"))),
             add("b.jpg", _jpeg(2), _result("left", "white")),
             add("c.jpg", _jpeg(3), _result("rear", "red"))]
    _upload(at, files)
    _vehicle(at)
    at.button(key="live_analyze").click().run()
    _ok(at)
    w = at.session_state.ws_live
    assert w["conflict"] and w["result"] is None
    assert "different vehicles" in _text(at) and "Photo 3: colour red" in _text(at)
    assert at.button(key="live_analyze").disabled
    at.button(key=f"rm_{at.session_state.photos[2]['uid']}").click().run()
    _ok(at)
    assert at.session_state.ws_live["conflict"] is None
    assert not at.button(key="live_analyze").disabled


def test_quota_error_is_readable_and_retry_runs_again(live):
    at, add, calls = live
    err = AnalysisError("Gemini analysis failed after 3 attempts: 429 RESOURCE_EXHAUSTED quota exceeded")
    _upload(at, [add("a.jpg", _jpeg(1), err)])
    _vehicle(at)
    at.button(key="live_analyze").click().run()
    _ok(at)
    e = at.session_state.ws_live["error"]
    assert e["kind"] == "quota" and e["retryable"] and "quota" in e["title"].lower()
    assert "Traceback" not in _text(at)
    before = len(calls)
    at.button(key="live_retry").click().run()
    _ok(at)
    assert len(calls) == before + 1 and at.session_state.ws_live["error"]["kind"] == "quota"


def test_user_supplied_text_is_escaped(live):
    at, add, _ = live
    evil = '<img src=x onerror="alert(1)">.jpg'
    _upload(at, [add(evil, _jpeg(5), _result("front", "white"))])
    bodies = " ".join(str(h.proto.body) for h in at.get("html"))
    assert "<img src=x" not in bodies and "&lt;img src=x" in bodies
