"""
FLOODRA entry point.

This file provides a simple project-health check so the repository
has a clear executable entry point while the satellite-processing
modules are developed.
"""

from pathlib import Path


def main():
    root = Path(__file__).resolve().parent
    image_path = root / "data" / "raw" / "flood_image.tif"

    print("======================================")
    print("        FLOODRA - Flood Mapping")
    print("======================================")
    print(f"Project folder: {root}")
    print(f"Satellite image: {'FOUND' if image_path.exists() else 'NOT FOUND'}")

    if not image_path.exists():
        print("\nPlace a Sentinel-1 GeoTIFF at:")
        print(image_path)

    print("\nAvailable commands:")
    print("  python src\\preprocessing\\satellite_viewer.py")
    print("  python src\\preprocessing\\preprocess.py")
    print("  python src\\processing\\flood_detector.py")


if __name__ == "__main__":
    main()
