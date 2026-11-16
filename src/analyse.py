"""Step 2 of the pipeline: ask Gemini to find the damage in ONE photo.

Setup:  put GEMINI_API_KEY=<key> (free key from https://aistudio.google.com/apikey) in the
project-root .env file, or set it in the terminal that launches the app. All settings are read
through src.settings (see .env.example): GEMINI_MODEL, GEMINI_API_VERSION (default v1beta),
GEMINI_MIN_INTERVAL, GEMINI_TIMEOUT_S, GEMINI_MAX_RETRIES.

API version: the analysis sends a system instruction. google-genai >= 3 defaults the Gemini
Developer API to "v1", which rejects system instructions ("Developer instruction is not enabled
for api version v1"), so the client is ALWAYS built with an explicit api_version (v1beta by
default) together with the timeout. No request-level http_options override it.

Behaviour:
- Cache key = image hash + provider + model + prompt version + schema version + view hint.
  Cache writes are atomic; a corrupt or out-of-range cache entry is discarded and re-analysed.
- Only transient errors (quota 429, 5xx, timeouts, malformed JSON) are retried. A missing or
  rejected key, unknown model or other configuration error fails at once (FatalAnalysisError).
- Calls are serialised with a lock so the rate limiter and shared client are safe if the UI
  triggers concurrent work.
- The result carries provenance (cache hit or fresh) in a private attribute, read via
  result_provenance(result). The API key is never stored in results.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
import time
from pathlib import Path

from pydantic import PrivateAttr, ValidationError

from . import settings
from .schemas import ImageResult
from .vocab import AMBIGUOUS_COMPONENTS, COMPONENTS, DAMAGE_TYPES, LOCATIONS, SEVERITIES

PROVIDER = "google-gemini"
PROMPT_VERSION = "v3"        # bump this when you edit the prompt, so old cache entries are not reused
SCHEMA_VERSION = "image-result-3"

# Module-level copies of the settings (tests monkeypatch these). refresh_settings() re-reads them.
MODEL = settings.GEMINI_MODEL          # verify with: python scripts/check_config.py --verify
API_VERSION = settings.GEMINI_API_VERSION
MIN_INTERVAL_S = settings.GEMINI_MIN_INTERVAL_S
TIMEOUT_S = settings.GEMINI_TIMEOUT_S
MAX_RETRIES = settings.GEMINI_MAX_RETRIES
CACHE_DIR: Path = settings.VISION_CACHE_DIR


def refresh_settings() -> None:
    """Pick up settings changed by settings.reload() and drop the cached client."""
    global MODEL, API_VERSION, MIN_INTERVAL_S, TIMEOUT_S, MAX_RETRIES, CACHE_DIR
    MODEL, API_VERSION = settings.GEMINI_MODEL, settings.GEMINI_API_VERSION
    MIN_INTERVAL_S, TIMEOUT_S = settings.GEMINI_MIN_INTERVAL_S, settings.GEMINI_TIMEOUT_S
    MAX_RETRIES, CACHE_DIR = settings.GEMINI_MAX_RETRIES, settings.VISION_CACHE_DIR
    reset_client()

_POSITIONED = [c for c in COMPONENTS if c not in AMBIGUOUS_COMPONENTS]

SYSTEM_PROMPT = f"""You are a vehicle damage inspector working for an insurance company.
You will be shown ONE photo of a car. Report only EXTERNAL damage that you can clearly see.

Rules:
- Use ONLY these component names: {", ".join(_POSITIONED)}. Use "other" if the damaged part is not in the list.
- Mirrors, tyres/wheels and side windows MUST include the side/position (e.g. side_mirror_left,
  wheel_tire_front_right, side_window_rear_left). If you cannot tell which one, use "other" and say why in notes.
- Use ONLY these damage types: {", ".join(DAMAGE_TYPES)}.
- Use ONLY these severities: {", ".join(SEVERITIES)}.
- Use ONLY these locations: {", ".join(LOCATIONS)}.
- "left" and "right" mean the CAR's own left and right (as seen by the driver sitting inside, facing forward), not the photographer's.
- Severity guide:
    minor    = cosmetic only (light scratch, small shallow dent, paint scuff).
    moderate = panel visibly deformed or paint broken through, but the part is still in place and repairable.
    severe   = structural deformation, shattered glass, broken lamp, flat or destroyed tire, or damage so large the part must be replaced.
- Give one entry per (component, damage_type). Do not list the same damage twice.
- If one impact affects several parts (for example a front corner hit), list each affected part separately.
- The rear side panel beside the rear door and taillight is the quarter panel (left_quarter_panel / right_quarter_panel), NOT "other".
- A part that is torn off, hanging loose or missing (for example a side mirror) is reported as "missing_part".
- Report "scratch" only for paint or surface scraping. Do not list both a dent and a scratch on the same component unless they are clearly separate areas.
- Only report damage visible in THIS photo; do not assume damage on parts that are hidden or out of frame.
- Do not report hidden, mechanical or structural damage you cannot see.
- confidence is a number from 0.0 to 1.0. Use below 0.5 when the damage is hard to see or you are guessing.
- evidence: a few words describing what is visible. severity_rationale: a few words on why that severity.
- box_2d: [ymin, xmin, ymax, xmax] on a 0-1000 grid tightly around the visible damage on this photo.
  Use null if you cannot localise it. Never guess a box for damage you cannot see.
- Never invent damage you cannot see. Reflections, dirt and shadows are not damage.
- is_vehicle: false if the photo is not of a car (then damages must be empty).
- vehicle_identity: the visible body colour, body type and make/model only if badges/shape make it clear (else "unknown").
  Do NOT read out number plates.
- If the car is undamaged, return an empty damages list and say so in notes.
- "view" says which side of the car the photo mainly shows (front, rear, left, right, top, close_up, unknown).
- notes: one short sentence about photo quality or anything unclear.
"""

_client = None
_client_sig: tuple | None = None       # (key fingerprint, api_version, timeout) of the cached client
_last_call = 0.0
_lock = threading.Lock()


class AnalysisError(RuntimeError):
    """The model could not analyse the image."""


class FatalAnalysisError(AnalysisError):
    """Configuration/authentication problem: retrying will not help."""


class _Provenance(ImageResult):
    _provenance: dict = PrivateAttr(default_factory=dict)


def result_provenance(result) -> dict:
    return dict(getattr(result, "_provenance", None) or {})


def _with_provenance(result: ImageResult, **prov) -> ImageResult:
    out = _Provenance.model_validate(result.model_dump())
    out._provenance = prov
    return out


def _redact(text) -> str:
    """Remove the API key from any text before it is shown, logged or raised."""
    key = settings.get_api_key()
    text = str(text)
    return text.replace(key, "[REDACTED]") if key else text


def build_client(api_key: str, api_version: str | None = None, timeout_s: float | None = None):
    """Create a google-genai client for the Gemini Developer API with an explicit API version."""
    from google import genai
    from google.genai import types
    http_options = types.HttpOptions(api_version=api_version or API_VERSION,
                                     timeout=int((timeout_s or TIMEOUT_S) * 1000))
    return genai.Client(api_key=api_key, vertexai=False, http_options=http_options)


def _get_client():
    """Shared client, rebuilt automatically when the key, API version or timeout changes."""
    global _client, _client_sig
    if _client is not None and _client_sig is None:          # injected (tests)
        return _client
    key = settings.get_api_key()
    if not key:
        status = settings.api_key_status()
        raise FatalAnalysisError(
            f"GEMINI_API_KEY is not set: {status.problem} "
            "Get a free key at https://aistudio.google.com/apikey. "
            "Diagnose with: python scripts/check_config.py")
    sig = (hashlib.sha256(key.encode()).hexdigest()[:12], API_VERSION, TIMEOUT_S)
    if _client is None or _client_sig != sig:
        _client = build_client(key, API_VERSION, TIMEOUT_S)
        _client_sig = sig
    return _client


def reset_client():
    """Forget the cached client (e.g. after the key changed)."""
    global _client, _client_sig
    _client = None
    _client_sig = None


def _wait_for_rate_limit():
    global _last_call
    gap = time.time() - _last_call
    if gap < MIN_INTERVAL_S:
        time.sleep(MIN_INTERVAL_S - gap)
    _last_call = time.time()


def _cache_path(jpeg_bytes: bytes, view_hint: str | None) -> Path:
    h = hashlib.sha256()
    h.update(jpeg_bytes)
    h.update(f"|{PROVIDER}|{MODEL}|{PROMPT_VERSION}|{SCHEMA_VERSION}|{view_hint}".encode())
    return CACHE_DIR / f"{h.hexdigest()}.json"


def _atomic_write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _parse(resp) -> ImageResult:
    parsed = getattr(resp, "parsed", None)
    if isinstance(parsed, ImageResult):
        return ImageResult.model_validate(parsed.model_dump())     # re-validate bounds
    text = (resp.text or "").strip()
    if not text:
        raise ValueError("empty response (the image may have been blocked by a safety filter)")
    text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return ImageResult.model_validate_json(text)


_FATAL_MARKERS = ("API_KEY_INVALID", "API key not valid", "PERMISSION_DENIED", "UNAUTHENTICATED",
                  " 401", " 403", "401 ", "403 ", "NOT_FOUND", "404", "is not found for API version",
                  "INVALID_ARGUMENT")
_TRANSIENT_MARKERS = ("429", "RESOURCE_EXHAUSTED", "500", "502", "503", "504", "UNAVAILABLE", "INTERNAL",
                      "DEADLINE_EXCEEDED", "timed out", "Timeout", "timeout", "Connection", "connection")


def classify_error(exc: Exception) -> str:
    """'fatal' | 'transient' | 'malformed'."""
    if isinstance(exc, (ValidationError, ValueError, json.JSONDecodeError)) and not hasattr(exc, "code"):
        return "malformed"
    code = getattr(exc, "code", None)
    if isinstance(code, int):
        if code == 429 or code >= 500:
            return "transient"
        if 400 <= code < 500:
            return "fatal"
    msg = f"{type(exc).__name__} {code or ''} {exc}"
    if any(m in msg for m in _TRANSIENT_MARKERS):
        return "transient"
    if any(m in msg for m in _FATAL_MARKERS):
        return "fatal"
    return "transient"


def analyse_image(jpeg_bytes: bytes, view_hint: str | None = None,
                  use_cache: bool = True, max_retries: int | None = None) -> ImageResult:
    """Analyse one photo (JPEG bytes). Results are cached on disk."""
    max_retries = max_retries or MAX_RETRIES
    cache_file = _cache_path(jpeg_bytes, view_hint)
    if use_cache and cache_file.exists():
        try:
            cached = ImageResult.model_validate_json(cache_file.read_text(encoding="utf-8"))
            return _with_provenance(cached, source="cache", cache_file=cache_file.name, model=MODEL,
                                    prompt_version=PROMPT_VERSION)
        except (ValidationError, ValueError, OSError):
            try:
                cache_file.unlink()                     # corrupt / out-of-range entry -> re-analyse
            except OSError:
                pass

    from google.genai import types

    user_text = "Inspect this vehicle photo and report the damage."
    if view_hint:
        user_text += f" The photographer says this photo shows the {view_hint} of the car."

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        response_mime_type="application/json",
        response_schema=ImageResult,
        temperature=0,
    )

    last_error = None
    with _lock:
        client = _get_client()
        for attempt in range(max_retries):
            try:
                _wait_for_rate_limit()
                resp = client.models.generate_content(
                    model=MODEL,
                    contents=[types.Part.from_bytes(data=jpeg_bytes, mime_type="image/jpeg"), user_text],
                    config=config,
                )
                result = _parse(resp)
                _atomic_write(cache_file, result.model_dump_json())
                return _with_provenance(result, source="fresh", cache_file=cache_file.name, model=MODEL,
                                        prompt_version=PROMPT_VERSION, attempts=attempt + 1)
            except AnalysisError:
                raise
            except Exception as exc:                            # network, quota, bad JSON ...
                last_error = exc
                kind = classify_error(exc)
                if kind == "fatal":
                    raise FatalAnalysisError(explain_fatal(exc)) from exc
                if attempt == max_retries - 1:
                    break
                wait = min(60, 15 * (attempt + 1)) if kind == "transient" and "429" in str(exc) else 2 * (attempt + 1)
                print(f"  [{kind} error, retrying in {wait}s: {_redact(exc)[:120]}]")
                time.sleep(wait)

    raise AnalysisError(f"Gemini analysis failed after {max_retries} attempts: {_redact(last_error)}")


def explain_fatal(exc: Exception) -> str:
    """Readable, key-free explanation of a non-retryable Gemini error."""
    msg = _redact(exc)
    low = msg.lower()
    if "api version" in low or "developer instruction" in low:
        hint = (f"The client used api_version={API_VERSION}. System instructions need v1beta; set "
                "GEMINI_API_VERSION=v1beta (the default) and reload the configuration or restart.")
    elif any(m in msg for m in ("API_KEY_INVALID", "API key not valid", "UNAUTHENTICATED", "401")):
        hint = "The key was rejected: check GEMINI_API_KEY in .env (no quotes/spaces) or create a new key."
    elif "PERMISSION_DENIED" in msg or "403" in msg:
        hint = "The key is not allowed to use this API/model (check the key's project and API restrictions)."
    elif "not found" in low or "404" in msg:
        hint = (f"Model '{MODEL}' is not available to this key/API version. List models with: "
                "python scripts/check_config.py --verify")
    else:
        hint = "Check GEMINI_API_KEY, GEMINI_MODEL and GEMINI_API_VERSION (python scripts/check_config.py)."
    return f"Gemini rejected the request (model {MODEL}, api {API_VERSION}): {msg}. {hint}"


def verify_connection(generate: bool = False) -> dict:
    """Check the key against the live API WITHOUT analysing an image.

    generate=False: list models (no generation request) and confirm GEMINI_MODEL is available.
    generate=True : also send one tiny request WITH a system instruction, proving the API
                    version accepts it (uses one small request of quota).
    Returns {"ok": bool, "stage": ..., "detail": ..., "model": ..., "api_version": ...}.
    The key is never included.
    """
    out = {"ok": False, "model": MODEL, "api_version": API_VERSION, "stage": "config", "detail": "",
           "model_available": None, "system_instruction_ok": None}
    try:
        client = _get_client()
    except AnalysisError as exc:
        out["detail"] = str(exc)
        return out
    try:
        out["stage"] = "list_models"
        names = []
        for m in client.models.list():
            actions = getattr(m, "supported_actions", None) or []
            if not actions or "generateContent" in actions:
                names.append(m.name.removeprefix("models/"))
        out["model_available"] = MODEL in names
        if not out["model_available"]:
            flash = sorted(n for n in names if "flash" in n)[:12]
            out["detail"] = (f"Connected, but model '{MODEL}' is not available to this key. "
                             f"Set GEMINI_MODEL to one of: {flash}")
            return out
        if generate:
            from google.genai import types
            out["stage"] = "generate_with_system_instruction"
            resp = client.models.generate_content(
                model=MODEL, contents="Reply with the single word OK.",
                config=types.GenerateContentConfig(system_instruction="You are a connectivity check.",
                                                   temperature=0, max_output_tokens=16))
            out["system_instruction_ok"] = True
            out["detail"] = f"Generation with a system instruction succeeded ({len((resp.text or '').strip())} chars returned)."
        out["ok"] = True
        out["stage"] = "done"
        if not out["detail"]:
            out["detail"] = "Key accepted and model available (no generation request sent)."
    except Exception as exc:                                    # noqa: BLE001 - report provider answer
        out["detail"] = explain_fatal(exc) if classify_error(exc) == "fatal" else _redact(exc)
    return out
