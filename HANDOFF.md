# HANDOFF — AutoInspect (vehicle damage assessment)

Updated 2026-11-17 after the UI redesign. Evidence: [docs/validation-log.md](docs/validation-log.md)
(see *UI redesign*). UI design and state rules: [docs/ui-workspace.md](docs/ui-workspace.md).

## Launch

```powershell
cd "C:\Users\ravit\OneDrive\Desktop\PROMPT ENG\vehicle-damage-assessment"
.\.venv\Scripts\streamlit.exe run app.py
```

Open <http://localhost:8501>. The first analysis after a server start also loads the embedding
model (~15–20 s); later runs are quick.

## Where things are

- **Project root:** `C:\Users\ravit\OneDrive\Desktop\PROMPT ENG\vehicle-damage-assessment\` — its own
  Git repo (`origin` = `github.com/raviteja2028tech/AutoInspect`, branch `main`). The redesign is
  **uncommitted** on top of commit `fff69e7` (together with the earlier cleanup edits that were
  already uncommitted). The home-directory Git repo was not touched.
- **Virtual env:** `.venv` at the project root. **Secrets:** key only in the git-ignored `.env`
  (consider rotating it).

## What changed in this session (UI redesign)

1. `app.py` reduced to page config, app bar and routing; the UI moved into `ui/` (pages, photos,
   vehicle, runner, results, connection, state, style, html). `src/` logic is unchanged except:
   - `src/intake.py`: `inspect_image_bytes()` (in-memory pre-check sharing `load_image`'s exact
     processing via `_process()`), used for thumbnails and quality flags.
   - `src/overlay.py`: optional `compact=True` (ID-only labels, larger font) for the on-screen
     viewer; the default (used by the PDF) is unchanged.
2. Theme tokens in `.streamlit/config.toml` (slate neutrals, one blue accent, semantic colours,
   16 px system font, `toolbarMode = "minimal"`, `showErrorDetails = "type"`).
3. Experience: *New assessment* is the default (uploader, thumbnails with remove, unique count,
   quality flags, suggested shots); compact dependent searchable vehicle selectors with manual
   fallback and pricing coverage; requirement checklist next to **Analyze**; real stage progress
   with measured durations; image-first results (viewer with Annotated/Original, thumbnails,
   Highlight component, *Show on photo*), cost card with inspection/envelope/partial warnings,
   Replace/Repair/Inspect counts, uncertainty; tabs Findings / Cost breakdown / Pricing evidence /
   Technical details; prominent PDF/JSON downloads with the PDF totals check; *Sample cases* is
   secondary and labelled.
4. Correctness: per-mode workspaces keyed by an input signature (no stale results/downloads;
   unchanged inputs reuse the result; Analyze disabled), one queued run per click, readable error
   classes (intake, key, quota, network, analysis, unexpected) with Retry, identity-conflict panel,
   top-level render guard (no tracebacks in the page), all user/model text escaped.
5. Tests: `tests/test_app_ui.py` rewritten (11 AppTest tests, Gemini stubbed, real pipeline) and
   `tests/test_ui_helpers.py` added (17). Docs updated: README, architecture, demo script,
   ui-workspace, validation log, review-needed.

## Checks performed

- `python -m pytest -q` → **134 passed, 2 deselected**; `python -m pytest -m smoke` → 1 passed;
  `python scripts/smoke_check.py` → 4/4 PASS, JSON↔PDF totals parity.
- Browser (headless Chromium, 1440 px and 390 px): upload → analyze → review → PDF/JSON download,
  viewer controls, input change, identity conflict, Start over, sample mode, missing key, invalid
  key + Retry, unusable files, escaping, Verify key, keyboard focus, mobile overflow — 0 console
  errors. Downloaded PDF totals = JSON = on-screen card (₹46,500 – ₹91,050; inspection
  ₹4,600 – ₹30,900; envelope ₹51,100 – ₹1,21,950).

## Remaining issues / not verified

- No **fresh** Gemini analysis was run through the browser: every live browser run used photos
  already in `.cache/vision/` (to avoid spending quota). The invalid-key test did reach Google.
- Clicking navigation *during* an analysis interrupts it (Streamlit reruns); the page then says it
  was interrupted and nothing was saved. Results already fetched from Gemini stay cached.
- On phones the tab strip scrolls horizontally (Streamlit's native behaviour).
- PDF verified by extracted text, not by rendering pages to images.
- Not checked: screen-reader output, Safari/Firefox, macOS/Linux.
- Unchanged from before: synthetic pricing only, no labelled accuracy evaluation, no genuine
  3–5 photo same-vehicle case recorded.

## Next actions

1. Review `git status` / the diff, then commit on a branch (nothing was committed or pushed).
2. Run one genuine 3–5 photo same-vehicle case through the browser (fresh Gemini calls) and
   record it in `docs/validation-log.md`.
3. Rotate the Gemini key; add sourced pricing records (`knowledge/README.md`); build a small
   labelled evaluation (`eval/`).
4. Delete `PROMPT ENG\vision\` (old venv) when the new layout is accepted.
