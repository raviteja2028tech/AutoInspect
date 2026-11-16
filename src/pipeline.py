"""The single entry point other members call:

    from src.pipeline import analyse_case
    damage_map = analyse_case(["front.jpg", "left.jpg"], {"make": "Hyundai", "model": "i20"})

Command line (run from the project root):

    python -m src.pipeline data/front.jpg data/left.jpg --make Hyundai --model i20 --out samples/my_case.json

Output contract: the agreed v1 keys are unchanged (vehicle, images_analysed, damages[] with
component/damage_type/severity/location/confidence, views_seen, warnings, images_failed, meta).
damage_map v2 ADDS: schema_version, observations (image-linked, with boxes), component_groups,
image_manifest, images_rejected, images_duplicate, images_not_vehicle, conflicts,
vehicle_consistency, narrative_check, accident_description.
Migration: damages[].component may now be a positioned name (e.g. side_mirror_left) and
damage_type may be "missing_part"; use src.components.adapt_damage_map() for either version.
"""
from __future__ import annotations

import argparse
import json
from typing import Callable, Optional

from . import analyse as _analyse
from .analyse import (PROMPT_VERSION, PROVIDER, SCHEMA_VERSION, AnalysisError, FatalAnalysisError,
                      analyse_image, result_provenance)
from .fuse import fuse_observations, legacy_damage, narrative_check, vehicle_consistency
from .intake import IntakeError, intake_images

MIN_RECOMMENDED_VIEWS = 3
DAMAGE_MAP_VERSION = "damage-map-2.0"


class VehicleMismatchError(AnalysisError):
    """Images appear to show different vehicles; caller must confirm before combining."""

    def __init__(self, message: str, consistency: dict, partial: dict):
        super().__init__(message)
        self.consistency = consistency
        self.partial = partial


def analyse_case(image_paths, vehicle_info: dict | None = None,
                 view_hints: dict | None = None, use_cache: bool = True, *,
                 accident_description: str | None = None, confirm_same_vehicle: bool = False,
                 progress: Optional[Callable[[str, float], None]] = None,
                 return_images: bool = False) -> dict:
    """Run the full vision pipeline and return the damage-map dictionary (v1 keys + v2 extras).

    view_hints (optional): {"front.jpg": "front", "left.jpg": "left"}
    Raises IntakeError, FatalAnalysisError (key/config), AnalysisError (nothing analysed) or
    VehicleMismatchError (clear identity conflict and confirm_same_vehicle is False).
    return_images=True also returns the processed JPEG bytes under "_processed_images" (for
    overlays); strip them with public_damage_map() before saving.
    """
    def step(msg, frac):
        if progress:
            progress(msg, frac)

    vehicle = {"make": "", "model": "", "reg_no": ""}
    vehicle.update(vehicle_info or {})

    step("Checking images", 0.02)
    intake = intake_images(image_paths)
    images = intake.images
    warnings = list(intake.warnings)
    failed, not_vehicle, analysed, cache_info = [], [], [], {}

    for k, img in enumerate(images):
        warnings.extend(f"{img.name}: {w}" for w in img.warnings)
        hint = (view_hints or {}).get(img.name)
        step(f"Analysing {img.name} ({k + 1}/{len(images)})", 0.05 + 0.85 * k / max(1, len(images)))
        try:
            res = analyse_image(img.jpeg_bytes, view_hint=hint, use_cache=use_cache)
        except FatalAnalysisError:
            raise
        except AnalysisError as exc:
            failed.append({"file": img.name, "image_id": img.image_id, "error": str(exc)})
            continue
        cache_info[img.image_id] = result_provenance(res).get("source", "unknown")
        if not getattr(res, "is_vehicle", True):
            not_vehicle.append({"file": img.name, "image_id": img.image_id,
                                "error": f"no vehicle visible ({res.notes})"})
            continue
        analysed.append((img, res))

    if not analysed:
        reasons = [f["error"] for f in failed + not_vehicle + intake.rejected]
        raise AnalysisError("No image could be analysed: " + "; ".join(reasons))

    items = [(img.image_id, res) for img, res in analysed]
    consistency = vehicle_consistency(items)
    observations, conflicts = fuse_observations(items)

    if len(analysed) < MIN_RECOMMENDED_VIEWS:
        warnings.append(f"Insufficient coverage: only {len(analysed)} usable unique photo(s); "
                        f"{MIN_RECOMMENDED_VIEWS}-5 from different sides are recommended.")
    if not observations:
        warnings.append("No visible damage detected.")
    for d in intake.duplicates:
        warnings.append(f"{d['file']} is a duplicate of {d['duplicate_of']}; counted once.")
    for f in not_vehicle:
        warnings.append(f"{f['file']}: {f['error']}")
    for note in dict.fromkeys(r.notes for _, r in analysed if r.notes):
        warnings.append(f"model note: {note}")
    for c in conflicts:
        if c["type"] in ("severity_conflict", "side_conflict"):
            warnings.append(f"{c['type'].replace('_', ' ')} on {c['component']}: {c['detail']}")
    if consistency["status"] == "conflict":
        warnings.append("Images may show different vehicles: " + "; ".join(consistency["evidence"]))
    elif consistency["status"] == "uncertain":
        warnings.append("Could not confirm that all images show the same vehicle; please confirm.")
    narrative = narrative_check(accident_description, observations)
    for c in narrative.get("contradictions", []):
        warnings.append(f"narrative: {c}")

    by_id = {img.image_id: img for img, _ in analysed}
    groups = {}
    for o in observations:
        g = groups.setdefault(o.component, {"damage_ids": [], "damage_types": [], "image_ids": []})
        g["damage_ids"].append(o.damage_id)
        g["damage_types"] = sorted(set(g["damage_types"]) | {o.damage_type})
        g["image_ids"] = sorted(set(g["image_ids"]) | set(o.image_ids))

    result = {
        # --- agreed contract (A -> B and C) ---
        "vehicle": vehicle,
        "images_analysed": len(analysed),
        "damages": [legacy_damage(o) for o in observations],
        # --- extra info (safe for others to ignore) ---
        "views_seen": sorted({r.view for _, r in analysed}),
        "warnings": warnings,
        "images_failed": intake.rejected + failed,
        "meta": {"provider": PROVIDER, "model": _analyse.MODEL, "api_version": _analyse.API_VERSION,
                 "prompt_version": PROMPT_VERSION, "schema_version": SCHEMA_VERSION, "cache": cache_info},
        # --- v2 additions ---
        "schema_version": DAMAGE_MAP_VERSION,
        "observations": [o.model_dump(mode="json") for o in observations],
        "component_groups": groups,
        "image_manifest": [{**img.manifest(), "view": res.view, "notes": res.notes,
                            "analysis_source": cache_info.get(img.image_id)} for img, res in analysed],
        "images_rejected": intake.rejected,
        "images_duplicate": intake.duplicates,
        "images_analysis_failed": failed,
        "images_not_vehicle": not_vehicle,
        "conflicts": conflicts,
        "vehicle_consistency": consistency,
        "narrative_check": narrative,
        "accident_description": accident_description or None,
    }
    result["_processed_images"] = {iid: by_id[iid].jpeg_bytes for iid in by_id}   # stripped before saving
    step("Vision analysis complete", 0.92)

    if consistency["status"] == "conflict" and not confirm_same_vehicle:
        raise VehicleMismatchError("The photos appear to show different vehicles: "
                                   + "; ".join(consistency["evidence"])
                                   + ". Confirm they are the same vehicle to continue.",
                                   consistency, public_damage_map(result))
    return result if return_images else public_damage_map(result)


def public_damage_map(result: dict) -> dict:
    """Damage map without in-memory image bytes (safe to serialise)."""
    return {k: v for k, v in result.items() if not k.startswith("_")}


def main():
    ap = argparse.ArgumentParser(description="Run vehicle damage analysis on 1-5 photos.")
    ap.add_argument("images", nargs="+", help="paths to the photos")
    ap.add_argument("--make", default="")
    ap.add_argument("--model", default="")
    ap.add_argument("--reg", default="")
    ap.add_argument("--description", default=None, help="optional accident description (untrusted context)")
    ap.add_argument("--confirm-same-vehicle", action="store_true")
    ap.add_argument("--out", help="save the JSON here instead of only printing it")
    ap.add_argument("--no-cache", action="store_true")
    args = ap.parse_args()

    try:
        result = analyse_case(args.images,
                              {"make": args.make, "model": args.model, "reg_no": args.reg},
                              use_cache=not args.no_cache, accident_description=args.description,
                              confirm_same_vehicle=args.confirm_same_vehicle)
    except (IntakeError, AnalysisError) as exc:
        raise SystemExit(f"ERROR: {exc}")

    text = json.dumps(public_damage_map(result), indent=2, ensure_ascii=False)
    print(text)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"\nSaved to {args.out}")


if __name__ == "__main__":
    main()
