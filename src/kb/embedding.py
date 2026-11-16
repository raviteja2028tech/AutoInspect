"""Embedding back-ends.

- SentenceTransformerEmbedder: the real semantic model (default all-MiniLM-L6-v2, configurable).
- HashingEmbedder: deterministic bag-of-words hashing. Used as a STUB in offline tests
  (method 'stub_test') and as the optional, clearly labelled 'lexical_fallback'.
"""
from __future__ import annotations

import hashlib
import re

import numpy as np


class EmbeddingUnavailable(RuntimeError):
    """The semantic embedding model could not be loaded."""


class SentenceTransformerEmbedder:
    method = "semantic"

    def __init__(self, model_name: str):
        self.model_name = model_name
        self.identifier = f"sentence-transformers:{model_name}"
        self._model = None

    def _load(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise EmbeddingUnavailable(
                    "sentence-transformers is not installed. Run: pip install -r requirements.txt") from exc
            try:
                self._model = SentenceTransformer(self.model_name, device="cpu")
            except Exception as exc:  # network / disk / unknown model name
                raise EmbeddingUnavailable(
                    f"Could not load embedding model '{self.model_name}'. The first run downloads it "
                    f"from Hugging Face (needs internet); later runs use the local cache. "
                    f"Set EMBEDDING_MODEL to another sentence-transformers model if needed. Cause: {exc}"
                ) from exc
        return self._model

    def embed(self, texts: list[str]) -> np.ndarray:
        vecs = self._load().encode(list(texts), normalize_embeddings=True, show_progress_bar=False)
        return np.asarray(vecs, dtype=np.float32)


class HashingEmbedder:
    """Deterministic token-hashing vectors. Not semantic; ranking is lexical overlap."""

    def __init__(self, dim: int = 512, method: str = "stub_test"):
        if method not in ("stub_test", "lexical_fallback"):
            raise ValueError("method must be stub_test or lexical_fallback")
        self.dim = dim
        self.method = method
        self.identifier = f"hashing-bow:{dim}:{method}"

    def embed(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, t in enumerate(texts):
            for tok in re.findall(r"[a-z0-9]+", t.lower()):
                h = int.from_bytes(hashlib.md5(tok.encode()).digest()[:4], "little")
                out[i, h % self.dim] += 1.0
            n = np.linalg.norm(out[i])
            if n:
                out[i] /= n
        return out
