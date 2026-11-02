"""Transparent, broad Indian crop-suitability and soil-test guidance rules."""

SOIL_TYPES = (
    "Alluvial",
    "Black",
    "Red",
    "Laterite",
    "Arid",
    "Forest",
    "Saline",
    "Peaty",
)

SEASONS = ("Kharif", "Rabi", "Zaid")

# Broad screening bands only. They are not district-specific crop calendars
# or substitutes for ICAR/state agriculture university recommendations.
INDIAN_CROP_PROFILES = {
    "Rice": {
        "soils": {"Alluvial", "Peaty"},
        "seasons": {"Kharif"},
        "temperature": (20, 35),
        "rainfall": (1000, 2500),
    },
    "Wheat": {
        "soils": {"Alluvial", "Black"},
        "seasons": {"Rabi"},
        "temperature": (10, 25),
        "rainfall": (300, 900),
    },
    "Maize": {
        "soils": {"Alluvial", "Red", "Black"},
        "seasons": {"Kharif", "Rabi", "Zaid"},
        "temperature": (18, 32),
        "rainfall": (500, 1000),
    },
    "Cotton": {
        "soils": {"Black", "Alluvial"},
        "seasons": {"Kharif"},
        "temperature": (21, 35),
        "rainfall": (500, 1000),
    },
    "Sugarcane": {
        "soils": {"Alluvial", "Black"},
        "seasons": {"Kharif", "Rabi", "Zaid"},
        "temperature": (20, 35),
        "rainfall": (1000, 1500),
    },
    "Millets": {
        "soils": {"Red", "Arid", "Black"},
        "seasons": {"Kharif"},
        "temperature": (25, 35),
        "rainfall": (250, 600),
    },
    "Pulses": {
        "soils": {"Red", "Black", "Alluvial"},
        "seasons": {"Kharif", "Rabi"},
        "temperature": (18, 32),
        "rainfall": (350, 750),
    },
}

NUTRIENT_GUIDANCE = {
    "nitrogen": {
        "Low": "Low SHC rating: discuss split nitrogen application, commonly through neem-coated urea, using the local crop package.",
        "Medium": "Medium SHC rating: follow the crop- and stage-specific nitrogen dose on your Soil Health Card; avoid blanket extra application.",
        "High": "High SHC rating: avoid additional nitrogen unless the crop-specific local recommendation calls for it.",
    },
    "phosphorus": {
        "Low": "Low SHC rating: ask a local advisor about a phosphorus source such as SSP or DAP; account for the nitrogen supplied by DAP.",
        "Medium": "Medium SHC rating: follow the crop-specific phosphorus dose on your Soil Health Card; avoid unneeded basal application.",
        "High": "High SHC rating: avoid extra phosphorus unless the crop-specific local recommendation calls for it.",
    },
    "potassium": {
        "Low": "Low SHC rating: ask a local advisor whether MOP is suitable for the crop and soil.",
        "Medium": "Medium SHC rating: follow the crop-specific potassium dose on your Soil Health Card.",
        "High": "High SHC rating: avoid additional potassium unless the crop-specific local recommendation calls for it.",
    },
}


def _range_fit(value, bounds):
    lower, upper = bounds
    if lower <= value <= upper:
        return 1.0, True
    distance = lower - value if value < lower else value - upper
    return max(0.0, 1 - distance / (upper - lower)), False


def recommend_indian_crop(soil_type, season, temperature, seasonal_rainfall):
    """Rank Indian crop options and return transparent factor-level reasoning."""
    ranked = []
    for crop, profile in INDIAN_CROP_PROFILES.items():
        soil_match = soil_type in profile["soils"]
        season_match = season in profile["seasons"]
        temperature_fit, temperature_match = _range_fit(
            temperature, profile["temperature"]
        )
        rainfall_fit, rainfall_match = _range_fit(
            seasonal_rainfall, profile["rainfall"]
        )
        score = (
            0.30 * soil_match
            + 0.30 * season_match
            + 0.20 * temperature_fit
            + 0.20 * rainfall_fit
        )
        ranked.append(
            (
                score,
                crop,
                {
                    "soil_match": soil_match,
                    "season_match": season_match,
                    "temperature_match": temperature_match,
                    "rainfall_match": rainfall_match,
                    "temperature_range": profile["temperature"],
                    "rainfall_range": profile["rainfall"],
                },
            )
        )
    score, crop, reasoning = max(ranked, key=lambda item: item[0])
    return crop, score, reasoning


def fertilizer_guidance(statuses):
    """Return non-quantitative suggestions based on farmer-entered SHC ratings."""
    return [
        NUTRIENT_GUIDANCE[nutrient][statuses[nutrient]]
        for nutrient in ("nitrogen", "phosphorus", "potassium")
    ]
