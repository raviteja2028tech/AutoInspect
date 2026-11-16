"""Render a serialized assessment dictionary into a PDF report with ReportLab.

The module deliberately imports nothing from the rest of ``src`` so that it stays
stable while the pipeline and contracts evolve. It never calls an LLM, never needs an
API key and never computes prices: every amount shown is copied from the input.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence
from xml.sax.saxutils import escape as _xml_escape

DISCLAIMER = ("Preliminary AI-assisted assessment. Not insurance approval or a substitute "
              "for physical inspection.")

RUPEE = "\u20b9"
NOT_AVAILABLE = "Not available"

# TrueType fonts tried in order; the first one that has the rupee glyph is used.
# Tests may monkeypatch this list (e.g. to [] to force the built-in Helvetica path).
FONT_CANDIDATES: list[tuple[str, str]] = [
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ("C:/Windows/Fonts/Nirmala.ttf", "C:/Windows/Fonts/NirmalaB.ttf"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
     "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"),
    ("/System/Library/Fonts/Supplemental/Arial.ttf",
     "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    ("/Library/Fonts/Arial Unicode.ttf", ""),
]

_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_CELL_LIMIT = 1200          # table cells are capped so no single row can exceed a page
_SYNTHETIC_TOKENS = {"synthetic_demo"}
_DEMO_MODES = {"sample_fixture", "sample", "demo", "fixture"}


# --------------------------------------------------------------------------- text helpers
def _clean(value: Any) -> str:
    """Plain text for any value; lists are comma-joined, control characters dropped."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (list, tuple, set)):
        return ", ".join(_clean(v) for v in value if v not in (None, ""))
    return _CTRL.sub("", str(value))


def _esc(value: Any, limit: Optional[int] = None) -> str:
    """Escape user text for ReportLab Paragraph markup (``& < > "``) and keep line breaks."""
    text = _clean(value)
    if limit is not None and len(text) > limit:
        text = text[:limit] + " ... [truncated; see full text above/below]"
    return _xml_escape(text, {'"': "&quot;"}).replace("\t", "    ").replace("\n", "<br/>")


def _get(mapping: Any, *keys: str, default: Any = None) -> Any:
    """Safe nested lookup that tolerates missing keys and non-dict values."""
    cur = mapping
    for key in keys:
        if not isinstance(cur, Mapping):
            return default
        cur = cur.get(key)
        if cur is None:
            return default
    return cur


def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _to_decimal(value: Any) -> Optional[Decimal]:
    if value is None or isinstance(value, bool) or value == "":
        return None
    if isinstance(value, Decimal):
        return value if value.is_finite() else None
    try:
        dec = Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, ValueError):
        return None
    return dec if dec.is_finite() else None


# --------------------------------------------------------------------------- fonts
class _Fonts:
    def __init__(self, regular: str, bold: str, rupee: bool):
        self.regular, self.bold, self.rupee = regular, bold, rupee


_FONT_CACHE: dict[tuple, _Fonts] = {}


def _resolve_fonts() -> _Fonts:
    key = tuple(tuple(c) for c in FONT_CANDIDATES)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    from reportlab.lib.fonts import addMapping
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    fonts = _Fonts("Helvetica", "Helvetica-Bold", rupee=False)
    for idx, (regular_path, bold_path) in enumerate(FONT_CANDIDATES):
        try:
            if not regular_path or not os.path.isfile(regular_path):
                continue
            reg_name = f"VDRReport-Regular-{idx}"
            reg = TTFont(reg_name, regular_path)
            if ord(RUPEE) not in getattr(reg.face, "charToGlyph", {}):
                continue
            pdfmetrics.registerFont(reg)
            bold_name = reg_name
            if bold_path and os.path.isfile(bold_path):
                try:
                    bold_name = f"VDRReport-Bold-{idx}"
                    pdfmetrics.registerFont(TTFont(bold_name, bold_path))
                except Exception:
                    bold_name = reg_name
            for b, i, name in ((0, 0, reg_name), (1, 0, bold_name),
                               (0, 1, reg_name), (1, 1, bold_name)):
                addMapping(reg_name, b, i, name)
            fonts = _Fonts(reg_name, bold_name, rupee=True)
            break
        except Exception:
            continue
    _FONT_CACHE[key] = fonts
    return fonts


# --------------------------------------------------------------------------- money
class _Money:
    def __init__(self, fonts: _Fonts):
        self.fonts = fonts

    def prefix(self, currency: Any) -> str:
        cur = _clean(currency).strip().upper()
        if cur == "INR":
            return RUPEE if self.fonts.rupee else "INR "
        return f"{cur} " if cur else ""

    def fmt(self, value: Any, currency: Any) -> str:
        """Format one amount. ``None``/missing -> 'Not available'; never coerced to zero."""
        if value is None or value == "":
            return NOT_AVAILABLE
        dec = _to_decimal(value)
        if dec is None:
            return f"{_clean(value)} (unparsed)"
        text = f"{dec:,.2f}"
        if not _clean(currency).strip():
            return f"{text} (currency not stated)"
        return f"{self.prefix(currency)}{text}"

    def rng(self, low: Any, high: Any, currency: Any) -> str:
        if low in (None, "") and high in (None, ""):
            return NOT_AVAILABLE
        lo, hi = self.fmt(low, currency), self.fmt(high, currency)
        return lo if lo == hi else f"{lo} \u2013 {hi}"


# --------------------------------------------------------------------------- flags
def _evidence_items(assessment: Mapping) -> list[tuple[str, Mapping]]:
    out = []
    for plan in _as_list(assessment.get("component_plans")):
        if not isinstance(plan, Mapping):
            continue
        name = _clean(plan.get("component_instance") or plan.get("component") or "?")
        for ev in _as_list(_get(plan, "retrieval", "evidence")):
            if isinstance(ev, Mapping):
                out.append((name, ev))
    for ev in _as_list(assessment.get("pricing_references")):
        if isinstance(ev, Mapping):
            out.append((_clean(ev.get("component") or "-"), ev))
    return out


def _ev_synthetic(ev: Mapping) -> Optional[bool]:
    if ev.get("synthetic") is True:
        return True
    if (ev.get("source_type") in _SYNTHETIC_TOKENS
            or _get(ev, "record", "data_quality") in _SYNTHETIC_TOKENS
            or ev.get("data_quality") in _SYNTHETIC_TOKENS):
        return True
    if ev.get("synthetic") is False:
        return False
    return None


def _is_synthetic(assessment: Mapping) -> bool:
    if assessment.get("pricing_label") or assessment.get("synthetic_pricing"):
        return True
    if _get(assessment, "provenance", "synthetic_pricing"):
        return True
    return any(_ev_synthetic(ev) for _, ev in _evidence_items(assessment))


def _is_demo(assessment: Mapping) -> bool:
    if _clean(assessment.get("mode")).lower() in _DEMO_MODES:
        return True
    for flag in ("demo", "demo_mode", "sample_mode", "is_demo", "is_sample"):
        if assessment.get(flag) or _get(assessment, "provenance", flag):
            return True
    return False


# --------------------------------------------------------------------------- images
def _scaled_size(width: float, height: float, max_w: float, max_h: float) -> tuple[float, float]:
    """Fit (width, height) inside (max_w, max_h) preserving aspect ratio; never upscale."""
    if width <= 0 or height <= 0:
        raise ValueError("image has no size")
    scale = min(max_w / width, max_h / height, 1.0)
    return width * scale, height * scale


def _normalise_images(image_paths: Any) -> list[tuple[str, str]]:
    if image_paths is None:
        return []
    if isinstance(image_paths, (str, os.PathLike)):
        image_paths = [image_paths]
    out = []
    for item in image_paths:
        if isinstance(item, Mapping):
            out.append((_clean(item.get("path")), _clean(item.get("caption"))))
        elif isinstance(item, (tuple, list)) and item:
            out.append((_clean(os.fspath(item[0]) if isinstance(item[0], os.PathLike) else item[0]),
                        _clean(item[1]) if len(item) > 1 else ""))
        elif item is not None:
            out.append((_clean(os.fspath(item) if isinstance(item, os.PathLike) else item), ""))
    return out


# --------------------------------------------------------------------------- main entry
def generate_pdf_report(assessment: Mapping[str, Any], output_path: Any,
                        image_paths: Optional[Sequence[Any]] = None) -> Path:
    """Write a PDF report for one assessment and return the output path.

    ``assessment`` is a plain dict, typically ``Assessment.model_dump(mode="json")``
    (an object with ``model_dump`` is also accepted). Every key is optional; anything
    missing is shown as "Not supplied"/"Not available" -- never as zero.

    Expected input mapping (names match ``src/contracts.py`` ``Assessment``):

    * ``assessment_id``: str; ``created_at``: ISO datetime string (shown verbatim).
    * ``mode``: ``"live" | "sample_fixture" | "legacy_json"``. ``sample_fixture`` (or any
      truthy ``demo`` / ``sample_mode`` / ``is_demo`` key, top level or in ``provenance``)
      prints a SAMPLE / DEMO banner on page 1 and in every page header.
    * ``pricing_label``: str. If set, or ``synthetic_pricing`` is truthy, or any retrieved
      evidence has ``synthetic: true`` / ``source_type == "synthetic_demo"`` /
      ``record.data_quality == "synthetic_demo"``, a SYNTHETIC PRICING banner is shown.
    * ``disclaimer``: str (printed in addition to the fixed disclaimer if different).
    * ``vehicle``: {make, model, year, variant, reg_no, source}; extra keys are listed too.
    * ``pricing_scope``: {region, currency, part_grade_preference, tax_rate}.
    * ``accident_description``: str.
    * ``observations``: [{damage_id, component, component_reported, damage_type, severity,
      location, confidence, uncertain, evidence, severity_rationale}].
    * ``component_plans``: [{component_instance, component_class, damage_types,
      max_severity, action, operation, rule_id, reason, explanation, covered_damage_note,
      clarification, notes[], pricing_status, selected_record_id,
      cost: {low, high, currency, record_id, operation, tax_included, parts_low, ...} | None,
      alternatives: [{operation, description, pricing_status, cost, evidence_record_ids}],
      retrieval: {status, message, fallback_level, evidence: [{record_id, source_id,
      source_title, source_type, synthetic, score, rank, fallback_level,
      applicability_reason, record: {data_quality, ...}}]}}].
    * ``totals``: {currency, status ("complete"|"partial"|"insufficient_pricing_data"|
      "no_damage"), status_label, tax_basis, observed_low/high, tax_rate, tax_low/high,
      observed_with_tax_low/high, unresolved_low/high, envelope_low/high,
      priced_components[], unresolved_components[], unpriced_components[], notes[]}.
      Totals are displayed exactly as supplied; nothing is summed here. Unless
      ``status == "complete"`` and nothing is listed as unpriced/unresolved, the observed
      amount is labelled as a PARTIAL subtotal.
    * ``uncertainty``: {level, points, reasons[], method}.
    * ``assumptions[]``, ``exclusions[]``, ``warnings[]``: str lists.
    * ``pricing_references`` (optional, non-contract): extra reference dicts shaped like
      retrieval evidence, plus an optional ``component``.

    Money values may be Decimal, int, float or numeric strings. INR is printed with the
    rupee sign only when a TrueType font containing that glyph is found, otherwise "INR".

    ``image_paths``: optional sequence of paths, ``(path, caption)`` tuples or
    ``{"path", "caption"}`` dicts. Images keep their aspect ratio; missing or unreadable
    files are reported in the PDF instead of failing the build.

    Raises ``ImportError`` with an explicit message when ReportLab is not installed.
    """
    try:
        import reportlab  # noqa: F401
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise ImportError("generate_pdf_report requires ReportLab: pip install reportlab") from exc

    if hasattr(assessment, "model_dump"):
        assessment = assessment.model_dump(mode="json")
    if not isinstance(assessment, Mapping):
        raise TypeError("assessment must be a dict (e.g. Assessment.model_dump(mode='json'))")

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".part")
    try:
        _build(assessment, tmp, _normalise_images(image_paths))
        os.replace(tmp, out)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
    return out


# --------------------------------------------------------------------------- builder
def _build(a: Mapping, path: Path, images: list[tuple[str, str]]) -> None:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.platypus import (Image, KeepTogether, LongTable, Paragraph,
                                    SimpleDocTemplate, Spacer, Table, TableStyle)

    fonts = _resolve_fonts()
    money = _Money(fonts)
    synthetic, demo = _is_synthetic(a), _is_demo(a)

    base = getSampleStyleSheet()
    body = ParagraphStyle("vdr_body", parent=base["BodyText"], fontName=fonts.regular,
                          fontSize=9, leading=11.5, splitLongWords=1)
    small = ParagraphStyle("vdr_small", parent=body, fontSize=8, leading=10)
    cell = ParagraphStyle("vdr_cell", parent=small, spaceBefore=0, spaceAfter=0)
    cell_b = ParagraphStyle("vdr_cell_b", parent=cell, fontName=fonts.bold)
    h1 = ParagraphStyle("vdr_h1", parent=base["Title"], fontName=fonts.bold, fontSize=17,
                        leading=21)
    h2 = ParagraphStyle("vdr_h2", parent=base["Heading2"], fontName=fonts.bold, fontSize=12.5,
                        leading=15, spaceBefore=10, spaceAfter=4)
    h3 = ParagraphStyle("vdr_h3", parent=base["Heading3"], fontName=fonts.bold, fontSize=10,
                        leading=12.5, spaceBefore=6, spaceAfter=2)
    banner = ParagraphStyle("vdr_banner", parent=body, fontName=fonts.bold, fontSize=10,
                            leading=13, alignment=TA_CENTER, textColor=colors.HexColor("#8a1c1c"))
    disc = ParagraphStyle("vdr_disc", parent=body, fontName=fonts.bold, fontSize=9.5,
                          leading=12, textColor=colors.HexColor("#333333"))

    page_w, page_h = A4
    margin = 15 * mm
    frame_w = page_w - 2 * margin

    def P(text_markup: str, style=body):
        return Paragraph(text_markup, style)

    def C(value: Any, style=cell) -> Paragraph:
        return Paragraph(_esc(value, limit=_CELL_LIMIT) or "-", style)

    grid = TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#9a9a9a")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e4e8ee")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ])
    kv_style = TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b5b5b5")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f1f3f6")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ])

    def table(header: list[str], rows: list[list[Any]], widths: list[float]):
        data = [[C(h, cell_b) for h in header]]
        data += [[v if isinstance(v, Paragraph) else C(v) for v in r] for r in rows]
        t = LongTable(data, colWidths=widths, repeatRows=1)
        t.setStyle(grid)
        return t

    def kv(rows: list[tuple[str, Any]], key_w: float = 42 * mm):
        data = [[C(k, cell_b), v if isinstance(v, Paragraph) else C(v)] for k, v in rows]
        t = LongTable(data, colWidths=[key_w, frame_w - key_w])
        t.setStyle(kv_style)
        return t

    def banner_box(text: str, fill: str):
        t = Table([[P(_esc(text), banner)]], colWidths=[frame_w])
        t.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 1.2, colors.HexColor("#8a1c1c")),
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(fill)),
            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        return t

    def bullets(items: Iterable[Any], empty: str):
        items = [i for i in items if _clean(i).strip()]
        if not items:
            return [P(f"<i>{_esc(empty)}</i>", small)]
        return [P("&bull; " + _esc(i), body) for i in items]

    story: list = []
    aid = _clean(a.get("assessment_id")) or "Not supplied"
    currency_default = (_get(a, "totals", "currency") or _get(a, "pricing_scope", "currency") or "")

    # ---------------------------------------------------------------- 1. title & vehicle
    story.append(P("Vehicle Damage Assessment Report", h1))
    if demo:
        story += [banner_box("SAMPLE / DEMO MODE \u2014 generated from sample or fixture data, "
                             "not a live analysis of a customer vehicle.", "#fff4d6"),
                  Spacer(1, 4)]
    if synthetic:
        label = _clean(a.get("pricing_label")) or "Illustrative demo pricing \u2014 not market verified."
        story += [banner_box(f"SYNTHETIC PRICING \u2014 {label}", "#fde3e3"), Spacer(1, 4)]
    story += [P(_esc(DISCLAIMER), disc), Spacer(1, 6)]

    generated = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    meta = [("Assessment ID", aid),
            ("Assessment date", _clean(a.get("created_at")) or "Not supplied"),
            ("Report generated (UTC)", generated),
            ("Mode", _clean(a.get("mode")) or "Not supplied")]
    if a.get("schema_version"):
        meta.append(("Schema version", a.get("schema_version")))
    scope = a.get("pricing_scope") if isinstance(a.get("pricing_scope"), Mapping) else {}
    if scope:
        meta.append(("Pricing scope",
                     ", ".join(f"{k.replace('_', ' ')}: {_clean(v)}"
                               for k, v in scope.items() if v not in (None, ""))
                     or "Not supplied"))
    story.append(kv(meta))

    story.append(P("Vehicle details (user-supplied)", h2))
    vehicle = a.get("vehicle") if isinstance(a.get("vehicle"), Mapping) else {}
    labels = {"make": "Make", "model": "Model", "year": "Year", "variant": "Variant",
              "reg_no": "Registration no.", "source": "Details source"}
    vrows = [(labels.get(k, k.replace("_", " ").capitalize()), v)
             for k, v in vehicle.items() if v not in (None, "")]
    story.append(kv(vrows) if vrows else P("<i>No vehicle details supplied.</i>", small))
    if _clean(a.get("accident_description")).strip():
        story += [P("Accident description (user-supplied)", h3), P(_esc(a["accident_description"]))]

    # ---------------------------------------------------------------- 2. findings
    story.append(P("Component findings and recommendations", h2))
    obs = [o for o in _as_list(a.get("observations")) if isinstance(o, Mapping)]
    if obs:
        story.append(P("Detected damage", h3))
        rows = []
        for o in obs:
            conf = o.get("confidence")
            conf_txt = f"{conf:.2f}" if isinstance(conf, (int, float)) and not isinstance(conf, bool) \
                else (_clean(conf) or "-")
            rows.append([o.get("damage_id"), o.get("component") or o.get("component_reported"),
                         o.get("damage_type"), o.get("severity"), o.get("location"), conf_txt,
                         "Yes" if o.get("uncertain") else "No"])
        w = [frame_w * f for f in (0.12, 0.26, 0.16, 0.12, 0.14, 0.10, 0.10)]
        story.append(table(["Damage ID", "Component", "Damage type", "Severity", "Location",
                            "Confidence", "Uncertain"], rows, w))
        detail = [o for o in obs if o.get("evidence") or o.get("severity_rationale")]
        for o in detail:
            bits = []
            if o.get("evidence"):
                bits.append(f"<b>Evidence:</b> {_esc(o['evidence'])}")
            if o.get("severity_rationale"):
                bits.append(f"<b>Severity rationale:</b> {_esc(o['severity_rationale'])}")
            story.append(P(f"<b>{_esc(o.get('damage_id') or '-')}</b> \u2014 " + " ".join(bits), small))

    plans = [p for p in _as_list(a.get("component_plans")) if isinstance(p, Mapping)]
    if not plans:
        story.append(P("<i>No component plans were supplied.</i>", small))
    for i, plan in enumerate(plans, 1):
        name = plan.get("component_instance") or plan.get("component") or "Unnamed component"
        cls = plan.get("component_class")
        title = f"{i}. {_esc(name)}" + (f" ({_esc(cls)})" if cls and cls != name else "")
        action, op = _clean(plan.get("action")), _clean(plan.get("operation"))
        rec = action or "Not supplied"
        if op and op != action:
            rec += f" (operation: {op})"
        rows = [("Damage types", plan.get("damage_types") or "Not supplied"),
                ("Max severity", plan.get("max_severity") or "Not supplied"),
                ("Recommendation", rec),
                ("Pricing status", plan.get("pricing_status") or "Not supplied")]
        if plan.get("components_reported"):
            rows.append(("Reported as", plan["components_reported"]))
        if plan.get("rule_id"):
            rows.append(("Rule", f"{_clean(plan['rule_id'])} {_clean(plan.get('rule_version'))}".strip()))
        if plan.get("ambiguous") or plan.get("clarification"):
            rows.append(("Clarification needed", plan.get("clarification") or "Component is ambiguous"))
        story += [P(title, h3), kv(rows)]
        for label, key in (("Reason", "reason"), ("Explanation", "explanation"),
                           ("Covered damage", "covered_damage_note")):
            if _clean(plan.get(key)).strip():
                story.append(P(f"<b>{label}:</b> {_esc(plan[key])}"))
        for note in _as_list(plan.get("notes")):
            if _clean(note).strip():
                story.append(P("&bull; " + _esc(note), small))
        for alt in _as_list(plan.get("alternatives")):
            if isinstance(alt, Mapping):
                story.append(P(f"<b>Alternative \u2014 {_esc(alt.get('operation') or '?')}:</b> "
                               f"{_esc(alt.get('description'))} "
                               f"[pricing: {_esc(alt.get('pricing_status') or 'not stated')}]", small))

    # ---------------------------------------------------------------- 3. costs
    story.append(P("Itemized cost ranges", h2))
    cost_rows: list[list[Any]] = []
    for plan in plans:
        name = plan.get("component_instance") or plan.get("component") or "-"
        cost = plan.get("cost") if isinstance(plan.get("cost"), Mapping) else None
        status = _clean(plan.get("pricing_status")) or "not stated"
        if cost:
            cur = cost.get("currency") or currency_default
            tax = cost.get("tax_included")
            tax_txt = "" if tax is None else (" (tax incl.)" if tax else " (excl. tax)")
            cost_rows.append([name, _clean(cost.get("operation") or plan.get("operation")) or "-",
                              status + tax_txt, money.fmt(cost.get("low"), cur),
                              money.fmt(cost.get("high"), cur),
                              cost.get("record_id") or plan.get("selected_record_id") or "-"])
        else:
            cost_rows.append([name, _clean(plan.get("operation") or plan.get("action")) or "-",
                              status, "Not priced", "Not priced",
                              plan.get("selected_record_id") or "-"])
        for alt in _as_list(plan.get("alternatives")):
            if not isinstance(alt, Mapping):
                continue
            acost = alt.get("cost") if isinstance(alt.get("cost"), Mapping) else None
            cur = (acost or {}).get("currency") or currency_default
            cost_rows.append([f"{_clean(name)} \u2014 alternative scenario",
                              alt.get("operation") or "-",
                              _clean(alt.get("pricing_status")) or "not stated",
                              money.fmt(acost.get("low"), cur) if acost else "Not priced",
                              money.fmt(acost.get("high"), cur) if acost else "Not priced",
                              (acost or {}).get("record_id") or alt.get("evidence_record_ids") or "-"])
    if cost_rows:
        w = [frame_w * f for f in (0.24, 0.11, 0.21, 0.14, 0.14, 0.16)]
        story.append(table(["Component", "Operation", "Pricing status", "Low", "High",
                            "Record ID"], cost_rows, w))
        story.append(P("<i>\u201cNot priced\u201d means no supported price was available. It is "
                       "not zero and is not included in any subtotal.</i>", small))
    else:
        story.append(P("<i>No itemized costs were supplied.</i>", small))

    story.append(P("Totals (as supplied)", h3))
    totals = a.get("totals") if isinstance(a.get("totals"), Mapping) else None
    if not totals:
        story.append(P("<i>No totals supplied. No total is shown and none has been "
                       "calculated by this report.</i>", small))
    else:
        cur = totals.get("currency") or currency_default
        status = _clean(totals.get("status"))
        unpriced = _as_list(totals.get("unpriced_components"))
        unresolved = _as_list(totals.get("unresolved_components"))
        # "complete" (engine status) = every finding priced, either in the observed subtotal or as an
        # inspection scenario range. Only unpriced items make the totals partial.
        complete = status == "complete" and not unpriced
        if complete and unresolved:
            obs_label = "Observed subtotal (excludes inspection items; see scenario range)"
        elif complete:
            obs_label = "Observed total (all findings priced)"
        elif status in ("", "unknown"):
            obs_label = "Observed subtotal (completeness not stated)"
        else:
            obs_label = "PARTIAL subtotal \u2014 priced components only"
        trows: list[tuple[str, Any]] = [
            ("Status", " \u2014 ".join(x for x in (status, _clean(totals.get("status_label"))) if x)
             or "Not stated"),
            ("Tax basis", totals.get("tax_basis") or "Not stated"),
            (obs_label, money.rng(totals.get("observed_low"), totals.get("observed_high"), cur)),
        ]
        if totals.get("tax_rate") is not None or totals.get("tax_low") is not None:
            trows.append((f"Tax (rate {_clean(totals.get('tax_rate')) or 'not stated'})",
                          money.rng(totals.get("tax_low"), totals.get("tax_high"), cur)))
        if totals.get("observed_with_tax_low") is not None or totals.get("observed_with_tax_high") is not None:
            trows.append(((obs_label + " incl. tax") if not complete else "Observed total incl. tax",
                          money.rng(totals.get("observed_with_tax_low"),
                                    totals.get("observed_with_tax_high"), cur)))
        trows.append(("Unresolved alternative scenarios",
                      money.rng(totals.get("unresolved_low"), totals.get("unresolved_high"), cur)))
        trows.append(("Envelope (observed + unresolved)",
                      money.rng(totals.get("envelope_low"), totals.get("envelope_high"), cur)))
        trows.append(("Priced components", totals.get("priced_components") or "None listed"))
        trows.append(("Unresolved components", unresolved or "None listed"))
        trows.append(("Unpriced components (excluded)", unpriced or "None listed"))
        story.append(kv(trows, key_w=62 * mm))
        if not complete:
            excluded = ", ".join(_clean(x) for x in unpriced) or "see itemized table"
            story.append(Spacer(1, 3))
            story.append(banner_box("Totals are PARTIAL: they exclude components without a supported "
                                    f"price ({excluded}). The real repair cost may be higher.",
                                    "#fff4d6"))
        if unresolved:
            story.append(Spacer(1, 3))
            story.append(banner_box(
                f"{len(unresolved)} item(s) need physical inspection ({', '.join(_clean(x) for x in unresolved)}); "
                "their cost is the unresolved scenario range, not part of the observed subtotal. "
                "The envelope shows the combined range.", "#fff4d6"))
        for note in _as_list(totals.get("notes")):
            if _clean(note).strip():
                story.append(P("&bull; " + _esc(note), small))

    # ---------------------------------------------------------------- 4. references
    story.append(P("Retrieved pricing references", h2))
    refs = _evidence_items(a)
    selected = {(_clean(p.get("component_instance") or p.get("component") or "?"),
                 _clean(p.get("selected_record_id") or _get(p, "cost", "record_id")))
                for p in plans}
    if refs:
        rows = []
        for comp, ev in refs:
            syn = _ev_synthetic(ev)
            rec_id = _clean(ev.get("record_id")) or "-"
            if (comp, rec_id) in selected:
                rec_id += " (selected)"
            src = " / ".join(x for x in (_clean(ev.get("source_title")),
                                         _clean(ev.get("source_type")),
                                         _clean(_get(ev, "record", "data_quality"))) if x)
            extra = " | ".join(x for x in (
                f"fallback: {_clean(ev.get('fallback_level'))}" if ev.get("fallback_level") else "",
                _clean(ev.get("applicability_reason"))) if x)
            if extra:
                src = f"{src}\n{extra[:300]}" if src else extra[:300]
            score = ev.get("score")
            score_txt = (f"{score:.3f}" if isinstance(score, (int, float)) and not isinstance(score, bool)
                         else _clean(score) or "-")
            rows.append([comp, _clean(ev.get("rank")) or "-", rec_id,
                         _clean(ev.get("source_id")) or "-", src or "-",
                         "YES" if syn else ("No" if syn is False else "Unknown"), score_txt])
        w = [frame_w * f for f in (0.15, 0.05, 0.17, 0.15, 0.29, 0.09, 0.10)]
        story.append(table(["Component", "#", "Record ID", "Source ID", "Source / type / notes",
                            "Synthetic", "Score"], rows, w))
        story.append(P("<i>Score is retrieval similarity used for ranking only; it is not a "
                       "probability or a measure of price accuracy.</i>", small))
    else:
        story.append(P("<i>No retrieved pricing references were supplied.</i>", small))
    for plan in plans:
        r = plan.get("retrieval") if isinstance(plan.get("retrieval"), Mapping) else None
        if r and r.get("status") and r.get("status") != "ok":
            story.append(P(f"&bull; {_esc(plan.get('component_instance') or '-')}: retrieval "
                           f"{_esc(r.get('status'))}. {_esc(r.get('message'))}", small))

    # ---------------------------------------------------------------- 5. uncertainty etc.
    story.append(P("Uncertainty, assumptions and exclusions", h2))
    unc = a.get("uncertainty") if isinstance(a.get("uncertainty"), Mapping) else None
    if unc:
        lvl = _clean(unc.get("level")).upper() or "NOT STATED"
        pts = f" ({_clean(unc.get('points'))} points)" if unc.get("points") is not None else ""
        story.append(P(f"<b>Uncertainty level:</b> {_esc(lvl)}{_esc(pts)}"))
        story += bullets(_as_list(unc.get("reasons")), "No uncertainty reasons supplied.")
        if unc.get("method"):
            story.append(P(f"<i>Method: {_esc(unc['method'])}</i>", small))
    else:
        story.append(P("<i>No uncertainty assessment supplied.</i>", small))

    story.append(P("Unpriced or unresolved components", h3))
    unpriced_lines = []
    tot = totals or {}
    for c in _as_list(tot.get("unpriced_components")):
        unpriced_lines.append(f"{_clean(c)}: excluded from totals (no supported price)")
    for c in _as_list(tot.get("unresolved_components")):
        unpriced_lines.append(f"{_clean(c)}: unresolved \u2014 alternative scenario kept open")
    listed = {_clean(c) for c in _as_list(tot.get("unpriced_components"))}
    for plan in plans:
        name = _clean(plan.get("component_instance") or plan.get("component"))
        if not isinstance(plan.get("cost"), Mapping) and name and name not in listed:
            unpriced_lines.append(f"{name}: {_clean(plan.get('pricing_status')) or 'no cost supplied'}")
    story += bullets(unpriced_lines, "None reported.")

    for heading, key, empty in (("Assumptions", "assumptions", "None supplied."),
                                ("Exclusions", "exclusions", "None supplied."),
                                ("Warnings", "warnings", "None.")):
        story.append(P(heading, h3))
        story += bullets(_as_list(a.get(key)), empty)

    # ---------------------------------------------------------------- 6. images
    story.append(P("Image evidence", h2))
    if not images:
        story.append(P("<i>No images were attached to this report.</i>", small))
    max_w, max_h = frame_w, 95 * mm
    for n, (img_path, caption) in enumerate(images, 1):
        label = f"Image {n}: {_esc(caption or os.path.basename(img_path) or img_path)}"
        if not img_path or not os.path.isfile(img_path):
            story.append(P(f"<b>{label}</b> \u2014 <font color='#8a1c1c'>image not available: file "
                           f"not found ({_esc(img_path or 'no path given')}).</font>", small))
            continue
        try:
            iw, ih = ImageReader(img_path).getSize()
            w, h = _scaled_size(float(iw), float(ih), max_w, max_h)
            story.append(KeepTogether([Image(img_path, width=w, height=h),
                                       P(label, small), Spacer(1, 6)]))
        except Exception as exc:  # unreadable / unsupported image
            story.append(P(f"<b>{label}</b> \u2014 <font color='#8a1c1c'>image could not be read "
                           f"({_esc(type(exc).__name__)}).</font>", small))

    # ---------------------------------------------------------------- disclaimer
    story.append(P("Disclaimer", h2))
    story.append(P(_esc(DISCLAIMER), disc))
    extra_disc = _clean(a.get("disclaimer")).strip()
    if extra_disc and extra_disc != DISCLAIMER:
        story.append(P(_esc(extra_disc), body))

    # ---------------------------------------------------------------- page furniture
    header_left = f"Vehicle Damage Assessment \u2014 {aid[:60]}"
    flags = " | ".join(x for x in ("SAMPLE / DEMO" if demo else "",
                                   "SYNTHETIC PRICING" if synthetic else "") if x)

    class _NumberedCanvas(rl_canvas.Canvas):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._saved_pages: list[dict] = []

        def showPage(self):
            self._saved_pages.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._saved_pages)
            for state in self._saved_pages:
                self.__dict__.update(state)
                self._decorate(total)
                super().showPage()
            super().save()

        def _decorate(self, total: int):
            self.saveState()
            self.setFont(fonts.regular, 7.5)
            self.setFillColor(colors.HexColor("#555555"))
            self.drawString(margin, page_h - 11 * mm, header_left)
            if flags:
                self.setFont(fonts.bold, 7.5)
                self.setFillColor(colors.HexColor("#8a1c1c"))
                self.drawRightString(page_w - margin, page_h - 11 * mm, flags)
            self.setStrokeColor(colors.HexColor("#c8c8c8"))
            self.line(margin, page_h - 12.5 * mm, page_w - margin, page_h - 12.5 * mm)
            self.line(margin, 12.5 * mm, page_w - margin, 12.5 * mm)
            self.setFont(fonts.regular, 6.8)
            self.setFillColor(colors.HexColor("#555555"))
            self.drawString(margin, 8.5 * mm, DISCLAIMER)
            self.drawRightString(page_w - margin, 8.5 * mm,
                                 f"Page {self._pageNumber} of {total}")
            self.restoreState()

    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=margin, rightMargin=margin,
                            topMargin=18 * mm, bottomMargin=17 * mm,
                            title=f"Vehicle damage assessment {aid[:80]}",
                            author="AI-assisted vehicle damage assessment",
                            subject="Preliminary AI-assisted assessment")
    doc.build(story, canvasmaker=_NumberedCanvas)
