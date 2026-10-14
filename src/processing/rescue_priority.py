
from pathlib import Path

import geopandas as gpd


BASE_DIR = Path(__file__).resolve().parents[2]

ISOLATION_PATH = (
    BASE_DIR / "data" / "processed" / "isolated_areas.geojson"
)
ROADS_PATH = (
    BASE_DIR / "data" / "processed" / "real_flooded_roads.geojson"
)
OUTPUT_PATH = (
    BASE_DIR / "data" / "processed" / "rescue_priority.geojson"
)


def road_risk_score(risk_level):
    """Convert road risk labels into a heuristic exposure score."""
    scores = {
        "HIGH RISK": 100,
        "MODERATE RISK": 70,
        "LOW RISK": 40,
        "CLEAR": 0,
    }
    return scores.get(str(risk_level).upper(), 0)


def proximity_score(distance_m):
    """Score proximity to a road with a non-clear risk classification."""
    if distance_m is None:
        return 0

    if distance_m <= 1000:
        return 100
    if distance_m <= 2000:
        return 70
    if distance_m <= 4000:
        return 35
    return 0


def classify_priority(score, isolation_level, flooded):
    """
    Classify rescue priority.

    A CRITICAL isolation classification or a flooded settlement
    with a critical isolation score receives CRITICAL priority.
    """
    isolation_level = str(isolation_level).upper()

    if isolation_level == "CRITICAL":
        return "CRITICAL"

    if flooded and score >= 60:
        return "CRITICAL"

    if score >= 60:
        return "HIGH"

    if score >= 40:
        return "MEDIUM"

    return "LOW"


def main():
    print("=" * 60)
    print("FLOODRA - RESCUE PRIORITY ANALYSIS")
    print("=" * 60)

    if not ISOLATION_PATH.exists():
        raise FileNotFoundError(
            f"Isolation file not found: {ISOLATION_PATH}"
        )

    if not ROADS_PATH.exists():
        raise FileNotFoundError(
            f"Road-risk file not found: {ROADS_PATH}"
        )

    settlements = gpd.read_file(ISOLATION_PATH)
    roads = gpd.read_file(ROADS_PATH)

    if settlements.empty:
        raise ValueError(
            "No candidate settlements found in isolated_areas.geojson."
        )

    if settlements.crs is None or roads.crs is None:
        raise ValueError("Input GeoJSON data must have a valid CRS.")

    if "risk_level" not in roads.columns:
        raise ValueError(
            "Road data is missing the 'risk_level' field."
        )

    if "isolation_score" not in settlements.columns:
        raise ValueError(
            "Settlement data is missing 'isolation_score'. "
            "Regenerate isolated_areas.geojson first."
        )

    # Use a projected CRS so distances are measured in metres.
    metric_crs = settlements.estimate_utm_crs()

    if metric_crs is None:
        raise ValueError(
            "Could not determine a suitable metric CRS for settlements."
        )

    settlements_metric = settlements.to_crs(metric_crs).copy()
    roads_metric = roads.to_crs(metric_crs).copy()

    # Ignore clear roads when calculating exposure to risky roads.
    roads_metric["road_score"] = roads_metric["risk_level"].apply(
        road_risk_score
    )

    risky_roads = roads_metric[
        roads_metric["road_score"] > 0
    ].copy()

    if risky_roads.empty:
        print(
            "Warning: No non-clear roads found. "
            "Road exposure scores will be zero."
        )

    nearest_distances = []
    nearest_levels = []
    exposure_scores = []
    accessibility_scores = []
    rescue_scores = []
    priority_levels = []

    for _, settlement in settlements_metric.iterrows():
        isolation_score = float(settlement["isolation_score"])
        isolation_level = settlement.get(
            "isolation_level", "LOW"
        )
        flooded_value = settlement.get("flooded", False)

        if isinstance(flooded_value, str):
            flooded = flooded_value.strip().lower() in {
                "true", "1", "yes"
            }
        else:
            flooded = bool(flooded_value)

        if risky_roads.empty:
            distance_m = None
            nearest_level = "UNKNOWN"
            exposure_score = 0
            access_score = 0
            proximity = 0
        else:
            distances = risky_roads.geometry.distance(
                settlement.geometry
            )

            nearest_index = distances.idxmin()
            distance_m = float(distances.loc[nearest_index])

            nearest_level = str(
                risky_roads.loc[nearest_index, "risk_level"]
            )

            exposure_score = road_risk_score(nearest_level)
            proximity = proximity_score(distance_m)

            # This is a heuristic concern score, NOT a measured
            # road-network accessibility calculation.
            access_score = proximity

        # Weighted heuristic score on a 0-100 scale.
        rescue_score = (
            0.45 * isolation_score
            + 0.35 * exposure_score
            + 0.20 * proximity
        )

        priority = classify_priority(
            rescue_score,
            isolation_level,
            flooded,
        )

        nearest_distances.append(
            round(distance_m, 2) if distance_m is not None else None
        )
        nearest_levels.append(nearest_level)
        exposure_scores.append(round(exposure_score, 2))
        accessibility_scores.append(round(access_score, 2))
        rescue_scores.append(round(rescue_score, 2))
        priority_levels.append(priority)

    settlements["nearest_risky_road_m"] = nearest_distances
    settlements["nearest_risky_road_level"] = nearest_levels
    settlements["road_exposure_score"] = exposure_scores

    # Retain this existing dashboard field for compatibility.
    # It represents proximity concern, not proven accessibility.
    settlements["accessibility_score"] = accessibility_scores

    settlements["rescue_score"] = rescue_scores
    settlements["priority_level"] = priority_levels

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Export geographic coordinates for the Leaflet dashboard.
    settlements.to_crs("EPSG:4326").to_file(
        OUTPUT_PATH,
        driver="GeoJSON",
    )

    print("\nRescue-priority analysis completed.")
    print("Total candidate settlements:", len(settlements))
    print("Output:", OUTPUT_PATH)

    print("\nPriority distribution:")
    for level in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        count = sum(
            1 for value in priority_levels if value == level
        )
        print(f"  {level}: {count}")

    print("\nSettlement results:")
    for _, row in settlements.iterrows():
        print(
            f"{row.get('name', 'Unknown')}: "
            f"score={row['rescue_score']:.1f}, "
            f"priority={row['priority_level']}"
        )


if __name__ == "__main__":
    main()
