"""Unit tests for the UI helper modules (no Streamlit runtime needed)."""
import io

import numpy as np
import pytest
from PIL import Image

pytest.importorskip("streamlit")

from src import analyse  # noqa: E402
from src.contracts import Observation  # noqa: E402
from src.intake import IntakeError, inspect_image_bytes, load_image  # noqa: E402
from src.overlay import draw_overlay  # noqa: E402
from ui.format import format_inr, human, money_range  # noqa: E402
from ui.html import chip, code, esc, md  # noqa: E402
from ui.photos import assess, precheck, summary  # noqa: E402
from ui.runner import _live_label, classify_error  # noqa: E402


def _jpeg(seed=0, size=(640, 480), flat=False) -> bytes:
    if flat:
        arr = np.full((size[1], size[0], 3), 128, dtype=np.uint8)
    else:
        arr = np.random.default_rng(seed).integers(0, 255, (size[1], size[0], 3), dtype=np.uint8)
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="JPEG", quality=92)
    return buf.getvalue()


# --------------------------------------------------------------------------- escaping
def test_escaping_helpers_neutralise_markup():
    assert esc('<b onclick="x">&') == "&lt;b onclick=&quot;x&quot;&gt;&amp;"
    assert "<script>" not in chip("<script>alert(1)</script>", "red")
    assert md("[link](javascript:x) **b** :red[x]") == r"\[link\]\(javascript\:x\) \*\*b\*\* \:red\[x\]"
    assert code("gemini-2.5-flash") == "`gemini-2.5-flash`"          # code spans are literal: no escapes
    assert code("a`b") == "`a'b`"
    assert chip("x", "not-a-tone").startswith('<span class="ai-chip ai-chip--neutral"')


def test_money_formatting_uses_indian_grouping():
    assert format_inr(158650) == "₹1,58,650" and format_inr(950) == "₹950" and format_inr(None) == "Not available"
    assert money_range(46500, 91050) == "₹46,500 – ₹91,050"
    assert money_range(100, 100) == "₹100" and money_range(None, None) == "Not priced"
    assert human("left_front_door") == "Left front door"


# --------------------------------------------------------------------------- errors
@pytest.mark.parametrize("exc,kind", [
    (IntakeError("x.jpg is too small"), "intake"),
    (analyse.FatalAnalysisError("GEMINI_API_KEY is not set: missing"), "config"),
    (analyse.FatalAnalysisError("Gemini rejected the request: API key not valid"), "config"),
    (analyse.AnalysisError("failed after 3 attempts: 429 RESOURCE_EXHAUSTED"), "quota"),
    (analyse.AnalysisError("failed: 504 DEADLINE_EXCEEDED"), "network"),
    (analyse.AnalysisError("failed: Connection reset by peer"), "network"),
    (analyse.AnalysisError("No image could be analysed: no vehicle visible"), "analysis"),
    (RuntimeError("boom"), "unexpected"),
])
def test_errors_are_classified_with_readable_copy(exc, kind):
    e = classify_error(exc)
    assert e["kind"] == kind and e["title"] and e["hint"]
    assert "Traceback" not in e["message"]


def test_config_error_title_distinguishes_missing_and_rejected_key():
    assert classify_error(analyse.FatalAnalysisError("GEMINI_API_KEY is not set"))["title"].endswith("not configured")
    assert classify_error(analyse.FatalAnalysisError("API key not valid"))["title"] == "Gemini rejected the request"


def test_error_messages_never_contain_the_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "secret-test-key-123456")
    e = classify_error(analyse.AnalysisError("bad request for key secret-test-key-123456"))
    assert "secret-test-key-123456" not in e["message"] and "[REDACTED]" in e["message"]


def test_progress_messages_map_to_photo_numbers():
    names = {"01_front.jpg": "Photo 1"}
    assert _live_label("Analysing 01_front.jpg (1/3)", names) == "Vision analysis: Photo 1 (1 of 3)"
    assert _live_label("Checking images", names).startswith("Validating photos")
    assert _live_label("something new", names) == "something new"      # unknown events shown verbatim


# --------------------------------------------------------------------------- photo intake
def test_precheck_matches_pipeline_image_id(tmp_path):
    data = _jpeg(7)
    p = tmp_path / "front.jpg"
    p.write_bytes(data)
    assert inspect_image_bytes("front.jpg", data).image_id == load_image(p).image_id
    photo = precheck("front.jpg", data)
    assert photo["ok"] and photo["image_id"] == load_image(p).image_id and photo["thumb"].startswith(b"\xff\xd8")


def test_precheck_rejects_bad_files_with_reason():
    assert "Unsupported file type" in precheck("doc.pdf", b"%PDF-1.4")["error"]
    assert "too small" in precheck("tiny.jpg", _jpeg(1, size=(120, 90)))["error"]
    assert "Cannot open image" in precheck("bad.jpg", b"\xff\xd8 garbage" * 5)["error"]


def test_photo_states_duplicate_blurry_unusable():
    a = precheck("a.jpg", _jpeg(1))
    dup = precheck("a_copy.jpg", _jpeg(1))
    blurry = precheck("flat.jpg", _jpeg(flat=True))
    bad = precheck("bad.jpg", b"nope")
    rows = assess([a, dup, blurry, bad])
    assert [r["state"] for r in rows] == ["ready", "duplicate", "blurry", "unusable"]
    assert "Photo 1" in rows[1]["notes"][0]
    s = summary([a, dup, blurry, bad])
    assert (s["total"], s["unique"], s["duplicates"], s["unusable"], s["blurry"]) == (4, 2, 1, 1, 1)


# --------------------------------------------------------------------------- overlay
def test_compact_overlay_is_opt_in_and_reports_same_unboxed():
    data = _jpeg(3)
    obs = [Observation(damage_id="O1", component="hood", component_reported="hood", damage_type="dent",
                       severity="minor", location="front", confidence=0.9, image_ids=["IMG-1"],
                       bbox_by_image={"IMG-1": [0.1, 0.1, 0.5, 0.5]}),
           Observation(damage_id="O2", component="front_bumper", component_reported="front_bumper",
                       damage_type="scratch", severity="minor", location="front", confidence=0.9,
                       image_ids=["IMG-1"], bbox_by_image={"IMG-1": None})]
    full, unboxed_full = draw_overlay(data, "IMG-1", obs)
    compact, unboxed_compact = draw_overlay(data, "IMG-1", obs, compact=True)
    assert full.startswith(b"\xff\xd8") and compact.startswith(b"\xff\xd8") and full != compact
    assert unboxed_full == unboxed_compact == ["O2 front_bumper scratch (minor)"]
