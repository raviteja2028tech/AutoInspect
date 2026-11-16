"""Build knowledge/indian_vehicles.json (Indian passenger vehicle catalog, 2022-2026).

    python -m src.kb.generate_catalog            # rewrites the catalog from VEHICLES below
    python -m src.kb.vehicles --validate         # then validate it

Importing this module has no side effects; the file is only written by main().
"""
import json
from pathlib import Path

from .. import settings

VEHICLES = [
    # ── 1. Maruti Suzuki ────────────────────────────────────────────────────────
    {
        "id": "maruti-suzuki-swift",
        "make": "Maruti Suzuki",
        "model": "Swift",
        "make_aliases": ["Maruti", "MSIL", "Maruti-Suzuki"],
        "model_aliases": ["Swift", "New Swift", "Swift 2024", "Maruti Swift"],
        "body_type": "Hatchback",
        "years": [2022, 2023, 2024, 2025, 2026],
        "generations": [
            {
                "name": "3rd Generation Facelift",
                "years": [2022, 2023, 2024],
                "variants": ["LXi", "VXi", "ZXi", "ZXi+"]
            },
            {
                "name": "4th Generation (Z-Series)",
                "years": [2024, 2025, 2026],
                "variants": ["LXi", "VXi", "VXi (O)", "ZXi", "ZXi+"]
            }
        ],
        "fuel_types": ["Petrol", "CNG"],
        "transmissions": ["Manual (5-speed)", "AMT (5-speed)"],
        "source": {
            "title": "Maruti Suzuki Official Swift Specifications",
            "url": "https://www.marutisuzuki.com/swift",
            "source_date": "2024-05-09",
            "retrieval_date": "2026-11-15",
            "verification_status": "verified_oem"
        },
        "known_gaps": "Special edition trims (e.g. Blitz Edition) share core body panels with base trims."
    },
    {
        "id": "maruti-suzuki-baleno",
        "make": "Maruti Suzuki",
        "model": "Baleno",
        "make_aliases": ["Maruti", "MSIL", "Nexa"],
        "model_aliases": ["Baleno", "New Baleno", "Nexa Baleno"],
        "body_type": "Premium Hatchback",
        "years": [2022, 2023, 2024, 2025, 2026],
        "generations": [
            {
                "name": "2nd Generation (New Baleno)",
                "years": [2022, 2023, 2024, 2025, 2026],
                "variants": ["Sigma", "Delta", "Zeta", "Alpha"]
            }
        ],
        "fuel_types": ["Petrol", "CNG"],
        "transmissions": ["Manual (5-speed)", "AGS (AMT)"],
        "source": {
            "title": "Nexa Experience Baleno Specifications",
            "url": "https://www.nexaexperience.com/baleno",
            "source_date": "2023-11-01",
            "retrieval_date": "2026-11-15",
            "verification_status": "verified_oem"
        },
        "known_gaps": "Regal Edition accessory packs map to Sigma/Delta/Zeta/Alpha."
    },
    {
        "id": "maruti-suzuki-brezza",
        "make": "Maruti Suzuki",
        "model": "Brezza",
        "make_aliases": ["Maruti", "MSIL"],
        "model_aliases": ["Brezza", "Vitara Brezza", "New Brezza"],
        "body_type": "Compact SUV",
        "years": [2022, 2023, 2024, 2025, 2026],
        "generations": [
            {
                "name": "2nd Generation (Brezza)",
                "years": [2022, 2023, 2024, 2025, 2026],
                "variants": ["LXi", "VXi", "ZXi", "ZXi+"]
            }
        ],
        "fuel_types": ["Petrol", "CNG"],
        "transmissions": ["Manual (5-speed)", "Automatic (6-speed TC)"],
        "source": {
            "title": "Maruti Suzuki Brezza Official Page",
            "url": "https://www.marutisuzuki.com/brezza",
            "source_date": "2024-01-10",
            "retrieval_date": "2026-11-15",
            "verification_status": "verified_oem"
        },
        "known_gaps": "Earlier generation called Vitara Brezza (pre-June 2022)."
    },
    {
        "id": "maruti-suzuki-dzire",
        "make": "Maruti Suzuki",
        "model": "Dzire",
        "make_aliases": ["Maruti", "MSIL"],
        "model_aliases": ["Dzire", "Swift Dzire", "New Dzire"],
        "body_type": "Compact Sedan",
        "years": [2022, 2023, 2024, 2025, 2026],
        "generations": [
            {
                "name": "3rd Generation",
                "years": [2022, 2023, 2024],
                "variants": ["LXi", "VXi", "ZXi", "ZXi+"]
            },
            {
                "name": "4th Generation (All-New Dzire)",
                "years": [2024, 2025, 2026],
                "variants": ["LXi", "VXi", "ZXi", "ZXi+"]
            }
        ],
        "fuel_types": ["Petrol", "CNG"],
        "transmissions": ["Manual (5-speed)", "AMT (5-speed)"],
        "source": {
            "title": "Maruti Suzuki All-New Dzire Official",
            "url": "https://www.marutisuzuki.com/dzire",
            "source_date": "2024-11-11",
            "retrieval_date": "2026-11-15",
            "verification_status": "verified_oem"
        },
        "known_gaps": "4th Gen launched November 2024 with distinct sheet metal from Swift."
    },
    {
        "id": "maruti-suzuki-fronx",
        "make": "Maruti Suzuki",
        "model": "Fronx",
        "make_aliases": ["Maruti", "MSIL", "Nexa"],
        "model_aliases": ["Fronx", "Nexa Fronx"],
        "body_type": "Crossover SUV",
        "years": [2023, 2024, 2025, 2026],
        "generations": [
            {
                "name": "1st Generation",
                "years": [2023, 2024, 2025, 2026],
                "variants": ["Sigma", "Delta", "Delta+", "Delta+ (O)", "Zeta", "Alpha"]
            }
        ],
        "fuel_types": ["Petrol", "Turbo Petrol (1.0L Boosterjet)", "CNG"],
        "transmissions": ["Manual (5-speed)", "AGS (AMT)", "Automatic (6-speed TC)"],
        "source": {
            "title": "Nexa Experience Fronx Official",
            "url": "https://www.nexaexperience.com/fronx",
            "source_date": "2023-04-24",
            "retrieval_date": "2026-11-15",
            "verification_status": "verified_oem"
        },
        "known_gaps": "Not sold in India in 2022 (introduced April 2023)."
    },
    {
        "id": "maruti-suzuki-grand-vitara",
        "make": "Maruti Suzuki",
        "model": "Grand Vitara",
        "make_aliases": ["Maruti", "MSIL", "Nexa"],
        "model_aliases": ["Grand Vitara", "GV"],
        "body_type": "Mid-size SUV",
        "years": [2022, 2023, 2024, 2025, 2026],
        "generations": [
            {
                "name": "1st Generation",
                "years": [2022, 2023, 2024, 2025, 2026],
                "variants": ["Sigma", "Delta", "Zeta", "Zeta+ Hybrid", "Alpha", "Alpha+ Hybrid"]
            }
        ],
        "fuel_types": ["Petrol", "Strong Hybrid", "CNG"],
        "transmissions": ["Manual (5-speed)", "Automatic (6-speed)", "e-CVT", "ALLGRIP 4WD"],
        "source": {
            "title": "Nexa Experience Grand Vitara",
            "url": "https://www.nexaexperience.com/grand-vitara",
            "source_date": "2022-09-26",
            "retrieval_date": "2026-11-15",
            "verification_status": "verified_oem"
        },
        "known_gaps": "Strong hybrid trims share powertrain with Toyota Urban Cruiser Hyryder."
    },
    {
        "id": "maruti-suzuki-wagon-r",
        "make": "Maruti Suzuki",
        "model": "Wagon R",
        "make_aliases": ["Maruti", "MSIL"],
        "model_aliases": ["Wagon R", "WagonR"],
        "body_type": "Tallboy Hatchback",
        "years": [2022, 2023, 2024, 2025, 2026],
        "generations": [
            {
                "name": "3rd Generation Facelift",
                "years": [2022, 2023, 2024, 2025, 2026],
                "variants": ["LXi", "VXi", "ZXi", "ZXi+"]
            }
        ],
        "fuel_types": ["Petrol (1.0L/1.2L)", "CNG"],
        "transmissions": ["Manual (5-speed)", "AGS (AMT)"],
        "source": {
            "title": "Maruti Suzuki Wagon R Official",
            "url": "https://www.marutisuzuki.com/wagonr",
            "source_date": "2023-01-15",
            "retrieval_date": "2026-11-15",
            "verification_status": "verified_oem"
        },
        "known_gaps": "1.0L engine on LXi/VXi, 1.2L on ZXi/ZXi+."
    },
    {
        "id": "maruti-suzuki-ertiga",
        "make": "Maruti Suzuki",
        "model": "Ertiga",
        "make_aliases": ["Maruti", "MSIL"],
        "model_aliases": ["Ertiga"],
        "body_type": "MPV",
        "years": [2022, 2023, 2024, 2025, 2026],
        "generations": [
            {
                "name": "2nd Generation Facelift",
                "years": [2022, 2023, 2024, 2025, 2026],
                "variants": ["LXi", "VXi", "ZXi", "ZXi+"]
            }
        ],
        "fuel_types": ["Petrol", "CNG"],
        "transmissions": ["Manual (5-speed)", "Automatic (6-speed TC)"],
        "source": {
            "title": "Maruti Suzuki Ertiga Official",
            "url": "https://www.marutisuzuki.com/ertiga",
            "source_date": "2022-04-15",
            "retrieval_date": "2026-11-15",
            "verification_status": "verified_oem"
        },
        "known_gaps": "Commercial Tour M variant not tracked in retail passenger list."
    },

    # ── 2. Hyundai ──────────────────────────────────────────────────────────────
    {
        "id": "hyundai-i20",
        "make": "Hyundai",
        "model": "i20",
        "make_aliases": ["Hyundai", "HMIL"],
        "model_aliases": ["i20", "Elite i20", "New i20", "i20 N Line"],
        "body_type": "Premium Hatchback",
        "years": [2022, 2023, 2024, 2025, 2026],
        "generations": [
            {
                "name": "3rd Generation",
                "years": [2022, 2023],
                "variants": ["Magna", "Sportz", "Asta", "Asta (O)", "N Line N6", "N Line N8"]
            },
            {
                "name": "3rd Generation Facelift",
                "years": [2023, 2024, 2025, 2026],
                "variants": ["Era", "Magna", "Sportz", "Sportz (O)", "Asta", "Asta (O)", "N Line N6", "N Line N8"]
            }
        ],
        "fuel_types": ["Petrol (1.2L)", "Turbo Petrol (1.0L T-GDi)"],
        "transmissions": ["Manual (5-speed)", "IVT (CVT)", "DCT (7-speed)"],
        "source": {
            "title": "Hyundai Motor India Official i20 Page",
            "url": "https://www.hyundai.com/in/en/find-a-car/i20",
            "source_date": "2023-09-08",
            "retrieval_date": "2026-11-15",
            "verification_status": "verified_oem"
        },
        "known_gaps": "Diesel option discontinued prior to 2023 BS6 Phase-2 transition."
    },
    {
        "id": "hyundai-creta",
        "make": "Hyundai",
        "model": "Creta",
        "make_aliases": ["Hyundai", "HMIL"],
        "model_aliases": ["Creta", "New Creta", "Creta N Line"],
        "body_type": "Mid-size SUV",
        "years": [2022, 2023, 2024, 2025, 2026],
        "generations": [
            {
                "name": "2nd Generation Pre-Facelift",
                "years": [2022, 2023],
                "variants": ["E", "EX", "S", "S+", "SX", "SX Executive", "SX(O)"]
            },
            {
                "name": "2nd Generation Major Facelift",
                "years": [2024, 2025, 2026],
                "variants": ["E", "EX", "S", "S(O)", "SX", "SX Tech", "SX(O)", "N Line N8", "N Line N10"]
            }
        ],
        "fuel_types": ["Petrol (1.5L)", "Diesel (1.5L CRDi)", "Turbo Petrol (1.5L T-GDi)"],
        "transmissions": ["Manual (6-speed)", "IVT", "Automatic (6-speed TC)", "DCT (7-speed)"],
        "source": {
            "title": "Hyundai Motor India Creta Page",
            "url": "https://www.hyundai.com/in/en/find-a-car/creta",
            "source_date": "2024-01-16",
            "retrieval_date": "2026-11-15",
            "verification_status": "verified_oem"
        },
        "known_gaps": "Facelift introduced January 2024 with altered front/rear fascia."
    },
    {
        "id": "hyundai-venue",
        "make": "Hyundai",
        "model": "Venue",
        "make_aliases": ["Hyundai", "HMIL"],
        "model_aliases": ["Venue", "New Venue", "Venue N Line"],
        "body_type": "Compact SUV",
        "years": [2022, 2023, 2024, 2025, 2026],
        "generations": [
            {
                "name": "1st Generation Facelift",
                "years": [2022, 2023, 2024, 2025, 2026],
                "variants": ["E", "S", "S(O)", "S+", "SX", "SX(O)", "N Line N6", "N Line N8"]
            }
        ],
        "fuel_types": ["Petrol (1.2L)", "Diesel (1.5L CRDi)", "Turbo Petrol (1.0L)"],
        "transmissions": ["Manual (5/6-speed)", "DCT (7-speed)"],
        "source": {
            "title": "Hyundai Venue Specifications",
            "url": "https://www.hyundai.com/in/en/find-a-car/venue",
            "source_date": "2023-05-10",
            "retrieval_date": "2026-11-15",
            "verification_status": "verified_oem"
        },
        "known_gaps": "iMT transmission discontinued in 2023 in favor of standard manual."
    },
    {
        "id": "hyundai-exter",
        "make": "Hyundai",
        "model": "Exter",
        "make_aliases": ["Hyundai", "HMIL"],
        "model_aliases": ["Exter"],
        "body_type": "Micro SUV",
        "years": [2023, 2024, 2025, 2026],
        "generations": [
            {
                "name": "1st Generation",
                "years": [2023, 2024, 2025, 2026],
                "variants": ["EX", "EX(O)", "S", "S(O)", "SX", "SX(O)", "SX(O) Connect", "Knight Edition"]
            }
        ],
        "fuel_types": ["Petrol (1.2L)", "CNG (Hy-CNG)"],
        "transmissions": ["Manual (5-speed)", "Smart Auto (AMT)"],
        "source": {
            "title": "Hyundai Exter Official Specifications",
            "url": "https://www.hyundai.com/in/en/find-a-car/exter",
            "source_date": "2023-07-10",
            "retrieval_date": "2026-11-15",
            "verification_status": "verified_oem"
        },
        "known_gaps": "Introduced July 2023; not present in 2022."
    },
    {
        "id": "hyundai-verna",
        "make": "Hyundai",
        "model": "Verna",
        "make_aliases": ["Hyundai", "HMIL"],
        "model_aliases": ["Verna", "New Verna"],
        "body_type": "Mid-size Sedan",
        "years": [2022, 2023, 2024, 2025, 2026],
        "generations": [
            {
                "name": "5th Generation",
                "years": [2022, 2023],
                "variants": ["E", "S+", "SX", "SX(O)"]
            },
            {
                "name": "6th Generation (All-New)",
                "years": [2023, 2024, 2025, 2026],
                "variants": ["EX", "S", "SX", "SX(O)", "SX Turbo", "SX(O) Turbo"]
            }
        ],
        "fuel_types": ["Petrol (1.5L)", "Turbo Petrol (1.5L T-GDi)"],
        "transmissions": ["Manual (6-speed)", "IVT", "DCT (7-speed)"],
        "source": {
            "title": "Hyundai All-New Verna Official",
            "url": "https://www.hyundai.com/in/en/find-a-car/verna",
            "source_date": "2023-03-21",
            "retrieval_date": "2026-11-15",
            "verification_status": "verified_oem"
        },
        "known_gaps": "Diesel engine dropped entirely with 6th Gen introduction in March 2023."
    },

    # ── 3. Tata Motors ──────────────────────────────────────────────────────────
    {
        "id": "tata-nexon",
        "make": "Tata",
        "model": "Nexon",
        "make_aliases": ["Tata", "Tata Motors", "TMPVL"],
        "model_aliases": ["Nexon", "New Nexon", "Nexon ICE"],
        "body_type": "Compact SUV",
        "years": [2022, 2023, 2024, 2025, 2026],
        "generations": [
            {
                "name": "1st Gen Facelift",
                "years": [2022, 2023],
                "variants": ["XE", "XM", "XM (S)", "XZ+", "XZ+ (HS)", "XZ+ (O)"]
            },
            {
                "name": "Major Facelift (Gen 2 Look)",
                "years": [2023, 2024, 2025, 2026],
                "variants": ["Smart", "Smart+", "Pure", "Pure S", "Creative", "Creative+", "Fearless", "Fearless+ S"]
            }
        ],
        "fuel_types": ["Petrol (1.2L Turbo)", "Diesel (1.5L)", "CNG (iCNG)"],
        "transmissions": ["Manual (5/6-speed)", "AMT (6-speed)", "DCA (7-speed Dual Clutch)"],
        "source": {
            "title": "Tata Motors Passenger Vehicles Nexon",
            "url": "https://cars.tatamotors.com/nexon/ice.html",
            "source_date": "2023-09-14",
            "retrieval_date": "2026-11-15",
            "verification_status": "verified_oem"
        },
        "known_gaps": "Trim naming scheme completely changed from XE/XM/XZ to Smart/Pure/Creative/Fearless in September 2023."
    },
    {
        "id": "tata-punch",
        "make": "Tata",
        "model": "Punch",
        "make_aliases": ["Tata", "Tata Motors"],
        "model_aliases": ["Punch"],
        "body_type": "Micro SUV",
        "years": [2022, 2023, 2024, 2025, 2026],
        "generations": [
            {
                "name": "1st Generation",
                "years": [2022, 2023, 2024, 2025, 2026],
                "variants": ["Pure", "Pure Rhythm", "Adventure", "Adventure Rhythm", "Accomplished", "Accomplished Dazzle", "Creative", "Creative Flagship"]
            }
        ],
        "fuel_types": ["Petrol (1.2L)", "CNG (twin-cylinder iCNG)"],
        "transmissions": ["Manual (5-speed)", "AMT (5-speed)"],
        "source": {
            "title": "Tata Punch Official Brochure",
            "url": "https://cars.tatamotors.com/punch/ice.html",
            "source_date": "2023-08-04",
            "retrieval_date": "2026-11-15",
            "verification_status": "verified_oem"
        },
        "known_gaps": "Camo and Kaziranga limited editions map to Accomplished/Creative trim bases."
    },
    {
        "id": "tata-tiago",
        "make": "Tata",
        "model": "Tiago",
        "make_aliases": ["Tata", "Tata Motors"],
        "model_aliases": ["Tiago"],
        "body_type": "Hatchback",
        "years": [2022, 2023, 2024, 2025, 2026],
        "generations": [
            {
                "name": "1st Gen Facelift",
                "years": [2022, 2023, 2024, 2025, 2026],
                "variants": ["XE", "XM", "XT", "XT Rhythm", "XZ+", "XZ+ Tech"]
            }
        ],
        "fuel_types": ["Petrol", "CNG (iCNG)"],
        "transmissions": ["Manual (5-speed)", "AMT (5-speed)"],
        "source": {
            "title": "Tata Tiago Official Specifications",
            "url": "https://cars.tatamotors.com/tiago/ice.html",
            "source_date": "2024-02-12",
            "retrieval_date": "2026-11-15",
            "verification_status": "verified_oem"
        },
        "known_gaps": "Tiago NRG crossover variant shares mechanical components but has distinct cladding."
    },
    {
        "id": "tata-altroz",
        "make": "Tata",
        "model": "Altroz",
        "make_aliases": ["Tata", "Tata Motors"],
        "model_aliases": ["Altroz", "Altroz Racer"],
        "body_type": "Premium Hatchback",
        "years": [2022, 2023, 2024, 2025, 2026],
        "generations": [
            {
                "name": "1st Generation",
                "years": [2022, 2023, 2024, 2025, 2026],
                "variants": ["XE", "XM", "XM+", "XT", "XZ", "XZ+ (S)", "Racer R1", "Racer R2", "Racer R3"]
            }
        ],
        "fuel_types": ["Petrol", "Turbo Petrol", "Diesel", "CNG"],
        "transmissions": ["Manual (5/6-speed)", "DCA (6-speed Dual Clutch)"],
        "source": {
            "title": "Tata Altroz Official Page",
            "url": "https://cars.tatamotors.com/altroz/ice.html",
            "source_date": "2024-06-11",
            "retrieval_date": "2026-11-15",
            "verification_status": "verified_oem"
        },
        "known_gaps": "Racer performance sub-model added mid-2024 with altered front bumper and spoiler."
    },
    {
        "id": "tata-harrier",
        "make": "Tata",
        "model": "Harrier",
        "make_aliases": ["Tata", "Tata Motors"],
        "model_aliases": ["Harrier", "New Harrier"],
        "body_type": "Mid-size SUV",
        "years": [2022, 2023, 2024, 2025, 2026],
        "generations": [
            {
                "name": "1st Gen Pre-Facelift",
                "years": [2022, 2023],
                "variants": ["XE", "XM", "XT", "XT+", "XZ", "XZ+", "Dark Edition"]
            },
            {
                "name": "Major Facelift",
                "years": [2023, 2024, 2025, 2026],
                "variants": ["Smart", "Pure", "Pure+", "Adventure", "Adventure+", "Fearless", "Fearless+"]
            }
        ],
        "fuel_types": ["Diesel (2.0L Kryotec)"],
        "transmissions": ["Manual (6-speed)", "Automatic (6-speed TC)"],
        "source": {
            "title": "Tata Harrier Official Page",
            "url": "https://cars.tatamotors.com/harrier/ice.html",
            "source_date": "2023-10-17",
            "retrieval_date": "2026-11-15",
            "verification_status": "verified_oem"
        },
        "known_gaps": "Diesel-only model in India; facelift received all-new bumper assemblies and connected lighting."
    },

    # ── 4. Mahindra ─────────────────────────────────────────────────────────────
    {
        "id": "mahindra-scorpio-n",
        "make": "Mahindra",
        "model": "Scorpio-N",
        "make_aliases": ["Mahindra", "M&M", "Mahindra & Mahindra"],
        "model_aliases": ["Scorpio N", "Scorpio-N", "ScorpioN"],
        "body_type": "Ladder-frame SUV",
        "years": [2022, 2023, 2024, 2025, 2026],
        "generations": [
            {
                "name": "1st Generation",
                "years": [2022, 2023, 2024, 2025, 2026],
                "variants": ["Z2", "Z4", "Z6", "Z8", "Z8 Select", "Z8L"]
            }
        ],
        "fuel_types": ["Petrol (2.0L mStallion)", "Diesel (2.2L mHawk)"],
        "transmissions": ["Manual (6-speed)", "Automatic (6-speed TC)", "4XPLOR 4WD"],
        "source": {
            "title": "Mahindra Scorpio-N Official Specifications",
            "url": "https://auto.mahindra.com/suv/scorpio-n",
            "source_date": "2022-06-27",
            "retrieval_date": "2026-11-15",
            "verification_status": "verified_oem"
        },
        "known_gaps": "Sold alongside Scorpio Classic; components are non-interchangeable."
    },
    {
        "id": "mahindra-xuv700",
        "make": "Mahindra",
        "model": "XUV700",
        "make_aliases": ["Mahindra", "M&M"],
        "model_aliases": ["XUV700", "XUV 700"],
        "body_type": "Mid-size SUV",
        "years": [2022, 2023, 2024, 2025, 2026],
        "generations": [
            {
                "name": "1st Generation",
                "years": [2022, 2023, 2024, 2025, 2026],
                "variants": ["MX", "AX3", "AX5", "AX5 Select", "AX7", "AX7L"]
            }
        ],
        "fuel_types": ["Petrol (2.0L mStallion)", "Diesel (2.2L mHawk)"],
        "transmissions": ["Manual (6-speed)", "Automatic (6-speed TC)", "AWD"],
        "source": {
            "title": "Mahindra XUV700 Official Page",
            "url": "https://auto.mahindra.com/suv/xuv700",
            "source_date": "2024-01-20",
            "retrieval_date": "2026-11-15",
            "verification_status": "verified_oem"
        },
        "known_gaps": "Available in 5-seater, 6-seater, and 7-seater body configurations sharing outer body panels."
    },
    {
        "id": "mahindra-thar",
        "make": "Mahindra",
        "model": "Thar",
        "make_aliases": ["Mahindra", "M&M"],
        "model_aliases": ["Thar", "Thar 4x4", "Thar RWD", "Thar Roxx"],
        "body_type": "4x4 Lifestyle SUV",
        "years": [2022, 2023, 2024, 2025, 2026],
        "generations": [
            {
                "name": "2nd Gen 3-Door",
                "years": [2022, 2023, 2024, 2025, 2026],
                "variants": ["AX(O)", "LX", "Earth Edition"]
            },
            {
                "name": "Thar Roxx (5-Door)",
                "years": [2024, 2025, 2026],
                "variants": ["MX1", "MX3", "AX3L", "MX5", "AX5L", "AX7L"]
            }
        ],
        "fuel_types": ["Petrol (1.5L/2.0L)", "Diesel (1.5L/2.2L)"],
        "transmissions": ["Manual (6-speed)", "Automatic (6-speed TC)", "4WD / RWD"],
        "source": {
            "title": "Mahindra Thar and Thar Roxx Official",
            "url": "https://auto.mahindra.com/suv/thar",
            "source_date": "2024-08-15",
            "retrieval_date": "2026-11-15",
            "verification_status": "verified_oem"
        },
        "known_gaps": "Thar Roxx (5-door) introduced August 2024 with extended wheelbase and distinct doors."
    },
    {
        "id": "mahindra-xuv-3xo",
        "make": "Mahindra",
        "model": "XUV 3XO",
        "make_aliases": ["Mahindra", "M&M"],
        "model_aliases": ["XUV 3XO", "XUV3XO", "XUV300"],
        "body_type": "Compact SUV",
        "years": [2022, 2023, 2024, 2025, 2026],
        "generations": [
            {
                "name": "XUV300",
                "years": [2022, 2023, 2024],
                "variants": ["W4", "W6", "W8", "W8(O)", "Turbosport TGDi"]
            },
            {
                "name": "XUV 3XO (Facelift)",
                "years": [2024, 2025, 2026],
                "variants": ["MX1", "MX2", "MX2 Pro", "MX3", "MX3 Pro", "AX5", "AX5L", "AX7", "AX7L"]
            }
        ],
        "fuel_types": ["Petrol (1.2L Turbo / mStallion TGDi)", "Diesel (1.5L)"],
        "transmissions": ["Manual (6-speed)", "Automatic (6-speed Aisin TC)", "AMT (AutoShift)"],
        "source": {
            "title": "Mahindra XUV 3XO Official Launch",
            "url": "https://auto.mahindra.com/suv/xuv-3xo",
            "source_date": "2024-04-29",
            "retrieval_date": "2026-11-15",
            "verification_status": "verified_oem"
        },
        "known_gaps": "Renamed from XUV300 to XUV 3XO with comprehensive re-skinning in April 2024."
    },

    # ── 5. Kia ──────────────────────────────────────────────────────────────────
    {
        "id": "kia-seltos",
        "make": "Kia",
        "model": "Seltos",
        "make_aliases": ["Kia", "Kia India", "Kia Motors"],
        "model_aliases": ["Seltos", "New Seltos"],
        "body_type": "Mid-size SUV",
        "years": [2022, 2023, 2024, 2025, 2026],
        "generations": [
            {
                "name": "1st Gen Pre-Facelift",
                "years": [2022, 2023],
                "variants": ["HTE", "HTK", "HTK+", "HTX", "HTX+", "GTX+", "X-Line"]
            },
            {
                "name": "1st Gen Facelift",
                "years": [2023, 2024, 2025, 2026],
                "variants": ["HTE", "HTK", "HTK+", "HTX", "HTX+", "GTX+", "X-Line"]
            }
        ],
        "fuel_types": ["Petrol (1.5L)", "Diesel (1.5L CRDi)", "Turbo Petrol (1.5L T-GDi)"],
        "transmissions": ["Manual (6-speed)", "iMT (6-speed)", "IVT", "Automatic (6-speed TC)", "DCT (7-speed)"],
        "source": {
            "title": "Kia India Official Seltos Page",
            "url": "https://www.kia.com/in/our-vehicles/seltos.html",
            "source_date": "2023-07-21",
            "retrieval_date": "2026-11-15",
            "verification_status": "verified_oem"
        },
        "known_gaps": "Facelift in July 2023 introduced connected taillamp assembly and redesigned tailgate."
    },
    {
        "id": "kia-sonet",
        "make": "Kia",
        "model": "Sonet",
        "make_aliases": ["Kia", "Kia India"],
        "model_aliases": ["Sonet", "New Sonet"],
        "body_type": "Compact SUV",
        "years": [2022, 2023, 2024, 2025, 2026],
        "generations": [
            {
                "name": "1st Gen Pre-Facelift",
                "years": [2022, 2023],
                "variants": ["HTE", "HTK", "HTK+", "HTX", "HTX+", "GTX+", "X-Line"]
            },
            {
                "name": "1st Gen Facelift",
                "years": [2024, 2025, 2026],
                "variants": ["HTE", "HTK", "HTK(O)", "HTK+", "HTX", "HTX+", "GTX+", "X-Line"]
            }
        ],
        "fuel_types": ["Petrol (1.2L)", "Diesel (1.5L)", "Turbo Petrol (1.0L)"],
        "transmissions": ["Manual (5/6-speed)", "iMT", "Automatic (6-speed TC)", "DCT (7-speed)"],
        "source": {
            "title": "Kia India Official Sonet Page",
            "url": "https://www.kia.com/in/our-vehicles/sonet.html",
            "source_date": "2024-01-12",
            "retrieval_date": "2026-11-15",
            "verification_status": "verified_oem"
        },
        "known_gaps": "Facelift in January 2024 introduced full-width light bar and new bumpers."
    },
    {
        "id": "kia-carens",
        "make": "Kia",
        "model": "Carens",
        "make_aliases": ["Kia", "Kia India"],
        "model_aliases": ["Carens"],
        "body_type": "MPV",
        "years": [2022, 2023, 2024, 2025, 2026],
        "generations": [
            {
                "name": "1st Generation",
                "years": [2022, 2023, 2024, 2025, 2026],
                "variants": ["Premium", "Prestige", "Prestige Plus", "Luxury", "Luxury Plus", "X-Line"]
            }
        ],
        "fuel_types": ["Petrol (1.5L)", "Turbo Petrol (1.5L)", "Diesel (1.5L)"],
        "transmissions": ["Manual (6-speed)", "iMT", "Automatic (6-speed TC)", "DCT (7-speed)"],
        "source": {
            "title": "Kia India Official Carens Page",
            "url": "https://www.kia.com/in/our-vehicles/carens.html",
            "source_date": "2022-02-15",
            "retrieval_date": "2026-11-15",
            "verification_status": "verified_oem"
        },
        "known_gaps": "1.4L Turbo replaced with 1.5L Turbo in 2023 due to emissions update."
    },

    # ── 6. Toyota ───────────────────────────────────────────────────────────────
    {
        "id": "toyota-hyryder",
        "make": "Toyota",
        "model": "Urban Cruiser Hyryder",
        "make_aliases": ["Toyota", "Toyota Bharat", "TKM"],
        "model_aliases": ["Hyryder", "Urban Cruiser Hyryder", "Toyota Hyryder"],
        "body_type": "Mid-size SUV",
        "years": [2022, 2023, 2024, 2025, 2026],
        "generations": [
            {
                "name": "1st Generation",
                "years": [2022, 2023, 2024, 2025, 2026],
                "variants": ["E", "S", "G", "V", "S Hybrid", "G Hybrid", "V Hybrid"]
            }
        ],
        "fuel_types": ["Petrol (NeoDrive)", "Strong Hybrid", "CNG"],
        "transmissions": ["Manual (5-speed)", "Automatic (6-speed TC)", "e-CVT", "AWD"],
        "source": {
            "title": "Toyota Kirloskar Motor Urban Cruiser Hyryder",
            "url": "https://www.toyotabharat.com/showroom/hyryder/",
            "source_date": "2022-09-09",
            "retrieval_date": "2026-11-15",
            "verification_status": "verified_oem"
        },
        "known_gaps": "Manufactured at TKM Bidadi facility; mechanical twin of Maruti Grand Vitara with distinct front grille/lamps."
    },
    {
        "id": "toyota-glanza",
        "make": "Toyota",
        "model": "Glanza",
        "make_aliases": ["Toyota", "TKM"],
        "model_aliases": ["Glanza", "New Glanza"],
        "body_type": "Premium Hatchback",
        "years": [2022, 2023, 2024, 2025, 2026],
        "generations": [
            {
                "name": "2nd Generation",
                "years": [2022, 2023, 2024, 2025, 2026],
                "variants": ["E", "S", "G", "V"]
            }
        ],
        "fuel_types": ["Petrol", "CNG"],
        "transmissions": ["Manual (5-speed)", "AMT (5-speed)"],
        "source": {
            "title": "Toyota Glanza Official Page",
            "url": "https://www.toyotabharat.com/showroom/glanza/",
            "source_date": "2022-03-15",
            "retrieval_date": "2026-11-15",
            "verification_status": "verified_oem"
        },
        "known_gaps": "Shares core platform with Maruti Baleno but has unique front bumper and DRLs."
    },
    {
        "id": "toyota-innova-crysta",
        "make": "Toyota",
        "model": "Innova Crysta",
        "make_aliases": ["Toyota", "TKM"],
        "model_aliases": ["Innova Crysta", "Innova Diesel"],
        "body_type": "MPV",
        "years": [2022, 2023, 2024, 2025, 2026],
        "generations": [
            {
                "name": "2nd Gen Diesel Relaunch",
                "years": [2022, 2023, 2024, 2025, 2026],
                "variants": ["GX", "GX+", "VX", "ZX"]
            }
        ],
        "fuel_types": ["Diesel (2.4L GD)"],
        "transmissions": ["Manual (5-speed)"],
        "source": {
            "title": "Toyota Innova Crysta Official Page",
            "url": "https://www.toyotabharat.com/showroom/innova-crysta/",
            "source_date": "2023-03-01",
            "retrieval_date": "2026-11-15",
            "verification_status": "verified_oem"
        },
        "known_gaps": "Diesel manual only upon 2023 relaunch; petrol variant replaced by Innova Hycross."
    },
    {
        "id": "toyota-urban-cruiser-discontinued",
        "make": "Toyota",
        "model": "Urban Cruiser",
        "make_aliases": ["Toyota", "TKM"],
        "model_aliases": ["Urban Cruiser"],
        "body_type": "Compact SUV",
        "years": [2022],
        "generations": [
            {
                "name": "1st Generation (Maruti Vitara Brezza based)",
                "years": [2022],
                "variants": ["Mid", "High", "Premium"]
            }
        ],
        "fuel_types": ["Petrol (1.5L K15B)"],
        "transmissions": ["Manual (5-speed)", "Automatic (4-speed TC)"],
        "source": {
            "title": "Toyota Kirloskar Motor Discontinued Models Archive",
            "url": "https://www.toyotabharat.com/media-releases/archive",
            "source_date": "2022-11-10",
            "retrieval_date": "2026-11-15",
            "verification_status": "verified_oem"
        },
        "known_gaps": "Discontinued late 2022; replaced by Urban Cruiser Hyryder."
    },

    # ── 7. Honda ────────────────────────────────────────────────────────────────
    {
        "id": "honda-city",
        "make": "Honda",
        "model": "City",
        "make_aliases": ["Honda", "HCIL", "Honda Cars"],
        "model_aliases": ["City", "All New City", "City e:HEV"],
        "body_type": "Mid-size Sedan",
        "years": [2022, 2023, 2024, 2025, 2026],
        "generations": [
            {
                "name": "5th Generation Pre-Facelift",
                "years": [2022, 2023],
                "variants": ["V", "VX", "ZX", "e:HEV ZX"]
            },
            {
                "name": "5th Generation Facelift",
                "years": [2023, 2024, 2025, 2026],
                "variants": ["SV", "V", "VX", "ZX", "e:HEV V", "e:HEV ZX"]
            }
        ],
        "fuel_types": ["Petrol (1.5L i-VTEC)", "Strong Hybrid (1.5L e:HEV)"],
        "transmissions": ["Manual (6-speed)", "CVT (7-speed paddle)", "e-CVT"],
        "source": {
            "title": "Honda Cars India Official City Page",
            "url": "https://www.hondacarindia.com/honda-city-5th-generation",
            "source_date": "2023-03-02",
            "retrieval_date": "2026-11-15",
            "verification_status": "verified_oem"
        },
        "known_gaps": "4th Gen City also sold concurrently until April 2023; diesel engine dropped April 2023."
    },
    {
        "id": "honda-elevate",
        "make": "Honda",
        "model": "Elevate",
        "make_aliases": ["Honda", "HCIL"],
        "model_aliases": ["Elevate"],
        "body_type": "Mid-size SUV",
        "years": [2023, 2024, 2025, 2026],
        "generations": [
            {
                "name": "1st Generation",
                "years": [2023, 2024, 2025, 2026],
                "variants": ["SV", "V", "VX", "ZX", "Apex Edition"]
            }
        ],
        "fuel_types": ["Petrol (1.5L i-VTEC)"],
        "transmissions": ["Manual (6-speed)", "CVT (7-speed paddle)"],
        "source": {
            "title": "Honda Cars India Official Elevate Page",
            "url": "https://www.hondacarindia.com/honda-elevate",
            "source_date": "2023-09-04",
            "retrieval_date": "2026-11-15",
            "verification_status": "verified_oem"
        },
        "known_gaps": "Introduced September 2023; not present in 2022."
    },
    {
        "id": "honda-amaze",
        "make": "Honda",
        "model": "Amaze",
        "make_aliases": ["Honda", "HCIL"],
        "model_aliases": ["Amaze", "New Amaze"],
        "body_type": "Compact Sedan",
        "years": [2022, 2023, 2024, 2025, 2026],
        "generations": [
            {
                "name": "2nd Gen Facelift",
                "years": [2022, 2023, 2024],
                "variants": ["E", "S", "VX", "Elite Edition"]
            },
            {
                "name": "3rd Generation",
                "years": [2024, 2025, 2026],
                "variants": ["V", "VX", "ZX"]
            }
        ],
        "fuel_types": ["Petrol (1.2L i-VTEC)"],
        "transmissions": ["Manual (5-speed)", "CVT"],
        "source": {
            "title": "Honda Cars India Amaze Official",
            "url": "https://www.hondacarindia.com/honda-amaze",
            "source_date": "2024-12-04",
            "retrieval_date": "2026-11-15",
            "verification_status": "verified_oem"
        },
        "known_gaps": "3rd Gen launched late 2024. Diesel engine dropped April 2023."
    },
    {
        "id": "honda-jazz-discontinued",
        "make": "Honda",
        "model": "Jazz",
        "make_aliases": ["Honda", "HCIL"],
        "model_aliases": ["Jazz"],
        "body_type": "Hatchback",
        "years": [2022, 2023],
        "generations": [
            {
                "name": "3rd Generation Facelift",
                "years": [2022, 2023],
                "variants": ["V", "VX", "ZX"]
            }
        ],
        "fuel_types": ["Petrol (1.2L i-VTEC)"],
        "transmissions": ["Manual (5-speed)", "CVT"],
        "source": {
            "title": "Honda Cars India Historical Model Lineup",
            "url": "https://www.hondacarindia.com/media",
            "source_date": "2023-04-01",
            "retrieval_date": "2026-11-15",
            "verification_status": "verified_oem"
        },
        "known_gaps": "Discontinued in India April 2023 ahead of RDE emissions deadline."
    },

    # ── 8. Renault ──────────────────────────────────────────────────────────────
    {
        "id": "renault-kwid",
        "make": "Renault",
        "model": "Kwid",
        "make_aliases": ["Renault", "Renault India"],
        "model_aliases": ["Kwid"],
        "body_type": "Hatchback",
        "years": [2022, 2023, 2024, 2025, 2026],
        "generations": [
            {
                "name": "1st Gen Facelift",
                "years": [2022, 2023, 2024, 2025, 2026],
                "variants": ["RXE", "RXL(O)", "RXT", "Climber"]
            }
        ],
        "fuel_types": ["Petrol (1.0L SCe)"],
        "transmissions": ["Manual (5-speed)", "AMT (Easy-R)"],
        "source": {
            "title": "Renault India Official Kwid Specifications",
            "url": "https://www.renault.co.in/cars/renault-kwid.html",
            "source_date": "2024-01-10",
            "retrieval_date": "2026-11-15",
            "verification_status": "verified_oem"
        },
        "known_gaps": "0.8L engine discontinued early 2023; 1.0L continues."
    },
    {
        "id": "renault-triber",
        "make": "Renault",
        "model": "Triber",
        "make_aliases": ["Renault", "Renault India"],
        "model_aliases": ["Triber"],
        "body_type": "Sub-4m MPV",
        "years": [2022, 2023, 2024, 2025, 2026],
        "generations": [
            {
                "name": "1st Generation",
                "years": [2022, 2023, 2024, 2025, 2026],
                "variants": ["RXE", "RXL", "RXT", "RXZ"]
            }
        ],
        "fuel_types": ["Petrol (1.0L)"],
        "transmissions": ["Manual (5-speed)", "AMT (Easy-R)"],
        "source": {
            "title": "Renault India Official Triber Page",
            "url": "https://www.renault.co.in/cars/renault-triber.html",
            "source_date": "2024-01-10",
            "retrieval_date": "2026-11-15",
            "verification_status": "verified_oem"
        },
        "known_gaps": "Stealth and Urban Night limited editions share sheet metal with standard trims."
    },
    {
        "id": "renault-kiger",
        "make": "Renault",
        "model": "Kiger",
        "make_aliases": ["Renault", "Renault India"],
        "model_aliases": ["Kiger"],
        "body_type": "Compact SUV",
        "years": [2022, 2023, 2024, 2025, 2026],
        "generations": [
            {
                "name": "1st Generation",
                "years": [2022, 2023, 2024, 2025, 2026],
                "variants": ["RXE", "RXL", "RXT", "RXT(O)", "RXZ"]
            }
        ],
        "fuel_types": ["Petrol (1.0L Energy)", "Turbo Petrol (1.0L)"],
        "transmissions": ["Manual (5-speed)", "AMT", "X-Tronic CVT"],
        "source": {
            "title": "Renault India Official Kiger Page",
            "url": "https://www.renault.co.in/cars/renault-kiger.html",
            "source_date": "2024-01-10",
            "retrieval_date": "2026-11-15",
            "verification_status": "verified_oem"
        },
        "known_gaps": "Shares CMF-A+ platform with Nissan Magnite."
    },

    # ── 9. Nissan ───────────────────────────────────────────────────────────────
    {
        "id": "nissan-magnite",
        "make": "Nissan",
        "model": "Magnite",
        "make_aliases": ["Nissan", "Nissan India"],
        "model_aliases": ["Magnite", "New Magnite"],
        "body_type": "Compact SUV",
        "years": [2022, 2023, 2024, 2025, 2026],
        "generations": [
            {
                "name": "1st Gen Pre-Facelift",
                "years": [2022, 2023, 2024],
                "variants": ["XE", "XL", "XV", "XV Premium", "Geza Edition", "Kuro Edition"]
            },
            {
                "name": "1st Gen Facelift",
                "years": [2024, 2025, 2026],
                "variants": ["Visia", "Visia+", "Acenta", "N-Connecta", "Tekna", "Tekna+"]
            }
        ],
        "fuel_types": ["Petrol (1.0L)", "Turbo Petrol (1.0L HRA0)"],
        "transmissions": ["Manual (5-speed)", "EZ-Shift (AMT)", "X-Tronic (CVT)"],
        "source": {
            "title": "Nissan Motor India Official Magnite Page",
            "url": "https://www.nissan.in/vehicles/new/magnite.html",
            "source_date": "2024-10-04",
            "retrieval_date": "2026-11-15",
            "verification_status": "verified_oem"
        },
        "known_gaps": "Global trim names (Visia/Acenta/Tekna) introduced with October 2024 facelift."
    },

    # ── 10. Skoda ───────────────────────────────────────────────────────────────
    {
        "id": "skoda-kushaq",
        "make": "Skoda",
        "model": "Kushaq",
        "make_aliases": ["Skoda", "Škoda", "Skoda Auto"],
        "model_aliases": ["Kushaq", "Kushaq Monte Carlo"],
        "body_type": "Compact SUV",
        "years": [2022, 2023, 2024, 2025, 2026],
        "generations": [
            {
                "name": "1st Generation",
                "years": [2022, 2023, 2024, 2025, 2026],
                "variants": ["Classic", "Signature", "Sportline", "Prestige", "Monte Carlo", "Active", "Ambition", "Style"]
            }
        ],
        "fuel_types": ["Petrol (1.0L TSI)", "Petrol (1.5L TSI EVO)"],
        "transmissions": ["Manual (6-speed)", "Automatic (6-speed TC)", "DSG (7-speed DQ200)"],
        "source": {
            "title": "Skoda Auto India Official Kushaq Specifications",
            "url": "https://www.skoda-auto.co.in/models/kushaq/kushaq",
            "source_date": "2024-05-02",
            "retrieval_date": "2026-11-15",
            "verification_status": "verified_oem"
        },
        "known_gaps": "Trim nomenclature updated mid-2024 from Active/Ambition/Style to Classic/Signature/Prestige."
    },
    {
        "id": "skoda-slavia",
        "make": "Skoda",
        "model": "Slavia",
        "make_aliases": ["Skoda", "Škoda"],
        "model_aliases": ["Slavia", "Slavia Monte Carlo"],
        "body_type": "Mid-size Sedan",
        "years": [2022, 2023, 2024, 2025, 2026],
        "generations": [
            {
                "name": "1st Generation",
                "years": [2022, 2023, 2024, 2025, 2026],
                "variants": ["Classic", "Signature", "Sportline", "Prestige", "Monte Carlo", "Active", "Ambition", "Style"]
            }
        ],
        "fuel_types": ["Petrol (1.0L TSI)", "Petrol (1.5L TSI)"],
        "transmissions": ["Manual (6-speed)", "Automatic (6-speed TC)", "DSG (7-speed)"],
        "source": {
            "title": "Skoda Auto India Official Slavia Specifications",
            "url": "https://www.skoda-auto.co.in/models/slavia/slavia",
            "source_date": "2024-05-02",
            "retrieval_date": "2026-11-15",
            "verification_status": "verified_oem"
        },
        "known_gaps": "Built on MQB-A0-IN platform; shares mechanical components with VW Virtus."
    },

    # ── 11. Volkswagen ──────────────────────────────────────────────────────────
    {
        "id": "volkswagen-taigun",
        "make": "Volkswagen",
        "model": "Taigun",
        "make_aliases": ["Volkswagen", "VW", "VW India"],
        "model_aliases": ["Taigun", "Taigun GT"],
        "body_type": "Compact SUV",
        "years": [2022, 2023, 2024, 2025, 2026],
        "generations": [
            {
                "name": "1st Generation",
                "years": [2022, 2023, 2024, 2025, 2026],
                "variants": ["Comfortline", "Highline", "Topline", "GT", "GT Edge", "GT Plus"]
            }
        ],
        "fuel_types": ["Petrol (1.0L TSI)", "Petrol (1.5L TSI EVO)"],
        "transmissions": ["Manual (6-speed)", "Automatic (6-speed TC)", "DSG (7-speed)"],
        "source": {
            "title": "Volkswagen India Official Taigun Specifications",
            "url": "https://www.volkswagen.co.in/en/models/taigun.html",
            "source_date": "2023-06-15",
            "retrieval_date": "2026-11-15",
            "verification_status": "verified_oem"
        },
        "known_gaps": "GT Plus Sport aesthetic pack shares sheet metal with GT Plus."
    },
    {
        "id": "volkswagen-virtus",
        "make": "Volkswagen",
        "model": "Virtus",
        "make_aliases": ["Volkswagen", "VW"],
        "model_aliases": ["Virtus", "Virtus GT"],
        "body_type": "Mid-size Sedan",
        "years": [2022, 2023, 2024, 2025, 2026],
        "generations": [
            {
                "name": "1st Generation",
                "years": [2022, 2023, 2024, 2025, 2026],
                "variants": ["Comfortline", "Highline", "Topline", "GT", "GT Plus"]
            }
        ],
        "fuel_types": ["Petrol (1.0L TSI)", "Petrol (1.5L TSI EVO)"],
        "transmissions": ["Manual (6-speed)", "Automatic (6-speed TC)", "DSG (7-speed)"],
        "source": {
            "title": "Volkswagen India Official Virtus Specifications",
            "url": "https://www.volkswagen.co.in/en/models/virtus.html",
            "source_date": "2022-06-09",
            "retrieval_date": "2026-11-15",
            "verification_status": "verified_oem"
        },
        "known_gaps": "Introduced June 2022 replacing VW Vento."
    },
    {
        "id": "volkswagen-polo-discontinued",
        "make": "Volkswagen",
        "model": "Polo",
        "make_aliases": ["Volkswagen", "VW"],
        "model_aliases": ["Polo", "Polo GT"],
        "body_type": "Hatchback",
        "years": [2022],
        "generations": [
            {
                "name": "5th Generation (PQ25 Platform)",
                "years": [2022],
                "variants": ["Trendline", "Comfortline", "Highline Plus", "GT TSI", "Legend Edition"]
            }
        ],
        "fuel_types": ["Petrol (1.0L TSI / MPI)"],
        "transmissions": ["Manual (6-speed)", "Automatic (6-speed TC)"],
        "source": {
            "title": "Volkswagen India Official Announcement: Polo Legend Edition",
            "url": "https://www.volkswagen.co.in/en/about-us/news.html",
            "source_date": "2022-04-07",
            "retrieval_date": "2026-11-15",
            "verification_status": "verified_oem"
        },
        "known_gaps": "Production ceased April 2022; final retail deliveries in mid-2022."
    },

    # ── 12. MG (Morris Garages) ─────────────────────────────────────────────────
    {
        "id": "mg-astor",
        "make": "MG",
        "model": "Astor",
        "make_aliases": ["MG", "MG Motor", "Morris Garages"],
        "model_aliases": ["Astor"],
        "body_type": "Compact SUV",
        "years": [2022, 2023, 2024, 2025, 2026],
        "generations": [
            {
                "name": "1st Generation",
                "years": [2022, 2023, 2024, 2025, 2026],
                "variants": ["Sprint", "Shine", "Select", "Sharp Pro", "Savvy Pro", "Style", "Super", "Smart", "Sharp"]
            }
        ],
        "fuel_types": ["Petrol (1.5L VTi-TECH)", "Turbo Petrol (1.3L 220Turbo)"],
        "transmissions": ["Manual (5-speed)", "CVT", "Automatic (6-speed TC)"],
        "source": {
            "title": "MG Motor India Official Astor Specifications",
            "url": "https://www.mgmotor.co.in/vehicles/mgastor",
            "source_date": "2024-01-15",
            "retrieval_date": "2026-11-15",
            "verification_status": "verified_oem"
        },
        "known_gaps": "Trim names updated in 2024 to Sprint/Shine/Select/Sharp Pro/Savvy Pro."
    },
    {
        "id": "mg-hector",
        "make": "MG",
        "model": "Hector",
        "make_aliases": ["MG", "MG Motor"],
        "model_aliases": ["Hector", "New Hector", "Hector Plus"],
        "body_type": "Mid-size SUV",
        "years": [2022, 2023, 2024, 2025, 2026],
        "generations": [
            {
                "name": "1st Gen Facelift",
                "years": [2022, 2023, 2024, 2025, 2026],
                "variants": ["Style", "Shine", "Shine Pro", "Select Pro", "Smart Pro", "Sharp Pro", "Savvy Pro"]
            }
        ],
        "fuel_types": ["Petrol (1.5L Turbo)", "Diesel (2.0L Multijet)"],
        "transmissions": ["Manual (6-speed)", "CVT"],
        "source": {
            "title": "MG Motor India Hector Specifications",
            "url": "https://www.mgmotor.co.in/vehicles/mghector",
            "source_date": "2023-01-11",
            "retrieval_date": "2026-11-15",
            "verification_status": "verified_oem"
        },
        "known_gaps": "Major cosmetic facelift debuted at Auto Expo January 2023."
    },
    {
        "id": "mg-comet-ev",
        "make": "MG",
        "model": "Comet EV",
        "make_aliases": ["MG", "MG Motor"],
        "model_aliases": ["Comet", "Comet EV"],
        "body_type": "Ultra-compact Electric Vehicle",
        "years": [2023, 2024, 2025, 2026],
        "generations": [
            {
                "name": "1st Generation",
                "years": [2023, 2024, 2025, 2026],
                "variants": ["Executive", "Excite", "Exclusive", "Blackstorm"]
            }
        ],
        "fuel_types": ["Electric (17.3 kWh)"],
        "transmissions": ["Automatic (Single Speed)"],
        "source": {
            "title": "MG Motor India Official Comet EV",
            "url": "https://www.mgmotor.co.in/vehicles/mgcomet",
            "source_date": "2023-04-26",
            "retrieval_date": "2026-11-15",
            "verification_status": "verified_oem"
        },
        "known_gaps": "Introduced April 2023; not present in 2022."
    },

    # ── 13. Citroën ─────────────────────────────────────────────────────────────
    {
        "id": "citroen-c3",
        "make": "Citroen",
        "model": "C3",
        "make_aliases": ["Citroen", "Citroën", "Citroen India"],
        "model_aliases": ["C3", "New C3"],
        "body_type": "Hatchback / B-segment Cross",
        "years": [2022, 2023, 2024, 2025, 2026],
        "generations": [
            {
                "name": "1st Generation",
                "years": [2022, 2023, 2024, 2025, 2026],
                "variants": ["Live", "Feel", "Feel (O)", "Shine"]
            }
        ],
        "fuel_types": ["Petrol (1.2L PureTech 82)", "Turbo Petrol (1.2L PureTech 110)"],
        "transmissions": ["Manual (5-speed/6-speed)", "Automatic (6-speed TC)"],
        "source": {
            "title": "Citroen India Official C3 Specifications",
            "url": "https://www.citroen.in/car/new-c3/",
            "source_date": "2022-07-20",
            "retrieval_date": "2026-11-15",
            "verification_status": "verified_oem"
        },
        "known_gaps": "Automatic transmission added in late 2024."
    },
    {
        "id": "citroen-c3-aircross",
        "make": "Citroen",
        "model": "C3 Aircross",
        "make_aliases": ["Citroen", "Citroën"],
        "model_aliases": ["C3 Aircross", "Aircross", "Basalt"],
        "body_type": "Compact SUV",
        "years": [2023, 2024, 2025, 2026],
        "generations": [
            {
                "name": "1st Generation",
                "years": [2023, 2024, 2025, 2026],
                "variants": ["You", "Plus", "Max"]
            }
        ],
        "fuel_types": ["Turbo Petrol (1.2L PureTech 110)"],
        "transmissions": ["Manual (6-speed)", "Automatic (6-speed TC)"],
        "source": {
            "title": "Citroen India Official C3 Aircross Page",
            "url": "https://www.citroen.in/",
            "source_date": "2023-09-15",
            "retrieval_date": "2026-11-15",
            "verification_status": "verified_oem"
        },
        "known_gaps": "Basalt coupe crossover shares front clip and cabin components."
    }
]

def main() -> None:
    catalog = {
        "version": "catalog-india-2022-2026-v1.0",
        "updated_at": "2026-11-15",
        "target_market": "India",
        "calendar_years": [2022, 2023, 2024, 2025, 2026],
        "description": "Validated catalog of mainstream budget and mid-range passenger vehicles sold in India during 2022–2026.",
        "models": VEHICLES
    }

    out_path = Path(settings.KNOWLEDGE_DIR) / "indian_vehicles.json"
    out_path.write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    print(f"Catalog successfully written to {out_path} with {len(VEHICLES)} vehicle models across {len(set(v['make'] for v in VEHICLES))} manufacturers.")


if __name__ == "__main__":
    main()
