"""PDF adapter for Assessment objects (public, stable interface: ``render_pdf``).

There is exactly ONE PDF implementation: ``src.reporting.pdf_report.generate_pdf_report``.
This module only adapts an ``Assessment`` (or its dict dump) plus optional overlay images to
that function and returns the bytes. Kept for compatibility with existing callers.
"""
from __future__ import annotations

import io
import re
import tempfile
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

from .contracts import Assessment
from .reporting.pdf_report import DISCLAIMER, generate_pdf_report

__all__ = ["render_pdf", "pdf_totals_match", "DISCLAIMER"]


def render_pdf(a: Assessment | Mapping[str, Any], overlays: dict[str, bytes] | None = None) -> bytes:
    """Render an Assessment (or its dictionary dump) into PDF bytes.

    overlays: optional {image_id: annotated JPEG bytes}, embedded as image evidence.
    """
    assessment_dict = a.model_dump() if hasattr(a, "model_dump") else dict(a)
    with tempfile.TemporaryDirectory(prefix="vda_pdf_") as tmp:
        tmp_dir = Path(tmp)
        image_paths = []
        for idx, (img_id, img_bytes) in enumerate((overlays or {}).items(), 1):
            img_path = tmp_dir / f"overlay_{idx}_{re.sub(r'[^A-Za-z0-9_-]', '_', str(img_id))}.jpg"
            img_path.write_bytes(img_bytes)
            image_paths.append((str(img_path), f"View {img_id} (approximate AI-marked regions)"))
        out_pdf = tmp_dir / "assessment_report.pdf"
        generate_pdf_report(assessment_dict, out_pdf, image_paths=image_paths or None)
        return out_pdf.read_bytes()


def pdf_totals_match(pdf_bytes: bytes, totals) -> str:
    """Check the PDF shows the same observed totals as the assessment object.

    Returns 'match', 'MISMATCH: ...' or 'not checked (...)'. The PDF prints amounts as
    12,345.00 (the UI uses Indian grouping, e.g. 1,23,450 - same value, different format).
    """
    try:
        import pypdf
    except ImportError:
        return "not checked (pypdf not installed; pip install -r requirements-dev.txt)"
    get = totals.get if isinstance(totals, Mapping) else (lambda k: getattr(totals, k, None))
    text = "".join(page.extract_text() or "" for page in pypdf.PdfReader(io.BytesIO(pdf_bytes)).pages)
    text = " ".join(text.split())
    expected = [f"{Decimal(str(v)):,.2f}" for v in (get("observed_low"), get("observed_high")) if v is not None]
    missing = [e for e in expected if e not in text]
    return "match" if not missing else f"MISMATCH: PDF text lacks {missing}"
