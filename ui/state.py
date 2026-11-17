"""Session state: one workspace per mode, input signatures, reset.

A workspace holds the result for ONE set of inputs. Its ``sig`` is a hash of everything that
can change the assessment (photos, vehicle, pricing scope, description, fixture). When the
current inputs no longer match ``sig`` the result and its downloads are discarded, so a stale
estimate or file can never be shown next to new inputs. Inference only ever runs from an
explicit Analyze/Run click (``request_run``); rendering never triggers it.
"""
from __future__ import annotations

import hashlib
import json

import streamlit as st

NAV_NEW = "new"
NAV_SAMPLES = "samples"
MODES = ("live", "sample")
DEFAULT_FIXTURE = "my_case_v2.json"


def _new_workspace() -> dict:
    return {
        "view": "inputs",      # inputs | running | results
        "pending": None,       # input snapshot queued by an explicit click
        "interrupted": False,
        "result": None,        # src.service.AssessmentResult
        "sig": None,           # input signature the result belongs to
        "exports": None,       # {"assessment_id", "json", "pdf", "pdf_error", "pdf_check"}
        "error": None,         # {"title", "message", "hint", "kind", "retryable", "sig", "inputs"}
        "conflict": None,      # vehicle-identity conflict for a photo set
        "timings": [],         # [(stage label, seconds)] of the last run
    }


def init() -> None:
    defaults = {
        "nav": NAV_NEW,
        "ws_live": _new_workspace(),
        "ws_sample": _new_workspace(),
        "photos": [],
        "uploader_gen": 0,
        "upload_notice": None,
        "api_check": None,
        "viewer_image": None,
        "overlay_cache": {},
        "sample_fixture": DEFAULT_FIXTURE,
        "_render_error": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def ws(mode: str) -> dict:
    return st.session_state[f"ws_{mode}"]


def signature(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def clear_result(w: dict) -> None:
    w.update(result=None, sig=None, exports=None, timings=[])
    st.session_state.overlay_cache = {}
    st.session_state.viewer_image = None


def sync_inputs(w: dict, sig: str, photo_sig: str | None = None) -> None:
    """Drop results, errors and conflicts that belong to different inputs than the current ones."""
    if w["result"] is not None and w["sig"] != sig:
        clear_result(w)
    if w["error"] and w["error"].get("sig") != sig:
        w["error"] = None
    if w["conflict"] and w["conflict"].get("photo_sig") != photo_sig:
        w["conflict"] = None


def request_run(mode: str, inputs: dict) -> None:
    """Button callback: queue exactly one run for these inputs."""
    w = ws(mode)
    w.update(pending=inputs, view="running", error=None, interrupted=False)


def show_view(mode: str, view: str) -> None:
    ws(mode)["view"] = view


LIVE_WIDGET_PREFIXES = ("live_",)


def reset_live() -> None:
    """'New assessment': forget photos, vehicle, description and results for live mode."""
    ss = st.session_state
    for key in [k for k in ss.keys() if isinstance(k, str) and k.startswith(LIVE_WIDGET_PREFIXES)]:
        del ss[key]
    ss.photos = []
    ss.uploader_gen += 1
    ss.upload_notice = None
    ss.ws_live = _new_workspace()
    ss.overlay_cache = {}
    ss.viewer_image = None
    ss.nav = NAV_NEW


def go(nav: str) -> None:
    st.session_state.nav = nav
