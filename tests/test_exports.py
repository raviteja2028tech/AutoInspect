"""JSON/PDF exports come from one object and agree; upload names are sanitised."""
import json

import pytest

from src.contracts import Assessment, VehicleInfo
from src.intake import safe_upload_name
from src.report import pdf_totals_match
from src.service import export_assessment, run_sample_assessment

from .conftest import SAMPLES

pytest.importorskip("pypdf")


@pytest.mark.parametrize("fixture,vehicle", [
    ("my_case_v2.json", VehicleInfo(make="Hyundai", model="i20", year=2021)),
    ("sample_minor.json", VehicleInfo(make="Maruti Suzuki", model="Swift", year=2022)),
    ("sample_no_damage.json", VehicleInfo(make="Honda", model="City", year=2021)),
])
def test_json_and_pdf_show_the_same_totals(fixture, vehicle, retriever):
    res = run_sample_assessment(SAMPLES / fixture, vehicle, retriever=retriever)
    json_text, pdf_bytes = export_assessment(res)
    again = Assessment.model_validate_json(json_text)
    assert again.totals == res.assessment.totals
    assert again.assessment_id == res.assessment.assessment_id
    assert pdf_bytes.startswith(b"%PDF")
    assert pdf_totals_match(pdf_bytes, res.assessment.totals) == "match"
    data = json.loads(json_text)
    assert data["mode"] == "sample_fixture"
    assert any("SAMPLE MODE" in w for w in data["warnings"])


def test_parity_check_detects_a_mismatch(retriever):
    res = run_sample_assessment(SAMPLES / "my_case_v2.json",
                                VehicleInfo(make="Hyundai", model="i20", year=2021), retriever=retriever)
    _, pdf_bytes = export_assessment(res)
    fake = res.assessment.totals.model_copy(update={"observed_low": res.assessment.totals.observed_low + 1})
    assert pdf_totals_match(pdf_bytes, fake).startswith("MISMATCH")


@pytest.mark.parametrize("name,idx,expected", [
    ("front.jpg", 1, "01_front.jpg"),
    ("../../etc/passwd.png", 2, "02_passwd.png"),
    ("C:\\Users\\x\\left side (1).JPEG", 3, "03_left_side__1.jpeg"),
    ("weird.exe", 4, "04_weird.jpg"),
    ("....", 5, "05_photo.jpg"),
])
def test_safe_upload_name(name, idx, expected):
    assert safe_upload_name(name, idx) == expected


def test_pipeline_warnings_reach_assessment_and_pdf(retriever):
    res = run_sample_assessment(SAMPLES / "fusion_check.json",
                                VehicleInfo(make="Hyundai", model="i20", year=2021), retriever=retriever)
    a = res.assessment
    coverage = [w for w in a.warnings if "usable photo" in w]
    assert coverage, a.warnings                       # copied from damage_map.warnings
    assert len(a.warnings) == len(set(a.warnings))    # no duplicates
    import io

    import pypdf
    _, pdf_bytes = export_assessment(res)
    text = " ".join("".join(p.extract_text() or "" for p in pypdf.PdfReader(io.BytesIO(pdf_bytes)).pages).split())
    assert "usable photo" in text
