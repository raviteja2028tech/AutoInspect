"""AutoInspect — vehicle damage assessment workspace (Streamlit UI only; logic lives in src/).

Launch from the project root (the folder containing this file):
    streamlit run app.py
"""
from __future__ import annotations

import hashlib
import html
import json
import shutil
import tempfile
import traceback
from decimal import Decimal
from pathlib import Path

import streamlit as st

# ── Project Backend Imports ──────────────────────────────────────────────────
from src import analyse, settings
from src.contracts import (
    Assessment,
    Observation,
    PricingScope,
    VehicleInfo,
)
from src.kb.retrieve import Retriever
from src.kb.vehicles import (
    PricingCoverage,
    check_pricing_coverage,
    get_manufacturers,
    get_models_for_make,
    get_variants_for_model_year,
    get_years_for_model,
    normalize_make,
    search_models,
)
from src.overlay import draw_overlay
from src.intake import safe_upload_name
from src.pipeline import VehicleMismatchError
from src.service import (
    AssessmentResult,
    export_assessment,
    get_retriever,
    run_live_assessment,
    run_sample_assessment,
)

PROJECT_ROOT = settings.PROJECT_ROOT
SAMPLES_DIR = PROJECT_ROOT / "samples"

# ═════════════════════════════════════════════════════════════════════════════
# Page Configuration & Global Styles
# ═════════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="AutoInspect — Vehicle Damage Assessment",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Custom Scoped CSS for Professional Automotive Inspection Workspace
st.markdown(
    """
<style>
/* ── Reset & Typography ─────────────────────────────────────── */
:root {
    --primary: #2563EB;
    --primary-hover: #1D4ED8;
    --navy-900: #0F172A;
    --navy-800: #1E293B;
    --slate-700: #334155;
    --slate-600: #475569;
    --slate-500: #64748B;
    --slate-200: #E2E8F0;
    --slate-100: #F1F5F9;
    --slate-50: #F8FAFC;
    --amber-600: #D97706;
    --amber-100: #FEF3C7;
    --red-600: #DC2626;
    --red-100: #FEE2E2;
    --green-600: #16A34A;
    --green-100: #DCFCE7;
    --purple-600: #7C3AED;
    --purple-100: #F3E8FF;
}

body, [data-testid="stAppViewContainer"] {
    background-color: var(--slate-50);
    color: var(--navy-900);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}

/* Hide default streamlit header decoration to keep workspace clean */
header[data-testid="stHeader"] {
    background: transparent;
}

/* ── Top Bar / Header ───────────────────────────────────────── */
.ai-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 24px;
    background: #FFFFFF;
    border: 1px solid var(--slate-200);
    border-radius: 12px;
    box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
    margin-bottom: 20px;
}
.ai-brand {
    display: flex;
    align-items: center;
    gap: 12px;
}
.ai-logo {
    width: 38px;
    height: 38px;
    background: var(--primary);
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #FFFFFF;
    font-weight: 700;
    font-size: 20px;
    letter-spacing: -0.5px;
}
.ai-title-wrap {
    display: flex;
    flex-direction: column;
}
.ai-title {
    font-size: 20px;
    font-weight: 700;
    color: var(--navy-900);
    line-height: 1.2;
    margin: 0;
}
.ai-subtitle {
    font-size: 13px;
    color: var(--slate-500);
    margin: 0;
}
.ai-status-group {
    display: flex;
    align-items: center;
    gap: 10px;
}
.ai-status-pill {
    font-size: 12px;
    font-weight: 500;
    padding: 4px 10px;
    border-radius: 9999px;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    border: 1px solid var(--slate-200);
    background: var(--slate-100);
    color: var(--slate-700);
}
.ai-status-pill.online {
    background: var(--green-100);
    color: var(--green-600);
    border-color: #BBF7D0;
}
.ai-status-pill.sample {
    background: var(--purple-100);
    color: var(--purple-600);
    border-color: #E9D5FF;
}

/* ── Stepper Navigation ─────────────────────────────────────── */
.ai-stepper {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
    margin-bottom: 24px;
}
.ai-step-card {
    background: #FFFFFF;
    border: 1px solid var(--slate-200);
    border-radius: 10px;
    padding: 12px 18px;
    display: flex;
    align-items: center;
    gap: 12px;
    transition: all 0.15s ease;
}
.ai-step-card.active {
    border-color: var(--primary);
    background: #FFFFFF;
    box-shadow: 0 0 0 1.5px var(--primary);
}
.ai-step-card.completed {
    border-color: #CBD5E1;
    background: var(--slate-50);
}
.ai-step-num {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    background: var(--slate-100);
    color: var(--slate-600);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 13px;
    font-weight: 600;
}
.ai-step-card.active .ai-step-num {
    background: var(--primary);
    color: #FFFFFF;
}
.ai-step-card.completed .ai-step-num {
    background: var(--green-600);
    color: #FFFFFF;
}
.ai-step-text {
    display: flex;
    flex-direction: column;
}
.ai-step-label {
    font-size: 14px;
    font-weight: 600;
    color: var(--navy-900);
    line-height: 1.2;
}
.ai-step-sub {
    font-size: 11px;
    color: var(--slate-500);
}

/* ── Surfaces & Cards ───────────────────────────────────────── */
.ai-card {
    background: #FFFFFF;
    border: 1px solid var(--slate-200);
    border-radius: 12px;
    padding: 20px;
    box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
    margin-bottom: 20px;
}
.ai-card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--slate-100);
}
.ai-card-title {
    font-size: 16px;
    font-weight: 700;
    color: var(--navy-900);
    margin: 0;
}
.ai-card-subtitle {
    font-size: 13px;
    color: var(--slate-500);
    margin: 0;
}

/* ── Metric Display ─────────────────────────────────────────── */
.ai-cost-hero {
    background: linear-gradient(180deg, #FFFFFF 0%, var(--slate-50) 100%);
    border: 1px solid var(--slate-200);
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 16px;
}
.ai-cost-label {
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--slate-500);
    margin-bottom: 4px;
}
.ai-cost-value {
    font-size: 32px;
    font-weight: 800;
    color: var(--navy-900);
    letter-spacing: -0.5px;
    line-height: 1.1;
}
.ai-cost-notes {
    font-size: 12px;
    color: var(--slate-600);
    margin-top: 6px;
}

/* ── Action Counters & Badges ───────────────────────────────── */
.ai-badge-row {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin-bottom: 16px;
}
.ai-badge {
    padding: 6px 12px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 600;
    display: inline-flex;
    align-items: center;
    gap: 6px;
}
.ai-badge-replace {
    background: var(--red-100);
    color: var(--red-600);
    border: 1px solid #FECACA;
}
.ai-badge-repair {
    background: #DBEAFE;
    color: #1E40AF;
    border: 1px solid #BFDBFE;
}
.ai-badge-inspect {
    background: var(--amber-100);
    color: var(--amber-600);
    border: 1px solid #FDE68A;
}

/* ── Notice Callouts ────────────────────────────────────────── */
.ai-notice {
    padding: 12px 16px;
    border-radius: 8px;
    font-size: 13px;
    line-height: 1.45;
    margin-bottom: 16px;
    border: 1px solid transparent;
}
.ai-notice-info {
    background: #EFF6FF;
    border-color: #BFDBFE;
    color: #1E40AF;
}
.ai-notice-amber {
    background: #FFFBEB;
    border-color: #FDE68A;
    color: #92400E;
}
.ai-notice-red {
    background: #FEF2F2;
    border-color: #FECACA;
    color: #991B1B;
}

/* ── Clean Streamlit Form Tweaks ────────────────────────────── */
div[data-testid="stTextInput"] label,
div[data-testid="stNumberInput"] label,
div[data-testid="stSelectbox"] label,
div[data-testid="stTextArea"] label {
    font-size: 13px !important;
    font-weight: 600 !important;
    color: var(--slate-700) !important;
}

button[kind="primary"] {
    background-color: var(--primary) !important;
    border-color: var(--primary) !important;
    font-weight: 600 !important;
    padding: 0.5rem 1.25rem !important;
    border-radius: 8px !important;
}
button[kind="primary"]:hover {
    background-color: var(--primary-hover) !important;
}

/* Table styles */
.ai-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
}
.ai-table th {
    text-align: left;
    padding: 10px 12px;
    background: var(--slate-100);
    color: var(--slate-600);
    font-weight: 600;
    border-bottom: 1px solid var(--slate-200);
}
.ai-table td {
    padding: 10px 12px;
    border-bottom: 1px solid var(--slate-200);
    color: var(--navy-900);
}
.ai-table tr:hover td {
    background: var(--slate-50);
}
</style>
""",
    unsafe_allow_html=True,
)


# ═════════════════════════════════════════════════════════════════════════════
# Helpers & Utilities
# ═════════════════════════════════════════════════════════════════════════════
def format_inr(val: int | float | Decimal | None) -> str:
    """Format numbers into authentic Indian currency grouping (Lakhs & Crores)."""
    if val is None:
        return "Not available"
    n = int(round(val))
    s = str(abs(n))
    if len(s) <= 3:
        res = s
    else:
        last3 = s[-3:]
        rem = s[:-3]
        groups = []
        while len(rem) > 2:
            groups.append(rem[-2:])
            rem = rem[:-2]
        if rem:
            groups.append(rem)
        groups.reverse()
        res = ",".join(groups) + "," + last3
    return f"₹{res}" if n >= 0 else f"-₹{res}"


@st.cache_resource(show_spinner="Loading pricing index (first run downloads the embedding model)...")
def get_cached_retriever() -> Retriever:
    """Load the pricing corpus + vector index once per server process (shared with src.service)."""
    return get_retriever(allow_lexical_fallback=True)


def key_status():
    return settings.api_key_status()


def api_check_state() -> str:
    """'missing' | 'configured' (not verified) | 'verified' | 'failed' for the current key/config."""
    status = key_status()
    if not status.configured:
        return "missing"
    chk = st.session_state.get("api_check")
    if not chk or chk.get("config_sig") != config_signature():
        return "configured"
    return "verified" if chk.get("ok") else "failed"


def config_signature() -> str:
    """Changes when the key, model or API version changes (key itself never stored)."""
    key = settings.get_api_key() or ""
    raw = f"{hashlib.sha256(key.encode()).hexdigest()[:12]}|{analyse.MODEL}|{analyse.API_VERSION}"
    return raw


# Scenario metadata dictionary for clean scenario cards
SCENARIO_CARDS = {
    "my_case_v2.json": {
        "title": "Multi-Photo Legacy Output",
        "make": "Hyundai",
        "model": "i20",
        "year": 2021,
        "variant": "Sportz",
        "desc": "Saved output of an earlier pipeline version on 3 local photos that the identity check "
        "flags as likely DIFFERENT vehicles. Demonstrates pricing/report only.",
        "findings_count": "13 findings",
        "views": "Front, Left, Rear, Close-up",
        "badge": "Legacy fixture",
    },
    "sample_severe.json": {
        "title": "Severe Frontal Collision",
        "make": "Hyundai",
        "model": "i20",
        "year": 2020,
        "variant": "Asta",
        "desc": "Heavy frontal deformation with shattered headlamps and torn bumper.",
        "findings_count": "5 severe findings",
        "views": "Front, Left, Rear",
        "badge": "Fixture",
    },
    "sample_minor.json": {
        "title": "Minor Parking Scratches",
        "make": "Maruti",
        "model": "Swift",
        "year": 2022,
        "variant": "VXI",
        "desc": "Surface scratch and minor dent on bumper suitable for local repair.",
        "findings_count": "2 minor findings",
        "views": "Rear, Front, Right",
        "badge": "Fixture",
    },
    "sample_no_damage.json": {
        "title": "Undamaged Control Vehicle",
        "make": "Honda",
        "model": "City",
        "year": 2021,
        "variant": "ZX",
        "desc": "Fixture with no findings: checks that no damage produces no charges.",
        "findings_count": "0 findings",
        "views": "Front, Left, Rear",
        "badge": "Fixture",
    },
}


# ═════════════════════════════════════════════════════════════════════════════
# Session State Management
# ═════════════════════════════════════════════════════════════════════════════
def init_session_state():
    defaults = {
        "step": 1,  # 1: Input, 2: Analyze, 3: Review
        "mode": "sample",  # 'sample' or 'live'
        "selected_scenario": "my_case_v2.json",
        "result": None,
        "error": None,
        "confirm_same_vehicle": False,
        "mismatch_conflict": None,
        "active_image_id": None,
        "show_overlays": True,
        "filter_component": "All findings",
        "uploaded_files_data": [],  # list of (name, bytes)
        "input_hash": None,
        "error_detail": None,
        "exports": None,  # {"assessment_id", "json", "pdf", "pdf_error"} for the CURRENT result
        "api_check": None,  # last verify_connection() result + config signature
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


init_session_state()


def reset_assessment():
    """Reset the current assessment and return to Step 1."""
    st.session_state.result = None
    st.session_state.exports = None
    st.session_state.error = None
    st.session_state.error_detail = None
    st.session_state.mismatch_conflict = None
    st.session_state.step = 1


# ═════════════════════════════════════════════════════════════════════════════
# Header Bar Component
# ═════════════════════════════════════════════════════════════════════════════
def render_header():
    current_mode = st.session_state.get("mode", "sample")
    state = api_check_state()
    red = 'style="background:#FEE2E2; color:#991B1B; border: 1px solid #FECACA;"'
    amber = 'style="background:#FEF3C7; color:#92400E; border: 1px solid #FDE68A;"'

    if current_mode == "sample":
        api_badge = '<span class="ai-status-pill sample">○ Vision API: not used (Sample mode)</span>'
    elif state == "missing":
        api_badge = f'<span class="ai-status-pill" {red}>⚠ Vision API: key missing</span>'
    elif state == "configured":
        api_badge = f'<span class="ai-status-pill" {amber}>● Vision API: key configured · not verified</span>'
    elif state == "verified":
        api_badge = '<span class="ai-status-pill online">● Vision API: connection verified</span>'
    else:
        api_badge = f'<span class="ai-status-pill" {red}>⚠ Vision API: connection check failed</span>'

    try:
        retriever = get_cached_retriever()
        n_rec = len(retriever.corpus.records)
        if retriever.method == "semantic":
            rag_badge = f'<span class="ai-status-pill online">● RAG: {n_rec} records (semantic)</span>'
        else:
            rag_badge = (f'<span class="ai-status-pill" {amber}>● RAG: {n_rec} records '
                         f'({html.escape(retriever.method)} - not semantic)</span>')
    except Exception as exc:  # noqa: BLE001 - shown to the user, app keeps running
        rag_badge = f'<span class="ai-status-pill" {red}>⚠ RAG unavailable</span>'
        st.session_state.error = f"Pricing index could not be loaded: {exc}"

    col1, col2 = st.columns([7, 3])
    with col1:
        st.markdown(
            f"""
        <div class="ai-header">
            <div class="ai-brand">
                <div class="ai-logo">AI</div>
                <div class="ai-title-wrap">
                    <h1 class="ai-title">AutoInspect</h1>
                    <p class="ai-subtitle">Vehicle Damage Assessment & Grounded Cost Estimation</p>
                </div>
            </div>
            <div class="ai-status-group">
                {rag_badge}
                {api_badge}
            </div>
        </div>
        """,
            unsafe_allow_html=True,
        )

    with col2:
        top_btn_cols = st.columns([1, 1])
        with top_btn_cols[0]:
            mode_choice = st.selectbox(
                "Inspection Mode",
                ["Sample Fixtures", "Live Photo Intake"],
                index=0 if st.session_state.mode == "sample" else 1,
                label_visibility="collapsed",
            )
            new_mode = (
                "sample" if mode_choice == "Sample Fixtures" else "live"
            )
            if new_mode != st.session_state.mode:
                st.session_state.mode = new_mode
                reset_assessment()
                st.rerun()

        with top_btn_cols[1]:
            if st.button("New Assessment", use_container_width=True):
                reset_assessment()
                st.rerun()


# ═════════════════════════════════════════════════════════════════════════════
# Stepper Navigation Component
# ═════════════════════════════════════════════════════════════════════════════
def render_stepper():
    current_step = st.session_state.step
    s1_class = (
        "active"
        if current_step == 1
        else ("completed" if current_step > 1 else "")
    )
    s2_class = (
        "active"
        if current_step == 2
        else ("completed" if current_step > 2 else "")
    )
    s3_class = "active" if current_step == 3 else ""

    s1_icon = "✓" if current_step > 1 else "1"
    s2_icon = "✓" if current_step > 2 else "2"
    s3_icon = "3"

    st.markdown(
        f"""
    <div class="ai-stepper">
        <div class="ai-step-card {s1_class}">
            <div class="ai-step-num">{s1_icon}</div>
            <div class="ai-step-text">
                <span class="ai-step-label">Vehicle & Evidence</span>
                <span class="ai-step-sub">Select scenario or upload photos</span>
            </div>
        </div>
        <div class="ai-step-card {s2_class}">
            <div class="ai-step-num">{s2_icon}</div>
            <div class="ai-step-text">
                <span class="ai-step-label">AI Analysis</span>
                <span class="ai-step-sub">Vision, fusion & RAG costing</span>
            </div>
        </div>
        <div class="ai-step-card {s3_class}">
            <div class="ai-step-num">{s3_icon}</div>
            <div class="ai-step-text">
                <span class="ai-step-label">Review & Export</span>
                <span class="ai-step-sub">Evidence, cost audit & reports</span>
            </div>
        </div>
    </div>
    """,
        unsafe_allow_html=True,
    )


# ═════════════════════════════════════════════════════════════════════════════
# Step 1: Input & Configuration
# ═════════════════════════════════════════════════════════════════════════════
def render_pricing_coverage_card(coverage: PricingCoverage):
    """Display real-time visual feedback on knowledge base pricing coverage for the vehicle."""
    if coverage.status == "full":
        badge_style = "background: #DCFCE7; color: #15803D; border: 1px solid #BBF7D0;"
        icon = "●"
        box_style = "background: #F0FDF4; border: 1px solid #BBF7D0; color: #166534;"
    elif coverage.status == "partial":
        badge_style = "background: #FEF3C7; color: #B45309; border: 1px solid #FDE68A;"
        icon = "◐"
        box_style = "background: #FFFBEB; border: 1px solid #FDE68A; color: #92400E;"
    elif coverage.status == "unpriced_recognized":
        badge_style = "background: #EDE9FE; color: #6D28D9; border: 1px solid #DDD6FE;"
        icon = "○"
        box_style = "background: #F5F3FF; border: 1px solid #DDD6FE; color: #5B21B6;"
    else:  # unverified_manual
        badge_style = "background: #F1F5F9; color: #475569; border: 1px solid #CBD5E1;"
        icon = "○"
        box_style = "background: #F8FAFC; border: 1px solid #E2E8F0; color: #334155;"

    components_preview = ""
    if coverage.priced_components:
        comp_tags = " ".join(
            f"<code style='background: rgba(0,0,0,0.05); padding: 2px 5px; border-radius: 3px; font-size: 11px;'>{c}</code>"
            for c in coverage.priced_components[:8]
        )
        if len(coverage.priced_components) > 8:
            comp_tags += f" <span style='font-size: 11px; opacity: 0.8;'>+{len(coverage.priced_components)-8} more</span>"
        components_preview = f"<div style='margin-top: 6px; font-size: 11px;'><strong>Priced Components:</strong> {comp_tags}</div>"

    st.markdown(
        f"""
        <div style="{box_style} padding: 12px 16px; border-radius: 8px; margin-top: 12px; margin-bottom: 12px; font-size: 13px; line-height: 1.45;">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px;">
                <span style="font-weight: 700; display: inline-flex; align-items: center; gap: 6px;">
                    {icon} {html.escape(coverage.status_label)}
                </span>
                <span style="{badge_style} padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;">
                    {coverage.record_count} Records
                </span>
            </div>
            <div style="font-size: 12px; opacity: 0.95;">
                {html.escape(coverage.message)}
            </div>
            {components_preview}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_vehicle_selector(
    prefix: str = "live",
    default_make: str = "Hyundai",
    default_model: str = "i20",
    default_year: int = 2023,
    default_variant: str = "Sportz",
) -> tuple[str, str, int, str]:
    """Interactive vehicle selector with Indian 2022-2026 catalog, cascading dependent selectors,
    quick alias/model search, manual fallback, and real-time pricing coverage.
    """
    entry_method = st.radio(
        "Vehicle Selection Method",
        ["Verified Indian Catalog (2022–2026)", "Manual Entry / Other Model"],
        key=f"{prefix}_entry_method",
        horizontal=True,
    )

    if entry_method == "Verified Indian Catalog (2022–2026)":
        # Quick Search bar for direct alias/model lookup
        q_search = st.text_input(
            "Quick Search Model or Alias",
            placeholder="Type e.g. 'Nexon', 'Swift', 'Baleno', 'Seltos', 'Brezza', 'XUV700'...",
            key=f"{prefix}_search_input",
            help="Instant model search across all 13 Indian manufacturers and verified nameplate aliases.",
        )

        if q_search.strip():
            matches = search_models(q_search.strip())
            if matches:
                st.caption(f"Found {len(matches)} matching model(s):")
                m_cols = st.columns(min(len(matches), 4))
                for idx, m_rec in enumerate(matches[:4]):
                    with m_cols[idx]:
                        if st.button(
                            f"{m_rec.make} {m_rec.model}",
                            key=f"{prefix}_quick_sel_{m_rec.make}_{m_rec.model}",
                            use_container_width=True,
                        ):
                            st.session_state[f"{prefix}_cat_make"] = m_rec.make
                            st.session_state[f"{prefix}_cat_model"] = m_rec.model
                            avail_yrs = get_years_for_model(m_rec.make, m_rec.model)
                            st.session_state[f"{prefix}_cat_year"] = avail_yrs[0] if avail_yrs else 2024
                            st.rerun()
            else:
                st.caption(f"No models found matching '{q_search.strip()}'. Use the selectors below or switch to Manual Entry.")

        col_make, col_model, col_year, col_variant = st.columns(4)

        # 1. Manufacturer
        makes = get_manufacturers()
        make_key = f"{prefix}_cat_make"
        # Session state drives these widgets (no index=/value=), which avoids Streamlit's
        # "default value but also set via Session State" conflict.
        norm_cur_make = normalize_make(st.session_state.get(make_key, default_make))
        st.session_state[make_key] = (
            norm_cur_make
            if norm_cur_make in makes
            else ("Hyundai" if "Hyundai" in makes else makes[0])
        )

        with col_make:
            sel_make = st.selectbox(
                "Manufacturer",
                options=makes,
                key=make_key,
                help="13 mainstream Indian automotive manufacturers verified for 2022–2026 sales.",
            )

        # 2. Model
        models = get_models_for_make(sel_make)
        model_key = f"{prefix}_cat_model"
        if st.session_state.get(model_key) not in models:
            st.session_state[model_key] = (
                default_model if default_model in models else models[0]
            )

        with col_model:
            sel_model = st.selectbox(
                "Model",
                options=models,
                key=model_key,
                help=f"Active models sold in India under {sel_make} during 2022–2026.",
            )

        # 3. Model Year
        years = get_years_for_model(sel_make, sel_model)
        year_key = f"{prefix}_cat_year"
        if st.session_state.get(year_key) not in years:
            st.session_state[year_key] = (
                default_year if default_year in years else years[0]
            )

        with col_year:
            sel_year = st.selectbox(
                "Model Year",
                options=years,
                key=year_key,
                help=f"Sales calendar years verified for {sel_make} {sel_model}.",
            )

        # 4. Variant
        variants = get_variants_for_model_year(sel_make, sel_model, sel_year)
        variant_choices = ["[Base / Unspecified]"] + variants + ["[Custom / Unlisted Trim]"]
        var_key = f"{prefix}_cat_var_choice"
        if st.session_state.get(var_key) not in variant_choices:
            st.session_state[var_key] = (
                default_variant if default_variant in variant_choices else variant_choices[0]
            )

        with col_variant:
            sel_variant_choice = st.selectbox(
                "Variant / Trim (Optional)",
                options=variant_choices,
                key=var_key,
                help="Trim specifications and powertrain variants verified for this model year.",
            )

        if sel_variant_choice == "[Custom / Unlisted Trim]":
            sel_variant = st.text_input(
                "Enter Trim Name",
                value="",
                placeholder="e.g. Turbo Edition, Dark, Anniversary...",
                key=f"{prefix}_cat_custom_trim",
            )
        elif sel_variant_choice == "[Base / Unspecified]":
            sel_variant = ""
        else:
            sel_variant = sel_variant_choice

        final_make = sel_make
        final_model = sel_model
        final_year = int(sel_year)
        final_variant = sel_variant

    else:
        # Manual entry mode
        c1, c2, c3, c4 = st.columns(4)
        for suffix, default in (("make", default_make), ("model", default_model),
                                ("year", int(default_year)), ("variant", default_variant)):
            st.session_state.setdefault(f"{prefix}_man_{suffix}", default)
        with c1:
            final_make = st.text_input("Make", key=f"{prefix}_man_make")
        with c2:
            final_model = st.text_input("Model", key=f"{prefix}_man_model")
        with c3:
            final_year = int(
                st.number_input(
                    "Year",
                    min_value=1980,
                    max_value=2030,
                    key=f"{prefix}_man_year",
                )
            )
        with c4:
            final_variant = st.text_input("Variant (optional)", key=f"{prefix}_man_variant")
        st.caption(
            "Manual entry supports legacy samples, imported vehicles, and models outside the 2022–2026 Indian catalog."
        )

    # Real-time pricing coverage check
    coverage = check_pricing_coverage(final_make, final_model, final_year)
    render_pricing_coverage_card(coverage)

    return final_make, final_model, final_year, final_variant


def render_advanced_pricing_options(prefix: str) -> tuple[str, str, str]:
    """Render collapsible advanced pricing scope options with readable labels."""
    with st.expander("Advanced Pricing Scope Options", expanded=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            region_map = {
                "IN-DEMO-METRO (India - Demonstration Metro Region)": "IN-DEMO-METRO",
                "IN-DEMO-TIER2 (India - Demonstration Tier-2 City)": "IN-DEMO-TIER2",
            }
            sel_region = st.selectbox(
                "Pricing Region",
                options=list(region_map.keys()),
                index=0,
                key=f"{prefix}_region_sel",
                help="Demonstration pricing regions. All current records are synthetic demo values, not market-verified quotes.",
            )
            region = region_map[sel_region]

        with c2:
            st.text_input(
                "Currency",
                value="INR (Indian Rupee - ₹)",
                disabled=True,
                key=f"{prefix}_currency_disp",
                help="The demonstration knowledge base and labor schedules are denominated in Indian Rupees.",
            )
            currency = "INR"

        with c3:
            grade_map = {
                "OEM (Original Equipment Manufacturer — Genuine)": "oem",
                "Aftermarket (Certified Replacement)": "aftermarket",
            }
            sel_grade = st.selectbox(
                "Part Grade Preference",
                options=list(grade_map.keys()),
                index=0,
                key=f"{prefix}_grade_sel",
                help="OEM parts use genuine manufacturer pricing; Aftermarket uses certified third-party schedules.",
            )
            part_grade = grade_map[sel_grade]

        st.caption(
            "ℹ️ **Part Grade Guidance:** OEM parts reflect authorized dealer replacement rates. "
            "Aftermarket parts reflect certified tier-1 supplier schedules where available."
        )

    return region, currency, part_grade


def render_step_1_input():
    mode = st.session_state.mode

    if mode == "sample":
        render_sample_mode()
    else:
        render_live_mode()


def render_sample_mode():
    st.markdown(
        """
    <div class="ai-card">
        <div class="ai-card-header">
            <div>
                <h3 class="ai-card-title">Select Inspection Scenario</h3>
                <p class="ai-card-subtitle">Saved damage-map fixtures (not live results, not validated cases) for exploring rules, retrieval, costing and reports offline.</p>
            </div>
            <span class="ai-status-pill sample">Offline · Zero API Spend</span>
        </div>
    """,
        unsafe_allow_html=True,
    )

    cols = st.columns(len(SCENARIO_CARDS))
    for i, (fname, meta) in enumerate(SCENARIO_CARDS.items()):
        is_selected = st.session_state.selected_scenario == fname
        with cols[i]:
            card_border = (
                "border: 2px solid #2563EB; background: #F8FAFC;"
                if is_selected
                else "border: 1px solid #E2E8F0; background: #FFFFFF;"
            )
            st.markdown(
                f"""
            <div style="{card_border} border-radius: 10px; padding: 14px; min-height: 180px; display: flex; flex-direction: column; justify-content: space-between;">
                <div>
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
                        <span style="font-size: 11px; font-weight: 700; color: #2563EB; text-transform: uppercase;">{meta["badge"]}</span>
                        <span style="font-size: 11px; color: #64748B;">{meta["findings_count"]}</span>
                    </div>
                    <h4 style="margin: 0 0 4px 0; font-size: 14px; font-weight: 700; color: #0F172A;">{meta["title"]}</h4>
                    <p style="margin: 0 0 8px 0; font-size: 12px; color: #475569; line-height: 1.35;">{meta["desc"]}</p>
                </div>
                <div style="font-size: 11px; color: #64748B; border-top: 1px solid #F1F5F9; padding-top: 6px;">
                    {meta["make"]} {meta["model"]} ({meta["year"]})
                </div>
            </div>
            """,
                unsafe_allow_html=True,
            )
            if st.button(
                "Selected" if is_selected else "Select",
                key=f"scen_{fname}",
                use_container_width=True,
                type="primary" if is_selected else "secondary",
            ):
                st.session_state.selected_scenario = fname
                # Reset sample selector inputs to match selected scenario
                new_meta = SCENARIO_CARDS[fname]
                st.session_state["sample_cat_make"] = new_meta["make"]
                st.session_state["sample_cat_model"] = new_meta["model"]
                st.session_state["sample_cat_year"] = new_meta["year"]
                st.session_state["sample_man_make"] = new_meta["make"]
                st.session_state["sample_man_model"] = new_meta["model"]
                st.session_state["sample_man_year"] = new_meta["year"]
                st.session_state["sample_man_variant"] = new_meta["variant"]
                st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

    # Selected scenario details & parameters
    selected_meta = SCENARIO_CARDS[st.session_state.selected_scenario]
    st.markdown(
        """
    <div class="ai-card">
        <div class="ai-card-header">
            <div>
                <h3 class="ai-card-title">Vehicle & Pricing Parameters</h3>
                <p class="ai-card-subtitle">Verify vehicle specifications and pricing region before analysis.</p>
            </div>
        </div>
    """,
        unsafe_allow_html=True,
    )

    make, model, year, variant = render_vehicle_selector(
        prefix="sample",
        default_make=selected_meta["make"],
        default_model=selected_meta["model"],
        default_year=selected_meta["year"],
        default_variant=selected_meta["variant"],
    )

    region, currency, part_grade = render_advanced_pricing_options("sample")

    action_col1, action_col2 = st.columns([8, 2])
    with action_col2:
        if st.button("Run Assessment →", type="primary", use_container_width=True):
            execute_sample_assessment(make, model, year, variant, region, currency, part_grade)

    st.markdown("</div>", unsafe_allow_html=True)


def render_system_status():
    """Key/config diagnostics without revealing the key: configured vs verified, reload, verify."""
    status = key_status()
    state = api_check_state()
    with st.expander(
        "Gemini connection & configuration",
        expanded=state in ("missing", "failed"),
    ):
        if status.configured:
            st.markdown(
                f"**Key:** configured via `{status.variable}` from the **{status.source}** (value hidden)."
            )
        else:
            st.markdown(f"**Key:** not configured — {html.escape(status.problem or '')}")
        st.markdown(
            f"**Project .env:** `{status.env_file}` — "
            f"{'exists' if status.env_file_exists else 'missing'} · {html.escape(status.env_file_status)}"
        )
        st.markdown(
            f"**Model:** `{analyse.MODEL}` · **API version:** `{analyse.API_VERSION}` "
            f"(set explicitly on the client) · **Timeout:** {analyse.TIMEOUT_S:g}s"
        )
        chk = st.session_state.get("api_check")
        if state == "verified":
            st.success(f"Connection verified: {chk.get('detail')}")
        elif state == "failed":
            st.error(f"Connection check failed ({chk.get('stage')}): {chk.get('detail')}")
        elif state == "configured":
            st.info("A key is configured but has not been verified with Google in this session.")
        for hint in settings.diagnostics():
            st.warning(hint)

        c1, c2 = st.columns(2)
        with c1:
            if st.button(
                "Reload configuration (.env)",
                use_container_width=True,
                help="Re-reads the project .env without restarting. Variables set in the terminal that "
                "launched Streamlit cannot change until you restart it.",
            ):
                settings.reload()
                analyse.refresh_settings()
                st.session_state.api_check = None
                st.rerun()
        with c2:
            if st.button(
                "Verify API connection",
                use_container_width=True,
                disabled=not status.configured,
                help="Lists models with your key (no image analysed, no generation request).",
            ):
                with st.spinner("Contacting Gemini..."):
                    res = analyse.verify_connection(generate=False)
                res["config_sig"] = config_signature()
                st.session_state.api_check = res
                st.rerun()
        st.caption(
            "If the key was set in a different terminal, this server cannot see it: put it in the project "
            ".env and press Reload, or stop this server (Ctrl+C) and start it from a terminal where the key "
            "is set. Command-line check: `python scripts/check_config.py --verify`."
        )


def render_live_mode():
    has_gemini = key_status().configured

    if not has_gemini:
        st.markdown(
            f"""
        <div class="ai-notice ai-notice-red">
            <strong>Gemini API key not configured:</strong> add <code>GEMINI_API_KEY=&lt;your key&gt;</code> to
            <code>{html.escape(str(settings.ENV_FILE))}</code> and press <strong>Reload configuration</strong> below
            (or restart the app). Use <strong>Sample Fixtures</strong> to explore without credentials.
        </div>
        """,
            unsafe_allow_html=True,
        )
    render_system_status()

    # Display Mismatch Conflict Notice if detected by pipeline
    conflict = st.session_state.get("mismatch_conflict")
    if conflict:
        evidence_items = "".join(f"<li>{html.escape(e)}</li>" for e in conflict.get("evidence", []))
        if conflict.get("status") == "conflict":
            st.markdown(
                f"""
                <div class="ai-notice ai-notice-red" style="border: 2px solid #EF4444; background: #FEF2F2; padding: 16px; border-radius: 8px; margin-bottom: 20px;">
                    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                        <span style="font-size: 20px;">🚫</span>
                        <strong style="color: #991B1B; font-size: 15px;">Vehicle Identity Mismatch: Uploaded photos show conflicting vehicle models or colors. Distinct vehicles cannot be merged.</strong>
                    </div>
                    <p style="color: #7F1D1D; font-size: 13px; margin: 0 0 8px 0;">
                        Multi-angle vehicle consistency check detected conflicting visual evidence across uploaded frames:
                    </p>
                    <ul style="color: #991B1B; font-size: 12px; margin: 0 0 10px 20px; line-height: 1.5;">
                        {evidence_items}
                    </ul>
                    <p style="color: #7F1D1D; font-size: 12px; margin: 0;">
                        <strong>Action Required:</strong> Please remove conflicting photographs and upload photos representing the same vehicle. Hard identity conflicts cannot be overridden.
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            # Uncertain status
            st.markdown(
                f"""
                <div class="ai-notice ai-notice-amber" style="padding: 16px; border-radius: 8px; margin-bottom: 20px;">
                    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                        <span style="font-size: 20px;">⚠️</span>
                        <strong style="color: #92400E; font-size: 14px;">Same-Vehicle Uncertainty: Could not verify identical vehicle with high confidence.</strong>
                    </div>
                    <ul style="color: #92400E; font-size: 12px; margin: 0 0 10px 20px; line-height: 1.5;">
                        {evidence_items}
                    </ul>
                </div>
                """,
                unsafe_allow_html=True,
            )
            confirm_same_box = st.checkbox(
                "Confirm all photos represent the same subject vehicle (angle or lighting differences only)",
                value=st.session_state.confirm_same_vehicle,
            )
            st.session_state.confirm_same_vehicle = confirm_same_box

    st.markdown(
        """
    <div class="ai-card">
        <div class="ai-card-header">
            <div>
                <h3 class="ai-card-title">1. Vehicle Information</h3>
                <p class="ai-card-subtitle">Specify vehicle particulars using the Indian catalog or manual entry to enable accurate catalog matching and parts pricing.</p>
            </div>
        </div>
    """,
        unsafe_allow_html=True,
    )

    make, model, year, variant = render_vehicle_selector(
        prefix="live",
        default_make="Hyundai",
        default_model="i20",
        default_year=2023,
        default_variant="Sportz",
    )

    region, currency, part_grade = render_advanced_pricing_options("live")

    st.markdown("</div>", unsafe_allow_html=True)

    # Photo Upload Card
    st.markdown(
        """
    <div class="ai-card">
        <div class="ai-card-header">
            <div>
                <h3 class="ai-card-title">2. Damage Evidence Photos</h3>
                <p class="ai-card-subtitle">Upload 3–5 multi-angle exterior photographs of the SAME vehicle.</p>
            </div>
            <span class="ai-status-pill">3–5 Recommended</span>
        </div>
    """,
        unsafe_allow_html=True,
    )

    uploaded = st.file_uploader(
        "Upload photos",
        type=["jpg", "jpeg", "png", "webp", "bmp"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )

    if not uploaded and st.session_state.uploaded_files_data:
        st.session_state.uploaded_files_data = []      # user removed every file
        st.session_state.mismatch_conflict = None
    if uploaded:
        current = [(f.name, f.getvalue()) for f in uploaded]
        sig = hashlib.sha256(b"".join(hashlib.sha256(d).digest() for _, d in current)).hexdigest()
        if sig != st.session_state.input_hash:
            st.session_state.uploaded_files_data = current
            st.session_state.input_hash = sig
            st.session_state.mismatch_conflict = None
            st.session_state.confirm_same_vehicle = False
        if len(uploaded) > 5:
            st.markdown(
                """
            <div class="ai-notice ai-notice-red">
                <strong>Too many photos:</strong> at most 5 photos of ONE vehicle can be analysed. Remove some.
            </div>
            """,
                unsafe_allow_html=True,
            )

        # Thumbnail Grid with remove & quality review
        n_up = len(uploaded)
        t_cols = st.columns(min(n_up, 5))
        for idx, f in enumerate(uploaded):
            with t_cols[idx % min(n_up, 5)]:
                st.image(f, caption=f.name, use_container_width=True)
                st.caption(f"Size: {len(f.getvalue()) / 1024:.1f} KB")

        if n_up < 3:
            st.markdown(
                f"""
            <div class="ai-notice ai-notice-amber">
                <strong>Low Coverage Warning:</strong> Only {n_up} photo(s) uploaded. At least 3 multi-angle views are recommended for complete assessment.
            </div>
            """,
                unsafe_allow_html=True,
            )

    # Optional narrative
    st.markdown("<p style='font-size: 13px; font-weight: 600; color: #334155; margin-top: 14px;'>Optional Accident Description</p>", unsafe_allow_html=True)
    narrative = st.text_area(
        "Accident Narrative",
        placeholder="e.g. Low-speed parking collision with a concrete pole while reversing...",
        label_visibility="collapsed",
    )

    has_hard_conflict = bool(conflict and conflict.get("status") == "conflict")
    can_analyze = bool(
        uploaded
        and len(uploaded) <= 5
        and has_gemini
        and make.strip()
        and model.strip()
        and not has_hard_conflict
    )

    action_col1, action_col2 = st.columns([7, 3])
    with action_col2:
        if st.button(
            "Analyze Vehicle Photos →",
            type="primary",
            use_container_width=True,
            disabled=not can_analyze,
        ):
            execute_live_assessment(
                make,
                model,
                year,
                variant,
                region,
                currency,
                part_grade,
                narrative,
                st.session_state.confirm_same_vehicle,
            )

    if has_hard_conflict:
        st.caption("🚫 Cannot run analysis: Conflicting vehicles detected. Please remove mismatched photos.")
    elif not can_analyze and not has_gemini:
        st.caption("⚠️ Cannot run live analysis: GEMINI_API_KEY not configured.")
    elif not can_analyze and not uploaded:
        st.caption("⚠️ Upload at least 1 photo to enable analysis.")

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════════════════════
# Step 2: Assessment Execution Functions
# ═════════════════════════════════════════════════════════════════════════════
def execute_sample_assessment(
    make, model, year, variant, region, currency, part_grade
):
    st.session_state.error = None
    st.session_state.error_detail = None
    sample_file = SAMPLES_DIR / st.session_state.selected_scenario

    if not sample_file.exists():
        st.session_state.error = f"Fixture file not found: {sample_file}"
        return

    progress_box = st.empty()
    progress_box.info("Executing sample assessment...")

    try:
        retriever = get_cached_retriever()
        scope = PricingScope(
            region=region,
            currency=currency,
            part_grade_preference=part_grade,
            tax_rate=settings.GST_RATE,
        )
        vehicle = VehicleInfo(
            make=make,
            model=model,
            year=year,
            variant=variant or "",
            source="user_supplied",
        )

        res = run_sample_assessment(
            sample_file, vehicle=vehicle, scope=scope, retriever=retriever
        )
        st.session_state.result = res
        st.session_state.exports = None
        st.session_state.step = 3
        progress_box.empty()
        st.rerun()
    except Exception as exc:
        progress_box.empty()
        st.session_state.error = (
            f"Assessment execution failed: {type(exc).__name__}: {exc}"
        )
        st.session_state.error_detail = traceback.format_exc()
        st.rerun()


def execute_live_assessment(
    make,
    model,
    year,
    variant,
    region,
    currency,
    part_grade,
    narrative,
    confirm_same,
):
    st.session_state.error = None
    st.session_state.error_detail = None
    if not st.session_state.uploaded_files_data:
        st.session_state.error = "No uploaded files found."
        return

    progress_container = st.container()
    with progress_container:
        st.markdown(
            """
        <div class="ai-card">
            <h3 class="ai-card-title">Live Vision & Cost Pipeline Running</h3>
            <p class="ai-card-subtitle">Executing multi-angle inference, consistency checking, and semantic RAG retrieval...</p>
        </div>
        """,
            unsafe_allow_html=True,
        )
        p_bar = st.progress(0.05, text="Validating uploaded photos...")

        def _on_progress(msg: str, frac: float):
            p_bar.progress(min(max(frac, 0.0), 1.0), text=msg)

        # Isolated per-case temp folder with sanitised names; always removed afterwards.
        tmp_dir = tempfile.mkdtemp(prefix="autoinspect_case_")
        image_paths = []
        for idx, (name, data) in enumerate(st.session_state.uploaded_files_data, 1):
            p = Path(tmp_dir) / safe_upload_name(name, idx)
            p.write_bytes(data)
            image_paths.append(str(p))

        try:
            retriever = get_cached_retriever()
            scope = PricingScope(
                region=region,
                currency=currency,
                part_grade_preference=part_grade,
                tax_rate=settings.GST_RATE,
            )
            vehicle = VehicleInfo(
                make=make,
                model=model,
                year=year,
                variant=variant or "",
                source="user_supplied",
            )

            res = run_live_assessment(
                image_paths,
                vehicle,
                accident_description=narrative or None,
                scope=scope,
                confirm_same_vehicle=confirm_same,
                retriever=retriever,
                progress=_on_progress,
            )
            st.session_state.mismatch_conflict = None
            st.session_state.result = res
            st.session_state.exports = None
            st.session_state.step = 3
        except VehicleMismatchError as exc:
            st.session_state.mismatch_conflict = {
                "status": exc.consistency.get("status", "conflict"),
                "evidence": exc.consistency.get("evidence", [str(exc)]),
                "message": str(exc),
            }
            st.session_state.step = 1
        except Exception as exc:  # noqa: BLE001 - every failure stays visible; never a fake result
            # Errors are already key-free (src.analyse redacts); the traceback goes in an expander.
            st.session_state.error = f"Live analysis failed: {type(exc).__name__}: {analyse._redact(exc)}"
            st.session_state.error_detail = analyse._redact(traceback.format_exc())
            if isinstance(exc, analyse.FatalAnalysisError):
                st.session_state.api_check = {
                    "ok": False, "stage": "analysis", "detail": analyse._redact(exc),
                    "config_sig": config_signature(),
                }
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        st.rerun()


# ═════════════════════════════════════════════════════════════════════════════
# Step 3: Review & Export Workspace
# ═════════════════════════════════════════════════════════════════════════════
def render_step_3_review():
    res: AssessmentResult | None = st.session_state.result
    if not res:
        st.warning("No assessment results found. Please start a new case.")
        if st.button("← Return to Inputs"):
            st.session_state.step = 1
            st.rerun()
        return

    a: Assessment = res.assessment
    t = a.totals
    cur = t.currency

    # Top Toolbar / Actions
    tb_col1, tb_col2 = st.columns([8, 2])
    with tb_col1:
        st.markdown(
            f"""
        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 12px;">
            <span style="font-size: 13px; font-weight: 700; color: #0F172A;">Case #{a.assessment_id}</span>
            <span style="font-size: 12px; color: #64748B;">·</span>
            <span style="font-size: 12px; color: #64748B;">{a.created_at.strftime('%Y-%m-%d %H:%M UTC')}</span>
            <span style="font-size: 12px; color: #64748B;">·</span>
            <span class="ai-status-pill {'sample' if a.mode == 'sample_fixture' else 'online'}">
                {'SAMPLE FIXTURE - not a live case' if a.mode == 'sample_fixture' else 'Live Assessment'}
            </span>
            {f'<span class="ai-status-pill" style="background: #FEF3C7; color: #B45309; border-color: #FDE68A;">{a.pricing_label}</span>' if a.pricing_label else ''}
        </div>
        """,
            unsafe_allow_html=True,
        )
    with tb_col2:
        if st.button("← Back to Inputs", use_container_width=True):
            st.session_state.step = 1
            st.rerun()

    # ── Two-Column Results Workspace ─────────────────────────────────────────
    left_col, right_col = st.columns([58, 42])

    # ── Left Column: Visual Evidence Viewer ──────────────────────────────────
    with left_col:
        render_evidence_viewer(res, a)

    # ── Right Column: Summary & Component Action Breakdown ───────────────────
    with right_col:
        render_assessment_summary(a)

    # ── Detailed Workspace Tabs ──────────────────────────────────────────────
    st.markdown("<div style='margin-top: 24px;'></div>", unsafe_allow_html=True)
    tab_findings, tab_evidence, tab_report = st.tabs(
        ["Component Findings", "Grounded Pricing Evidence", "Report & Exports"]
    )

    with tab_findings:
        render_findings_tab(a)

    with tab_evidence:
        render_pricing_evidence_tab(a)

    with tab_report:
        render_report_tab(res, a)


# ── Evidence Viewer Subcomponent ─────────────────────────────────────────────
def render_evidence_viewer(res: AssessmentResult, a: Assessment):
    st.markdown(
        """
    <div class="ai-card">
        <div class="ai-card-header">
            <div>
                <h3 class="ai-card-title">Damage Evidence & Localization</h3>
                <p class="ai-card-subtitle">AI-localized damage bounding boxes projected onto original intake frames.</p>
            </div>
        </div>
    """,
        unsafe_allow_html=True,
    )

    if res.overlays and len(res.overlays) > 0:
        image_ids = list(res.overlays.keys())

        # Select active image
        if st.session_state.active_image_id not in image_ids:
            st.session_state.active_image_id = image_ids[0]

        # Top Controls: Overlay Toggle & Component Filter
        ctrl_c1, ctrl_c2 = st.columns([1, 1])
        with ctrl_c1:
            st.session_state.show_overlays = st.toggle(
                "Show AI Bounding Boxes", value=st.session_state.show_overlays
            )

        with ctrl_c2:
            comp_list = ["All findings"] + sorted(
                list({p.component_instance for p in a.component_plans})
            )
            st.session_state.filter_component = st.selectbox(
                "Filter Component", comp_list, index=0
            )

        # Image thumbnail selection strip
        if len(image_ids) > 1:
            th_cols = st.columns(len(image_ids))
            for i, iid in enumerate(image_ids):
                with th_cols[i]:
                    is_active = iid == st.session_state.active_image_id
                    th_border = "2px solid #2563EB" if is_active else "1px solid #CBD5E1"
                    if st.button(
                        f"View {i+1}: {iid[:10]}",
                        key=f"th_{iid}",
                        use_container_width=True,
                        type="primary" if is_active else "secondary",
                    ):
                        st.session_state.active_image_id = iid
                        st.rerun()

        active_id = st.session_state.active_image_id

        # Determine rendered image bytes
        if not st.session_state.show_overlays:
            # Show clean original
            display_bytes = res.originals.get(active_id) or res.overlays.get(active_id)
        else:
            # Check if filtered
            if st.session_state.filter_component == "All findings":
                display_bytes = res.overlays.get(active_id)
            else:
                # Dynamically draw overlay with filtered observations
                orig = res.originals.get(active_id)
                if orig:
                    filtered_obs = [
                        Observation.model_validate(o)
                        for o in a.damage_map.get("observations", [])
                        if o.get("component") == st.session_state.filter_component
                    ]
                    display_bytes, _ = draw_overlay(orig, active_id, filtered_obs)
                else:
                    display_bytes = res.overlays.get(active_id)

        if display_bytes:
            st.image(
                display_bytes,
                caption=f"Viewing {active_id} (AI approximate localization)",
                use_container_width=True,
            )

        # Bounding box legend
        st.markdown(
            """
        <div style="display: flex; gap: 14px; font-size: 12px; margin-top: 8px; color: #475569;">
            <span style="display: flex; align-items: center; gap: 4px;"><span style="width: 10px; height: 10px; background: #DC2626; border-radius: 2px;"></span> Severe Damage</span>
            <span style="display: flex; align-items: center; gap: 4px;"><span style="width: 10px; height: 10px; background: #EA580C; border-radius: 2px;"></span> Moderate Damage</span>
            <span style="display: flex; align-items: center; gap: 4px;"><span style="width: 10px; height: 10px; background: #2563EB; border-radius: 2px;"></span> Minor Scratch/Dent</span>
        </div>
        """,
            unsafe_allow_html=True,
        )

        unboxed = res.unboxed.get(active_id, [])
        if unboxed:
            st.caption(
                f"ℹ️ Findings without reliable bounding box: {', '.join(unboxed)}"
            )

    else:
        # Honest state when no image coordinates/files are present
        st.markdown(
            """
        <div style="background: #F8FAFC; border: 1px dashed #CBD5E1; border-radius: 10px; padding: 48px 24px; text-align: center;">
            <div style="font-size: 32px; margin-bottom: 8px; color: #94A3B8;">📸</div>
            <h4 style="margin: 0 0 6px 0; font-size: 15px; font-weight: 700; color: #334155;">Visual Localization Not Available</h4>
            <p style="margin: 0 auto; max-width: 440px; font-size: 13px; color: #64748B; line-height: 1.45;">
                This assessment was generated from a saved damage-map fixture. No raw camera images were uploaded, so bounding box overlays cannot be rendered.
            </p>
            <p style="margin: 12px 0 0 0; font-size: 12px; color: #2563EB; font-weight: 600;">
                All damage findings, rule decisions, and retrieved pricing evidence below remain fully auditable.
            </p>
        </div>
        """,
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)


# ── Assessment Summary Subcomponent ──────────────────────────────────────────
def render_assessment_summary(a: Assessment):
    t = a.totals
    cur = t.currency

    # Cost Range Card
    # Labels mirror the engine's Totals.status so the UI, JSON and PDF tell the same story.
    if t.status == "partial":
        status_label = "Priced subtotal — INCOMPLETE (some items unpriced)"
    elif t.status == "insufficient_pricing_data":
        status_label = "No applicable price records"
    elif t.status == "no_damage":
        status_label = "No visible damage findings"
    elif t.unresolved_components:
        status_label = "Observed subtotal (excludes inspection items)"
    else:
        status_label = "Estimated cost range (all findings priced)"

    def _rng(lo, hi):
        return f"{format_inr(lo)} – {format_inr(hi)}"

    cost_str = _rng(t.observed_low, t.observed_high) if t.observed_low is not None else "Not priced"
    extra = []
    if t.unresolved_components and t.unresolved_low is not None:
        extra.append(
            f"Inspection items ({len(t.unresolved_components)}): <strong>{_rng(t.unresolved_low, t.unresolved_high)}</strong>"
        )
        extra.append(f"Envelope: <strong>{_rng(t.envelope_low, t.envelope_high)}</strong>")
    if t.observed_with_tax_low is not None:
        extra.append(f"Incl. tax: <strong>{_rng(t.observed_with_tax_low, t.observed_with_tax_high)}</strong>")
    if t.unpriced_components:
        extra.append(f"Unpriced (cost unknown, not zero): <strong>{html.escape(', '.join(t.unpriced_components))}</strong>")

    st.markdown(
        f"""
    <div class="ai-cost-hero">
        <div class="ai-cost-label">{status_label}</div>
        <div class="ai-cost-value">{cost_str}</div>
        <div class="ai-cost-notes">
            Basis: <strong>{t.tax_basis}</strong> · Currency: <strong>{cur}</strong>
            {''.join(f'<br/>{e}' for e in extra)}
            <br/><span style="opacity:0.85">{html.escape(t.status_label)}</span>
        </div>
    </div>
    """,
        unsafe_allow_html=True,
    )

    # Action Recommendations Counters
    n_replace = sum(1 for p in a.component_plans if p.action == "replace")
    n_repair = sum(1 for p in a.component_plans if p.action == "repair")
    n_inspect = sum(1 for p in a.component_plans if p.action == "inspect")

    st.markdown(
        f"""
    <div class="ai-badge-row">
        <span class="ai-badge ai-badge-replace">● {n_replace} Replace</span>
        <span class="ai-badge ai-badge-repair">● {n_repair} Repair / Refinish</span>
        <span class="ai-badge ai-badge-inspect">● {n_inspect} Inspection Required</span>
    </div>
    """,
        unsafe_allow_html=True,
    )

    # Uncertainty Card
    u = a.uncertainty
    u_color = (
        "var(--green-600)"
        if u.level == "low"
        else ("var(--amber-600)" if u.level == "medium" else "var(--red-600)")
    )
    u_bg = (
        "var(--green-100)"
        if u.level == "low"
        else ("var(--amber-100)" if u.level == "medium" else "var(--red-100)")
    )

    st.markdown(
        f"""
    <div class="ai-card" style="padding: 16px 20px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <span style="font-size: 13px; font-weight: 700; color: #0F172A;">Estimate Uncertainty</span>
            <span style="font-size: 11px; font-weight: 700; padding: 3px 8px; border-radius: 4px; background: {u_bg}; color: {u_color};">
                {u.level.upper()} ({u.points} pts)
            </span>
        </div>
        <ul style="margin: 0; padding-left: 18px; font-size: 12px; color: #475569; line-height: 1.4;">
            {''.join(f'<li>{html.escape(r)}</li>' for r in u.reasons[:3])}
        </ul>
    </div>
    """,
        unsafe_allow_html=True,
    )

    # Pipeline / estimate warnings (coverage, duplicates, conflicts, partial pricing ...)
    if a.warnings:
        items = "".join(f"<li>{html.escape(w)}</li>" for w in a.warnings[:12])
        more = f"<li>… {len(a.warnings) - 12} more in the JSON/PDF</li>" if len(a.warnings) > 12 else ""
        st.markdown(
            f"""
        <div class="ai-notice ai-notice-amber">
            <strong>Warnings ({len(a.warnings)}):</strong>
            <ul style="margin: 4px 0 0 0; padding-left: 18px; font-size: 12px; line-height: 1.4;">{items}{more}</ul>
        </div>
        """,
            unsafe_allow_html=True,
        )

    # Honest Limitations Notice
    st.markdown(
        f"""
    <div class="ai-notice ai-notice-amber" style="margin-bottom: 0;">
        <strong>Assessment Disclaimers:</strong>
        <div style="font-size: 12px; margin-top: 4px;">
            • {html.escape(a.disclaimer)}<br/>
            • {html.escape(a.pricing_label) if a.pricing_label else "Pricing provenance: see the Grounded Pricing Evidence tab."}<br/>
            • Internal mechanical, structural-frame and safety systems are not assessed from exterior photos.
        </div>
    </div>
    """,
        unsafe_allow_html=True,
    )


# ── Tab 1: Findings Subcomponent ─────────────────────────────────────────────
def render_findings_tab(a: Assessment):
    st.markdown(
        """
    <div class="ai-card">
        <h3 class="ai-card-title" style="margin-bottom: 12px;">Component-Level Action & Cost Decisions</h3>
    """,
        unsafe_allow_html=True,
    )

    if not a.component_plans:
        st.info("No visible damage detected across submitted evidence.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    for plan in a.component_plans:
        badge_class = (
            "ai-badge-replace"
            if plan.action == "replace"
            else (
                "ai-badge-repair"
                if plan.action == "repair"
                else "ai-badge-inspect"
            )
        )

        c_low = plan.cost.low if plan.cost else None
        c_high = plan.cost.high if plan.cost else None

        cost_label = (
            f"{format_inr(c_low)} – {format_inr(c_high)}"
            if c_low is not None
            else plan.pricing_status.replace("_", " ").title()
        )

        with st.expander(
            f"{plan.component_instance.replace('_', ' ').title()} — {plan.action.upper()} ({cost_label})",
            expanded=False,
        ):
            fc1, fc2 = st.columns([6, 4])
            with fc1:
                st.markdown(
                    f"""
                <div style="font-size: 13px; line-height: 1.5;">
                    <strong>Recommended Action:</strong> <span class="ai-badge {badge_class}">{plan.action.upper()}{' (' + plan.operation + ')' if plan.operation else ''}</span><br/>
                    <strong>Rule Evaluation:</strong> <code>{plan.rule_id}</code> (v{plan.rule_version})<br/>
                    <strong>Decision Rationale:</strong> {html.escape(plan.reason)}<br/>
                    {f'<span style="color: #64748B;">{html.escape(plan.covered_damage_note)}</span><br/>' if plan.covered_damage_note else ''}
                    <strong>Damage Types:</strong> {', '.join(plan.damage_types)} (Worst: <strong>{plan.max_severity}</strong>)
                </div>
                """,
                    unsafe_allow_html=True,
                )

                # Supporting findings list
                obs_map = {o.damage_id: o for o in a.observations}
                st.markdown("<p style='font-size: 12px; font-weight: 600; margin: 8px 0 4px 0;'>Supporting Visual Findings:</p>", unsafe_allow_html=True)
                for did in plan.damage_ids:
                    ob = obs_map.get(did)
                    if ob:
                        st.markdown(
                            f"<div style='font-size: 12px; color: #475569; padding-left: 8px; border-left: 2px solid #E2E8F0; margin-bottom: 4px;'>"
                            f"<code>{did}</code>: {ob.damage_type} ({ob.severity}) · Uncalibrated model score: <strong>{ob.confidence:.2f}</strong> · {ob.views_supporting} view(s)"
                            f"</div>",
                            unsafe_allow_html=True,
                        )

            with fc2:
                if plan.cost:
                    st.markdown(
                        f"""
                    <div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 12px; font-size: 13px;">
                        <strong style="color: #0F172A;">Cost Breakdown:</strong><br/>
                        Parts: {format_inr(plan.cost.parts_low)} – {format_inr(plan.cost.parts_high)}<br/>
                        Labour: {format_inr(plan.cost.labor_low)} – {format_inr(plan.cost.labor_high)}<br/>
                        Paint/Materials: {format_inr(plan.cost.paint_materials_low)} – {format_inr(plan.cost.paint_materials_high)}<br/>
                        <hr style="margin: 6px 0; border: none; border-top: 1px solid #E2E8F0;"/>
                        <strong>Line Total: {format_inr(plan.cost.low)} – {format_inr(plan.cost.high)}</strong>
                    </div>
                    """,
                        unsafe_allow_html=True,
                    )
                else:
                    st.info(f"Status: {plan.pricing_status.replace('_', ' ').title()}")

                if plan.alternatives:
                    st.markdown("<p style='font-size: 12px; font-weight: 600; margin-top: 6px;'>Alternative Scenarios:</p>", unsafe_allow_html=True)
                    for alt in plan.alternatives:
                        alt_cost = (
                            f"{format_inr(alt.cost.low)} – {format_inr(alt.cost.high)}"
                            if alt.cost
                            else alt.pricing_status.replace("_", " ")
                        )
                        st.caption(f"• {alt.operation.title()}: {alt_cost}")

    st.markdown("</div>", unsafe_allow_html=True)


# ── Tab 2: Pricing Evidence Subcomponent ─────────────────────────────────────
def render_pricing_evidence_tab(a: Assessment):
    st.markdown(
        """
    <div class="ai-card">
        <h3 class="ai-card-title">Retrieved Pricing Citations & Vector Search Audit</h3>
        <p class="ai-card-subtitle">Every priced component links to genuine source records retrieved via semantic vector similarity.</p>
    """,
        unsafe_allow_html=True,
    )

    evidence_items = []
    for plan in a.component_plans:
        if plan.retrieval and plan.retrieval.evidence:
            for ev in plan.retrieval.evidence:
                evidence_items.append((plan.component_instance, ev))

    if not evidence_items:
        st.info("No pricing citations available.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    table_rows = []
    for comp, ev in evidence_items:
        badge = (
            '<span class="ai-status-pill sample">Illustrative Demo</span>'
            if ev.synthetic
            else '<span class="ai-status-pill online">Verified Sourced</span>'
        )
        rec = ev.record
        parts_range = f"{format_inr(rec.parts_cost_low)}–{format_inr(rec.parts_cost_high)}"
        labor_hours = f"{rec.labor_hours_low}–{rec.labor_hours_high} hrs"

        table_rows.append(
            f"""
        <tr>
            <td><strong>{html.escape(comp)}</strong></td>
            <td><code>{html.escape(ev.record_id)}</code></td>
            <td>{html.escape(ev.source_title)}<br/>{badge}</td>
            <td>{rec.operation} ({rec.part_grade})</td>
            <td>{parts_range}</td>
            <td>{labor_hours} @ {format_inr(rec.labor_rate_low)}/hr</td>
            <td>{ev.score:.4f} ({ev.retrieval_method})<br/><small style='color: #64748B;'>{ev.fallback_level}</small></td>
        </tr>
        """
        )

    st.markdown(
        f"""
    <table class="ai-table">
        <thead>
            <tr>
                <th>Component</th>
                <th>Record ID</th>
                <th>Source Reference</th>
                <th>Operation</th>
                <th>Parts Cost</th>
                <th>Labour Hours/Rate</th>
                <th>Cosine Score</th>
            </tr>
        </thead>
        <tbody>
            {''.join(table_rows)}
        </tbody>
    </table>
    """,
        unsafe_allow_html=True,
    )

    st.markdown("</div>", unsafe_allow_html=True)


# ── Tab 3: Report & Exports Subcomponent ─────────────────────────────────────
def render_report_tab(res: AssessmentResult, a: Assessment):
    st.markdown(
        """
    <div class="ai-card">
        <h3 class="ai-card-title">Export Validated Assessment Deliverables</h3>
        <p class="ai-card-subtitle">Preliminary PDF report and machine-readable JSON, both rendered from the same validated assessment object.</p>
    """,
        unsafe_allow_html=True,
    )

    # JSON and PDF are rendered ONCE per assessment, from the same validated object, and keyed by
    # assessment_id so a newer result can never be paired with an older download.
    ex = st.session_state.exports
    if not ex or ex.get("assessment_id") != a.assessment_id:
        json_text, pdf_bytes, pdf_error = a.model_dump_json(indent=2), b"", None
        try:
            json_text, pdf_bytes = export_assessment(res)
        except Exception as exc:  # noqa: BLE001 - JSON stays available; PDF error is shown
            pdf_error = f"{type(exc).__name__}: {exc}"
        ex = {"assessment_id": a.assessment_id, "json": json_text, "pdf": pdf_bytes, "pdf_error": pdf_error}
        st.session_state.exports = ex
    if ex["pdf_error"]:
        st.error(f"PDF generation failed: {ex['pdf_error']}")

    dl_col1, dl_col2 = st.columns(2)
    with dl_col1:
        if ex["pdf"]:
            st.download_button(
                "📥 Download PDF Report",
                data=ex["pdf"],
                file_name=f"{a.assessment_id}.pdf",
                mime="application/pdf",
                type="primary",
                use_container_width=True,
            )
        else:
            st.button(
                "PDF Not Available", disabled=True, use_container_width=True
            )

    with dl_col2:
        st.download_button(
            "📄 Download Assessment JSON",
            data=ex["json"],
            file_name=f"{a.assessment_id}.json",
            mime="application/json",
            use_container_width=True,
        )
    st.caption(
        "Both files come from the same validated assessment object, so their totals match the summary above. "
        + ("This is a SAMPLE fixture, not a live case. " if a.mode == "sample_fixture" else "")
        + (f"{a.pricing_label}" if a.pricing_label else "")
    )

    # Full JSON inspector
    with st.expander("Inspect Raw Serialized Assessment JSON", expanded=False):
        st.json(json.loads(ex["json"]))

    # Audit Metadata & Provenance
    st.markdown("<p style='font-size: 13px; font-weight: 700; color: #0F172A; margin-top: 18px;'>System Provenance & Pipeline Hashes</p>", unsafe_allow_html=True)
    prov = a.provenance
    st.markdown(
        f"""
    <div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 14px; font-size: 12px; color: #475569; line-height: 1.6;">
        <strong>Rules Engine Version:</strong> <code>{prov.get('rules_version')}</code><br/>
        <strong>Component Vocabulary:</strong> <code>{prov.get('vocab_version')}</code><br/>
        <strong>Vector Search Embedding Model:</strong> <code>{prov.get('retrieval', {}).get('embedding_model')}</code><br/>
        <strong>Pricing Corpus Content Hash:</strong> <code>{prov.get('retrieval', {}).get('corpus_hash')}</code><br/>
        <strong>Vision Cache Provenance:</strong> {prov.get('vision_cache', 'N/A')}
    </div>
    """,
        unsafe_allow_html=True,
    )

    st.markdown("</div>", unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════════════════════
# Main Application Flow
# ═════════════════════════════════════════════════════════════════════════════
def main():
    render_header()
    render_stepper()

    # Display error notice if present
    if st.session_state.error:
        st.markdown(
            f"""
        <div class="ai-notice ai-notice-red">
            <strong>Pipeline Error:</strong> {html.escape(st.session_state.error)}
        </div>
        """,
            unsafe_allow_html=True,
        )
        if st.session_state.get("error_detail"):
            with st.expander("Technical details"):
                st.code(st.session_state.error_detail, language="text")

    if st.session_state.step == 1:
        render_step_1_input()
    elif st.session_state.step == 3:
        render_step_3_review()
    else:
        render_step_1_input()


if __name__ == "__main__":
    main()
