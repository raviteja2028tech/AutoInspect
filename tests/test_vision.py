"""Offline tests (no API key or internet needed).  Run from the project root:  python -m pytest tests/test_vision.py"""
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

import src.pipeline as pipeline
from src.fuse import fuse
from src.intake import IntakeError, load_image, load_images
from src.schemas import Damage, ImageResult


def _img(path, size=(640, 480), noisy=True, seed=0):
    rng = np.random.default_rng(seed)
    arr = rng.integers(0, 255, (size[1], size[0], 3), dtype=np.uint8) if noisy else np.full((size[1], size[0], 3), 128, np.uint8)
    Image.fromarray(arr).save(path)
    return path


def _result(view, *damages):
    return ImageResult(view=view, damages=list(damages), notes="")


def _d(comp, typ, sev, conf, loc="front"):
    return Damage(component=comp, damage_type=typ, severity=sev, location=loc, confidence=conf)


def test_intake_ok_and_resize():
    with tempfile.TemporaryDirectory() as t:
        p = _img(Path(t) / "a.png", (3000, 2000))
        out = load_image(p)
        assert max(out.width, out.height) == 1280 and out.jpeg_bytes[:2] == b"\xff\xd8"


def test_intake_rejects_bad_files():
    with tempfile.TemporaryDirectory() as t:
        small = _img(Path(t) / "s.jpg", (100, 100))
        txt = Path(t) / "x.txt"
        txt.write_text("hi")
        for bad in (small, txt, Path(t) / "missing.jpg"):
            try:
                load_image(bad)
                raise AssertionError("should have failed")
            except IntakeError:
                pass
        good = _img(Path(t) / "g.jpg")
        imgs, errs = load_images([good, txt])
        assert len(imgs) == 1 and len(errs) == 1
        try:
            load_images([good] * 6)
            raise AssertionError("too many images should fail")
        except IntakeError:
            pass


def test_blur_warning():
    with tempfile.TemporaryDirectory() as t:
        flat = _img(Path(t) / "flat.jpg", noisy=False)
        assert load_image(flat).warnings


def test_fuse_merges_duplicates():
    a = _result("front", _d("front_bumper", "dent", "moderate", 0.8))
    b = _result("left", _d("front_bumper", "dent", "severe", 0.9), _d("hood", "scratch", "minor", 0.4))
    out = fuse([a, b])
    bumper = next(x for x in out if x["component"] == "front_bumper")
    assert len([x for x in out if x["component"] == "front_bumper"]) == 1
    assert bumper["severity"] == "severe" and bumper["views_supporting"] == 2
    assert bumper["confidence"] == 0.85           # plain mean; the old +0.05 per-view bonus was removed
    assert next(x for x in out if x["component"] == "hood")["uncertain"] is True


def test_fuse_empty():
    assert fuse([_result("front")]) == []


def test_pipeline_with_fake_model():
    with tempfile.TemporaryDirectory() as t:
        paths = [_img(Path(t) / f"{n}.jpg", seed=i) for i, n in enumerate(("front", "left"))]
        fake = iter([_result("front", _d("front_bumper", "crack", "severe", 0.9)),
                     _result("left", _d("front_bumper", "crack", "moderate", 0.7))])
        original = pipeline.analyse_image
        pipeline.analyse_image = lambda b, view_hint=None, use_cache=True: next(fake)
        try:
            out = pipeline.analyse_case(paths, {"make": "Test"})
        finally:
            pipeline.analyse_image = original
        assert out["images_analysed"] == 2 and len(out["damages"]) == 1
        assert out["vehicle"]["make"] == "Test"
        assert any("recommended" in w for w in out["warnings"])      # only 2 photos
        for key in ("component", "damage_type", "severity", "location", "confidence"):
            assert key in out["damages"][0]


def test_schema_accepts_gemini_config():
    from google.genai import types
    types.GenerateContentConfig(response_mime_type="application/json", response_schema=ImageResult)


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print("PASS", fn.__name__)
    print(f"\nAll {len(tests)} tests passed.")
