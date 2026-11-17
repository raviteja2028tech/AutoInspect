"""The two workspaces: New assessment (live photos, default) and Sample cases (offline fixtures)."""
from __future__ import annotations

import re

import streamlit as st

from src import settings

from . import state
from .connection import api_state, index_status
from .html import bullet_list, chip, esc, md, page_header, render, section_title
from .photos import photo_signature, render_photo_panel, summary
from .results import render_results
from .runner import execute_live, execute_sample
from .vehicle import render_vehicle_panel, set_vehicle

STALE_SLOTS = 10      # >= the number of top-level blocks an inputs page renders

SAMPLES = {
    "my_case_v2.json": {
        "title": "Multi-panel damage (legacy output)", "make": "Hyundai", "model": "i20", "year": 2021,
        "variant": "Sportz", "findings": "13 findings",
        "desc": "Saved output of an earlier pipeline version on 3 local photos. The current identity check "
                "flags those photos as likely different vehicles, so use it to explore pricing and reports only.",
    },
    "sample_severe.json": {
        "title": "Severe frontal collision", "make": "Hyundai", "model": "i20", "year": 2020,
        "variant": "Asta", "findings": "5 findings",
        "desc": "Hand-prepared fixture: heavy frontal deformation, broken headlamps, torn bumper.",
    },
    "sample_minor.json": {
        "title": "Minor parking scratches", "make": "Maruti Suzuki", "model": "Swift", "year": 2022,
        "variant": "VXI", "findings": "2 findings",
        "desc": "Hand-prepared fixture: bumper scratch and small door dent. Mostly outside the priced scope.",
    },
    "sample_no_damage.json": {
        "title": "Undamaged control", "make": "Honda", "model": "City", "year": 2021,
        "variant": "ZX", "findings": "0 findings",
        "desc": "Hand-prepared fixture with no findings: checks that no damage produces no charges.",
    },
}


# --------------------------------------------------------------------------- shared bits
def _requirements(items: list[tuple[bool, str]]) -> None:
    """Checklist next to the primary action, so a disabled button always says why."""
    rows = "".join(
        f'<li class="{"ok" if ok else "todo"}"><span class="ai-req-icon" aria-hidden="true">'
        f'{"✓" if ok else "•"}</span>{esc(text)}<span class="ai-sr">{" (done)" if ok else " (to do)"}</span></li>'
        for ok, text in items)
    render(f'<ul class="ai-req">{rows}</ul>')


def _error_panel(mode: str, w: dict) -> None:
    err = w.get("error")
    if not err:
        return
    with st.container(border=True, key=f"card_error_{mode}"):
        render(f'<div class="ai-alert ai-alert--red" role="alert"><p class="ai-alert-title">{esc(err["title"])}</p>'
               f'<p>{esc(err["hint"])}</p></div>')
        with st.expander("Error details"):
            st.code(err["message"], language=None, wrap_lines=True)
        if err.get("retryable") and err.get("inputs"):
            st.button("Retry analysis", icon=":material/refresh:", type="primary", key=f"{mode}_retry",
                      on_click=state.request_run, args=(mode, err["inputs"]))


def _running_view(mode: str, w: dict, title: str, subtitle: str) -> None:
    pending = w.get("pending")
    if not pending:
        # A rerun interrupted the previous run before it stored anything (e.g. the user navigated).
        w.update(view="inputs", interrupted=True)
        st.rerun()
    w["pending"] = None                 # consume first: an interruption can never re-trigger inference
    page_header(title, subtitle, eyebrow="Analysis in progress")
    with st.container(border=True, key=f"card_running_{mode}"):
        if mode == "live":
            photos = st.session_state.photos
            with st.container(horizontal=True, gap="small", key="running_thumbs"):
                for idx, _, _, _ in pending["photos"]:
                    p = photos[idx - 1] if idx - 1 < len(photos) else None
                    with st.container(width=120, gap="xxsmall", key=f"run_thumb_{idx}"):
                        if p and p.get("thumb"):
                            st.image(p["thumb"], width="stretch", alt=f"Photo {idx}")
                        st.caption(f"Photo {idx}")
            st.caption("Photos analysed earlier are read from the local result cache instead of being sent to "
                       "Gemini again; Technical details shows which results were fresh.")
        status = st.status("Starting…", expanded=True)
    # Streamlit keeps the previous run's elements on screen until this run ends. Overwrite the
    # remaining top-level slots so the old (still clickable) input widgets are not shown while
    # the pipeline blocks; the placeholders are empty and vanish when the run finishes.
    for _ in range(STALE_SLOTS):
        st.empty()
    if mode == "live":
        execute_live(w, pending, status)
    else:
        execute_sample(w, pending, status)
    st.rerun()


def _results_ready_banner(mode: str, w: dict) -> None:
    if w["result"] is not None:
        with st.container(border=True, key=f"card_ready_{mode}"):
            c1, c2 = st.columns([3, 1], vertical_alignment="center")
            c1.markdown(":material/task_alt: **Results for these inputs are ready.** Change any input to start a "
                        "new analysis.")
            c2.button("View results", icon=":material/arrow_forward:", type="primary", key=f"{mode}_view_results",
                      on_click=state.show_view, args=(mode, "results"), width="stretch")


# --------------------------------------------------------------------------- New assessment
def render_new_assessment() -> None:
    w = state.ws("live")
    if w["view"] == "running":
        _running_view("live", w, "Analyzing photos", "Each stage below is reported by the pipeline as it runs.")
        return
    if w["view"] == "results" and w["result"] is not None:
        render_results("live")
        return
    w["view"] = "inputs"

    ss = st.session_state
    has_input = bool(ss.photos) or any(ss.get(k) for k in ("live_make", "live_m_make", "live_m_model", "live_narrative"))
    with st.container(horizontal=True, vertical_alignment="bottom", key="live_head"):
        page_header("New assessment", "Upload photos of one vehicle, confirm its details, then run the analysis.")
        if has_input:
            st.button("Start over", icon=":material/restart_alt:", type="tertiary", key="live_start_over",
                      on_click=state.reset_live, help="Remove all photos, vehicle details and results.")
    api = api_state()
    idx = index_status()
    if api == "missing":
        with st.container(border=True, key="card_keymissing"):
            render('<div class="ai-alert ai-alert--amber" role="alert"><p class="ai-alert-title">'
                   'Gemini API key not configured</p><p>Live photo analysis is unavailable until a key is set. '
                   f'Add <code>GEMINI_API_KEY=&lt;your key&gt;</code> to <code>{esc(settings.ENV_FILE)}</code>, '
                   'then open <strong>Connection</strong> (top right) and choose <strong>Reload configuration</strong>. '
                   'You can still prepare photos here or explore a sample case.</p></div>')
            st.button("Explore sample cases", icon=":material/science:", key="keymissing_samples",
                      on_click=state.go, args=(state.NAV_SAMPLES,))
    if not idx.ok:
        st.error(f"The pricing index could not be loaded, so costs cannot be computed: {md(idx.error)}",
                 icon=":material/error:")
    if w.get("interrupted"):
        st.info("The previous analysis was interrupted before it finished, so nothing was saved. "
                "Press Analyze to run it again.", icon=":material/info:")
    # Outcome panels (results ready / identity conflict / error) sit above the inputs so they are
    # the first thing seen after a run; they are filled once the current input signature is known.
    outcome_slot = st.container(key="live_outcome")

    left, right = st.columns([7, 5], gap="medium")
    with left:
        with st.container(border=True, key="card_photos"):
            s = render_photo_panel()
    with right:
        with st.container(border=True, key="card_vehicle"):
            section_title("Vehicle", "Used to match catalog prices for this make, model and year.")
            v = render_vehicle_panel("live")
        with st.container(border=True, key="card_run"):
            section_title("Run analysis")
            narrative = (st.text_area(
                "Accident description (optional)", key="live_narrative", max_chars=600, height=90,
                placeholder="e.g. Reversed into a pole at low speed", persist_state="session",
                help="Used only to flag contradictions with the photos; it never adds findings.") or "").strip()

            photos = st.session_state.photos
            photo_sig = photo_signature(photos)
            sig = state.signature({"photos": photo_sig, "vehicle": v.as_dict(), "narrative": narrative})
            state.sync_inputs(w, sig, photo_sig)
            conflict = w.get("conflict")
            reqs = [
                (s["unique"] >= 1, "At least one usable photo" if s["unique"] < 1 else
                 f"{s['unique']} usable photo{'s' if s['unique'] != 1 else ''}"),
                (v.complete, "Vehicle make, model and year" if not v.complete else f"Vehicle: {v.label()}"),
                (api != "missing", "Gemini API key configured" if api == "missing" else
                 ("Gemini key configured" if api != "verified" else "Gemini key verified")),
            ]
            if not idx.ok:
                reqs.append((False, "Pricing index available"))
            if conflict:
                reqs.append((False, "Photos show one vehicle"))
            ready = all(ok for ok, _ in reqs)
            _requirements(reqs)
            inputs = {"sig": sig, "photo_sig": photo_sig, "vehicle": v, "narrative": narrative,
                      "photos": [(i, p["name"], p["data"], p["image_id"]) for i, p in enumerate(photos, 1)]}
            st.button(f"Analyze {s['unique']} photo{'s' if s['unique'] != 1 else ''}" if s["unique"] else "Analyze photos",
                      type="primary", icon=":material/document_scanner:", key="live_analyze", width="stretch",
                      disabled=not ready or w["result"] is not None, on_click=state.request_run, args=("live", inputs))
            if s["total"] and s["unique"] < 3 and ready:
                st.caption("Fewer than 3 views: the report will flag limited coverage.")
            st.caption("Photos are sent to Google Gemini for analysis when you press Analyze.")

    with outcome_slot:
        _results_ready_banner("live", w)
        if conflict:
            _conflict_panel(conflict)
        _error_panel("live", w)


def _conflict_panel(conflict: dict) -> None:
    ids: dict[str, str] = {}
    for i, p in enumerate(st.session_state.photos, 1):
        if p.get("image_id"):
            ids.setdefault(p["image_id"], f"Photo {i}")

    def name(iid: str) -> str:
        return ids.get(iid, iid)

    cues = conflict.get("cues") or {}
    per_photo: dict[str, list[str]] = {}
    for label, values in cues.items():
        for iid, val in (values or {}).items():
            per_photo.setdefault(name(iid), []).append(f"{label.replace('_', ' ')} {val}")
    evidence = [re.sub(r"IMG-[0-9a-f]{10}", lambda m: name(m.group(0)), e) for e in conflict.get("evidence", [])]
    with st.container(border=True, key="card_conflict"):
        render('<div class="ai-alert ai-alert--red" role="alert"><p class="ai-alert-title">'
               'These photos may show different vehicles</p><p>The analysis stopped before pricing because the '
               'vehicle identity cues disagree. Remove the photos of the other vehicle, then analyze again. Photos '
               'already analysed are cached and are not sent to Gemini twice.</p></div>')
        if per_photo:
            render('<p class="ai-dl-title">What the model saw in each photo</p>' + bullet_list(
                f"{k}: {', '.join(v)}" for k, v in sorted(per_photo.items())))
        elif evidence:
            render('<p class="ai-dl-title">Why</p>' + bullet_list(evidence))
        st.caption(md(conflict.get("method", "")))


# --------------------------------------------------------------------------- Sample cases
def _pick_sample(fname: str) -> None:
    meta = SAMPLES[fname]
    st.session_state.sample_fixture = fname
    set_vehicle("sample", meta["make"], meta["model"], meta["year"], meta["variant"])


def render_samples() -> None:
    w = state.ws("sample")
    ss = st.session_state
    if "sample_manual" not in ss and "sample_make" not in ss and "sample_m_make" not in ss:
        _pick_sample(ss.sample_fixture)
    if w["view"] == "running":
        _running_view("sample", w, "Running sample case", "Saved fixture: no photos are analysed and Gemini is not called.")
        return
    if w["view"] == "results" and w["result"] is not None:
        render_results("sample")
        return
    w["view"] = "inputs"

    page_header("Sample cases", "Saved damage maps for exploring rules, pricing and reports offline. They are not "
                "live results and not validated cases.", eyebrow="Offline demo")
    idx = index_status()
    if not idx.ok:
        st.error(f"The pricing index could not be loaded: {md(idx.error)}", icon=":material/error:")
    outcome_slot = st.container(key="sample_outcome")

    left, right = st.columns([7, 5], gap="medium")
    with left:
        with st.container(border=True, key="card_samples"):
            section_title("Choose a sample", right_html=chip("No Gemini calls", "violet"))
            st.radio("Sample fixture", list(SAMPLES), key="sample_fixture", label_visibility="collapsed",
                     persist_state="session",
                     format_func=lambda f: SAMPLES[f]["title"],
                     captions=[f"{m['make']} {m['model']} {m['year']} · {m['findings']}. {m['desc']}"
                               for m in SAMPLES.values()],
                     on_change=lambda: _pick_sample(st.session_state.sample_fixture))
    with right:
        with st.container(border=True, key="card_sample_vehicle"):
            section_title("Vehicle", "Pre-filled from the fixture. Change it to see how pricing coverage changes.")
            v = render_vehicle_panel("sample")
        with st.container(border=True, key="card_sample_run"):
            section_title("Run sample")
            sig = state.signature({"fixture": ss.sample_fixture, "vehicle": v.as_dict()})
            state.sync_inputs(w, sig)
            reqs = [(v.complete, "Vehicle make, model and year" if not v.complete else f"Vehicle: {v.label()}"),
                    (idx.ok, "Pricing index available")]
            _requirements(reqs)
            st.button("Run sample assessment", type="primary", icon=":material/play_arrow:", key="sample_run",
                      width="stretch", disabled=not all(ok for ok, _ in reqs) or w["result"] is not None,
                      on_click=state.request_run,
                      args=("sample", {"sig": sig, "fixture": ss.sample_fixture, "vehicle": v}))
    with outcome_slot:
        _results_ready_banner("sample", w)
        _error_panel("sample", w)
