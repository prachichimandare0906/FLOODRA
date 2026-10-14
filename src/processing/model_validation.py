
import json
from pathlib import Path

import numpy as np
import rasterio


BASE_DIR = Path(__file__).resolve().parents[2]
PROCESSED_DIR = BASE_DIR / "data" / "processed"

FLOOD_MASK_PATH = PROCESSED_DIR / "flood_mask.tif"
SEVERITY_PATH = PROCESSED_DIR / "flood_severity.tif"
REPORT_PATH = PROCESSED_DIR / "model_validation_report.json"


def check_raster(path, label):
    """Check whether a raster is readable and has valid metadata."""

    if not path.is_file():
        return {
            "name": label,
            "passed": False,
            "message": f"File missing: {path.name}",
        }

    try:
        with rasterio.open(path) as src:
            data = src.read(1, masked=True)

            result = {
                "name": label,
                "passed": True,
                "file": str(path.relative_to(BASE_DIR)),
                "width": src.width,
                "height": src.height,
                "bands": src.count,
                "crs": str(src.crs) if src.crs else None,
                "dtype": src.dtypes[0],
                "nodata": (
                    float(src.nodata)
                    if src.nodata is not None
                    else None
                ),
                "valid_pixels": int(data.count()),
                "message": "Raster opened successfully.",
            }

            if src.width == 0 or src.height == 0:
                result["passed"] = False
                result["message"] = "Raster has invalid dimensions."

            if src.crs is None:
                result["passed"] = False
                result["message"] = "Raster has no CRS metadata."

            return result

    except Exception as error:
        return {
            "name": label,
            "passed": False,
            "message": f"Could not read raster: {error}",
        }


def compare_rasters():
    """Check whether flood mask and severity raster align."""

    if not FLOOD_MASK_PATH.is_file() or not SEVERITY_PATH.is_file():
        return {
            "name": "Raster alignment",
            "passed": False,
            "message": "One or both rasters are missing.",
        }

    try:
        with rasterio.open(FLOOD_MASK_PATH) as mask_src, \
                rasterio.open(SEVERITY_PATH) as severity_src:

            same_grid = (
                mask_src.width == severity_src.width
                and mask_src.height == severity_src.height
                and mask_src.transform == severity_src.transform
                and mask_src.crs == severity_src.crs
            )

            return {
                "name": "Raster alignment",
                "passed": bool(same_grid),
                "message": (
                    "Rasters share the same grid and CRS."
                    if same_grid
                    else "Raster dimensions, transform, or CRS differ."
                ),
            }

    except Exception as error:
        return {
            "name": "Raster alignment",
            "passed": False,
            "message": str(error),
        }


def check_severity_values():
    """Ensure valid severity pixels use only classes 0 through 3."""

    if not SEVERITY_PATH.is_file():
        return {
            "name": "Severity class values",
            "passed": False,
            "message": "Severity raster is missing.",
        }

    try:
        with rasterio.open(SEVERITY_PATH) as src:
            data = src.read(1, masked=True)
            values = np.asarray(data.compressed())

        if values.size == 0:
            return {
                "name": "Severity class values",
                "passed": False,
                "message": "No valid severity pixels found.",
            }

        unique_values = sorted(int(value) for value in np.unique(values))
        valid_classes = all(value in (0, 1, 2, 3) for value in unique_values)

        return {
            "name": "Severity class values",
            "passed": valid_classes,
            "unique_values": unique_values,
            "message": (
                "All valid pixels use classes 0, 1, 2, or 3."
                if valid_classes
                else "Unexpected class values found."
            ),
        }

    except Exception as error:
        return {
            "name": "Severity class values",
            "passed": False,
            "message": str(error),
        }


def check_flood_mask_values():
    """Check the flood mask's non-NoData values."""

    if not FLOOD_MASK_PATH.is_file():
        return {
            "name": "Flood mask values",
            "passed": False,
            "message": "Flood mask is missing.",
        }

    try:
        with rasterio.open(FLOOD_MASK_PATH) as src:
            data = src.read(1, masked=True)
            values = np.asarray(data.compressed())

        if values.size == 0:
            return {
                "name": "Flood mask values",
                "passed": False,
                "message": "No valid flood-mask pixels found.",
            }

        unique_values = sorted(
            float(value) for value in np.unique(values)
        )
        valid_values = all(value in (0.0, 1.0) for value in unique_values)

        return {
            "name": "Flood mask values",
            "passed": valid_values,
            "unique_values": unique_values,
            "message": (
                "Mask contains only 0 and 1."
                if valid_values
                else "Unexpected values found; inspect the mask encoding."
            ),
        }

    except Exception as error:
        return {
            "name": "Flood mask values",
            "passed": False,
            "message": str(error),
        }


def main():
    print("=" * 60)
    print("FLOODRA - RASTER DATA QUALITY CHECK")
    print("=" * 60)

    checks = [
        check_raster(FLOOD_MASK_PATH, "Flood mask raster"),
        check_raster(SEVERITY_PATH, "Severity raster"),
        compare_rasters(),
        check_severity_values(),
        check_flood_mask_values(),
    ]

    passed = sum(bool(check["passed"]) for check in checks)

    report = {
        "title": "FLOODRA Raster Data Quality Report",
        "checks_passed": passed,
        "checks_total": len(checks),
        "structural_validation_passed": passed == len(checks),
        "checks": checks,
        "limitations": [
            "These checks assess file integrity and class encoding, not flood-detection accuracy.",
            "No independent ground-truth flood labels are evaluated.",
            "Severity classes are relative heuristic categories, not measured flood depths.",
        ],
    }

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    for check in checks:
        status = "PASS" if check["passed"] else "FAIL"
        print(f"[{status}] {check['name']}: {check['message']}")

    print(f"\nChecks passed: {passed}/{len(checks)}")
    print(f"Report saved: {REPORT_PATH}")

    if passed != len(checks):
        print("Some checks failed. Inspect the report before proceeding.")
        return 1

    print("All structural checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
