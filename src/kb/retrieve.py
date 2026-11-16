"""Retrieval: structured applicability filters, explicit fallback levels, then semantic ranking.

Hard filters (never relaxed): currency, region, make, model, component instance, operation.
Fallback levels, tried in order, each labelled in the output:

  L0_exact             year inside record range, variant matches, preferred part grade
  L1_grade_relaxed     as L0 but any part grade (preferred grade had no record)
  L2_year_unverified   the request has no vehicle year, so the year range cannot be checked
  L3_broader_reference same make+model but a DIFFERENT model-year range. Only when the caller
                       passes allow_broader=True; always labelled as a broader reference.

A different make or model is never substituted. If nothing passes, status is
insufficient_pricing_data.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .. import settings
from ..contracts import PricingRecord, RetrievalResult, RetrievedEvidence, VehicleInfo
from .embedding import EmbeddingUnavailable, HashingEmbedder, SentenceTransformerEmbedder
from .index import VectorIndex, load_or_build
from .records import Corpus, human_component, load_corpus
from .vehicles import normalize_make

LEVEL_LABELS = {
    "L0_exact": "exact match: vehicle make/model, model-year range, variant, region, currency, component and operation",
    "L1_grade_relaxed": "vehicle/year match; preferred part grade unavailable, other grade used",
    "L2_year_unverified": "make/model match but vehicle year not supplied - year applicability NOT verified",
    "L3_broader_reference": "BROADER REFERENCE: same make/model, different model-year range - may not be interchangeable",
}


def _eq(a: str, b: str) -> bool:
    return a.strip().lower() == b.strip().lower()


@dataclass
class Query:
    vehicle: VehicleInfo
    component: str
    operation: str
    region: str
    currency: str
    part_grade: str = "oem"
    damage_types: tuple[str, ...] = ()

    def text(self) -> str:
        yr = self.vehicle.year or "unknown year"
        dmg = ", ".join(d.replace("_", " ") for d in self.damage_types) or "damage"
        return (f"{self.vehicle.make} {self.vehicle.model} {yr} {self.vehicle.variant or ''} "
                f"{human_component(self.component)} {dmg}: {self.operation} ({self.part_grade} part) "
                f"in region {self.region}").replace("  ", " ")


class Retriever:
    def __init__(self, corpus: Corpus, index: VectorIndex, embedder):
        self.corpus, self.index, self.embedder = corpus, index, embedder

    @property
    def method(self) -> str:
        return self.embedder.method

    def _hard(self, r: PricingRecord, q: Query) -> bool:
        return (r.currency == q.currency and r.region == q.region
                and _eq(normalize_make(r.make), normalize_make(q.vehicle.make))
                and _eq(r.model, q.vehicle.model) and r.applies_to_component(q.component)
                and r.operation == q.operation)

    @staticmethod
    def _variant_ok(r: PricingRecord, q: Query) -> bool:
        return _eq(r.variant, "all") or not q.vehicle.variant or _eq(r.variant, q.vehicle.variant)

    @staticmethod
    def _grade_ok(r: PricingRecord, q: Query) -> bool:
        return r.part_grade in ("n/a", q.part_grade)

    @staticmethod
    def _year_in(r: PricingRecord, q: Query) -> bool:
        return q.vehicle.year is not None and r.year_from <= q.vehicle.year <= r.year_to

    def _levels(self, q: Query, allow_broader: bool):
        if q.vehicle.year is not None:
            yield "L0_exact", lambda r: self._year_in(r, q) and self._variant_ok(r, q) and self._grade_ok(r, q)
            yield "L1_grade_relaxed", lambda r: self._year_in(r, q) and self._variant_ok(r, q)
        else:
            yield "L2_year_unverified", lambda r: self._variant_ok(r, q) and self._grade_ok(r, q)
            yield "L2_year_unverified", lambda r: self._variant_ok(r, q)
        if allow_broader:
            yield "L3_broader_reference", lambda r: True

    def retrieve(self, q: Query, top_k: int | None = None, allow_broader: bool = False) -> RetrievalResult:
        top_k = top_k or settings.RETRIEVAL_TOP_K
        filters = {"currency": q.currency, "region": q.region, "make": q.vehicle.make,
                   "model": q.vehicle.model, "year": q.vehicle.year, "variant": q.vehicle.variant or "any",
                   "component": q.component, "operation": q.operation, "part_grade_preference": q.part_grade,
                   "allow_broader_reference": allow_broader}
        text = q.text()
        hard = [r for r in self.corpus.records if self._hard(r, q)]
        for level, pred in self._levels(q, allow_broader):
            candidates = [r for r in hard if pred(r)]
            if not candidates:
                continue
            qvec = self.embedder.embed([text])[0]
            scores = self.index.scores(qvec, [r.record_id for r in candidates])
            ranked = sorted(candidates, key=lambda r: (-scores[r.record_id], r.record_id))[:top_k]
            evidence = []
            for rank, r in enumerate(ranked, 1):
                src = self.corpus.sources[r.source_id]
                reason = (f"{LEVEL_LABELS[level]}. Record covers {r.make} {r.model} {r.year_from}-{r.year_to} "
                          f"({r.variant}), {r.component}"
                          f"{' (any position)' if r.position == 'any' else ''}, {r.operation}, "
                          f"{r.part_grade} grade, {r.region}, {r.currency}, "
                          f"{'tax included' if r.tax_included else 'excl. tax'}.")
                evidence.append(RetrievedEvidence(
                    record_id=r.record_id, source_id=r.source_id, source_title=src.title,
                    source_type=src.source_type, source_entered_date=src.entered_date,
                    source_price_date=src.price_date, synthetic=r.data_quality == "synthetic_demo",
                    score=round(scores[r.record_id], 4), rank=rank, fallback_level=level,
                    applicability_reason=reason, retrieval_method=self.method, record=r))
            return RetrievalResult(status="ok", query=text, fallback_level=level, evidence=evidence,
                                   filters_applied=filters)
        why = ("no record for this make/model/component/operation in this region and currency"
               if not hard else "records exist for this make/model but none apply to this model year/variant"
               + ("" if allow_broader else " (broader references not allowed)"))
        return RetrievalResult(status="insufficient_pricing_data", query=text, filters_applied=filters,
                               message=why)


def make_embedder(kind: str = "semantic", model_name: str | None = None):
    if kind == "semantic":
        return SentenceTransformerEmbedder(model_name or settings.EMBEDDING_MODEL)
    if kind in ("stub_test", "lexical_fallback"):
        return HashingEmbedder(method=kind)
    raise ValueError(f"unknown embedder kind {kind}")


def open_retriever(kb_dir: Path | None = None, index_dir: Path | None = None, embedder=None,
                   allow_lexical_fallback: bool = False, rebuild_if_stale: bool = True) -> Retriever:
    """Load corpus + index (rebuilding if records changed). Semantic by default."""
    kb_dir = Path(kb_dir or settings.KNOWLEDGE_DIR)
    corpus = load_corpus(kb_dir, expected_currency=None)
    embedder = embedder or make_embedder("semantic")
    base_index_dir = Path(index_dir or settings.INDEX_DIR)
    try:
        sub = base_index_dir / embedder.identifier.replace(":", "_").replace("/", "_")
        index = load_or_build(corpus, embedder, sub, rebuild_if_stale=rebuild_if_stale)
    except EmbeddingUnavailable:
        if not allow_lexical_fallback:
            raise
        embedder = make_embedder("lexical_fallback")
        sub = base_index_dir / embedder.identifier.replace(":", "_").replace("/", "_")
        index = load_or_build(corpus, embedder, sub, rebuild_if_stale=rebuild_if_stale)
    return Retriever(corpus, index, embedder)
