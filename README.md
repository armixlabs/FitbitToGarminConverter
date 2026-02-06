# Fitbit to Garmin Connect CSV Converter

Converts Fitbit health data from a [Google Takeout](https://takeout.google.com/) export into CSV files that can be imported directly into [Garmin Connect](https://connect.garmin.com/).

## Requirements

- Python 3.8+
- No external dependencies (uses only the Python standard library)

## Quick Start

```bash
# Convert all available data
python convert_fitbit_to_garmin.py ~/Downloads/Takeout/Fitbit

# Convert a specific date range
python convert_fitbit_to_garmin.py ~/Downloads/Takeout/Fitbit --start 2025-01-01 --end 2025-12-31

# Specify a custom output directory
python convert_fitbit_to_garmin.py ~/Downloads/Takeout/Fitbit -o ./garmin_import
```

## How to Get Your Fitbit Data

1. Go to [Google Takeout](https://takeout.google.com/)
2. Deselect all products, then select only **Fitbit**
3. Click "Next step" and choose your export format (ZIP recommended)
4. Wait for the export to be ready and download it
5. Unzip the archive — the `Fitbit` folder inside `Takeout/` is what this script needs

## Usage

```
python convert_fitbit_to_garmin.py <fitbit_dir> [options]
```

| Argument | Description |
|---|---|
| `fitbit_dir` | Path to the `Fitbit` folder inside your Google Takeout export |
| `-o`, `--output` | Output directory (default: parent of `fitbit_dir`) |
| `-s`, `--start` | Start date in `YYYY-MM-DD` format (default: all data) |
| `-e`, `--end` | End date in `YYYY-MM-DD` format (default: all data) |

## Generated Files

### Garmin Connect Importable

These three files can be uploaded directly at [connect.garmin.com/modern/import-data](https://connect.garmin.com/modern/import-data):

| File | Content |
|---|---|
| `garmin_body.csv` | Weight (kg), BMI, body fat % |
| `garmin_activities.csv` | Daily steps, calories, distance (km), floors, active minutes |
| `garmin_sleep.csv` | Sleep sessions with REM, light and deep sleep stages |

### Supplementary Data

These files contain additional health metrics that Garmin Connect doesn't support importing via CSV. They are provided for reference or use with other tools:

| File | Content |
|---|---|
| `garmin_supplement_resting_hr.csv` | Daily resting heart rate |
| `garmin_supplement_hrv.csv` | Heart rate variability (RMSSD, entropy) |
| `garmin_supplement_respiratory_rate.csv` | Daily respiratory rate |
| `garmin_supplement_spo2.csv` | Blood oxygen saturation (SpO2) |
| `garmin_supplement_sleep_scores.csv` | Sleep quality scores |
| `garmin_supplement_readiness.csv` | Daily readiness scores |

## Importing into Garmin Connect

1. Go to [Garmin Connect](https://connect.garmin.com/) and log in
2. Click the import icon (cloud with upward arrow) in the top right corner
3. Select **Import Data**
4. Browse and select the `garmin_body.csv`, `garmin_activities.csv`, and/or `garmin_sleep.csv` files
5. Choose your preferred unit system (metric/imperial) when prompted

**Important notes:**

- Do **not** open the CSV files in Excel before importing — Excel reformats the data and makes the files invalid for Garmin. Use a plain text editor if you want to inspect them.
- Sleep data import can be unreliable on Garmin's side. If sleep data doesn't appear after import, this is a known Garmin limitation.
- It is recommended to import no more than one year of data at a time.

## Data Sources

The script reads from these folders inside the Fitbit export:

```
Fitbit/
├── Physical Activity_GoogleData/   (steps, calories, distance, floors, active minutes, HR, HRV, ...)
├── Global Export Data/             (weight JSON with BMI and body fat)
├── Health Fitness Data_GoogleData/ (sleep sessions and sleep stages)
├── Sleep Score/                    (sleep quality scores)
└── Oxygen Saturation (SpO2)/      (daily and minute-level SpO2)
```

## Formats and Units

- **Weight:** kilograms (converted from lbs in the Fitbit export)
- **Distance:** kilometers (converted from meters in the Fitbit export)
- **Dates:** `YYYY-MM-DD` (body/activities), `MM/DD/YYYY HH:MM` (sleep)
- **Numbers:** decimal point (e.g. `85.7`), no thousands separator
- **Column headers:** English (required by Garmin Connect)

## License

MIT
