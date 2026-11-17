# IMPLEMENTATION.md — How AutoInspect works (plain-English guide)

Read this to explain the project to anyone: what it does, which tools it uses, how each part works,
and what its limits are. File names are given so you can open the code and point to it.

---

## 1. What the project is (one paragraph to say out loud)

**AutoInspect** is a vehicle damage assessment app. You upload 3–5 photos of one damaged car and
choose the car (make, model, year). The app sends each photo to **Google Gemini** (an AI vision
model), which lists visible damage (part, damage type, severity, approximate box on the photo). The
app merges the findings from all photos, applies **fixed repair rules** (repair / replace /
inspect), looks up prices from a **local pricing database** using **semantic search (RAG)**,
calculates a **cost range in rupees**, and produces a **PDF report and a JSON file**. It is a
*preliminary* estimate — not insurance approval — and the prices in the database are **synthetic
demo values**, not real market prices.

---

## 2. Tech stack (what we used and why)

| Tool / library | Used for |
|---|---|
| **Python 3.12** | Whole project |
| **Streamlit 1.67** | Web UI (`app.py` + `ui/` folder) |
| **Google Gemini API** (`google-genai`, model `gemini-2.5-flash`, API version `v1beta`) | Looks at each photo and returns damage as structured JSON |
| **Pydantic** | Strict data models (validates AI output and the final assessment) |
| **Pillow + OpenCV + NumPy** | Image loading, resizing, rotation fix, blur check, drawing boxes |
| **sentence-transformers** (`all-MiniLM-L6-v2`) + **PyTorch (CPU)** | Turns text into vectors for semantic price search |
| **NumPy vector index** | Stores the price-record vectors (no external database) |
| **ReportLab** | Generates the PDF report |
| **python-dotenv** | Reads the API key from `.env` |
| **pytest** | 134 automated tests |
| **pypdf** (dev) | Checks PDF totals match the JSON |

No server, no database, no agent framework. Everything runs locally except the Gemini call.

---

## 3. Big picture — the pipeline

```
Photos ─► 1. Intake ─► 2. Gemini vision ─► 3. Fusion ─► 4. Rules ─► 5. RAG price lookup ─► 6. Costing ─► 7. Report
         (check &      (one call per      (merge all   (repair /   (find matching price   (₹ ranges,   (PDF + JSON
          clean)        unique photo)      photos)      replace /   records, semantic       totals,      from the same
                                                         inspect)    search + filters)       uncertainty) object)
```

Entry points: `src/service.py` → `run_live_assessment()` (real photos) and `run_sample_assessment()`
(saved demo files). `export_assessment()` makes the JSON + PDF.

---

## 4. Each step in detail

### Step 1 — Intake (`src/intake.py`)
- Accepts JPG / PNG / WebP / BMP, max **5 photos**, max **20 MB** each, min **200 px** side.
- Fully decodes each file (catches corrupt files), fixes phone rotation (EXIF), converts to RGB,
  shrinks to max **1280 px**, saves as JPEG.
- **Blur check**: Laplacian variance (OpenCV); below 60 → "looks blurry" warning.
- **Image ID** = `IMG-` + first 10 chars of the SHA-256 hash of the processed image.
- **Exact duplicates** are removed (counted once). **Near-duplicates** (perceptual hash, dHash
  distance ≤ 4) give a warning but are kept.
- Safety: decompression-bomb guard (50 MP), safe file names for uploads.

### Step 2 — Gemini vision (`src/analyse.py`, `src/schemas.py`)
- One Gemini call **per unique photo**, with a detailed **system prompt** (fixed list of allowed
  component names, damage types, severities; "left/right = the car's own left/right"; "never
  invent damage"; return a box `[ymin, xmin, ymax, xmax]` on a 0–1000 grid or null).
- Output is forced into a **JSON schema** (`ImageResult`): view (front/rear/left/right…),
  damages list (component, damage type, severity, location, confidence 0–1, evidence text, box),
  `is_vehicle`, vehicle identity (colour, body type, make guess), notes.
- **Temperature 0** (as deterministic as possible).
- **Cache**: every result is saved in `.cache/vision/` keyed by image hash + model + prompt version
  + schema version → the same photo is never sent to Gemini twice.
- **Retries** only for temporary errors (429 quota, 5xx, timeouts, bad JSON). Key/config errors
  stop immediately (`FatalAnalysisError`) with a readable explanation.
- The API key is **redacted** from every error message. Client is pinned to `api_version=v1beta`
  (the newer SDK defaults to `v1`, which rejects system instructions).

### Step 3 — Fusion across photos (`src/fuse.py`, `src/pipeline.py`)
- Merges the same damage seen in several photos into one **observation** (e.g. `O3`), keeping which
  photos support it and its box on each photo.
- If strong views **disagree on severity by two levels** → marked `severity_unresolved` (later sent
  to inspection).
- **Same-vehicle check**: compares colour / body type / make guessed in each photo. If they differ →
  **stops** with "photos may show different vehicles" (fallible check, clearly labelled).
- **Narrative check**: compares the optional accident description with the findings and reports
  contradictions (the description never adds damage).
- Coverage warning if fewer than 3 usable photos.
- Output: the **damage map** (v1 keys kept for compatibility + v2 extras).

### Step 4 — Repair rules (`src/components.py`, `src/rules.py`)
- Findings are grouped **per component** (e.g. all damage on "left front door").
- Versioned rules (`rules-2026.11-v2`) decide the action, each with a **rule id**:
  - Part-type rules: bumpers `PP-*` (plastic: dent/crack/missing), body panels `PB-*` (dent without
    tear → repair, severe deformation → replace), scratches `*-SCR-1/2` (refinish / filler repair),
    lamps `L-1/L-2` (broken → replace), mirrors `M-1…M-3`, wheels/tyres `W-1…W-3`
    (destroyed tyre → replace, flat → inspect, rim → inspect).
  - Guard rules: `G-SEV-CONFLICT` (photos disagree → inspect), `G-UNCERTAIN` (weak evidence →
    inspect), `G-AMB` (ambiguous part like "mirror" without side → not priced, ask to clarify),
    `G-OTHER` (part outside the catalog → not priced), `G-MISMATCH`.
- "Inspect" items keep **alternative scenarios** (e.g. refinish / repair / replace) with prices.

### Step 5 — Price lookup with RAG (`src/kb/`)
- **Knowledge base**: `knowledge/pricing_records_demo.csv` — **57 records**, all
  `synthetic_demo` (Hyundai i20 + 2 Maruti Swift records), plus `sources.json`.
- Each record: make, model, year range, variant, component, operation, part grade, parts cost
  low/high, labour hours low/high, labour rate low/high, paint/materials low/high, INR, region.
- **Index**: each record is turned into text → embedded with MiniLM → stored as a NumPy matrix in
  `.cache/kb-index/` (rebuilt automatically when the CSV changes).
- **Retrieval** (`retrieve.py`): first **hard filters** (make, model, component, operation, region,
  currency), then **labelled fallback levels**:
  - `L0_exact` (year + variant + preferred grade match)
  - `L1_grade_relaxed` (other part grade)
  - `L2_year_unverified` (no year given)
  - `L3_broader_reference` (different years — only if explicitly allowed)
  - then ranks the survivors by **cosine similarity** (top 3). If the model can't load, it falls
    back to keyword (lexical) ranking and says so.
- No match → **"insufficient pricing data"** — the cost is shown as *unknown, not zero*.
- **Vehicle catalog** (`knowledge/indian_vehicles.json`, `src/kb/vehicles.py`): 47 models from 13
  Indian manufacturers (2022–2026) with years and variants — used for the dropdowns and the
  "pricing coverage" check.

### Step 6 — Costing (`src/costing.py`, `src/estimate.py`)
- Money uses Python **Decimal** (no float rounding errors).
- Per line: `low = parts_low + labour_hours_low × rate_low + paint_low` (same for high).
- **Totals**:
  - *Observed subtotal* = sum of priced repairs/replacements.
  - *Inspection items* = separate range (cheapest → most expensive scenario).
  - *Envelope* = observed + inspection items.
  - Optional GST if `GST_RATE` is set.
  - Status: `complete`, `partial` (some items unpriced → "subtotal is NOT complete"),
    `insufficient_pricing_data`, `no_damage`.
- **Uncertainty**: points for risk factors (few photos, identity doubt, contradictions, inspection
  items, missing prices, weak scores, inexact price match, synthetic prices) → low / medium /
  high. Clearly labelled as a heuristic, **not** a statistical accuracy.
- Result = one validated **`Assessment`** object (`src/contracts.py`) with id `VDA-YYYYMMDD-xxxx`.

### Step 7 — Report (`src/report.py`, `src/reporting/pdf_report.py`)
- **JSON** = the Assessment object dumped. **PDF** = ReportLab report from the *same* object
  (vehicle, findings, rules, costs, evidence citations, warnings, disclaimers, annotated photos).
- `pdf_totals_match()` reads the PDF back and confirms totals match the JSON.
- Overlays (`src/overlay.py`): coloured boxes on the processed photo — red severe, orange moderate,
  blue minor — labelled "approximate regions (AI), not measurements".

---

## 5. The web app (Streamlit UI)

`app.py` = page setup + top bar + navigation. `ui/` folder = all screens:

| File | What it does |
|---|---|
| `ui/pages.py` | **New assessment** page (default) and **Sample cases** page, progress view, error panels |
| `ui/photos.py` | Upload, thumbnails, remove buttons, unique count, quality flags (local check, no AI) |
| `ui/vehicle.py` | Make → Model → Year → Variant searchable dropdowns, manual entry, pricing coverage |
| `ui/runner.py` | Runs the pipeline, shows **real** stages with timings, turns errors into readable messages |
| `ui/results.py` | Results: big photo viewer, cost card, tabs (Findings, Cost breakdown, Pricing evidence, Technical details), downloads |
| `ui/connection.py` | Gemini key status (missing / not verified / verified / failed), Reload + Verify |
| `ui/state.py` | Session memory; **input signature** so old results are discarded when inputs change |
| `ui/html.py`, `ui/style.py` | Escaping of all user/AI text (security) and styling |
| `.streamlit/config.toml` | Theme: colours, font, sizes |

User flow: upload photos → pick vehicle → **Analyze** → see progress → results (photo with numbered
boxes, cost range, counts, uncertainty) → download PDF / JSON. **Sample cases** = 4 saved damage
maps (`samples/`) that run offline without a key (labelled "not a live case").

Safety in the UI: no stale results, no repeated AI calls on clicks, key never shown, no tracebacks,
all text escaped.

---

## 6. Configuration (`src/settings.py`, `.env`)

- Put `GEMINI_API_KEY=...` in `.env` (git-ignored). `.env.example` is only a template.
- Other settings: `GEMINI_MODEL`, `GEMINI_API_VERSION` (v1beta), `GEMINI_TIMEOUT_S`,
  `GEMINI_MAX_RETRIES`, `GST_RATE`, `EMBEDDING_MODEL`, `RETRIEVAL_TOP_K`.
- Check without showing the key: `python scripts/check_config.py --verify`.

---

## 7. Folder map

```
app.py              Streamlit entry      ui/          screens
src/                all logic            knowledge/   price records + vehicle catalog
samples/            demo damage maps     tests/       134 tests
scripts/            check_config, assess (CLI), smoke_check
eval/               accuracy scripts (need labelled data)   docs/   extra docs
.cache/             vision cache + price index (generated)   outputs/  CLI results
```

---

## 8. How to run and test

```powershell
.\.venv\Scripts\streamlit.exe run app.py          # the app → http://localhost:8501
python -m pytest                                  # 134 offline tests (AI is stubbed)
python scripts/smoke_check.py                      # all samples → JSON + PDF, totals match
python scripts/assess.py a.jpg b.jpg c.jpg --make Hyundai --model i20 --year 2021   # CLI
```

---

## 9. Honest limits (say these if asked)

1. **Prices are synthetic** demo values for mainly Hyundai i20 — not real quotes.
2. **No measured accuracy** — no labelled dataset evaluation has been done yet.
3. Boxes are **approximate** AI localisation, not segmentation; confidence scores are **not
   calibrated** probabilities.
4. Only **exterior visible** damage; no internal/mechanical/structural assessment.
5. The same-vehicle check is based on colour/body/make guesses — it can be wrong.
6. Depends on Gemini (needs key, internet, quota); results are cached to save calls.

---

## 10. Likely questions — quick answers

- **Where is the AI?** Only in step 2 (Gemini reads photos). Rules, prices and maths are
  deterministic Python, so every rupee can be traced to a record id.
- **What is RAG here?** Retrieval-Augmented: we *retrieve* matching price records (semantic search
  + filters) and compute cost from their numbers — the AI never invents prices.
- **Why rules instead of AI for repair/replace?** Repeatable, explainable (rule id on every line),
  versioned.
- **How do you avoid hallucination?** Strict JSON schema, fixed vocabulary, "never invent damage"
  prompt, multi-photo fusion, unpriced = unknown (not zero), guard rules send doubtful items to
  inspection.
- **Why is the PDF trustworthy?** JSON and PDF come from one validated object, and a check confirms
  the totals match.
