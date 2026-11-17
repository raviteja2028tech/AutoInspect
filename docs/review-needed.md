# Items for human review

Nothing below was deleted. Decide and act when convenient.

## Outside the repository (in `PROMPT ENG/`)

| Path | What it is | Suggestion |
|---|---|---|
| `vision/vision/.venv` (+ `.pytest_cache`, `__pycache__`) | The OLD virtual environment from before the move. Venvs are not relocatable, so it was left in place; the new `.venv` at the project root has been verified. | Delete `PROMPT ENG/vision/` once you are happy (it holds a full PyTorch install). |
| `vision.zip` | Original upload of the early project (no secrets; contains the `data/` photos). | Keep as history or delete. |
| `backup_before_restructure_2026-11-17.zip` | Snapshot taken right before the cleanup (no `.venv`, caches, `.env` or photos; key removed). | Keep until the new layout is accepted. |
| `Project_Task_Distribution.pdf` | **Empty file (0 bytes).** Not project documentation. | Replace with the real document or delete. |

## Inside the repository

| Path | Question |
|---|---|
| `data/*.jpg` | Provenance/licence unknown; git-ignored. Do not publish them. |
| `samples/my_case.json`, `my_case_v2.json` | Derived from photos that appear to show different vehicles. Kept as fixtures; consider replacing with a genuine same-vehicle case. |
| `samples/sample_severe/minor/no_damage.json` | Origin unknown (likely hand-prepared). |
| `knowledge/indian_vehicles.json` | Says "verified" models/variants with official source URLs; these were not re-checked during the cleanup. |
| `eval/` | Tooling only; never run in this repo. Needs CarDD or another labelled set. |
| `.cache/vision/` | Earlier Gemini answers (no secrets). Safe to delete; analyses would be re-run (API cost). |
| `PHASE.md` | Original build brief, kept with an appended status section. |
| `docs/ui-workspace.md` | Rewritten on 2026-11-17 for the redesigned UI (the stepper-era notes were removed). |

## Security

The Gemini key had been written into `.env.example` (a template intended for Git). It was moved to
the git-ignored `.env`. It was never committed (the nested repo's only commit contains
`README.md`), but it sat in a shareable template file and in a OneDrive-synced folder.
**Consider rotating the key** at <https://aistudio.google.com/apikey> and updating `.env`.
