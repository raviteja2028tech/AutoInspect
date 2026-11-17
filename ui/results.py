"""Results workspace: image-first evidence viewer, cost summary, exports and detail tabs.

Everything shown comes from the validated Assessment (and the overlays drawn from it) that
the JSON and PDF exports are rendered from, so the on-screen totals match both files.
"""
from __future__ import annotations

import json

import streamlit as st

from src.contracts import Observation
from src.overlay import draw_overlay

from . import state
from .format import (ACTIONS, OPERATIONS, SEVERITIES, action_label, file_size, format_inr, human,
                     money_range, pricing_status_label, severity_label)
from .html import bullet_list, chip, esc, md, render, section_title
from .photos import make_thumb
from .runner import build_exports

TAX_BASIS = {"excl_tax": "Excluding tax", "incl_tax": "Including tax", "mixed": "Mixed tax basis",
             "n/a": "No priced items"}
UNCERTAINTY_TONE = {"low": "green", "medium": "amber", "high": "red"}
ALL = "__all__"


# --------------------------------------------------------------------------- helpers
def photo_labels(a, photos: list[dict]) -> dict[str, str]:
    """image_id -> 'Photo 2 · front' (numbering matches the upload thumbnails)."""
    by_id: dict[str, int] = {}
    for i, p in enumerate(photos, 1):
        if p.get("image_id"):
            by_id.setdefault(p["image_id"], i)      # a duplicate upload keeps the first photo's number
    labels = {}
    for n, m in enumerate(a.damage_map.get("image_manifest", []) or [], 1):
        iid = m.get("image_id")
        view = (m.get("view") or "").replace("_", " ")
        labels[iid] = f"Photo {by_id.get(iid, n)}" + (f" · {view}" if view and view != "unknown" else "")
    return labels


def _obs_by_id(a) -> dict[str, Observation]:
    return {o.damage_id: o for o in a.observations}


def _plan_images(a, plan) -> list[str]:
    obs = _obs_by_id(a)
    ids: list[str] = []
    for did in plan.damage_ids:
        o = obs.get(did)
        if not o:
            continue
        boxed = [i for i, b in o.bbox_by_image.items() if b]
        for iid in boxed + list(o.image_ids):
            if iid not in ids:
                ids.append(iid)
    return ids


def _ensure_exports(w: dict) -> dict:
    a = w["result"].assessment
    ex = w.get("exports")
    if not ex or ex.get("assessment_id") != a.assessment_id:
        ex = build_exports(w["result"])
        w["exports"] = ex
    return ex


def focus_component(plan_instance: str, image_id: str | None) -> None:
    """Findings-tab callback: show this component's regions in the evidence viewer."""
    ss = st.session_state
    if image_id:
        ss.viewer_image = image_id
    ss.viewer_focus = plan_instance
    ss.viewer_layer = "Annotated"


def _back_to_inputs(mode: str) -> None:
    state.show_view(mode, "inputs")


def _new(mode: str) -> None:
    if mode == "live":
        state.reset_live()
    else:
        state.clear_result(state.ws("sample"))
        state.show_view("sample", "inputs")


# --------------------------------------------------------------------------- page
def render_results(mode: str) -> None:
    w = state.ws(mode)
    res = w["result"]
    a = res.assessment
    ex = _ensure_exports(w)
    labels = photo_labels(a, st.session_state.photos if mode == "live" else [])

    with st.container(horizontal=True, vertical_alignment="center", key="results_toolbar"):
        st.button("Edit inputs", icon=":material/arrow_back:", type="tertiary", key=f"{mode}_edit_inputs",
                  on_click=_back_to_inputs, args=(mode,))
        st.space("stretch")
        st.button("New assessment" if mode == "live" else "Choose another sample", icon=":material/add:",
                  key=f"{mode}_new_from_results", on_click=_new, args=(mode,))

    _result_header(a, ex)
    _notice(a)

    if res.overlays:
        left, right = st.columns([3, 2], gap="medium")
        with left:
            evidence_viewer(mode)
        with right:
            _cost_summary(a)
    else:
        left, right = st.columns([3, 2], gap="medium")
        with left:
            _findings_overview(a)
        with right:
            _cost_summary(a)

    tabs = st.tabs(["Findings", "Cost breakdown", "Pricing evidence", "Technical details"], key=f"{mode}_tabs")
    with tabs[0]:
        _findings_tab(a, bool(res.overlays), labels)
    with tabs[1]:
        _cost_tab(a)
    with tabs[2]:
        _evidence_tab(a)
    with tabs[3]:
        _technical_tab(a, w, ex, labels)


def _result_header(a, ex: dict) -> None:
    v = a.vehicle
    vehicle = " ".join(x for x in (v.make, v.model, str(v.year) if v.year else "", v.variant) if x) or "Vehicle not set"
    mode_chip = (chip("Sample fixture · not a live case", "violet") if a.mode == "sample_fixture"
                 else chip("Live photo analysis", "blue"))
    n_img = a.damage_map.get("images_analysed")
    photos_txt = f"{n_img} photo{'s' if n_img != 1 else ''} analysed" if isinstance(n_img, int) and a.mode == "live" else ""
    with st.container(border=True, key="card_result_head"):
        c1, c2 = st.columns([3, 2], vertical_alignment="center", gap="medium")
        with c1:
            meta = " · ".join(x for x in (a.created_at.strftime("%d %b %Y, %H:%M UTC"), photos_txt) if x)
            render(f'<div class="ai-result-head"><div class="ai-eyebrow">Assessment {esc(a.assessment_id)}</div>'
                   f'<h1 class="ai-result-title">{esc(vehicle)}</h1>'
                   f'<div class="ai-chip-row">{mode_chip}'
                   + (chip(a.pricing_label, "amber") if a.pricing_label else "")
                   + f'</div><p class="ai-result-meta">{esc(meta)}</p></div>')
        with c2:
            with st.container(horizontal=True, horizontal_alignment="right", gap="small", key="downloads"):
                if ex["pdf"]:
                    st.download_button("Download PDF", data=ex["pdf"], file_name=f"{a.assessment_id}.pdf",
                                       mime="application/pdf", type="primary", icon=":material/picture_as_pdf:",
                                       on_click="ignore", key=f"dl_pdf_{a.assessment_id}")
                st.download_button("Download JSON", data=ex["json"], file_name=f"{a.assessment_id}.json",
                                   mime="application/json", icon=":material/data_object:", on_click="ignore",
                                   key=f"dl_json_{a.assessment_id}")
            if ex["pdf_error"]:
                st.error(f"PDF could not be generated: {md(ex['pdf_error'])}. The JSON export is available.",
                         icon=":material/error:")
            elif ex.get("pdf_check") == "match":
                st.caption(":material/check_circle: PDF and JSON totals match this summary.")
            elif (ex.get("pdf_check") or "").startswith("MISMATCH"):
                st.error(f"PDF totals check failed: {md(ex['pdf_check'])}", icon=":material/error:")


def _notice(a) -> None:
    items = [f"<strong>{esc(a.disclaimer)}</strong>"]
    if a.pricing_label:
        items.append(f"<strong>Pricing:</strong> {esc(a.pricing_label)}")
    items.append("Exterior photos only: internal mechanical, structural-frame and safety systems are not assessed.")
    if a.mode == "sample_fixture":
        items.insert(0, "<strong>Sample mode:</strong> built from a saved fixture. No photos were analysed in "
                        "this run and this is not a real case.")
    render('<div class="ai-notice" role="note">' + "".join(f"<p>{i}</p>" for i in items) + "</div>")


# --------------------------------------------------------------------------- evidence viewer
def _set_image(image_id: str) -> None:
    st.session_state.viewer_image = image_id
    st.session_state.viewer_focus = ALL


def _overlay_for(res, a, image_id: str, focus: str) -> bytes:
    """On-screen overlay with compact ID labels (the PDF keeps the full-label overlays)."""
    cache = st.session_state.overlay_cache
    key = (a.assessment_id, image_id, focus)
    if key not in cache:
        if focus == ALL:
            obs = list(a.observations)
        else:
            plan = next((p for p in a.component_plans if p.component_instance == focus), None)
            ids = set(plan.damage_ids) if plan else set()
            obs = [o for o in a.observations if o.damage_id in ids]
        cache[key] = draw_overlay(res.originals[image_id], image_id, obs, compact=True)[0]
    return cache[key]


def _thumb_for(res, a, image_id: str) -> bytes:
    cache = st.session_state.overlay_cache
    key = (a.assessment_id, image_id, "thumb")
    if key not in cache:
        cache[key] = make_thumb(res.originals.get(image_id) or res.overlays[image_id], (240, 180))
    return cache[key]


@st.fragment
def evidence_viewer(mode: str) -> None:
    """Large image + layer toggle + component highlight + thumbnail navigation (reruns alone)."""
    ss = st.session_state
    w = state.ws(mode)
    res = w["result"]
    if res is None:
        return
    a = res.assessment
    ids = list(res.overlays)
    labels = photo_labels(a, ss.photos if mode == "live" else [])
    if ss.viewer_image not in ids:
        ss.viewer_image = ids[0]
    iid = ss.viewer_image
    obs_here = [o for o in a.observations if iid in o.image_ids]
    plans_here = [p for p in a.component_plans if any(o.damage_id in p.damage_ids for o in obs_here)]
    focus_options = [ALL] + [p.component_instance for p in plans_here]
    if ss.get("viewer_focus") not in focus_options:
        ss.viewer_focus = ALL
    ss.setdefault("viewer_layer", "Annotated")

    with st.container(border=True, key="card_viewer"):
        n = len(obs_here)
        section_title("Damage evidence", f"{labels.get(iid, iid)} · {n} finding{'s' if n != 1 else ''} on this photo",
                      chip("AI-marked regions are approximate", "neutral"))
        c1, c2 = st.columns([2, 3], vertical_alignment="bottom")
        layer = c1.segmented_control("Image", ["Annotated", "Original"], key="viewer_layer", required=True)
        focus = c2.selectbox("Highlight component", focus_options, key="viewer_focus",
                             format_func=lambda x: "All findings" if x == ALL else human(x),
                             disabled=layer == "Original",
                             help="Show only the regions linked to one component.")
        if layer == "Original":
            img = res.originals.get(iid) or res.overlays[iid]
            alt = f"{labels.get(iid, iid)}, original photo"
        elif iid not in res.originals:
            img = res.overlays[iid]
            alt = f"{labels.get(iid, iid)} with all AI-marked damage regions"
        elif focus == ALL:
            img = _overlay_for(res, a, iid, ALL)
            alt = f"{labels.get(iid, iid)} with all AI-marked damage regions"
        else:
            img = _overlay_for(res, a, iid, focus)
            alt = f"{labels.get(iid, iid)} with regions for {human(focus)}"
        st.image(img, width="stretch", alt=alt)
        render('<div class="ai-legend" aria-label="Box colours">'
               '<span><i class="ai-swatch ai-swatch--severe"></i>Severe</span>'
               '<span><i class="ai-swatch ai-swatch--moderate"></i>Moderate</span>'
               '<span><i class="ai-swatch ai-swatch--minor"></i>Minor</span></div>')

        if len(ids) > 1:
            with st.container(horizontal=True, gap="small", key="viewer_thumbs"):
                for other in ids:
                    with st.container(width=124, gap="xxsmall", key=f"vthumb_box_{other}"):
                        st.image(_thumb_for(res, a, other), width="stretch", alt=labels.get(other, other))
                        st.button(labels.get(other, other).split(" · ")[0], key=f"vthumb_{other}",
                                  type="primary" if other == iid else "secondary", width="stretch",
                                  on_click=_set_image, args=(other,),
                                  help=f"Show {labels.get(other, other)}")

        if obs_here:
            focus_ids = None
            if layer != "Original" and focus != ALL:
                plan = next((p for p in plans_here if p.component_instance == focus), None)
                focus_ids = set(plan.damage_ids) if plan else None
            rows = []
            for o in obs_here:
                if focus_ids is not None and o.damage_id not in focus_ids:
                    continue
                sev_label, sev_tone, _ = SEVERITIES.get(o.severity, (severity_label(o.severity), "neutral", "gray"))
                boxed = "boxed on photo" if o.bbox_by_image.get(iid) else "not localised on this photo"
                rows.append(f'<li><span class="ai-obs-id ai-obs-id--{esc(o.severity)}">{esc(o.damage_id)}</span>'
                            f'<span class="ai-obs-main"><strong>{esc(human(o.component))}</strong> · '
                            f'{esc(human(o.damage_type).lower())}<span class="ai-obs-meta"> · {esc(boxed)}</span>'
                            f'</span>{chip(sev_label, sev_tone)}</li>')
            render('<ul class="ai-obs">' + "".join(rows) + "</ul>")
        else:
            st.caption("No damage was reported on this photo.")


def _findings_overview(a) -> None:
    """Left column for results without photos (sample fixtures): compact component list."""
    with st.container(border=True, key="card_overview"):
        section_title("Findings overview", "Sample fixtures have no photos, so there is nothing to annotate.")
        if not a.component_plans:
            st.success("This fixture contains no damage findings.", icon=":material/check_circle:")
            return
        rows = []
        for p in a.component_plans:
            act, act_tone, _, _ = ACTIONS.get(p.action, (action_label(p.action), "neutral", "gray", ""))
            sev, sev_tone, _ = SEVERITIES.get(p.max_severity, (severity_label(p.max_severity), "neutral", "gray"))
            cost = money_range(p.cost.low, p.cost.high) if p.cost else pricing_status_label(p.pricing_status)
            rows.append(f'<li><span class="ai-obs-main"><strong>{esc(human(p.component_instance))}</strong></span>'
                        f'{chip(act, act_tone)}{chip(sev, sev_tone)}<span class="ai-obs-cost">{esc(cost)}</span></li>')
        render('<ul class="ai-obs ai-obs--plans">' + "".join(rows) + "</ul>")


# --------------------------------------------------------------------------- cost summary
def _headline(t) -> str:
    if t.status == "partial":
        return "Priced subtotal (incomplete)"
    if t.status == "insufficient_pricing_data":
        return "No applicable price records"
    if t.status == "no_damage":
        return "No visible damage found"
    if t.unresolved_components:
        return "Estimated cost of confirmed repairs"
    return "Estimated repair cost"


def _cost_summary(a) -> None:
    t = a.totals
    with st.container(border=True, key="card_cost"):
        if t.status == "no_damage":
            value = "No charges"
        elif t.observed_low is not None:
            value = money_range(t.observed_low, t.observed_high)
        else:
            value = "Not priced"
        basis = TAX_BASIS.get(t.tax_basis, t.tax_basis)
        rows = []
        if t.observed_with_tax_low is not None:
            rate = f" ({t.tax_rate * 100:g}%)" if t.tax_rate is not None else ""
            rows.append((f"Including tax{rate}", money_range(t.observed_with_tax_low, t.observed_with_tax_high)))
        if t.unresolved_components and t.unresolved_low is not None:
            n = len(t.unresolved_components)
            rows.append((f"Inspection items ({n}), not included above", money_range(t.unresolved_low, t.unresolved_high)))
            rows.append(("If inspected items need work", money_range(t.envelope_low, t.envelope_high)))
        rows_html = "".join(f'<div class="ai-cost-row"><dt>{esc(k)}</dt><dd>{esc(v)}</dd></div>' for k, v in rows)
        render(f'<div class="ai-cost" role="group" aria-label="Cost estimate">'
               f'<div class="ai-cost-label">{esc(_headline(t))}</div>'
               f'<div class="ai-cost-value">{esc(value)}</div>'
               f'<div class="ai-cost-basis">{esc(basis)} · {esc(t.currency)}</div>'
               + (f'<dl class="ai-cost-rows">{rows_html}</dl>' if rows_html else "") + "</div>")

        names = ", ".join(human(c) for c in t.unpriced_components)
        n = len(t.unpriced_components)
        if t.status == "insufficient_pricing_data":
            st.warning("**No finding could be priced** from the pricing corpus for this vehicle"
                       + (f". Cost unknown, not zero: {md(names)}." if names else "."), icon=":material/warning:")
        elif t.unpriced_components:
            st.warning(f"**Partial subtotal.** {n} item{'s' if n != 1 else ''} could not be priced, so "
                       f"{'their' if n != 1 else 'its'} cost is unknown, not zero: {md(names)}.",
                       icon=":material/warning:")
        st.caption(md(t.status_label))

        counts = {k: sum(1 for p in a.component_plans if p.action == k) for k in ("replace", "repair", "inspect")}
        tiles = "".join(
            f'<div class="ai-stat ai-stat--{ACTIONS[k][1]}"><span class="ai-stat-value">{counts[k]}</span>'
            f'<span class="ai-stat-label">{esc(ACTIONS[k][0])}</span></div>' for k in ("replace", "repair", "inspect"))
        render(f'<div class="ai-stats" role="group" aria-label="Recommended actions">{tiles}</div>')

        u = a.uncertainty
        tone = UNCERTAINTY_TONE.get(u.level, "neutral")
        shown, more = u.reasons[:4], len(u.reasons) - 4
        more_html = f'<p class="ai-muted">+{more} more in Technical details</p>' if more > 0 else ""
        render(f'<div class="ai-uncert"><div class="ai-uncert-head"><span>Estimate uncertainty</span>'
               f'{chip(f"{u.level.title()} · {u.points} pts", tone)}</div>{bullet_list(shown)}{more_html}</div>')

        if a.warnings:
            with st.expander(f"Warnings ({len(a.warnings)})", icon=":material/warning:"):
                render(bullet_list(a.warnings))


# --------------------------------------------------------------------------- tabs
def _findings_tab(a, has_photos: bool, labels: dict) -> None:
    if not a.component_plans:
        st.success("No visible damage findings." if a.mode != "sample_fixture"
                   else "This fixture contains no damage findings.", icon=":material/check_circle:")
        return
    obs = _obs_by_id(a)
    st.caption(f"{len(a.component_plans)} component(s) · {len(a.observations)} visual finding(s). Model scores are "
               "uncalibrated and are not probabilities.")
    for i, p in enumerate(a.component_plans):
        act, act_tone, _, _ = ACTIONS.get(p.action, (action_label(p.action), "neutral", "gray", ""))
        sev, sev_tone, _ = SEVERITIES.get(p.max_severity, (severity_label(p.max_severity), "neutral", "gray"))
        cost = money_range(p.cost.low, p.cost.high) if p.cost else pricing_status_label(p.pricing_status)
        op = (f" · {OPERATIONS.get(p.operation, human(p.operation)).lower()}"
              if p.operation and p.action != "inspect" and p.operation != p.action else "")
        with st.container(border=True, key=f"card_finding_{i}"):
            render(f'<div class="ai-finding-head"><div><h3 class="ai-finding-title">{esc(human(p.component_instance))}</h3>'
                   f'<div class="ai-chip-row">{chip(act + op, act_tone)}{chip(sev, sev_tone)}'
                   f'{chip(", ".join(human(d).lower() for d in p.damage_types), "neutral")}</div></div>'
                   f'<div class="ai-finding-cost">{esc(cost)}</div></div>'
                   f'<p class="ai-finding-reason">{esc(p.reason)}</p>'
                   + (f'<p class="ai-muted">{esc(p.covered_damage_note)}</p>' if p.covered_damage_note else "")
                   + (f'<p class="ai-finding-clar">{esc(p.clarification)}</p>' if p.clarification else ""))
            images = _plan_images(a, p)
            if has_photos and images:
                where = ", ".join(labels.get(x, x).split(" · ")[0] for x in images)
                c1, c2 = st.columns([3, 1], vertical_alignment="center")
                c1.caption(f"Seen in {md(where)}")
                c2.button("Show on photo", icon=":material/center_focus_strong:", key=f"show_{i}", type="tertiary",
                          on_click=focus_component, args=(p.component_instance, images[0]), width="stretch")
            with st.expander("Evidence and rule details"):
                details = [("Rule", f"{p.rule_id} ({p.rule_version})"),
                           ("Pricing", pricing_status_label(p.pricing_status)
                            + (f" · record {p.selected_record_id}" if p.selected_record_id else ""))]
                if p.explanation:
                    details.append(("Explanation", p.explanation))
                render('<dl class="ai-dl">' + "".join(f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>" for k, v in details)
                       + "</dl>")
                items = []
                for did in p.damage_ids:
                    o = obs.get(did)
                    if not o:
                        continue
                    seen = ", ".join(labels.get(x, x).split(" · ")[0] for x in o.image_ids) or "no photo link"
                    flags = (" · photos disagree on severity" if o.severity_unresolved else "") + \
                            (" · uncertain" if o.uncertain else "")
                    text = (f"{o.damage_id}: {human(o.damage_type).lower()}, {severity_label(o.severity).lower()} · "
                            f"model score {o.confidence:.2f} · {o.views_supporting} view(s) · {seen}{flags}")
                    if o.evidence:
                        text += f" · “{o.evidence}”"
                    items.append(text)
                if items:
                    render('<p class="ai-dl-title">Supporting findings</p>' + bullet_list(items))
                if p.alternatives:
                    alts = [f"{OPERATIONS.get(s.operation, s.operation)}: "
                            f"{money_range(s.cost.low, s.cost.high) if s.cost else pricing_status_label(s.pricing_status)}"
                            f" ({s.description})" for s in p.alternatives]
                    render('<p class="ai-dl-title">Scenarios kept open</p>' + bullet_list(alts))
                if p.notes:
                    render('<p class="ai-dl-title">Notes</p>' + bullet_list(p.notes))


def _cost_tab(a) -> None:
    t = a.totals
    rows = []
    for p in a.component_plans:
        c = p.cost
        rows.append({
            "Component": human(p.component_instance), "Action": action_label(p.action),
            "Operation": OPERATIONS.get(p.operation, "—") if p.operation else "—",
            "Parts": money_range(c.parts_low, c.parts_high) if c else "—",
            "Labour": money_range(c.labor_low, c.labor_high) if c else "—",
            "Paint & materials": money_range(c.paint_materials_low, c.paint_materials_high) if c else "—",
            "Line total": money_range(c.low, c.high) if c else "—",
            "Status": pricing_status_label(p.pricing_status), "Record": p.selected_record_id or "—"})
    if rows:
        st.dataframe(rows, hide_index=True, width="stretch")
    else:
        st.info("No components to price.", icon=":material/info:")

    lines = [("Observed subtotal", money_range(t.observed_low, t.observed_high) if t.observed_low is not None else "Not priced")]
    if t.tax_low is not None:
        lines.append((f"Tax ({t.tax_rate * 100:g}%)", money_range(t.tax_low, t.tax_high)))
        lines.append(("Observed including tax", money_range(t.observed_with_tax_low, t.observed_with_tax_high)))
    if t.unresolved_components:
        lines.append((f"Inspection items: {', '.join(human(c) for c in t.unresolved_components)}",
                      money_range(t.unresolved_low, t.unresolved_high)))
        lines.append(("Envelope (observed + inspection items)", money_range(t.envelope_low, t.envelope_high)))
    if t.unpriced_components:
        lines.append((f"Unpriced (cost unknown, not zero): {', '.join(human(c) for c in t.unpriced_components)}", "—"))
    with st.container(border=True, key="card_totals"):
        section_title("Totals", f"{TAX_BASIS.get(t.tax_basis, t.tax_basis)} · {t.currency}")
        render('<table class="ai-totals"><tbody>' + "".join(
            f'<tr><th scope="row">{esc(k)}</th><td>{esc(v)}</td></tr>' for k, v in lines) + "</tbody></table>")
        notes = [t.status_label] + list(t.notes)
        render(bullet_list(notes))

    alts = [{"Component": human(p.component_instance), "Scenario": OPERATIONS.get(s.operation, s.operation),
             "Status": pricing_status_label(s.pricing_status),
             "Range": money_range(s.cost.low, s.cost.high) if s.cost else "—", "Description": s.description}
            for p in a.component_plans for s in p.alternatives]
    if alts:
        st.markdown("**Scenarios kept open** (not in the observed subtotal)")
        st.dataframe(alts, hide_index=True, width="stretch")


def _evidence_tab(a) -> None:
    if a.pricing_label:
        st.warning(f"{md(a.pricing_label)} Records marked *Synthetic demo* are illustrative values, not quotes.",
                   icon=":material/science:")
    rows, missing = [], []
    for p in a.component_plans:
        r = p.retrieval
        if r and r.evidence:
            for ev in r.evidence:
                rec = ev.record
                rows.append({
                    "Component": human(p.component_instance), "Used": ev.record_id == p.selected_record_id,
                    "Rank": ev.rank, "Record": ev.record_id, "Source": ev.source_title,
                    "Data": "Synthetic demo" if ev.synthetic else human(ev.source_type),
                    "Operation": OPERATIONS.get(rec.operation, rec.operation), "Grade": rec.part_grade.upper(),
                    "Parts": money_range(rec.parts_cost_low, rec.parts_cost_high),
                    "Labour hours": f"{rec.labor_hours_low:g}–{rec.labor_hours_high:g} h",
                    "Labour rate": f"{format_inr(rec.labor_rate_low)}–{format_inr(rec.labor_rate_high)}/h",
                    "Paint & materials": money_range(rec.paint_materials_low, rec.paint_materials_high),
                    "Similarity": float(ev.score), "Method": ev.retrieval_method.replace("_", " "),
                    "Match level": ev.fallback_level})
        else:
            reason = (r.message if r and r.message else pricing_status_label(p.pricing_status))
            missing.append(f"{human(p.component_instance)}: {reason}")
    if rows:
        st.dataframe(rows, hide_index=True, width="stretch", column_config={
            "Used": st.column_config.CheckboxColumn("Used", help="Record selected for the cost line"),
            "Similarity": st.column_config.NumberColumn(
                "Similarity", format="%.3f", help="Cosine similarity used for ranking only; not a probability."),
        })
        st.caption("Each cost line is computed only from the numeric fields of its selected record. Match level "
                   "L0 is an exact vehicle/year/variant match; higher levels are labelled fallbacks.")
    else:
        st.info("No pricing records were retrieved for these findings.", icon=":material/info:")
    if missing:
        with st.container(border=True, key="card_missing_prices"):
            section_title("Not priced", "No applicable record was found (or the item needs inspection first).")
            render(bullet_list(missing))


def _technical_tab(a, w: dict, ex: dict, labels: dict) -> None:
    dm = a.damage_map
    c1, c2 = st.columns(2, gap="medium")
    with c1:
        with st.container(border=True, key="card_tech_warn"):
            section_title("Warnings", f"{len(a.warnings)} recorded")
            render(bullet_list(a.warnings) if a.warnings else '<p class="ai-muted">None.</p>')
        with st.container(border=True, key="card_tech_unc"):
            u = a.uncertainty
            section_title("Uncertainty", f"{u.level.title()} · {u.points} points")
            render(bullet_list(u.reasons) + f'<p class="ai-muted">{esc(u.method)}</p>')
    with c2:
        with st.container(border=True, key="card_tech_input"):
            v, s = a.vehicle, a.pricing_scope
            section_title("Inputs")
            pairs = [("Vehicle", " ".join(x for x in (v.make, v.model, str(v.year or ""), v.variant) if x) or "—"),
                     ("Pricing region", s.region), ("Currency", s.currency),
                     ("Part grade", s.part_grade_preference.upper()),
                     ("Tax rate", f"{s.tax_rate * 100:g}%" if s.tax_rate is not None else "Not configured"),
                     ("Accident description", a.accident_description or "—")]
            render('<dl class="ai-dl">' + "".join(f"<dt>{esc(k)}</dt><dd>{esc(val)}</dd>" for k, val in pairs) + "</dl>")
        with st.container(border=True, key="card_tech_prov"):
            prov = a.provenance or {}
            r = prov.get("retrieval", {}) or {}
            vm = prov.get("vision_meta", {}) or {}
            section_title("Provenance")
            pairs = [("Rules", prov.get("rules_version")), ("Vocabulary", prov.get("vocab_version")),
                     ("Retrieval", f"{r.get('method')} · {r.get('embedding_model')}"),
                     ("Pricing corpus", f"{r.get('n_records')} records ({r.get('n_synthetic_records')} synthetic) · "
                                        f"hash {r.get('corpus_hash')}"),
                     ("Vision model", f"{vm.get('model', '—')} · prompt {vm.get('prompt_version', '—')}"
                                      + (f" · API {vm['api_version']}" if vm.get("api_version") else "")),
                     ("Vision results", prov.get("vision_cache", "not used (sample fixture)")),
                     ("PDF totals check", ex.get("pdf_check") or "not run")]
            render('<dl class="ai-dl">' + "".join(f"<dt>{esc(k)}</dt><dd>{esc(val)}</dd>" for k, val in pairs) + "</dl>")

    manifest = dm.get("image_manifest") or []
    if manifest:
        st.markdown("**Photos analysed**")
        st.dataframe([{
            "Photo": labels.get(m.get("image_id"), m.get("image_id")), "Image ID": m.get("image_id"),
            "Original size": "×".join(str(x) for x in m.get("original_size", [])),
            "File": file_size(m.get("file_bytes") or 0), "Sharpness": m.get("blur_score"),
            "Vision result": m.get("analysis_source") or "—", "Model note": m.get("notes") or "—",
        } for m in manifest], hide_index=True, width="stretch")
    skipped = [f"{x.get('file')}: {x.get('error')}" for key in ("images_rejected", "images_duplicate",
                                                                "images_analysis_failed", "images_not_vehicle")
               for x in (dm.get(key) or [])]
    vc = dm.get("vehicle_consistency") or {}
    nc = dm.get("narrative_check") or {}
    if skipped or vc or nc.get("provided"):
        with st.container(border=True, key="card_tech_checks"):
            section_title("Intake and consistency checks")
            if skipped:
                render('<p class="ai-dl-title">Skipped files</p>' + bullet_list(skipped))
            if vc:
                render(f'<p class="ai-dl-title">Same-vehicle check: {esc(vc.get("status"))}</p>'
                       + (bullet_list(vc.get("evidence")) if vc.get("evidence") else "")
                       + f'<p class="ai-muted">{esc(vc.get("method", ""))}</p>')
            if nc.get("provided"):
                contra = nc.get("contradictions") or []
                render('<p class="ai-dl-title">Accident description check</p>'
                       + (bullet_list(contra) if contra else '<p class="ai-muted">No contradictions with the photos.</p>'))
    if w.get("timings"):
        with st.expander("Stage timings of this run"):
            render(bullet_list(f"{label}: {secs:.1f} s" for label, secs in w["timings"]))
    if a.assumptions or a.exclusions:
        with st.expander("Assumptions and exclusions"):
            render('<p class="ai-dl-title">Assumptions</p>' + bullet_list(a.assumptions)
                   + '<p class="ai-dl-title">Exclusions</p>' + bullet_list(a.exclusions))
    with st.expander("Raw assessment JSON"):
        st.json(json.loads(ex["json"]), expanded=1)
