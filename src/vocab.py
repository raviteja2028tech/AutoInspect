"""Shared vocabulary.

Members A, B and C must all use these exact names. If you change a list,
tell the others first.

Compatibility notes (vocab v2):
- Legacy component names "side_mirror", "wheel_tire" and "side_window" are still accepted
  but are AMBIGUOUS (no side/position). They are never silently assigned to a side; the
  estimate flags them for clarification. New output should use the positioned names.
- "missing_part" is new: a part torn off / missing. Legacy output reported this as
  "crack" + "severe" (see LEGACY_NOTES); the adapter keeps such legacy entries as they are.
"""

VOCAB_VERSION = "v2"

DAMAGE_TYPES = ["dent", "scratch", "crack", "glass_shatter", "lamp_broken", "tire_flat", "missing_part"]

SEVERITIES = ["minor", "moderate", "severe"]
SEVERITY_RANK = {"minor": 0, "moderate": 1, "severe": 2}

LOCATIONS = ["front", "rear", "left", "right", "top"]

VIEWS = ["front", "rear", "left", "right", "top", "close_up", "unknown"]

# Positioned instances that replace the ambiguous legacy names.
AMBIGUOUS_COMPONENTS = {
    "side_mirror": ["side_mirror_left", "side_mirror_right"],
    "wheel_tire": ["wheel_tire_front_left", "wheel_tire_front_right",
                   "wheel_tire_rear_left", "wheel_tire_rear_right"],
    "side_window": ["side_window_front_left", "side_window_front_right",
                    "side_window_rear_left", "side_window_rear_right"],
}

COMPONENTS = [
    "front_bumper", "rear_bumper", "hood", "trunk", "roof",
    "left_front_door", "right_front_door", "left_rear_door", "right_rear_door",
    "left_fender", "right_fender", "left_quarter_panel", "right_quarter_panel",
    "windshield", "rear_window",
    "headlight_left", "headlight_right", "taillight_left", "taillight_right",
    *AMBIGUOUS_COMPONENTS["side_mirror"],
    *AMBIGUOUS_COMPONENTS["wheel_tire"],
    *AMBIGUOUS_COMPONENTS["side_window"],
    # legacy ambiguous names (accepted, flagged downstream)
    "side_window", "wheel_tire", "side_mirror",
    "other",
]

# Family of each instance (used by rules and by records that apply to any position).
COMPONENT_FAMILY = {name: name for name in COMPONENTS}
for _family, _instances in AMBIGUOUS_COMPONENTS.items():
    for _inst in _instances:
        COMPONENT_FAMILY[_inst] = _family

# Broad class used by the repair/replace/inspect rules.
_PLASTIC_PANELS = {"front_bumper", "rear_bumper"}
_BOLT_ON_METAL = {"hood", "trunk", "left_front_door", "right_front_door", "left_rear_door",
                  "right_rear_door", "left_fender", "right_fender"}
_WELDED_PANELS = {"roof", "left_quarter_panel", "right_quarter_panel"}
_LAMPS = {"headlight_left", "headlight_right", "taillight_left", "taillight_right"}
_GLASS = {"windshield", "rear_window", "side_window"}


def component_class(name: str) -> str:
    family = COMPONENT_FAMILY.get(name, "other")
    if family in _PLASTIC_PANELS:
        return "panel_plastic"
    if family in _BOLT_ON_METAL:
        return "panel_bolt_on"
    if family in _WELDED_PANELS:
        return "panel_welded"
    if family in _LAMPS:
        return "lamp"
    if family in _GLASS:
        return "glass"
    if family == "side_mirror":
        return "mirror"
    if family == "wheel_tire":
        return "wheel_tire"
    return "other"


# Common spellings mapped onto vocabulary names (lower-case, underscores).
COMPONENT_ALIASES = {
    "bonnet": "hood", "boot": "trunk", "boot_lid": "trunk", "tailgate": "trunk", "dickey": "trunk",
    "front_bumper_cover": "front_bumper", "rear_bumper_cover": "rear_bumper",
    "windscreen": "windshield", "front_windshield": "windshield", "rear_windshield": "rear_window",
    "back_glass": "rear_window",
    "left_headlight": "headlight_left", "right_headlight": "headlight_right",
    "left_taillight": "taillight_left", "right_taillight": "taillight_right",
    "left_tail_lamp": "taillight_left", "right_tail_lamp": "taillight_right",
    "left_head_lamp": "headlight_left", "right_head_lamp": "headlight_right",
    "left_mirror": "side_mirror_left", "right_mirror": "side_mirror_right",
    "left_side_mirror": "side_mirror_left", "right_side_mirror": "side_mirror_right",
    "orvm_left": "side_mirror_left", "orvm_right": "side_mirror_right", "mirror": "side_mirror",
    "tyre": "wheel_tire", "tire": "wheel_tire", "wheel": "wheel_tire",
    "front_left_tire": "wheel_tire_front_left", "front_right_tire": "wheel_tire_front_right",
    "rear_left_tire": "wheel_tire_rear_left", "rear_right_tire": "wheel_tire_rear_right",
    "left_front_fender": "left_fender", "right_front_fender": "right_fender",
    "left_rear_quarter_panel": "left_quarter_panel", "right_rear_quarter_panel": "right_quarter_panel",
}

OPERATIONS = ["refinish", "repair", "replace"]          # priced operations
ACTIONS = ["repair", "replace", "inspect"]              # recommendation shown to the user


def normalise_component(name: str) -> str:
    """Map a free-form component name onto the vocabulary (unknown -> 'other')."""
    key = str(name).strip().lower().replace(" ", "_").replace("-", "_")
    key = COMPONENT_ALIASES.get(key, key)
    return key if key in COMPONENT_FAMILY else "other"
