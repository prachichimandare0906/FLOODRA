from pathlib import Path

import geopandas as gpd
import rasterio

from rasterio.features import geometry_mask

from shapely.geometry import mapping


BASE_DIR = Path(__file__).resolve().parents[2]


RASTER_PATH = (
    BASE_DIR /
    "data" /
    "processed" /
    "flood_mask.tif"
)


ROADS_PATH = (
    BASE_DIR /
    "data" /
    "raw" /
    "real_roads.geojson"
)


OUTPUT_PATH = (
    BASE_DIR /
    "data" /
    "processed" /
    "real_flooded_roads.geojson"
)


def calculate_road_risk():

    print("=" * 55)
    print("       FLOODRA REAL ROAD RISK ANALYSIS")
    print("=" * 55)


    if not RASTER_PATH.exists():

        print(
            "ERROR: flood_mask.tif not found!"
        )

        return


    if not ROADS_PATH.exists():

        print(
            "ERROR: real_roads.geojson not found!"
        )

        return


    # ---------------------------------------------
    # Load flood mask
    # ---------------------------------------------

    print(
        "\nLoading flood mask..."
    )


    with rasterio.open(
        RASTER_PATH
    ) as src:

        flood_mask = src.read(1)

        raster_crs = src.crs

        raster_transform = src.transform

        raster_height = src.height

        raster_width = src.width


        print(
            "Raster CRS:",
            raster_crs
        )

        print(
            "Raster size:",
            raster_width,
            "x",
            raster_height
        )


        # -----------------------------------------
        # Load roads
        # -----------------------------------------

        print(
            "\nLoading OpenStreetMap roads..."
        )


        roads = gpd.read_file(
            ROADS_PATH
        )


        print(
            "Roads loaded:",
            len(roads)
        )


        # -----------------------------------------
        # Reproject roads
        # -----------------------------------------

        roads = roads.to_crs(
            raster_crs
        )


        flood_percentages = []

        risk_levels = []


        print(
            "\nAnalyzing road flood exposure..."
        )


        # -----------------------------------------
        # Analyze every road
        # -----------------------------------------

        for _, road in roads.iterrows():

            geometry = road.geometry


            if (
                geometry is None
                or geometry.is_empty
            ):

                flood_percentages.append(
                    0.0
                )

                risk_levels.append(
                    "CLEAR"
                )

                continue


            road_mask = geometry_mask(
                [mapping(geometry)],
                transform=raster_transform,
                invert=True,
                out_shape=(
                    raster_height,
                    raster_width
                )
            )


            road_pixels = int(
                road_mask.sum()
            )


            if road_pixels == 0:

                flood_percentage = 0.0

            else:

                flooded_pixels = int(
                    (
                        flood_mask[road_mask] == 1
                    ).sum()
                )


                flood_percentage = (
                    flooded_pixels /
                    road_pixels *
                    100
                )


            # -----------------------------------------
            # Risk classification
            # -----------------------------------------

            if flood_percentage >= 50:

                risk = "HIGH RISK"

            elif flood_percentage >= 20:

                risk = "MODERATE RISK"

            elif flood_percentage > 0:

                risk = "LOW RISK"

            else:

                risk = "CLEAR"


            flood_percentages.append(
                round(
                    float(flood_percentage),
                    2
                )
            )


            risk_levels.append(
                risk
            )


        # -----------------------------------------
        # Add attributes
        # -----------------------------------------

        roads[
            "flood_pct"
        ] = flood_percentages


        roads[
            "risk_level"
        ] = risk_levels


        # -----------------------------------------
        # Convert for web map
        # -----------------------------------------

        roads = roads.to_crs(
            "EPSG:4326"
        )


        # -----------------------------------------
        # Save
        # -----------------------------------------

        OUTPUT_PATH.parent.mkdir(
            parents=True,
            exist_ok=True
        )


        roads.to_file(
            OUTPUT_PATH,
            driver="GeoJSON"
        )


    # ---------------------------------------------
    # Statistics
    # ---------------------------------------------

    high = sum(
        risk == "HIGH RISK"
        for risk in risk_levels
    )

    moderate = sum(
        risk == "MODERATE RISK"
        for risk in risk_levels
    )

    low = sum(
        risk == "LOW RISK"
        for risk in risk_levels
    )

    clear = sum(
        risk == "CLEAR"
        for risk in risk_levels
    )


    print("\n" + "=" * 55)

    print(
        "ROAD RISK ANALYSIS COMPLETE"
    )

    print("=" * 55)

    print(
        f"Total roads   : {len(roads)}"
    )

    print(
        f"High risk     : {high}"
    )

    print(
        f"Moderate risk : {moderate}"
    )

    print(
        f"Low risk      : {low}"
    )

    print(
        f"Clear         : {clear}"
    )

    print(
        "\nOutput:"
    )

    print(
        OUTPUT_PATH
    )


if __name__ == "__main__":

    calculate_road_risk()