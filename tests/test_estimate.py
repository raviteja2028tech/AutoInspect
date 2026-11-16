"""Rules + cost engine + end-to-end estimate from damage-map JSON (offline, stub embeddings)."""
import json
from decimal import Decimal

import pytest

from tests.conftest import SAMPLES
from src.components import ClarificationError
from src.contracts import Assessment, PricingRecord, PricingScope, VehicleInfo
from src.costing import line_cost
from src.estimate import build_assessment

I20 = {"make": "Hyundai", "model": "i20", "year": 2021}
SCOPE = PricingScope(region="IN-DEMO-METRO", currency="INR")


def dm(*damages, n=3):
    return {"vehicle": {"make": "Hyundai", "model": "i20", "reg_no": ""}, "images_analysed": n,
            "damages": [dict(zip(("component", "damage_type", "severity", "location", "confidence"), d))
                        for d in damages]}


def plan(a, comp):
    return next(p for p in a.component_plans if p.component_instance == comp)


def run(retriever, damage_map, scope=SCOPE, **kw):
    return build_assessment(damage_map, VehicleInfo(**I20), scope, retriever, **kw)


# ---------------------------------------------------------------- arithmetic
def test_line_formula_and_rounding():
    r = PricingRecord(record_id="T1", source_id="S", make="Hyundai", model="i20", year_from=2020, year_to=2024,
                      component="hood", operation="repair", parts_cost_low=Decimal("100"),
                      parts_cost_high=Decimal("200"), labor_hours_low=Decimal("1.5"),
                      labor_hours_high=Decimal("2.25"), labor_rate_low=Decimal("555"),
                      labor_rate_high=Decimal("701"), paint_materials_low=Decimal("10"),
                      paint_materials_high=Decimal("20.4"), currency="INR", region="X", tax_included=False,
                      data_quality="synthetic_demo")
    c = line_cost(r)
    assert c.labor_low == Decimal("833")          # 832.5 -> ROUND_HALF_UP
    assert c.labor_high == Decimal("1577")        # 1577.25
    assert c.low == Decimal("100") + Decimal("833") + Decimal("10")
    assert c.high == Decimal("200") + Decimal("1577") + Decimal("20")


def test_bumper_dent_and_scratch_counted_once(retriever):
    a = run(retriever, dm(("front_bumper", "dent", "moderate", "front", 0.9),
                          ("front_bumper", "scratch", "minor", "front", 0.8)))
    assert len(a.component_plans) == 1
    p = a.component_plans[0]
    assert p.damage_ids == ["D1", "D2"] and p.operation == "repair" and p.action == "repair"
    assert "not charged twice" in p.covered_damage_note
    assert a.totals.observed_low == p.cost.low and a.totals.observed_high == p.cost.high
    assert p.selected_record_id in [e.record_id for e in p.retrieval.evidence]


def test_severe_dent_plus_scratch_single_replacement(retriever):
    a = run(retriever, dm(("front_bumper", "dent", "severe", "front", 0.95),
                          ("front_bumper", "scratch", "minor", "front", 0.75)))
    p = a.component_plans[0]
    assert p.operation == "replace" and "covers D2" in p.covered_damage_note
    assert a.totals.observed_low == p.cost.low                    # one replacement charge only
    assert [s.operation for s in p.alternatives] == ["repair"]    # alternate scenario kept


def test_left_and_right_components_distinct(retriever):
    a = run(retriever, dm(("headlight_left", "lamp_broken", "severe", "front", 0.9),
                          ("headlight_right", "lamp_broken", "severe", "front", 0.9),
                          ("side_mirror_left", "crack", "severe", "left", 0.9),
                          ("side_mirror_right", "scratch", "minor", "right", 0.9)))
    assert [p.component_instance for p in a.component_plans] == [
        "headlight_left", "headlight_right", "side_mirror_left", "side_mirror_right"]
    assert plan(a, "side_mirror_right").operation == "refinish"
    assert a.totals.observed_low == sum(p.cost.low for p in a.component_plans)
    assert a.totals.status == "complete"


def test_ambiguous_legacy_name_flagged_then_clarified(retriever):
    d = dm(("side_mirror", "crack", "severe", "left", 0.98), ("hood", "dent", "moderate", "front", 0.9))
    a = run(retriever, d)
    p = plan(a, "side_mirror")
    assert p.ambiguous and p.pricing_status == "ambiguous_component" and p.cost is None
    assert "side_mirror_left" in p.clarification
    assert a.totals.status == "partial" and "side_mirror" in a.totals.unpriced_components
    assert "NOT a complete estimate" in a.totals.status_label
    b = run(retriever, d, clarifications={"D1": "side_mirror_left"})
    assert plan(b, "side_mirror_left").pricing_status == "priced" and b.totals.status == "complete"
    with pytest.raises(ClarificationError):
        run(retriever, d, clarifications={"D1": "wheel_tire_front_left"})


def test_unsupported_parts_are_null_not_zero(retriever):
    a = run(retriever, dm(("other", "dent", "moderate", "front", 0.9),
                          ("side_window_front_left", "glass_shatter", "severe", "left", 0.9),
                          ("hood", "dent", "moderate", "front", 0.9)))
    assert plan(a, "other").pricing_status == "unsupported_component"
    sw = plan(a, "side_window_front_left")
    assert sw.action == "replace" and sw.pricing_status == "insufficient_pricing_data" and sw.cost is None
    assert a.totals.status == "partial"
    assert a.totals.observed_low == plan(a, "hood").cost.low          # only the priced item, labelled partial
    assert set(a.totals.unpriced_components) == {"other", "side_window_front_left"}


def test_nothing_priced_for_unsupported_vehicle(retriever):
    a = build_assessment(dm(("hood", "dent", "moderate", "front", 0.9)),
                         VehicleInfo(make="Toyota", model="Glanza", year=2022), SCOPE, retriever)
    assert a.totals.status == "insufficient_pricing_data" and a.totals.observed_low is None


def test_inspect_scenarios_kept_out_of_observed_subtotal(retriever):
    a = run(retriever, dm(("left_quarter_panel", "dent", "severe", "left", 0.9),
                          ("hood", "scratch", "minor", "front", 0.9)))
    qp = plan(a, "left_quarter_panel")
    assert qp.action == "inspect" and qp.rule_id == "PW-STRUCT" and qp.cost is None
    assert {s.operation for s in qp.alternatives} == {"repair", "replace"}
    t = a.totals
    assert t.observed_low == plan(a, "hood").cost.low
    assert t.unresolved_low == min(s.cost.low for s in qp.alternatives)
    assert t.unresolved_high == max(s.cost.high for s in qp.alternatives)
    assert t.envelope_high == t.observed_high + t.unresolved_high
    assert t.unresolved_components == ["left_quarter_panel"]


def test_low_confidence_finding_requires_inspection(retriever):
    a = run(retriever, dm(("windshield", "crack", "minor", "front", 0.41)))
    p = a.component_plans[0]
    assert p.action == "inspect" and p.rule_id == "G-UNCERTAIN"
    assert any("Low model scores" in r for r in a.uncertainty.reasons)


def test_severity_alone_does_not_decide(retriever):
    strong = run(retriever, dm(("left_front_door", "dent", "severe", "left", 0.95)))
    weak = run(retriever, dm(("left_front_door", "dent", "severe", "left", 0.6)))
    tyre = run(retriever, dm(("wheel_tire_front_left", "tire_flat", "moderate", "left", 0.9)))
    assert strong.component_plans[0].action == "replace"
    assert weak.component_plans[0].action == "inspect"
    assert tyre.component_plans[0].action == "inspect"          # possible puncture repair


def test_tax_applied_only_when_configured(retriever):
    d = dm(("hood", "dent", "moderate", "front", 0.9))
    a = run(retriever, d)
    assert a.totals.tax_basis == "excl_tax" and a.totals.tax_low is None
    b = run(retriever, d, scope=PricingScope(region="IN-DEMO-METRO", currency="INR", tax_rate=Decimal("0.18")))
    t = b.totals
    assert t.tax_low == (t.observed_low * Decimal("0.18")).quantize(Decimal("1"))
    assert t.observed_with_tax_high == t.observed_high + t.tax_high


def test_mixed_tax_treatment_not_combined(retriever, monkeypatch):
    a = run(retriever, dm(("hood", "dent", "moderate", "front", 0.9),
                          ("trunk", "dent", "moderate", "rear", 0.9)))
    trunk = plan(a, "trunk")
    from src.costing import compute_totals
    trunk.cost = trunk.cost.model_copy(update={"tax_included": True})
    t = compute_totals(a.component_plans, "INR", None)
    assert t.tax_basis == "mixed" and t.observed_low is None and t.status == "partial"
    t2 = compute_totals(a.component_plans, "INR", Decimal("0.18"))
    assert t2.tax_low == (plan(a, "hood").cost.low * Decimal("0.18")).quantize(Decimal("1"))


def test_no_damage(retriever):
    a = run(retriever, dm())
    assert a.totals.status == "no_damage" and a.component_plans == []


# ---------------------------------------------------------------- legacy samples end to end
@pytest.mark.parametrize("name", ["my_case_v2.json", "sample_severe.json", "sample_minor.json",
                                  "sample_no_damage.json", "fusion_check.json", "my_case.json"])
def test_all_legacy_samples_produce_valid_estimates(retriever, name, tmp_path):
    damage_map = json.loads((SAMPLES / name).read_text(encoding="utf-8"))
    a = run(retriever, damage_map)
    out = tmp_path / "e.json"
    out.write_text(a.model_dump_json(), encoding="utf-8")
    back = Assessment.model_validate_json(out.read_text(encoding="utf-8"))
    assert back.damage_map == damage_map                       # input retained verbatim
    assert back.schema_version == "assessment-1.0" and back.disclaimer.startswith("Preliminary")
    for p in back.component_plans:
        if p.cost is not None:                                 # every priced item is explained + cited
            assert p.selected_record_id and p.selected_record_id in p.explanation and p.rule_id in p.explanation
    if back.component_plans:
        assert back.pricing_label == "Illustrative demo pricing — not market verified."
    total = sum((p.cost.low for p in back.component_plans if p.cost), Decimal(0))
    if back.totals.observed_low is not None:
        assert back.totals.observed_low == total


def test_my_case_v2_end_to_end(retriever):
    damage_map = json.loads((SAMPLES / "my_case_v2.json").read_text(encoding="utf-8"))
    a = run(retriever, damage_map)
    fb = plan(a, "front_bumper")
    assert fb.damage_ids == ["D7", "D12"] and fb.operation == "replace"      # dent + scratch -> one plan
    assert plan(a, "side_mirror").pricing_status == "ambiguous_component"
    assert plan(a, "wheel_tire").pricing_status == "ambiguous_component"
    assert plan(a, "right_quarter_panel").action == "inspect"
    assert a.totals.status == "partial"


def test_unresolved_severity_conflict_goes_to_inspection(retriever):
    """Strong views disagreeing by two levels must not be dropped as 'low-confidence' (rules v2)."""
    from src.contracts import Observation
    common = dict(component="left_front_door", component_reported="left_front_door", location="left",
                  image_ids=["IMG-A", "IMG-B"])
    obs = [
        Observation(damage_id="O1", damage_type="scratch", severity="moderate", confidence=0.9, **common),
        Observation(damage_id="O2", damage_type="dent", severity="severe", confidence=0.9, uncertain=True,
                    severity_unresolved=True, per_image=[{"image_id": "IMG-A", "severity": "minor", "score": 0.9},
                                                         {"image_id": "IMG-B", "severity": "severe", "score": 0.9}],
                    **common),
    ]
    damage_map = {"vehicle": {"make": "Hyundai", "model": "i20"}, "images_analysed": 3, "damages": [],
                  "observations": [o.model_dump(mode="json") for o in obs]}
    a = run(retriever, damage_map)
    p = plan(a, "left_front_door")
    assert p.action == "inspect" and p.rule_id == "G-SEV-CONFLICT" and p.cost is None
    assert "minor/severe" in p.reason
    assert {"repair", "replace"} <= {s.operation for s in p.alternatives}
    assert a.totals.unresolved_components == ["left_front_door"]
    assert not any("low-confidence" in n and "O2" in n for n in p.notes)


def test_fusion_flags_unresolved_severity(retriever):
    from src.fuse import fuse_observations
    from src.schemas import Damage, ImageResult

    def r(sev):
        return ImageResult(view="left", notes="", damages=[Damage(component="left_front_door", damage_type="dent",
                                                                  severity=sev, location="left", confidence=0.9)])
    observations, conflicts = fuse_observations([("IMG-A", r("minor")), ("IMG-B", r("severe"))])
    assert observations[0].severity_unresolved and observations[0].uncertain
    assert any(c["type"] == "severity_conflict" and c["unresolved"] for c in conflicts)
    same, _ = fuse_observations([("IMG-A", r("severe")), ("IMG-B", r("severe"))])
    assert not same[0].severity_unresolved
