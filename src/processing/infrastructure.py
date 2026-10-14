from pathlib import Path

import geopandas as gpd
import rasterio
from rasterio.features import geometry_mask


FLOOD_MASK_PATH = "data/processed/flood_mask.tif"
ROADS_PATH = "data/raw/roads.geojson"
OUTPUT_PATH = "data/processed/flooded_roads.geojson"


def load_flood_mask():

    with rasterio.open(FLOOD_MASK_PATH) as src:

        mask = src.read(1)

        transform = src.transform

        crs = src.crs

        bounds = src.bounds

        return mask, transform, crs, bounds


def analyse_roads():

    print("\nLoading flood mask...")

    flood_mask, transform, raster_crs, bounds = load_flood_mask()

    print("Flood mask loaded.")

    print("\nLoading road network...")

    roads = gpd.read_file(ROADS_PATH)

    print("Roads loaded:", len(roads))

    # Make sure both datasets use the same CRS
    if roads.crs != raster_crs:

        roads = roads.to_crs(raster_crs)

    flooded_roads = []

    for index, road in roads.iterrows():

        geometry = road.geometry

        if geometry is None:
            continue

        # Create a raster mask for this road
        road_mask = geometry_mask(
            [geometry],
            transform=transform,
            invert=True,
            out_shape=flood_mask.shape
        )

        road_pixels = flood_mask[road_mask]

        if len(road_pixels) == 0:

            flood_percentage = 0

        else:

            flood_percentage = (
                road_pixels > 0
            ).sum() / len(road_pixels) * 100

        road_copy = road.copy()

        road_copy["flood_pct"] = round(
            flood_percentage,
            2
        )

        if flood_percentage >= 50:

            road_copy["status"] = "HIGH RISK"

        elif flood_percentage >= 20:

            road_copy["status"] = "MODERATE RISK"

        elif flood_percentage > 0:

            road_copy["status"] = "LOW RISK"

        else:

            road_copy["status"] = "CLEAR"

        flooded_roads.append(road_copy)

    result = gpd.GeoDataFrame(
        flooded_roads,
        crs=raster_crs
    )

    return result


def save_results(result):

    Path("data/processed").mkdir(
        parents=True,
        exist_ok=True
    )

    result.to_file(
        OUTPUT_PATH,
        driver="GeoJSON"
    )

    print("\nInfrastructure analysis saved!")

    print(
        "Output:",
        OUTPUT_PATH
    )


if __name__ == "__main__":

    print("=" * 50)

    print(
        "     FLOODRA INFRASTRUCTURE ANALYSIS"
    )

    print("=" * 50)

    result = analyse_roads()

    print("\n========== ROAD RISK SUMMARY ==========")

    print(
        result["status"]
        .value_counts()
        .to_string()
    )

    print("========================================")

    save_results(result)