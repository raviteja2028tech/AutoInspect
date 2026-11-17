# Troubleshooting

Start every investigation with the safe diagnostic (it never prints the key):

```powershell
python scripts/check_config.py            # what THIS process sees: key configured? from where?
python scripts/check_config.py --verify   # contact Google: key accepted? model available?
```

*Configured* only means a key string is visible to the process. *Verified* means Google accepted
it. The app header shows the same distinction (**key missing** / **key configured · not
verified** / **connection verified** / **connection check failed**).

## "GEMINI_API_KEY required" although the key "is set"

Causes found in this project, in order of likelihood:

| Cause | How to recognise it | Fix |
|---|---|---|
| Key typed into `.env.example` | `check_config.py` prints a HINT that `.env.example contains a value` | Move it to `.env` (same folder as `app.py`) and blank it in the template. **This was the actual state of this repo before the cleanup.** |
| `.env` in the wrong folder | HINT `Found …\.env, which is NOT read` | Only `<project root>/.env` is loaded (resolved from `src/settings.py`, not the current directory). Move the file. |
| Key set in another terminal | `check_config.py` in that terminal says configured, the app says missing | Environment variables are per process. Put the key in `.env`, or launch `streamlit run app.py` from the terminal where the key is set. |
| Stale Streamlit server | `check_config.py` reports something listening on 8501–8503 | A server keeps the environment it started with. Press **Reload configuration** (re-reads `.env`) or stop it (Ctrl+C) and start again. To find stray servers on Windows: `Get-CimInstance Win32_Process \| ? CommandLine -match streamlit \| select ProcessId,CommandLine`, then `Stop-Process -Id <id>`. |
| Placeholder value | status says `placeholder value` | Replace `your-api-key-here` with the real key. |

Precedence: a non-empty variable present when the process started > `.env` > defaults.
`.env` never overrides an explicit variable. `settings.reload()` (the app's **Reload
configuration** button) re-reads `.env` and refreshes values that came from it; the Gemini client
is rebuilt automatically when the key, API version or timeout changes.

## `400 INVALID_ARGUMENT: Developer instruction is not enabled for api version v1`

Cause: `google-genai` 3.x (installed: 3.3.0) defaults the Gemini Developer API to `v1`
(`GOOGLE_AI_API_DEFAULT_VERSION = 'v1'` in `google/genai/_api_client.py`). The analysis prompt is
sent as a `system_instruction`, which `v1` rejects.

Fix (implemented): `src/analyse.build_client()` always creates
`genai.Client(api_key=…, vertexai=False, http_options=HttpOptions(api_version="v1beta", timeout=…))`.
No request-level `http_options` override it, and the system instruction is kept.
`GEMINI_API_VERSION` accepts `v1beta` (default) or `v1alpha`; `v1` is rejected with a readable
configuration error. `GOOGLE_GENAI_API_VERSION` / `GOOGLE_GENAI_USE_VERTEXAI` in the environment are
ignored (and reported by `check_config.py`).

Verified on 2026-11-17: the same tiny request with a system instruction returns this exact 400 on
`v1` and succeeds on `v1beta` (`python scripts/check_config.py --generate`).

## Other errors

| Message | Meaning |
|---|---|
| `503 UNAVAILABLE … high demand` / `504 DEADLINE_EXCEEDED` / `429` | Transient; retried automatically (`GEMINI_MAX_RETRIES`). Re-run if it persists. |
| `Model '…' is not available to this key` | Set `GEMINI_MODEL` to a model listed by `python scripts/check_config.py --list-models`. |
| `Could not load embedding model …` | First run needs internet to download the embedding model; afterwards it is cached. Offline fallback (labelled `lexical_fallback`): `python -m src.kb.build_index --embedder lexical_fallback`. |
| `Pricing records changed since the index was built` | Expected after editing `knowledge/`; the app rebuilds automatically, or run `python -m src.kb.build_index`. |
| `The photos appear to show different vehicles` | The identity check found conflicting colour/body/make evidence. Remove the odd photo(s); hard conflicts cannot be overridden in the UI. |
| "No applicable price records" | The vehicle/year/component is outside the synthetic pricing scope (see `knowledge/README.md`). Cost is unknown, not zero. |
