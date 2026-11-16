"""Tests for the Indian Passenger Vehicle Catalog (src/kb/vehicles.py)."""
from pathlib import Path
import pytest

from src.kb.vehicles import (
    get_manufacturers,
    get_models_for_make,
    get_model_record,
    get_years_for_model,
    get_variants_for_model_year,
    search_models,
    normalize_make,
    check_pricing_coverage,
    validate_catalog,
    load_vehicle_catalog,
)
from src.kb.records import load_corpus
from src import settings


def test_catalog_integrity():
    """Verify the local catalog JSON has no duplicates, missing fields, or invalid URLs."""
    errors = validate_catalog()
    assert not errors, f"Catalog validation errors: {errors}"


def test_manufacturers_list():
    """Verify all 13 required target manufacturers exist in alphabetical order."""
    makes = get_manufacturers()
    expected = [
        "Citroen", "Honda", "Hyundai", "Kia", "MG", "Mahindra",
        "Maruti Suzuki", "Nissan", "Renault", "Skoda", "Tata", "Toyota", "Volkswagen"
    ]
    for exp in expected:
        assert exp in makes, f"Expected manufacturer '{exp}' not found in {makes}"
    assert makes == sorted(makes)


def test_models_for_make():
    """Verify models are returned exclusively for the selected manufacturer."""
    hyundai_models = get_models_for_make("Hyundai")
    assert "i20" in hyundai_models
    assert "Creta" in hyundai_models
    assert "Nexon" not in hyundai_models  # Nexon belongs to Tata
    assert "Swift" not in hyundai_models  # Swift belongs to Maruti

    tata_models = get_models_for_make("Tata")
    assert "Nexon" in tata_models
    assert "Punch" in tata_models
    assert "i20" not in tata_models


def test_alias_normalization():
    """Verify brand aliases resolve to canonical brand names."""
    assert normalize_make("Maruti") == "Maruti Suzuki"
    assert normalize_make("maruti suzuki") == "Maruti Suzuki"
    assert normalize_make("MSIL") == "Maruti Suzuki"
    assert normalize_make("TATA") == "Tata"
    assert normalize_make("Tata Motors") == "Tata"
    assert normalize_make("VW") == "Volkswagen"
    assert normalize_make("volkswagen") == "Volkswagen"
    assert normalize_make("Skoda") == "Skoda"
    assert normalize_make("Škoda") == "Skoda"
    assert normalize_make("UnknownMake") == "UnknownMake"


def test_years_and_variants_for_model():
    """Verify year-dependent variant lookup."""
    years = get_years_for_model("Hyundai", "i20")
    assert 2022 in years and 2024 in years

    variants_2024 = get_variants_for_model_year("Hyundai", "i20", 2024)
    assert "Sportz" in variants_2024
    assert "Asta" in variants_2024

    # Maruti Swift 4th gen vs 3rd gen
    swift_2025_vars = get_variants_for_model_year("Maruti Suzuki", "Swift", 2025)
    assert "ZXi+" in swift_2025_vars

    # Non-existent model returns empty list
    assert get_variants_for_model_year("Hyundai", "NonExistentModel", 2024) == []


def test_discontinued_models_in_2022_2026_window():
    """Verify models sold during 2022-2026 but since discontinued are properly captured."""
    # VW Polo was discontinued in 2022
    polo = get_model_record("Volkswagen", "Polo")
    assert polo is not None
    assert 2022 in polo.years
    assert 2025 not in polo.years  # Not sold in 2025

    # Honda Jazz was discontinued in 2023
    jazz = get_model_record("Honda", "Jazz")
    assert jazz is not None
    assert 2022 in jazz.years and 2023 in jazz.years
    assert 2026 not in jazz.years


def test_search_models_fuzzy_and_aliases():
    """Verify search returns correct matches across canonical names and aliases."""
    res1 = search_models("swift")
    assert any(m.model == "Swift" and m.make == "Maruti Suzuki" for m in res1)

    res2 = search_models("nexon", make="Tata")
    assert len(res2) == 1 and res2[0].model == "Nexon"

    # Searching with brand alias in query
    res3 = search_models("maruti baleno")
    assert any(m.model == "Baleno" for m in res3)


def test_pricing_coverage_checker():
    """Verify pricing coverage classifications against the actual corpus."""
    corpus = load_corpus(settings.KNOWLEDGE_DIR)

    # 1. Full pricing coverage
    cov_i20 = check_pricing_coverage("Hyundai", "i20", 2021, corpus=corpus)
    assert cov_i20.status == "full"
    assert cov_i20.record_count >= 10
    assert cov_i20.synthetic is True

    # 2. Partial pricing coverage (Maruti Swift has only front bumper & headlight)
    cov_swift = check_pricing_coverage("Maruti Suzuki", "Swift", 2021, corpus=corpus)
    assert cov_swift.status == "partial"
    assert cov_swift.record_count == 2
    assert "front_bumper" in cov_swift.priced_components

    # 3. Alias check (Maruti -> Maruti Suzuki Swift)
    cov_swift_alias = check_pricing_coverage("Maruti", "Swift", 2021, corpus=corpus)
    assert cov_swift_alias.status == "partial"

    # 4. Recognized vehicle without repair pricing in demo catalog
    cov_nexon = check_pricing_coverage("Tata", "Nexon", 2023, corpus=corpus)
    assert cov_nexon.status == "unpriced_recognized"
    assert cov_nexon.record_count == 0
    assert "Tata Nexon is a verified Indian market vehicle" in cov_nexon.message

    # 5. Unverified manual entry
    cov_custom = check_pricing_coverage("VintageBrand", "UnknownCar", 1995, corpus=corpus)
    assert cov_custom.status == "unverified_manual"
    assert cov_custom.record_count == 0

