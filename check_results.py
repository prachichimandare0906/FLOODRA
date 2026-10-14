
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

FILES = {
    "Road Risk": BASE_DIR / "data/processed/real_flooded_roads.geojson",
    "Isolation Risk": BASE_DIR / "data/processed/isolated_areas.geojson",
    "Rescue Priority": BASE_DIR / "data/processed/rescue_priority.geojson",
}


def load_features(path):
    if not path.exists():
        print(f"File missing: {path}")
        return []

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    return data.get("features", [])


def main():
    for label, path in FILES.items():
        features = load_features(path)
        print(f"\n{'=' * 55}")
        print(f"{label}: {len(features)} features")
        print("=" * 55)

        if not features:
            print("No features found.")
            continue

        properties = [
            feature.get("properties") or {}
            for feature in features
        ]

        if label == "Road Risk":
            field = "risk_level"
            print("Risk-level distribution:")

        elif label == "Isolation Risk":
            field = "risk_level"
            if not any(field in item for item in properties):
                field = "isolation_level"
            print("Isolation-level distribution:")

        else:
            field = "priority_level"
            print("Rescue-priority distribution:")

        counts = {}
        for item in properties:
            value = item.get(field, "UNKNOWN")
            counts[value] = counts.get(value, 0) + 1

        for level, count in sorted(counts.items()):
            print(f"  {level}: {count}")

        print("\nSample records:")
        for item in properties[:3]:
            print(json.dumps(item, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
