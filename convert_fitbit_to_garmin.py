#!/usr/bin/env python3
"""
Convert Fitbit Google Takeout data to Garmin Connect importable CSV files.

Reads a Fitbit data export (Google Takeout format) and generates CSV files
that can be directly imported into Garmin Connect, plus supplementary CSVs
for health metrics that Garmin doesn't support importing.

Usage:
    python convert_fitbit_to_garmin.py <fitbit_dir> [options]

Example:
    python convert_fitbit_to_garmin.py ~/Downloads/Takeout/Fitbit
    python convert_fitbit_to_garmin.py ~/Downloads/Takeout/Fitbit --start 2025-01-01 --end 2025-12-31
    python convert_fitbit_to_garmin.py ~/Downloads/Takeout/Fitbit -o ./output
"""

import argparse
import json
import csv
import os
import glob
import sys
from datetime import datetime, date, timedelta
from collections import defaultdict


# ============================================================
# DATE PARSING UTILITIES
# ============================================================

def parse_date(dt_str):
    """Parse various date formats to date object."""
    try:
        if isinstance(dt_str, date) and not isinstance(dt_str, datetime):
            return dt_str
        dt_str = str(dt_str).strip()
        if 'T' in dt_str:
            return datetime.fromisoformat(dt_str.replace('Z', '+00:00')).date()
        try:
            return datetime.strptime(dt_str, '%Y-%m-%d').date()
        except ValueError:
            pass
        try:
            return datetime.strptime(dt_str, '%m/%d/%y').date()
        except ValueError:
            pass
        return datetime.fromisoformat(dt_str).date()
    except (ValueError, TypeError):
        return None


def parse_sleep_datetime(dt_str):
    """Parse sleep datetime format like '2025-12-03 21:12:30+0000'."""
    try:
        dt_str = str(dt_str).strip()
        if '+' in dt_str and 'T' not in dt_str:
            parts = dt_str.rsplit('+', 1)
            base = parts[0]
            tz = parts[1]
            if len(tz) == 4:
                dt_str = base + '+' + tz[:2] + ':' + tz[2:]
            dt_str = dt_str.replace(' ', 'T', 1)
        elif 'T' not in dt_str and '+' not in dt_str:
            dt_str = dt_str.replace(' ', 'T', 1)
        return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
    except (ValueError, TypeError):
        return None


# ============================================================
# CONVERTER CLASS
# ============================================================

class FitbitToGarminConverter:
    """Converts Fitbit Google Takeout data to Garmin Connect CSV format."""

    def __init__(self, fitbit_dir, output_dir, start_date, end_date):
        self.fitbit_dir = fitbit_dir
        self.output_dir = output_dir
        self.start_date = start_date
        self.end_date = end_date

        # Subdirectories within the Fitbit export
        self.pa_dir = os.path.join(fitbit_dir, "Physical Activity_GoogleData")
        self.ge_dir = os.path.join(fitbit_dir, "Global Export Data")
        self.hf_dir = os.path.join(fitbit_dir, "Health Fitness Data_GoogleData")
        self.sleep_score_dir = os.path.join(fitbit_dir, "Sleep Score")
        self.spo2_dir = os.path.join(fitbit_dir, "Oxygen Saturation (SpO2)")

    # --------------------------------------------------------
    # 1. BODY DATA (Weight, BMI, Fat)
    # --------------------------------------------------------
    def generate_body_csv(self):
        """Generate Garmin-compatible Body CSV from weight data."""
        print("Generating Body CSV...")
        body_data = {}

        # Source 1: Global Export Data JSON files (weight in lbs, with BMI and fat%)
        json_files = glob.glob(os.path.join(self.ge_dir, "weight-*.json"))
        for jf in sorted(json_files):
            try:
                with open(jf) as f:
                    entries = json.load(f)
                for entry in entries:
                    d = parse_date(entry.get('date', ''))
                    if d and self.start_date <= d <= self.end_date:
                        weight_lbs = float(entry.get('weight', 0))
                        weight_kg = round(weight_lbs * 0.453592, 1)
                        bmi = round(float(entry.get('bmi', 0)), 1)
                        fat = round(float(entry.get('fat', 0)), 1)
                        date_str = d.strftime('%Y-%m-%d')
                        body_data[date_str] = {
                            'weight': weight_kg,
                            'bmi': bmi,
                            'fat': fat
                        }
            except Exception as e:
                print(f"  Warning: Error reading {jf}: {e}")

        # Fallback: CSV weight data (in grams)
        if not body_data:
            weight_csv = os.path.join(self.pa_dir, "weight.csv")
            if os.path.exists(weight_csv):
                with open(weight_csv) as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        d = parse_date(row.get('timestamp', ''))
                        if d and self.start_date <= d <= self.end_date:
                            weight_g = float(row.get('weight grams', 0))
                            weight_kg = round(weight_g / 1000, 1)
                            date_str = d.strftime('%Y-%m-%d')
                            body_data[date_str] = {
                                'weight': weight_kg,
                                'bmi': 0,
                                'fat': 0
                            }

        # Enrich with body fat from body_fat CSV files
        bf_files = glob.glob(os.path.join(self.pa_dir, "body_fat_*.csv"))
        for bf in sorted(bf_files):
            try:
                with open(bf) as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        d = parse_date(row.get('timestamp', ''))
                        if d and self.start_date <= d <= self.end_date:
                            date_str = d.strftime('%Y-%m-%d')
                            fat = float(row.get('body fat percentage', 0))
                            if date_str in body_data:
                                body_data[date_str]['fat'] = round(fat, 1)
                            else:
                                body_data[date_str] = {'weight': 0, 'bmi': 0, 'fat': round(fat, 1)}
            except Exception as e:
                print(f"  Warning: Error reading {bf}: {e}")

        # Write Garmin-compatible Body CSV
        output_path = os.path.join(self.output_dir, "garmin_body.csv")
        with open(output_path, 'w', newline='') as f:
            f.write("Body\n")
            f.write("Date,Weight,BMI,Fat\n")
            for date_str in sorted(body_data.keys()):
                d = body_data[date_str]
                f.write(f'"{date_str}","{d["weight"]}","{d["bmi"]}","{d["fat"]}"\n')

        print(f"  Body CSV: {len(body_data)} entries -> {output_path}")
        return body_data

    # --------------------------------------------------------
    # 2. ACTIVITIES DATA (Daily Summaries)
    # --------------------------------------------------------
    def _aggregate_csv(self, pattern, value_col, cast=float):
        """Aggregate minute-level CSV data into daily totals."""
        daily = defaultdict(float)
        for fp in sorted(glob.glob(os.path.join(self.pa_dir, pattern))):
            try:
                with open(fp) as f:
                    for row in csv.DictReader(f):
                        d = parse_date(row.get('timestamp', ''))
                        if d and self.start_date <= d <= self.end_date:
                            daily[d.strftime('%Y-%m-%d')] += cast(row.get(value_col, 0))
            except Exception as e:
                print(f"  Warning: Error reading {fp}: {e}")
        return daily

    def generate_activities_csv(self):
        """Generate Garmin-compatible Activities CSV from minute-level data."""
        print("Generating Activities CSV...")

        print("  Processing steps...")
        daily_steps = self._aggregate_csv("steps_*.csv", "steps", lambda x: int(float(x)))

        print("  Processing calories...")
        daily_calories = self._aggregate_csv("calories_*.csv", "calories")

        print("  Processing distance...")
        daily_distance = self._aggregate_csv("distance_*.csv", "distance")

        print("  Processing floors...")
        daily_floors = self._aggregate_csv("floors_*.csv", "floors", lambda x: int(float(x)))

        # Active minutes (light, moderate, very)
        print("  Processing active minutes...")
        daily_light = defaultdict(int)
        daily_fairly = defaultdict(int)
        daily_very = defaultdict(int)
        for af in sorted(glob.glob(os.path.join(self.pa_dir, "active_minutes_*.csv"))):
            try:
                with open(af) as f:
                    for row in csv.DictReader(f):
                        d = parse_date(row.get('timestamp', ''))
                        if d and self.start_date <= d <= self.end_date:
                            ds = d.strftime('%Y-%m-%d')
                            daily_light[ds] += int(float(row.get('light', 0)))
                            daily_fairly[ds] += int(float(row.get('moderate', 0)))
                            daily_very[ds] += int(float(row.get('very', 0)))
            except Exception as e:
                print(f"  Warning: Error reading {af}: {e}")

        # Sedentary minutes from activity_level
        print("  Processing activity levels for sedentary minutes...")
        daily_sedentary = defaultdict(int)
        for al_file in sorted(glob.glob(os.path.join(self.pa_dir, "activity_level_*.csv"))):
            try:
                with open(al_file) as f:
                    for row in csv.DictReader(f):
                        d = parse_date(row.get('timestamp', ''))
                        if d and self.start_date <= d <= self.end_date:
                            if row.get('level', '') == 'SEDENTARY':
                                daily_sedentary[d.strftime('%Y-%m-%d')] += 1
            except Exception as e:
                print(f"  Warning: Error reading {al_file}: {e}")

        # Collect all dates
        all_dates = sorted(set(
            list(daily_steps.keys()) + list(daily_calories.keys()) +
            list(daily_distance.keys())
        ))

        # Write Garmin-compatible Activities CSV
        output_path = os.path.join(self.output_dir, "garmin_activities.csv")
        with open(output_path, 'w', newline='') as f:
            f.write("Activities\n")
            f.write("Date,Calories Burned,Steps,Distance,Floors,Minutes Sedentary,"
                    "Minutes Lightly Active,Minutes Fairly Active,Minutes Very Active,"
                    "Activity Calories\n")
            for ds in all_dates:
                cal = int(round(daily_calories.get(ds, 0)))
                steps = int(daily_steps.get(ds, 0))
                dist_km = round(daily_distance.get(ds, 0) / 1000, 2)
                floors = int(daily_floors.get(ds, 0))
                sedentary = daily_sedentary.get(ds, 0)
                light = daily_light.get(ds, 0)
                fairly = daily_fairly.get(ds, 0)
                very = daily_very.get(ds, 0)
                act_cal = max(0, cal - 1500) if cal > 0 else 0

                f.write(f'"{ds}","{cal}","{steps}","{dist_km}","{floors}",'
                        f'"{sedentary}","{light}","{fairly}","{very}","{act_cal}"\n')

        print(f"  Activities CSV: {len(all_dates)} days -> {output_path}")
        return all_dates

    # --------------------------------------------------------
    # 3. SLEEP DATA
    # --------------------------------------------------------
    def generate_sleep_csv(self):
        """Generate Garmin-compatible Sleep CSV from UserSleeps and UserSleepStages."""
        print("Generating Sleep CSV...")

        sleeps = {}
        for sf in sorted(glob.glob(os.path.join(self.hf_dir, "UserSleeps_*.csv"))):
            print(f"  Reading {os.path.basename(sf)}...")
            try:
                with open(sf) as f:
                    for row in csv.DictReader(f):
                        start_dt = parse_sleep_datetime(row.get('sleep_start', ''))
                        if start_dt and self.start_date <= start_dt.date() <= self.end_date:
                            sleep_id = row.get('sleep_id', '')
                            sleeps[sleep_id] = {
                                'start': row.get('sleep_start', ''),
                                'end': row.get('sleep_end', ''),
                                'start_dt': start_dt,
                                'end_dt': parse_sleep_datetime(row.get('sleep_end', '')),
                                'minutes_asleep': int(float(row.get('minutes_asleep', 0))),
                                'minutes_awake': int(float(row.get('minutes_awake', 0))),
                                'minutes_in_period': int(float(row.get('minutes_in_sleep_period', 0))),
                                'start_offset': row.get('start_utc_offset', '+01:00'),
                                'end_offset': row.get('end_utc_offset', '+01:00'),
                            }
            except Exception as e:
                print(f"  Warning: Error reading {sf}: {e}")

        print(f"  Found {len(sleeps)} sleep sessions in date range")

        # Read sleep stages for REM/Light/Deep breakdown
        sleep_stages = defaultdict(lambda: {'rem': 0, 'light': 0, 'deep': 0, 'awake_count': 0})
        for stf in sorted(glob.glob(os.path.join(self.hf_dir, "UserSleepStages_*.csv"))):
            try:
                with open(stf) as f:
                    for row in csv.DictReader(f):
                        sleep_id = row.get('sleep_id', '')
                        if sleep_id in sleeps:
                            stage_type = row.get('sleep_stage_type', '')
                            s_dt = parse_sleep_datetime(row.get('sleep_stage_start', ''))
                            e_dt = parse_sleep_datetime(row.get('sleep_stage_end', ''))
                            if s_dt and e_dt:
                                duration = (e_dt - s_dt).total_seconds() / 60
                                if stage_type == 'REM':
                                    sleep_stages[sleep_id]['rem'] += duration
                                elif stage_type == 'LIGHT':
                                    sleep_stages[sleep_id]['light'] += duration
                                elif stage_type == 'DEEP':
                                    sleep_stages[sleep_id]['deep'] += duration
                                elif stage_type == 'AWAKE':
                                    sleep_stages[sleep_id]['awake_count'] += 1
            except Exception as e:
                print(f"  Warning: Error reading {stf}: {e}")

        # Write Garmin-compatible Sleep CSV
        output_path = os.path.join(self.output_dir, "garmin_sleep.csv")
        with open(output_path, 'w', newline='') as f:
            f.write("Sleep\n")
            f.write("Start Time,End Time,Minutes Asleep,Minutes Awake,"
                    "Number of Awakenings,Time in Bed,Minutes REM Sleep,"
                    "Minutes Light Sleep,Minutes Deep Sleep\n")

            for sleep_id in sorted(sleeps.keys(), key=lambda x: sleeps[x]['start']):
                s = sleeps[sleep_id]
                stages = sleep_stages.get(sleep_id,
                                          {'rem': 0, 'light': 0, 'deep': 0, 'awake_count': 0})
                start_dt = s['start_dt']
                end_dt = s['end_dt']

                if start_dt and end_dt:
                    # Apply UTC offset to get local time
                    for key, dt_ref in [('start_offset', 'start'), ('end_offset', 'end')]:
                        offset_str = s[key]
                        try:
                            offset_h = int(offset_str.replace(':', '')[:-2]) if offset_str else 0
                        except (ValueError, IndexError):
                            offset_h = 0
                        if key == 'start_offset':
                            start_local = start_dt + timedelta(hours=offset_h)
                        else:
                            end_local = end_dt + timedelta(hours=offset_h)

                    f.write(f'"{start_local.strftime("%m/%d/%Y %H:%M")}",'
                            f'"{end_local.strftime("%m/%d/%Y %H:%M")}",'
                            f'"{s["minutes_asleep"]}","{s["minutes_awake"]}",'
                            f'"{stages["awake_count"]}","{s["minutes_in_period"]}",'
                            f'"{int(round(stages["rem"]))}",'
                            f'"{int(round(stages["light"]))}",'
                            f'"{int(round(stages["deep"]))}"\n')

        print(f"  Sleep CSV: {len(sleeps)} sleep sessions -> {output_path}")
        return sleeps

    # --------------------------------------------------------
    # 4. SUPPLEMENTARY DATA (not directly Garmin-importable)
    # --------------------------------------------------------
    def _write_supplement(self, filename, fieldnames, data):
        """Write a supplementary CSV file."""
        output_path = os.path.join(self.output_dir, filename)
        with open(output_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
        return output_path

    def _read_daily_csv(self, filepath, value_cols):
        """Read a daily summary CSV and filter by date range."""
        data = []
        if not os.path.exists(filepath):
            return data
        with open(filepath) as f:
            for row in csv.DictReader(f):
                d = parse_date(row.get('timestamp', ''))
                if d and self.start_date <= d <= self.end_date:
                    entry = {'date': d.strftime('%Y-%m-%d')}
                    for out_key, csv_key in value_cols.items():
                        entry[out_key] = row.get(csv_key, '')
                    data.append(entry)
        return data

    def generate_supplementary_csvs(self):
        """Generate additional CSV files for health metrics."""
        print("Generating supplementary CSVs...")

        # Resting Heart Rate
        print("  Processing resting heart rate...")
        rhr_data = self._read_daily_csv(
            os.path.join(self.pa_dir, "daily_resting_heart_rate.csv"),
            {'resting_hr': 'beats per minute'}
        )
        for entry in rhr_data:
            try:
                entry['resting_hr'] = round(float(entry['resting_hr']), 1)
            except (ValueError, TypeError):
                pass
        self._write_supplement("garmin_supplement_resting_hr.csv",
                               ['date', 'resting_hr'], rhr_data)
        print(f"    Resting HR: {len(rhr_data)} entries")

        # Heart Rate Variability
        print("  Processing HRV...")
        hrv_data = self._read_daily_csv(
            os.path.join(self.pa_dir, "daily_heart_rate_variability.csv"),
            {
                'hrv_rmssd': 'average heart rate variability milliseconds',
                'nrem_hr': 'non rem heart rate beats per minute',
                'entropy': 'entropy',
                'deep_sleep_rmssd': 'deep sleep root mean square of successive differences milliseconds'
            }
        )
        self._write_supplement("garmin_supplement_hrv.csv",
                               ['date', 'hrv_rmssd', 'nrem_hr', 'entropy', 'deep_sleep_rmssd'],
                               hrv_data)
        print(f"    HRV: {len(hrv_data)} entries")

        # Respiratory Rate
        print("  Processing respiratory rate...")
        rr_data = self._read_daily_csv(
            os.path.join(self.pa_dir, "daily_respiratory_rate.csv"),
            {'respiratory_rate': 'breaths per minute'}
        )
        self._write_supplement("garmin_supplement_respiratory_rate.csv",
                               ['date', 'respiratory_rate'], rr_data)
        print(f"    Respiratory Rate: {len(rr_data)} entries")

        # SpO2
        print("  Processing SpO2...")
        spo2_data = []
        spo2_files = sorted(glob.glob(os.path.join(self.spo2_dir, "Daily SpO2 - *.csv")))
        for sf in spo2_files:
            try:
                with open(sf) as f:
                    for row in csv.DictReader(f):
                        d = parse_date(row.get('timestamp', ''))
                        if d and self.start_date <= d <= self.end_date:
                            spo2_data.append({
                                'date': d.strftime('%Y-%m-%d'),
                                'avg_spo2': row.get('average_value', ''),
                                'min_spo2': row.get('lower_bound', ''),
                                'max_spo2': row.get('upper_bound', '')
                            })
            except Exception as e:
                print(f"  Warning: Error reading {sf}: {e}")
        self._write_supplement("garmin_supplement_spo2.csv",
                               ['date', 'avg_spo2', 'min_spo2', 'max_spo2'], spo2_data)
        print(f"    SpO2: {len(spo2_data)} entries")

        # Sleep Scores
        print("  Processing sleep scores...")
        score_file = os.path.join(self.sleep_score_dir, "sleep_score.csv")
        sleep_score_data = []
        if os.path.exists(score_file):
            with open(score_file) as f:
                for row in csv.DictReader(f):
                    d = parse_date(row.get('timestamp', ''))
                    if d and self.start_date <= d <= self.end_date:
                        sleep_score_data.append({
                            'date': d.strftime('%Y-%m-%d'),
                            'overall_score': row.get('overall_score', ''),
                            'composition_score': row.get('composition_score', ''),
                            'revitalization_score': row.get('revitalization_score', ''),
                            'duration_score': row.get('duration_score', ''),
                            'deep_sleep_min': row.get('deep_sleep_in_minutes', ''),
                            'resting_hr': row.get('resting_heart_rate', '')
                        })
        self._write_supplement("garmin_supplement_sleep_scores.csv",
                               ['date', 'overall_score', 'composition_score',
                                'revitalization_score', 'duration_score',
                                'deep_sleep_min', 'resting_hr'],
                               sleep_score_data)
        print(f"    Sleep Scores: {len(sleep_score_data)} entries")

        # Daily Readiness
        print("  Processing daily readiness...")
        readiness_data = self._read_daily_csv(
            os.path.join(self.pa_dir, "daily_readiness.csv"),
            {
                'score': 'score',
                'level': 'type',
                'hrv_readiness': 'heart rate variability readiness',
                'rhr_readiness': 'resting heart rate readiness',
                'sleep_readiness': 'sleep readiness'
            }
        )
        self._write_supplement("garmin_supplement_readiness.csv",
                               ['date', 'score', 'level', 'hrv_readiness',
                                'rhr_readiness', 'sleep_readiness'],
                               readiness_data)
        print(f"    Readiness: {len(readiness_data)} entries")

    # --------------------------------------------------------
    # RUN ALL
    # --------------------------------------------------------
    def convert(self):
        """Run the full conversion pipeline."""
        print("=" * 60)
        print("Fitbit to Garmin Connect CSV Converter")
        print(f"  Source:     {self.fitbit_dir}")
        print(f"  Output:     {self.output_dir}")
        if self.start_date == date(2000, 1, 1) and self.end_date == date(2099, 12, 31):
            print("  Date range: all available data")
        else:
            print(f"  Date range: {self.start_date} to {self.end_date}")
        print("=" * 60)
        print()

        # Validate input directory
        if not os.path.isdir(self.fitbit_dir):
            print(f"Error: Fitbit directory not found: {self.fitbit_dir}")
            sys.exit(1)

        if not os.path.isdir(self.pa_dir):
            print(f"Error: Expected subdirectory not found: {self.pa_dir}")
            print("Make sure you point to the 'Fitbit' folder inside your Google Takeout export.")
            sys.exit(1)

        os.makedirs(self.output_dir, exist_ok=True)

        body_data = self.generate_body_csv()
        print()
        all_dates = self.generate_activities_csv()
        print()
        sleep_data = self.generate_sleep_csv()
        print()
        self.generate_supplementary_csvs()

        print()
        print("=" * 60)
        print("DONE! Generated files:")
        print()
        print("GARMIN CONNECT IMPORTABLE:")
        print("  Upload at: https://connect.garmin.com/modern/import-data")
        print(f"  1. garmin_body.csv          - Weight/BMI/Fat ({len(body_data)} entries)")
        print(f"  2. garmin_activities.csv     - Daily activity summary ({len(all_dates)} days)")
        print(f"  3. garmin_sleep.csv          - Sleep sessions ({len(sleep_data)} nights)")
        print()
        print("SUPPLEMENTARY DATA (for reference, not directly importable):")
        print("  4. garmin_supplement_resting_hr.csv")
        print("  5. garmin_supplement_hrv.csv")
        print("  6. garmin_supplement_respiratory_rate.csv")
        print("  7. garmin_supplement_spo2.csv")
        print("  8. garmin_supplement_sleep_scores.csv")
        print("  9. garmin_supplement_readiness.csv")
        print()
        print("IMPORTANT: Do NOT open the CSV files in Excel before importing!")
        print("Excel changes the formatting and makes them invalid for Garmin.")
        print("=" * 60)


# ============================================================
# CLI ENTRY POINT
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Convert Fitbit Google Takeout data to Garmin Connect CSV format.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s ~/Downloads/Takeout/Fitbit
  %(prog)s ~/Downloads/Takeout/Fitbit --start 2025-01-01 --end 2025-12-31
  %(prog)s ~/Downloads/Takeout/Fitbit -o ./garmin_import

The script expects the standard Google Takeout Fitbit export structure:
  <fitbit_dir>/
    Physical Activity_GoogleData/
    Global Export Data/
    Health Fitness Data_GoogleData/
    Sleep Score/
    Oxygen Saturation (SpO2)/
        """
    )

    parser.add_argument(
        "fitbit_dir",
        help="Path to the Fitbit folder inside your Google Takeout export"
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output directory for generated CSV files (default: same as fitbit_dir parent)"
    )
    parser.add_argument(
        "-s", "--start",
        default=None,
        help="Start date in YYYY-MM-DD format (default: all available data)"
    )
    parser.add_argument(
        "-e", "--end",
        default=None,
        help="End date in YYYY-MM-DD format (default: all available data)"
    )

    args = parser.parse_args()

    # Resolve paths
    fitbit_dir = os.path.abspath(args.fitbit_dir)
    output_dir = os.path.abspath(args.output) if args.output else os.path.dirname(fitbit_dir)

    # Parse dates
    if args.start:
        try:
            start_date = datetime.strptime(args.start, '%Y-%m-%d').date()
        except ValueError:
            print(f"Error: Invalid start date '{args.start}'. Use YYYY-MM-DD format.")
            sys.exit(1)
    else:
        start_date = date(2000, 1, 1)

    if args.end:
        try:
            end_date = datetime.strptime(args.end, '%Y-%m-%d').date()
        except ValueError:
            print(f"Error: Invalid end date '{args.end}'. Use YYYY-MM-DD format.")
            sys.exit(1)
    else:
        end_date = date(2099, 12, 31)

    converter = FitbitToGarminConverter(fitbit_dir, output_dir, start_date, end_date)
    converter.convert()


if __name__ == '__main__':
    main()
