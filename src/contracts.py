"""Validated data contracts for pricing records, retrieval evidence and the assessment/estimate.

The original damage-map (A -> B/C) contract is unchanged and kept verbatim inside
Assessment.damage_map. Everything here is additive and versioned via SCHEMA_VERSION.
Money is Decimal (serialised as a string in JSON) so that no float arithmetic is involved.
"""
from __future__ import annotations

import math
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .vocab import COMPONENT_FAMILY, DAMAGE_TYPES, LOCATIONS, OPERATIONS, SEVERITIES

SCHEMA_VERSION = "assessment-1.0"
DISCLAIMER = ("Preliminary AI-assisted assessment. Not insurance approval or a substitute "
              "for physical inspection.")
SYNTHETIC_LABEL = "Illustrative demo pricing — not market verified."

SourceType = Literal["synthetic_demo", "published_price_list", "dealer_quote",
                     "workshop_estimate", "insurer_schedule", "other_documented"]
Operation = Literal["refinish", "repair", "replace"]
Action = Literal["repair", "replace", "inspect"]
PricingStatus = Literal["priced", "insufficient_pricing_data", "ambiguous_component",
                        "unsupported_component", "not_priced_inspection"]


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


# --------------------------------------------------------------------------- pricing corpus
class PricingSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: str
    title: str
    reference: str = Field(description="Where the numbers came from (document, quote no., URL).")
    source_type: SourceType
    entered_date: date
    price_date: Optional[date] = None
    notes: str = ""


def _range_ok(lo, hi, name):
    if lo is None or hi is None:
        raise ValueError(f"{name}: both low and high are required")
    if lo < 0 or hi < 0:
        raise ValueError(f"{name}: negative values are not allowed")
    if lo > hi:
        raise ValueError(f"{name}: low ({lo}) is greater than high ({hi})")


class PricingRecord(BaseModel):
    """One structured price reference. Numeric fields are the ONLY source of arithmetic."""
    model_config = ConfigDict(extra="forbid")
    record_id: str
    source_id: str
    make: str
    model: str
    year_from: int
    year_to: int
    variant: str = "all"
    component: str
    position: str = "n/a"          # 'any' = applies to every positioned instance of the family
    operation: Operation
    part_grade: Literal["oem", "aftermarket", "n/a"] = "n/a"
    parts_cost_low: Decimal
    parts_cost_high: Decimal
    labor_hours_low: Decimal
    labor_hours_high: Decimal
    labor_rate_low: Decimal
    labor_rate_high: Decimal
    paint_materials_low: Decimal
    paint_materials_high: Decimal
    currency: str
    region: str
    tax_included: bool
    assumptions: str = ""
    applicability_limits: str = ""
    data_quality: Literal["synthetic_demo", "sourced_unverified", "sourced_verified"]

    @field_validator("make", "model", "variant", "component", "position", "region", "currency")
    @classmethod
    def _strip(cls, v: str) -> str:
        return str(v).strip()

    @field_validator("component")
    @classmethod
    def _known_component(cls, v: str) -> str:
        if v not in COMPONENT_FAMILY or v == "other":
            raise ValueError(f"component '{v}' is not in src/vocab.py")
        return v

    @model_validator(mode="after")
    def _check(self):
        if not (1980 <= self.year_from <= self.year_to <= 2100):
            raise ValueError(f"{self.record_id}: invalid year range {self.year_from}-{self.year_to}")
        _range_ok(self.parts_cost_low, self.parts_cost_high, "parts_cost")
        _range_ok(self.labor_hours_low, self.labor_hours_high, "labor_hours")
        _range_ok(self.labor_rate_low, self.labor_rate_high, "labor_rate")
        _range_ok(self.paint_materials_low, self.paint_materials_high, "paint_materials")
        if len(self.currency) != 3 or not self.currency.isupper():
            raise ValueError(f"{self.record_id}: currency must be an ISO code like INR")
        if self.position == "any" and COMPONENT_FAMILY[self.component] != self.component:
            raise ValueError(f"{self.record_id}: position 'any' requires a family name, not an instance")
        return self

    def applies_to_component(self, instance: str) -> bool:
        if self.component == instance:
            return True
        return self.position == "any" and COMPONENT_FAMILY.get(instance) == self.component


class RetrievedEvidence(BaseModel):
    record_id: str
    source_id: str
    source_title: str
    source_type: SourceType
    source_entered_date: Optional[date] = None
    source_price_date: Optional[date] = None
    synthetic: bool
    score: float = Field(description="Semantic similarity (cosine). Ranking only; not a probability.")
    rank: int
    fallback_level: str
    applicability_reason: str
    retrieval_method: Literal["semantic", "lexical_fallback", "stub_test"]
    record: PricingRecord


class RetrievalResult(BaseModel):
    status: Literal["ok", "insufficient_pricing_data"]
    query: str
    fallback_level: Optional[str] = None
    evidence: list[RetrievedEvidence] = []
    filters_applied: dict[str, Any] = {}
    message: str = ""


# --------------------------------------------------------------------------- vision side
class BBox(BaseModel):
    """Approximate normalised box [x_min, y_min, x_max, y_max] in 0..1 on the processed image."""
    x_min: float
    y_min: float
    x_max: float
    y_max: float

    @model_validator(mode="after")
    def _valid(self):
        vals = (self.x_min, self.y_min, self.x_max, self.y_max)
        if not all(math.isfinite(v) for v in vals):
            raise ValueError("bounding box values must be finite")
        if not all(0.0 <= v <= 1.0 for v in vals):
            raise ValueError("bounding box values must be within 0..1")
        if not (self.x_min < self.x_max and self.y_min < self.y_max):
            raise ValueError("bounding box must have x_min < x_max and y_min < y_max")
        return self

    def as_list(self) -> list[float]:
        return [self.x_min, self.y_min, self.x_max, self.y_max]


class Observation(BaseModel):
    """One damage finding fed into costing (from the legacy flat list or the v2 pipeline)."""
    damage_id: str
    component: str                       # normalised vocabulary name (may be ambiguous legacy)
    component_reported: str              # what the input actually said
    damage_type: str
    severity: str
    location: str
    confidence: float = Field(ge=0.0, le=1.0)
    uncertain: bool = False
    # True when strong views disagree on severity by two levels (set by src.fuse). Optional and
    # defaulting to False, so legacy/sample damage maps still validate.
    severity_unresolved: bool = False
    views_supporting: int = 1
    image_ids: list[str] = []
    evidence: str = ""
    severity_rationale: str = ""
    bbox_by_image: dict[str, Optional[list[float]]] = {}
    per_image: list[dict[str, Any]] = []
    localization_note: str = ""
    legacy: bool = False

    @field_validator("bbox_by_image")
    @classmethod
    def _boxes(cls, v):
        for image_id, box in v.items():
            if box is not None:
                if len(box) != 4:
                    raise ValueError(f"box for {image_id} needs 4 values")
                BBox(x_min=box[0], y_min=box[1], x_max=box[2], y_max=box[3])
        return v

    @model_validator(mode="after")
    def _box_images(self):
        unknown = set(self.bbox_by_image) - set(self.image_ids)
        if self.image_ids and unknown:
            raise ValueError(f"boxes refer to images not linked to this observation: {sorted(unknown)}")
        return self

    @field_validator("damage_type")
    @classmethod
    def _dt(cls, v):
        if v not in DAMAGE_TYPES:
            raise ValueError(f"unknown damage_type '{v}'")
        return v

    @field_validator("severity")
    @classmethod
    def _sev(cls, v):
        if v not in SEVERITIES:
            raise ValueError(f"unknown severity '{v}'")
        return v

    @field_validator("location")
    @classmethod
    def _loc(cls, v):
        if v not in LOCATIONS:
            raise ValueError(f"unknown location '{v}'")
        return v


# --------------------------------------------------------------------------- estimate
class LineCost(BaseModel):
    operation: Operation
    record_id: str
    currency: str
    tax_included: bool
    parts_low: Decimal
    parts_high: Decimal
    labor_low: Decimal
    labor_high: Decimal
    paint_materials_low: Decimal
    paint_materials_high: Decimal
    low: Decimal
    high: Decimal
    formula: str = ("low = parts_low + labor_hours_low*labor_rate_low + paint_materials_low; "
                    "high = parts_high + labor_hours_high*labor_rate_high + paint_materials_high")


class Scenario(BaseModel):
    """An alternative operation kept open because photos cannot resolve it."""
    operation: Operation
    description: str
    pricing_status: PricingStatus
    cost: Optional[LineCost] = None
    evidence_record_ids: list[str] = []


class ComponentPlan(BaseModel):
    component_instance: str
    component_class: str
    components_reported: list[str]
    ambiguous: bool = False
    clarification: Optional[str] = None
    damage_ids: list[str]
    damage_types: list[str]
    max_severity: str
    action: Action
    operation: Optional[Operation] = None
    rule_id: str
    rule_version: str
    reason: str
    covered_damage_note: str = ""
    alternatives: list[Scenario] = []
    pricing_status: PricingStatus
    retrieval: Optional[RetrievalResult] = None
    selected_record_id: Optional[str] = None
    cost: Optional[LineCost] = None
    explanation: str = ""
    notes: list[str] = []


class Totals(BaseModel):
    currency: str
    status: Literal["complete", "partial", "insufficient_pricing_data", "no_damage"]
    status_label: str
    tax_basis: Literal["excl_tax", "incl_tax", "mixed", "n/a"]
    observed_low: Optional[Decimal] = None
    observed_high: Optional[Decimal] = None
    tax_rate: Optional[Decimal] = None
    tax_low: Optional[Decimal] = None
    tax_high: Optional[Decimal] = None
    observed_with_tax_low: Optional[Decimal] = None
    observed_with_tax_high: Optional[Decimal] = None
    unresolved_low: Optional[Decimal] = None
    unresolved_high: Optional[Decimal] = None
    envelope_low: Optional[Decimal] = None
    envelope_high: Optional[Decimal] = None
    priced_components: list[str] = []
    unresolved_components: list[str] = []
    unpriced_components: list[str] = []
    notes: list[str] = []


class Uncertainty(BaseModel):
    level: Literal["low", "medium", "high"]
    points: int
    reasons: list[str]
    method: str = ("Heuristic count of documented risk factors (coverage, unresolved findings, "
                   "applicability, provenance, missing prices). Not a statistical interval "
                   "or an accuracy probability.")


class VehicleInfo(BaseModel):
    make: str = ""
    model: str = ""
    year: Optional[int] = None
    variant: str = ""
    reg_no: str = ""
    source: str = "user_supplied"

    @field_validator("year", mode="before")
    @classmethod
    def _year(cls, v):
        if v in (None, "", 0, "0"):
            return None
        v = int(v)
        if not 1980 <= v <= 2100:
            raise ValueError("vehicle year out of range")
        return v


class PricingScope(BaseModel):
    region: str
    currency: str
    part_grade_preference: Literal["oem", "aftermarket"] = "oem"
    tax_rate: Optional[Decimal] = None


class Assessment(BaseModel):
    schema_version: str = SCHEMA_VERSION
    assessment_id: str
    created_at: datetime = Field(default_factory=utcnow)
    mode: Literal["live", "sample_fixture", "legacy_json"]
    disclaimer: str = DISCLAIMER
    pricing_label: Optional[str] = None
    vehicle: VehicleInfo
    pricing_scope: PricingScope
    accident_description: Optional[str] = None
    damage_map: dict[str, Any]
    observations: list[Observation]
    component_plans: list[ComponentPlan]
    totals: Totals
    uncertainty: Uncertainty
    assumptions: list[str] = []
    exclusions: list[str] = []
    warnings: list[str] = []
    provenance: dict[str, Any] = {}
