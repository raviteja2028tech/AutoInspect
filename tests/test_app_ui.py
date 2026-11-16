"""Headless Streamlit checks of app.py (AppTest): no browser, no network, stub retrieval."""
import os

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

from src import service  # noqa: E402

from .conftest import ROOT  # noqa: E402


@pytest.fixture
def app(monkeypatch, retriever):
    import streamlit as st
    st.cache_resource.clear()
    monkeypatch.setattr(service, "_retriever", retriever)      # stub embeddings, temp index
    for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=90)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _button(at, label):
    matches = [b for b in at.button if b.label == label]
    assert matches, f"no button {label!r}; have {[b.label for b in at.button]}"
    return matches[0]


def _run_sample(at):
    _button(at, "Run Assessment →").click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state.step == 3
    return at.session_state.result.assessment


def test_sample_flow_produces_matching_exports(app):
    a = _run_sample(app)
    assert a.mode == "sample_fixture"
    ex = app.session_state.exports
    assert ex["assessment_id"] == a.assessment_id and ex["pdf"].startswith(b"%PDF")
    assert '"mode": "sample_fixture"' in ex["json"]
    assert not app.session_state.error


def test_new_run_after_back_never_reuses_old_downloads(app):
    first = _run_sample(app)
    _button(app, "← Back to Inputs").click().run()
    app.button(key="scen_sample_minor.json").click().run()
    second = _run_sample(app)
    assert second.assessment_id != first.assessment_id
    assert app.session_state.exports["assessment_id"] == second.assessment_id


def test_live_mode_without_key_is_explicit(app):
    mode = [s for s in app.selectbox if s.label == "Inspection Mode"][0]
    mode.set_value("Live Photo Intake").run()
    assert not app.exception, [e.value for e in app.exception]
    html_blob = " ".join(m.value for m in app.markdown)
    assert "key missing" in html_blob and "not configured" in html_blob
    assert "connected" not in html_blob.lower().replace("not connected", "")
    assert os.environ.get("GEMINI_API_KEY") is None
