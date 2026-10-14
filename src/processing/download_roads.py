import osmnx as ox
import rasterio

from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]

RASTER_PATH = (
    BASE_DIR /
    "data" /
    "raw" /
    "flood_image.tif"
)

OUTPUT_PATH = (
    BASE_DIR /
    "data" /
    "raw" /
    "real_roads.geojson"
)


def download_roads():

    print("=" * 55)
    print("       FLOODRA REAL ROAD DATA")
    print("=" * 55)


    # ---------------------------------------------
    # Read satellite bounds
    # ---------------------------------------------

    with rasterio.open(
        RASTER_PATH
    ) as src:

        bounds = src.bounds

        west = bounds.left
        south = bounds.bottom
        east = bounds.right
        north = bounds.top

        print(
            "\nSatellite scene bounds:"
        )

        print("West :", west)
        print("South:", south)
        print("East :", east)
        print("North:", north)


    # ---------------------------------------------
    # Download OSM roads
    # ---------------------------------------------

    print(
        "\nDownloading roads from OpenStreetMap..."
    )


    graph = ox.graph_from_bbox(
        bbox=(
            west,
            south,
            east,
            north
        ),
        network_type="drive"
    )


    # ---------------------------------------------
    # Convert graph to GeoDataFrame
    # ---------------------------------------------

    roads = ox.graph_to_gdfs(
        graph,
        nodes=False,
        edges=True
    )


    # ---------------------------------------------
    # Convert to WGS84
    # ---------------------------------------------

    roads = roads.to_crs(
        "EPSG:4326"
    )


    # ---------------------------------------------
    # Save
    # ---------------------------------------------

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )


    roads.to_file(
        OUTPUT_PATH,
        driver="GeoJSON"
    )


    print(
        "\nReal road data downloaded!"
    )

    print(
        "Number of roads:",
        len(roads)
    )

    print(
        "Output:",
        OUTPUT_PATH
    )


if __name__ == "__main__":

    download_roads()