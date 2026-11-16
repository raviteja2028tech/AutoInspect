"""Load and validate the pricing corpus (sources.json + pricing_records_*.csv)."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from pydantic import ValidationError

from ..contracts import PricingRecord, PricingSource
from ..vocab import COMPONENT_FAMILY

DOC_TEMPLATE_VERSION = "doc-v1"
_HUMAN_OP = {"refinish": "refinish / repaint", "repair": "repair (dent or crack) and refinish",
             "replace": "replace with new part"}


class CorpusError(ValueError):
    """The pricing corpus is invalid."""


class Corpus:
    def __init__(self, sources: dict[str, PricingSource], records: list[PricingRecord]):
        self.sources = sources
        self.records = records
        self.by_id = {r.record_id: r for r in records}

    @property
    def content_hash(self) -> str:
        """Hash of every validated value + the document template; edits force a rebuild."""
        payload = {
            "template": DOC_TEMPLATE_VERSION,
            "sources": [s.model_dump(mode="json") for s in sorted(self.sources.values(), key=lambda s: s.source_id)],
            "records": [r.model_dump(mode="json") for r in self.records],
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    def record_hash(self, record_id: str) -> str:
        return hashlib.sha256(json.dumps(self.by_id[record_id].model_dump(mode="json"),
                                         sort_keys=True).encode()).hexdigest()[:16]


def _bool(v: str) -> bool:
    v = str(v).strip().lower()
    if v in ("true", "yes", "1"):
        return True
    if v in ("false", "no", "0"):
        return False
    raise ValueError(f"tax_included must be true/false, got '{v}'")


def load_corpus(kb_dir: Path, expected_currency: str | None = None) -> Corpus:
    kb_dir = Path(kb_dir)
    src_file = kb_dir / "sources.json"
    if not src_file.exists():
        raise CorpusError(f"Missing {src_file}")
    sources = {}
    for raw in json.loads(src_file.read_text(encoding="utf-8"))["sources"]:
        s = PricingSource.model_validate(raw)
        if s.source_id in sources:
            raise CorpusError(f"duplicate source_id {s.source_id}")
        sources[s.source_id] = s

    records, errors = [], []
    csv_files = sorted(kb_dir.glob("pricing_records_*.csv"))
    if not csv_files:
        raise CorpusError(f"No pricing_records_*.csv in {kb_dir}")
    for f in csv_files:
        with f.open(encoding="utf-8", newline="") as fh:
            for line_no, row in enumerate(csv.DictReader(fh), start=2):
                if not any((v or "").strip() for v in row.values()):
                    continue
                try:
                    row = {k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
                    row["tax_included"] = _bool(row.get("tax_included", ""))
                    rec = PricingRecord.model_validate(row)
                except (ValidationError, ValueError) as exc:
                    errors.append(f"{f.name}:{line_no}: {exc}")
                    continue
                src = sources.get(rec.source_id)
                if src is None:
                    errors.append(f"{f.name}:{line_no}: unknown source_id {rec.source_id}")
                    continue
                if (src.source_type == "synthetic_demo") != (rec.data_quality == "synthetic_demo"):
                    errors.append(f"{f.name}:{line_no}: data_quality '{rec.data_quality}' contradicts "
                                  f"source type '{src.source_type}'")
                    continue
                if "demo" in f.name and rec.data_quality != "synthetic_demo":
                    errors.append(f"{f.name}:{line_no}: sourced records belong in pricing_records_sourced.csv")
                    continue
                if expected_currency and rec.currency != expected_currency:
                    errors.append(f"{f.name}:{line_no}: currency {rec.currency} differs from corpus "
                                  f"currency {expected_currency}")
                    continue
                records.append(rec)

    ids = [r.record_id for r in records]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        errors.append(f"duplicate record_id(s): {dupes}")
    if errors:
        raise CorpusError("Invalid pricing corpus:\n  " + "\n  ".join(errors))
    records.sort(key=lambda r: r.record_id)
    return Corpus(sources, records)


def human_component(name: str) -> str:
    return name.replace("_", " ")


def record_document(rec: PricingRecord, source: PricingSource) -> str:
    """Natural-language document used ONLY for semantic ranking (never for arithmetic)."""
    family = COMPONENT_FAMILY.get(rec.component, rec.component)
    pos = "any position" if rec.position == "any" else rec.position
    grade = {"oem": "OEM genuine part", "aftermarket": "aftermarket part", "n/a": "no part"}[rec.part_grade]
    return (f"{rec.make} {rec.model} {rec.year_from}-{rec.year_to} {rec.variant} variant. "
            f"Component: {human_component(rec.component)} ({human_component(family)}, {pos}). "
            f"Operation: {_HUMAN_OP[rec.operation]}. {grade}. Region {rec.region}. "
            f"{rec.assumptions} Source type: {source.source_type.replace('_', ' ')}.")
