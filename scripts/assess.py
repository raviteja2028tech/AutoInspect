"""End-to-end assessment from the command line; writes matching JSON + PDF (+ overlays).

Live (Gemini vision, needs a configured key):
    python scripts/assess.py photo1.jpg photo2.jpg photo3.jpg --make Hyundai --model i20 --year 2021 \
        --description "Reversed into a pole" [--confirm-same-vehicle] [--no-cache]

Saved fixture (offline, no key; always labelled SAMPLE):
    python scripts/assess.py --sample samples/sample_minor.json

Output: outputs/<assessment_id>/{assessment.json, assessment.pdf, overlay_<image_id>.jpg}
(outputs/ is git-ignored). The JSON and PDF are rendered from the same validated object and
the script checks that the PDF shows the same totals as the JSON.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import settings  # noqa: E402
from src.analyse import AnalysisError  # noqa: E402
from src.contracts import PricingScope, VehicleInfo  # noqa: E402
from src.intake import IntakeError  # noqa: E402
from src.pipeline import VehicleMismatchError  # noqa: E402
from src.report import pdf_totals_match  # noqa: E402
from src.service import export_assessment, get_retriever, run_live_assessment, run_sample_assessment  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):   # pragma: no cover
    pass


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("images", nargs="*", help="1-5 photos of ONE vehicle (3-5 recommended)")
    ap.add_argument("--sample", help="saved damage-map fixture instead of photos (offline)")
    ap.add_argument("--make")
    ap.add_argument("--model")
    ap.add_argument("--year", type=int)
    ap.add_argument("--variant", default="")
    ap.add_argument("--description", help="optional accident description (untrusted context)")
    ap.add_argument("--region", default=settings.DEFAULT_REGION)
    ap.add_argument("--grade", default="oem", choices=["oem", "aftermarket"])
    ap.add_argument("--confirm-same-vehicle", action="store_true")
    ap.add_argument("--no-cache", action="store_true", help="force fresh Gemini calls")
    ap.add_argument("--out-dir", default=str(settings.OUTPUT_DIR))
    args = ap.parse_args()

    if bool(args.sample) == bool(args.images):
        ap.error("give either photos or --sample (not both)")

    scope = PricingScope(region=args.region, currency=settings.DEFAULT_CURRENCY,
                         part_grade_preference=args.grade, tax_rate=settings.GST_RATE)
    retriever = get_retriever(allow_lexical_fallback=True)
    try:
        if args.sample:
            dm_vehicle = json.loads(Path(args.sample).read_text(encoding="utf-8")).get("vehicle", {})
            vehicle = VehicleInfo(make=args.make or dm_vehicle.get("make", ""),
                                  model=args.model or dm_vehicle.get("model", ""),
                                  year=args.year, variant=args.variant)
            result = run_sample_assessment(Path(args.sample), vehicle, scope=scope, retriever=retriever)
        else:
            if not (args.make and args.model):
                ap.error("--make and --model are required for photos")
            vehicle = VehicleInfo(make=args.make, model=args.model, year=args.year, variant=args.variant)
            result = run_live_assessment(
                args.images, vehicle, accident_description=args.description, scope=scope,
                confirm_same_vehicle=args.confirm_same_vehicle, use_cache=not args.no_cache, retriever=retriever,
                progress=lambda msg, frac: print(f"  [{frac:4.0%}] {msg}"))
    except VehicleMismatchError as exc:
        print(f"STOPPED - vehicle identity check: {exc}")
        return 2
    except (IntakeError, AnalysisError) as exc:
        print(f"ERROR: {exc}")
        return 1

    a = result.assessment
    json_text, pdf_bytes = export_assessment(result)
    out = Path(args.out_dir) / a.assessment_id
    out.mkdir(parents=True, exist_ok=True)
    (out / "assessment.json").write_text(json_text, encoding="utf-8")
    (out / "assessment.pdf").write_bytes(pdf_bytes)
    for iid, data in result.overlays.items():
        (out / f"overlay_{iid}.jpg").write_bytes(data)

    t = a.totals
    print(f"\nAssessment {a.assessment_id}  mode={a.mode}  retrieval={retriever.method}")
    if a.pricing_label:
        print(f"*** {a.pricing_label} ***")
    for p in a.component_plans:
        cost = f"{p.cost.low:,.0f} - {p.cost.high:,.0f}" if p.cost else p.pricing_status
        print(f"  {p.component_instance:26s} {p.action:8s} {p.rule_id:12s} {cost}")
    print(f"Totals: {t.status} | observed {t.observed_low} - {t.observed_high} {t.currency} ({t.tax_basis})")
    print(f"Uncertainty: {a.uncertainty.level}")
    for w in a.warnings[:12]:
        print(f"  warning: {w}")
    parity = pdf_totals_match(pdf_bytes, t)
    print(f"JSON/PDF totals: {parity}")
    print(f"Wrote {out}")
    return 0 if not parity.startswith("MISMATCH") else 3


if __name__ == "__main__":
    sys.exit(main())
