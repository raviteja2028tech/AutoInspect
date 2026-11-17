"""Damage map -> component plans -> retrieved pricing evidence -> validated estimate.

Command line (run from the project root, the folder with requirements.txt):

    python -m src.estimate samples/my_case_v2.json --year 2021 --out samples/estimate_my_case_v2.json
    python -m src.estimate samples/my_case_v2.json --year 2021 --clarify D5=side_mirror_left \
        --clarify D6=wheel_tire_front_right

Works without any vision API key: the input is an existing damage-map JSON (legacy or v2).
"""
from __future__ import annotations

import argparse
import json
import uuid
from collections import Counter
from decimal import Decimal
from pathlib import Path

from . import settings
from .components import adapt_damage_map, apply_clarifications, group_by_instance
from .contracts import (SYNTHETIC_LABEL, Assessment, ComponentPlan, PricingScope, Scenario, Uncertainty,
                        VehicleInfo, utcnow)
from .costing import compute_totals, fmt_money, line_cost
from .kb.retrieve import Query, Retriever, open_retriever
from .rules import RULES_VERSION, decide_group
from .vocab import VOCAB_VERSION

PAINTED = {"panel_plastic", "panel_bolt_on", "panel_welded"}

EXCLUSIONS = [
    "Hidden, internal, mechanical, electrical, structural-frame and safety-system (airbag/ADAS) damage is not assessed.",
    "Policy coverage, deductibles, depreciation, liability, settlement and claim approval are not determined.",
    "Towing, storage, rental and wheel alignment are not included.",
]


def _explain(p: ComponentPlan, ev, currency: str) -> str:
    r = ev.record
    c = p.cost
    return (f"{p.component_instance}: {', '.join(p.damage_ids)} ({', '.join(p.damage_types)}, worst {p.max_severity}) "
            f"-> {p.action} [{p.rule_id}: {p.reason}]. Priced from {r.record_id} "
            f"({ev.source_title}; {ev.source_type}; {ev.fallback_level}): parts {fmt_money(c.parts_low, currency)}-"
            f"{int(c.parts_high):,} + labour {r.labor_hours_low}-{r.labor_hours_high} h x {int(r.labor_rate_low)}-"
            f"{int(r.labor_rate_high)}/h + paint/materials {int(c.paint_materials_low):,}-"
            f"{int(c.paint_materials_high):,} = {fmt_money(c.low, currency)}-{int(c.high):,}."
            + (f" {p.covered_damage_note}" if p.covered_damage_note else ""))


def _price(retriever: Retriever, vehicle: VehicleInfo, scope: PricingScope, instance: str, op: str,
           damage_types, allow_broader: bool):
    res = retriever.retrieve(Query(vehicle, instance, op, scope.region, scope.currency,
                                   scope.part_grade_preference, tuple(damage_types)),
                             allow_broader=allow_broader)
    cost = line_cost(res.evidence[0].record) if res.status == "ok" else None
    return res, cost


def build_assessment(damage_map: dict, vehicle: VehicleInfo | dict | None = None,
                     scope: PricingScope | None = None, retriever: Retriever | None = None,
                     clarifications: dict | None = None, mode: str = "legacy_json",
                     allow_broader: bool = False, accident_description: str | None = None,
                     assessment_id: str | None = None, extra_warnings: list[str] | None = None) -> Assessment:
    if vehicle is None:
        vehicle = VehicleInfo(**{k: v for k, v in damage_map.get("vehicle", {}).items()
                                 if k in VehicleInfo.model_fields})
    elif isinstance(vehicle, dict):
        vehicle = VehicleInfo(**vehicle)
    scope = scope or PricingScope(region=settings.DEFAULT_REGION, currency=settings.DEFAULT_CURRENCY,
                                  tax_rate=settings.GST_RATE)
    retriever = retriever or open_retriever()

    observations = apply_clarifications(adapt_damage_map(damage_map), clarifications)
    groups = group_by_instance(observations)
    plans: list[ComponentPlan] = []
    fallback_levels, synthetic_used = Counter(), False

    for g in groups:
        d = decide_group(g)
        plan = ComponentPlan(
            component_instance=g.instance, component_class=g.cls,
            components_reported=sorted({o.component_reported for o in g.observations}),
            ambiguous=g.ambiguous, clarification=g.clarification_hint(), damage_ids=g.damage_ids,
            damage_types=g.damage_types, max_severity=g.max_severity, action=d.action, operation=d.operation,
            rule_id=d.rule_id, rule_version=RULES_VERSION, reason=d.reason, covered_damage_note=d.covered_note,
            pricing_status="not_priced_inspection", notes=list(d.notes))

        if d.rule_id == "G-AMB":
            plan.pricing_status = "ambiguous_component"
            plan.explanation = f"{g.instance}: not priced. {plan.clarification}"
        elif d.rule_id == "G-OTHER":
            plan.pricing_status = "unsupported_component"
            plan.explanation = f"{g.instance}: not priced; component outside the supported catalog."
        else:
            if d.operation:
                res, cost = _price(retriever, vehicle, scope, g.instance, d.operation, g.damage_types, allow_broader)
                plan.retrieval = res
                if cost:
                    ev = res.evidence[0]
                    plan.cost, plan.selected_record_id, plan.pricing_status = cost, ev.record_id, "priced"
                    fallback_levels[ev.fallback_level] += 1
                    synthetic_used |= ev.synthetic
                    plan.explanation = _explain(plan, ev, scope.currency)
                else:
                    plan.pricing_status = "insufficient_pricing_data"
                    plan.explanation = (f"{g.instance}: {d.action} recommended [{d.rule_id}] but no applicable "
                                        f"price record ({res.message}). Cost unknown (not zero).")
            for alt in d.alternatives:
                res, cost = _price(retriever, vehicle, scope, g.instance, alt, g.damage_types, allow_broader)
                if cost:
                    fallback_levels[res.evidence[0].fallback_level] += 1
                    synthetic_used |= res.evidence[0].synthetic
                plan.alternatives.append(Scenario(
                    operation=alt, cost=cost,
                    pricing_status="priced" if cost else "insufficient_pricing_data",
                    evidence_record_ids=[e.record_id for e in res.evidence],
                    description=(f"If inspection shows {alt} is appropriate" if d.action == "inspect"
                                 else f"Alternative outcome: {alt}")))
            if d.action == "inspect":
                priced_alts = [s for s in plan.alternatives if s.cost]
                plan.explanation = (f"{g.instance}: inspect [{d.rule_id}: {d.reason}]. "
                                    + (f"Scenario range {fmt_money(min(s.cost.low for s in priced_alts), scope.currency)}-"
                                       f"{int(max(s.cost.high for s in priced_alts)):,} from "
                                       f"{', '.join(s.evidence_record_ids[0] for s in priced_alts)} (not in observed subtotal)."
                                       if priced_alts else "No priced scenario available."))
        plans.append(plan)

    totals = compute_totals(plans, scope.currency, scope.tax_rate)

    # ----- uncertainty (heuristic, documented) -----
    pts, reasons = 0, []
    n_img = damage_map.get("images_analysed")
    if isinstance(n_img, int) and n_img < 3:
        pts += 1
        reasons.append(f"Image coverage: only {n_img} usable image(s); 3-5 views recommended.")
    vc = (damage_map.get("vehicle_consistency") or {}).get("status")
    if vc in ("conflict", "uncertain"):
        pts += 1
        reasons.append(f"Same-vehicle check across images: {vc}.")
    contra = (damage_map.get("narrative_check") or {}).get("contradictions") or []
    if contra:
        pts += 1
        reasons.append(f"Accident description disagrees with photos ({len(contra)} point(s)).")
    if any(o.legacy for o in observations):
        reasons.append("Input is a legacy damage map without image-linked regions; findings cannot be traced to boxes.")
    n_unres = len(totals.unresolved_components) + sum(p.action == "inspect" for p in plans
                                                      if p.component_instance in totals.unpriced_components)
    if n_unres:
        pts += 2 if n_unres >= 3 else 1
        reasons.append(f"{n_unres} finding(s) need physical inspection before the operation is known.")
    if totals.unpriced_components:
        pts += 2
        reasons.append(f"Missing prices for: {', '.join(totals.unpriced_components)}.")
    conflicted = [o.damage_id for o in observations if o.severity_unresolved]
    weak = [o.damage_id for o in observations
            if (o.uncertain or o.confidence < 0.5) and not o.severity_unresolved]
    if weak:
        pts += 1
        reasons.append(f"Low model scores on {', '.join(weak)} (or no strong supporting view; "
                       "scores are uncalibrated).")
    if conflicted:          # already counted above as findings needing inspection; no extra points
        reasons.append(f"Photos disagree on the severity of {', '.join(conflicted)}.")
    inexact = {k: v for k, v in fallback_levels.items() if k != "L0_exact"}
    if inexact:
        pts += 1
        reasons.append(f"Pricing applicability not exact: {dict(inexact)}.")
    if synthetic_used:
        pts += 1
        reasons.append("Price provenance: synthetic demonstration records, not market verified.")
    if not reasons:
        reasons.append("No specific risk factor detected (still a preliminary photo-based estimate).")
    level = "low" if pts <= 1 else ("medium" if pts <= 3 else "high")

    painted = [p for p in plans if p.component_class in PAINTED and p.cost is not None]
    assumptions = [
        "Each component instance is priced once with one selected operation; multiple findings on the "
        "same part share that plan.",
        "Labour hours, labour rates and paint/material costs come only from the cited record's numeric fields.",
    ]
    if len(painted) >= 2:
        assumptions.append(f"{len(painted)} painted panels are priced independently; a workshop may share "
                           "paint setup or blend adjacent panels, so the combined actual cost may be lower.")
    if not vehicle.year:
        assumptions.append("Vehicle year not supplied; model-year applicability of prices is not verified.")

    warnings = list(extra_warnings or [])
    if totals.status == "partial":
        warnings.append(totals.status_label)
    # Surface the vision pipeline's own warnings (coverage, duplicates, blur, severity/side
    # conflicts, identity, narrative contradictions) so UI and PDF show them, not only the raw map.
    for w in damage_map.get("warnings", []) or []:
        if isinstance(w, str) and w.strip() and w not in warnings:
            warnings.append(w)

    idx = retriever.index.meta
    return Assessment(
        assessment_id=assessment_id or f"VDA-{utcnow():%Y%m%d}-{uuid.uuid4().hex[:8]}",
        mode=mode, pricing_label=SYNTHETIC_LABEL if synthetic_used else None,
        vehicle=vehicle, pricing_scope=scope, accident_description=accident_description,
        damage_map=damage_map, observations=observations, component_plans=plans, totals=totals,
        uncertainty=Uncertainty(level=level, points=pts, reasons=reasons),
        assumptions=assumptions, exclusions=EXCLUSIONS, warnings=warnings,
        provenance={
            "rules_version": RULES_VERSION, "vocab_version": VOCAB_VERSION,
            "retrieval": {"embedding_model": idx["embedding_model"], "method": idx["retrieval_method"],
                          "corpus_hash": idx["corpus_hash"][:16], "index_built_at": idx["built_at"],
                          "n_records": idx["n_records"], "n_synthetic_records": idx["n_synthetic"],
                          "allow_broader_reference": allow_broader},
            "clarifications": clarifications or {},
            "vision_meta": damage_map.get("meta", {}),
        },
    )


def save_assessment(a: Assessment, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(a.model_dump_json(indent=2), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Build a cost estimate from a damage-map JSON (no vision key needed).")
    ap.add_argument("damage_map", help="legacy or v2 damage-map JSON (e.g. samples/my_case_v2.json)")
    ap.add_argument("--make")
    ap.add_argument("--model")
    ap.add_argument("--year", type=int)
    ap.add_argument("--variant", default="")
    ap.add_argument("--region", default=settings.DEFAULT_REGION)
    ap.add_argument("--currency", default=settings.DEFAULT_CURRENCY)
    ap.add_argument("--grade", default="oem", choices=["oem", "aftermarket"])
    ap.add_argument("--tax-rate", type=Decimal, default=settings.GST_RATE, help="e.g. 0.18; default none")
    ap.add_argument("--clarify", action="append", default=[], metavar="ID=INSTANCE",
                    help="resolve an ambiguous part, e.g. D5=side_mirror_left (repeatable)")
    ap.add_argument("--allow-broader-reference", action="store_true",
                    help="allow labelled other-model-year records when no exact record exists")
    ap.add_argument("--lexical-fallback", action="store_true",
                    help="if the embedding model cannot load, use labelled lexical ranking")
    ap.add_argument("--out")
    args = ap.parse_args()

    dm = json.loads(Path(args.damage_map).read_text(encoding="utf-8"))
    v = dict(dm.get("vehicle", {}))
    for k in ("make", "model", "year", "variant"):
        if getattr(args, k):
            v[k] = getattr(args, k)
    vehicle = VehicleInfo(**{k: val for k, val in v.items() if k in VehicleInfo.model_fields})
    clar = dict(c.split("=", 1) for c in args.clarify)
    scope = PricingScope(region=args.region, currency=args.currency, part_grade_preference=args.grade,
                         tax_rate=args.tax_rate)
    retriever = open_retriever(allow_lexical_fallback=args.lexical_fallback)
    a = build_assessment(dm, vehicle, scope, retriever, clar, mode="legacy_json",
                         allow_broader=args.allow_broader_reference)

    cur = a.totals.currency
    print(f"Assessment {a.assessment_id}  [{a.disclaimer}]")
    if a.pricing_label:
        print(f"*** {a.pricing_label} ***")
    print(f"Vehicle (user supplied): {vehicle.make} {vehicle.model} {vehicle.year or '(year not given)'}  "
          f"| region {scope.region} | retrieval {retriever.method} ({retriever.index.meta['embedding_model']})")
    for p in a.component_plans:
        price = (f"{fmt_money(p.cost.low, cur)} - {int(p.cost.high):,}" if p.cost else p.pricing_status)
        print(f"  {p.component_instance:24s} {p.action:8s} {p.rule_id:12s} {price:28s} "
              f"evidence={[e.record_id for e in (p.retrieval.evidence if p.retrieval else [])]}")
    t = a.totals
    print(f"Status: {t.status} - {t.status_label}")
    print(f"Observed subtotal: {fmt_money(t.observed_low, cur)} - {fmt_money(t.observed_high, cur)} ({t.tax_basis})")
    if t.unresolved_low is not None:
        print(f"Unresolved scenarios: {fmt_money(t.unresolved_low, cur)} - {fmt_money(t.unresolved_high, cur)}")
    print(f"Uncertainty: {a.uncertainty.level} ({'; '.join(a.uncertainty.reasons)})")
    if args.out:
        save_assessment(a, Path(args.out))
        print(f"Saved to {args.out}")


if __name__ == "__main__":
    main()
