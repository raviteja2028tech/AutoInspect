"""Streamlit presentation layer for AutoInspect.

All assessment logic lives in ``src/``; these modules only collect inputs, call
``src.service`` and render its validated ``Assessment``. Every piece of user- or model-supplied
text is escaped before it reaches HTML or Markdown (see ``ui.html``).
"""
