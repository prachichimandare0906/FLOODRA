
from pathlib import Path

import geopandas as gpd
import rasterio
import osmnx as ox
from rasterio.warp import transform_bounds


BASE_DIR = Path(__file__).resolve().parents[2]

RASTER_PATH = BASE_DIR / "data" / "raw" / "flood_image.tif"
OUTPUT_PATH = BASE_DIR / "data" / "raw" / "real_settlements.geojson"


def download_settlements():
    print("=" * 55)
    print("FLOODRA - DOWNLOADING REAL SETTLEMENTS")
    print("=" * 55)

    # Check that the satellite image exists.
    if not RASTER_PATH.exists():
        raise FileNotFoundError(
            f"Satellite image not found: {RASTER_PATH}"
        )

    # Read the satellite scene bounds and convert them to WGS84.
    with rasterio.open(RASTER_PATH) as src:
        if src.crs is None:
            raise ValueError(
                "The satellite image has no CRS/geographic reference."
            )

        west, south, east, north = transform_bounds(
            src.crs,
            "EPSG:4326",
            src.bounds.left,
            src.bounds.bottom,
            src.bounds.right,
            src.bounds.top,
        )

    print("\nSatellite scene bounds (EPSG:4326):")
    print("West :", west)
    print("South:", south)
    print("East :", east)
    print("North:", north)

    # Retrieve settlement-related features from OpenStreetMap.
    tags = {
        "place": [
            "city",
            "town",
            "village",
            "hamlet",
            "isolated_dwelling",
            "suburb",
            "neighbourhood",
        ]
    }

    print("\nDownloading settlement data from OpenStreetMap...")

    # OSMnx API varies by installed version.
    try:
        # Newer OSMnx versions.
        settlements = ox.features_from_bbox(
            (west, south, east, north),
            tags=tags,
        )
    except (AttributeError, TypeError):
        # Older OSMnx versions.
        if hasattr(ox, "geometries_from_bbox"):
            settlements = ox.geometries_from_bbox(
                north, south, east, west, tags
            )
        else:
            raise RuntimeError(
                "Your OSMnx version has no supported feature-download "
                "function. Check it with: "
                "python -c \"import osmnx; print(osmnx.__version__)\""
            )

    if settlements.empty:
        raise ValueError(
            "No settlement features were found inside this satellite "
            "scene. Check the scene location and OpenStreetMap coverage."
        )

    # Keep only actual place features.
    if "place" in settlements.columns:
        settlements = settlements[
            settlements["place"].notna()
        ].copy()

    if settlements.empty:
        raise ValueError(
            "OpenStreetMap returned features, but none were settlement "
            "place features."
        )

    # Ensure the geometries have a known CRS.
    if settlements.crs is None:
        settlements = settlements.set_crs("EPSG:4326")
    else:
        settlements = settlements.to_crs("EPSG:4326")

    # Use representative points so polygon settlements can be sampled
    # against the flood raster later.
    settlements["geometry"] = settlements.geometry.apply(
        lambda geom: geom.representative_point()
        if geom is not None and not geom.is_empty
        else None
    )

    settlements = settlements[
        settlements.geometry.notna()
        & ~settlements.geometry.is_empty
    ].copy()

    # Retain useful properties where available.
    useful_columns = [
        col for col in [
            "name",
            "place",
            "population",
            "geometry",
        ]
        if col in settlements.columns
    ]

    settlements = settlements[useful_columns].copy()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    settlements.to_file(OUTPUT_PATH, driver="GeoJSON")

    print("\nSettlement download completed.")
    print("Number of settlement features:", len(settlements))
    print("Output:", OUTPUT_PATH)


if __name__ == "__main__":
    download_settlements()
