
from flask import Flask, render_template, jsonify
from pathlib import Path
import json

import numpy as np
import rasterio
from pyproj import Geod
from flask import send_file
from io import BytesIO
from datetime import datetime

# =====================================================
# FLASK APP
# =====================================================

app = Flask(__name__)

# =====================================================
# PATHS
# =====================================================

BASE_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"


# =====================================================
# GEOJSON LOADER
# =====================================================

def load_geojson(filename):
    path = PROCESSED_DIR / filename

    if not path.exists():
        return {
            "type": "FeatureCollection",
            "features": [],
        }

    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if data.get("type") != "FeatureCollection":
            return {
                "type": "FeatureCollection",
                "features": [],
            }

        return data

    except (json.JSONDecodeError, OSError) as exc:
        app.logger.exception("Could not load %s", path)
        return {
            "type": "FeatureCollection",
            "features": [],
            "error": str(exc),
        }


def get_features(filename):
    data = load_geojson(filename)
    return data.get("features", [])


# =====================================================
# HOME
# =====================================================

@app.route("/")
def index():
    return render_template("index.html")


# =====================================================
# ROAD RISK API
# =====================================================

@app.route("/api/roads")
def roads():
    return jsonify(load_geojson("real_flooded_roads.geojson"))


# =====================================================
# ISOLATION API
# =====================================================

@app.route("/api/isolation")
def isolation():
    return jsonify(load_geojson("isolated_areas.geojson"))


# =====================================================
# RESCUE PRIORITY API
# =====================================================

@app.route("/api/priority")
def priority():
    return jsonify(load_geojson("rescue_priority.geojson"))


# =====================================================
# DASHBOARD SUMMARY API
# =====================================================

@app.route("/api/summary")
def summary():
    road_features = get_features("real_flooded_roads.geojson")
    isolation_features = get_features("isolated_areas.geojson")
    priority_features = get_features("rescue_priority.geojson")

    high_risk_roads = sum(
        1
        for feature in road_features
        if str(
            (feature.get("properties") or {}).get("risk_level", "")
        ).upper() == "HIGH RISK"
    )

    critical_zones = sum(
        1
        for feature in priority_features
        if str(
            (feature.get("properties") or {}).get("priority_level", "")
        ).upper() == "CRITICAL"
    )

    priority_counts = {
        "CRITICAL": 0,
        "HIGH": 0,
        "MEDIUM": 0,
        "LOW": 0,
    }

    for feature in priority_features:
        properties = feature.get("properties") or {}
        level = str(properties.get("priority_level", "")).upper()

        if level in priority_counts:
            priority_counts[level] += 1

    return jsonify({
        "status": "OK",
        "high_risk_roads": high_risk_roads,
        "isolation_risks": len(isolation_features),
        "critical_zones": critical_zones,
        "total_priority_locations": len(priority_features),
        "priority_counts": priority_counts,
    })


# =====================================================
# SYSTEM STATUS
# =====================================================

@app.route("/api/status")
def status():
    return jsonify({
        "system": "FLOODRA",
        "status": "ONLINE",
        "analysis": "Satellite Flood Analysis",
        "message": "Emergency mapping system ready",
    })


# =====================================================
# FLOOD STATISTICS
# =====================================================

@app.route("/api/flood-stats")
def flood_stats():
    raster_path = PROCESSED_DIR / "flood_mask.tif"

    if not raster_path.exists():
        return jsonify({
            "status": "ERROR",
            "message": "Flood mask not found",
        }), 404

    try:
        with rasterio.open(raster_path) as src:
            mask = src.read(1)
            transform = src.transform
            crs = src.crs

            # Count pixels classified as flooded.
            flood_pixels = int(np.count_nonzero(mask == 1))
            total_pixels = int(mask.size)

            flood_percentage = (
                flood_pixels / total_pixels * 100
                if total_pixels else 0.0
            )

            # Calculate the area of one pixel.
            if crs is not None and crs.is_geographic:
                geod = Geod(ellps="WGS84")

                x0 = transform.c
                y0 = transform.f
                x1 = x0 + transform.a
                y1 = y0 + transform.e

                pixel_area, _ = geod.polygon_area_perimeter(
                    [x0, x1, x1, x0],
                    [y0, y0, y1, y1],
                )

                pixel_area = abs(pixel_area)

            else:
                pixel_area = abs(transform.a * transform.e)

                # Convert projected CRS units to square metres.
                if crs is not None:
                    factors = [
                        axis.unit_conversion_factor
                        for axis in crs.axis_info[:2]
                    ]

                    if len(factors) == 2:
                        pixel_area *= factors[0] * factors[1]

            flooded_area_m2 = flood_pixels * pixel_area
            flooded_area_km2 = flooded_area_m2 / 1_000_000

        return jsonify({
            "status": "OK",
            "flood_pixels": flood_pixels,
            "total_pixels": total_pixels,
            "flood_percentage": round(flood_percentage, 2),
            "flood_area_km2": round(flooded_area_km2, 3),
        })

    except Exception:
        app.logger.exception("Flood statistics calculation failed")
        return jsonify({
            "status": "ERROR",
            "message": "Could not calculate flood statistics. Check the server log.",
        }), 500


# =====================================================
# ANALYSIS REPORT API
# =====================================================

@app.route("/api/analysis-report")
def analysis_report():
    report_path = PROCESSED_DIR / "analysis_report.json"

    if not report_path.exists():
        return jsonify({
            "status": "ERROR",
            "message": (
                "Analysis report not found. "
                "Run: python -m src.processing.analysis_report"
            )
        }), 404

    try:
        with report_path.open("r", encoding="utf-8") as file:
            report = json.load(file)

        return jsonify({
            "status": "OK",
            "report": report
        })

    except (json.JSONDecodeError, OSError):
        app.logger.exception("Failed to load analysis report")

        return jsonify({
            "status": "ERROR",
            "message": "Could not read the analysis report."
        }), 500

# =====================================================
# ROAD RISK DISTRIBUTION API
# =====================================================

@app.route("/api/road-risk-summary")
def road_risk_summary():
    features = load_geojson("real_flooded_roads.geojson").get(
        "features", []
    )

    counts = {
        "HIGH RISK": 0,
        "MODERATE RISK": 0,
        "LOW RISK": 0,
        "CLEAR": 0,
    }

    for feature in features:
        properties = feature.get("properties") or {}
        level = str(properties.get("risk_level", "CLEAR")).upper()

        if level in counts:
            counts[level] += 1

    return jsonify({
        "status": "OK",
        "total_segments": len(features),
        "risk_distribution": counts,
    })

# =====================================================
# DOWNLOAD EMERGENCY ANALYSIS REPORT
# =====================================================

@app.route("/api/download-report")
def download_report():
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
    )

    roads = load_geojson("real_flooded_roads.geojson").get(
        "features", []
    )
    isolation = load_geojson("isolated_areas.geojson").get(
        "features", []
    )
    priority = load_geojson("rescue_priority.geojson").get(
        "features", []
    )

    road_counts = {
        "HIGH RISK": 0,
        "MODERATE RISK": 0,
        "LOW RISK": 0,
        "CLEAR": 0,
    }

    for feature in roads:
        properties = feature.get("properties") or {}
        level = str(properties.get("risk_level", "CLEAR")).upper()
        if level in road_counts:
            road_counts[level] += 1

    priority_counts = {
        "CRITICAL": 0,
        "HIGH": 0,
        "MEDIUM": 0,
        "LOW": 0,
    }

    for feature in priority:
        properties = feature.get("properties") or {}
        level = str(properties.get("priority_level", "")).upper()
        if level in priority_counts:
            priority_counts[level] += 1

    critical_locations = [
        feature.get("properties") or {}
        for feature in priority
        if str(
            (feature.get("properties") or {}).get(
                "priority_level", ""
            )
        ).upper() == "CRITICAL"
    ]

    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.8 * cm,
        leftMargin=1.8 * cm,
        topMargin=1.8 * cm,
        bottomMargin=1.8 * cm,
    )

    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("FLOODRA", styles["Title"]))
    story.append(
        Paragraph(
            "Flood Damage &amp; Connectivity Analysis Report",
            styles["Heading2"],
        )
    )
    story.append(
        Paragraph(
            "Generated: " + datetime.now().astimezone().strftime(
                "%d %B %Y, %H:%M %Z"
            ),
            styles["Normal"],
        )
    )
    story.append(Spacer(1, 18))

    story.append(Paragraph("1. Analysis Summary", styles["Heading2"]))

    summary_data = [
        ["Metric", "Count"],
        ["Road segments analyzed", str(len(roads))],
        ["High-risk roads", str(road_counts["HIGH RISK"])],
        ["Isolation-risk locations", str(len(isolation))],
        ["Rescue-priority locations", str(len(priority))],
        ["Critical rescue-priority locations", str(priority_counts["CRITICAL"])],
    ]

    table = Table(summary_data, colWidths=[10 * cm, 5 * cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#102a43")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("PADDING", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(table)
    story.append(Spacer(1, 16))

    story.append(Paragraph("2. Road Risk Distribution", styles["Heading2"]))

    road_data = [["Risk category", "Segments"]]
    for level, count in road_counts.items():
        road_data.append([level, str(count)])

    table = Table(road_data, colWidths=[10 * cm, 5 * cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#102a43")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(table)
    story.append(Spacer(1, 16))

    story.append(Paragraph("3. Rescue Priority", styles["Heading2"]))

    priority_data = [["Priority", "Locations"]]
    for level, count in priority_counts.items():
        priority_data.append([level, str(count)])

    table = Table(priority_data, colWidths=[10 * cm, 5 * cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#102a43")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(table)
    story.append(Spacer(1, 16))

    story.append(
        Paragraph("4. Critical Locations", styles["Heading2"])
    )

    if critical_locations:
        for location in critical_locations:
            name = str(location.get("name") or "Unnamed settlement")
            score = location.get("rescue_score", "N/A")
            story.append(
                Paragraph(
                    f"{name} — Rescue score: {score}/100",
                    styles["Normal"],
                )
            )
    else:
        story.append(
            Paragraph(
                "No critical rescue-priority locations were recorded.",
                styles["Normal"],
            )
        )

    story.append(Spacer(1, 16))
    story.append(
        Paragraph("5. Validation and Limitations", styles["Heading2"])
    )
    story.append(
        Paragraph(
            "FLOODRA currently uses a threshold-based flood mask and "
            "heuristic road-exposure, isolation, and rescue-priority scores. "
            "The results have not been independently validated. They do not "
            "confirm real-world damage, safe routes, or actual isolation. "
            "Verify findings with authoritative data and field responders "
            "before operational use.",
            styles["Normal"],
        )
    )

    document.build(story)
    buffer.seek(0)

    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name="FLOODRA_Emergency_Analysis_Report.pdf",
    )

# =====================================================
# CONNECTIVITY SCENARIO API
# =====================================================

@app.route("/api/connectivity")
def connectivity():
    return jsonify(
        load_geojson("connectivity_analysis.geojson")
    )

# =====================================================
# CONNECTIVITY SUMMARY API
# =====================================================

@app.route("/api/connectivity-summary")
def connectivity_summary():
    data = load_geojson("connectivity_analysis.geojson")
    features = data.get("features", [])

    total = len(features)

    connected = sum(
        1
        for feature in features
        if (
            feature.get("properties") or {}
        ).get("scenario_connected_to_largest_component") is True
    )

    outside_largest_component = total - connected

    return jsonify({
        "status": "OK",
        "total_settlements": total,
        "connected_settlements": connected,
        "outside_largest_component": outside_largest_component,
        "interpretation": (
            "Simplified graph scenario only; not verified physical "
            "accessibility or confirmed settlement isolation."
        ),
    })

# =====================================================
# START SERVER
# =====================================================

@app.route("/api/response-decisions")
def response_decisions():
    report_path = PROCESSED_DIR / "response_decision_report.json"

    if not report_path.exists():
        return jsonify({
            "error": "Response decision report not found",
            "message": (
                "Run src/processing/response_decision_engine.py first."
            )
        }), 404

    try:
        with report_path.open("r", encoding="utf-8") as file:
            report = json.load(file)

        return jsonify(report)

    except (OSError, json.JSONDecodeError) as error:
        return jsonify({
            "error": "Unable to read response decision report",
            "message": str(error)
        }), 500

@app.route("/api/model-validation")
def model_validation():
    report_path = PROCESSED_DIR / "model_validation_report.json"

    if not report_path.exists():
        return jsonify({
            "status": "ERROR",
            "message": (
                "Validation report not found. Run "
                "src/processing/model_validation.py first."
            )
        }), 404

    try:
        with report_path.open("r", encoding="utf-8") as file:
            report = json.load(file)

        return jsonify({
            "status": "OK",
            "report": report
        })

    except (OSError, json.JSONDecodeError) as error:
        return jsonify({
            "status": "ERROR",
            "message": str(error)
        }), 500

if __name__ == "__main__":
    print("=" * 55)
    print("             FLOODRA DASHBOARD")
    print("=" * 55)
    print("Dashboard: http://127.0.0.1:5000")
    print("=" * 55)

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True,
    )
