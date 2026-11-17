"""Display formatting: money, component names, action/severity metadata."""
from __future__ import annotations

from decimal import Decimal


def format_inr(val: int | float | Decimal | None) -> str:
    """Indian digit grouping (lakhs/crores): 158650 -> ₹1,58,650. None -> 'Not available'."""
    if val is None:
        return "Not available"
    n = int(round(val))
    s = str(abs(n))
    if len(s) > 3:
        last3, rem = s[-3:], s[:-3]
        groups = []
        while len(rem) > 2:
            groups.append(rem[-2:])
            rem = rem[:-2]
        if rem:
            groups.append(rem)
        s = ",".join(reversed(groups)) + "," + last3
    return f"₹{s}" if n >= 0 else f"-₹{s}"


def money_range(lo, hi) -> str:
    if lo is None and hi is None:
        return "Not priced"
    if lo is not None and hi is not None and int(round(lo)) == int(round(hi)):
        return format_inr(lo)
    return f"{format_inr(lo)} – {format_inr(hi)}"


def human(name: str | None) -> str:
    """'left_front_door' -> 'Left front door'."""
    text = (name or "").replace("_", " ").strip()
    return text[:1].upper() + text[1:] if text else "Unknown"


# label, chip tone, st.badge colour, material icon
ACTIONS = {
    "replace": ("Replace", "red", "red", ":material/swap_horiz:"),
    "repair": ("Repair", "blue", "blue", ":material/build:"),
    "inspect": ("Inspect", "amber", "orange", ":material/search:"),
}

# label, chip tone, st.badge colour. Matches the overlay box colours in src/overlay.py.
SEVERITIES = {
    "severe": ("Severe", "red", "red"),
    "moderate": ("Moderate", "amber", "orange"),
    "minor": ("Minor", "blue", "blue"),
}

PRICING_STATUS = {
    "priced": "Priced",
    "insufficient_pricing_data": "No price record",
    "ambiguous_component": "Ambiguous component",
    "unsupported_component": "Not in pricing scope",
    "not_priced_inspection": "Needs inspection",
}

OPERATIONS = {"refinish": "Refinish", "repair": "Repair", "replace": "Replace"}


def action_label(action: str) -> str:
    return ACTIONS.get(action, (human(action),))[0]


def severity_label(sev: str) -> str:
    return SEVERITIES.get(sev, (human(sev),))[0]


def pricing_status_label(status: str) -> str:
    return PRICING_STATUS.get(status, human(status))


def file_size(n: int) -> str:
    if n >= 1024 * 1024:
        return f"{n / (1024 * 1024):.1f} MB"
    return f"{max(1, round(n / 1024))} KB"
