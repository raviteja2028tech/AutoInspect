"""Photo intake: uploader, thumbnails with remove actions, unique-photo count, quality warnings.

Each upload is pre-checked locally with src.intake.inspect_image_bytes - the same decode,
resize and hashing the pipeline uses - so the warnings shown here (unreadable, too small,
blurry, duplicate, near-duplicate) and the image IDs match what the analysis will report.
No network call is made here.
"""
from __future__ import annotations

import hashlib
import io
import uuid

import streamlit as st
from PIL import Image, ImageOps

from src.intake import ALLOWED_EXT, MAX_IMAGES, SIMILAR_HAMMING, IntakeError, inspect_image_bytes

from .format import file_size
from .html import chip, esc, md, render, section_title

UPLOAD_TYPES = sorted(e.lstrip(".") for e in ALLOWED_EXT)
SHOT_LIST = ("Front", "Rear", "Left side", "Right side", "Close-up of each damaged area")
THUMB_SIZE = (360, 270)          # 4:3, centre-cropped so the grid stays even
RECOMMENDED_MIN = 3


def make_thumb(jpeg_bytes: bytes, size=THUMB_SIZE) -> bytes:
    img = Image.open(io.BytesIO(jpeg_bytes)).convert("RGB")
    img = ImageOps.fit(img, size, Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=82)
    return buf.getvalue()


def precheck(name: str, data: bytes) -> dict:
    """Local validation of one upload (no API call)."""
    photo = {"uid": uuid.uuid4().hex[:10], "name": str(name), "size": len(data), "data": data,
             "raw_sha": hashlib.sha256(data).hexdigest(), "ok": False, "error": None,
             "image_id": None, "sha256": None, "blur": None, "warnings": [], "dims": None,
             "thumb": None, "dhash": None}
    try:
        img = inspect_image_bytes(name, data)
    except IntakeError as exc:
        photo["error"] = str(exc)
        return photo
    photo.update(ok=True, image_id=img.image_id, sha256=img.sha256, blur=round(img.blur_score),
                 warnings=list(img.warnings), dims=(img.original_width, img.original_height),
                 thumb=make_thumb(img.jpeg_bytes), dhash=img.dhash)
    return photo


def ingest(widget_key: str) -> None:
    """file_uploader on_change: move new files into the managed photo list, then clear the uploader."""
    ss = st.session_state
    files = ss.get(widget_key) or []
    skipped = []
    for f in files:
        if len(ss.photos) >= MAX_IMAGES:
            skipped.append(f.name)
            continue
        ss.photos.append(precheck(f.name, f.getvalue()))
    ss.upload_notice = (
        f"Only {MAX_IMAGES} photos can be analysed together; {len(skipped)} file(s) were not added: "
        + ", ".join(skipped)) if skipped else None
    ss.uploader_gen += 1          # a fresh, empty uploader; the managed list is the source of truth


def remove_photo(uid: str) -> None:
    ss = st.session_state
    ss.photos = [p for p in ss.photos if p["uid"] != uid]
    ss.upload_notice = None


def clear_photos() -> None:
    st.session_state.photos = []
    st.session_state.upload_notice = None
    st.session_state.uploader_gen += 1


def assess(photos: list[dict]) -> list[dict]:
    """Per-photo status in upload order: ready / blurry / similar / duplicate / unusable."""
    out, seen = [], {}
    for idx, p in enumerate(photos, 1):
        info = {"index": idx, "photo": p, "state": "ready", "notes": []}
        if not p["ok"]:
            info["state"] = "unusable"
            info["notes"].append(p["error"] or "cannot be read")
        elif p["sha256"] in seen:
            info["state"] = "duplicate"
            info["notes"].append(f"Same image as Photo {seen[p['sha256']]}; analysed once")
        else:
            for other in out:
                q = other["photo"]
                if other["state"] in ("ready", "blurry", "similar") and q["dhash"] is not None:
                    dist = bin(p["dhash"] ^ q["dhash"]).count("1")
                    if dist <= SIMILAR_HAMMING:
                        info["state"] = "similar"
                        info["notes"].append(f"Very similar to Photo {other['index']}; use a different angle")
                        break
            if p["warnings"]:
                info["notes"].append(f"Looks blurry (sharpness {p['blur']}); findings may be unreliable")
                if info["state"] == "ready":
                    info["state"] = "blurry"
            seen[p["sha256"]] = idx
        out.append(info)
    return out


def summary(photos: list[dict]) -> dict:
    rows = assess(photos)
    unique = [r for r in rows if r["state"] in ("ready", "blurry", "similar")]
    return {"rows": rows, "total": len(photos), "unique": len(unique),
            "unusable": sum(r["state"] == "unusable" for r in rows),
            "duplicates": sum(r["state"] == "duplicate" for r in rows),
            "blurry": sum(bool(r["photo"]["warnings"]) for r in rows if r["state"] != "duplicate"),
            "similar": sum(r["state"] == "similar" for r in rows)}


def photo_signature(photos: list[dict]) -> str:
    return hashlib.sha256("|".join(p["raw_sha"] for p in photos).encode()).hexdigest()[:16]


STATE_CHIP = {
    "ready": ("Ready", "green"),
    "blurry": ("Blurry", "amber"),
    "similar": ("Similar view", "amber"),
    "duplicate": ("Duplicate", "amber"),
    "unusable": ("Can't be used", "red"),
}


def render_photo_panel() -> dict:
    """Uploader + thumbnails + quality summary. Returns summary()."""
    ss = st.session_state
    s = summary(ss.photos)
    count_tone = "green" if s["unique"] >= RECOMMENDED_MIN else ("amber" if s["total"] else "neutral")
    right = chip(f"{s['total']} of {MAX_IMAGES} added · {s['unique']} unique", count_tone)
    section_title("Damage photos", "3–5 photos of the same vehicle: front, rear, both sides and close-ups "
                  "of the damage.", right)

    if s["total"] < MAX_IMAGES:
        key = f"photo_uploader_{ss.uploader_gen}"
        st.file_uploader(
            "Add photos", type=UPLOAD_TYPES, accept_multiple_files=True, key=key,
            on_change=ingest, args=(key,), label_visibility="collapsed",
            help="JPG, PNG, WebP or BMP, up to 20 MB each. Photos stay on this machine until you "
                 "press Analyze; they are then sent to Gemini for analysis.")
    else:
        st.info(f"{MAX_IMAGES} photos added, the maximum for one assessment. Remove one to add another.",
                icon=":material/photo_library:")
    if ss.upload_notice:
        st.warning(md(ss.upload_notice), icon=":material/block:")
    if s["unique"] < RECOMMENDED_MIN:
        render('<p class="ai-shots-title">Suggested shots</p><ul class="ai-shots">' + "".join(
            f"<li>{chip(x)}</li>" for x in SHOT_LIST) + "</ul>")

    if s["rows"]:
        with st.container(horizontal=True, gap="xsmall", key="photo_grid"):
            for row in s["rows"]:
                _thumb(row)
        c1, c2 = st.columns([3, 1], vertical_alignment="center")
        with c2:
            st.button("Clear all", icon=":material/delete_sweep:", type="tertiary", on_click=clear_photos,
                      key="photos_clear", width="stretch")
        with c1:
            _quality_notes(s)
    return s


def _thumb(row: dict) -> None:
    p, idx = row["photo"], row["index"]
    label, tone = STATE_CHIP[row["state"]]
    with st.container(border=True, key=f"ptile_{p['uid']}", width=176, gap="xsmall"):
        if p["thumb"]:
            st.image(p["thumb"], width="stretch", alt=f"Photo {idx}: {p['name']}")
        else:
            render('<div class="ai-thumb-missing" role="img" aria-label="Unreadable file">'
                   '<span>No preview</span></div>')
        meta = f"{file_size(p['size'])}" + (f" · {p['dims'][0]}×{p['dims'][1]}" if p["dims"] else "")
        note_cls = "ai-thumb-note ai-thumb-note--red" if row["state"] == "unusable" else "ai-thumb-note"
        notes = "".join(f'<p class="{note_cls}">{esc(n)}</p>' for n in row["notes"])
        render(f'<div class="ai-thumb-meta"><div class="ai-thumb-head"><strong>Photo {idx}</strong>'
               f'{chip(label, tone)}</div><p class="ai-thumb-name" title="{esc(p["name"])}">{esc(p["name"])}</p>'
               f'<p class="ai-thumb-size">{esc(meta)}</p>{notes}</div>')
        st.button(f"Remove photo {idx}", icon=":material/close:", key=f"rm_{p['uid']}", type="tertiary",
                  on_click=remove_photo, args=(p["uid"],), width="stretch")


def _quality_notes(s: dict) -> None:
    notes = []
    if s["unique"] == 0:
        notes.append(("red", "None of the photos can be analysed. Add clear JPG or PNG photos of the vehicle."))
    elif s["unique"] < RECOMMENDED_MIN:
        notes.append(("amber", f"Only {s['unique']} unique photo{'s' if s['unique'] != 1 else ''}. "
                               f"{RECOMMENDED_MIN}–5 from different sides give better coverage; the report "
                               "will flag limited coverage."))
    if s["duplicates"]:
        notes.append(("neutral", f"{s['duplicates']} duplicate photo(s) will be analysed once."))
    if s["unusable"]:
        notes.append(("red", f"{s['unusable']} file(s) can't be read and will be skipped."))
    if s["blurry"]:
        notes.append(("amber", f"{s['blurry']} photo(s) look blurry; retake them if you can."))
    if notes:
        render('<div class="ai-quality">' + "".join(
            f'<p class="ai-quality-item ai-quality-item--{tone}">{esc(text)}</p>' for tone, text in notes) + "</div>")
