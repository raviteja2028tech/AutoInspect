"""Deterministic cost arithmetic (Decimal, explicit rounding) and estimate totals.

    line_low  = parts_low  + labor_hours_low  * labor_rate_low  + paint_materials_low
    line_high = parts_high + labor_hours_high * labor_rate_high + paint_materials_high

One selected plan per component instance is summed. Unknown costs stay None (never 0).
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from .contracts import ComponentPlan, LineCost, PricingRecord, Totals

UNIT = Decimal("1")          # INR: whole rupees


def q(x: Decimal) -> Decimal:
    return Decimal(x).quantize(UNIT, rounding=ROUND_HALF_UP)


def line_cost(r: PricingRecord) -> LineCost:
    labor_low = q(r.labor_hours_low * r.labor_rate_low)
    labor_high = q(r.labor_hours_high * r.labor_rate_high)
    parts_low, parts_high = q(r.parts_cost_low), q(r.parts_cost_high)
    pm_low, pm_high = q(r.paint_materials_low), q(r.paint_materials_high)
    return LineCost(operation=r.operation, record_id=r.record_id, currency=r.currency,
                    tax_included=r.tax_included, parts_low=parts_low, parts_high=parts_high,
                    labor_low=labor_low, labor_high=labor_high, paint_materials_low=pm_low,
                    paint_materials_high=pm_high, low=parts_low + labor_low + pm_low,
                    high=parts_high + labor_high + pm_high)


def fmt_money(x: Decimal | None, currency: str = "INR") -> str:
    if x is None:
        return "not priced"
    return f"{currency} {int(x):,}"


def _sum(vals):
    vals = list(vals)
    return sum(vals, Decimal(0)) if vals else None


def compute_totals(plans: list[ComponentPlan], currency: str, tax_rate: Decimal | None) -> Totals:
    if not plans:
        return Totals(currency=currency, status="no_damage", tax_basis="n/a",
                      status_label="No visible damage findings to price.")

    priced = [p for p in plans if p.cost is not None]
    unresolved, unpriced = [], []
    for p in plans:
        if p.cost is not None:
            continue
        priced_alts = [s for s in p.alternatives if s.cost is not None]
        if p.action == "inspect" and priced_alts:
            unresolved.append(p)
        else:
            unpriced.append(p)

    lines = [p.cost for p in priced] + [s.cost for p in unresolved for s in p.alternatives if s.cost]
    tax_flags = {c.tax_included for c in lines}
    basis = "n/a" if not tax_flags else ("mixed" if len(tax_flags) > 1 else
                                         ("incl_tax" if tax_flags == {True} else "excl_tax"))
    notes = []
    obs_low = _sum(p.cost.low for p in priced)
    obs_high = _sum(p.cost.high for p in priced)

    excl_priced = [p.cost for p in priced if not p.cost.tax_included]
    tax_low = tax_high = with_low = with_high = None
    if basis == "mixed" and tax_rate is None:
        inc = [p.cost for p in priced if p.cost.tax_included]
        notes.append("Records mix tax-inclusive and tax-exclusive prices and no tax rate is configured; "
                     f"subtotals are kept separate: tax-inclusive {fmt_money(_sum(c.low for c in inc), currency)}"
                     f"-{fmt_money(_sum(c.high for c in inc), currency)}, tax-exclusive "
                     f"{fmt_money(_sum(c.low for c in excl_priced), currency)}-"
                     f"{fmt_money(_sum(c.high for c in excl_priced), currency)}.")
        obs_low = obs_high = None
    elif tax_rate is not None and priced:
        tax_low = q(_sum(c.low for c in excl_priced) * tax_rate) if excl_priced else Decimal(0)
        tax_high = q(_sum(c.high for c in excl_priced) * tax_rate) if excl_priced else Decimal(0)
        with_low, with_high = obs_low + tax_low, obs_high + tax_high
        notes.append(f"Tax at {tax_rate * 100}% applied only to tax-exclusive record amounts.")
    elif basis == "excl_tax":
        notes.append("All amounts exclude GST/taxes (no tax rate configured).")

    unres_low = _sum(min(s.cost.low for s in p.alternatives if s.cost) for p in unresolved)
    unres_high = _sum(max(s.cost.high for s in p.alternatives if s.cost) for p in unresolved)
    if unresolved:
        notes.append("Unresolved items (inspection needed) are shown as a separate scenario range "
                     "(cheapest to most expensive candidate operation), before tax.")

    env_low = env_high = None
    if obs_low is not None or unres_low is not None:
        env_low = (obs_low or Decimal(0)) + (unres_low or Decimal(0))
        env_high = (obs_high or Decimal(0)) + (unres_high or Decimal(0))

    if unpriced:
        status = "partial" if (priced or unresolved) else "insufficient_pricing_data"
        label = (f"PARTIAL estimate: {len(unpriced)} item(s) could not be priced "
                 f"({', '.join(p.component_instance for p in unpriced)}). The subtotal is NOT a complete estimate."
                 if status == "partial" else "Insufficient pricing data: no finding could be priced.")
    elif basis == "mixed" and tax_rate is None:
        status, label = "partial", "PARTIAL: mixed tax treatment prevents a combined total."
    else:
        status = "complete"
        label = ("Estimate covers every finding." if not unresolved else
                 f"All findings priced; {len(unresolved)} item(s) need inspection and are shown as a scenario range.")
    return Totals(currency=currency, status=status, status_label=label, tax_basis=basis,
                  observed_low=obs_low, observed_high=obs_high, tax_rate=tax_rate, tax_low=tax_low,
                  tax_high=tax_high, observed_with_tax_low=with_low, observed_with_tax_high=with_high,
                  unresolved_low=unres_low, unresolved_high=unres_high, envelope_low=env_low,
                  envelope_high=env_high, priced_components=[p.component_instance for p in priced],
                  unresolved_components=[p.component_instance for p in unresolved],
                  unpriced_components=[p.component_instance for p in unpriced], notes=notes)
