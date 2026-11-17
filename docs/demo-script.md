# Demo script (about 6 minutes)

Before the demo: `python scripts/check_config.py --verify` (key accepted, model available) and
`python scripts/smoke_check.py` (offline chain OK). Start with `streamlit run app.py`. The first
analysis after a server start also loads the embedding model (~15–20 s); run one sample case
beforehand to warm it up.

1. **Framing (30 s).** "AutoInspect turns 3–5 photos of one car into a preliminary, auditable
   repair estimate. It is decision support, not insurer approval, and the prices are synthetic."
   Point at the app-bar chips: Gemini key status and "57 synthetic demo prices".

2. **Live configuration (30 s).** Open **Connection** (top right): key source shown, value hidden,
   model and pinned `v1beta`. Press **Verify key** (lists models only) → chip turns to
   *Gemini verified*.

3. **Live case (2.5 min).** On **New assessment**, drop 3–5 photos of the same car (your own; none
   are shipped). Show the thumbnails, the unique-photo count and quality flags (blurry, duplicate,
   can't be used), and the remove buttons. Pick make → model → year (type to search) and point at
   the pricing-coverage box. Add a short description → **Analyze N photos**.
   - The progress card lists the real pipeline stages with measured durations.
   - Results: large photo with numbered regions, Annotated/Original toggle, thumbnails, and
     **Highlight component**. In *Findings*, press **Show on photo** on a part.
   - Cost card: range, inspection items kept separate, envelope, Replace/Repair/Inspect counts,
     uncertainty reasons. *Pricing evidence* cites record ids, similarity and match level.
   - **Download PDF** / **Download JSON**: the caption confirms the PDF totals match.
   - Optional guard demo: **Edit inputs**, add a photo of a different car → analysis stops with
     "These photos may show different vehicles" and lists what was seen per photo.
   - Optional: upload the same photo twice → flagged *Duplicate*, analysed once.

4. **Sample case (1.5 min).** **Sample cases** → *Multi-panel damage (legacy output)* (Hyundai i20
   2021, opens in manual entry because 2021 is outside the 2022–2026 catalog) → **Run sample
   assessment**. Point at the *Sample fixture · not a live case* label and the **Partial
   subtotal** warning (ambiguous mirror/wheel positions are unpriced: unknown, not zero).

5. **Close (30 s).** Limits: synthetic prices for a narrow scope, approximate boxes, uncalibrated
   scores, no measured accuracy yet. Next steps: sourced price records, a labelled evaluation set.
