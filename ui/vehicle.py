"""Compact vehicle-details panel: dependent, searchable make → model → year → variant selectors
backed by knowledge/indian_vehicles.json, a manual-entry fallback for vehicles outside that
catalog, and the pricing-coverage check against the actual pricing corpus."""
from __future__ import annotations

from dataclasses import dataclass, field

import streamlit as st

from src import settings
from src.contracts import PricingScope, VehicleInfo
from src.kb.vehicles import (
    check_pricing_coverage,
    get_manufacturers,
    get_model_record,
    get_models_for_make,
    get_variants_for_model_year,
    get_years_for_model,
    normalize_make,
)

from .html import chip, esc, render

REGIONS = {
    "IN-DEMO-METRO": "India · metro (demo region)",
    "IN-DEMO-TIER2": "India · tier-2 city (demo region)",
}
GRADES = {"oem": "OEM (genuine parts)", "aftermarket": "Aftermarket (certified)"}
CURRENCY = "INR"
PERSIST = "session"     # keep values while the results view hides these widgets

COVERAGE_TONE = {"full": "green", "partial": "amber", "unpriced_recognized": "violet",
                 "unverified_manual": "neutral"}


@dataclass
class VehicleInputs:
    make: str = ""
    model: str = ""
    year: int | None = None
    variant: str = ""
    manual: bool = False
    region: str = "IN-DEMO-METRO"
    grade: str = "oem"
    missing: list[str] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return not self.missing

    def vehicle_info(self) -> VehicleInfo:
        return VehicleInfo(make=self.make, model=self.model, year=self.year, variant=self.variant,
                           source="user_supplied")

    def scope(self) -> PricingScope:
        return PricingScope(region=self.region, currency=CURRENCY, part_grade_preference=self.grade,
                            tax_rate=settings.GST_RATE)

    def label(self) -> str:
        parts = [self.make, self.model, str(self.year) if self.year else "", self.variant]
        return " ".join(p for p in parts if p).strip() or "Vehicle not set"

    def as_dict(self) -> dict:
        return {"make": self.make, "model": self.model, "year": self.year, "variant": self.variant,
                "region": self.region, "grade": self.grade}


@st.cache_data(show_spinner=False)
def _coverage(make: str, model: str, year: int | None):
    return check_pricing_coverage(make, model, year)


def _clear(prefix: str, fields: tuple[str, ...]) -> None:
    for f in fields:
        st.session_state[f"{prefix}_{f}"] = None


def set_vehicle(prefix: str, make: str, model: str, year: int | None, variant: str = "") -> None:
    """Pre-fill the panel (used by sample fixtures). Uses the catalog only when the exact
    make/model/year exists there; otherwise switches to manual entry so the year is kept."""
    ss = st.session_state
    canon = normalize_make(make)
    rec = get_model_record(canon, model)
    in_catalog = rec is not None and year in rec.years
    ss[f"{prefix}_manual"] = not in_catalog
    if in_catalog:
        ss[f"{prefix}_make"], ss[f"{prefix}_model"], ss[f"{prefix}_year"] = rec.make, rec.model, int(year)
        known = get_variants_for_model_year(rec.make, rec.model, int(year))
        # use the catalog's spelling of the trim when it matches (e.g. "VXI" -> "VXi")
        ss[f"{prefix}_variant"] = next((k for k in known if k.lower() == (variant or "").strip().lower()),
                                       variant or None)
    else:
        ss[f"{prefix}_m_make"], ss[f"{prefix}_m_model"] = make, model
        ss[f"{prefix}_m_year"], ss[f"{prefix}_m_variant"] = year, variant or ""


def render_vehicle_panel(prefix: str) -> VehicleInputs:
    ss = st.session_state
    out = VehicleInputs()
    out.manual = st.toggle(
        "Enter vehicle manually", key=f"{prefix}_manual", persist_state=PERSIST,
        help="For vehicles outside the 2022–2026 Indian catalog (older model years, imports).")

    if not out.manual:
        makes = get_manufacturers()
        c1, c2 = st.columns(2)
        make = c1.selectbox(
            "Make", makes, index=None, placeholder="Search make", key=f"{prefix}_make",
            on_change=_clear, args=(prefix, ("model", "year", "variant")), persist_state=PERSIST)
        models = get_models_for_make(make) if make else []
        model = c2.selectbox(
            "Model", models, index=None, key=f"{prefix}_model", disabled=not make,
            placeholder="Search model" if make else "Choose a make first",
            on_change=_clear, args=(prefix, ("year", "variant")), persist_state=PERSIST)
        years = get_years_for_model(make, model) if (make and model) else []
        c3, c4 = st.columns(2)
        year = c3.selectbox(
            "Model year", years, index=None, key=f"{prefix}_year", disabled=not model,
            placeholder="Select year" if model else "Choose a model first",
            on_change=_clear, args=(prefix, ("variant",)), persist_state=PERSIST)
        variants = get_variants_for_model_year(make, model, year) if year else []
        variant = c4.selectbox(        # accept_new_options keeps a custom trim the user types
            "Variant (optional)", variants, index=None, key=f"{prefix}_variant", disabled=not year,
            placeholder="Search or type a trim" if year else "Choose a year first",
            accept_new_options=True, persist_state=PERSIST)
        out.make, out.model = make or "", model or ""
        out.year, out.variant = (int(year) if year else None), (variant or "").strip()
    else:
        c1, c2 = st.columns(2)
        out.make = (c1.text_input("Make", key=f"{prefix}_m_make", max_chars=40, placeholder="e.g. Hyundai",
                                  persist_state=PERSIST) or "").strip()
        out.model = (c2.text_input("Model", key=f"{prefix}_m_model", max_chars=40, placeholder="e.g. i20",
                                   persist_state=PERSIST) or "").strip()
        c3, c4 = st.columns(2)
        year = c3.number_input("Model year", min_value=1980, max_value=2030, value=None, step=1,
                               key=f"{prefix}_m_year", placeholder="e.g. 2021", persist_state=PERSIST)
        out.year = int(year) if year else None
        out.variant = (c4.text_input("Variant (optional)", key=f"{prefix}_m_variant", max_chars=40,
                                     persist_state=PERSIST) or "").strip()

    out.missing = [label for label, value in (("make", out.make), ("model", out.model), ("model year", out.year))
                   if not value]
    if out.make and out.model:
        _render_coverage(out)
    else:
        st.caption("Pricing coverage appears once make and model are set.")

    with st.expander("Pricing options", icon=":material/tune:"):
        ss.setdefault(f"{prefix}_region", "IN-DEMO-METRO")
        ss.setdefault(f"{prefix}_grade", "oem")
        out.region = st.selectbox("Pricing region", list(REGIONS), format_func=REGIONS.get,
                                  key=f"{prefix}_region", persist_state=PERSIST,
                                  help="Demonstration regions of the pricing corpus.")
        out.grade = st.selectbox("Part grade", list(GRADES), format_func=GRADES.get, key=f"{prefix}_grade",
                                 persist_state=PERSIST,
                                 help="Preferred grade; the other grade is used (and labelled) when no record exists.")
        st.caption("Currency: Indian rupee (INR). Tax is shown separately using the configured GST rate.")
    out.region = out.region or "IN-DEMO-METRO"
    out.grade = out.grade or "oem"
    return out


def _render_coverage(v: VehicleInputs) -> None:
    cov = _coverage(v.make, v.model, v.year)
    tone = COVERAGE_TONE.get(cov.status, "neutral")
    count = (f"{cov.record_count} record{'s' if cov.record_count != 1 else ''} · "
             f"{len(cov.priced_components)} component{'s' if len(cov.priced_components) != 1 else ''}"
             if cov.record_count else "no price records")
    synthetic = chip("Synthetic demo prices", "amber") if cov.synthetic else ""
    render(
        f'<div class="ai-coverage ai-coverage--{tone}" role="status">'
        f'<div class="ai-coverage-head">{chip(cov.status_label, tone, dot=True)}'
        f'<span class="ai-coverage-count">{esc(count)}</span>{synthetic}</div>'
        f'<p class="ai-coverage-msg">{esc(cov.message)}</p></div>')
