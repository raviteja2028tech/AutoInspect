"""Tests for src/reporting/pdf_report.py. Offline; no Gemini, no API key, no project pipeline."""
import copy
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

pytest.importorskip("reportlab")
pypdf = pytest.importorskip("pypdf")

from src.reporting import DISCLAIMER, generate_pdf_report  # noqa: E402
from src.reporting import pdf_report  # noqa: E402


def _evidence(record_id, source_id, synthetic=False, rank=1):
    return {
        "record_id": record_id, "source_id": source_id,
        "source_title": "Workshop price sheet", "rank": rank, "score": 0.8123,
        "source_type": "synthetic_demo" if synthetic else "workshop_estimate",
        "synthetic": synthetic, "fallback_level": "exact_model",
        "applicability_reason": "Same make/model/year range",
        "retrieval_method": "semantic",
        "record": {"data_quality": "synthetic_demo" if synthetic else "sourced_verified"},
    }


def _cost(low, high, record_id):
    return {"operation": "repair", "record_id": record_id, "currency": "INR",
            "tax_included": False, "low": low, "high": high}


@pytest.fixture
def assessment():
    return {
        "schema_version": "assessment-1.0",
        "assessment_id": "ASM-2026-0042",
        "created_at": "2026-11-15T10:20:30+00:00",
        "mode": "live",
        "disclaimer": DISCLAIMER,
        "pricing_label": None,
        "vehicle": {"make": "Maruti", "model": "Swift", "year": 2021, "variant": "VXI",
                    "reg_no": "KA01AB1234", "source": "user_supplied"},
        "pricing_scope": {"region": "IN-KA", "currency": "INR", "part_grade_preference": "oem"},
        "accident_description": "Low-speed parking collision.",
        "observations": [
            {"damage_id": "d1", "component": "front_bumper", "damage_type": "dent",
             "severity": "moderate", "location": "front", "confidence": 0.82,
             "uncertain": False, "evidence": "Visible dent near fog lamp",
             "severity_rationale": "Deformation > 5 cm"},
        ],
        "component_plans": [
            {"component_instance": "front_bumper", "component_class": "bumper",
             "damage_types": ["dent", "scratch"], "max_severity": "moderate",
             "action": "repair", "operation": "repair", "rule_id": "R-12", "rule_version": "1",
             "reason": "Moderate dent is repairable", "pricing_status": "priced",
             "selected_record_id": "REC-1", "cost": _cost("4500.00", "7000.00", "REC-1"),
             "retrieval": {"status": "ok", "evidence": [_evidence("REC-1", "SRC-A")]}},
        ],
        "totals": {"currency": "INR", "status": "complete", "status_label": "All findings priced",
                   "tax_basis": "excl_tax", "observed_low": "4500.00", "observed_high": "7000.00",
                   "priced_components": ["front_bumper"], "unresolved_components": [],
                   "unpriced_components": []},
        "uncertainty": {"level": "medium", "points": 3,
                        "reasons": ["Single view of damage"], "method": "Heuristic count"},
        "assumptions": ["OEM parts"], "exclusions": ["Hidden structural damage"],
        "warnings": [], "provenance": {},
    }


def _text(path: Path) -> tuple[str, int]:
    reader = pypdf.PdfReader(str(path))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    return re.sub(r"\s+", " ", text), len(reader.pages)


def test_normal_assessment_produces_readable_pdf(tmp_path, assessment):
    out = generate_pdf_report(assessment, tmp_path / "sub" / "report.pdf")
    assert out == tmp_path / "sub" / "report.pdf"
    assert out.read_bytes()[:5] == b"%PDF-"
    assert not list(tmp_path.rglob("*.part"))
    text, pages = _text(out)
    assert pages >= 1
    for expected in ("Vehicle Damage Assessment Report", "ASM-2026-0042", "2026-11-15",
                     "Maruti", "Swift", "KA01AB1234", "front_bumper", "dent", "moderate",
                     "Moderate dent is repairable", "REC-1", "SRC-A", "4,500.00", "7,000.00",
                     "Observed total", "Single view of damage", "OEM parts",
                     "Hidden structural damage", f"Page 1 of {pages}"):
        assert expected in text, expected
    assert DISCLAIMER in text
    assert "SYNTHETIC PRICING" not in text and "SAMPLE / DEMO" not in text
    assert "PARTIAL" not in text


def test_missing_prices_and_partial_totals(tmp_path, assessment):
    a = copy.deepcopy(assessment)
    a["component_plans"].append({
        "component_instance": "headlamp_left", "damage_types": ["crack"], "max_severity": "severe",
        "action": "replace", "operation": "replace", "reason": "Cracked lens",
        "pricing_status": "insufficient_pricing_data", "cost": None,
        "retrieval": {"status": "insufficient_pricing_data", "message": "No record for model"}})
    a["totals"].update(status="partial", status_label="Partial: 1 component unpriced",
                       unpriced_components=["headlamp_left"],
                       envelope_low=None, envelope_high=None)
    out = generate_pdf_report(a, tmp_path / "partial.pdf")
    text, _ = _text(out)
    assert "PARTIAL subtotal" in text
    assert "Totals are PARTIAL" in text and "headlamp_left" in text
    assert "Not priced" in text
    assert "Not available" in text          # envelope was None, not shown as zero
    assert "insufficient_pricing_data" in text
    assert not re.search(r"(?<![\d,])0\.00", text), "unknown values must not render as 0.00"
    assert "4,500.00" in text and "7,000.00" in text   # supplied subtotal displayed verbatim


def test_missing_totals_and_empty_assessment(tmp_path):
    out = generate_pdf_report({}, tmp_path / "empty.pdf")
    text, _ = _text(out)
    assert "No totals supplied" in text
    assert "No vehicle details supplied" in text
    assert "Not supplied" in text
    assert DISCLAIMER in text


def test_long_text_spans_multiple_pages(tmp_path, assessment):
    a = copy.deepcopy(assessment)
    long_reason = ("The panel shows extensive deformation. " * 250) + "X" * 400
    base = a["component_plans"][0]
    a["component_plans"] = []
    for i in range(30):
        p = copy.deepcopy(base)
        p["component_instance"] = f"panel_{i:02d}"
        p["reason"] = long_reason if i == 0 else f"Reason {i}"
        p["retrieval"]["evidence"] = [_evidence(f"REC-{i}-{r}", f"SRC-{r}", rank=r) for r in range(1, 4)]
        a["component_plans"].append(p)
    a["accident_description"] = "Very long description. " * 200
    out = generate_pdf_report(a, tmp_path / "long.pdf")
    text, pages = _text(out)
    assert pages >= 4
    assert f"Page {pages} of {pages}" in text
    assert "panel_29" in text and "REC-29-3" in text
    assert text.count("Record ID") >= 2   # long tables repeat their header row


def test_markup_characters_are_escaped(tmp_path, assessment):
    a = copy.deepcopy(assessment)
    nasty = "<b>bold</b> & <script>alert(1)</script> <font color=red>x A < B > C \"q\""
    a["vehicle"]["model"] = "Swift <i>"
    a["accident_description"] = nasty
    a["component_plans"][0]["reason"] = "Unclosed <para tag & stray </b>"
    a["assumptions"] = ["Tom & Jerry <OEM>"]
    out = generate_pdf_report(a, tmp_path / "markup.pdf")
    text, _ = _text(out)
    assert "<script>alert(1)</script>" in text
    assert "<b>bold</b>" in text
    assert "Swift <i>" in text
    assert "Unclosed <para tag & stray </b>" in text
    assert "Tom & Jerry <OEM>" in text


def test_synthetic_and_demo_labels(tmp_path, assessment):
    a = copy.deepcopy(assessment)
    a["mode"] = "sample_fixture"
    a["pricing_label"] = "Illustrative demo pricing — not market verified."
    a["component_plans"][0]["retrieval"]["evidence"] = [_evidence("REC-1", "SRC-DEMO", synthetic=True)]
    text, _ = _text(generate_pdf_report(a, tmp_path / "demo.pdf"))
    assert "SAMPLE / DEMO MODE" in text
    assert "SYNTHETIC PRICING" in text and "not market verified" in text
    assert "YES" in text   # synthetic column in the references table


def test_synthetic_detected_from_evidence_without_label(tmp_path, assessment):
    a = copy.deepcopy(assessment)
    a["component_plans"][0]["retrieval"]["evidence"] = [
        {"record_id": "REC-1", "source_id": "SRC-DEMO", "record": {"data_quality": "synthetic_demo"}}]
    text, _ = _text(generate_pdf_report(a, tmp_path / "syn.pdf"))
    assert "SYNTHETIC PRICING" in text
    assert "SAMPLE / DEMO" not in text


def test_inr_fallback_when_font_lacks_rupee(tmp_path, assessment, monkeypatch):
    monkeypatch.setattr(pdf_report, "FONT_CANDIDATES", [])
    text, _ = _text(generate_pdf_report(assessment, tmp_path / "inr.pdf"))
    assert "INR 4,500.00" in text
    assert "₹" not in text


def test_money_never_coerces_unknown_to_zero():
    m = pdf_report._Money(pdf_report._Fonts("Helvetica", "Helvetica-Bold", rupee=False))
    assert m.fmt(None, "INR") == "Not available"
    assert m.fmt("", "INR") == "Not available"
    assert m.fmt("abc", "INR") == "abc (unparsed)"
    assert m.fmt(0, "INR") == "INR 0.00"          # a real supplied zero is still shown
    assert m.rng(None, None, "INR") == "Not available"
    assert m.rng("100", None, "INR") == "INR 100.00 – Not available"


def test_images_keep_aspect_ratio_and_missing_is_noted(tmp_path, assessment):
    PIL_Image = pytest.importorskip("PIL.Image")
    img = tmp_path / "wide.png"
    PIL_Image.new("RGB", (1600, 400), (200, 30, 30)).save(img)
    w, h = pdf_report._scaled_size(1600, 400, 500, 300)
    assert w == pytest.approx(500) and h == pytest.approx(125)
    assert pdf_report._scaled_size(100, 50, 500, 300) == (100, 50)   # no upscaling
    missing = tmp_path / "nope.jpg"
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"not an image")
    out = generate_pdf_report(assessment, tmp_path / "img.pdf",
                              image_paths=[img, (str(missing), "Rear view"), {"path": str(bad)}])
    text, _ = _text(out)
    assert "Image 1: wide.png" in text
    assert "Rear view" in text and "image not available" in text
    assert "image could not be read" in text
    reader = pypdf.PdfReader(str(out))
    assert sum(len(p.images) for p in reader.pages) == 1


def test_inspection_scenarios_are_not_called_unpriced(tmp_path, assessment):
    """Engine 'complete' + unresolved items: PDF must not claim those items lack a price."""
    a = dict(assessment)
    a["totals"] = {**a["totals"], "status": "complete", "unpriced_components": [],
                   "unresolved_components": ["left_front_door"], "unresolved_low": "4600",
                   "unresolved_high": "30900", "status_label": "All findings priced; 1 item(s) need inspection"}
    out = tmp_path / "r.pdf"
    generate_pdf_report(a, out)
    text = " ".join("".join(p.extract_text() or "" for p in pypdf.PdfReader(str(out)).pages).split())
    assert "without a supported price" not in text
    assert "need physical inspection" in text and "left_front_door" in text
