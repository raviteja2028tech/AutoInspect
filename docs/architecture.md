# Architecture

One Python package (`src/`) for all logic, and a Streamlit front end (`app.py` + `ui/`) that only
collects inputs, calls `src.service` and renders the validated `Assessment`. No server, database or
agent framework. UI structure and state rules: [ui-workspace.md](ui-workspace.md).

```
photos ──► intake.py ──► analyse.py (Gemini, 1 call per unique image, cached) ──► fuse.py
           validate,       v1beta client, JSON schema,                           per (component,
           EXIF, resize,   retries for transient errors only,                    damage type);
           blur, sha256    atomic cache keyed by image+model+prompt+schema       identity + narrative
           de-duplicate                                                           checks
                                     pipeline.analyse_case()  ──► damage map (v1 keys + v2 extras)
                                                                       │
             components.py (group per component instance) ◄──────────┘
                    │
             rules.py  (repair / replace / inspect, rule id + version)
                    │
             kb/retrieve.py  hard filters → labelled fallback levels → semantic ranking
                    │          (kb/records.py corpus, kb/index.py NumPy index, kb/embedding.py)
             costing.py  Decimal line costs, totals, tax handling
                    │
             estimate.build_assessment()  ──► Assessment (contracts.py, pydantic, versioned)
                    │
             service.export_assessment()  ──► JSON text + PDF bytes (report.py → reporting/pdf_report.py)
```

## Key contracts (`src/contracts.py`)

- `Assessment` (`schema_version = assessment-1.0`): id, mode (`live` | `sample_fixture` |
  `legacy_json`), disclaimer, `pricing_label`, user-supplied `vehicle`, `pricing_scope`, the full
  `damage_map`, `observations`, `component_plans`, `totals`, `uncertainty`, assumptions,
  exclusions, warnings (pipeline + estimate), provenance (rules/vocab versions, embedding model,
  corpus hash, vision model/API version, cache provenance).
- `ComponentPlan`: one per component instance; contributing damage ids, action, operation, rule id,
  reason, retrieval evidence (record ids, scores, fallback level), selected cost, alternatives.
- `Totals.status`: `complete` (every finding priced, possibly as an inspection scenario range),
  `partial` (some items unpriced — the subtotal is not an estimate), `insufficient_pricing_data`,
  `no_damage`. Observed subtotal, unresolved-scenario range and envelope are kept separate.
- `Observation.severity_unresolved` (optional, default `False`): strong views disagree on severity
  by two levels → rule `G-SEV-CONFLICT` sends the part to inspection with priced scenarios
  (rules `rules-2026.11-v2`).

## Damage map (`src/pipeline.py`)

v1 keys are unchanged (`vehicle`, `images_analysed`, `damages[]`, `views_seen`, `warnings`,
`images_failed`, `meta`). v2 adds `schema_version`, image-linked `observations` with normalised
boxes, `component_groups`, `image_manifest`, `images_rejected`, `images_duplicate`,
`images_not_vehicle`, `conflicts`, `vehicle_consistency`, `narrative_check`,
`accident_description`. `meta` now also records `api_version`. Old maps are read by
`components.adapt_damage_map()`.

## Configuration (`src/settings.py`)

Single source of truth. Loads `<project root>/.env` without overriding explicit environment
variables; validates numbers and the API version with readable messages (`CONFIG_ERRORS`);
resolves relative paths from the project root; `reload()` re-reads `.env`; `api_key_status()` /
`describe()` / `diagnostics()` never expose the key. `src.analyse.refresh_settings()` applies a
reload to the vision module.

## Paths

| What | Where | In Git |
|---|---|---|
| Pricing records, sources, vehicle catalog | `knowledge/` | yes |
| Vector index (generated) | `.cache/kb-index/<embedder>/` | no |
| Earlier Gemini answers (cache) | `.cache/vision/` | no |
| CLI / smoke outputs | `outputs/` | no |
| Uploaded photos (UI) | OS temp dir `autoinspect_case_*`, deleted after each run | no |
| Your photos | `data/` | no |

## Safety properties

- Live mode never falls back to sample data; every failure is shown as an error.
- Duplicates (byte-identical after normalisation) are analysed and counted once.
- Unknown prices are `null` ("not priced"), never zero; partial totals are labelled.
- JSON and PDF are rendered from the same object, cached per `assessment_id` in the UI; the PDF
  only copies numbers, it never computes them.
- Narrative text is untrusted context: contradictions are reported, it never adds findings.
