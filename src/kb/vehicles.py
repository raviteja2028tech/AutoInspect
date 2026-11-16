"""Indian Passenger Vehicle Catalog (2022-2026), dependent selectors, and pricing coverage.

Provides verified manufacturer, model, generation, year, and variant records for
mainstream budget and mid-range passenger vehicles sold in India during 2022–2026.
Supports alias mapping, dependent selector filtering, and real pricing-corpus coverage checks.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from .. import settings
from .records import Corpus, load_corpus

CATALOG_PATH = Path(settings.KNOWLEDGE_DIR) / "indian_vehicles.json"

# ── Canonical Brand Aliases ──────────────────────────────────────────────────
# Maps lower-cased alias variants to canonical manufacturer name
MAKE_ALIASES: dict[str, str] = {
    "maruti": "Maruti Suzuki",
    "maruti suzuki": "Maruti Suzuki",
    "maruti-suzuki": "Maruti Suzuki",
    "msil": "Maruti Suzuki",
    "nexa": "Maruti Suzuki",
    "hyundai": "Hyundai",
    "hmil": "Hyundai",
    "tata": "Tata",
    "tata motors": "Tata",
    "tmpvl": "Tata",
    "mahindra": "Mahindra",
    "m&m": "Mahindra",
    "mahindra & mahindra": "Mahindra",
    "kia": "Kia",
    "kia india": "Kia",
    "kia motors": "Kia",
    "toyota": "Toyota",
    "toyota kirloskar": "Toyota",
    "toyota bharat": "Toyota",
    "tkm": "Toyota",
    "honda": "Honda",
    "honda cars": "Honda",
    "honda cars india": "Honda",
    "hcil": "Honda",
    "renault": "Renault",
    "renault india": "Renault",
    "nissan": "Nissan",
    "nissan india": "Nissan",
    "nissan motor": "Nissan",
    "skoda": "Skoda",
    "škoda": "Skoda",
    "skoda auto": "Skoda",
    "volkswagen": "Volkswagen",
    "vw": "Volkswagen",
    "vw india": "Volkswagen",
    "mg": "MG",
    "mg motor": "MG",
    "morris garages": "MG",
    "citroen": "Citroen",
    "citroën": "Citroen",
    "citroen india": "Citroen",
}


def normalize_make(make_input: str | None) -> str:
    """Resolve make alias or common spelling to canonical brand name."""
    if not make_input:
        return ""
    cleaned = make_input.strip()
    return MAKE_ALIASES.get(cleaned.lower(), cleaned)


# ── Catalog Data Structures ──────────────────────────────────────────────────
@dataclass
class CatalogSource:
    title: str
    url: str
    source_date: str | None
    retrieval_date: str
    verification_status: str


@dataclass
class Generation:
    name: str
    years: list[int]
    variants: list[str]


@dataclass
class VehicleModel:
    id: str
    make: str
    model: str
    make_aliases: list[str]
    model_aliases: list[str]
    body_type: str
    years: list[int]
    generations: list[Generation]
    fuel_types: list[str]
    transmissions: list[str]
    source: CatalogSource
    known_gaps: str = ""

    def applies_to_year(self, year: int) -> bool:
        return year in self.years

    def get_variants_for_year(self, year: int | None) -> list[str]:
        if year is None:
            # Union of all variants
            seen = set()
            out = []
            for g in self.generations:
                for v in g.variants:
                    if v not in seen:
                        seen.add(v)
                        out.append(v)
            return out

        variants_for_year: list[str] = []
        for g in self.generations:
            if year in g.years:
                for v in g.variants:
                    if v not in variants_for_year:
                        variants_for_year.append(v)

        if not variants_for_year:
            # Fallback to all variants if specific year generation not isolated
            for g in self.generations:
                for v in g.variants:
                    if v not in variants_for_year:
                        variants_for_year.append(v)
        return variants_for_year


# In-memory cached catalog
_CATALOG_CACHE: dict[str, VehicleModel] | None = None
_CATALOG_BY_MAKE: dict[str, list[VehicleModel]] | None = None


def load_vehicle_catalog(path: Path | None = None, reload: bool = False) -> dict[str, VehicleModel]:
    """Load the verified Indian vehicle catalog from JSON."""
    global _CATALOG_CACHE, _CATALOG_BY_MAKE
    if _CATALOG_CACHE is not None and not reload:
        return _CATALOG_CACHE

    p = path or CATALOG_PATH
    if not p.exists():
        _CATALOG_CACHE = {}
        _CATALOG_BY_MAKE = {}
        return _CATALOG_CACHE

    raw = json.loads(p.read_text(encoding="utf-8"))
    models_dict = {}
    by_make: dict[str, list[VehicleModel]] = {}

    for item in raw.get("models", []):
        src_data = item.get("source", {})
        source = CatalogSource(
            title=src_data.get("title", "Official OEM Documentation"),
            url=src_data.get("url", ""),
            source_date=src_data.get("source_date"),
            retrieval_date=src_data.get("retrieval_date", "2026-11-15"),
            verification_status=src_data.get("verification_status", "verified_oem"),
        )
        generations = [
            Generation(
                name=g.get("name", "Standard Generation"),
                years=g.get("years", []),
                variants=g.get("variants", []),
            )
            for g in item.get("generations", [])
        ]
        vm = VehicleModel(
            id=item["id"],
            make=item["make"],
            model=item["model"],
            make_aliases=item.get("make_aliases", []),
            model_aliases=item.get("model_aliases", []),
            body_type=item.get("body_type", "Passenger Car"),
            years=item.get("years", []),
            generations=generations,
            fuel_types=item.get("fuel_types", []),
            transmissions=item.get("transmissions", []),
            source=source,
            known_gaps=item.get("known_gaps", ""),
        )
        models_dict[vm.id] = vm
        by_make.setdefault(vm.make, []).append(vm)

    _CATALOG_CACHE = models_dict
    _CATALOG_BY_MAKE = by_make
    return _CATALOG_CACHE


def get_manufacturers(catalog_path: Path | None = None) -> list[str]:
    """Return sorted list of verified manufacturers in the catalog."""
    load_vehicle_catalog(catalog_path)
    if _CATALOG_BY_MAKE:
        return sorted(_CATALOG_BY_MAKE.keys())
    return [
        "Maruti Suzuki", "Hyundai", "Tata", "Mahindra", "Kia", "Toyota",
        "Honda", "Renault", "Nissan", "Skoda", "Volkswagen", "MG", "Citroen",
    ]


def get_models_for_make(make: str, catalog_path: Path | None = None) -> list[str]:
    """Return sorted list of verified canonical model names for the selected manufacturer."""
    canon_make = normalize_make(make)
    load_vehicle_catalog(catalog_path)
    if _CATALOG_BY_MAKE and canon_make in _CATALOG_BY_MAKE:
        return sorted(vm.model for vm in _CATALOG_BY_MAKE[canon_make])
    return []


def get_model_record(make: str, model: str, catalog_path: Path | None = None) -> VehicleModel | None:
    """Retrieve full record for a make and model."""
    canon_make = normalize_make(make)
    models = load_vehicle_catalog(catalog_path)
    for vm in models.values():
        if vm.make.lower() == canon_make.lower() and vm.model.lower() == model.strip().lower():
            return vm
        # Check aliases
        if vm.make.lower() == canon_make.lower() and any(a.lower() == model.strip().lower() for a in vm.model_aliases):
            return vm
    return None


def get_years_for_model(make: str, model: str, catalog_path: Path | None = None) -> list[int]:
    """Return descending list of supported years for a model."""
    vm = get_model_record(make, model, catalog_path)
    if vm and vm.years:
        return sorted(vm.years, reverse=True)
    # Default 2022-2026 range if not in catalog
    return [2026, 2025, 2024, 2023, 2022]


def get_variants_for_model_year(
    make: str, model: str, year: int | None, catalog_path: Path | None = None
) -> list[str]:
    """Return verified variants for the selected model and year."""
    vm = get_model_record(make, model, catalog_path)
    if vm:
        return vm.get_variants_for_year(year)
    return []


def search_models(query: str, make: str | None = None, catalog_path: Path | None = None) -> list[VehicleModel]:
    """Search catalog using case-insensitive substring, multi-token matching, and aliases."""
    catalog = load_vehicle_catalog(catalog_path)
    q = query.strip().lower()
    if not q and not make:
        return list(catalog.values())

    canon_make = normalize_make(make) if make else None
    results = []
    tokens = q.split()

    for vm in catalog.values():
        if canon_make and vm.make.lower() != canon_make.lower():
            continue
        if not q:
            results.append(vm)
            continue

        # Build searchable string pool for this vehicle
        text_pool = [
            vm.model.lower(),
            vm.make.lower(),
            f"{vm.make.lower()} {vm.model.lower()}",
            vm.body_type.lower(),
        ]
        text_pool.extend(a.lower() for a in vm.model_aliases)
        text_pool.extend(a.lower() for a in vm.make_aliases)
        for a in vm.make_aliases:
            text_pool.append(f"{a.lower()} {vm.model.lower()}")

        combined_text = " ".join(text_pool)

        # Match exact substring OR all tokens present in text pool
        if q in combined_text or all(tok in combined_text for tok in tokens):
            results.append(vm)
    return results


# ── Real Pricing Coverage Checker ────────────────────────────────────────────
@dataclass
class PricingCoverage:
    status: str  # 'full' | 'partial' | 'unpriced_recognized' | 'unverified_manual'
    status_label: str
    record_count: int
    priced_components: list[str]
    synthetic: bool
    message: str


def check_pricing_coverage(
    make: str,
    model: str,
    year: int | None,
    corpus: Corpus | None = None,
    catalog_path: Path | None = None,
) -> PricingCoverage:
    """Evaluate real pricing coverage for a selected vehicle against the knowledge base."""
    canon_make = normalize_make(make)
    model_clean = model.strip()

    # Load corpus if not passed
    if corpus is None:
        try:
            corpus = load_corpus(settings.KNOWLEDGE_DIR)
        except Exception:
            corpus = None

    matching_records = []
    if corpus:
        for r in corpus.records:
            # Check make match (allowing canonical equivalence like Maruti <-> Maruti Suzuki)
            r_make_canon = normalize_make(r.make)
            if r_make_canon.lower() == canon_make.lower() and r.model.strip().lower() == model_clean.lower():
                if year is None or (r.year_from <= year <= r.year_to):
                    matching_records.append(r)

    # Check if recognized in vehicle catalog
    in_catalog = get_model_record(canon_make, model_clean, catalog_path) is not None

    if matching_records:
        components = sorted(list({r.component for r in matching_records}))
        synthetic = any(r.data_quality == "synthetic_demo" for r in matching_records)
        provenance = "synthetic demonstration records (not market verified)" if synthetic else "verified sourced price records"

        # Check depth of component coverage
        # Major crash components: bumper, hood, doors, lamps, glass
        has_major = {"front_bumper", "hood", "headlight_left"}.issubset(set(components))

        if len(components) >= 8 and has_major:
            return PricingCoverage(
                status="full",
                status_label="Pricing Records Available",
                record_count=len(matching_records),
                priced_components=components,
                synthetic=synthetic,
                message=f"Pricing database covers {len(matching_records)} operations across {len(components)} components for {canon_make} {model_clean} ({provenance}).",
            )
        else:
            comp_sample = ", ".join(components[:4])
            return PricingCoverage(
                status="partial",
                status_label="Partial Pricing Coverage",
                record_count=len(matching_records),
                priced_components=components,
                synthetic=synthetic,
                message=f"Partial pricing available ({len(matching_records)} records covering: {comp_sample}). Unpriced findings will be reported as unknown costs (not zero).",
            )

    if in_catalog:
        return PricingCoverage(
            status="unpriced_recognized",
            status_label="Vehicle Recognized · Pricing Unavailable",
            record_count=0,
            priced_components=[],
            synthetic=False,
            message=f"{canon_make} {model_clean} is a verified Indian market vehicle (2022–2026), but parts pricing is not yet entered in the demonstration catalog. Damage detection and rule recommendations will run normally; cost lines will be listed as unpriced.",
        )

    return PricingCoverage(
        status="unverified_manual",
        status_label="Manual Vehicle Entry · Unverified Catalog Match",
        record_count=0,
        priced_components=[],
        synthetic=False,
        message="Vehicle details were entered manually and do not match the pre-verified 2022–2026 catalog or pricing database. Assessment will proceed using standard component rules.",
    )


# ── Validation & Integrity CLI ───────────────────────────────────────────────
def validate_catalog(path: Path | None = None) -> list[str]:
    """Rigorous integrity verification of the vehicle catalog file."""
    p = path or CATALOG_PATH
    if not p.exists():
        return [f"Catalog file does not exist: {p}"]

    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"Malformed JSON in catalog: {exc}"]

    errors = []
    models = data.get("models", [])
    if not models:
        errors.append("No models found in catalog.")

    seen_ids = set()
    for idx, m in enumerate(models, 1):
        mid = m.get("id")
        if not mid:
            errors.append(f"Model #{idx} is missing an 'id'.")
        elif mid in seen_ids:
            errors.append(f"Duplicate model id '{mid}'.")
        seen_ids.add(mid)

        make = m.get("make")
        if not make or not isinstance(make, str):
            errors.append(f"{mid}: invalid or missing 'make'.")

        model_name = m.get("model")
        if not model_name or not isinstance(model_name, str):
            errors.append(f"{mid}: invalid or missing 'model'.")

        years = m.get("years", [])
        if not years or not all(isinstance(y, int) and 2000 <= y <= 2030 for y in years):
            errors.append(f"{mid}: invalid or empty years list {years}.")

        generations = m.get("generations", [])
        if not generations:
            errors.append(f"{mid}: no generations defined.")
        for g in generations:
            if not g.get("name"):
                errors.append(f"{mid}: generation missing 'name'.")
            if not g.get("variants"):
                errors.append(f"{mid}: generation '{g.get('name')}' has empty variants list.")

        src = m.get("source", {})
        if not src.get("title"):
            errors.append(f"{mid}: source missing 'title'.")
        if not src.get("url") or not src.get("url").startswith("http"):
            errors.append(f"{mid}: source has invalid or non-HTTP 'url': '{src.get('url')}'.")

    return errors


def main():
    parser = argparse.ArgumentParser(description="Validate or query the Indian Vehicle Catalog.")
    parser.add_argument("--validate", action="store_true", help="Run comprehensive catalog integrity validation")
    parser.add_argument("--catalog", type=Path, default=CATALOG_PATH, help="Path to catalog JSON")
    parser.add_argument("--make", help="Filter by manufacturer")
    parser.add_argument("--search", help="Search query")
    args = parser.parse_args()

    if args.validate:
        errs = validate_catalog(args.catalog)
        if errs:
            print(f"FAILED: {len(errs)} integrity error(s) found:")
            for e in errs:
                print(f"  • {e}")
            raise SystemExit(1)
        models = load_vehicle_catalog(args.catalog, reload=True)
        makes = get_manufacturers(args.catalog)
        print(f"VALID: {len(models)} models verified across {len(makes)} manufacturers.")
        print(f"Manufacturers: {', '.join(makes)}")
        return

    if args.search or args.make:
        res = search_models(args.search or "", make=args.make, catalog_path=args.catalog)
        print(f"Found {len(res)} model(s):")
        for vm in res:
            print(f"  • {vm.make} {vm.model} ({min(vm.years)}-{max(vm.years)}) — {len(vm.get_variants_for_year(None))} variants")
        return

    parser.print_help()


if __name__ == "__main__":
    main()
