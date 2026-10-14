from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.transform import rowcol


# ============================================================
# FLOODRA - REAL SETTLEMENT ISOLATION ANALYSIS
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

MASK_PATH = BASE_DIR / "data" / "processed" / "flood_mask.tif"

ROADS_PATH = (
    BASE_DIR / "data" / "processed" / "real_flooded_roads.geojson"
)

SETTLEMENTS_PATH = (
    BASE_DIR / "data" / "raw" / "real_settlements.geojson"
)

OUTPUT_PATH = (
    BASE_DIR / "data" / "processed" / "isolated_areas.geojson"
)


def calculate_isolation():
    print("=" * 65)
    print("       FLOODRA REAL SETTLEMENT ISOLATION ANALYSIS")
    print("=" * 65)

    # --------------------------------------------------------
    # 1. Validate required files
    # --------------------------------------------------------
    for path in (MASK_PATH, ROADS_PATH, SETTLEMENTS_PATH):
        if not path.exists():
            raise FileNotFoundError(
                f"Required input file not found: {path}"
            )

    # --------------------------------------------------------
    # 2. Load flood raster and preserve its georeferencing
    # --------------------------------------------------------
    print("\nLoading flood mask...")

    with rasterio.open(MASK_PATH) as src:
        if src.crs is None:
            raise ValueError("Flood mask has no CRS.")

        flood_mask = src.read(1)
        raster_transform = src.transform
        raster_crs = src.crs
        raster_height = src.height
        raster_width = src.width

        print("Raster CRS:", raster_crs)
        print("Raster dimensions:", raster_width, "x", raster_height)

    # --------------------------------------------------------
    # 3. Load roads and settlements
    # --------------------------------------------------------
    print("\nLoading road-risk data...")
    roads = gpd.read_file(ROADS_PATH)

    print("Road features:", len(roads))

    print("\nLoading OSM settlements...")
    settlements = gpd.read_file(SETTLEMENTS_PATH)

    print("Settlement features:", len(settlements))

    if roads.crs is None:
        raise ValueError("Road GeoJSON has no CRS.")

    if settlements.crs is None:
        raise ValueError("Settlement GeoJSON has no CRS.")

    if settlements.empty:
        raise ValueError("No settlements were found in the input file.")

    if "risk_level" not in roads.columns:
        raise ValueError(
            "Road data is missing the 'risk_level' field. "
            "Run real_road_risk.py first."
        )

    # --------------------------------------------------------
    # 4. Sample raster using coordinates in the raster CRS
    # --------------------------------------------------------
    # This is separate from distance calculations. Raster
    # coordinates must match the raster's own CRS and transform.
    settlements_raster = settlements.to_crs(raster_crs)

    flooded_values = []
    inside_scene_values = []

    for geometry in settlements_raster.geometry:
        if geometry is None or geometry.is_empty:
            flooded_values.append(False)
            inside_scene_values.append(False)
            continue

        point = geometry.representative_point()

        row, col = rowcol(
            raster_transform,
            point.x,
            point.y
        )

        inside = (
            0 <= row < raster_height
            and 0 <= col < raster_width
        )

        inside_scene_values.append(inside)

        if inside:
            flooded_values.append(
                bool(flood_mask[row, col] == 1)
            )
        else:
            flooded_values.append(False)

    settlements["inside_satellite_scene"] = inside_scene_values
    settlements["flooded_pixel"] = flooded_values

    # Only analyze settlements inside this satellite scene.
    settlements = settlements[
        settlements["inside_satellite_scene"]
    ].copy()

    if settlements.empty:
        raise ValueError(
            "No settlements fall inside the satellite scene. "
            "Check the raster bounds and settlement coordinates."
        )

    print("Settlements inside scene:", len(settlements))

    # --------------------------------------------------------
    # 5. Select risky roads
    # --------------------------------------------------------
    risky_roads = roads[
        roads["risk_level"].isin(
            ["HIGH RISK", "MODERATE RISK"]
        )
    ].copy()

    print("High/moderate-risk roads:", len(risky_roads))

    # --------------------------------------------------------
    # 6. Reproject both layers to metres for distance analysis
    # --------------------------------------------------------
    # estimate_utm_crs selects a local UTM CRS based on the
    # settlement data. Do not calculate metre thresholds in EPSG:4326.
    projected_crs = settlements.estimate_utm_crs()

    if projected_crs is None:
        raise ValueError(
            "Could not determine a suitable projected CRS."
        )

    settlements_metric = settlements.to_crs(projected_crs)
    risky_roads_metric = risky_roads.to_crs(projected_crs)

    print("Distance calculation CRS:", projected_crs)

    # --------------------------------------------------------
    # 7. Calculate isolation indicators
    # --------------------------------------------------------
    results = []

    for index, settlement in settlements.iterrows():
        point_metric = settlements_metric.loc[index].geometry

        if point_metric is None or point_metric.is_empty:
            continue

        flooded = bool(settlement["flooded_pixel"])

        if risky_roads_metric.empty:
            nearest_distance = None
            road_score = 0
        else:
            distances = risky_roads_metric.geometry.distance(
                point_metric
            )

            nearest_distance = float(distances.min())

            if nearest_distance <= 1000:
                road_score = 100
            elif nearest_distance <= 2000:
                road_score = 70
            elif nearest_distance <= 4000:
                road_score = 35
            else:
                road_score = 0

        flood_score = 100 if flooded else 0

        # Heuristic estimate, not a confirmed isolation probability.
        isolation_score = (
            flood_score * 0.60
            + road_score * 0.40
        )

        if isolation_score >= 80:
            isolation_level = "CRITICAL"
        elif isolation_score >= 60:
            isolation_level = "HIGH"
        elif isolation_score >= 30:
            isolation_level = "MODERATE"
        else:
            isolation_level = "LOW"

        name = settlement.get("name")
        place_type = settlement.get("place", "unknown")
        population = settlement.get("population")

        results.append({
            "name": str(name) if name is not None else "Unnamed settlement",
            "place_type": str(place_type) if place_type is not None else "unknown",
            "population": str(population) if population is not None else None,
            "flooded": flooded,
            "flood_score": flood_score,
            "road_score": road_score,
            "isolation_score": round(isolation_score, 2),
            "isolation_level": isolation_level,
            "nearest_risky_road_m": (
                round(nearest_distance, 2)
                if nearest_distance is not None
                else -1
            ),
            "geometry": settlement.geometry
        })

    if not results:
        raise ValueError("No settlement risk results were generated.")

    result = gpd.GeoDataFrame(
        results,
        geometry="geometry",
        crs=settlements.crs
    )

    # Keep only settlements classified moderate risk or higher.
    risk_result = result[
        result["isolation_level"].isin(
            ["CRITICAL", "HIGH", "MODERATE"]
        )
    ].copy()

    # --------------------------------------------------------
    # 8. Save in WGS84 for Leaflet
    # --------------------------------------------------------
    risk_result = risk_result.to_crs("EPSG:4326")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    risk_result.to_file(
        OUTPUT_PATH,
        driver="GeoJSON"
    )

    # --------------------------------------------------------
    # 9. Report results
    # --------------------------------------------------------
    print("\n" + "=" * 65)
    print("SETTLEMENT ISOLATION ANALYSIS COMPLETE")
    print("=" * 65)

    print("Settlements analyzed:", len(result))
    print("Potential risk locations:", len(risk_result))
    print(
        "Critical:",
        int((risk_result["isolation_level"] == "CRITICAL").sum())
    )
    print(
        "High:",
        int((risk_result["isolation_level"] == "HIGH").sum())
    )
    print(
        "Moderate:",
        int((risk_result["isolation_level"] == "MODERATE").sum())
    )
    print("Output:", OUTPUT_PATH)

    print(
        "\nNote: These are heuristic exposure estimates, "
        "not confirmed isolated communities."
    )


if __name__ == "__main__":
    calculate_isolation()