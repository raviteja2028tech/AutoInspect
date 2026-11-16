"""Step 3 of the pipeline: merge per-photo results.

v2 (deterministic reconciliation, NOT verified cross-view understanding):
- Findings are merged by (component instance, damage type); distinct damage types and
  image-linked boxes are kept underneath. Different wheels/mirrors never merge because the
  instance names differ.
- Support = number of UNIQUE images (duplicates are removed at intake).
- No confidence bonus for extra photos. The reported score is the mean of the per-image model
  scores (uncalibrated).
- Severity: chosen from strong observations (score >= STRONG). A weak higher-severity view does
  not override strong contrary evidence; it is recorded as a conflict. Strong views two levels
  apart (minor vs severe) leave the severity unresolved (finding marked uncertain -> inspect).

fuse(results) keeps the legacy flat output (used by older callers/tests).
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict

from .contracts import Observation
from .schemas import ImageResult, normalised_box
from .vocab import SEVERITY_RANK

UNCERTAIN_BELOW = 0.5      # entries below this confidence are flagged "uncertain"
STRONG = 0.7               # per-image score treated as strong evidence for severity


def fuse(results: list[ImageResult]) -> list[dict]:
    """Legacy flat fusion (one entry per component+damage type). No extra-view bonus."""
    obs, _ = fuse_observations([(f"img{i}", r) for i, r in enumerate(results)])
    return [legacy_damage(o) for o in obs]


def legacy_damage(o: Observation) -> dict:
    return {"component": o.component, "damage_type": o.damage_type, "severity": o.severity,
            "location": o.location, "confidence": o.confidence, "views_supporting": o.views_supporting,
            "uncertain": o.uncertain, "damage_id": o.damage_id}


def _side(component: str) -> str | None:
    for side in ("left", "right"):
        if re.search(rf"(^|_){side}($|_)", component):
            return side
    return None


def fuse_observations(items: list[tuple[str, ImageResult]]) -> tuple[list[Observation], list[dict]]:
    """items = [(image_id, ImageResult)] for unique, successfully analysed vehicle images."""
    groups: dict[tuple[str, str], dict[str, list]] = defaultdict(lambda: defaultdict(list))
    order = {image_id: i for i, (image_id, _) in enumerate(items)}
    for image_id, r in items:
        for d in r.damages:
            groups[(d.component, d.damage_type)][image_id].append(d)

    built, conflicts = [], []
    for (comp, dtype), per_img in groups.items():
        entries = []
        for image_id in sorted(per_img, key=order.get):
            ds = per_img[image_id]
            best = max(ds, key=lambda d: d.confidence)
            if len(ds) > 1:
                conflicts.append({"type": "same_image_repeat", "component": comp, "damage_type": dtype,
                                  "image_id": image_id, "detail": f"{len(ds)} entries in one image merged"})
            entries.append((image_id, best))

        strong = [(i, d) for i, d in entries if d.confidence >= STRONG]
        pool = strong or entries
        severity = max((d.severity for _, d in pool), key=SEVERITY_RANK.get)
        conf = round(sum(d.confidence for _, d in entries) / len(entries), 2)
        uncertain = conf < UNCERTAIN_BELOW
        reason = ("worst severity among strong views" if strong else
                  "no strong view; worst reported severity, kept uncertain")
        conflict_note = None
        unresolved = False
        if len({d.severity for _, d in entries}) > 1:
            overridden = [(i, d) for i, d in entries
                          if SEVERITY_RANK[d.severity] > SEVERITY_RANK[severity]]
            strong_ranks = [SEVERITY_RANK[d.severity] for _, d in strong]
            unresolved = bool(strong_ranks) and max(strong_ranks) - min(strong_ranks) >= 2
            if unresolved:
                uncertain = True
                reason = "strong views disagree by two levels: severity unresolved, inspection required"
            conflict_note = {
                "type": "severity_conflict", "component": comp, "damage_type": dtype,
                "views": [{"image_id": i, "severity": d.severity, "score": d.confidence} for i, d in entries],
                "chosen": severity, "unresolved": unresolved,
                "detail": (f"weak higher-severity view(s) {[i for i, _ in overridden]} not used over strong evidence"
                           if overridden else reason)}
        if not strong:
            uncertain = True

        locs = Counter(d.location for _, d in entries)
        location = max(locs, key=lambda k: (locs[k], -min(order[i] for i, d in entries if d.location == k)))
        side = _side(comp)
        if side and any(d.location in ("left", "right") and d.location != side for _, d in entries):
            conflicts.append({"type": "side_conflict", "component": comp, "damage_type": dtype,
                              "detail": f"component is on the {side} but a view reported location "
                                        f"{[d.location for _, d in entries]}; check left/right assignment"})
        boxes, box_notes = {}, []
        for i, d in entries:
            box, note = normalised_box(d.box_2d)
            boxes[i] = box
            if box is None:
                box_notes.append(f"{i}: {note}")
        chosen = next(d for _, d in pool if d.severity == severity)
        built.append((conflict_note, Observation(
            damage_id="", component=comp, component_reported=comp, damage_type=dtype, severity=severity,
            location=location, confidence=conf, uncertain=uncertain, severity_unresolved=unresolved,
            views_supporting=len(entries),
            image_ids=[i for i, _ in entries],
            evidence="; ".join(dict.fromkeys(d.evidence for _, d in entries if d.evidence)),
            severity_rationale=f"{chosen.severity_rationale} [{reason}]".strip(),
            bbox_by_image=boxes,
            per_image=[{"image_id": i, "severity": d.severity, "score": d.confidence, "location": d.location,
                        "box": boxes[i], "evidence": d.evidence} for i, d in entries],
            localization_note="; ".join(box_notes) or "approximate VLM localisation (not segmentation)")))

    built.sort(key=lambda t: (-t[1].confidence, t[1].component, t[1].damage_type))
    observations = []
    for n, (conflict, o) in enumerate(built, 1):
        o.damage_id = f"O{n}"
        if conflict:
            conflicts.append({**conflict, "damage_id": o.damage_id})
        observations.append(o)
    return observations, conflicts


# --------------------------------------------------------------------------- vehicle identity
_COLOR_FAMILY = {"grey": "grey", "gray": "grey", "silver": "grey", "white": "white", "pearl": "white",
                 "black": "black", "red": "red", "maroon": "red", "blue": "blue", "navy": "blue",
                 "green": "green", "yellow": "yellow", "orange": "orange", "brown": "brown", "beige": "brown",
                 "bronze": "brown", "gold": "gold", "golden": "gold", "purple": "purple"}


def _color(c: str) -> str | None:
    for word in re.findall(r"[a-z]+", (c or "").lower()):
        if word in _COLOR_FAMILY:
            return _COLOR_FAMILY[word]
    return None


def vehicle_consistency(items: list[tuple[str, ImageResult]]) -> dict:
    """Fallible same-vehicle check from visible identity cues. Not identity verification."""
    colors, bodies, makes = {}, {}, {}
    for image_id, r in items:
        vi = r.vehicle_identity
        if not vi:
            continue
        if _color(vi.color):
            colors[image_id] = _color(vi.color)
        if vi.body_type not in ("unknown", "other"):
            bodies[image_id] = vi.body_type
        guess = (vi.make_model_guess or "").strip().lower()
        if guess and guess != "unknown":
            makes[image_id] = guess.split()[0]
    evidence, conflict = [], False
    for label, vals in (("colour", colors), ("body type", bodies), ("make", makes)):
        if len(set(vals.values())) > 1:
            conflict = True
            evidence.append(f"{label} differs between images: {vals}")
    known = max(len(colors), len(bodies))
    if conflict:
        status = "conflict"
    elif len(items) > 1 and known < 2:
        status = "uncertain"
        evidence.append("too few identity cues to compare images")
    else:
        status = "consistent" if len(items) > 1 else "single_image"
    return {"status": status, "evidence": evidence, "requires_confirmation": status in ("conflict", "uncertain"),
            "method": "visible colour/body-type/make cues reported by the vision model; fallible, not identity "
                      "verification",
            "cues": {"colour": colors, "body_type": bodies, "make": makes}}


# --------------------------------------------------------------------------- narrative check
_AREA_WORDS = {"front": ["front", "head-on", "headlight", "bonnet", "hood", "windshield", "windscreen"],
               "rear": ["rear", "back", "reversing", "reversed", "tail", "boot", "trunk", "dickey"],
               "left": ["left"], "right": ["right"]}


def narrative_check(description: str | None, observations: list[Observation]) -> dict:
    """Keyword comparison of the user's accident description with visual findings.

    The narrative is untrusted context: it never adds findings. Contradictions are reported.
    """
    if not description or not description.strip():
        return {"provided": False}
    text = description.lower()
    mentioned = sorted(a for a, words in _AREA_WORDS.items() if any(re.search(rf"\b{re.escape(w)}", text)
                                                                    for w in words))
    found = {"front": set(), "rear": set(), "left": set(), "right": set()}
    for o in observations:
        if o.location in found:
            found[o.location].add(o.damage_id)
        s = _side(o.component)
        if s:
            found[s].add(o.damage_id)
    contradictions = [f"Description mentions the {a} but no {a} damage was found in the photos"
                      for a in mentioned if not found[a]]
    unmentioned = [f"Damage found at the {a} ({', '.join(sorted(ids))}) is not mentioned in the description"
                   for a, ids in found.items() if ids and mentioned and a not in mentioned]
    return {"provided": True, "areas_mentioned": mentioned, "contradictions": contradictions,
            "not_mentioned": unmentioned,
            "method": "keyword match of areas (front/rear/left/right); not semantic understanding. "
                      "The description is not evidence and never adds findings."}
