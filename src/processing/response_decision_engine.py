
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import json
import math


BASE_DIR = Path(__file__).resolve().parents[2]
PROCESSED_DIR = BASE_DIR / "data" / "processed"

PRIORITY_FILE = PROCESSED_DIR / "rescue_priority.geojson"
CONNECTIVITY_FILE = PROCESSED_DIR / "connectivity_analysis.geojson"
ROADS_FILE = PROCESSED_DIR / "real_flooded_roads.geojson"
OUTPUT_FILE = PROCESSED_DIR / "response_decision_report.json"


def load_geojson(path):
    if not path.exists():
        print(f"WARNING: Missing input: {path.name}")
        return []

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    return data.get("features", [])


def safe_number(value, default=0):
    try:
        number = float(value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError):
        return default


def main():
    priorities = load_geojson(PRIORITY_FILE)
    connectivity = load_geojson(CONNECTIVITY_FILE)
    roads = load_geojson(ROADS_FILE)

    connectivity_by_name = {}

    for feature in connectivity:
        props = feature.get("properties", {})
        name = props.get("name")

        if name:
            connectivity_by_name[str(name).strip().lower()] = props

    road_counts = Counter(
        str(f.get("properties", {}).get("risk_level", "UNKNOWN")).upper()
        for f in roads
    )

    decisions = []

    for feature in priorities:
        props = feature.get("properties", {})
        name = props.get("name") or "Unnamed settlement"

        connection = connectivity_by_name.get(
            str(name).strip().lower(), {}
        )

        priority_level = str(
            props.get("priority_level", "UNKNOWN")
        ).upper()

        connectivity_status = connection.get(
            "connectivity_status", "UNKNOWN"
        )

        isolation_level = str(
            props.get("isolation_level", "UNKNOWN")
        ).upper()

        rescue_score = safe_number(props.get("rescue_score"))
        reasons = []

        if isolation_level == "CRITICAL":
            reasons.append("Critical heuristic isolation score")

        if connectivity_status == "POTENTIALLY DISCONNECTED":
            reasons.append(
                "Outside the largest road-network component "
                "in the high-risk-road exclusion scenario"
            )
        elif connectivity_status == "UNKNOWN":
            reasons.append(
                "Connectivity could not be established reliably"
            )

        road_level = str(
            props.get("nearest_risky_road_level", "UNKNOWN")
        ).upper()

        if road_level in {"HIGH RISK", "MODERATE RISK"}:
            reasons.append(
                f"Nearest classified road risk: {road_level}"
            )

        if not reasons:
            reasons.append(
                "Ranked using the available heuristic rescue-priority score"
            )

        if priority_level == "CRITICAL":
            recommended_action = (
                "Urgently verify conditions and access with local "
                "emergency authorities."
            )
        elif connectivity_status == "POTENTIALLY DISCONNECTED":
            recommended_action = (
                "Verify road access and identify an alternative route "
                "using current authoritative road information."
            )
        elif connectivity_status == "UNKNOWN":
            recommended_action = (
                "Verify settlement location and road-network coverage "
                "before making access decisions."
            )
        else:
            recommended_action = (
                "Monitor conditions and validate reported exposure."
            )

        decisions.append({
            "settlement": name,
            "priority_level": priority_level,
            "rescue_score": round(rescue_score, 2),
            "isolation_level": isolation_level,
            "connectivity_status": connectivity_status,
            "nearest_risky_road_level": road_level,
            "reasons": reasons,
            "recommended_action": recommended_action,
            "geometry": feature.get("geometry"),
        })

    priority_order = {
        "CRITICAL": 0,
        "HIGH": 1,
        "MEDIUM": 2,
        "LOW": 3,
        "UNKNOWN": 4,
    }

    decisions.sort(
        key=lambda item: (
            priority_order.get(item["priority_level"], 4),
            -item["rescue_score"],
        )
    )

    summary = {
        "settlements_assessed": len(decisions),
        "priority_counts": dict(
            Counter(item["priority_level"] for item in decisions)
        ),
        "connectivity_counts": dict(
            Counter(item["connectivity_status"] for item in decisions)
        ),
        "road_risk_counts": dict(road_counts),
    }

    report = {
        "project": "FLOODRA",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "method": "Rule-based decision support using existing heuristic outputs",
        "summary": summary,
        "decisions": decisions,
        "limitations": [
            "Flood classifications have not been independently validated.",
            "Priority scores are heuristic rankings, not calibrated probabilities.",
            "Connectivity results are road-graph scenarios, not proof of isolation.",
            "Recommendations require verification with current local conditions.",
            "A missing connectivity match is reported as UNKNOWN.",
        ],
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(report, file, indent=2, allow_nan=False)

    print("\nFLOODRA Response Decision Report")
    print("--------------------------------")
    print(f"Settlements assessed: {summary['settlements_assessed']}")
    print(f"Priority counts: {summary['priority_counts']}")
    print(f"Connectivity counts: {summary['connectivity_counts']}")
    print(f"Saved report: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
