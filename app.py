"""AutoInspect — vehicle damage assessment workspace (Streamlit UI; all logic lives in src/).

Launch from the project root (the folder containing this file):
    streamlit run app.py

UI modules live in ui/: pages (New assessment / Sample cases), photos, vehicle, runner,
results, connection, state, style. They call src.service and render its validated Assessment.
"""
from __future__ import annotations

import logging

import streamlit as st

st.set_page_config(
    page_title="AutoInspect · Vehicle damage assessment",
    page_icon=":material/directions_car:",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from ui import state, style  # noqa: E402  (set_page_config must run first)
from ui.connection import API_CHIP, api_state, index_status, render_connection_panel  # noqa: E402
from ui.html import chip, render  # noqa: E402
from ui.pages import render_new_assessment, render_samples  # noqa: E402

log = logging.getLogger("autoinspect.ui")

NAV_LABELS = {state.NAV_NEW: ":material/add_a_photo: New assessment",
              state.NAV_SAMPLES: ":material/science: Sample cases"}


def render_appbar() -> None:
    api = api_state()
    idx = index_status()
    api_text, api_tone = API_CHIP[api]
    chips = [chip(api_text, api_tone, dot=True)]
    if idx.ok:
        if idx.all_synthetic:
            chips.append(chip(f"{idx.records} synthetic demo prices", "amber",
                              title="Every pricing record is an illustrative demo value, not a market quote."))
        else:
            chips.append(chip(f"{idx.records} price records ({idx.synthetic} synthetic)", "neutral"))
        if idx.method != "semantic":
            chips.append(chip("Keyword retrieval", "amber",
                              title="The embedding model is unavailable, so prices are matched by keywords."))
    else:
        chips.append(chip("Pricing index unavailable", "red"))

    with st.container(horizontal=True, horizontal_alignment="distribute", vertical_alignment="center",
                      gap="small", key="appbar"):
        with st.container(horizontal=True, vertical_alignment="center", gap="medium", width="content",
                          key="appbar_left"):
            render('<div class="ai-brand"><div class="ai-logo" role="img" aria-label="AutoInspect logo"></div>'
                   '<div><div class="ai-brand-name">AutoInspect</div>'
                   '<div class="ai-brand-sub">Vehicle damage assessment</div></div></div>', width="content")
            st.segmented_control("Workspace", list(NAV_LABELS), key="nav", required=True,
                                 format_func=NAV_LABELS.get, label_visibility="collapsed")
        with st.container(horizontal=True, vertical_alignment="center", gap="small", width="content",
                          key="appbar_right"):
            render(f'<div class="ai-status" role="status" aria-label="System status">{"".join(chips)}</div>',
                   width="content")
            with st.popover("Connection", icon=":material/settings_ethernet:"):
                render_connection_panel()


def _reset_workspace() -> None:
    state.reset_live()
    st.session_state._render_error = None


def main() -> None:
    style.inject()
    state.init()
    try:
        render_appbar()
        if st.session_state.nav == state.NAV_SAMPLES:
            render_samples()
        else:
            render_new_assessment()
        st.session_state._render_error = None
    except Exception as exc:  # noqa: BLE001 - readable panel instead of a traceback; details go to the log
        log.exception("UI render failed")
        st.session_state._render_error = f"{type(exc).__name__}: {exc}"
        st.error("This view could not be displayed. Your inputs are kept; try again, or reset the workspace. "
                 "Technical details were written to the server console.", icon=":material/error:")
        st.button("Reset workspace", on_click=_reset_workspace, key="render_error_reset")


main()
