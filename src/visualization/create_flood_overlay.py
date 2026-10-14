import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import transform_bounds
from PIL import Image


BASE_DIR = Path(__file__).resolve().parents[2]

MASK_PATH = BASE_DIR / "data" / "processed" / "flood_mask.tif"
OUTPUT_IMAGE = BASE_DIR / "dashboard" / "static" / "flood_overlay.png"
OUTPUT_BOUNDS = BASE_DIR / "dashboard" / "static" / "flood_overlay_bounds.json"


def create_overlay():

    if not MASK_PATH.exists():
        print("ERROR: flood_mask.tif not found!")
        print(f"Expected location: {MASK_PATH}")
        return

    print("Loading flood mask...")

    with rasterio.open(MASK_PATH) as src:

        mask = src.read(1)

        print("Raster CRS:", src.crs)
        print("Raster size:", src.width, "x", src.height)
        print("Raster bounds:", src.bounds)

        # -------------------------------------------------
        # Convert raster bounds to WGS84
        # -------------------------------------------------

        if src.crs is None:

            print("\nWARNING: Raster CRS is missing.")
            print("Using raster coordinates directly for now.")

            west = src.bounds.left
            south = src.bounds.bottom
            east = src.bounds.right
            north = src.bounds.top

            bounds = (
                west,
                south,
                east,
                north
            )

        else:

            bounds = transform_bounds(
                src.crs,
                "EPSG:4326",
                *src.bounds
            )

    # -----------------------------------------------------
    # Identify flood pixels
    # -----------------------------------------------------

    flood = mask == 1

    # -----------------------------------------------------
    # Create transparent RGBA overlay
    # -----------------------------------------------------

    rgba = np.zeros(
        (mask.shape[0], mask.shape[1], 4),
        dtype=np.uint8
    )

    # Blue flood area
    rgba[flood, 0] = 0
    rgba[flood, 1] = 120
    rgba[flood, 2] = 255
    rgba[flood, 3] = 170

    image = Image.fromarray(
        rgba,
        mode="RGBA"
    )

    # -----------------------------------------------------
    # Save overlay image
    # -----------------------------------------------------

    OUTPUT_IMAGE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    image.save(
        OUTPUT_IMAGE
    )

    # -----------------------------------------------------
    # Save Leaflet bounds
    # -----------------------------------------------------

    west, south, east, north = bounds

    leaflet_bounds = {
        "south": south,
        "west": west,
        "north": north,
        "east": east
    }

    with open(
        OUTPUT_BOUNDS,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            leaflet_bounds,
            file,
            indent=4
        )

    # -----------------------------------------------------
    # Statistics
    # -----------------------------------------------------

    flood_pixels = int(
        np.sum(flood)
    )

    total_pixels = int(
        mask.size
    )

    percentage = (
        flood_pixels / total_pixels * 100
        if total_pixels > 0
        else 0
    )

    # -----------------------------------------------------
    # Final output
    # -----------------------------------------------------

    print("\n" + "=" * 50)
    print("       FLOODRA FLOOD OVERLAY")
    print("=" * 50)

    print(f"Flood pixels      : {flood_pixels}")
    print(f"Total pixels      : {total_pixels}")
    print(f"Flood percentage  : {percentage:.2f}%")

    print("\nFiles created:")

    print(f"Overlay image:")
    print(OUTPUT_IMAGE)

    print(f"\nBounds file:")
    print(OUTPUT_BOUNDS)

    print("\nFlood overlay created successfully!")


if __name__ == "__main__":
    create_overlay()