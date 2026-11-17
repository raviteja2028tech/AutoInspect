"""Run an assessment and show its REAL stages.

Stage lines come only from the pipeline's own progress callback (src.pipeline/src.service)
and from the steps this module actually performs (loading the index, rendering exports).
Durations are measured, not simulated. Errors are classified into readable messages; the
traceback is logged to the server console and never shown in the page.
"""
from __future__ import annotations

import logging
import re
import shutil
import tempfile
import time
from pathlib import Path

import streamlit as st

from src import analyse, service, settings
from src.intake import IntakeError, safe_upload_name
from src.pipeline import VehicleMismatchError
from src.report import pdf_totals_match

from .connection import config_signature, get_cached_retriever
from .html import md

log = logging.getLogger("autoinspect.ui")
SAMPLES_DIR = settings.PROJECT_ROOT / "samples"


class StageTracker:
    """Renders a checklist of stages inside an st.status container with measured durations."""

    def __init__(self, status, total_hint: str = ""):
        self.status = status
        self.done: list[tuple[str, float]] = []
        self.current: str | None = None
        self.t0 = time.perf_counter()
        with status:
            self.bar = st.progress(0.0, text=total_hint or "Starting")
            self.box = st.empty()

    def _draw(self) -> None:
        lines = [f":green[:material/check_circle:] {md(label)} · {secs:.1f} s" for label, secs in self.done]
        if self.current:
            lines.append(f":blue[:material/pending:] **{md(self.current)}**")
        self.box.markdown("  \n".join(lines))

    def stage(self, label: str, frac: float | None = None) -> None:
        now = time.perf_counter()
        if self.current:
            self.done.append((self.current, now - self.t0))
        self.current, self.t0 = label, now
        if frac is not None:
            self.bar.progress(min(max(frac, 0.0), 1.0), text=label)
        self.status.update(label=f"{label}…", state="running", expanded=True)
        self._draw()

    def finish(self, label: str) -> list[tuple[str, float]]:
        if self.current:
            self.done.append((self.current, time.perf_counter() - self.t0))
            self.current = None
        self.bar.progress(1.0, text=label)
        self.status.update(label=label, state="complete", expanded=False)
        self._draw()
        return self.done

    def fail(self, label: str) -> None:
        if self.current:
            self.done.append((self.current + " (stopped)", time.perf_counter() - self.t0))
            self.current = None
        self.status.update(label=label, state="error", expanded=True)
        self._draw()


_ANALYSING = re.compile(r"^Analysing (?P<name>.+) \((?P<k>\d+)/(?P<n>\d+)\)$")


def _live_label(msg: str, names: dict[str, str]) -> str:
    """Translate src.pipeline progress messages into UI copy (same events, nothing added)."""
    m = _ANALYSING.match(msg)
    if m:
        who = names.get(m["name"], m["name"])
        return f"Vision analysis: {who} ({m['k']} of {m['n']})"
    return {
        "Checking images": "Validating photos (format, size, sharpness, duplicates)",
        "Vision analysis complete": "Merging findings across photos and checking vehicle identity",
        "Retrieving prices and building estimate": "Applying repair rules, retrieving prices, costing "
                                                   "and drawing damage overlays",
    }.get(msg, msg)


def build_exports(result) -> dict:
    """JSON + PDF rendered once from the same validated Assessment, keyed by its id."""
    a = result.assessment
    ex = {"assessment_id": a.assessment_id, "json": a.model_dump_json(indent=2), "pdf": b"",
          "pdf_error": None, "pdf_check": None}
    try:
        ex["json"], ex["pdf"] = service.export_assessment(result)
        ex["pdf_check"] = pdf_totals_match(ex["pdf"], a.totals)
    except Exception as exc:  # noqa: BLE001 - JSON stays available; the PDF problem is shown
        log.exception("PDF export failed")
        ex["pdf_error"] = f"{type(exc).__name__}: {exc}"
    return ex


def classify_error(exc: BaseException) -> dict:
    """Readable title/message/hint for any failure. The message is key-redacted."""
    msg = analyse._redact(exc)
    low = msg.lower()
    if isinstance(exc, IntakeError):
        return {"kind": "intake", "title": "The photos could not be used", "message": msg,
                "hint": "Replace the listed files with clear JPG/PNG photos (at least 200 px) and analyze again.",
                "retryable": False}
    if isinstance(exc, analyse.FatalAnalysisError):
        missing = "not set" in low
        return {"kind": "config", "retryable": True, "message": msg,
                "title": "Gemini API key not configured" if missing else "Gemini rejected the request",
                "hint": "Open Connection (top right) to check the key, use Reload configuration after editing "
                        ".env, then retry."}
    if any(m in msg for m in ("429", "RESOURCE_EXHAUSTED")) or "quota" in low or "rate limit" in low:
        return {"kind": "quota", "title": "Gemini quota or rate limit reached", "message": msg, "retryable": True,
                "hint": "Wait a minute and retry. Photos that were already analysed are cached locally and "
                        "are not sent again."}
    if any(m in low for m in ("timed out", "timeout", "deadline", "connection", "unavailable", "503", "502",
                              "504", "network", "getaddrinfo", "ssl")):
        return {"kind": "network", "title": "Couldn't reach Gemini", "message": msg, "retryable": True,
                "hint": "Check the internet connection and retry. Already-analysed photos are cached."}
    if isinstance(exc, analyse.AnalysisError):
        return {"kind": "analysis", "title": "The photos could not be analysed", "message": msg, "retryable": True,
                "hint": "Make sure each photo clearly shows the vehicle, then retry."}
    return {"kind": "unexpected", "title": "Something went wrong during the assessment",
            "message": f"{type(exc).__name__}: {msg}", "retryable": True,
            "hint": "Retry once. If it keeps failing, the server console has the technical details."}


def _finish_ok(w: dict, inputs: dict, result, exports: dict, timings) -> None:
    w.update(result=result, sig=inputs["sig"], exports=exports, view="results", error=None,
             conflict=None, timings=timings)
    st.session_state.overlay_cache = {}
    st.session_state.viewer_image = None


def _finish_error(w: dict, inputs: dict, exc: BaseException) -> None:
    log.error("assessment failed", exc_info=exc)
    err = classify_error(exc)
    err.update(sig=inputs["sig"], inputs=inputs)
    w.update(error=err, view="inputs")
    if err["kind"] == "config":
        st.session_state.api_check = {"ok": False, "stage": "analysis", "detail": err["message"],
                                      "config_sig": config_signature()}


def execute_live(w: dict, inputs: dict, status) -> None:
    """inputs: {"sig", "photo_sig", "photos": [(index, name, bytes, image_id)], "vehicle": VehicleInputs,
    "narrative"}. Writes the outcome into workspace w; never raises."""
    tracker = StageTracker(status, "Starting")
    tmp_dir = tempfile.mkdtemp(prefix="autoinspect_case_")
    try:
        tracker.stage("Preparing photos", 0.01)
        paths, names = [], {}
        for idx, name, data, _ in inputs["photos"]:
            p = Path(tmp_dir) / safe_upload_name(name, idx)
            p.write_bytes(data)
            paths.append(str(p))
            names[p.name] = f"Photo {idx}"
        tracker.stage("Loading pricing index", 0.02)
        retriever = get_cached_retriever()
        v = inputs["vehicle"]

        def progress(msg: str, frac: float) -> None:
            if msg == "Done":        # end of the service call; the next real stage closes the timer
                return
            tracker.stage(_live_label(msg, names), frac)

        result = service.run_live_assessment(
            paths, v.vehicle_info(), accident_description=inputs["narrative"] or None, scope=v.scope(),
            retriever=retriever, progress=progress)
        tracker.stage("Rendering PDF and JSON report", 0.99)
        exports = build_exports(result)
        timings = tracker.finish("Assessment complete")
        _finish_ok(w, inputs, result, exports, timings)
    except VehicleMismatchError as exc:
        tracker.fail("Stopped: the photos may show different vehicles")
        log.warning("vehicle identity conflict: %s", analyse._redact(exc))
        w.update(view="inputs", conflict={
            "photo_sig": inputs["photo_sig"], "status": exc.consistency.get("status", "conflict"),
            "evidence": list(exc.consistency.get("evidence", [])),
            "cues": exc.consistency.get("cues", {}), "method": exc.consistency.get("method", "")})
    except Exception as exc:  # noqa: BLE001 - every failure becomes a readable panel, never a fake result
        tracker.fail("Assessment failed")
        _finish_error(w, inputs, exc)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def execute_sample(w: dict, inputs: dict, status) -> None:
    """inputs: {"sig", "fixture", "vehicle": VehicleInputs}. Saved fixture - no vision call."""
    tracker = StageTracker(status, "Starting")
    try:
        tracker.stage("Loading pricing index", 0.05)
        retriever = get_cached_retriever()
        path = SAMPLES_DIR / inputs["fixture"]
        if not path.is_file():
            raise FileNotFoundError(f"Sample fixture not found: samples/{inputs['fixture']}")
        tracker.stage("Applying repair rules, retrieving prices and costing (saved fixture, no vision call)", 0.3)
        v = inputs["vehicle"]
        result = service.run_sample_assessment(path, vehicle=v.vehicle_info(), scope=v.scope(),
                                               retriever=retriever)
        tracker.stage("Rendering PDF and JSON report", 0.8)
        exports = build_exports(result)
        timings = tracker.finish("Sample assessment complete")
        _finish_ok(w, inputs, result, exports, timings)
    except Exception as exc:  # noqa: BLE001
        tracker.fail("Sample assessment failed")
        _finish_error(w, inputs, exc)
