"""Validate the pricing corpus, embed it and save the index.

    python -m src.kb.build_index                      # semantic (sentence-transformers)
    python -m src.kb.build_index --embedder lexical_fallback
    python -m src.kb.build_index --check              # validate records only
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from .. import settings
from .embedding import EmbeddingUnavailable
from .index import build_index
from .records import CorpusError, load_corpus
from .retrieve import make_embedder


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kb-dir", default=str(settings.KNOWLEDGE_DIR))
    ap.add_argument("--index-dir", default=str(settings.INDEX_DIR))
    ap.add_argument("--embedder", default="semantic", choices=["semantic", "lexical_fallback", "stub_test"])
    ap.add_argument("--model", default=None, help="sentence-transformers model (default from EMBEDDING_MODEL)")
    ap.add_argument("--check", action="store_true", help="only validate the records")
    args = ap.parse_args()

    try:
        corpus = load_corpus(Path(args.kb_dir))
    except CorpusError as exc:
        raise SystemExit(f"ERROR: {exc}")
    types = Counter(r.data_quality for r in corpus.records)
    print(f"Validated {len(corpus.records)} records from {len(corpus.sources)} source(s): {dict(types)}")
    print(f"Corpus hash: {corpus.content_hash[:16]}")
    if types.get("synthetic_demo"):
        print("NOTE: synthetic_demo records are illustrative demo pricing - not market verified.")
    if args.check:
        return
    embedder = make_embedder(args.embedder, args.model)
    sub = Path(args.index_dir) / embedder.identifier.replace(":", "_").replace("/", "_")
    try:
        idx = build_index(corpus, embedder, sub)
    except EmbeddingUnavailable as exc:
        raise SystemExit(f"ERROR: {exc}\nOffline alternative (labelled lexical_fallback): "
                         f"python -m src.kb.build_index --embedder lexical_fallback")
    print(f"Index saved to {sub} ({idx.meta['n_records']} vectors, dim {idx.meta['dim']}, "
          f"model {idx.meta['embedding_model']}, method {idx.meta['retrieval_method']})")


if __name__ == "__main__":
    main()
