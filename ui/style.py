"""Stylesheet for the parts the Streamlit theme (.streamlit/config.toml) cannot express.

Selectors are limited to (a) this app's own classes (``ai-*``) on markup it renders,
(b) the documented ``st-key-<key>`` classes of keyed containers and (c) a few stable
``data-testid`` hooks. No generated ``st-emotion-cache-*`` classes are targeted.
"""
from __future__ import annotations

import streamlit as st

CSS = """
<style>
:root {
  --ai-surface: #FFFFFF;
  --ai-border: #E2E8F0;
  --ai-border-strong: #CBD5E1;
  --ai-text: #0F172A;
  --ai-text-2: #334155;
  --ai-muted: #475569;
  --ai-subtle: #64748B;
  --ai-accent: #2563EB;
  --ai-accent-ink: #1D4ED8;
  --ai-accent-soft: #EFF6FF;
  --ai-red: #B91C1C;   --ai-red-bg: #FEF2F2;   --ai-red-bd: #FECACA;   --ai-red-solid: #DC2626;
  --ai-amber: #B45309; --ai-amber-bg: #FFF7ED; --ai-amber-bd: #FED7AA; --ai-amber-solid: #EA8C00;
  --ai-green: #15803D; --ai-green-bg: #F0FDF4; --ai-green-bd: #BBF7D0;
  --ai-blue: #1D4ED8;  --ai-blue-bg: #EFF6FF;  --ai-blue-bd: #BFDBFE;  --ai-blue-solid: #2563EB;
  --ai-violet: #6D28D9; --ai-violet-bg: #F5F3FF; --ai-violet-bd: #DDD6FE;
  --ai-neutral-bg: #F1F5F9;
  --ai-shadow: 0 1px 2px rgba(15, 23, 42, .05), 0 4px 12px rgba(15, 23, 42, .04);
  --ai-radius: 12px;
}

/* ---- page frame ---------------------------------------------------------------------- */
[data-testid="stMainBlockContainer"] { max-width: 1240px; padding: 1.25rem 2rem 4rem; }
.stHtml dl, .stHtml dd { margin-left: 0; padding-left: 0; }
@media (max-width: 640px) {
  [data-testid="stMainBlockContainer"] { padding-left: 1rem; padding-right: 1rem; padding-top: .75rem; }
}
:focus-visible { outline: 2px solid var(--ai-accent) !important; outline-offset: 2px; }

/* ---- surfaces: keyed containers whose key starts with card_ / appbar -------------------- */
[class*="st-key-card_"], .st-key-appbar {
  background: var(--ai-surface);
  border-color: var(--ai-border) !important;
  border-radius: var(--ai-radius);
  box-shadow: var(--ai-shadow);
}
/* Streamlit's markdown list styles would otherwise indent the app's own lists. */
.stHtml ul.ai-req, .stHtml ul.ai-obs, .stHtml ul.ai-shots { padding-left: 0; margin-left: 0; }
.stHtml ul.ai-list { padding-left: 1.25rem; margin-left: 0; }
.stHtml li { margin-bottom: 0; }
.st-key-appbar {
  border: 1px solid var(--ai-border);
  padding: .625rem 1rem;
  margin-bottom: .5rem;
}
[class*="st-key-ptile_"], [class*="st-key-vthumb_box_"] { background: var(--ai-surface); }
/* Photo tiles: three per row on desktop, two on phones. Progressive enhancement - without
   :has() support the tiles keep their fixed 176px width and still wrap. */
[data-testid="stLayoutWrapper"]:has(> [class*="st-key-ptile_"]) {
  flex: 0 0 calc((100% - 1rem) / 3) !important; width: calc((100% - 1rem) / 3) !important; min-width: 0; }
@media (max-width: 640px) {
  [data-testid="stLayoutWrapper"]:has(> [class*="st-key-ptile_"]) {
    flex-basis: calc((100% - .5rem) / 2) !important; width: calc((100% - .5rem) / 2) !important; }
}
.st-key-appbar_right .ai-status { justify-content: flex-start; }

/* ---- brand ----------------------------------------------------------------------------- */
.ai-brand { display: flex; align-items: center; gap: .75rem; }
.ai-logo { width: 40px; height: 40px; border-radius: 10px; flex: none;
  background: var(--ai-accent) url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjRkZGRkZGIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCI+PHBhdGggZD0iTTUgMTdoMTR2LTQuNWwtMS44LTQuMkEyIDIgMCAwIDAgMTUuNCA3SDguNmEyIDIgMCAwIDAtMS44IDEuM0w1IDEyLjVWMTd6Ii8+PHBhdGggZD0iTTUgMTIuNWgxNCIvPjxjaXJjbGUgY3g9IjgiIGN5PSIxNyIgcj0iMS42Ii8+PGNpcmNsZSBjeD0iMTYiIGN5PSIxNyIgcj0iMS42Ii8+PC9zdmc+") center / 24px 24px no-repeat; }
.ai-brand-name { font-size: 1.125rem; font-weight: 700; color: var(--ai-text); line-height: 1.2; }
.ai-brand-sub { font-size: .875rem; color: var(--ai-muted); line-height: 1.3; }

/* ---- headings -------------------------------------------------------------------------- */
.ai-page-head { margin: .5rem 0 .25rem; }
.ai-page-title { font-size: 1.75rem; font-weight: 700; color: var(--ai-text); margin: 0; padding: 0;
  line-height: 1.25; letter-spacing: -.01em; }
.ai-page-sub { margin: .25rem 0 0; color: var(--ai-muted); font-size: 1rem; }
.ai-eyebrow { font-size: .875rem; font-weight: 600; color: var(--ai-accent-ink); letter-spacing: .02em;
  margin-bottom: .125rem; }
.ai-section-head { display: flex; justify-content: space-between; align-items: flex-start; gap: .75rem;
  flex-wrap: wrap; }
.ai-section-title { font-size: 1.125rem; font-weight: 650; color: var(--ai-text); margin: 0; padding: 0;
  line-height: 1.35; }
.ai-section-sub { margin: .125rem 0 0; color: var(--ai-muted); font-size: .9375rem; line-height: 1.45; }
.ai-section-right { display: flex; gap: .375rem; flex-wrap: wrap; }
.ai-muted { color: var(--ai-muted); font-size: .9375rem; margin: .25rem 0 0; }
.ai-sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }

/* ---- chips ----------------------------------------------------------------------------- */
.ai-chip { display: inline-flex; align-items: center; gap: .375rem; padding: .125rem .625rem;
  border-radius: 999px; font-size: .875rem; font-weight: 600; line-height: 1.5; white-space: nowrap;
  border: 1px solid var(--ai-border); background: var(--ai-neutral-bg); color: var(--ai-text-2);
  max-width: 100%; overflow: hidden; text-overflow: ellipsis; }
.ai-chip--blue   { background: var(--ai-blue-bg);   color: var(--ai-blue);   border-color: var(--ai-blue-bd); }
.ai-chip--green  { background: var(--ai-green-bg);  color: var(--ai-green);  border-color: var(--ai-green-bd); }
.ai-chip--amber  { background: var(--ai-amber-bg);  color: var(--ai-amber);  border-color: var(--ai-amber-bd); }
.ai-chip--red    { background: var(--ai-red-bg);    color: var(--ai-red);    border-color: var(--ai-red-bd); }
.ai-chip--violet { background: var(--ai-violet-bg); color: var(--ai-violet); border-color: var(--ai-violet-bd); }
.ai-dot { width: .5rem; height: .5rem; border-radius: 50%; background: currentColor; flex: none; }
.ai-chip-row { display: flex; flex-wrap: wrap; gap: .375rem; margin-top: .375rem; }
.ai-chip-row .ai-chip { white-space: normal; }
.ai-status { display: flex; flex-wrap: wrap; gap: .375rem; justify-content: flex-end; }

/* ---- alerts / notices ------------------------------------------------------------------ */
.ai-alert { border-left: 4px solid; padding: .125rem 0 .125rem .875rem; }
.ai-alert p { margin: .25rem 0 0; color: var(--ai-text-2); line-height: 1.5; }
.ai-alert .ai-alert-title { margin: 0; font-weight: 650; color: var(--ai-text); font-size: 1.0625rem; }
.ai-alert--red { border-color: var(--ai-red-solid); }
.ai-alert--amber { border-color: var(--ai-amber-solid); }
.ai-alert code, .ai-coverage code { font-size: .875rem; background: var(--ai-neutral-bg); padding: .05rem .3rem;
  border-radius: 4px; word-break: break-all; }
.ai-notice { background: var(--ai-amber-bg); border: 1px solid var(--ai-amber-bd); border-radius: var(--ai-radius);
  padding: .75rem 1rem; color: #7C2D12; }
.ai-notice p { margin: 0; line-height: 1.5; font-size: .9375rem; }
.ai-notice p + p { margin-top: .25rem; }

/* ---- photo intake ---------------------------------------------------------------------- */
.ai-thumb-meta { display: flex; flex-direction: column; gap: .125rem; }
.ai-thumb-head { display: flex; justify-content: space-between; align-items: center; gap: .25rem .375rem;
  flex-wrap: wrap; }
.ai-thumb-head strong { font-size: .9375rem; color: var(--ai-text); white-space: nowrap; }
.ai-thumb-name { margin: 0; font-size: .875rem; color: var(--ai-muted); white-space: nowrap; overflow: hidden;
  text-overflow: ellipsis; }
.ai-thumb-size { margin: 0; font-size: .875rem; color: var(--ai-subtle); }
.ai-thumb-note { margin: .125rem 0 0; font-size: .875rem; color: var(--ai-amber); line-height: 1.35;
  overflow-wrap: anywhere; }
.ai-thumb-note--red { color: var(--ai-red); }
.ai-thumb-missing { aspect-ratio: 4 / 3; display: grid; place-items: center; border-radius: 6px;
  background: var(--ai-neutral-bg); color: var(--ai-subtle); font-size: .875rem; }
.ai-quality { display: flex; flex-direction: column; gap: .25rem; }
.ai-quality-item { margin: 0; font-size: .9375rem; line-height: 1.45; padding-left: 1rem; position: relative;
  color: var(--ai-text-2); }
.ai-quality-item::before { content: ""; position: absolute; left: 0; top: .5rem; width: .5rem; height: .5rem;
  border-radius: 50%; background: var(--ai-subtle); }
.ai-quality-item--amber::before { background: var(--ai-amber-solid); }
.ai-quality-item--red::before { background: var(--ai-red-solid); }
[data-testid="stFileUploaderDropzone"] { min-height: 150px; display: flex; flex-direction: column;
  align-items: center; justify-content: center; gap: .5rem; text-align: center;
  border: 2px dashed var(--ai-border-strong); background: var(--ai-accent-soft); }
[data-testid="stFileUploaderDropzone"]::before { content: "Drag and drop photos here, or";
  font-size: 1rem; font-weight: 600; color: var(--ai-text-2); }
.ai-shots { list-style: none; display: flex; flex-wrap: wrap; gap: .375rem; margin: 0; }
.ai-shots-title { margin: 0 0 .375rem; font-size: .9375rem; color: var(--ai-muted); }

/* ---- vehicle --------------------------------------------------------------------------- */
.ai-coverage { border: 1px solid var(--ai-border); border-radius: 10px; padding: .625rem .75rem;
  background: #FBFCFD; }
.ai-coverage-head { display: flex; flex-wrap: wrap; align-items: center; gap: .5rem; }
.ai-coverage-count { font-size: .875rem; color: var(--ai-muted); }
.ai-coverage-msg { margin: .375rem 0 0; font-size: .9375rem; color: var(--ai-text-2); line-height: 1.45; }

/* ---- requirement checklist ------------------------------------------------------------- */
.ai-req { list-style: none; margin: .25rem 0 0; padding: 0; display: flex; flex-direction: column; gap: .25rem; }
.ai-req li { display: flex; align-items: baseline; gap: .5rem; font-size: .9375rem; color: var(--ai-text-2); }
.ai-req li.todo { color: var(--ai-muted); }
.ai-req-icon { width: 1.25rem; height: 1.25rem; border-radius: 50%; display: inline-grid; place-items: center;
  font-size: .875rem; line-height: 1; font-weight: 700; flex: none; transform: translateY(2px); }
.ai-req li.ok .ai-req-icon { background: var(--ai-green-bg); color: var(--ai-green); border: 1px solid var(--ai-green-bd); }
.ai-req li.todo .ai-req-icon { background: var(--ai-neutral-bg); color: var(--ai-subtle); border: 1px solid var(--ai-border-strong); }

/* ---- results header -------------------------------------------------------------------- */
.ai-result-title { font-size: 1.5rem; font-weight: 700; margin: 0; padding: 0; color: var(--ai-text); line-height: 1.3; }
.ai-result-meta { margin: .375rem 0 0; color: var(--ai-muted); font-size: .9375rem; }

/* ---- evidence viewer ------------------------------------------------------------------- */
.ai-legend { display: flex; flex-wrap: wrap; gap: 1rem; font-size: .875rem; color: var(--ai-muted); }
.ai-legend span { display: inline-flex; align-items: center; gap: .375rem; }
.ai-swatch { width: .875rem; height: .875rem; border-radius: 3px; display: inline-block; border: 2px solid; }
.ai-swatch--severe { border-color: var(--ai-red-solid); }
.ai-swatch--moderate { border-color: var(--ai-amber-solid); }
.ai-swatch--minor { border-color: var(--ai-blue-solid); }
.ai-obs { list-style: none; margin: 0; padding: 0; border-top: 1px solid var(--ai-border); }
.ai-obs li { display: flex; flex-wrap: wrap; align-items: center; gap: .5rem; padding: .5rem 0;
  border-bottom: 1px solid var(--ai-border); font-size: .9375rem; color: var(--ai-text-2); }
.ai-obs-main { flex: 1 1 12rem; min-width: 0; }
.ai-obs-main strong { color: var(--ai-text); }
.ai-obs-meta { font-size: .875rem; color: var(--ai-subtle); }
.ai-obs-id { flex: none; min-width: 2.75rem; text-align: center; font-size: .875rem; font-weight: 700;
  color: #FFFFFF; border-radius: 6px; padding: .0625rem .375rem; background: var(--ai-subtle);
  font-variant-numeric: tabular-nums; }
.ai-obs-id--severe { background: var(--ai-red-solid); }
.ai-obs-id--moderate { background: #C2410C; }
.ai-obs-id--minor { background: var(--ai-blue-solid); }
.ai-obs-cost { margin-left: auto; font-weight: 600; color: var(--ai-text); font-variant-numeric: tabular-nums; }

/* ---- cost summary ---------------------------------------------------------------------- */
.ai-cost-label { font-size: .9375rem; font-weight: 600; color: var(--ai-muted); }
.ai-cost-value { font-size: 2rem; font-weight: 750; letter-spacing: -.02em; color: var(--ai-text);
  line-height: 1.2; margin-top: .125rem; font-variant-numeric: tabular-nums; overflow-wrap: anywhere; }
.ai-cost-basis { font-size: .9375rem; color: var(--ai-muted); margin-top: .125rem; }
.ai-cost-rows { margin: .75rem 0 0; padding: .5rem 0 0; border-top: 1px solid var(--ai-border); }
.ai-cost-row { display: flex; justify-content: space-between; gap: 1rem; padding: .25rem 0; font-size: .9375rem; }
.ai-cost-row dt { color: var(--ai-muted); }
.ai-cost-row dd { margin: 0; font-weight: 600; color: var(--ai-text); text-align: right;
  font-variant-numeric: tabular-nums; white-space: nowrap; }
.ai-stats { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: .5rem; }
.ai-stat { border: 1px solid var(--ai-border); border-radius: 10px; padding: .5rem .75rem; display: flex;
  flex-direction: column; border-top-width: 3px; }
.ai-stat--red { border-top-color: var(--ai-red-solid); }
.ai-stat--blue { border-top-color: var(--ai-blue-solid); }
.ai-stat--amber { border-top-color: var(--ai-amber-solid); }
.ai-stat-value { font-size: 1.5rem; font-weight: 700; color: var(--ai-text); line-height: 1.2; }
.ai-stat-label { font-size: .875rem; color: var(--ai-muted); }
.ai-uncert-head { display: flex; justify-content: space-between; align-items: center; gap: .5rem;
  font-weight: 600; color: var(--ai-text); flex-wrap: wrap; }

/* ---- lists, definition lists, tables --------------------------------------------------- */
.ai-list { margin: .375rem 0 0; padding-left: 1.25rem; color: var(--ai-text-2); font-size: .9375rem; line-height: 1.5; }
.ai-list li + li { margin-top: .25rem; }
.ai-dl { display: grid; grid-template-columns: minmax(8rem, max-content) 1fr; gap: .25rem 1rem; margin: 0;
  font-size: .9375rem; }
.ai-dl dt { color: var(--ai-muted); }
.ai-dl dd { margin: 0; color: var(--ai-text); overflow-wrap: anywhere; }
@media (max-width: 520px) { .ai-dl { grid-template-columns: 1fr; } .ai-dl dd { margin-bottom: .375rem; } }
.ai-dl-title { margin: .75rem 0 0; font-weight: 650; color: var(--ai-text); font-size: .9375rem; }
.ai-totals { width: 100%; border-collapse: collapse; font-size: .9375rem; }
.ai-totals th { text-align: left; font-weight: 500; color: var(--ai-text-2); padding: .5rem 0;
  border-bottom: 1px solid var(--ai-border); }
.ai-totals td { text-align: right; font-weight: 650; color: var(--ai-text); padding: .5rem 0 .5rem 1rem;
  border-bottom: 1px solid var(--ai-border); white-space: nowrap; font-variant-numeric: tabular-nums; }

/* ---- tabs (semantic role selector) ----------------------------------------------------- */
[role="tab"] p { font-size: 1rem; font-weight: 600; }

/* ---- findings -------------------------------------------------------------------------- */
.ai-finding-head { display: flex; justify-content: space-between; align-items: flex-start; gap: .75rem; flex-wrap: wrap; }
.ai-finding-title { font-size: 1.0625rem; font-weight: 650; margin: 0; padding: 0; color: var(--ai-text); }
.ai-finding-cost { font-weight: 650; color: var(--ai-text); font-variant-numeric: tabular-nums; }
.ai-finding-reason { margin: .5rem 0 0; color: var(--ai-text-2); font-size: .9375rem; line-height: 1.5; }
.ai-finding-clar { margin: .375rem 0 0; color: var(--ai-amber); font-size: .9375rem; }

@media (max-width: 640px) {
  .ai-page-title { font-size: 1.5rem; }
  .ai-cost-value { font-size: 1.625rem; }
  .ai-brand-sub { display: none; }
}
</style>
"""


def inject() -> None:
    st.html(CSS)
