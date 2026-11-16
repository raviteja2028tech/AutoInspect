"""Persisted NumPy vector index with metadata and staleness checks."""
from __future__ import annotations

import io
import json
import os
import tempfile
from pathlib import Path

import numpy as np

from ..contracts import utcnow
from .records import DOC_TEMPLATE_VERSION, Corpus, record_document

INDEX_FORMAT = "kb-index-1"


class IndexStaleError(RuntimeError):
    """Index missing, stale or built with an incompatible embedding model."""


class VectorIndex:
    def __init__(self, vectors: np.ndarray, record_ids: list[str], meta: dict):
        self.vectors = vectors
        self.record_ids = record_ids
        self.meta = meta
        self.row = {rid: i for i, rid in enumerate(record_ids)}

    def scores(self, query_vec: np.ndarray, record_ids: list[str]) -> dict[str, float]:
        rows = [self.row[r] for r in record_ids]
        sims = self.vectors[rows] @ query_vec
        return {rid: float(s) for rid, s in zip(record_ids, sims)}


def _atomic_write(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def build_index(corpus: Corpus, embedder, index_dir: Path) -> VectorIndex:
    docs = [record_document(r, corpus.sources[r.source_id]) for r in corpus.records]
    vecs = embedder.embed(docs).astype(np.float32)
    meta = {
        "format": INDEX_FORMAT,
        "embedding_model": embedder.identifier,
        "retrieval_method": embedder.method,
        "dim": int(vecs.shape[1]),
        "doc_template": DOC_TEMPLATE_VERSION,
        "corpus_hash": corpus.content_hash,
        "record_ids": [r.record_id for r in corpus.records],
        "record_hashes": {r.record_id: corpus.record_hash(r.record_id) for r in corpus.records},
        "n_records": len(corpus.records),
        "n_synthetic": sum(r.data_quality == "synthetic_demo" for r in corpus.records),
        "built_at": utcnow().isoformat(),
    }
    index_dir = Path(index_dir)

    buf = io.BytesIO()
    np.save(buf, vecs)
    _atomic_write(index_dir / "vectors.npy", buf.getvalue())
    _atomic_write(index_dir / "index_meta.json", json.dumps(meta, indent=2).encode())
    return VectorIndex(vecs, meta["record_ids"], meta)


def load_index(corpus: Corpus, embedder, index_dir: Path) -> VectorIndex:
    index_dir = Path(index_dir)
    meta_file, vec_file = index_dir / "index_meta.json", index_dir / "vectors.npy"
    if not (meta_file.exists() and vec_file.exists()):
        raise IndexStaleError(f"No index in {index_dir}. Build it: python -m src.kb.build_index")
    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    if meta.get("format") != INDEX_FORMAT:
        raise IndexStaleError("Index format is incompatible; rebuild with python -m src.kb.build_index")
    if meta.get("embedding_model") != embedder.identifier:
        raise IndexStaleError(f"Index was built with '{meta.get('embedding_model')}' but the current embedder is "
                          f"'{embedder.identifier}'. Rebuild with python -m src.kb.build_index")
    if meta.get("corpus_hash") != corpus.content_hash:
        changed = sorted(rid for rid in set(meta.get("record_hashes", {})) | set(corpus.by_id)
                         if meta.get("record_hashes", {}).get(rid)
                         != (corpus.record_hash(rid) if rid in corpus.by_id else None))
        raise IndexStaleError("Pricing records changed since the index was built "
                          f"(changed/added/removed: {changed[:10] or 'sources or template'}). "
                          "Rebuild with python -m src.kb.build_index")
    vecs = np.load(vec_file)
    if vecs.shape != (len(meta["record_ids"]), meta["dim"]):
        raise IndexStaleError("Index vectors do not match metadata; rebuild the index")
    return VectorIndex(vecs, meta["record_ids"], meta)


def load_or_build(corpus: Corpus, embedder, index_dir: Path, rebuild_if_stale: bool = True) -> VectorIndex:
    try:
        return load_index(corpus, embedder, index_dir)
    except IndexStaleError:
        if not rebuild_if_stale:
            raise
        return build_index(corpus, embedder, index_dir)
