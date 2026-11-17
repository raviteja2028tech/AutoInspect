# Validation log

Last updated **2026-11-17** (repository cleanup). Environment: Windows 11, Python 3.12.10, fresh
`.venv` created at the project root with the documented commands (CPU torch 2.15.0,
google-genai 3.3.0, streamlit 1.67.0, sentence-transformers 6.3.0; `pip check` clean).
Commands run from the project root.

## Results

| Check | Command | Result |
|---|---|---|
| Baseline before cleanup (old location, old venv) | `python -m pytest -q` | 83 passed, 2 deselected |
| Offline suite (after cleanup) | `python -m pytest -q` | 109 passed, 2 deselected |
| Offline suite (after UI redesign) | `python -m pytest -q` | **134 passed, 2 deselected** |
| Real embedding model | `python -m pytest -m smoke -q` | 1 passed |
| Offline end-to-end, semantic | `python scripts/smoke_check.py` | 4/4 fixtures PASS, JSON↔PDF totals match |
| Offline end-to-end, lexical fallback | `python scripts/smoke_check.py --lexical` | 4/4 PASS |
| Vehicle catalog | `python -m src.kb.vehicles --validate` | VALID: 47 models, 13 manufacturers |
| Pricing corpus | `python -m src.kb.build_index --check` | 57 records, 1 source, all `synthetic_demo` |
| Config diagnostic (offline) | `python scripts/check_config.py` | key configured via `.env` file, value hidden |
| **Live**: key + model | `python scripts/check_config.py --verify` | VERIFIED — `gemini-2.5-flash` available, api `v1beta` |
| **Live**: system instruction on v1beta | `python scripts/check_config.py --generate` | 1st try: transient `504 DEADLINE_EXCEEDED`; retry: VERIFIED |
| **Live**: control on v1 | one request with `api_version="v1"` | `400 INVALID_ARGUMENT … Developer instruction is not enabled for api version v1` (original error reproduced) |
| **Live**: vision smoke | `RUN_LIVE=1 python -m pytest -m live` | 1 passed (fresh call on `data/front.jpg`, boxes returned) |
| **Live**: mismatch guard | `python scripts/assess.py data/front.jpg data/left.jpg data/rear.jpg data/left_copy.jpg …` | 4 files → 3 unique; one `503` retried automatically; stopped: different vehicles (colour grey/grey/white) |
| **Live** (from cache): full chain | `python scripts/assess.py data/front.jpg data/left.jpg --make Hyundai --model i20 --year 2021 …` | `mode=live`, semantic retrieval, 8 components, `left_front_door` → inspect (`G-SEV-CONFLICT`), observed ₹46,500–91,050, JSON↔PDF totals match, 2 overlays embedded |
| App launch | `streamlit run app.py` | `/_stcore/health` = ok |
| Browser QA (headless Chromium) | sample run, report tab, live status, Verify button | 0 console errors, 0 failed requests; UI cost card = JSON (₹92,650 – ₹1,58,650); badge "key configured · not verified" → "connection verified"; key text not in page |
| PDF visual inspection | rendered pages of the live case | no clipping; synthetic banner; totals/inspection/envelope consistent with JSON; overlays readable |

## Status by capability

| Capability | Implemented | Offline-tested | Live-tested | Notes |
|---|---|---|---|---|
| Intake: validation, EXIF, limits, blur, de-dup | yes | yes | yes | duplicates counted once |
| Gemini vision with schema, cache, retries | yes | yes (stubs) | yes | `v1beta` pinned |
| Key/config diagnostics, reload | yes | yes | yes | configured ≠ verified |
| Multi-image fusion, identity & narrative checks | yes | yes | yes (mismatch) | identity check is fallible |
| Rules (`rules-2026.11-v2`) | yes | yes | yes | |
| Semantic retrieval + labelled fallbacks | yes | yes (stub + real model) | n/a | |
| Cost engine, partial/unresolved totals | yes | yes | yes | |
| JSON + PDF from one object | yes | yes | yes | parity checked automatically |
| Streamlit UI | yes | yes (AppTest, stubbed Gemini) | browser QA | browser upload → analyze → export automated with cached vision results |

## Blocked / outstanding

- **Genuine same-vehicle 3–5 photo case** — no redistributable photo set exists; the local photos
  show different vehicles. The full live chain has run on 2 consistent photos (cache) only.
- **Real pricing** — only synthetic records; no sourced price has been verified.
- **Accuracy** — no labelled evaluation has been run (`eval/` needs a dataset such as CarDD).
- **macOS/Linux** — commands documented, not executed.
- **Browser upload** — now automated (see *UI redesign* below), but only with photos already in the
  vision cache; a fresh Gemini analysis has not been run through the browser.

## UI redesign (2026-11-17)

Server: `streamlit run app.py --server.port 8765` (plus two throw-away instances that ignore `.env`:
one with no key, one with a deliberately invalid key). Browser: headless Chromium (patchright),
driven by scripts; screenshots reviewed at 1440 px and 390 px. Photos `data/front.jpg`,
`data/left.jpg`, `data/rear.jpg`, `data/left_copy.jpg` were all in the vision cache, so the live
runs below made **no** Gemini generation calls.

| Check | Result |
|---|---|
| Upload → vehicle → Analyze → results (front + left + duplicate) | results in 2.3 s (cache); 2 overlays; duplicate flagged and analysed once |
| UI cost card vs downloaded JSON vs downloaded PDF (pypdf text) | ₹46,500 – ₹91,050 observed, ₹4,600 – ₹30,900 inspection, ₹51,100 – ₹1,21,950 envelope: identical in all three; synthetic label + disclaimer in PDF |
| Downloads | `VDA-….pdf` / `VDA-….json` saved; results stay on screen (no rerun) |
| Viewer | Annotated/Original toggle disables Highlight; Photo 2 thumbnail; *Show on photo* focuses the component |
| No repeated inference | Edit inputs → "results ready" + Analyze disabled → View results returns the same assessment id |
| Stale results | changing the model year discards result and downloads; Analyze re-enabled |
| Identity guard (front + left + rear) | stops before pricing; per-photo cues (grey, grey, white); Analyze disabled until the white car's photo is removed |
| Start over / navigation | clears photos and vehicle; Sample cases ↔ New assessment keep separate state |
| Sample case *Minor parking scratches* | Maruti Suzuki Swift 2022 VXi (catalog spelling); "No finding could be priced"; PDF totals check = match |
| Missing key (no `.env`) | chip "Gemini key missing", banner with `.env` path, Analyze disabled with reason, Verify disabled, no "connected" wording |
| Invalid key + uncached synthetic image | "Gemini rejected the request" panel, chip "Gemini check failed", Retry makes a second real attempt, changing an input clears the error, no traceback in page |
| Unusable uploads | 150×100 image and a corrupt file shown as *Can't be used* with the intake reason |
| Escaping | HTML typed into Make and an HTML-like file name render as text |
| Verify key (models list only) | chip "Gemini key not verified" → "Gemini verified" |
| Mobile 390 px | no horizontal overflow except Streamlit's own scrollable tab strip; no text below 14 px |
| Keyboard | tab focus shows a 2 px blue outline; all actions are native buttons/selectors |
| Console / network | 0 console errors, 0 failed requests in every run |

Not verified in this session: a fresh (uncached) Gemini analysis of real vehicle photos through
the browser, macOS/Linux browsers, screen-reader output, PDF page rendering as images (PDF was
checked by extracted text only).

