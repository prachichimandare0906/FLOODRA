
import os
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]

PIPELINE = [
    (
        "Flood Detection",
        BASE_DIR / "src" / "processing" / "flood_detector.py",
    ),
    (
        "Flood Severity Mapping",
        BASE_DIR / "src" / "processing" / "severity_mapper.py",
    ),
    (
        "Flood Overlay Generation",
        BASE_DIR / "src" / "visualization" / "create_flood_overlay.py",
    ),
    (
        "Road Risk Analysis",
        BASE_DIR / "src" / "processing" / "real_road_risk.py",
    ),
    (
        "Settlement Isolation Analysis",
        BASE_DIR / "src" / "processing" / "isolated_areas.py",
    ),
    (
        "Rescue Priority Calculation",
        BASE_DIR / "src" / "processing" / "rescue_priority.py",
    ),
    (
        "Road Connectivity Analysis",
        BASE_DIR / "src" / "processing" / "connectivity_analysis.py",
    ),
    (
        "Analysis Report Generation",
        BASE_DIR / "src" / "processing" / "analysis_report.py",
    ),
    (
        "Response Decision Engine",
        BASE_DIR / "src" / "processing" / "response_decision_engine.py",
    ),
    (
        "Model Validation",
        BASE_DIR / "src" / "processing" / "model_validation.py",
    ),
]

REQUIRED_INPUTS = [
    BASE_DIR / "data" / "raw" / "flood_image.tif",
    BASE_DIR / "data" / "raw" / "real_roads.geojson",
    BASE_DIR / "data" / "raw" / "real_settlements.geojson",
]

EXPECTED_OUTPUTS = [
    "data/processed/flood_mask.tif",
    "data/processed/flood_severity.tif",
    "data/processed/real_flooded_roads.geojson",
    "data/processed/isolated_areas.geojson",
    "data/processed/rescue_priority.geojson",
    "data/processed/connectivity_analysis.geojson",
    "data/processed/analysis_report.json",
    "data/processed/response_decision_report.json",
    "data/processed/model_validation_report.json",
    "dashboard/static/flood_overlay.png",
]


def check_inputs():
    missing = [path for path in REQUIRED_INPUTS if not path.is_file()]

    if missing:
        print("\nERROR: Required input files are missing.")

        for path in missing:
            print(f"  - {path.relative_to(BASE_DIR)}")

        print("\nPrepare or download these files before running the pipeline.")
        return False

    return True


def run_pipeline():
    print("=" * 65)
    print("FLOODRA - FLOOD RESPONSE ANALYSIS PIPELINE")
    print("=" * 65)

    if not check_inputs():
        return 1

    # Make the project root discoverable by imports such as:
    # from src.preprocessing.preprocess import ...
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        str(BASE_DIR)
        if not existing_pythonpath
        else str(BASE_DIR) + os.pathsep + existing_pythonpath
    )

    total = len(PIPELINE)

    for index, (stage_name, script_path) in enumerate(PIPELINE, start=1):
        print(f"\n[{index}/{total}] {stage_name}")
        print("-" * 65)

        if not script_path.is_file():
            print(f"ERROR: Script not found: {script_path}")
            return 1

        try:
            result = subprocess.run(
                [sys.executable, str(script_path)],
                cwd=str(BASE_DIR),
                env=env,
                check=False,
            )
        except OSError as error:
            print(f"ERROR: Could not start script: {error}")
            return 1

        if result.returncode != 0:
            print(f"\nPIPELINE STOPPED: {stage_name} failed.")
            print(f"Exit code: {result.returncode}")
            print("Fix the reported error before rerunning the pipeline.")
            return result.returncode or 1

        print(f"COMPLETED: {stage_name}")

    print("\n" + "=" * 65)
    print("FLOODRA PIPELINE FINISHED")
    print("=" * 65)

    missing_outputs = []

    print("\nOutput file check:")

    for relative_path in EXPECTED_OUTPUTS:
        output_path = BASE_DIR / relative_path

        if output_path.is_file():
            print(f"  [FOUND]   {relative_path}")
        else:
            print(f"  [MISSING] {relative_path}")
            missing_outputs.append(relative_path)

    if missing_outputs:
        print("\nWARNING: Some expected outputs were not created.")
        return 1

    print("\nAll expected output files exist.")
    print("Note: file existence does not establish prediction accuracy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_pipeline())
