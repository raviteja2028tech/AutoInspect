"""Configuration loading, key diagnostics and Gemini client setup (offline, no network)."""
import os
from unittest import mock

import pytest

from src import analyse, settings

FAKE_KEY = "AIzaFAKE-test-key-0123456789abcdef"


@pytest.fixture
def env(monkeypatch, tmp_path):
    """Isolated environment: no real key, .env loading enabled for a temp file, restored afterwards."""
    with mock.patch.dict(os.environ, clear=False):
        for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GEMINI_MODEL", "GEMINI_API_VERSION",
                     "GEMINI_TIMEOUT_S", "GST_RATE", settings.NO_DOTENV_FLAG):
            os.environ.pop(name, None)
        monkeypatch.setattr(settings, "_FROM_DOTENV", {})
        monkeypatch.setattr(settings, "_EXPLICIT", frozenset())
        env_file = tmp_path / ".env"
        monkeypatch.setattr(settings, "ENV_FILE", env_file)
        yield env_file
    settings._apply()          # recompute module settings from the restored environment
    analyse.refresh_settings()


# ---------------------------------------------------------------- .env precedence
def test_env_file_is_loaded_and_reload_picks_up_edits(env):
    env.write_text(f"GEMINI_API_KEY={FAKE_KEY}\nGEMINI_MODEL=model-a\n", encoding="utf-8")
    settings.reload()
    assert settings.get_api_key() == FAKE_KEY and settings.GEMINI_MODEL == "model-a"
    st = settings.api_key_status()
    assert st.configured and st.source == ".env file" and st.variable == "GEMINI_API_KEY"

    env.write_text("GEMINI_MODEL=model-b\n", encoding="utf-8")      # key removed, model edited
    settings.reload()
    assert settings.get_api_key() is None and settings.GEMINI_MODEL == "model-b"
    assert not settings.api_key_status().configured


def test_explicit_environment_wins_over_env_file(env, monkeypatch):
    os.environ["GEMINI_API_KEY"] = "AIzaEXPLICIT-key-value-000000000000"
    monkeypatch.setattr(settings, "_EXPLICIT", frozenset({"GEMINI_API_KEY"}))
    env.write_text(f"GEMINI_API_KEY={FAKE_KEY}\n", encoding="utf-8")
    settings.reload()
    assert settings.get_api_key() == "AIzaEXPLICIT-key-value-000000000000"
    assert settings.api_key_status().source == "process environment"
    assert "kept explicit" in settings.ENV_FILE_STATUS


def test_missing_env_file_and_placeholder_are_reported(env):
    settings.reload()
    st = settings.api_key_status()
    assert not st.configured and not st.env_file_exists and "GEMINI_API_KEY" in st.problem
    env.write_text("GEMINI_API_KEY=your-api-key-here\n", encoding="utf-8")
    settings.reload()
    st = settings.api_key_status()
    assert not st.configured and "placeholder" in st.problem


def test_diagnostics_never_contain_the_key(env, tmp_path, monkeypatch):
    env.write_text(f"GEMINI_API_KEY={FAKE_KEY}\n", encoding="utf-8")
    example = tmp_path / ".env.example"
    example.write_text(f"GEMINI_API_KEY={FAKE_KEY}\n", encoding="utf-8")
    monkeypatch.setattr(settings, "ENV_EXAMPLE_FILE", example)
    settings.reload()
    blob = repr(settings.describe()) + repr(settings.api_key_status()) + repr(settings.diagnostics())
    assert FAKE_KEY not in blob
    assert any(".env.example contains a value" in h for h in settings.diagnostics())


def test_invalid_values_fall_back_with_readable_errors(env):
    env.write_text("GEMINI_TIMEOUT_S=abc\nGEMINI_API_VERSION=v1\nGST_RATE=18\n", encoding="utf-8")
    settings.reload()
    assert settings.GEMINI_TIMEOUT_S == 90.0 and settings.GEMINI_API_VERSION == "v1beta"
    assert settings.GST_RATE is None
    errors = " ".join(settings.CONFIG_ERRORS)
    assert "GEMINI_TIMEOUT_S" in errors and "system instruction" in errors and "GST_RATE" in errors


def test_relative_paths_resolve_from_project_root(env, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)                                   # an unrelated working directory
    env.write_text("KB_DIR=knowledge\n", encoding="utf-8")
    settings.reload()
    assert settings.KNOWLEDGE_DIR == settings.PROJECT_ROOT / "knowledge"


# ---------------------------------------------------------------- Gemini client
class _FakeGenai:
    def __init__(self):
        self.created = []

    def Client(self, **kw):                                       # noqa: N802 - mimics genai.Client
        self.created.append(kw)
        return mock.MagicMock(name="client")


def test_client_pins_v1beta_with_timeout_and_rebuilds_on_key_change(env, monkeypatch):
    fake = _FakeGenai()
    monkeypatch.setattr("google.genai.Client", fake.Client)
    monkeypatch.setattr(analyse, "_client", None)
    monkeypatch.setattr(analyse, "_client_sig", None)
    env.write_text(f"GEMINI_API_KEY={FAKE_KEY}\n", encoding="utf-8")
    settings.reload()
    analyse.refresh_settings()

    c1 = analyse._get_client()
    kw = fake.created[-1]
    assert kw["http_options"].api_version == "v1beta"
    assert kw["http_options"].timeout == int(analyse.TIMEOUT_S * 1000)
    assert kw["vertexai"] is False and kw["api_key"] == FAKE_KEY
    assert analyse._get_client() is c1 and len(fake.created) == 1     # cached

    env.write_text("GEMINI_API_KEY=AIzaSECOND-key-1111111111111111\n", encoding="utf-8")
    settings.reload()                                                  # no refresh call needed
    analyse._get_client()
    assert len(fake.created) == 2                                      # rebuilt for the new key


def test_request_keeps_system_instruction_and_no_http_override(env, monkeypatch, tmp_path):
    captured = {}

    class Client:
        def __init__(self):
            self.models = self

        def generate_content(self, **kw):
            captured.update(kw)
            return mock.MagicMock(parsed=None, text='{"view":"front","damages":[],"notes":"ok"}')

    monkeypatch.setattr(analyse, "_client", Client())
    monkeypatch.setattr(analyse, "_client_sig", None)
    monkeypatch.setattr(analyse, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(analyse, "MIN_INTERVAL_S", 0)
    analyse.analyse_image(b"jpeg-bytes", use_cache=False)
    cfg = captured["config"]
    assert cfg.system_instruction == analyse.SYSTEM_PROMPT
    assert cfg.http_options is None                  # nothing overrides the client's api_version


def test_v1_error_is_fatal_explained_and_redacted(env):
    env.write_text(f"GEMINI_API_KEY={FAKE_KEY}\n", encoding="utf-8")
    settings.reload()

    class ClientError(Exception):
        code = 400

    exc = ClientError(f"400 INVALID_ARGUMENT. Developer instruction is not enabled for api version v1. "
                      f"Use api version v1beta instead. key={FAKE_KEY}")
    assert analyse.classify_error(exc) == "fatal"
    msg = analyse.explain_fatal(exc)
    assert "v1beta" in msg and FAKE_KEY not in msg and "[REDACTED]" in msg


def test_verify_connection_without_key_reports_not_configured(env, monkeypatch):
    monkeypatch.setattr(analyse, "_client", None)
    monkeypatch.setattr(analyse, "_client_sig", None)
    settings.reload()
    res = analyse.verify_connection()
    assert res["ok"] is False and "GEMINI_API_KEY is not set" in res["detail"]
