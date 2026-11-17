# UI workspace — design and behaviour (2026-11-17 redesign)

The Streamlit front end is `app.py` (page config, app bar, routing) plus the `ui/` package. It only
collects inputs, calls `src.service` and renders the validated `Assessment`; no assessment logic
lives in the UI. This replaces the 2026-11-15 stepper design (three decorative step cards, HTML
"card" wrappers that did not actually contain their widgets, sample mode as the default).

## Modules

| Module | Responsibility |
|---|---|
| `app.py` | `set_page_config`, stylesheet, app bar (brand, navigation, status chips, Connection popover), top-level error guard |
| `ui/pages.py` | *New assessment* (default) and *Sample cases* pages; running view; error, conflict and "results ready" panels |
| `ui/photos.py` | uploader, managed photo list, local pre-check, thumbnails, remove/clear, quality summary |
| `ui/vehicle.py` | dependent make → model → year → variant selectors, manual entry, pricing coverage, pricing options |
| `ui/runner.py` | runs the service, shows real stages with measured durations, classifies errors, renders exports |
| `ui/results.py` | results header + downloads, evidence viewer (fragment), cost summary, Findings / Cost breakdown / Pricing evidence / Technical details tabs |
| `ui/connection.py` | Gemini key state (missing / not verified / verified / failed), Reload + Verify, cached pricing index |
| `ui/state.py` | per-mode workspaces, input signatures, stale-result invalidation, reset |
| `ui/html.py` | `esc()` (HTML), `md()` (Markdown), `code()` (code spans), chip and heading builders |
| `ui/style.py` | the small stylesheet the theme cannot express |
| `.streamlit/config.toml` | theme tokens: slate neutrals, one blue accent, semantic colours, system font stack, 16 px base, 8 px radius; `toolbarMode = "minimal"`; `showErrorDetails = "type"` |

## Visual system

- Surfaces: page `#F4F6F9`, white cards (keyed `st.container(border=True, key="card_*")`) with a
  `#E2E8F0` border and a subtle shadow. One accent (`#2563EB`). Severity colours match the overlay
  boxes in `src/overlay.py`: severe red, moderate orange, minor blue. Actions: replace red, repair
  blue, inspect amber.
- Typography: system UI font stack, 16 px body, nothing below 14 px except decorative glyphs.
- Icons: Streamlit Material Symbols on native widgets; the logo is a CSS data-URI SVG.
- CSS selectors are limited to the app's own `ai-*` classes, documented `st-key-*` classes of
  keyed containers, `role` attributes and a few `data-testid` hooks. No generated
  `st-emotion-cache-*` classes. The 3-up/2-up photo grid uses `:has()` as progressive enhancement
  (fixed 176 px tiles still wrap without it).
- Layout: max width 1240 px; two columns (7:5 inputs, 3:2 results) that stack below 640 px.

## Flow and state rules

1. **New assessment is the default.** Photos are added through the uploader into a managed list
   (`st.session_state.photos`); the uploader is reset after each add, so every thumbnail has a real
   **Remove photo N** button. At most 5 photos; extra files are reported, not silently dropped.
2. **Local pre-check (no network).** `src.intake.inspect_image_bytes` runs the pipeline's own
   decode/resize/hash, so tile states (Ready, Blurry, Similar view, Duplicate, Can't be used) and
   image IDs match what the analysis reports. The count chip shows `added · unique`.
3. **Vehicle.** Searchable selectboxes (type to filter); each change clears the dependent fields.
   Variant accepts a custom trim. *Enter vehicle manually* covers years/models outside the
   2022–2026 catalog. The coverage box shows the real record count from the pricing corpus and the
   synthetic label. Widget values use `persist_state="session"`, so they survive the results view.
4. **Analyze** is enabled only when there is ≥ 1 usable photo, make + model + year, a configured
   key, a loaded pricing index and no unresolved identity conflict; a checklist next to the
   button says what is missing.
5. **Running.** The click queues one run (`state.request_run`); the next script run consumes the
   queued inputs *before* starting (an interrupted run can never re-trigger inference) and shows the
   pipeline's own progress events with measured durations. Previously analysed photos come from
   the local vision cache (said explicitly; *Technical details* shows cache vs fresh).
6. **No stale results.** Each workspace stores the result with the signature of its inputs
   (photo hashes, vehicle, pricing scope, description / fixture). Any change discards the result,
   its downloads, errors and conflicts for other inputs. Unchanged inputs show *Results for these
   inputs are ready → View results*, and Analyze stays disabled — no repeated inference.
   Viewer, tab and download interactions never call the model (downloads use `on_click="ignore"`;
   the viewer is an `st.fragment`).
7. **Results (image-first).** Large photo with numbered regions (compact on-screen overlay; the PDF
   keeps the full-label overlays), Annotated/Original toggle, thumbnails, **Highlight component**,
   and the list of findings on the current photo. *Findings* → **Show on photo** links a component
   to its regions. Cost card: range, tax line if configured, inspection items kept separate,
   envelope, partial-subtotal or no-price warnings (unknown, not zero), Replace/Repair/Inspect
   counts, uncertainty reasons, warnings. The disclaimer, synthetic-pricing label and exterior-only
   limitation are always shown above the results; sample results are labelled
   *Sample fixture · not a live case*.
8. **Exports.** JSON and PDF are rendered once per assessment id from the same object; the header
   shows **Download PDF** (primary) and **Download JSON**, plus the result of
   `src.report.pdf_totals_match`.
9. **Errors.** `ui/runner.classify_error` maps failures to readable titles: photos unusable, key
   missing/rejected, quota/rate limit, network/timeout, analysis failure, unexpected. Messages are
   key-redacted; tracebacks go to the server log only. Retry re-queues the same inputs. A vehicle
   identity conflict stops before pricing and lists what the model saw per photo; it clears once
   the photo set changes.
10. **Sample cases** are secondary (top navigation), labelled *Offline demo · No Gemini calls*, and
    pre-fill the vehicle from the fixture (catalog spelling of the trim when it matches).
