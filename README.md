# AutoInspect — AI-assisted vehicle damage assessment (demo)

Upload **3–5 photos of the same vehicle**, enter the vehicle details and an optional accident
description, and get:

image validation & de-duplication → Gemini vision findings with approximate boxes →
multi-image reconciliation → repair / replace / inspect recommendations (versioned rules) →
semantic retrieval of pricing records → deterministic cost ranges with uncertainty →
a Streamlit review workspace → matching **JSON and PDF** downloads.

> **Preliminary AI-assisted assessment. Not insurance approval or a substitute for physical
> inspection.** All prices in this repository are **synthetic demonstration data** ("Illustrative
> demo pricing — not market verified"). Hidden, mechanical and structural damage is not assessed.

Status, test results and known limitations: [docs/validation-log.md](docs/validation-log.md).

---

## Quick start

Requires **Python 3.12**. All commands run from the project root (the folder with `app.py`).

**Windows (PowerShell)**

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements-dev.txt     # or requirements.txt for runtime only
Copy-Item .env.example .env                        # then edit .env and set GEMINI_API_KEY
python scripts/check_config.py --verify            # key configured? accepted by Google?
streamlit run app.py
```

**macOS / Linux (bash)** — same steps; so far tested on Windows only.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu   # avoids CUDA builds on Linux
python -m pip install -r requirements-dev.txt
cp .env.example .env                               # then edit .env
python scripts/check_config.py --verify
streamlit run app.py
```

Open <http://localhost:8501>. The app opens on **New assessment** (upload photos → confirm the
vehicle → Analyze → review → download PDF/JSON), which needs a Gemini key. **Sample cases** (top
navigation) works offline without any key and is labelled as saved fixtures, not live results.

**First run:** the embedding model `sentence-transformers/all-MiniLM-L6-v2` (~90 MB) is downloaded
once from Hugging Face into your user cache (`~/.cache/huggingface`, or `HF_HOME`) and reused
afterwards, offline. The pricing index is then built into `.cache/kb-index/` and rebuilt
automatically whenever `knowledge/` records change.

## Configuring the Gemini key

1. Get a free key at <https://aistudio.google.com/apikey>.
2. Put it in **`<project root>/.env`** as `GEMINI_API_KEY=...` (`.env.example` is only a template
   and is never read; `.env` is git-ignored).
3. Check without revealing it: `python scripts/check_config.py` (configured?) and
   `python scripts/check_config.py --verify` (accepted by Google? model available?).

Precedence: a variable set in the **same terminal that launches the app** wins over `.env`;
`.env` never overrides it. A running Streamlit server keeps the environment it started with —
after changing `.env`, open **Connection** (top right of the app) and press **Reload
configuration**, or restart the server; after changing a terminal variable you must restart. The
header chip distinguishes **Gemini key missing**, **Gemini key not verified** (configured, not yet
checked), **Gemini verified** (after **Verify key**, which only lists models) and **Gemini check
failed**. Details and fixes for known errors: [docs/troubleshooting.md](docs/troubleshooting.md).

The client always uses the Gemini Developer API with **`api_version=v1beta`** (`GEMINI_API_VERSION`).
`google-genai` 3.x defaults to `v1`, which rejects the system instruction this app sends
("Developer instruction is not enabled for api version v1").

## Everyday commands

| Task | Command |
|---|---|
| Run the app | `streamlit run app.py` |
| Configuration check (offline, never prints the key) | `python scripts/check_config.py` |
| Verify key + model with Google (no generation) | `python scripts/check_config.py --verify` |
| Prove system instructions work (1 tiny request) | `python scripts/check_config.py --generate` |
| Offline tests | `python -m pytest` |
| Real embedding-model smoke test | `python -m pytest -m smoke` |
| Live Gemini smoke test (1 call; PowerShell) | `$env:RUN_LIVE="1"; python -m pytest -m live` |
| Offline end-to-end check (all fixtures → JSON + PDF) | `python scripts/smoke_check.py` |
| Assess your photos from the CLI | `python scripts/assess.py a.jpg b.jpg c.jpg --make Hyundai --model i20 --year 2021` |
| Cost a saved damage map | `python -m src.estimate samples/my_case_v2.json --year 2021 --out outputs/case.json` |
| Validate / rebuild the pricing index | `python -m src.kb.build_index --check` / `python -m src.kb.build_index` |
| Validate the vehicle catalog | `python -m src.kb.vehicles --validate` |

CLI outputs go to `outputs/` (git-ignored).

## Repository layout

```
vehicle-damage-assessment/
  app.py                    Streamlit entry point: page config, app bar, routing
  ui/                       presentation only: pages, photos, vehicle, runner, results, connection,
                            state, style, html (escaping); calls src.service, never re-implements logic
  .streamlit/config.toml    theme tokens (colours, font, radius) + upload limit + toolbar mode
  src/
    settings.py             configuration: project .env, precedence, validation, key diagnostics
    intake.py               image validation, EXIF, resize, blur, hashing, de-duplication
    analyse.py              Gemini call per image (v1beta client, retries, cache, redaction)
    fuse.py                 multi-image reconciliation, identity + narrative checks
    pipeline.py             analyse_case(): intake -> vision -> fusion (public entry point)
    components.py rules.py  component grouping, versioned repair/replace/inspect rules
    kb/                     pricing corpus, embeddings, persisted index, retrieval, vehicle catalog
    costing.py estimate.py  Decimal arithmetic, totals, uncertainty, build_assessment()
    service.py              run_live_assessment / run_sample_assessment / export_assessment
    report.py               render_pdf() adapter  ->  reporting/pdf_report.py (the one PDF engine)
    overlay.py              approximate boxes drawn on the processed image
  knowledge/                editable pricing records + sources + vehicle catalog (see its README)
  samples/                  saved damage-map fixtures, clearly NOT live results (see its README)
  scripts/                  check_config.py, assess.py, smoke_check.py
  tests/                    offline tests (+ smoke / live markers)
  eval/                     optional accuracy-evaluation scripts (need a labelled dataset)
  docs/                     architecture, troubleshooting, validation log, demo script
  data/                     your local photos (git-ignored)
  .cache/                   generated: kb-index/ and vision/ (git-ignored, rebuildable)
```

Public interfaces kept compatible: `src.pipeline.analyse_case(image_paths, vehicle_info=None,
view_hints=None, use_cache=True, ...)`, `src.service.run_live_assessment / run_sample_assessment`,
`src.report.render_pdf`, `src.reporting.generate_pdf_report`. Architecture and contracts:
[docs/architecture.md](docs/architecture.md). Pricing data: [knowledge/README.md](knowledge/README.md).

## Limitations (honest summary)

- Pricing is synthetic and covers Hyundai i20 (2020–2024) fully, plus a few Swift / older-i20 rows.
  Other vehicles return "no applicable price records" (unknown, never zero).
- Boxes are approximate vision-language-model localisation, not segmentation or measurement.
- Model scores are uncalibrated; the uncertainty level is a documented heuristic, not a statistic.
- No measured accuracy is claimed. `eval/` contains tooling but no evaluation has been run.
- The same-vehicle check is a fallible consistency check, not identity verification.
- A genuine 3–5 photo same-vehicle case has not been run yet (no such photo set is in the repo).
