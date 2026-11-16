"""Pydantic schemas. The model's JSON answer is validated against these.

v3 (backward compatible): every new field has a default, so cached v1/v2 answers still load.
Confidence bounds are enforced on every load (fresh or cached). Boxes use Gemini's native
box_2d format [ymin, xmin, ymax, xmax] on a 0-1000 grid and are converted/validated by
normalised_box(); an invalid box becomes None with a reason, never a guessed box.
"""
from __future__ import annotations

import math
from typing import Literal, Optional

from pydantic import BaseModel, Field

from .vocab import COMPONENTS, DAMAGE_TYPES, LOCATIONS, SEVERITIES, VIEWS

Component = Literal[tuple(COMPONENTS)]
DamageType = Literal[tuple(DAMAGE_TYPES)]
Severity = Literal[tuple(SEVERITIES)]
Location = Literal[tuple(LOCATIONS)]
View = Literal[tuple(VIEWS)]
BodyType = Literal["hatchback", "sedan", "suv", "muv", "pickup", "van", "other", "unknown"]


class Damage(BaseModel):
    component: Component
    damage_type: DamageType
    severity: Severity
    location: Location
    confidence: float = Field(ge=0.0, le=1.0,
                              description="Number from 0.0 to 1.0: how sure you are this damage is real.")
    evidence: str = Field(default="", description="What is visibly seen, in a few words.")
    severity_rationale: str = Field(default="", description="Why this severity, in a few words.")
    box_2d: Optional[list[int]] = Field(
        default=None, description="[ymin, xmin, ymax, xmax] on a 0-1000 grid around the damaged area, "
                                  "or null if it cannot be localised.")


class VehicleIdentity(BaseModel):
    color: str = Field(default="unknown", description="Main body colour, one or two words, or 'unknown'.")
    body_type: BodyType = "unknown"
    make_model_guess: str = Field(default="unknown", description="Make/model if badges/shape make it clear, "
                                                                 "else 'unknown'.")


class ImageResult(BaseModel):
    view: View = Field(description="Which side of the car this photo mainly shows.")
    damages: list[Damage] = Field(description="Empty list if no damage is visible.")
    notes: str = Field(description="One short sentence: photo quality issues or anything unclear.")
    is_vehicle: bool = Field(default=True, description="False if the photo does not show a car.")
    vehicle_identity: Optional[VehicleIdentity] = None


def normalised_box(box_2d) -> tuple[Optional[list[float]], str]:
    """Gemini [ymin,xmin,ymax,xmax] (0-1000) -> ([x_min,y_min,x_max,y_max] in 0..1, reason)."""
    if box_2d is None:
        return None, "model did not localise this finding"
    try:
        if len(box_2d) != 4:
            return None, "box rejected: needs 4 numbers"
        ymin, xmin, ymax, xmax = (float(v) for v in box_2d)
    except (TypeError, ValueError):
        return None, "box rejected: non-numeric"
    vals = (ymin, xmin, ymax, xmax)
    if not all(math.isfinite(v) for v in vals):
        return None, "box rejected: non-finite values"
    if not all(0 <= v <= 1000 for v in vals):
        return None, "box rejected: outside the image"
    if not (xmin < xmax and ymin < ymax):
        return None, "box rejected: min/max out of order or zero area"
    return [round(xmin / 1000, 4), round(ymin / 1000, 4), round(xmax / 1000, 4), round(ymax / 1000, 4)], \
        "approximate VLM localisation (not segmentation)"
