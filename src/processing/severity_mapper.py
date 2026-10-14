
import numpy as np
import matplotlib.pyplot as plt
import rasterio
from pathlib import Path

from src.preprocessing.preprocess import load_image, normalize_image


BASE_DIR = Path(__file__).resolve().parents[2]

IMAGE_PATH = BASE_DIR / "data" / "raw" / "flood_image.tif"
OUTPUT_PATH = BASE_DIR / "data" / "processed" / "flood_severity.tif"

FLOOD_THRESHOLD = 0.30
NODATA_VALUE = 255


def create_severity_map(image):
    """
    Create a relative flood-severity map.

    Values:
        0 = No flood
        1 = Low severity
        2 = Moderate severity
        3 = High severity
        255 = NoData

    Lower normalized SAR backscatter is treated as a stronger
    flood indication in this baseline model.

    Note: This is a heuristic classification, not a validated
    flood-severity prediction model.
    """

    normalized = normalize_image(image)

    # Initialize all pixels as no flood.
    severity = np.zeros(normalized.shape, dtype=np.uint8)

    # Identify invalid pixels if present.
    valid_mask = np.isfinite(normalized)

    # Apply the existing flood threshold only to valid pixels.
    flood_mask = valid_mask & (normalized < FLOOD_THRESHOLD)

    flooded_values = normalized[flood_mask]

    if flooded_values.size > 0:
        # Relative thresholds within detected flooded pixels.
        low_limit = np.percentile(flooded_values, 66)
        high_limit = np.percentile(flooded_values, 33)

        # Lower backscatter = potentially stronger flooding.
        severity[
            flood_mask & (normalized >= low_limit)
        ] = 1

        severity[
            flood_mask
            & (normalized >= high_limit)
            & (normalized < low_limit)
        ] = 2

        severity[
            flood_mask & (normalized < high_limit)
        ] = 3

    # Reserve 255 for invalid pixels.
    severity[~valid_mask] = NODATA_VALUE

    return normalized, severity


def save_severity_map(severity):
    """Save the severity map using the source raster's georeferencing."""

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(IMAGE_PATH) as src:
        profile = src.profile.copy()

        profile.update(
            driver="GTiff",
            dtype="uint8",
            count=1,
            nodata=NODATA_VALUE,
            compress="lzw"
        )

        with rasterio.open(
            OUTPUT_PATH,
            "w",
            **profile
        ) as dst:
            dst.write(severity.astype(np.uint8), 1)


def calculate_statistics(severity):
    """Print class counts while excluding NoData pixels."""

    valid = severity != NODATA_VALUE
    total = int(np.sum(valid))

    no_flood = int(np.sum(valid & (severity == 0)))
    low = int(np.sum(valid & (severity == 1)))
    moderate = int(np.sum(valid & (severity == 2)))
    high = int(np.sum(valid & (severity == 3)))
    nodata = int(np.sum(~valid))

    print("\n========== FLOOD SEVERITY ==========")

    if total > 0:
        print(
            f"No flood:     {no_flood:,} "
            f"({no_flood / total * 100:.2f}%)"
        )
        print(
            f"Low severity: {low:,} "
            f"({low / total * 100:.2f}%)"
        )
        print(
            f"Moderate:     {moderate:,} "
            f"({moderate / total * 100:.2f}%)"
        )
        print(
            f"High:         {high:,} "
            f"({high / total * 100:.2f}%)"
        )
    else:
        print("No valid pixels available for statistics.")

    print(f"NoData pixels: {nodata:,}")
    print("====================================")


def display_severity(severity):
    """Display severity classes without plotting NoData as a class."""

    display_data = np.ma.masked_equal(severity, NODATA_VALUE)

    plt.figure(figsize=(10, 8))

    image = plt.imshow(
        display_data,
        cmap="jet",
        vmin=0,
        vmax=3
    )

    plt.title("FLOODRA - Relative Flood Severity Map")

    plt.colorbar(
        image,
        ticks=[0, 1, 2, 3],
        label="Relative severity (0 = none, 3 = high)"
    )

    plt.axis("off")
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    print("=" * 45)
    print("       FLOODRA FLOOD SEVERITY")
    print("=" * 45)

    print("\nLoading satellite image...")

    image = load_image()

    normalized, severity = create_severity_map(image)

    calculate_statistics(severity)

    print("\nSaving severity map...")

    save_severity_map(severity)

    print("Severity map saved successfully!")
    print(f"Output: {OUTPUT_PATH}")

    display_severity(severity)
