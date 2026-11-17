# data/ — local, private photos (never committed)

Everything in this folder except this README and `.gitkeep` is ignored by Git. Put your own
test photos here; do not commit customer or personal images.

Present locally (not in Git, licence/provenance unknown — do not redistribute):

- `front.jpg`, `left.jpg`, `rear.jpg` — the identity check reports these as likely **different
  vehicles** (rear is white, the others grey). Useful for testing the mismatch guard, not as a
  same-vehicle case.
- `left_copy.jpg` — byte-identical copy of `left.jpg`, used to test duplicate handling.

A genuine demo needs **3–5 photos of the same vehicle** from different sides (front, both sides,
rear, a close-up). Upload them in the app's Live mode, or run:

```
python scripts/assess.py data/<a>.jpg data/<b>.jpg data/<c>.jpg --make Hyundai --model i20 --year 2021
```
