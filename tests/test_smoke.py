"""Smoke tests against REAL dependencies. Not part of the default offline run.

    python -m pytest -m smoke     # real sentence-transformers model (downloads once, then cached)
    RUN_LIVE=1 python -m pytest -m live   # real Gemini call; key from .env or environment

A skipped live test is a documented blocker, not a pass.
"""
import json
import os
from pathlib import Path

import pytest

from src.contracts import VehicleInfo
from src.kb.embedding import EmbeddingUnavailable
from src.kb.retrieve import Query, make_embedder, open_retriever

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.smoke
def test_semantic_embedding_retrieval(tmp_path):
    emb = make_embedder("semantic")
    try:
        r = open_retriever(index_dir=tmp_path / "idx", embedder=emb)
    except EmbeddingUnavailable as exc:
        pytest.skip(f"BLOCKED: embedding model unavailable: {exc}")
    assert r.method == "semantic" and r.index.meta["embedding_model"].startswith("sentence-transformers:")
    v = VehicleInfo(make="Hyundai", model="i20", year=2022)
    res = r.retrieve(Query(v, "front_bumper", "replace", "IN-DEMO-METRO", "INR", "aftermarket", ("crack",)))
    assert res.status == "ok" and res.evidence[0].retrieval_method == "semantic"
    assert res.evidence[0].record.component == "front_bumper"
    # semantic ranking puts the aftermarket record first when aftermarket is preferred
    assert res.evidence[0].record.part_grade == "aftermarket"
    # stored index reloads without rebuild
    r2 = open_retriever(index_dir=tmp_path / "idx", embedder=emb, rebuild_if_stale=False)
    assert r2.index.meta["corpus_hash"] == r.index.meta["corpus_hash"]


@pytest.mark.live
def test_live_gemini_single_image():
    if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
        pytest.skip("BLOCKED: GEMINI_API_KEY not set - live test not run")
    if os.environ.get("RUN_LIVE") != "1":
        pytest.skip("set RUN_LIVE=1 to spend a live API call")
    from src.analyse import MODEL, analyse_image, result_provenance
    from src.intake import load_image
    photo = Path(os.environ.get("LIVE_TEST_IMAGE", ROOT / "data" / "front.jpg"))
    if not photo.is_file():
        pytest.skip(f"BLOCKED: no test photo at {photo} (set LIVE_TEST_IMAGE)")
    img = load_image(photo)
    res = analyse_image(img.jpeg_bytes, use_cache=False)
    prov = result_provenance(res)
    assert prov["source"] == "fresh" and prov["model"] == MODEL
    print(json.dumps(res.model_dump(), indent=1)[:2000])
