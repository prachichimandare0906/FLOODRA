
from pathlib import Path
import json

import numpy as np
import rasterio


BASE_DIR = Path(__file__).resolve().parents[2]

MASK_PATH = BASE_DIR / "data" / "processed" / "flood_mask.tif"
SEVERITY_PATH = BASE_DIR / "data" / "processed" / "flood_severity.tif"
ROADS_PATH = BASE_DIR / "data" / "processed" / "real_flooded_roads.geojson"
ISOLATION_PATH = BASE_DIR / "data" / "processed" / "isolated_areas.geojson"
PRIORITY_PATH = BASE_DIR / "data" / "processed" / "rescue_priority.geojson"

OUTPUT_PATH = BASE_DIR / "data" / "processed" / "analysis_report.json"


def count_geojson_features(path):
    if not path.exists():
        return 0

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    return len(data.get("features", []))


def main():
    print("=" * 60)
    print("FLOODRA - FLOOD ANALYSIS QUALITY REPORT")
    print("=" * 60)

    if not MASK_PATH.exists():
        raise FileNotFoundError(
            f"Flood mask not found: {MASK_PATH}"
        )

    with rasterio.open(MASK_PATH) as src:
        mask = src.read(1)
        crs = str(src.crs) if src.crs else None
        width = src.width
        height = src.height
        transform = src.transform

        flooded_pixels = int(np.count_nonzero(mask == 1))
        total_pixels = int(mask.size)
        non_flood_pixels = total_pixels - flooded_pixels

        flooded_percentage = (
            flooded_pixels / total_pixels * 100
            if total_pixels else 0.0
        )

        # This is the affine pixel area in coordinate units.
        pixel_area_coordinate_units = abs(
            transform.a * transform.e
            - transform.b * transform.d
        )

    report = {
        "project": "FLOODRA",
        "report_type": "Flood analysis quality report",
        "method": (
            "Threshold-based baseline flood-mask classification; "
            "not a trained or independently validated AI model."
        ),
        "validation_status": "NOT INDEPENDENTLY VALIDATED",
        "source_raster": str(
            MASK_PATH.relative_to(BASE_DIR)
        ),
        "raster": {
            "width_pixels": width,
            "height_pixels": height,
            "total_pixels": total_pixels,
            "crs": crs,
        },
        "flood_detection": {
            "flooded_pixels": flooded_pixels,
            "non_flood_pixels": non_flood_pixels,
            "flooded_pixel_percentage": round(
                flooded_percentage, 2
            ),
        },
        "other_outputs": {
            "severity_raster_exists": SEVERITY_PATH.exists(),
            "road_features": count_geojson_features(ROADS_PATH),
            "isolation_locations": count_geojson_features(
                ISOLATION_PATH
            ),
            "rescue_priority_locations": count_geojson_features(
                PRIORITY_PATH
            ),
        },
        "limitations": [
            "The flood mask uses a threshold rather than a trained model.",
            "Flood detections have not been independently validated.",
            "Road risk depends on intersection with the generated flood mask.",
            "Isolation and rescue scores are heuristic estimates.",
            "The report does not establish actual damage or safe rescue routes.",
        ],
    }

    # Record pixel area in coordinate units only; don't label it m²
    # unless the raster CRS uses metre-based projected coordinates.
    report["raster"]["pixel_area_coordinate_units_squared"] = round(
        pixel_area_coordinate_units, 12
    )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        json.dump(report, file, indent=4)

    print("\nFlooded pixels:", flooded_pixels)
    print("Flooded pixel percentage:", f"{flooded_percentage:.2f}%")
    print("Road features:", report["other_outputs"]["road_features"])
    print("Isolation locations:", report["other_outputs"]["isolation_locations"])
    print(
        "Rescue-priority locations:",
        report["other_outputs"]["rescue_priority_locations"],
    )
    print("\nValidation:", report["validation_status"])
    print("Report saved to:", OUTPUT_PATH)


if __name__ == "__main__":
    main()
