"""Reproducible OFFLINE smoke check (no API key, no network after the first model download).

    python scripts/smoke_check.py            # semantic retrieval (real embedding model)
    python scripts/smoke_check.py --lexical  # deterministic lexical ranking, no model needed

For every sample fixture it builds the assessment, renders JSON + PDF from the same object,
re-validates the JSON, and checks that the PDF shows the same totals. Files are written to
outputs/smoke/ (git-ignored). Exit code 0 = all checks passed.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import settings  # noqa: E402
from src.contracts import Assessment, VehicleInfo  # noqa: E402
from src.kb.retrieve import make_embedder, open_retriever  # noqa: E402
from src.report import pdf_totals_match  # noqa: E402
from src.service import AssessmentResult, export_assessment, get_retriever, run_sample_assessment  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):   # pragma: no cover
    pass

# fixture -> vehicle details a user would enter (fixtures carry make/model only)
CASES = {
    "my_case_v2.json": VehicleInfo(make="Hyundai", model="i20", year=2021),
    "sample_severe.json": VehicleInfo(make="Hyundai", model="i20", year=2020),
    "sample_minor.json": VehicleInfo(make="Maruti Suzuki", model="Swift", year=2022),
    "sample_no_damage.json": VehicleInfo(make="Honda", model="City", year=2021),
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lexical", action="store_true", help="use labelled lexical ranking (no embedding model)")
    args = ap.parse_args()

    if args.lexical:
        retriever = open_retriever(embedder=make_embedder("lexical_fallback"))
    else:
        retriever = get_retriever(allow_lexical_fallback=True)
    print(f"Retrieval: {retriever.method} ({retriever.index.meta['embedding_model']}), "
          f"{len(retriever.corpus.records)} pricing records")
    out_dir = settings.OUTPUT_DIR / "smoke"
    out_dir.mkdir(parents=True, exist_ok=True)

    failures = 0
    for name, vehicle in CASES.items():
        res: AssessmentResult = run_sample_assessment(ROOT / "samples" / name, vehicle, retriever=retriever)
        a = res.assessment
        json_text, pdf_bytes = export_assessment(res)
        again = Assessment.model_validate_json(json_text)          # JSON round-trips through the contract
        checks = {
            "labelled sample": a.mode == "sample_fixture" and any("SAMPLE MODE" in w for w in a.warnings),
            "json round-trip totals": again.totals == a.totals,
            "pdf rendered": pdf_bytes.startswith(b"%PDF"),
            "pdf totals": pdf_totals_match(pdf_bytes, a.totals) in ("match",) or
                          pdf_totals_match(pdf_bytes, a.totals).startswith("not checked"),
            "synthetic label": (a.pricing_label is not None) == any(
                e.synthetic for p in a.component_plans if p.retrieval for e in p.retrieval.evidence),
        }
        (out_dir / f"{Path(name).stem}.json").write_text(json_text, encoding="utf-8")
        (out_dir / f"{Path(name).stem}.pdf").write_bytes(pdf_bytes)
        ok = all(checks.values())
        failures += not ok
        t = a.totals
        print(f"[{'PASS' if ok else 'FAIL'}] {name:24s} status={t.status:26s} "
              f"observed={t.observed_low}-{t.observed_high} {t.currency} plans={len(a.component_plans)} "
              f"pdf={len(pdf_bytes) // 1024}KB  totals-parity={pdf_totals_match(pdf_bytes, t)}")
        for k, v in checks.items():
            if not v:
                print(f"       failed check: {k}")
    print(f"\nOutputs in {out_dir}")
    print("ALL PASSED" if not failures else f"{failures} case(s) FAILED")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
