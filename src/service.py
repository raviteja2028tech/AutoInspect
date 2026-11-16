"""Assessment service: intake -> vision -> reconciliation -> rules -> retrieval -> costing.

    from src.service import run_live_assessment, run_sample_assessment
    result = run_live_assessment(["a.jpg", "b.jpg", "c.jpg"], {"make": "Hyundai", "model": "i20", "year": 2021},
                                 accident_description="Hit a pole while reversing")
    result.assessment      # validated Assessment (JSON via .model_dump_json())
    result.overlays        # {image_id: annotated JPEG bytes}

    json_text, pdf_bytes = export_assessment(result)   # both from the SAME validated object

Live mode never falls back to samples: if analysis fails, the error is raised.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from . import settings
from .contracts import Observation, PricingScope, VehicleInfo
from .estimate import build_assessment
from .kb.retrieve import Retriever, open_retriever
from .overlay import draw_overlay
from .pipeline import analyse_case, public_damage_map
from .report import render_pdf


@dataclass
class AssessmentResult:
    assessment: object
    overlays: dict[str, bytes] = field(default_factory=dict)
    unboxed: dict[str, list[str]] = field(default_factory=dict)
    originals: dict[str, bytes] = field(default_factory=dict)


_retriever: Retriever | None = None


def get_retriever(allow_lexical_fallback: bool = True) -> Retriever:
    """Process-wide retriever (index loaded/built once)."""
    global _retriever
    if _retriever is None:
        _retriever = open_retriever(allow_lexical_fallback=allow_lexical_fallback)
    return _retriever


def default_scope(region: str | None = None, grade: str = "oem") -> PricingScope:
    return PricingScope(region=region or settings.DEFAULT_REGION, currency=settings.DEFAULT_CURRENCY,
                        part_grade_preference=grade, tax_rate=settings.GST_RATE)


def run_live_assessment(image_paths, vehicle: dict | VehicleInfo, *, accident_description: str | None = None,
                        scope: PricingScope | None = None, clarifications: dict | None = None,
                        confirm_same_vehicle: bool = False, use_cache: bool = True,
                        allow_broader: bool = False, retriever: Retriever | None = None,
                        progress: Optional[Callable[[str, float], None]] = None) -> AssessmentResult:
    vehicle = vehicle if isinstance(vehicle, VehicleInfo) else VehicleInfo(**vehicle)
    raw = analyse_case(image_paths, {"make": vehicle.make, "model": vehicle.model, "reg_no": vehicle.reg_no},
                       use_cache=use_cache, accident_description=accident_description,
                       confirm_same_vehicle=confirm_same_vehicle, progress=progress, return_images=True)
    images = raw.get("_processed_images", {})
    dm = public_damage_map(raw)
    if progress:
        progress("Retrieving prices and building estimate", 0.95)
    extra = []
    if confirm_same_vehicle and dm["vehicle_consistency"]["status"] in ("conflict", "uncertain"):
        extra.append("User confirmed the photos show the same vehicle despite the identity check result "
                     f"'{dm['vehicle_consistency']['status']}'.")
    sources = set(dm["meta"].get("cache", {}).values())
    a = build_assessment(dm, vehicle, scope or default_scope(), retriever or get_retriever(), clarifications,
                         mode="live", allow_broader=allow_broader, accident_description=accident_description,
                         extra_warnings=extra)
    a.provenance["vision_cache"] = ("all results from local cache of earlier live calls" if sources == {"cache"}
                                    else "fresh live inference" if sources == {"fresh"} else
                                    f"mixed: {dm['meta'].get('cache')}")
    obs = [Observation.model_validate(o) for o in dm["observations"]]
    result = AssessmentResult(a, originals=images)
    for iid, data in images.items():
        result.overlays[iid], result.unboxed[iid] = draw_overlay(data, iid, obs)
    if progress:
        progress("Done", 1.0)
    return result


def run_sample_assessment(sample_path: Path, vehicle: dict | VehicleInfo | None = None,
                          scope: PricingScope | None = None, clarifications: dict | None = None,
                          retriever: Retriever | None = None) -> AssessmentResult:
    """Saved-fixture demo: no vision call. Always labelled sample_fixture."""
    dm = json.loads(Path(sample_path).read_text(encoding="utf-8"))
    if isinstance(vehicle, dict):
        vehicle = VehicleInfo(**vehicle)
    a = build_assessment(dm, vehicle, scope or default_scope(), retriever or get_retriever(), clarifications,
                         mode="sample_fixture",
                         extra_warnings=[f"SAMPLE MODE: saved fixture '{Path(sample_path).name}', no live image "
                                         "analysis was performed. Not a real case."])
    return AssessmentResult(a)


def export_assessment(result: AssessmentResult) -> tuple[str, bytes]:
    """(JSON text, PDF bytes) rendered from one validated Assessment, so totals always match."""
    a = result.assessment
    return a.model_dump_json(indent=2), render_pdf(a, result.overlays or None)
