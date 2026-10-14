
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import rasterize


BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_PREDICTION = BASE_DIR / "data" / "processed" / "flood_mask.tif"
DEFAULT_OUTPUT = BASE_DIR / "data" / "processed" / "flood_accuracy_report.json"


def load_polygon_layer(path, target_crs, label):
    """Load polygons, repair invalid geometries, and reproject them."""

    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"{label} file not found: {path}")

    layer = gpd.read_file(path)

    if layer.empty:
        raise ValueError(f"{label} layer is empty: {path}")

    if layer.crs is None:
        raise ValueError(f"{label} layer has no CRS: {path}")

    layer = layer.to_crs(target_crs)
    layer = layer[
        layer.geometry.notna()
        & ~layer.geometry.is_empty
    ].copy()

    # Repair invalid geometries where supported by the installed
    # GeoPandas/Shapely version.
    invalid = ~layer.geometry.is_valid

    if invalid.any():
        layer.loc[invalid, "geometry"] = (
            layer.loc[invalid, "geometry"].make_valid()
        )

    layer = layer[
        layer.geometry.notna()
        & ~layer.geometry.is_empty
        & layer.geometry.is_valid
    ]

    polygon_types = {"Polygon", "MultiPolygon"}
    layer = layer[
        layer.geometry.geom_type.isin(polygon_types)
    ]

    if layer.empty:
        raise ValueError(
            f"{label} contains no usable polygon geometries."
        )

    return layer


def safe_ratio(numerator, denominator):
    return (
        float(numerator / denominator)
        if denominator
        else None
    )


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate FLOODRA's predicted flood mask against "
            "an independent reference flood extent."
        )
    )

    parser.add_argument(
        "--prediction",
        default=str(DEFAULT_PREDICTION),
        help="Path to FLOODRA's binary flood_mask.tif",
    )

    parser.add_argument(
        "--reference-flood",
        required=True,
        help="Polygon file containing mapped flooded areas only",
    )

    parser.add_argument(
        "--reference-aoi",
        required=True,
        help="Polygon file defining the independently assessed AOI",
    )

    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Path for the JSON accuracy report",
    )

    parser.add_argument(
        "--event-description",
        required=True,
        help="Documented flood event and reference observation date",
    )

    args = parser.parse_args()

    prediction_path = Path(args.prediction)
    output_path = Path(args.output)

    if not prediction_path.is_file():
        raise FileNotFoundError(
            f"Prediction raster not found: {prediction_path}"
        )

    print("=" * 65)
    print("FLOODRA - INDEPENDENT FLOOD MAP EVALUATION")
    print("=" * 65)

    with rasterio.open(prediction_path) as src:
        prediction_data = src.read(1, masked=True)
        prediction = np.asarray(prediction_data.data)
        prediction_valid = ~np.ma.getmaskarray(prediction_data)

        if src.crs is None:
            raise ValueError(
                "Prediction raster has no CRS; cannot align reference data."
            )

        if not np.all(np.isin(np.unique(prediction[prediction_valid]), [0, 1])):
            raise ValueError(
                "Prediction raster must contain binary values 0 and 1 "
                "on valid pixels. Check flood_mask.tif."
            )

        reference_flood = load_polygon_layer(
            args.reference_flood,
            src.crs,
            "Reference flood extent",
        )

        reference_aoi = load_polygon_layer(
            args.reference_aoi,
            src.crs,
            "Reference AOI",
        )

        transform = src.transform
        shape = (src.height, src.width)

        aoi_mask = rasterize(
            [(geom, 1) for geom in reference_aoi.geometry],
            out_shape=shape,
            transform=transform,
            fill=0,
            dtype="uint8",
        ).astype(bool)

        flood_mask = rasterize(
            [(geom, 1) for geom in reference_flood.geometry],
            out_shape=shape,
            transform=transform,
            fill=0,
            dtype="uint8",
        ).astype(bool)

        # Score only pixels within the assessed AOI and valid
        # pixels in the predicted raster.
        evaluation_mask = aoi_mask & prediction_valid

        if not evaluation_mask.any():
            raise ValueError(
                "No overlapping valid pixels between the reference AOI "
                "and prediction raster. Check coordinates, CRS, and files."
            )

        predicted_flood = prediction == 1
        actual_flood = flood_mask

        tp = int(np.sum(
            evaluation_mask & predicted_flood & actual_flood
        ))
        fp = int(np.sum(
            evaluation_mask & predicted_flood & ~actual_flood
        ))
        fn = int(np.sum(
            evaluation_mask & ~predicted_flood & actual_flood
        ))
        tn = int(np.sum(
            evaluation_mask & ~predicted_flood & ~actual_flood
        ))

        evaluated_pixels = tp + fp + fn + tn

        precision = safe_ratio(tp, tp + fp)
        recall = safe_ratio(tp, tp + fn)
        f1 = safe_ratio(
            2 * tp,
            2 * tp + fp + fn,
        )
        iou = safe_ratio(tp, tp + fp + fn)
        accuracy = safe_ratio(tp + tn, evaluated_pixels)

        report = {
            "title": "FLOODRA Independent Flood Map Evaluation",
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "prediction_raster": str(prediction_path),
            "reference_flood_layer": str(
                Path(args.reference_flood)
            ),
            "reference_aoi_layer": str(
                Path(args.reference_aoi)
            ),
            "event_description": args.event_description,
            "crs": str(src.crs),
            "raster_width": src.width,
            "raster_height": src.height,
            "confusion_matrix_pixels": {
                "true_positive": tp,
                "false_positive": fp,
                "false_negative": fn,
                "true_negative": tn,
                "evaluated_pixels": evaluated_pixels,
            },
            "metrics": {
                "precision": precision,
                "recall": recall,
                "f1_score": f1,
                "intersection_over_union": iou,
                "overall_accuracy": accuracy,
            },
            "limitations": [
                "Metrics are valid only if the reference event, date, "
                "location, and flood definition are appropriate.",
                "Reference polygons are rasterized onto the prediction grid; "
                "resolution differences can affect results.",
                "Pixels outside the supplied reference AOI are excluded.",
                "A mapped area outside the flood polygons is treated as "
                "non-flooded within the assessed AOI.",
                "These metrics evaluate the binary flood mask, not severity "
                "classes, road risk, settlement isolation, or rescue priorities.",
            ],
        }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    print(f"Evaluated pixels: {evaluated_pixels:,}")
    print(f"True positives:   {tp:,}")
    print(f"False positives:  {fp:,}")
    print(f"False negatives:  {fn:,}")
    print(f"True negatives:   {tn:,}")

    print("\nMetrics:")
    for name, value in report["metrics"].items():
        if value is None:
            print(f"  {name}: undefined")
        else:
            print(f"  {name}: {value:.4f} ({value * 100:.2f}%)")

    print(f"\nReport saved: {output_path}")
    print(
        "\nEvaluation complete. Interpret these results only after "
        "confirming that the reference event and AOI are appropriate."
    )


if __name__ == "__main__":
    main()
