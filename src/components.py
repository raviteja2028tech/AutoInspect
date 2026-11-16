"""Turn a damage map into observations and group them into component instances.

Two input shapes are supported:
- legacy flat damage map (samples/*.json): damages[] with component/damage_type/severity/...
  -> adapt_damage_map() assigns stable damage IDs D1..Dn in list order.
- v2 damage map from src.pipeline (has "observations"): used as is.

Ambiguous legacy names (side_mirror, wheel_tire, side_window) are never assigned to a side
silently. They stay ambiguous unless the caller passes an explicit clarification, e.g.
{"D5": "side_mirror_left"} (by damage ID) or {"side_mirror": "side_mirror_left"} (by name).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .contracts import Observation
from .vocab import AMBIGUOUS_COMPONENTS, SEVERITY_RANK, component_class, normalise_component


class ClarificationError(ValueError):
    pass


def adapt_damage_map(damage_map: dict) -> list[Observation]:
    """Return validated observations from a legacy or v2 damage map."""
    if damage_map.get("observations"):
        return [Observation.model_validate(o) for o in damage_map["observations"]]
    out = []
    for i, d in enumerate(damage_map.get("damages", []), start=1):
        reported = str(d.get("component", "other"))
        conf = float(d.get("confidence", 0.0))
        out.append(Observation(
            damage_id=f"D{i}",
            component=normalise_component(reported),
            component_reported=reported,
            damage_type=d["damage_type"],
            severity=d["severity"],
            location=d.get("location", "front"),
            confidence=max(0.0, min(1.0, conf)),
            uncertain=bool(d.get("uncertain", conf < 0.5)),
            views_supporting=int(d.get("views_supporting", 1)),
            legacy=True,
        ))
    return out


def apply_clarifications(observations: list[Observation], clarifications: dict | None) -> list[Observation]:
    if not clarifications:
        return observations
    out = []
    for o in observations:
        target = clarifications.get(o.damage_id) or clarifications.get(o.component)
        if target and o.component in AMBIGUOUS_COMPONENTS:
            if target not in AMBIGUOUS_COMPONENTS[o.component]:
                raise ClarificationError(f"{o.damage_id}: '{target}' is not a valid position for {o.component}; "
                                         f"choose one of {AMBIGUOUS_COMPONENTS[o.component]}")
            o = o.model_copy(update={"component": target})
        out.append(o)
    return out


@dataclass
class ComponentGroup:
    instance: str
    observations: list[Observation] = field(default_factory=list)

    @property
    def ambiguous(self) -> bool:
        return self.instance in AMBIGUOUS_COMPONENTS

    @property
    def cls(self) -> str:
        return component_class(self.instance)

    @property
    def damage_ids(self) -> list[str]:
        return [o.damage_id for o in self.observations]

    @property
    def damage_types(self) -> list[str]:
        return sorted({o.damage_type for o in self.observations})

    @property
    def max_severity(self) -> str:
        return max((o.severity for o in self.observations), key=SEVERITY_RANK.get)

    def clarification_hint(self) -> str | None:
        if not self.ambiguous:
            return None
        locs = sorted({o.location for o in self.observations})
        return (f"'{self.instance}' does not say which one (reported location: {', '.join(locs)}). "
                f"Confirm one of {AMBIGUOUS_COMPONENTS[self.instance]} before pricing.")


def group_by_instance(observations: list[Observation]) -> list[ComponentGroup]:
    groups: dict[str, ComponentGroup] = {}
    for o in observations:
        groups.setdefault(o.component, ComponentGroup(o.component)).observations.append(o)
    return sorted(groups.values(), key=lambda g: g.instance)
