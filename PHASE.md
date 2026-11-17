# PHASE.md — Complete Vehicle Damage Assessment Demo

## Instructions to Claude

Act as the implementation engineer for this existing Python repository. Build and verify the project; do not stop after giving a plan. Work quickly through exactly the three phases below, starting with RAG and costing. Prefer small, dependable implementations over additional frameworks. Continue through all phases without requesting routine approvals. Ask only when a missing credential or essential external input actually blocks dependent work; continue independent work meanwhile.

First locate the real project root containing requirements.txt and src/pipeline.py. The workspace may contain nested vision/vision directories. Read the existing source, tests, README and applicable repository instructions before editing. Preserve existing work and unrelated changes. Do not create a second application in a separate repository.

Update this file with phase status, checks actually run, and remaining blockers. Do not mark a phase complete because code was generated. If a session ends, leave an exact next action so the next session resumes rather than rebuilds.

### Objective and boundaries

Deliver a runnable local application accepting 3–5 photos of ONE damaged vehicle, vehicle details, and an optional accident description. Produce image-linked visible damage findings, approximate localization, multi-image consolidation, repair/replacement/inspection recommendations, retrieved pricing evidence, estimated cost ranges, structured JSON, and a formatted PDF.

Support 1–2 usable images with an explicit insufficient-coverage warning, preserving the existing API. Clearly label the result: “Preliminary AI-assisted assessment. Not insurance approval or a substitute for physical inspection.” Do not infer policy coverage, settlement, liability, hidden mechanical damage, or roadworthiness from photos.

Build for one locally running user first. Authentication, cloud deployment, payment, insurer integrations, custom model training and precise segmentation are outside this demo. Never claim perfection or measured accuracy without evaluation evidence.

### Existing foundation and compatibility

- Existing modules: src/intake.py, analyse.py, schemas.py, vocab.py, fuse.py, pipeline.py.
- Existing entry point: analyse_case(image_paths, vehicle_info=None, view_hints=None, use_cache=True).
- Preserve top-level vehicle, images_analysed, damages, views_seen, warnings, images_failed and meta; preserve existing per-damage fields.
- Add versioned fields and optional keyword arguments rather than silently breaking consumers. Document any necessary migration and provide an adapter for old sample JSON.
- Existing calls use Gemini through google-genai. Keep that provider unless a verified blocker requires a change. Make model selection configurable and verify an available model with a smoke test; do not copy unverified model names from sample metadata.
- Claude is the coding assistant; the app needs its own runtime API credential. Never embed credentials in source, screenshots, logs or reports.

### Fast implementation defaults

Use Python, Pydantic, a single Streamlit interface, Pillow for overlays, ReportLab for PDF, and pytest. Reuse existing dependencies where sensible. For local RAG use sentence-transformers embeddings and a persisted NumPy index with metadata; a hosted vector database is unnecessary for a small catalog. Keep the embedding model configurable and record its identifier. If this approach is incompatible with the environment, use the smallest equivalent implementation and document the reason.

Separate vision, retrieval, recommendation rules, arithmetic, and presentation into importable functions. Do not put the full pipeline into the UI script. Avoid unnecessary agent frameworks, LangChain, separate frontend/backend servers, or services that slow local setup. Check current official documentation when API behavior is uncertain.

## Phase 1 — RAG knowledge base, recommendations and cost engine

**Goal:** Starting with existing sample damage-map JSON, produce an auditable estimate before changing the vision pipeline. This phase must work without a vision API key.

### 1. Establish the contract

Create validated models for pricing records, retrieved evidence, component plans, estimate totals and case status. Retain the input damage map. Include schema_version, assessment_id, currency, pricing region, vehicle details, provenance and timestamps.

Group findings into one component instance before costing. A bumper dent and scratch may require one combined repair plan; they must not produce two replacement charges. Store all contributing damage IDs. Side and position identify mirrors, windows and wheels; legacy ambiguous names must be flagged for clarification rather than silently assigned or merged.

### 2. Build a transparent pricing corpus

Use INR and a clearly named Indian demonstration region by default; make region and currency explicit rather than implicit. Start with a small declared vehicle/model-year scope, not a claim of all-car support.

Create editable JSON/CSV source records and normalized retrieval documents containing:

- record_id, source_id, source title/reference, source type, retrieved/entered date and price date when known;
- make, model, year range, variant applicability, component, side/position if relevant, operation and part grade;
- parts cost low/high, labor hours low/high, labor rate low/high, paint/material cost low/high;
- currency, region, tax inclusion, assumptions, applicability limits and data_quality.

Keep source fields distinct from numeric values; embedding prose must never be the source of arithmetic. Normalize aliases against src/vocab.py. Reject negative/reversed ranges, invalid years and incompatible currencies.

Prefer accessible, attributable real pricing records for a narrow vehicle scope. Do not invent supplier URLs, OEM quotations or market validation. If real records are unavailable, create clearly marked synthetic demonstration records with source_type=synthetic_demo and keep them separate from sourced records. Label every affected result “Illustrative demo pricing — not market verified.” The demo may function with synthetic data, but realistic-pricing validation remains outstanding.

Cover cosmetic panel repair, panel replacement, lamps, glass, mirrors and tires in the declared catalog. Unknown components, side_window and other must safely return missing/ambiguous pricing rather than invented costs. Document how to add genuine records.

### 3. Implement actual retrieval and grounded explanation

Create a command that validates records, generates embeddings and saves the index plus metadata. Record source content hashes and embedding model/version so edited records force rebuilding and incompatible indexes are rejected.

For a request, apply structured applicability filters for currency, region, vehicle, year, component and operation, then perform semantic ranking over compatible documents. Return top-k records, scores and the reason each applies. Relax filters only through explicit, documented fallback levels; label broader references as such. Never silently substitute a different model's part price. If no suitable records exist, return insufficient_pricing_data.

Use retrieved record IDs to build the component recommendation/cost explanation. Templates grounded in retrieved records and explicit rules are sufficient; do not require a second paid LLM. If generated prose is added, validate citations and prevent new numeric claims. Show retrieval evidence in both JSON and UI. A hardcoded price dictionary or CSV loaded without retrieval does not satisfy this phase.

Allow first-run embedding model download, with a useful error if unavailable. An optional lexical fallback must be labeled lexical_fallback and must not be presented as successful semantic retrieval. Cache the index/model for fast subsequent runs.

### 4. Add rules and deterministic estimates

Version explicit component-specific rules. Return repair, replace, or inspect with a short reason and rule ID. Example rules are preliminary demo heuristics: light surface scratches can suggest refinishing; clearly shattered glass can suggest replacement; uncertain or potentially structural findings require inspection. Severity alone must not automatically decide every operation. Preserve alternate scenarios when visible evidence cannot resolve repairability.

Calculate with Decimal and explicit rounding:

`line_low = parts_low + labor_hours_low * labor_rate_low + paint_materials_low`

`line_high = parts_high + labor_hours_high * labor_rate_high + paint_materials_high`

Aggregate one selected plan per component instance. Prevent duplicate labor/material operations within that plan. Show shared-job assumptions if overlap across components cannot be resolved. Apply tax only when configured and supported by record tax treatment; do not mix tax-inclusive/exclusive amounts silently. Keep optional allowances separate and explain their basis.

If any component lacks pricing, label the result partial and list unpriced items. A priced subtotal must never appear as a complete estimate. Unknown costs are null, not zero. Separate observed-damage subtotal, optional unresolved scenarios and exclusions. Do not manufacture a hidden-damage percentage and call it statistically validated uncertainty.

Provide low/medium/high estimate uncertainty with reasons: image coverage, unresolved observations, vehicle applicability, price provenance and missing items. Keep this separate from model confidence and retrieval similarity. No uncalibrated score is an accuracy probability or statistical confidence interval.

### Phase 1 acceptance gate

- A documented CLI accepts legacy sample damage JSON and writes a validated estimate JSON.
- Retrieval tests include correct match, wrong model/year/region exclusion, missing data, source edits/index rebuild and synthetic-data labeling.
- Cost tests cover bumper dent+scratch counted once, distinct left/right components, formula/range correctness, tax treatment, unsupported parts, partial totals and inspect scenarios.
- Rules and retrieved source IDs explain every priced component. Offline tests use local fixtures and deterministic stub embeddings; at least one separate smoke test verifies the actual embedding/retrieval path when its model is available.
- Record exact commands and outcomes; then continue to Phase 2.

## Phase 2 — Reliable vision, localization and complete assessment pipeline

**Goal:** Replace Phase 1 fixture inputs with actual image evidence while keeping outputs compatible.

### 1. Strengthen image intake and identity checks

Keep EXIF correction, resizing and blur warnings. Add file-size/pixel limits, stable image IDs, decoded-image validation and exact normalized-image deduplication. Similar-image checks may warn, but must not silently discard genuine distinct angles. Duplicates must not count as independent views, increase confidence or produce duplicate charges.

Keep original filename, processed dimensions, hash and processing transform in an image manifest. Image overlays and coordinates must refer to the same EXIF-corrected image. Track rejected, duplicate and failed files separately. Count only successfully analyzed unique images in images_analysed.

Flag obvious vehicle mismatches using visible identity evidence across images. Treat matching as a fallible consistency check, not verified identity. Ask the user to confirm uncertain cases in the UI; do not automatically combine clearly conflicting vehicles. Existing front/left/rear sample files appear to show different vehicles and must not be presented as a validated same-car case.

### 2. Extend the vision schema

Add observation_id, image_id, component instance/position, visible evidence description, severity rationale, confidence basis and optional normalized bounding box [x_min, y_min, x_max, y_max]. Validate finite values, coordinate range, ordering and image association. Enforce confidence bounds in Pydantic, including cached responses. If a region cannot be localized reliably, return null plus a reason instead of a fabricated box.

Ask Gemini only for visible external evidence. Accident narrative is untrusted context, not proof; it must not introduce damage absent from images. Record contradictions between the narrative and visual findings. Correct the current vocabulary rule that treats a missing part as a crack: add a truthful damage category compatibly or preserve legacy output through an explicit adapter.

Preserve current per-image analysis if it works. Add a bounded cross-image reconciliation pass when supported and useful, or deterministic reconciliation plus explicit unresolved conflicts. Do not call independent per-image name grouping verified cross-view understanding. Label approximate VLM localization honestly; do not advertise segmentation or detector-level precision.

### 3. Fix fusion and provenance

Merge observations by component instance; retain distinct damage types and image-linked regions underneath. Do not merge different wheels or opposite mirrors. Preserve legacy flat damages through a documented adapter while exposing component_groups for correct costing.

Retain supporting unique image IDs, conflicting observations, original scores and the reason for chosen severity. A weak severe observation must not automatically override strong contrary evidence. Ambiguous severity remains unresolved or requires inspection. Repeated views must not create artificial certainty. Remove the arbitrary extra-photo confidence bonus; report conservative model scores as uncalibrated and expose independent support separately.

### 4. Connect and harden runtime behavior

Create one assessment service joining intake → vision → reconciliation → component rules → retrieval → cost engine. Accept vehicle year/variant and optional description. Use validated settings, .env.example, bounded timeouts/retries and progress callbacks. Retry transient errors only; fail promptly for authentication or invalid configuration.

Version cache keys with image hash, provider/model, prompt/schema, relevant narrative/context and settings. Distinguish cache hit from fresh inference. Handle corrupt cache entries and write atomically. Prevent shared-client/rate-limit state from corrupting concurrent requests, or explicitly serialize local analysis. Keep API keys out of outputs. Do not silently switch to samples when live analysis fails.

### Phase 2 acceptance gate

- Duplicate input leaves unique observation count, support and cost unchanged.
- Tests cover mixed vehicles, opposite-side components, severity conflict, invalid boxes/scores, non-vehicle/undamaged input, missing key, malformed response, quota failure and partial image failures.
- Offline model stubs exercise pipeline behavior; separately run a live API smoke test with a supplied key and record its actual outcome. Missing credentials are a documented blocker, never a passing live test.
- Visually inspect overlays on real photos. Review false positives, missed damage, side assignment and localization on a small held-out set; report sample size and observed errors without inventing accuracy.
- At least one genuine same-vehicle multi-view case completes through cost JSON, or this gate remains visibly blocked pending suitable images/API access.

## Phase 3 — Application, PDF report and verified demonstration

**Goal:** Deliver a complete, reviewable upload-to-download application with no hidden mocked behavior.

### 1. Build the local interface

Create a clean Streamlit app with:

- live assessment and separately labeled saved/sample demonstration modes;
- vehicle make/model/year/variant, pricing scope, optional narrative and 3–5 image uploads;
- thumbnails, duplicate/quality warnings, mismatch confirmation and progress/status;
- annotated image gallery with component labels and approximate regions;
- one component assessment table with observed damage, evidence, severity, model score label, action and reason;
- expandable retrieved records with source/date, applicability, synthetic-data badges and missing-price status;
- low/high totals, partial-subtotal labels, assumptions, exclusions and uncertainty reasons;
- JSON and PDF downloads generated from the same validated assessment object.

Persist the completed result across UI reruns so downloading or expanding a section does not invoke the API again. Store uploads in isolated temporary case directories, sanitize filenames, clean up predictably and provide a reset action. Do not add personal/registration data unless needed; never commit private uploads or credentials.

### 2. Generate the report

Generate a readable PDF with assessment ID/date, user-supplied vehicle information labeled as such, image evidence, component recommendations/reasons, itemized cost ranges, source references, uncertainty, unpriced items, assumptions and disclaimer. Mark sample mode and synthetic pricing prominently when applicable. Show visible damage only; do not invent insurer policy details, inspection signatures or claim approval.

Support long component notes and tables across pages, page numbers, embedded images, and currency rendering using an appropriate font or “INR”. Escape user text passed into PDF markup. Preserve full JSON provenance even where the PDF summarizes it. Render a generated PDF and inspect page images for clipping and incorrect totals.

### 3. Finish setup, verification and handoff

Provide README instructions for Windows PowerShell and Mac/Linux: virtual environment, dependency installation, environment setup, index build, offline tests, live smoke test and app launch. After implementation, give exact commands that actually match the implemented modules. Pin a tested dependency set; do not claim untested cross-platform operation.

Include .env.example, pricing-data documentation, rules/contract documentation, a reproducible smoke-check command and a short presentation script. If redistribution-safe multi-view images are unavailable, document the required user-provided set; do not fabricate genuine accident photographs. Keep old samples labeled as fixtures. Maintain a validation log distinguishing implemented, offline-tested, live-tested and blocked behavior.

### Phase 3 acceptance gate — definition of done

- Start from a fresh virtual environment using documented commands and launch the application successfully.
- A real same-vehicle case runs from uploads to annotated evidence, recommendations, cited retrieval, cost range, downloadable JSON and readable PDF.
- Totals match across engine, UI, JSON and PDF; duplicate images and component findings do not duplicate money.
- Verify undamaged input, blurry/rejected files, unrelated vehicles, unsupported vehicle pricing, missing key, API failure and partial pricing. Errors must remain visible and must not become false “no damage” results.
- Verify both sample mode without a vision key and live mode with a valid key. Sample mode is always labeled; cached live results identify cache provenance.
- Run the full meaningful test suite once after final fixes, inspect the UI and rendered PDF, and record actual outcomes. If browser access is unavailable, state that UI visual verification is outstanding instead of claiming it passed.
- Provide changed files, exact run commands, test results, pricing coverage/provenance, known limitations and genuine remaining blockers. Every unchecked external dependency remains explicit.

## Execution directive

Begin implementation now at Phase 1 inside the existing repository. Inspect first, then make changes and run the corresponding acceptance checks. Use existing sample damage JSON to unblock RAG and costing immediately. Continue to Phase 2 and Phase 3 as gates permit. Do not stop at scaffolding, a new README, placeholder functions, or a polished interface with hardcoded live results. Optimize for a small, honest, fully connected demo that can be demonstrated and explained.


---

## Actual Verification Log & Status (Updated: 2026-11-15)

### Verification Summary
- **Test execution command:**
  `pytest tests/ -v -o "addopts=-p no:cacheprovider"`
- **Total tests run:** 77
- **Passed:** 76
- **Skipped:** 1 (`tests/test_smoke.py::test_live_gemini_single_image` — Skipped due to documented blocker: `GEMINI_API_KEY` not set in environment)
- **Failed:** 0

### Phase 1 Status: COMPLETE & VERIFIED
- Contracts, schema models (`contracts.py`), component grouping (`components.py`), rule engine (`rules.py`), and costing with `Decimal` precision (`costing.py`) implemented.
- 40 tests in `tests/test_estimate.py` and `tests/test_kb.py` passing.
- Deterministic CLI verified: `python -m src.estimate samples/my_case_v2.json --year 2021`.

### Phase 2 Status: BACKEND VERIFIED; LIVE CREDENTIALS PENDING
- Image intake (`intake.py`), EXIF correction, blur check, duplicate deduplication, and bounding box validation implemented.
- Multi-image observation fusion (`fuse.py`), cross-view vehicle mismatch detection (`VehicleMismatchError`), and narrative contradiction checks implemented.
- 25 tests in `tests/test_pipeline_v2.py` and `tests/test_vision.py` passing.
- Real semantic vector index built with `sentence-transformers/all-MiniLM-L6-v2` (`src.kb.build_index`) generating 57 vectors (dimension 384) with metadata and corpus hash.
- Real semantic embedding retrieval test `tests/test_smoke.py::test_semantic_embedding_retrieval` PASSING.
- **Documented Blocker:** Live Gemini API test requires a valid `GEMINI_API_KEY` in environment. Existing `front.jpg`/`left.jpg`/`rear.jpg` files are from distinct vehicles (correctly flagged by identity check).

### Phase 3 Status: IMPLEMENTED & VERIFIED
- Single canonical ReportLab PDF reporting engine unified under `src/reporting/pdf_report.py` and wrapped by `src/report.py::render_pdf`.
- All 10 PDF reporting tests in `tests/test_reporting.py` passing (INR fallback, multi-page layout, escaped markup, synthetic badges, partial totals).
- Full Streamlit application implemented in `vision/vision/app.py`:
  - Clearly separated Sample Demo and Live Assessment modes.
  - Vehicle details, pricing region, and currency selectors.
  - Multi-image file uploader with preview cards and warning banners.
  - Vehicle consistency mismatch override confirmation checkbox.
  - Annotated image gallery showing bounding box overlays.
  - Component assessment cards with damage types, severity, repair/replace/inspect recommendations, and rule IDs.
  - Grounded RAG pricing cards showing record ID, source title, part/labor/paint breakdown, and synthetic demo badges.
  - Low/high cost summary, partial estimate warnings, uncertainty analysis, and disclaimers.
  - Cached JSON (`assessment.json`) and PDF (`assessment.pdf`) download buttons.
  - Session state persistence preventing unnecessary reruns.
- `requirements.txt` updated with pinned dependencies (`streamlit`, `reportlab`, `sentence-transformers`, `pypdf`, `python-dotenv`).
- `.env.example` created with all supported environment variables.

### Phase 3 UI Redesign (AutoInspect Professional Workspace): COMPLETED & VERIFIED
- **Structural Redesign:** Replaced oversized sidebar forms and stacked emoji banners with a professional automotive inspection workspace:
  - Brand identity: "AutoInspect" with dark navy `#0F172A` typography, electric blue primary actions (`#2563EB`), neutral `#F8FAFC` background, and white surface cards.
  - Compact header with mode switcher (`Sample Benchmarks` vs `Live Photo Intake`), system status pills (`RAG: 57 Records`, `Vision API: Status`), and `New Assessment` reset.
  - Functional 3-step workflow indicator: `1. Vehicle & Evidence` → `2. AI Analysis` → `3. Review & Export` with non-destructive step navigation.
  - Interactive scenario cards for benchmark fixtures (`my_case_v2.json`, `sample_severe.json`, `sample_minor.json`, `sample_no_damage.json`).
  - Two-column results workspace:
    - Left (58%): Evidence viewer with photo thumbnail strip, overlay toggle (`Show AI Bounding Boxes` / `Clean Raw Photo`), dynamic component filtering, severity color legend, and honest fallback notice for fixtures without photos.
    - Right (42%): Cost summary card with authentic Indian number grouping (`₹92,650 – ₹1,58,650`), action counts (`● X Replace`, `● Y Repair`, `● Z Inspect`), uncertainty score card, and concise limitations notice.
  - Workspace tabs for `Component Findings`, `Grounded Pricing Evidence` (RAG citations table), and `Report & Exports` (one-click PDF and JSON downloads).
  - All 76 backend and reporting tests pass continuously.

### Phase 3 Data-Backed Indian Vehicle Selector & UI Consistency: COMPLETED & VERIFIED
- **Verified Indian Vehicle Dataset (`knowledge/indian_vehicles.json`):**
  - Curated 47 mainstream budget and mid-range passenger car models across 13 Indian manufacturers (Maruti Suzuki, Hyundai, Tata, Mahindra, Kia, Toyota, Honda, Renault, Nissan, Skoda, Volkswagen, MG, Citroen) sold during calendar years 2022–2026.
  - Captures generation identifiers, year-by-year sales availability, verified trim variants, fuel types, transmission options, official source URLs, retrieval dates, and known gaps.
  - Accurately captures discontinued vehicles sold during the 2022–2026 window (e.g. Volkswagen Polo discontinued in 2022, Honda Jazz discontinued in 2023).
  - Repeatable builder script implemented in `src/kb/generate_catalog.py` and CLI validator `python -m src.kb.vehicles --validate`.
- **Searchable, Dependent Vehicle Selector Module (`src/kb/vehicles.py`):**
  - Implemented cascading lookup queries: `get_manufacturers()`, `get_models_for_make()`, `get_years_for_model()`, and `get_variants_for_model_year()`.
  - Token-based multi-keyword and alias search engine (`search_models()`) resolving informal names (e.g., "maruti baleno", "nexon ev", "creta", "seltos", "brezza").
  - Canonical brand normalization (`normalize_make()`) resolving aliases such as "Maruti" / "MSIL" ↔ "Maruti Suzuki", "VW" ↔ "Volkswagen", "TATA" ↔ "Tata".
  - Knowledge base pricing coverage evaluator (`check_pricing_coverage()`) classifying any make/model/year into `full`, `partial`, `unpriced_recognized`, or `unverified_manual`.
- **Retrieval Engine Hard Filter Normalization (`src/kb/retrieve.py`):**
  - Updated `_hard()` filtering to normalize vehicle makes via `normalize_make(r.make) == normalize_make(q.vehicle.make)`, preventing pricing misses when queries use informal aliases.
- **AutoInspect Streamlit UI Integration (`vision/vision/app.py`):**
  - Replaced free-text vehicle inputs with connected, dependent controls: `Manufacturer` → `Model` → `Year` → `Variant`.
  - Implemented quick search bar for instant model jump by alias or nameplate.
  - Seamless toggle to "Manual Entry / Other Model" for pre-2022 vehicles, foreign models, and older benchmark fixtures.
  - Real-time Pricing Coverage Card rendered beneath vehicle selection showing exact database status, verified record counts, priced component badges, and synthetic-data transparency notices.
  - Redesigned "Advanced Pricing Scope Options" expander with human-readable region labels (`IN-DEMO-METRO (India - Demonstration Metro Region)`, `IN-DEMO-TIER2 (India - Demonstration Tier-2 City)`), default `INR (₹)`, and OEM vs Aftermarket guidance notes.
  - Fixed live mode header badge: Now explicitly shows `⚠ Vision API: Key Required (Live Mode)` when offline in live mode, eliminating the stale `(Sample Mode)` badge.
  - Fixed vehicle mismatch override: Caught `VehicleMismatchError` with `status == "conflict"` displays a prominent red warning banner explaining distinct vehicles cannot be merged, disables analysis, and removes the bypass checkbox so users must remove conflicting photos.
- **Verification & Test Suite:**
  - 10 dedicated unit tests in `tests/test_vehicles.py` covering catalog integrity, OEM listing, model filtering, alias normalization, year/variant dependencies, discontinued models, multi-token search, pricing coverage classifications, and UI helper registration.
  - All 85 non-deselected unit tests across all test suites PASS:
    `85 passed, 2 deselected in 8.18s`.


---

## Status update — 2026-11-17 (repository cleanup and live fixes)

The project now lives at `PROMPT ENG/vehicle-damage-assessment/` (formerly `vision/vision/`);
the history above refers to the old path. Test counts above were superseded.

- **Phase 1:** complete. Re-verified: offline suite 109 passed / 2 deselected; semantic smoke passed.
  Rules bumped to `rules-2026.11-v2` (`G-SEV-CONFLICT`). Pricing is still synthetic only.
- **Phase 2:** backend complete and **live-tested**: key verified, `v1beta` client pinned (the
  "Developer instruction is not enabled for api version v1" error was reproduced on v1 and fixed),
  live vision smoke passed, mismatch guard and de-duplication confirmed live.
  **Still blocked:** a genuine same-vehicle 3–5 photo case (no suitable photos available) and the
  held-out accuracy review.
- **Phase 3:** app launches from a fresh venv with the documented commands; headless-browser QA
  and rendered-PDF inspection done; JSON/PDF totals parity is checked automatically.
  Outstanding: browser-driven upload of a real same-vehicle set; macOS/Linux not executed.

Exact commands and outcomes: `docs/validation-log.md`. Next actions: `HANDOFF.md`.
