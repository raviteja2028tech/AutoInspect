"""Step 1 of the pipeline: validate and preprocess the input photos.

v2 additions (backward compatible): file-size / pixel limits, full decode validation, stable
image IDs from the normalised image hash, exact-duplicate removal, a similar-image WARNING
(never a silent discard) and an image manifest. load_image()/load_images() keep their
signatures; intake_images() returns the richer result.
"""
from __future__ import annotations

import hashlib
import io
import re
import warnings as _warnings
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
MAX_SIDE = 1280          # longest side after resizing (pixels)
MIN_SIDE = 200           # reject images smaller than this
BLUR_WARN_BELOW = 60.0   # Laplacian variance below this -> "looks blurry" warning
MAX_IMAGES = 5
MAX_FILE_BYTES = 20 * 1024 * 1024      # 20 MB per file
MAX_PIXELS = 50_000_000                # decompression-bomb guard (50 MP)
SIMILAR_HAMMING = 4                    # dHash distance <= this -> "very similar" warning
TRANSFORM = f"exif_transpose -> RGB -> thumbnail({MAX_SIDE}) -> JPEG q90"


class IntakeError(ValueError):
    """The input photos are not usable."""


@dataclass
class ProcessedImage:
    name: str
    jpeg_bytes: bytes
    width: int
    height: int
    blur_score: float
    warnings: list[str] = field(default_factory=list)
    image_id: str = ""
    sha256: str = ""
    original_width: int = 0
    original_height: int = 0
    file_bytes: int = 0
    dhash: int = 0

    def manifest(self) -> dict:
        return {"image_id": self.image_id, "original_filename": self.name, "file_bytes": self.file_bytes,
                "original_size": [self.original_width, self.original_height],
                "processed_size": [self.width, self.height], "sha256": self.sha256,
                "transform": TRANSFORM, "blur_score": round(self.blur_score, 1), "warnings": list(self.warnings)}


@dataclass
class IntakeResult:
    images: list[ProcessedImage]
    rejected: list[dict]
    duplicates: list[dict]
    warnings: list[str]


def safe_upload_name(name: str, index: int) -> str:
    """Filesystem-safe, unique name for an uploaded file: no directories, no odd characters.

    The index prefix keeps two uploads with the same name from overwriting each other.
    """
    base = Path(str(name).replace("\\", "/")).name
    stem = re.sub(r"[^A-Za-z0-9._-]", "_", Path(base).stem)[:60].strip("._") or "photo"
    ext = Path(base).suffix.lower()
    return f"{index:02d}_{stem}{ext if ext in ALLOWED_EXT else '.jpg'}"


def _dhash(img: Image.Image) -> int:
    small = np.asarray(img.convert("L").resize((9, 8), Image.Resampling.LANCZOS), dtype=np.int16)
    bits = (small[:, 1:] > small[:, :-1]).flatten()
    return int("".join("1" if b else "0" for b in bits), 2)


def load_image(path) -> ProcessedImage:
    """Open one photo, validate it, fix rotation, resize, convert to RGB JPEG bytes."""
    path = Path(path)
    if not path.exists():
        raise IntakeError(f"File not found: {path}")
    if path.suffix.lower() not in ALLOWED_EXT:
        raise IntakeError(f"Unsupported file type '{path.suffix}' (use jpg, png, webp or bmp)")
    return _process(lambda: path, path.name, path.stat().st_size)


def inspect_image_bytes(name: str, data: bytes) -> ProcessedImage:
    """Validate and preprocess an in-memory upload exactly as load_image() would.

    Used by the UI to show quality warnings before analysis. The processing is identical, so
    the returned image_id/sha256 are the ones the pipeline will report for the same file.
    """
    name = Path(str(name).replace("\\", "/")).name or "photo"
    if Path(name).suffix.lower() not in ALLOWED_EXT:
        raise IntakeError(f"Unsupported file type '{Path(name).suffix}' (use jpg, png, webp or bmp)")
    return _process(lambda: io.BytesIO(data), name, len(data))


def _process(open_source, name: str, size: int) -> ProcessedImage:
    """Shared decode/validate/resize step. open_source() returns a fresh path or file object."""
    if size > MAX_FILE_BYTES:
        raise IntakeError(f"{name} is too large ({size / 1e6:.1f} MB); limit is {MAX_FILE_BYTES // 2**20} MB")
    if size == 0:
        raise IntakeError(f"{name} is empty")

    try:
        with _warnings.catch_warnings():
            _warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(open_source()) as probe:
                if probe.width * probe.height > MAX_PIXELS:
                    raise IntakeError(f"{name} has too many pixels ({probe.width}x{probe.height})")
                probe.verify()                       # structural check
            img = Image.open(open_source())
            img.load()                               # full decode (catches truncated files)
        img = ImageOps.exif_transpose(img)           # respect phone rotation
        img = img.convert("RGB")
    except IntakeError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombWarning,
            Image.DecompressionBombError) as exc:
        raise IntakeError(f"Cannot open image {name}: {exc}") from exc

    ow, oh = img.size
    if min(img.size) < MIN_SIDE:
        raise IntakeError(f"{name} is too small ({img.width}x{img.height}); need at least {MIN_SIDE}px")

    img.thumbnail((MAX_SIDE, MAX_SIDE))      # keeps aspect ratio, only shrinks

    gray = np.array(img.convert("L"))
    blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    warnings = []
    if blur < BLUR_WARN_BELOW:
        warnings.append(f"image looks blurry (sharpness {blur:.0f}); results may be unreliable")

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    data = buf.getvalue()
    digest = hashlib.sha256(data).hexdigest()
    return ProcessedImage(name, data, img.width, img.height, blur, warnings,
                          image_id=f"IMG-{digest[:10]}", sha256=digest, original_width=ow,
                          original_height=oh, file_bytes=size, dhash=_dhash(img))


def intake_images(paths) -> IntakeResult:
    """Load 1-5 photos; separate usable, rejected and exact-duplicate files."""
    paths = list(paths)
    if not paths:
        raise IntakeError("No images given.")
    if len(paths) > MAX_IMAGES:
        raise IntakeError(f"Too many images ({len(paths)}). Maximum is {MAX_IMAGES}.")

    good, rejected, dupes, warnings = [], [], [], []
    seen: dict[str, ProcessedImage] = {}
    for p in paths:
        try:
            img = load_image(p)
        except IntakeError as exc:
            rejected.append({"file": Path(p).name, "error": str(exc)})
            continue
        if img.sha256 in seen:
            first = seen[img.sha256]
            dupes.append({"file": img.name, "duplicate_of": first.name, "image_id": first.image_id,
                          "error": f"identical to {first.name} after normalisation; counted once"})
            continue
        for other in good:
            dist = bin(img.dhash ^ other.dhash).count("1")
            if dist <= SIMILAR_HAMMING:
                warnings.append(f"{img.name} looks very similar to {other.name} (perceptual distance {dist}); "
                                "both are kept - make sure they are different angles")
        seen[img.sha256] = img
        good.append(img)
    if not good:
        raise IntakeError("None of the images could be used: " + "; ".join(e["error"] for e in rejected))
    return IntakeResult(good, rejected, dupes, warnings)


def load_images(paths) -> tuple[list[ProcessedImage], list[dict]]:
    """Legacy API: (usable unique images, errors). Duplicates are reported as errors."""
    r = intake_images(paths)
    return r.images, r.rejected + r.duplicates
