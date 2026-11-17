"""Gemini key/connection status and the shared pricing index (no secrets are ever displayed).

Status wording is deliberate: a key that is merely present is "configured, not verified";
"verified" appears only after a successful verify_connection() for the CURRENT key/model/API
version. Nothing in the UI claims a live connection that has not been checked.
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass

import streamlit as st

from src import analyse, service, settings
from src.kb.retrieve import Retriever

from .html import code, md

log = logging.getLogger("autoinspect.ui")


# --------------------------------------------------------------------------- pricing index
@st.cache_resource(show_spinner="Loading the pricing index (the first run may download the embedding model)…")
def get_cached_retriever() -> Retriever:
    """Pricing corpus + vector index, loaded once per server process (shared with src.service)."""
    return service.get_retriever(allow_lexical_fallback=True)


@dataclass
class IndexStatus:
    ok: bool
    records: int = 0
    method: str = ""
    synthetic: int = 0
    error: str = ""

    @property
    def all_synthetic(self) -> bool:
        return self.ok and self.records > 0 and self.synthetic == self.records


def index_status() -> IndexStatus:
    try:
        r = get_cached_retriever()
    except Exception as exc:  # noqa: BLE001 - shown as a readable status; app keeps running
        log.exception("pricing index failed to load")
        return IndexStatus(False, error=f"{type(exc).__name__}: {analyse._redact(exc)}")
    recs = r.corpus.records
    return IndexStatus(True, len(recs), r.method, sum(1 for x in recs if x.data_quality == "synthetic_demo"))


# --------------------------------------------------------------------------- Gemini key
def config_signature() -> str:
    """Changes when the key, model or API version changes (the key itself is never stored)."""
    key = settings.get_api_key() or ""
    return f"{hashlib.sha256(key.encode()).hexdigest()[:12]}|{analyse.MODEL}|{analyse.API_VERSION}"


def api_state() -> str:
    """'missing' | 'configured' (not verified) | 'verified' | 'failed' for the current key/config."""
    if not settings.api_key_status().configured:
        return "missing"
    chk = st.session_state.get("api_check")
    if not chk or chk.get("config_sig") != config_signature():
        return "configured"
    return "verified" if chk.get("ok") else "failed"


API_CHIP = {
    "missing": ("Gemini key missing", "red"),
    "configured": ("Gemini key not verified", "neutral"),
    "verified": ("Gemini verified", "green"),
    "failed": ("Gemini check failed", "red"),
}


def _reload_config() -> None:
    settings.reload()
    analyse.refresh_settings()
    st.session_state.api_check = None


def _verify() -> None:
    res = analyse.verify_connection(generate=False)
    res["config_sig"] = config_signature()
    st.session_state.api_check = res


def render_connection_panel() -> None:
    """Key source, model and API version, diagnostics, Reload and Verify (inside a popover)."""
    status = settings.api_key_status()
    state = api_state()
    st.markdown("**Gemini vision**")
    if status.configured:
        st.markdown(f"Key configured via {code(status.variable)} from the {md(status.source)} (value hidden).")
    else:
        st.markdown(f"Key not configured: {md(status.problem)}")
    st.markdown(f"Model {code(analyse.MODEL)} · API {code(analyse.API_VERSION)} · timeout {analyse.TIMEOUT_S:g} s")
    st.caption(f"Project .env: {md(status.env_file)} ({'found' if status.env_file_exists else 'missing'}; "
               f"{md(status.env_file_status)})")

    chk = st.session_state.get("api_check") or {}
    if state == "verified":
        st.success(f"Verified: {md(chk.get('detail'))}", icon=":material/check_circle:")
    elif state == "failed":
        st.error(f"Check failed ({md(chk.get('stage'))}): {md(chk.get('detail'))}", icon=":material/error:")
    elif state == "configured":
        st.info("A key is configured but has not been checked with Google in this session.",
                icon=":material/info:")
    for hint in settings.diagnostics():
        st.warning(md(hint), icon=":material/warning:")

    c1, c2 = st.columns(2)
    c1.button("Reload configuration", icon=":material/refresh:", on_click=_reload_config, width="stretch",
              help="Re-reads the project .env without restarting. Variables set in the launching terminal "
                   "cannot change until the server restarts.", key="conn_reload")
    if c2.button("Verify key", icon=":material/verified:", width="stretch",
                 disabled=not status.configured, key="conn_verify",
                 help="Lists models with your key. No image is analysed and no generation request is sent."):
        with st.spinner("Checking the key with Google…"):
            _verify()
        st.rerun()
    st.caption("Command-line check: python scripts/check_config.py --verify")
