"""Website API endpoints that reuse the Streamlit dashboard's datasets and itinerary engine.

The original Streamlit application remains unchanged. The API serves only the
selected/aggregated data needed by the HTML pages, not the full CSV exports.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
import logging
from functools import lru_cache
from pathlib import Path
from typing import Literal

import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.itinerary_engine2 import (
    add_day_type, build_itinerary, get_daily_weather,
    prepare_city, replan,
)

from backend.forecast_service import forecast_info, predict_tci, recommend, tci_label, catalog
from backend.weather_forecast import predict_weather

router = APIRouter(prefix="/website", tags=["Website dashboard"])
ROOT = Path(__file__).resolve().parents[1]
MONTHS = ["January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]


def data_path(name: str) -> Path:
    candidates = [
        ROOT / name, ROOT / "cleaned_data" / name,
        ROOT / "python files" / "processed_data" / name,
    ]
    for path in candidates:
        if path.is_file():
            return path
    raise HTTPException(status_code=503, detail=f"Required dataset unavailable: {name}")


@lru_cache(maxsize=9)
def frame(name: str) -> pd.DataFrame:
    try:
        path = data_path(name)
        # Only load the columns the website uses from the large analysis CSVs.
        # This reduces RAM pressure on Render's 512 MB free instance.
        if name == "tourism_final_clean.csv":
            return pd.read_csv(path, usecols=lambda col: col in {
                "TCI", "TCI_Category"
            }, low_memory=False)
        if name == "full.csv":
            return pd.read_csv(path, usecols=lambda col: col in {
                "Country", "Country_dest", "country", "Month", "month",
                "Destination Name", "Destination", "destination", "Place", "Name",
                "TCI", "tci", "City", "city", "Governorate", "Province",
                "Region", "governorate"
            }, low_memory=False)
        return pd.read_csv(path, low_memory=False)
    except HTTPException:
        raise
    except (OSError, ValueError, pd.errors.ParserError) as exc:
        raise HTTPException(status_code=503, detail=f"Could not read dataset: {name}") from exc


def records(data: pd.DataFrame) -> list[dict]:
    """Pandas' JSON serializer turns numpy scalars and NaN into valid JSON."""
    return json.loads(data.to_json(orient="records", date_format="iso"))


def select_col(df: pd.DataFrame, candidates: list[str]) -> str:
    for column in candidates:
        if column in df.columns:
            return column
    raise HTTPException(
        status_code=503, detail="The selected dataset is missing expected columns."
    )


def eq(series: pd.Series, value: str) -> pd.Series:
    return series.astype("string").str.strip().str.casefold().eq(value.strip().casefold()).fillna(False)


def country_cities(df: pd.DataFrame) -> list[dict]:
    if not {"Country_dest", "City"}.issubset(df.columns):
        return []
    data = df[["Country_dest", "City"]].dropna().drop_duplicates()
    data = data.sort_values(["Country_dest", "City"])
    return [{"country": country, "city": city} for country, city
            in data.itertuples(index=False, name=None)]


@router.get("/filters")
def filters() -> dict:
    """All filter options come from the same sources as the Streamlit pages."""
    climate = frame("city_month_features.csv")
    places = frame("places_with_clusters.csv")
    attractions = frame("attractions_with_clusters.csv") if (ROOT / "python files" / "processed_data" / "attractions_with_clusters.csv").exists() else places
    full = frame("full.csv")
    country_col = select_col(full, ["Country", "Country_dest", "country"])
    # The browser can fetch Open-Meteo directly, avoiding hosting providers'
    # shared outbound IP limits. Use the same city centroids as the planner.
    centers = places[["City", "Latitude", "Longitude"]].copy()
    centers["Latitude"] = pd.to_numeric(centers["Latitude"], errors="coerce")
    centers["Longitude"] = pd.to_numeric(centers["Longitude"], errors="coerce")
    centers = centers.dropna(subset=["City", "Latitude", "Longitude"])
    centers = centers.groupby("City")[["Latitude", "Longitude"]].mean()
    return {
        "climate_cities": country_cities(climate),
        "planner_cities": country_cities(attractions),
        "adaptive_cities": sorted(places["City"].dropna().astype(str).unique().tolist()),
        "adaptive_coordinates": {
            str(city): {"latitude": float(row["Latitude"]), "longitude": float(row["Longitude"])}
            for city, row in centers.iterrows()
        },
        "map_countries": sorted(full[country_col].dropna().astype(str).str.strip().unique().tolist()),
        "months": MONTHS,
    }


@lru_cache(maxsize=1)
def _destination_city_coordinates() -> dict[str, dict[str, float]]:
    """Load only city centroids, not the full dashboard filter datasets."""
    places = pd.read_csv(
        data_path("places_with_clusters.csv"),
        usecols=["City", "Latitude", "Longitude"],
        low_memory=False,
    )
    for column in ("Latitude", "Longitude"):
        places[column] = pd.to_numeric(places[column], errors="coerce")
    places = places.dropna(subset=["City", "Latitude", "Longitude"])
    places = places[
        places["Latitude"].between(-90, 90)
        & places["Longitude"].between(-180, 180)
    ]
    centers = places.groupby("City", sort=True)[["Latitude", "Longitude"]].mean()
    return {
        str(city): {
            "latitude": float(row["Latitude"]),
            "longitude": float(row["Longitude"]),
        }
        for city, row in centers.iterrows()
    }


@router.get("/destination-coordinates")
def destination_coordinates() -> dict:
    """Aggregated city positions for the public map, not raw attraction data."""
    return {"coordinates": _destination_city_coordinates()}


@router.get("/overview")
def overview() -> dict:
    tourism = frame("tourism_final_clean.csv")
    places = frame("attractions_with_clusters.csv") if (ROOT / "python files" / "processed_data" / "attractions_with_clusters.csv").exists() else frame("places_with_clusters.csv")
    climate = frame("city_month_features.csv")
    countries = frame("country_cluster_summary.csv")
    counts = tourism["TCI_Category"].fillna("Unclassified").astype(str).value_counts()
    return {
        "metrics": {
            "destinations": int(places["Destination Name"].nunique()),
            "cities": int(climate["City"].nunique()),
            "countries": int(places["Country_dest"].nunique()),
            "average_tci": round(float(pd.to_numeric(tourism["TCI"], errors="coerce").mean()), 1),
        },
        "categories": [{"category": str(k), "count": int(v)} for k, v in counts.items()],
        "country_summary": records(countries.head(10)),
        "mission": {
            "description": "Climate plays a pivotal role in global tourism satisfaction, safety, and operational sustainability. This platform leverages multi-year meteorological metrics, spatial clustering (DBSCAN), and the Tourism Climatic Index (TCI) to evaluate destinations worldwide.",
            "objectives": [
                "Climate Suitability Assessment: Evaluate thermal comfort, precipitation, sunshine hours, and wind speeds.",
                "Spatial Attraction Clustering: Discover dense tourism clusters and outlier hotspots.",
                "Smart Recommendations: Plan trips optimized for ideal weather windows.",
            ],
        },
    }


@router.get("/climate")
def climate(country: str = Query(..., min_length=1),
            city: str = Query(..., min_length=1)) -> dict:
    df = frame("city_month_features.csv")
    subset = df.loc[eq(df["Country_dest"], country) & eq(df["City"], city)].copy()
    if subset.empty:
        raise HTTPException(status_code=404, detail="No climate data for this city and country.")
    subset["Month"] = pd.to_numeric(subset["Month"], errors="coerce")
    subset = subset.sort_values(["Year", "Month"])
    columns = ["Year", "Month", "Temp_Max_Mean", "Temp_Min_Mean", "Temp_Mean",
               "RH_Mean", "Precip_Total_mm", "Sunshine_h_per_day",
               "Wind_Mean_ms", "TCI", "TCI_Category"]
    columns = [col for col in columns if col in subset.columns]
    history = records(subset[columns])
    numeric = [name for name in columns if name not in {"Year", "Month", "TCI_Category"}]
    monthly = subset.groupby("Month", as_index=False)[numeric].mean(numeric_only=True)
    def label(score: float) -> str:
        # Match the TCI_Category definitions in the cleaned climate CSV.
        if score >= 90: return "Ideal"
        if score >= 80: return "Excellent"
        if score >= 70: return "Very Good"
        if score >= 60: return "Good"
        if score >= 50: return "Acceptable"
        if score >= 40: return "Marginal"
        if score >= 30: return "Unfavorable"
        if score >= 20: return "Very Unfavorable"
        return "Extremely Unfavorable"
    monthly["TCI_Category"] = monthly["TCI"].map(label)
    return {"country": country, "city": city, "history": history,
            "monthly": records(monthly), "months": MONTHS,
            "years": sorted(int(x) for x in subset["Year"].dropna().unique())}


@router.get("/forecast-info")
def forecast_dates():
    return forecast_info()


@router.get("/forecast")
def monthly_forecast(country: str, city: str, travel_date: date):
    scores, reliability = predict_tci(country, travel_date, city)
    return {"predictions": records(scores), "forecast": reliability, "monthly_weather": predict_weather(country, city, travel_date)}


@router.get("/explorer")
def explorer(country: str = Query(..., min_length=1),
             month: int = Query(8, ge=1, le=12),
             location: str = Query("", max_length=120), travel_date: date | None = None) -> dict:
    """Date-based model predictions, or legacy historical month mode."""
    if travel_date is not None:
        selected, reliability = recommend(country, travel_date, location or None)
        top = selected.head(5)
        keys = set(zip(top.City, top["Destination Name"]))
        top5 = [{"destination": str(r["Destination Name"]), "city": str(r.City),
                 "country": str(r.Country_dest), "month": travel_date.month,
                 "tci": round(float(r.predicted_tci), 2)} for _, r in top.iterrows()]
        points = [{"name": str(r["Destination Name"]), "city": str(r.City),
                   "lat": float(r.Latitude), "lon": float(r.Longitude),
                   "cluster": int(r.spatial_cluster), "type": str(r.Type),
                   "category": str(r.Category), "tci": round(float(r.predicted_tci),2),
                   "within_10_pct": reliability["within_10_pct"],
                   "is_top": (r.City,r["Destination Name"]) in keys}
                  for _, r in selected.iterrows()]
        return {"country": country, "month": travel_date.month, "month_name": travel_date.strftime("%B %Y"),
                "location": location, "warning": reliability["warning"], "forecast": reliability,
                "top5": top5, "points": points,
                "counts": {"recommendations":len(top5), "on_map":sum(p["is_top"] for p in points),
                           "clustered":sum(p["cluster"] != -1 for p in points),
                           "noise":sum(p["cluster"] == -1 for p in points), "unknown":0}}

    full = frame("full.csv")
    places = frame("places_with_clusters.csv")
    country_col = select_col(full, ["Country", "Country_dest", "country"])
    month_col = select_col(full, ["Month", "month"])
    name_col = select_col(full, ["Destination Name", "destination", "Destination", "Place", "Name"])
    tci_col = select_col(full, ["TCI", "tci"])
    selection = full.loc[
        eq(full[country_col], country) &
        pd.to_numeric(full[month_col], errors="coerce").eq(month)
    ].copy()
    warning = None
    if location.strip():
        candidates = [c for c in ["City", "Governorate", "Province", "Region",
                                  "city", "governorate"] if c in selection.columns]
        if candidates:
            mask = pd.Series(False, index=selection.index)
            for col in candidates:
                mask |= eq(selection[col], location)
            selection = selection.loc[mask]
        else:
            warning = "The recommendations data has no city/governorate column; showing all country results."
    selection[tci_col] = pd.to_numeric(selection[tci_col], errors="coerce")
    selection = selection.dropna(subset=[tci_col])
    top = selection.sort_values(tci_col, ascending=False).drop_duplicates(subset=[name_col]).head(5)
    city_col = next((c for c in ["City", "city"] if c in top.columns), None)
    top5 = [
        {"destination": str(r[name_col]),
         "city": str(r[city_col]) if city_col and pd.notna(r[city_col]) else "",
         "country": str(r[country_col]), "month": int(r[month_col]),
         "tci": round(float(r[tci_col]), 2)}
        for _, r in top.iterrows()
    ]
    points = places.loc[eq(places["Country_dest"], country)].copy()
    points["Latitude"] = pd.to_numeric(points["Latitude"], errors="coerce")
    points["Longitude"] = pd.to_numeric(points["Longitude"], errors="coerce")
    points = points.dropna(subset=["Latitude", "Longitude"])
    points = points.loc[points["Latitude"].between(-90, 90) & points["Longitude"].between(-180, 180)]
    top_names = {str(x["destination"]).strip().casefold() for x in top5}
    map_points = [
        {"name": str(r["Destination Name"]),
         "city": str(r["City"]), "lat": float(r["Latitude"]),
         "lon": float(r["Longitude"]),
         "cluster": int(r["spatial_cluster"]) if pd.notna(r["spatial_cluster"]) else None,
         "type": str(r["Type"]), "category": str(r["Category"]),
         "tci": float(r["TCI"]) if pd.notna(r["TCI"]) else None,
         "is_top": str(r["Destination Name"]).strip().casefold() in top_names}
        for _, r in points.iterrows()
    ]
    return {"country": country, "month": month, "month_name": MONTHS[month - 1],
            "location": location, "warning": warning, "top5": top5,
            "points": map_points,
            "counts": {
                "recommendations": len(top5),
                "on_map": sum(p["is_top"] for p in map_points),
                "clustered": sum(p["cluster"] is not None and p["cluster"] != -1 for p in map_points),
                "noise": sum(p["cluster"] == -1 for p in map_points),
                "unknown": sum(p["cluster"] is None for p in map_points),
            }}


@router.get("/planner")
def planner(country: str = Query(..., min_length=1),
            city: str = Query(..., min_length=1),
            month: int = Query(1, ge=1, le=12),
            category: Literal["All", "Outdoor", "Indoor"] = "All", travel_date: date | None = None) -> dict:
    if travel_date is not None:
        scores, reliability = predict_tci(country, travel_date, city)
        selected, _ = recommend(country, travel_date, city, category)
        score = float(scores.iloc[0].predicted_tci)
        weather = {"TCI":round(score,2), "TCI_Category":tci_label(score),
                   "source":"Monthly TCI from Residual XGBoost; separate monthly weather models are shown below.",
                   "historical_mean_tci":round(float(scores.iloc[0].historical_mean_tci),2)}
        attractions_list = [{"name":str(r["Destination Name"]), "type":str(r.Type),
                             "category":str(r.Category), "latitude":float(r.Latitude),
                             "longitude":float(r.Longitude), "tci":round(float(r.predicted_tci),2),
                             "tci_category":tci_label(float(r.predicted_tci))}
                            for _, r in selected.head(10).iterrows()]
        return {"country":country,"city":city,"month":travel_date.month,
                "month_name":travel_date.strftime("%B %Y"),"category":category,
                "weather":weather,"forecast":reliability,"monthly_weather":predict_weather(country,city,travel_date),"attractions":attractions_list,
                "total_matching":len(selected),
                "tip":"City-level monthly suitability; attraction popularity breaks ties. Check short-range weather before travel."}
    attractions = frame("attractions_with_clusters.csv") if (ROOT / "python files" / "processed_data" / "attractions_with_clusters.csv").exists() else frame("places_with_clusters.csv")
    climate = frame("city_month_features.csv")
    filtered = attractions.loc[eq(attractions["Country_dest"], country) & eq(attractions["City"], city)].copy()
    if category != "All":
        filtered = filtered.loc[eq(filtered["Category"], category)]
    chosen = filtered.head(10)
    climate_rows = climate.loc[
        eq(climate["Country_dest"], country) & eq(climate["City"], city) &
        pd.to_numeric(climate["Month"], errors="coerce").eq(month)
    ]
    weather = None
    if not climate_rows.empty:
        fields = ["Temp_Mean", "TCI", "Sunshine_h_per_day", "Precip_Total_mm",
                  "RH_Mean", "Temp_Max_Mean", "Temp_Min_Mean"]
        weather = {field: round(float(pd.to_numeric(climate_rows[field], errors="coerce").mean()), 2)
                   for field in fields if field in climate_rows.columns}
        weather["TCI_Category"] = str(climate_rows["TCI_Category"].mode().iloc[0]) if not climate_rows["TCI_Category"].mode().empty else "N/A"
        weather["source"] = "Historical monthly mean, not a live weather forecast"
    attractions_list = [
        {"name": str(r["Destination Name"]), "type": str(r["Type"]),
         "category": str(r["Category"]),
         "latitude": float(r["Latitude"]), "longitude": float(r["Longitude"]),
         "tci": float(r["TCI"]) if pd.notna(r["TCI"]) else None,
         "tci_category": str(r["TCI_Category"])}
        for _, r in chosen.iterrows()
    ]
    return {"country": country, "city": city, "month": month,
            "month_name": MONTHS[month-1], "category": category,
            "weather": weather, "attractions": attractions_list,
            "total_matching": int(len(filtered)),
            "tip": "Ideal spot for photography and cultural exploration during your selected travel month!"}


class BrowserForecast(BaseModel):
    """Daily Open-Meteo observations sent by the visitor's browser."""
    time: list[str] = Field(min_length=1, max_length=7)
    temperature_2m_max: list[float] = Field(min_length=1, max_length=7)
    precipitation_sum: list[float] = Field(min_length=1, max_length=7)
    wind_speed_10m_max: list[float] = Field(min_length=1, max_length=7)


class BuildRequest(BaseModel):
    city: str = Field(min_length=1, max_length=100)
    days: int = Field(default=5, ge=1, le=7)
    stops: int = Field(default=3, ge=2, le=5)
    forecast: BrowserForecast | None = None
    start_date: date = Field(default_factory=date.today)


class SavedStop(BaseModel):
    raw_name: str
    category: str
    slot: str
    lat: float
    lon: float
    cluster: int | None = None


class SavedDay(BaseModel):
    date: str
    day_type: Literal["indoor", "mixed", "outdoor"]
    stops: list[SavedStop]


class RecheckRequest(BuildRequest):
    previous: list[SavedDay] = Field(min_length=1, max_length=7)
    simulate_storm: bool = False
    storm_date: str | None = None
    rain_mm: float = Field(default=8, ge=0, le=50)


def weather_for(city: str, days: int, supplied_forecast: BrowserForecast | None = None, start_date: date | None = None):
    start_date = start_date or date.today()
    expected = [start_date + timedelta(days=i) for i in range(days)]
    if start_date < date.today() or expected[-1] > date.today() + timedelta(days=6):
        raise HTTPException(422, "Live daily forecast is limited to the next seven days.")
    places = frame("places_with_clusters.csv")
    names = places["City"].dropna().astype(str).unique()
    canonical = next((x for x in names if x.casefold() == city.strip().casefold()), None)
    if not canonical:
        raise HTTPException(status_code=404, detail="This city has no attractions for daily planning.")
    within = places.loc[eq(places["City"], canonical)].copy()
    lat = pd.to_numeric(within["Latitude"], errors="coerce").mean()
    lon = pd.to_numeric(within["Longitude"], errors="coerce").mean()
    if pd.isna(lat) or pd.isna(lon):
        raise HTTPException(status_code=503, detail="City coordinates are unavailable.")
    if supplied_forecast is not None:
        # Open-Meteo supports CORS. Browser-side fetching avoids shared proxy IPs
        # that can be rate-limited on free hosting. Never use client coordinates.
        forecast = supplied_forecast.model_dump()
        if any(len(values) != days for values in forecast.values()):
            raise HTTPException(status_code=422, detail="Forecast must contain exactly the requested number of days.")
        try:
            parsed = [date.fromisoformat(value) for value in forecast["time"]]
            if parsed != expected:
                raise ValueError("Forecast dates must exactly match the requested trip")
            data = pd.DataFrame(forecast)
            numeric = data[["temperature_2m_max","precipitation_sum","wind_speed_10m_max"]]
            if not numeric.apply(lambda col: col.map(lambda v: pd.notna(v) and abs(v) != float("inf"))).all().all() or (numeric[["precipitation_sum","wind_speed_10m_max"]] < 0).any().any():
                raise ValueError("Invalid daily forecast values")
            data = add_day_type(data)
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=422, detail="Invalid daily forecast supplied.") from exc
    else:
        try:
            forecast = get_daily_weather(float(lat), float(lon), 7)
            wx = pd.DataFrame(forecast)
            data = add_day_type(wx[wx.time.isin([d.isoformat() for d in expected])].copy())
            if len(data) != days:
                raise ValueError("Incomplete forecast")
        except Exception as exc:
            logging.getLogger(__name__).exception(
                "Open-Meteo forecast failure for city=%r, days=%d, coordinates=(%.4f, %.4f)",
                canonical, days, float(lat), float(lon),
            )
            raise HTTPException(status_code=503, detail="Live forecast unavailable from Open-Meteo. Try again later.") from exc
    return places, canonical, data


def serialise_plan(plan, weather, city, n_stops, places, changes=None, monthly=None):
    wx = {str(r["time"]): r for _, r in weather.iterrows()}
    output = []
    for i, (date, (kind, items)) in enumerate(plan.items(), start=1):
        day_stops = []
        for j, (_, r) in enumerate(items.iterrows(), start=1):
            raw = str(r["Destination Name"])
            cluster = r.get("spatial_cluster")
            day_stops.append({
                "order": j, "raw_name": raw,
                "name": raw.rsplit(" (", 1)[0],
                "category": str(r["Category"]), "slot": str(r["slot"]),
                "lat": float(r["Latitude"]), "lon": float(r["Longitude"]),
                "cluster": int(cluster) if pd.notna(cluster) else None,
            })
        w = wx[str(date)]
        output.append({
            "number": i, "date": str(date), "day_type": kind,
            "weather": ({key: None for key in ["temperature_2m_max","precipitation_sum","wind_speed_10m_max"]} if monthly is not None else {
                "temperature_2m_max": round(float(w["temperature_2m_max"]), 1),
                "precipitation_sum": round(float(w["precipitation_sum"]), 1),
                "wind_speed_10m_max": round(float(w["wind_speed_10m_max"]), 1),
            }), "monthly_forecast": monthly.get(str(date)[:7]) if monthly is not None else None, "stops": day_stops,
        })
    available = len(prepare_city(places, city))
    warning = f"{city} has only {available} distinct attractions; some days have fewer stops." if len(weather) * n_stops > available else ""
    if monthly is not None:
        warning = ("Provisional monthly TCI-based itinerary. Monthly temperature, rainfall, wind, humidity and sunshine are estimated separately; daily values are unavailable. "
                   "Day types are planning preferences; re-check daily weather closer to travel. " + warning).strip()
    return {"city": city, "days": output, "available": available,
            "requested_stops": n_stops, "mode": "monthly" if monthly is not None else "daily",
            "warning": warning or None, "changes": changes,
            "monthly_forecasts": list(monthly.values()) if monthly is not None else []}


@router.post("/adaptive/build")
def adaptive_build(request: BuildRequest):
    end = request.start_date + timedelta(days=request.days-1)
    if request.start_date < date.today():
        raise HTTPException(422, "Choose today or a future date.")
    if end > date.today() + timedelta(days=6):
        if request.forecast is not None:
            raise HTTPException(422, "Daily forecasts cannot be used for a long-range trip.")
        places = catalog()
        matching = places.loc[eq(places.City, request.city)]
        cities = matching[["Country_dest","City"]].drop_duplicates()
        if len(cities) != 1:
            raise HTTPException(404, "City is missing or ambiguous in the attraction catalog.")
        country, city = cities.iloc[0].tolist()
        monthly, rows = {}, []
        for i in range(request.days):
            day = request.start_date + timedelta(days=i)
            month = day.strftime("%Y-%m")
            if month not in monthly:
                scores, reliability = predict_tci(country, day, city)
                score = float(scores.iloc[0].predicted_tci)
                monthly[month] = {**reliability,"predicted_tci":round(score,2),"tci_category":tci_label(score),
                                  "monthly_weather":predict_weather(country,city,day)}
            score = monthly[month]["predicted_tci"]
            # Planning preference, not a classification of a specific day's weather.
            kind = "indoor" if score < 50 else "mixed"
            rows.append({"time":day.isoformat(),"day_type":kind})
        weather = pd.DataFrame(rows)
        plan = build_itinerary(places, city, weather, request.stops)
        return serialise_plan(plan, weather, city, request.stops, places, monthly=monthly)
    places, city, weather = weather_for(request.city, request.days, request.forecast, request.start_date)
    try:
        plan = build_itinerary(places, city, weather, request.stops)
        return serialise_plan(plan, weather, city, request.stops, places)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Could not build an itinerary for this city.") from exc


@router.post("/adaptive/recheck")
def adaptive_recheck(request: RecheckRequest):
    expected = [(request.start_date + timedelta(days=i)).isoformat() for i in range(request.days)]
    if [d.date for d in request.previous] != expected:
        raise HTTPException(422, "Previous itinerary dates do not match the requested trip.")
    places, city, weather = weather_for(request.city, request.days, request.forecast, request.start_date)
    if request.simulate_storm:
        if request.storm_date not in set(weather["time"].astype(str)):
            raise HTTPException(status_code=422, detail="Select a day within the current forecast.")
        weather.loc[weather["time"].eq(request.storm_date), "precipitation_sum"] = request.rain_mm
        weather = add_day_type(weather)
    old_plan = {}
    for day in request.previous:
        stops = pd.DataFrame([
            {"Destination Name": s.raw_name, "Category": s.category,
             "slot": s.slot, "Latitude": s.lat, "Longitude": s.lon,
             "spatial_cluster": s.cluster}
            for s in day.stops
        ], columns=["Destination Name", "Category", "slot",
                    "Latitude", "Longitude", "spatial_cluster"])
        old_plan[day.date] = (day.day_type, stops)
    try:
        plan, changes = replan(old_plan, places, city, weather, request.stops)
        return serialise_plan(plan, weather, city, request.stops, places, changes)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Could not re-plan the itinerary.") from exc


class ExportStop(BaseModel):
    order: int = Field(ge=1, le=100)
    name: str = Field(min_length=1, max_length=250)
    category: str = Field(default="", max_length=100)
    slot: str = Field(default="", max_length=100)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class ExportWeather(BaseModel):
    temperature_2m_max: float | None = None
    precipitation_sum: float | None = None
    wind_speed_10m_max: float | None = None


class ExportDay(BaseModel):
    number: int = Field(ge=1, le=7)
    date: str = Field(min_length=4, max_length=32)
    day_type: str = Field(min_length=1, max_length=32)
    weather: ExportWeather
    stops: list[ExportStop] = Field(max_length=5)


class ExportMonthlyVariable(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    unit: str = Field(max_length=24)
    prediction: float = Field(allow_inf_nan=False)
    mae: float = Field(ge=0, allow_inf_nan=False)
    tolerance: float = Field(gt=0, allow_inf_nan=False)
    within_tolerance_pct: float = Field(ge=0, le=100)


class ExportMonthlyWeather(BaseModel):
    variables: list[ExportMonthlyVariable] = Field(min_length=1, max_length=5)


class ExportMonthlyForecast(BaseModel):
    target_month: str = Field(pattern=r"^\d{4}-\d{2}$")
    predicted_tci: float = Field(ge=0, le=100)
    tci_category: str = Field(max_length=80)
    within_10_pct: float = Field(ge=0, le=100)
    mae: float = Field(ge=0, allow_inf_nan=False)
    monthly_weather: ExportMonthlyWeather


class ExportRequest(BaseModel):
    city: str = Field(min_length=1, max_length=100)
    days: list[ExportDay] = Field(min_length=1, max_length=7)
    warning: str | None = Field(default=None, max_length=600)
    changes: list[dict] | None = None
    monthly_forecasts: list[ExportMonthlyForecast] = Field(default_factory=list, max_length=2)


@router.get("/guide-cover")
def guide_cover(city: str = Query(..., min_length=1, max_length=100)):
    """Small same-origin cover JPEG; never fetch arbitrary external URLs."""
    from fastapi.responses import Response
    from backend.guide_cover import city_cover, RequiredPhotoUnavailable
    canonical = next((name for name in _destination_city_coordinates()
                      if name.casefold() == city.strip().casefold()), None)
    if canonical is None:
        raise HTTPException(404, "Unknown destination.")
    try:
        data, kind = city_cover(canonical)
    except RequiredPhotoUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    return Response(data, media_type="image/jpeg",
                    headers={"Cache-Control": "public, max-age=86400", "X-Guide-Cover": kind,
                             "Access-Control-Expose-Headers": "X-Guide-Cover"})


@router.post("/adaptive/export-pdf")
def export_adaptive_pdf(request: ExportRequest):
    """A short, readable travel guide from the current itinerary."""
    import re
    from fastapi.responses import Response
    from backend.trip_guide import make_guide
    from backend.guide_cover import RequiredPhotoUnavailable
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", request.city).strip("-")[:65] or "Trip"
    try:
        guide = make_guide(request.model_dump())
    except RequiredPhotoUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    return Response(guide, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="WanderClimate-{slug}-Travel-Guide.pdf"'})
