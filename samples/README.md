# Sample damage maps (fixtures — NOT live results)

These JSON files are saved damage maps used by **Sample mode**, the cost-engine CLI and the tests.
They are not evidence about any real vehicle, and they are not validated benchmark cases.
Every assessment built from them is labelled `mode=sample_fixture` with a
"SAMPLE MODE … Not a real case" warning in the UI, JSON and PDF.

| File | Origin (as far as known) | Notes |
|---|---|---|
| `my_case.json` | Output of an early pipeline version (prompt v1) on the three local photos `data/front.jpg`, `data/left.jpg`, `data/rear.jpg`. | Legacy flat format. The current identity check flags those three photos as likely **different vehicles** (colour differs), so this is not a valid same-car case. |
| `my_case_v2.json` | Same photos, prompt v2. | Same caveat. Used as the default UI sample because it exercises many components. |
| `fusion_check.json` | `left.jpg` + `left_copy.jpg` (an exact duplicate). | Shows the old fusion behaviour on duplicate input and the coverage warning. |
| `sample_severe.json` | Unknown / hand-prepared; metadata says `gemini-2.5-flash`, prompt v1. | Treat as synthetic. |
| `sample_minor.json` | Unknown / hand-prepared. | Maruti Swift; most findings fall outside the priced scope → shows `insufficient_pricing_data`. |
| `sample_no_damage.json` | Unknown / hand-prepared. | Zero findings → `no_damage`, no charges. |

`meta.model` values inside these files (e.g. `gemini-3.8-flash`) are historical labels from the
files themselves and were **not** used to choose the runtime model. The runtime model is
`GEMINI_MODEL` (default `gemini-2.5-flash`), verified with `python scripts/check_config.py --verify`.

Legacy and v2 damage maps are both accepted by `src.components.adapt_damage_map()`.
