"""Stage complete new climate months; never invent TCI or replace training data.

Run from repo root: python scripts/refresh_climate.py
Reconstruct and verify TCI before appending new observations; --apply is explicit.
"""
from pathlib import Path
from datetime import date, timedelta
import argparse
import importlib.util
import time
import sys
import shutil
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tci_scoring import score_tci, verify_original
HISTORY = ROOT / "cleaned_data" / "city_month_features.csv"
STAGING = ROOT / "cleaned_data" / "climate_refresh"
KEY = ["Country_dest","City"]
COORDS = ["City_Center_Lat","City_Center_Lon"]
WEATHER = ["Temp_Max_Mean","Temp_Min_Mean","Temp_Mean","RH_Mean","RH_Min_Mean",
           "Precip_Total_mm","Sunshine_h_per_day","Wind_Mean_ms"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--through", help="Last complete month YYYY-MM (default: latest safely available)")
    parser.add_argument("--apply", action="store_true", help="Append verified scored observations, then retrain before serving")
    args = parser.parse_args()
    history = pd.read_csv(HISTORY)
    print("Original scoring parity:",verify_original(history))
    observed = pd.to_datetime(dict(year=history.Year,month=history.Month,day=1)).dt.to_period("M")
    origin = observed.max()
    safe = pd.Period(date.today()-timedelta(days=7),"M")-1
    through = pd.Period(args.through,"M") if args.through else safe
    if through > safe:
        raise SystemExit(f"Archive may be incomplete. Last safely available month: {safe}")
    if through <= origin:
        print(f"No new complete months after {origin}.")
        return
    months = pd.period_range(origin+1,through,freq="M")
    spec = importlib.util.spec_from_file_location("weather_source",ROOT/"python files"/"weather_py.file.py")
    source = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(source)
    source.START_DATE = str(months[0].start_time.date())
    source.END_DATE = str(months[-1].end_time.date())
    folder = STAGING / f"{months[0]}_to_{months[-1]}"
    folder.mkdir(parents=True,exist_ok=True)
    cities = history[KEY+COORDS].drop_duplicates()
    if cities.duplicated(KEY).any():
        raise ValueError("City coordinates vary over history; resolve before download.")
    parts = []
    failed = []
    for i,row in enumerate(cities.itertuples(index=False),1):
        path = folder / f"city_{i:03d}.csv"
        try:
            if path.exists():
                monthly = pd.read_csv(path)
            else:
                payload = source.api_get(row.City_Center_Lat,row.City_Center_Lon)
                if not payload:
                    raise ValueError("No archive response")
                # Check all daily and hourly values; do not accept partial climate history.
                for field in source.DAILY_VARS:
                    if pd.Series(payload["daily"][field]).isna().any():
                        raise ValueError(f"Missing daily {field}")
                for field in source.HOURLY_VARS:
                    if pd.Series(payload["hourly"][field]).isna().any():
                        raise ValueError(f"Missing hourly {field}")
                monthly = source.to_monthly(payload)
                monthly["Country_dest"] = row.Country_dest
                monthly["City"] = row.City
                monthly["City_Center_Lat"] = row.City_Center_Lat
                monthly["City_Center_Lon"] = row.City_Center_Lon
            dates = pd.to_datetime(dict(year=monthly.Year,month=monthly.Month,day=1)).dt.to_period("M")
            if (list(dates)!=list(months) or not (monthly.n_days.to_numpy()==dates.dt.days_in_month.to_numpy()).all()
                or not (monthly.n_valid_days==monthly.n_days).all() or not np.isfinite(monthly[WEATHER]).all().all()):
                raise ValueError("Partial or invalid month")
            if not monthly.City.eq(row.City).all() or not monthly.Country_dest.eq(row.Country_dest).all():
                raise ValueError("Cached city mismatch")
            monthly.to_csv(path,index=False)
            parts.append(monthly)
            print(f"{i}/{len(cities)} {row.City}: {len(monthly)} complete months",flush=True)
        except Exception as exc:
            failed.append((row.Country_dest,row.City,str(exc)))
            print(f"Failed: {row.City}: {exc}",flush=True)
        time.sleep(8)
    if failed:
        raise SystemExit(f"Refresh incomplete; cached valid cities for rerun. Failures: {failed}")
    staged = pd.concat(parts,ignore_index=True).sort_values(KEY+["Year","Month"])
    assert len(staged)==len(cities)*len(months) and not staged.duplicated(KEY+["Year","Month"]).any()
    output = folder/"new_weather_observations.csv"
    staged.to_csv(output,index=False)
    print(f"Staged {len(staged)} rows in {output}")
    scored=score_tci(staged)
    scored=scored[history.columns]
    verify_original(scored)
    scored.to_csv(folder/"new_scored_observations.csv",index=False)
    # All known historical scores are reproduced, but unseen extreme regimes
    # are assumptions. Flag those rather than silently applying them.
    for t,r in [("Temp_Max_Mean","RH_Min_Mean"),("Temp_Mean","RH_Mean")]:
        effective=lambda df: df[t]-.4*(df[t]-10)*(1-df[r]/100)
        previous=effective(history)
        current=effective(scored)
        if ((current<previous.min()) | (current>previous.max())).any():
            print(f"WARNING: {t} effective temperature outside original observed range; review scored CSV.")
    if ((scored.Wind_Mean_ms<history.Wind_Mean_ms.min()) | (scored.Wind_Mean_ms>history.Wind_Mean_ms.max())).any():
        print("WARNING: wind outside original observed range; review scoring.")
    if args.apply:
        combined=pd.concat([history,scored],ignore_index=True).sort_values(KEY+["Year","Month"])
        if combined.duplicated(KEY+["Year","Month"]).any():
            raise ValueError("Duplicate month in combined history")
        verify_original(combined)
        backup=folder/"city_month_features_before_refresh.csv"
        shutil.copy2(HISTORY,backup)
        temp=HISTORY.with_suffix(".tmp")
        combined.to_csv(temp,index=False)
        temp.replace(HISTORY)
        print(f"Appended {len(scored)} rows, backup: {backup}")
        print("STOP: rerun forecasting notebook to regenerate matching artifacts before restarting/deploying.")
    else:
        print("Scored preview written. Inspect it; use --apply to append, then retrain.")


if __name__=="__main__":
    main()
