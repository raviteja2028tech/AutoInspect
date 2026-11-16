"""Pricing corpus validation, persisted index and retrieval (offline, stub embeddings)."""
import csv
import json

import pytest

from src.contracts import VehicleInfo
from src.kb.index import IndexStaleError, build_index, load_index
from src.kb.records import CorpusError, load_corpus
from src.kb.retrieve import Query, make_embedder, open_retriever

I20 = VehicleInfo(make="Hyundai", model="i20", year=2021)


def q(component, op, vehicle=I20, region="IN-DEMO-METRO", currency="INR", grade="oem"):
    return Query(vehicle, component, op, region, currency, grade, ("dent",))


def _rows(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _write(path, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


# ---------------------------------------------------------------- corpus validation
def test_real_corpus_validates_and_is_labelled_synthetic(kb_copy):
    c = load_corpus(kb_copy)
    assert len(c.records) >= 50
    assert all(r.data_quality == "synthetic_demo" for r in c.records)
    assert {s.source_type for s in c.sources.values()} == {"synthetic_demo"}
    covered = {(r.component, r.operation) for r in c.records}
    for need in [("front_bumper", "refinish"), ("left_front_door", "replace"), ("headlight_left", "replace"),
                 ("windshield", "replace"), ("side_mirror_right", "replace"), ("wheel_tire", "replace")]:
        assert need in covered


@pytest.mark.parametrize("field,value,msg", [
    ("parts_cost_low", "-5", "negative"),
    ("parts_cost_low", "999999", "greater than high"),
    ("year_from", "2030", "invalid year"),
    ("currency", "inr", "ISO"),
    ("component", "side_window", None),      # valid vocab name -> accepted (control)
    ("component", "spoiler", "not in src/vocab.py"),
])
def test_invalid_records_rejected(kb_copy, field, value, msg):
    path = kb_copy / "pricing_records_demo.csv"
    rows = _rows(path)
    rows[0][field] = value
    _write(path, rows)
    if msg is None:
        load_corpus(kb_copy)
        return
    with pytest.raises(CorpusError, match=msg):
        load_corpus(kb_copy)


def test_incompatible_currency_rejected(kb_copy):
    path = kb_copy / "pricing_records_demo.csv"
    rows = _rows(path)
    rows[3]["currency"] = "USD"
    _write(path, rows)
    with pytest.raises(CorpusError, match="currency USD"):
        load_corpus(kb_copy, expected_currency="INR")


def test_sourced_file_cannot_claim_synthetic_source(kb_copy):
    rows = _rows(kb_copy / "pricing_records_demo.csv")[:1]
    rows[0]["record_id"] = "SRC-X-1"
    rows[0]["data_quality"] = "sourced_verified"           # but source SRC-DEMO-001 is synthetic
    _write(kb_copy / "pricing_records_sourced.csv", rows)
    with pytest.raises(CorpusError, match="contradicts"):
        load_corpus(kb_copy)


# ---------------------------------------------------------------- index persistence
def test_index_rebuild_required_after_source_edit(kb_copy, tmp_path):
    emb = make_embedder("stub_test")
    c = load_corpus(kb_copy)
    build_index(c, emb, tmp_path / "idx")
    load_index(c, emb, tmp_path / "idx")                      # fresh -> loads
    path = kb_copy / "pricing_records_demo.csv"
    rows = _rows(path)
    rows[0]["parts_cost_high"] = "350"                        # edit a number
    _write(path, rows)
    c2 = load_corpus(kb_copy)
    with pytest.raises(IndexStaleError, match="DEMO-001"):
        load_index(c2, emb, tmp_path / "idx")
    r = open_retriever(kb_dir=kb_copy, index_dir=tmp_path / "idx2", embedder=emb)   # auto rebuild
    assert r.index.meta["corpus_hash"] == c2.content_hash


def test_index_rejects_other_embedding_model(kb_copy, tmp_path):
    c = load_corpus(kb_copy)
    build_index(c, make_embedder("stub_test"), tmp_path / "idx")
    with pytest.raises(IndexStaleError, match="built with"):
        load_index(c, make_embedder("lexical_fallback"), tmp_path / "idx")


def test_index_meta_records_model_and_hashes(retriever):
    m = retriever.index.meta
    assert m["embedding_model"].startswith("hashing-bow") and m["retrieval_method"] == "stub_test"
    assert len(m["record_hashes"]) == m["n_records"] and m["n_synthetic"] == m["n_records"]


# ---------------------------------------------------------------- retrieval
def test_correct_match_with_citation(retriever):
    res = retriever.retrieve(q("front_bumper", "replace"))
    assert res.status == "ok" and res.fallback_level == "L0_exact"
    top = res.evidence[0]
    assert top.record.component == "front_bumper" and top.record.operation == "replace"
    assert top.record.part_grade == "oem" and top.record.year_from <= 2021 <= top.record.year_to
    assert top.source_id == "SRC-DEMO-001" and top.synthetic and "exact match" in top.applicability_reason
    assert top.retrieval_method == "stub_test"
    # every returned record passes the hard filters (no aftermarket at L0, no tier-2, no Swift, no 2015-19)
    for e in res.evidence:
        assert e.record.region == "IN-DEMO-METRO" and e.record.model == "i20" and e.record.year_from == 2020


def test_wrong_model_year_region_excluded(retriever):
    old = VehicleInfo(make="Hyundai", model="i20", year=2017)
    res = retriever.retrieve(q("left_front_door", "replace", vehicle=old))
    assert res.status == "insufficient_pricing_data"                 # no 2015-19 door record; no silent substitute
    res = retriever.retrieve(q("front_bumper", "replace", vehicle=old))
    assert res.status == "ok" and all(e.record.year_to == 2019 for e in res.evidence)
    swift = VehicleInfo(make="Maruti Suzuki", model="Swift", year=2020)
    res = retriever.retrieve(q("left_front_door", "replace", vehicle=swift))
    assert res.status == "insufficient_pricing_data"                 # never borrows i20 prices
    res = retriever.retrieve(q("front_bumper", "replace", region="IN-DEMO-TIER2"))
    assert res.status == "ok" and all(e.record.region == "IN-DEMO-TIER2" for e in res.evidence)
    res = retriever.retrieve(q("front_bumper", "replace", currency="USD"))
    assert res.status == "insufficient_pricing_data"


def test_broader_reference_only_when_allowed_and_labelled(retriever):
    newer = VehicleInfo(make="Hyundai", model="i20", year=2026)
    assert retriever.retrieve(q("hood", "replace", vehicle=newer)).status == "insufficient_pricing_data"
    res = retriever.retrieve(q("hood", "replace", vehicle=newer), allow_broader=True)
    assert res.status == "ok" and res.fallback_level == "L3_broader_reference"
    assert "BROADER REFERENCE" in res.evidence[0].applicability_reason


def test_missing_year_is_labelled(retriever):
    res = retriever.retrieve(q("hood", "repair", vehicle=VehicleInfo(make="Hyundai", model="i20")))
    assert res.fallback_level == "L2_year_unverified"


def test_unknown_and_ambiguous_components_have_no_price(retriever):
    for comp in ("side_window", "side_window_front_left", "other"):
        assert retriever.retrieve(q(comp, "replace")).status == "insufficient_pricing_data"


def test_family_record_applies_to_positioned_tyre(retriever):
    res = retriever.retrieve(q("wheel_tire_rear_left", "replace", grade="aftermarket"))
    assert res.status == "ok" and res.evidence[0].record.position == "any"
    # oem preference falls back to aftermarket tyre with a label
    res = retriever.retrieve(q("wheel_tire_rear_left", "replace", grade="oem"))
    assert res.fallback_level == "L1_grade_relaxed"


def test_lexical_fallback_is_labelled(tmp_path):
    r = open_retriever(index_dir=tmp_path / "i", embedder=make_embedder("lexical_fallback"))
    res = r.retrieve(q("hood", "repair"))
    assert res.evidence[0].retrieval_method == "lexical_fallback"


def test_index_files_written(retriever, tmp_path):
    files = list((tmp_path / "index").rglob("*"))
    meta = [f for f in files if f.name == "index_meta.json"][0]
    assert json.loads(meta.read_text())["format"] == "kb-index-1"
