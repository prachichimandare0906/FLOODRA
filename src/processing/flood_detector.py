import numpy as np
import matplotlib.pyplot as plt
import rasterio

from src.preprocessing.preprocess import load_image, normalize_image


IMAGE_PATH = "data/raw/flood_image.tif"
OUTPUT_PATH = "data/processed/flood_mask.tif"

THRESHOLD = 0.30


# =====================================================
# FLOOD DETECTION
# =====================================================

def detect_flood(image, threshold=THRESHOLD):

    normalized = normalize_image(image)

    flood_mask = normalized < threshold

    return normalized, flood_mask


# =====================================================
# SAVE GEOREFERENCED FLOOD MASK
# =====================================================

def save_flood_mask(mask):

    with rasterio.open(IMAGE_PATH) as src:

        profile = src.profile.copy()

        # Preserve source CRS, transform, bounds,
        # width, height and other spatial metadata.
        profile.update(
            dtype=rasterio.uint8,
            count=1,
            compress="lzw",
            nodata=0
        )

        with rasterio.open(
            OUTPUT_PATH,
            "w",
            **profile
        ) as dst:

            dst.write(
                mask.astype(rasterio.uint8),
                1
            )

        print("\nGeoreferencing preserved:")
        print("CRS:", src.crs)
        print("Bounds:", src.bounds)
        print("Transform:", src.transform)


# =====================================================
# DISPLAY RESULT
# =====================================================

def display_result(normalized, flood_mask):

    plt.figure(figsize=(12, 6))

    plt.subplot(1, 2, 1)

    plt.imshow(
        normalized,
        cmap="gray"
    )

    plt.title(
        "Normalized Sentinel-1"
    )

    plt.axis("off")


    plt.subplot(1, 2, 2)

    plt.imshow(
        flood_mask,
        cmap="Blues"
    )

    plt.title(
        "FLOODRA Flood Mask"
    )

    plt.axis("off")

    plt.tight_layout()

    plt.show()


# =====================================================
# MAIN
# =====================================================

if __name__ == "__main__":

    print("=" * 50)
    print("        FLOODRA FLOOD DETECTION")
    print("=" * 50)

    print("\nLoading Sentinel-1 image...")

    image = load_image()

    normalized, flood_mask = detect_flood(
        image
    )

    flood_pixels = int(
        np.sum(flood_mask)
    )

    total_pixels = int(
        flood_mask.size
    )

    flood_percentage = (
        flood_pixels /
        total_pixels *
        100
        if total_pixels > 0
        else 0
    )

    print("\nFlood detection completed!")

    print(
        "Detected flood pixels:",
        flood_pixels
    )

    print(
        "Total pixels:",
        total_pixels
    )

    print(
        f"Estimated flooded pixels: "
        f"{flood_percentage:.2f}%"
    )

    print("\nSaving georeferenced flood mask...")

    save_flood_mask(
        flood_mask
    )

    print(
        "\nFlood mask saved successfully!"
    )

    print(
        f"Output: {OUTPUT_PATH}"
    )

    display_result(
        normalized,
        flood_mask
    )