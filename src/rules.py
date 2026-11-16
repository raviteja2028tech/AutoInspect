"""Repair / replace / inspect rules (preliminary demo heuristics, versioned).

Each observation on a component instance is evaluated by a component-class rule that looks at
damage TYPE, severity and (for borderline cases) model score - severity alone never decides.
The group decision then combines them:

  1. ambiguous instance  -> inspect (needs side/position)          [G-AMB]
  2. component "other"   -> inspect (unsupported)                  [G-OTHER]
  3. no observation with score >= CONFIDENT -> inspect             [G-UNCERTAIN]
  4. any definite replace -> replace; replacement covers every other finding on that part
  5. any inspect          -> inspect, keeping the candidate operations as scenarios
  6. otherwise the strongest operation (repair > refinish); the refinish of a scratch is part of
     the repair of the same panel, so it is not charged twice.

These are not validated workshop or insurer rules.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .components import ComponentGroup
from .contracts import Observation

RULES_VERSION = "rules-2026.11-v2"     # v2: G-SEV-CONFLICT (unresolved multi-view severity -> inspect)
CONFIDENT = 0.5         # below this, a finding alone cannot drive a priced operation
STRONG = 0.8            # severe deformation on a bolt-on panel is "replace" only when this sure

_OP_RANK = {"refinish": 0, "repair": 1, "replace": 2}


@dataclass
class ObsDecision:
    kind: str                       # "op" | "inspect"
    operation: str | None
    rule_id: str
    reason: str
    alternatives: list[str] = field(default_factory=list)


@dataclass
class GroupDecision:
    action: str                     # repair | replace | inspect
    operation: str | None
    rule_id: str
    reason: str
    alternatives: list[str]
    covered_note: str = ""
    notes: list[str] = field(default_factory=list)


def _op(op, rid, reason, alts=()):
    return ObsDecision("op", op, rid, reason, list(alts))


def _inspect(rid, reason, alts=()):
    return ObsDecision("inspect", None, rid, reason, list(alts))


def _scratch(o: Observation, prefix: str) -> ObsDecision:
    if o.severity == "severe":
        return _op("repair", f"{prefix}-SCR-2", "deep scratch/gouge: filler repair and refinish")
    return _op("refinish", f"{prefix}-SCR-1", "surface scratch: refinish the panel")


def decide_observation(cls: str, o: Observation) -> ObsDecision:
    t, s = o.damage_type, o.severity
    if cls == "panel_plastic":
        if t == "scratch":
            return _scratch(o, "PP")
        if t == "dent":
            if s == "severe":
                return _op("replace", "PP-DENT-2", "severe deformation of plastic bumper cover; "
                           "replacement is usually more economical", ["repair"])
            return _op("repair", "PP-DENT-1", "localised dent in bumper cover: reshape and refinish")
        if t == "crack":
            if s == "severe":
                return _op("replace", "PP-CRK-2", "severely cracked/torn bumper cover: replace")
            return _op("repair", "PP-CRK-1", "limited crack: plastic repair may be possible if mounting "
                       "tabs are intact", ["replace"])
        if t == "missing_part":
            return _op("replace", "PP-MISS", "part missing or torn off: replace")
    elif cls == "panel_bolt_on":
        if t == "scratch":
            return _scratch(o, "PB")
        if t == "dent":
            if s != "severe":
                return _op("repair", "PB-DENT-1", "dent without visible panel tear: panel repair and refinish")
            if o.confidence >= STRONG:
                return _op("replace", "PB-DENT-2", "severe deformation clearly visible on a bolt-on panel: "
                           "replacement likely", ["repair"])
            return _inspect("PB-DENT-3", "severe deformation reported with limited certainty: "
                            "repairability must be checked", ["repair", "replace"])
        if t == "crack":
            if s == "severe":
                return _op("replace", "PB-CRK-2", "torn or split metal panel: replace")
            return _inspect("PB-CRK-1", "metal crack/split: check whether it can be repaired", ["repair", "replace"])
        if t == "missing_part":
            return _op("replace", "PB-MISS", "panel missing or detached: replace")
    elif cls == "panel_welded":
        if t == "scratch":
            return _scratch(o, "PW")
        if t == "dent" and s != "severe":
            return _op("repair", "PW-DENT-1", "dent on welded panel without visible structural distortion: repair")
        if t in ("dent", "crack", "missing_part"):
            return _inspect("PW-STRUCT", "welded panel (roof/quarter) with severe or torn damage may be "
                            "structural: physical inspection required", ["repair", "replace"])
    elif cls == "lamp":
        if t in ("lamp_broken", "crack", "missing_part", "glass_shatter"):
            return _op("replace", "L-1", "broken or cracked lamp: replace assembly (sealing is lost)")
        return _inspect("L-2", "lamp scuff/other: polishing or inspection; not priced")
    elif cls == "glass":
        if t in ("glass_shatter", "missing_part"):
            return _op("replace", "GL-1", "shattered or missing glass: replace")
        if t == "crack":
            if s == "minor":
                return _inspect("GL-3", "small chip/crack: resin repair may be possible (not priced)", ["replace"])
            return _op("replace", "GL-2", "crack across laminated/toughened glass: replace")
        return _inspect("GL-4", "glass surface mark: inspect")
    elif cls == "mirror":
        if t in ("crack", "missing_part", "glass_shatter", "lamp_broken") or (t == "dent" and s == "severe"):
            return _op("replace", "M-1", "broken, cracked or detached mirror: replace assembly")
        if t == "scratch":
            return _op("refinish", "M-2", "scratched mirror cover: refinish")
        return _inspect("M-3", "mirror cover dent: inspect", ["refinish", "replace"])
    elif cls == "wheel_tire":
        if t == "tire_flat":
            if s == "severe":
                return _op("replace", "W-1", "destroyed or severely damaged tyre: replace (rim, suspension "
                           "and alignment not assessed)")
            return _inspect("W-2", "flat tyre: may be a repairable puncture", ["repair", "replace"])
        return _inspect("W-3", "rim/wheel damage: inspect (rims are not in the pricing catalog)")
    return _inspect("G-MISMATCH", f"damage type '{t}' is unexpected for a {cls.replace('_', ' ')}: inspect")


def decide_group(g: ComponentGroup) -> GroupDecision:
    if g.ambiguous:
        return GroupDecision("inspect", None, "G-AMB", g.clarification_hint() or "position unknown", [])
    if g.cls == "other":
        return GroupDecision("inspect", None, "G-OTHER",
                             "component is not in the supported list: manual assessment needed", [])

    confident = [o for o in g.observations if o.confidence >= CONFIDENT and not o.uncertain]
    # Strong views that disagree on severity are NOT weak evidence: they need inspection.
    unresolved = [o for o in g.observations if o.severity_unresolved and o.confidence >= CONFIDENT]
    weak = [o for o in g.observations if o not in confident and o not in unresolved]
    if not confident and not unresolved:
        alts = sorted({a for o in g.observations for d in [decide_observation(g.cls, o)]
                       for a in ([d.operation] if d.operation else []) + d.alternatives}, key=_OP_RANK.get)
        return GroupDecision("inspect", None, "G-UNCERTAIN",
                             "all findings on this part have low model scores: confirm physically", alts,
                             notes=[f"{o.damage_id} score {o.confidence:.2f}" for o in weak])

    decided = [(o, decide_observation(g.cls, o)) for o in confident]
    notes = [f"{o.damage_id} ({o.damage_type}, score {o.confidence:.2f}"
             f"{'' if o.confidence < CONFIDENT else ', no strong supporting view'}) is low-confidence and not "
             "costed separately; verify at inspection" for o in weak]
    replaces = [(o, d) for o, d in decided if d.kind == "op" and d.operation == "replace"]
    if replaces:
        o, d = replaces[0]
        others = [x.damage_id for x in g.observations if x is not o]
        cover = (f"Replacement also covers {', '.join(others)} on the same part." if others else "")
        alts = sorted({a for _, x in replaces for a in x.alternatives if a != "replace"}, key=_OP_RANK.get)
        # low-confidence findings on a replaced part are covered by the replacement: no extra notes
        return GroupDecision("replace", "replace", d.rule_id, d.reason, alts, cover, [])
    if unresolved:
        alts = {x.operation for _, x in decided if x.operation} | {a for _, x in decided for a in x.alternatives}
        detail = []
        for o in unresolved:
            sevs = sorted({str(v.get("severity")) for v in o.per_image if v.get("severity")} or {o.severity},
                          key=lambda s: ["minor", "moderate", "severe"].index(s) if s in
                          ("minor", "moderate", "severe") else 9)
            detail.append(f"{o.damage_id} {o.damage_type} reported as {'/'.join(sevs)}")
            for sev in sevs:
                if sev in ("minor", "moderate", "severe"):
                    alt = decide_observation(g.cls, o.model_copy(update={"severity": sev, "uncertain": False}))
                    alts |= ({alt.operation} if alt.operation else set()) | set(alt.alternatives)
        return GroupDecision("inspect", None, "G-SEV-CONFLICT",
                             f"photos disagree on severity ({'; '.join(detail)}): inspect to choose the operation",
                             sorted(alts, key=_OP_RANK.get), "", notes)
    inspects = [(o, d) for o, d in decided if d.kind == "inspect"]
    if inspects:
        o, d = inspects[0]
        alts = {a for _, x in decided for a in x.alternatives}
        alts |= {x.operation for _, x in decided if x.operation}
        return GroupDecision("inspect", None, d.rule_id, d.reason, sorted(alts, key=_OP_RANK.get), "", notes)
    o, d = max(decided, key=lambda od: _OP_RANK[od[1].operation])
    others = [x.damage_id for x in confident if x is not o]
    cover = (f"One {d.operation} plan covers {', '.join(others)} as well (refinish is not charged twice)."
             if others else "")
    alts = sorted({a for _, x in decided for a in x.alternatives if a != d.operation}, key=_OP_RANK.get)
    action = "repair" if d.operation in ("repair", "refinish") else "replace"
    return GroupDecision(action, d.operation, d.rule_id, d.reason, alts, cover, notes)
