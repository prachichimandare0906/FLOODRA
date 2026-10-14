# FLOODRA — AI-Powered Flood Damage & Connectivity Mapping

FLOODRA is a student-hackathon MVP for mapping flood-affected areas from satellite imagery and preparing the data for road/bridge/connectivity analysis.

## Current MVP
1. Load a Sentinel-1 GeoTIFF.
2. Inspect raster metadata.
3. Normalize SAR backscatter.
4. Create a baseline flood mask using a configurable threshold.
5. Display the normalized image and flood mask.
6. Calculate the percentage of pixels classified as flooded.

> Important: The current threshold detector is a baseline/demo method, not a production-grade AI model. It should be replaced or validated against labeled flood data before real emergency use.

## Project structure

```text
FLOODRA/
├── app.py
├── requirements.txt
├── .gitignore
├── README.md
├── data/
│   └── raw/
│       └── README.txt
└── src/
    ├── __init__.py
    ├── preprocessing/
    │   ├── __init__.py
    │   ├── satellite_viewer.py
    │   └── preprocess.py
    └── processing/
        ├── __init__.py
        └── flood_detector.py
```

## Setup on Windows

From the FLOODRA folder:

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Place your Sentinel-1 GeoTIFF at:

```text
data\raw\flood_image.tif
```

Then run:

```powershell
python src\preprocessing\satellite_viewer.py
```

For preprocessing:

```powershell
python src\preprocessing\preprocess.py
```

For flood detection:

```powershell
python src\processing\flood_detector.py
```

## Notes about Sentinel-1

SAR images can look dark/noisy compared with normal optical satellite imagery. This is expected. Flood detection quality depends strongly on acquisition date, polarization, terrain, preprocessing, threshold selection, and whether pre-flood/post-flood imagery is available.

## Next planned modules

- Pre-flood vs post-flood change detection
- AI/ML flood segmentation
- Road and bridge exposure mapping
- Connectivity/isolated-area analysis
- Interactive map dashboard
- Severity scoring
- Secure data/audit layer
