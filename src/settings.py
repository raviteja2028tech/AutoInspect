"""Runtime configuration for the whole project (single source of truth).

Where a value comes from, highest priority first:

1. A variable that was already set (non-empty) in the process environment when Python
   started, e.g. ``$env:GEMINI_API_KEY="..."`` / ``export GEMINI_API_KEY=...`` typed in the
   SAME terminal that launched the app. Another terminal's variables are never visible.
2. ``<PROJECT_ROOT>/.env`` - always the project-root file, resolved from this module's
   location, never from the current working directory or a parent folder.
3. Built-in defaults.

``.env`` never overrides an explicit environment variable. ``reload()`` re-reads ``.env``
without restarting (the Streamlit app exposes it as "Reload configuration"); a variable set
in the launching terminal cannot change inside a running process - restart it instead.

Invalid values never crash an import: they fall back to the default and are reported in
``CONFIG_ERRORS`` with a readable message (shown by the app and ``scripts/check_config.py``).

Secrets: the API key value is never logged, printed or returned by any diagnostic helper -
only whether it is configured and where it came from.
"""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"
ENV_EXAMPLE_FILE = PROJECT_ROOT / ".env.example"
NO_DOTENV_FLAG = "AUTOINSPECT_NO_DOTENV"      # "1" = ignore .env (hermetic offline tests)

KEY_VARIABLES = ("GEMINI_API_KEY", "GOOGLE_API_KEY")   # first non-placeholder value wins
SUPPORTED_API_VERSIONS = ("v1beta", "v1alpha")
DEFAULT_API_VERSION = "v1beta"

_PLACEHOLDERS = {"", "your-api-key-here", "your_api_key_here", "your-gemini-api-key", "changeme",
                 "replace-me", "xxx", "none", "null", "<your-key>", "<your_api_key>"}

# Variables explicitly present (non-empty) when this process started. .env never overrides them.
_EXPLICIT: frozenset[str] = frozenset(k for k, v in os.environ.items() if v.strip())
_FROM_DOTENV: dict[str, str] = {}
ENV_FILE_STATUS = "not loaded"
CONFIG_ERRORS: list[str] = []


class ConfigError(ValueError):
    """A configuration value is invalid or missing."""


# --------------------------------------------------------------------------- .env handling
def load_env_file(path: Path | None = None) -> list[str]:
    """Apply ``path`` (default: project-root .env) to os.environ; return the names applied.

    Values that an earlier call took from .env are refreshed (so edits and removals are
    picked up), but explicitly set environment variables are left untouched.
    """
    global ENV_FILE_STATUS
    path = Path(path or ENV_FILE)
    for name, value in list(_FROM_DOTENV.items()):        # forget what .env set last time
        if os.environ.get(name) == value:
            os.environ.pop(name, None)
        _FROM_DOTENV.pop(name, None)

    if os.environ.get(NO_DOTENV_FLAG) == "1":
        ENV_FILE_STATUS = f"disabled ({NO_DOTENV_FLAG}=1)"
        return []
    if not path.is_file():
        ENV_FILE_STATUS = f"not found at {path}"
        return []
    try:
        from dotenv import dotenv_values
    except ImportError:                                    # pragma: no cover
        ENV_FILE_STATUS = "python-dotenv is not installed; .env ignored (pip install -r requirements.txt)"
        return []
    try:
        values = dotenv_values(path, encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        ENV_FILE_STATUS = f"could not read {path}: {exc}"
        return []

    applied, skipped = [], []
    for name, value in values.items():
        value = (value or "").strip()
        if not value:
            continue
        if name in _EXPLICIT:
            skipped.append(name)
            continue
        os.environ[name] = value
        _FROM_DOTENV[name] = value
        applied.append(name)
    ENV_FILE_STATUS = f"loaded {len(applied)} variable(s) from {path}"
    if skipped:
        ENV_FILE_STATUS += f"; kept explicit environment value(s) for {', '.join(sorted(skipped))}"
    return applied


def value_source(name: str) -> str | None:
    """'process environment' | '.env file' | None (unset). Never returns the value."""
    if not os.environ.get(name, "").strip():
        return None
    return ".env file" if _FROM_DOTENV.get(name) == os.environ.get(name) else "process environment"


# --------------------------------------------------------------------------- parsing helpers
def _env(name: str, default: str) -> str:
    value = os.environ.get(name, "").strip()
    return value or default


def _number(name: str, default, kind, lo=None, hi=None):
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = kind(raw)
    except (TypeError, ValueError):
        CONFIG_ERRORS.append(f"{name}='{raw}' is not a valid {kind.__name__}; using default {default}.")
        return default
    if (lo is not None and value < lo) or (hi is not None and value > hi):
        CONFIG_ERRORS.append(f"{name}={raw} is outside the allowed range [{lo}, {hi}]; using default {default}.")
        return default
    return value


def _path(name: str, default: Path) -> Path:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    p = Path(raw).expanduser()
    return p if p.is_absolute() else PROJECT_ROOT / p     # relative to the project, never the CWD


def _decimal_rate(name: str) -> Decimal | None:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return None
    try:
        rate = Decimal(raw)
    except InvalidOperation:
        CONFIG_ERRORS.append(f"{name}='{raw}' is not a number (use e.g. 0.18 for 18%); tax disabled.")
        return None
    if not (Decimal("0") <= rate < Decimal("1")):
        CONFIG_ERRORS.append(f"{name}={raw} must be a fraction between 0 and 1 (e.g. 0.18); tax disabled.")
        return None
    return rate


def _apply() -> None:
    """(Re)compute every module-level setting from the current environment."""
    global KNOWLEDGE_DIR, INDEX_DIR, CACHE_DIR, VISION_CACHE_DIR, OUTPUT_DIR, EMBEDDING_MODEL
    global DEFAULT_REGION, DEFAULT_CURRENCY, GST_RATE, RETRIEVAL_TOP_K
    global GEMINI_MODEL, GEMINI_API_VERSION, GEMINI_TIMEOUT_S, GEMINI_MAX_RETRIES, GEMINI_MIN_INTERVAL_S
    CONFIG_ERRORS.clear()

    KNOWLEDGE_DIR = _path("KB_DIR", PROJECT_ROOT / "knowledge")
    CACHE_DIR = _path("CACHE_DIR", PROJECT_ROOT / ".cache")
    INDEX_DIR = _path("KB_INDEX_DIR", CACHE_DIR / "kb-index")              # generated, never committed
    VISION_CACHE_DIR = _path("VISION_CACHE_DIR", CACHE_DIR / "vision")     # earlier live Gemini answers
    OUTPUT_DIR = _path("OUTPUT_DIR", PROJECT_ROOT / "outputs")             # CLI reports (git-ignored)

    EMBEDDING_MODEL = _env("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    DEFAULT_REGION = _env("PRICING_REGION", "IN-DEMO-METRO")
    DEFAULT_CURRENCY = _env("PRICING_CURRENCY", "INR").upper()
    GST_RATE = _decimal_rate("GST_RATE")
    RETRIEVAL_TOP_K = _number("RETRIEVAL_TOP_K", 3, int, 1, 20)

    GEMINI_MODEL = _env("GEMINI_MODEL", "gemini-2.5-flash")
    version = _env("GEMINI_API_VERSION", DEFAULT_API_VERSION).lower()
    if version not in SUPPORTED_API_VERSIONS:
        CONFIG_ERRORS.append(
            f"GEMINI_API_VERSION='{version}' is not supported: the analysis uses a system instruction, "
            f"which the Gemini Developer API only accepts on {' or '.join(SUPPORTED_API_VERSIONS)}. "
            f"Using {DEFAULT_API_VERSION}.")
        version = DEFAULT_API_VERSION
    GEMINI_API_VERSION = version
    GEMINI_TIMEOUT_S = _number("GEMINI_TIMEOUT_S", 90.0, float, 5, 600)
    GEMINI_MAX_RETRIES = _number("GEMINI_MAX_RETRIES", 4, int, 1, 10)
    GEMINI_MIN_INTERVAL_S = _number("GEMINI_MIN_INTERVAL", 4.5, float, 0, 120)


def reload() -> None:
    """Re-read the project .env and recompute settings (no process restart needed for .env edits).

    Modules that cache settings (src.analyse) expose their own refresh; the app calls both.
    """
    load_env_file()
    _apply()


# --------------------------------------------------------------------------- API key helpers
def _is_placeholder(value: str) -> bool:
    v = value.strip().strip('"').strip("'").lower()
    return v in _PLACEHOLDERS or v.startswith(("your", "<", "replace", "paste", "insert"))


def get_api_key() -> str | None:
    """The usable Gemini key visible to THIS process, or None. Never log the return value."""
    for name in KEY_VARIABLES:
        value = os.environ.get(name, "").strip()
        if value and not _is_placeholder(value):
            return value
    return None


@dataclass(frozen=True)
class KeyStatus:
    configured: bool                 # a non-placeholder key is visible to this process
    variable: str | None             # which variable supplies it
    source: str | None               # 'process environment' | '.env file'
    problem: str | None              # why it is not configured (or a caution when it is)
    env_file: str
    env_file_exists: bool
    env_file_status: str

    def summary(self) -> str:
        if self.configured:
            return (f"Key configured via {self.variable} from the {self.source} "
                    "(not yet verified with Google - run a connection check).")
        return f"Key NOT configured: {self.problem}"

    def as_dict(self) -> dict:
        return asdict(self)


def api_key_status() -> KeyStatus:
    """Whether a key is configured, and where from - without revealing it."""
    problem, variable, source = None, None, None
    for name in KEY_VARIABLES:
        value = os.environ.get(name, "").strip()
        if not value:
            continue
        if _is_placeholder(value):
            problem = (f"{name} is set to a placeholder value from the {value_source(name)}; "
                       f"put your real key in {ENV_FILE}")
            continue
        variable, source = name, value_source(name)
        break
    configured = variable is not None
    if configured and variable == "GOOGLE_API_KEY" and os.environ.get("GEMINI_API_KEY", "").strip():
        problem = "GEMINI_API_KEY holds a placeholder; GOOGLE_API_KEY is being used instead."
    if not configured and problem is None:
        problem = (f"neither GEMINI_API_KEY nor GOOGLE_API_KEY is visible to this process. Put "
                   f"GEMINI_API_KEY=<key> in {ENV_FILE} (then use 'Reload configuration' or restart), "
                   "or set it in the SAME terminal before launching.")
    return KeyStatus(configured, variable, source, problem, str(ENV_FILE), ENV_FILE.is_file(), ENV_FILE_STATUS)


def diagnostics() -> list[str]:
    """Human-readable hints about common misconfigurations (no secret values)."""
    hints = list(CONFIG_ERRORS)
    if os.environ.get("GOOGLE_GENAI_API_VERSION"):
        hints.append("GOOGLE_GENAI_API_VERSION is set in the environment; it is ignored because the client "
                      f"pins api_version={GEMINI_API_VERSION} explicitly.")
    if os.environ.get("GOOGLE_GENAI_USE_VERTEXAI"):
        hints.append("GOOGLE_GENAI_USE_VERTEXAI is set; it is ignored - this app uses the Gemini Developer API "
                     "(AI Studio key).")
    if ENV_EXAMPLE_FILE.is_file():
        try:
            for line in ENV_EXAMPLE_FILE.read_text(encoding="utf-8").splitlines():
                name, _, value = line.partition("=")
                if name.strip() in KEY_VARIABLES and value.strip() and not _is_placeholder(value):
                    hints.append(f".env.example contains a value for {name.strip()}. That file is a template and "
                                 f"is NEVER loaded; move the key to {ENV_FILE} and blank it in .env.example.")
        except OSError:
            pass
    stray = {Path.cwd() / ".env", PROJECT_ROOT.parent / ".env", PROJECT_ROOT.parent.parent / ".env"}
    for p in sorted(stray):
        try:
            if p.resolve() != ENV_FILE.resolve() and p.is_file():
                hints.append(f"Found {p}, which is NOT read. Only {ENV_FILE} is loaded.")
        except OSError:
            pass
    return hints


def describe() -> dict:
    """Non-secret snapshot of the effective configuration (for the app and check script)."""
    return {
        "project_root": str(PROJECT_ROOT),
        "env_file": str(ENV_FILE),
        "env_file_status": ENV_FILE_STATUS,
        "gemini_model": GEMINI_MODEL,
        "gemini_model_source": value_source("GEMINI_MODEL") or "default",
        "gemini_api_version": GEMINI_API_VERSION,
        "gemini_timeout_s": GEMINI_TIMEOUT_S,
        "gemini_max_retries": GEMINI_MAX_RETRIES,
        "embedding_model": EMBEDDING_MODEL,
        "pricing_region": DEFAULT_REGION,
        "pricing_currency": DEFAULT_CURRENCY,
        "gst_rate": str(GST_RATE) if GST_RATE is not None else None,
        "retrieval_top_k": RETRIEVAL_TOP_K,
        "knowledge_dir": str(KNOWLEDGE_DIR),
        "index_dir": str(INDEX_DIR),
        "vision_cache_dir": str(VISION_CACHE_DIR),
        "config_errors": list(CONFIG_ERRORS),
    }


# Initialise on import: project .env first (without overriding explicit variables), then values.
load_env_file()
_apply()
