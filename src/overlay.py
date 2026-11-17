"""Draw approximate damage regions on the SAME processed (EXIF-corrected, resized) image the
model saw. Boxes are approximate VLM localisation, not segmentation."""
from __future__ import annotations

import io

from PIL import Image, ImageDraw, ImageFont

from .contracts import Observation

_COLORS = {"severe": (220, 38, 38), "moderate": (234, 140, 0), "minor": (37, 99, 235)}


def _font(size: int):
    for name in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def draw_overlay(jpeg_bytes: bytes, image_id: str, observations: list[Observation],
                 compact: bool = False) -> tuple[bytes, list[str]]:
    """Return (JPEG bytes with boxes, list of labels without a box on this image).

    compact=True labels each box with its finding ID only, in a larger font, for on-screen
    viewers that list the findings beside the image. The default (full labels) is used for
    the PDF report.
    """
    img = Image.open(io.BytesIO(jpeg_bytes)).convert("RGB")
    draw = ImageDraw.Draw(img)
    w, h = img.size
    font = _font(max(18, w // 36) if compact else max(14, w // 60))
    unboxed = []
    for o in observations:
        if image_id not in o.image_ids:
            continue
        box = o.bbox_by_image.get(image_id)
        full_label = f"{o.damage_id} {o.component} {o.damage_type} ({o.severity})"
        label = o.damage_id if compact else full_label
        if not box:
            unboxed.append(full_label)
            continue
        x0, y0, x1, y1 = box[0] * w, box[1] * h, box[2] * w, box[3] * h
        color = _COLORS.get(o.severity, (0, 0, 0))
        draw.rectangle([x0, y0, x1, y1], outline=color, width=max(3, w // 300))
        tb = draw.textbbox((0, 0), label, font=font)
        tw, th = tb[2] - tb[0], tb[3] - tb[1]
        ty = y0 - th - 6 if y0 - th - 6 > 0 else min(h - th - 4, y1 + 2)
        tx = min(max(0, x0), max(0, w - tw - 6))
        draw.rectangle([tx, ty, tx + tw + 6, ty + th + 4], fill=color)
        draw.text((tx + 3, ty + 1), label, fill=(255, 255, 255), font=font)
    draw.text((6, h - max(16, w // 55) - 6), "Approximate regions (AI) - not measurements",
              fill=(255, 255, 255), font=_font(max(12, w // 80)), stroke_width=2, stroke_fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88)
    return buf.getvalue(), unboxed
