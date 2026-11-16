"""Shared pytest fixtures. Offline: deterministic stub embeddings, temp index directories.

The project .env (which may hold a real key) is NOT loaded during tests, so offline tests are
hermetic and can never spend API quota. Live tests opt in with RUN_LIVE=1, which re-enables .env.
"""
import os
import shutil
import sys
from pathlib import Path

if os.environ.get("RUN_LIVE") != "1":
    os.environ["AUTOINSPECT_NO_DOTENV"] = "1"          # must be set before src.settings is imported

import pytest  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.kb.retrieve import make_embedder, open_retriever  # noqa: E402

KB = ROOT / "knowledge"
SAMPLES = ROOT / "samples"


@pytest.fixture
def kb_copy(tmp_path):
    """A private, editable copy of the pricing corpus."""
    dst = tmp_path / "knowledge"
    shutil.copytree(KB, dst, ignore=shutil.ignore_patterns("index"))
    return dst


@pytest.fixture
def retriever(tmp_path):
    return open_retriever(kb_dir=KB, index_dir=tmp_path / "index", embedder=make_embedder("stub_test"))
