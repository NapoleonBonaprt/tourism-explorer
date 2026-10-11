
import os
import time
 
import pandas as pd
import requests
 
DESKTOP = os.path.join(os.path.expanduser("~"), "Desktop")
DEST_FILE = os.path.join(DESKTOP, "Global_Destinations.csv")
CACHE_DIR = os.path.join(DESKTOP, "weather_cache")
OUTPUT_FILE = os.path.join(DESKTOP, "Weather_Monthly.csv")
 
START_DATE = "2015-01-01"
END_DATE = "2025-12-31"
API_URL = "https://archive-api.open-meteo.com/v1/archive"
SLEEP_BETWEEN_CITIES = 8  
 
DAILY_VARS = [
    "temperature_2m_max",
    "temperature_2m_min",
    "temperature_2m_mean",
    "precipitation_sum",
    "sunshine_duration",      
]
HOURLY_VARS = [
    "relative_humidity_2m",   
    "wind_speed_10m",        
]
 
 
def load_cities():
    df = pd.read_csv(DEST_FILE)
    if {"City_Center_Lat", "City_Center_Lon"}.issubset(df.columns):
        lat_col, lon_col = "City_Center_Lat", "City_Center_Lon"
    else:  
        lat_col, lon_col = "Latitude", "Longitude"
    cities = (
        df.groupby(["City", "Country"], as_index=False)[[lat_col, lon_col]]
        .mean()
        .rename(columns={lat_col: "Lat", lon_col: "Lon"})
    )
    return cities
 
 
def api_get(lat, lon, retries=5):
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": START_DATE,
        "end_date": END_DATE,
        "daily": ",".join(DAILY_VARS),
        "hourly": ",".join(HOURLY_VARS),
        "wind_speed_unit": "ms",
        "timezone": "auto",
    }
    for attempt in range(retries):
        try:
            r = requests.get(API_URL, params=params, timeout=120)
            if r.status_code == 200:
                return r.json()
            print(f"   HTTP {r.status_code}: {r.text[:150]}")
            if r.status_code == 429:          
                time.sleep(60 * (attempt + 1))
                continue
        except requests.RequestException as e:
            print(f"   {type(e).__name__}: {e}")
        time.sleep(10 * (attempt + 1))
    return None
 
 
def to_monthly(payload):
    daily = pd.DataFrame(payload["daily"])
    daily["time"] = pd.to_datetime(daily["time"])
    daily = daily.set_index("time")
 
    hourly = pd.DataFrame(payload["hourly"])
    hourly["time"] = pd.to_datetime(hourly["time"])
    hourly["date"] = hourly["time"].dt.normalize()
    h = hourly.groupby("date").agg(
        rh_mean=("relative_humidity_2m", "mean"),
        rh_min=("relative_humidity_2m", "min"),
        wind_mean_ms=("wind_speed_10m", "mean"),
    )
 
    d = daily.join(h)
    d["sunshine_h"] = d["sunshine_duration"] / 3600.0
    d["Year"] = d.index.year
    d["Month"] = d.index.month
 
    monthly = d.groupby(["Year", "Month"]).agg(
        Temp_Max_Mean=("temperature_2m_max", "mean"),    
        Temp_Min_Mean=("temperature_2m_min", "mean"),
        Temp_Mean=("temperature_2m_mean", "mean"),
        RH_Mean=("rh_mean", "mean"),                    
        RH_Min_Mean=("rh_min", "mean"),                   #
        Precip_Total_mm=("precipitation_sum", lambda s: s.sum(min_count=1)),
        Sunshine_h_per_day=("sunshine_h", "mean"),
        Wind_Mean_ms=("wind_mean_ms", "mean"),
        n_valid_days=("temperature_2m_mean", "count"),
        n_days=("temperature_2m_mean", "size"),
    ).reset_index()
    return monthly.round(3)
 
 
def main():
    os.makedirs(CACHE_DIR, exist_ok=True)
    cities = load_cities()
    print(f"{len(cities)} cities, {START_DATE} -> {END_DATE}")
 
    failed = []
    for i, row in enumerate(cities.itertuples(index=False), start=1):
        safe = "".join(ch if ch.isalnum() else "_" for ch in row.City)
        cache_file = os.path.join(CACHE_DIR, f"{safe}.csv")
        if os.path.exists(cache_file):
            print(f"[{i}/{len(cities)}] {row.City}: cached, skipping")
            continue
 
        print(f"[{i}/{len(cities)}] {row.City}: downloading...")
        payload = api_get(row.Lat, row.Lon)
        if payload is None or "daily" not in payload or "hourly" not in payload:
            print(f"   FAILED -> {row.City} (will be listed at the end)")
            failed.append(row.City)
            continue
 
        monthly = to_monthly(payload)
        monthly.insert(0, "Country", row.Country)
        monthly.insert(0, "City", row.City)
        monthly["Lat"] = row.Lat
        monthly["Lon"] = row.Lon
        monthly["Data_Source"] = "open-meteo-era5"
        monthly.to_csv(cache_file, index=False)
        time.sleep(SLEEP_BETWEEN_CITIES)
 
    files = [os.path.join(CACHE_DIR, f) for f in os.listdir(CACHE_DIR)
             if f.endswith(".csv")]
    if not files:
        print("Nothing downloaded.")
        return
    out = pd.concat((pd.read_csv(f) for f in files), ignore_index=True)
    out = out.sort_values(["City", "Year", "Month"])
    out.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
 
    print("\n" + "=" * 60)
    print(f"Saved {len(out):,} rows ({out['City'].nunique()} cities) -> {OUTPUT_FILE}")
    print("Missing values per column:")
    print(out.isna().sum()[lambda s: s > 0].to_string() or "  none")
    if failed:
        print("\nFailed cities (just re-run the script, it resumes):")
        for c in failed:
            print("  ", c)
    print("=" * 60)
 
 
if __name__ == "__main__":
    main()