"""Website API endpoints that reuse the Streamlit dashboard's datasets and itinerary engine.

The original Streamlit application remains unchanged. The API serves only the
selected/aggregated data needed by the HTML pages, not the full CSV exports.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from itinerary_engine2 import (
    add_day_type, build_itinerary, get_daily_weather,
    prepare_city, replan,
)

router = APIRouter(prefix="/website", tags=["Website dashboard"])
ROOT = Path(__file__).resolve().parent
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
        return pd.read_csv(data_path(name), low_memory=False)
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
    return {
        "climate_cities": country_cities(climate),
        "planner_cities": country_cities(attractions),
        "adaptive_cities": sorted(places["City"].dropna().astype(str).unique().tolist()),
        "map_countries": sorted(full[country_col].dropna().astype(str).str.strip().unique().tolist()),
        "months": MONTHS,
    }


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


@router.get("/explorer")
def explorer(country: str = Query(..., min_length=1),
             month: int = Query(8, ge=1, le=12),
             location: str = Query("", max_length=120)) -> dict:
    """Same Top 5 ranking and country-wide DBSCAN map as dashboard.py."""
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
            category: Literal["All", "Outdoor", "Indoor"] = "All") -> dict:
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


class BuildRequest(BaseModel):
    city: str = Field(min_length=1, max_length=100)
    days: int = Field(default=5, ge=1, le=7)
    stops: int = Field(default=3, ge=2, le=5)


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


def weather_for(city: str, days: int):
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
    try:
        forecast = get_daily_weather(float(lat), float(lon), days)
        data = add_day_type(pd.DataFrame(forecast))
        if len(data) != days:
            raise ValueError("Incomplete forecast")
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Live forecast unavailable from Open-Meteo. Try again later.") from exc
    return places, canonical, data


def serialise_plan(plan, weather, city, n_stops, places, changes=None):
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
            "weather": {
                "temperature_2m_max": round(float(w["temperature_2m_max"]), 1),
                "precipitation_sum": round(float(w["precipitation_sum"]), 1),
                "wind_speed_10m_max": round(float(w["wind_speed_10m_max"]), 1),
            }, "stops": day_stops,
        })
    available = len(prepare_city(places, city))
    return {"city": city, "days": output, "available": available,
            "requested_stops": n_stops,
            "warning": f"{city} has only {available} distinct attractions; some days have fewer stops." if len(weather) * n_stops > available else None,
            "changes": changes}


@router.post("/adaptive/build")
def adaptive_build(request: BuildRequest):
    places, city, weather = weather_for(request.city, request.days)
    try:
        plan = build_itinerary(places, city, weather, request.stops)
        return serialise_plan(plan, weather, city, request.stops, places)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Could not build an itinerary for this city.") from exc


@router.post("/adaptive/recheck")
def adaptive_recheck(request: RecheckRequest):
    places, city, weather = weather_for(request.city, request.days)
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
    stops: list[ExportStop] = Field(max_length=100)


class ExportRequest(BaseModel):
    city: str = Field(min_length=1, max_length=100)
    days: list[ExportDay] = Field(min_length=1, max_length=7)
    warning: str | None = Field(default=None, max_length=600)
    changes: list[dict] | None = None


@router.post("/adaptive/export-pdf")
def export_adaptive_pdf(request: ExportRequest):
    """A print-ready PDF made from the itinerary currently shown to the user."""
    import io
    from datetime import datetime, timezone

    from fastapi.responses import Response
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
    from xml.sax.saxutils import escape as xml_escape

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=(595.28, 841.89),
                            rightMargin=45, leftMargin=45, topMargin=52, bottomMargin=50)
    palette = {
        "ink": colors.HexColor("#24352B"),
        "green": colors.HexColor("#3F6B4A"),
        "muted": colors.HexColor("#617268"),
        "line": colors.HexColor("#DDE7DE"),
        "paper": colors.HexColor("#F2F6F1")
    }
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="WCBrand", parent=styles["Normal"], fontSize=12,
                              leading=17, textColor=palette["green"], spaceAfter=12))
    styles.add(ParagraphStyle(name="WCTitle", parent=styles["Heading1"], fontSize=25,
                              leading=31, textColor=palette["ink"], spaceAfter=6))
    styles.add(ParagraphStyle(name="WCDay", parent=styles["Heading2"], fontSize=15,
                              leading=21, textColor=palette["green"], spaceBefore=16, spaceAfter=8))
    styles.add(ParagraphStyle(name="WCBody", parent=styles["Normal"], fontSize=10.5,
                              leading=16, textColor=palette["ink"], spaceAfter=7,
                              alignment=TA_LEFT, wordWrap="CJK"))
    styles.add(ParagraphStyle(name="WCNote", parent=styles["Normal"], fontSize=9,
                              leading=14, textColor=palette["muted"], spaceAfter=8))
    story = [
        Paragraph("WANDERCLIMATE", styles["WCBrand"]),
        Paragraph(f"Your trip to {xml_escape(request.city)}", styles["WCTitle"]),
        Paragraph(f"{len(request.days)} day(s) - forecast-informed itinerary", styles["WCNote"]),
        Paragraph("Saved on " + datetime.now(timezone.utc).strftime("%d %B %Y %H:%M UTC"), styles["WCNote"]),
        Spacer(1, 10),
    ]
    if request.warning:
        story.append(Paragraph(xml_escape(request.warning), styles["WCNote"]))
    for day in request.days:
        wx = day.weather
        def temp(v, unit):
            return f"{v:.1f} {unit}" if v is not None else "N/A"
        cells = [
            ["Temperature", temp(wx.temperature_2m_max, "C")],
            ["Rainfall", temp(wx.precipitation_sum, "mm")],
            ["Wind", temp(wx.wind_speed_10m_max, "km/h")],
        ]
        table = Table(cells, colWidths=[100, 125], hAlign="LEFT")
        table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), palette["paper"]),
            ("TEXTCOLOR", (0,0), (-1,-1), palette["ink"]),
            ("FONTSIZE", (0,0), (-1,-1), 9),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
            ("TOPPADDING", (0,0), (-1,-1), 6),
            ("LINEBELOW", (0,-1), (-1,-1), 0.5, palette["line"])
        ]))
        block = [
            Paragraph(f"Day {day.number} | {xml_escape(day.date)} | {xml_escape(day.day_type.title())}", styles["WCDay"]),
            table, Spacer(1, 8)
        ]
        if not day.stops:
            block.append(Paragraph("No attractions were available for this day.", styles["WCBody"]))
        for stop in day.stops:
            name = xml_escape(stop.name)
            category = xml_escape(stop.category)
            slot = xml_escape(stop.slot)
            block.append(Paragraph(f"<b>{stop.order}. {name}</b> | {category} | {slot}", styles["WCBody"]))
            block.append(Paragraph(f"Coordinates: {stop.lat:.5f}, {stop.lon:.5f}", styles["WCNote"]))
        story.append(KeepTogether(block[:2]))
        story.extend(block[2:])
    if request.changes:
        story.append(Paragraph("Weather re-check changes", styles["WCDay"]))
        for change in request.changes[:7]:
            label = f"{change.get('date','')} | {change.get('from','')} to {change.get('to','')}: {change.get('reason','')}"
            story.append(Paragraph(xml_escape(label), styles["WCNote"]))
    story.append(Spacer(1, 10))
    story.append(Paragraph("ROUTE NOTE: Connecting lines on the map are straight-line visual guides between attractions, not driving, walking, or turn-by-turn directions.", styles["WCNote"]))
    story.append(Paragraph("Forecasts can change. Verify local weather, access and opening hours before travel.", styles["WCNote"]))

    def page_footer(canvas, pdf):
        canvas.saveState()
        canvas.setStrokeColor(palette["line"])
        canvas.line(45, 37, 550, 37)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(palette["muted"])
        canvas.drawString(45, 24, "WanderClimate - Climate-driven tourism intelligence")
        canvas.drawRightString(550, 24, f"Page {pdf.page}")
        canvas.restoreState()
    doc.build(story, onFirstPage=page_footer, onLaterPages=page_footer)
    cityslug = "".join(c if c.isalnum() or c in "-_" else "-" for c in request.city).strip("-")[:65] or "trip"
    return Response(buffer.getvalue(), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="WanderClimate-{cityslug}-Itinerary.pdf"'})
