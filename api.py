"""Project: Climate-Smart Tourism Intelligence API

Author: Data Science & Analytics Team
Description: Production-grade, fully-typed FastAPI backend for global tourism
             analytics, DBSCAN spatial clustering, and meteorological climate profiles.
"""

import os
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
import pandas as pd

# Initialize FastAPI application with rich metadata
app = FastAPI(
    title="🌍 Climate-Smart Tourism Intelligence API",
    description=(
        "Professional backend service providing comprehensive meteorological"
        " analytics, DBSCAN spatial clusters, and real-time destination"
        " recommendations."
    ),
    version="2.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

from fastapi.middleware.cors import CORSMiddleware

# أضيفي هذا بعد تعريف app مباشرة:
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # السماح للجميع بالاتصال
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Root directory for automated file discovery
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))


# --- Pydantic Models for Perfect Documentation & Strict Responses ---
class SystemStatusResponse(BaseModel):
  status: str = Field(..., example="online")
  project: str = Field(..., example="Climate-Smart Tourism Intelligence")
  version: str = Field(..., example="2.2.0")
  documentation: str = Field(..., example="/docs")
  redoc: str = Field(..., example="/redoc")


def find_file(filename: str) -> Optional[str]:
  """Recursively searches for required dataset files within the project directory."""
  for root, dirs, files in os.walk(ROOT_DIR):
    if filename in files:
      return os.path.join(root, filename)
  return None


@app.get(
    "/",
    tags=["System Status"],
    summary="API Health Check & Documentation Index",
    response_model=SystemStatusResponse,
)
def read_root():
  """Returns operational status and navigation links for the analytics engine."""
  return {
      "status": "online",
      "project": "Climate-Smart Tourism Intelligence",
      "version": "2.2.0",
      "documentation": "/docs",
      "redoc": "/redoc",
  }


class CityOption(BaseModel):
  city: str
  country: str


@app.get(
    "/cities",
    tags=["Climate Intelligence"],
    summary="List available cities and their countries",
    response_model=List[CityOption],
)
def list_cities() -> List[CityOption]:
  """Return unique city/country pairs from the same data as city climate search."""
  path = find_file("city_month_features.csv")
  if not path:
    raise HTTPException(
        status_code=404, detail="Dataset 'city_month_features.csv' not found."
    )

  try:
    cities = pd.read_csv(
        path, usecols=["City", "Country_dest"], dtype="string"
    ).dropna()
  except ValueError as exc:
    raise HTTPException(
        status_code=500,
        detail="City or Country_dest column missing from climate dataset.",
    ) from exc
  except (OSError, pd.errors.ParserError) as exc:
    raise HTTPException(
        status_code=500, detail="Unable to read the climate dataset."
    ) from exc

  cities["City"] = cities["City"].str.strip()
  cities["Country_dest"] = cities["Country_dest"].str.strip()
  cities = cities[(cities["City"] != "") & (cities["Country_dest"] != "")]
  cities = (
      cities.drop_duplicates(subset=["City", "Country_dest"])
      .sort_values(["City", "Country_dest"], key=lambda values: values.str.casefold())
  )
  return [
      CityOption(city=city, country=country)
      for city, country in cities.itertuples(index=False, name=None)
  ]


@app.get(
    "/overview/summary",
    tags=["Spatial Analytics"],
    summary="Retrieve DBSCAN Spatial Cluster Summary",
)
def get_cluster_summary() -> List[Dict]:
  """Fetches statistical summaries and metadata for spatial clusters."""
  try:
    path = find_file("cluster_summary.csv")
    if not path:
      raise HTTPException(
          status_code=404, detail="Dataset 'cluster_summary.csv' not found."
      )
    df = pd.read_csv(path)
    return df.to_dict(orient="records")
  except Exception as e:
    raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/overview/countries",
    tags=["Spatial Analytics"],
    summary="Retrieve Country-Level Climate & Cluster Classification",
)
def get_country_summary() -> List[Dict]:
  """Fetches aggregated country cluster profiles and climate classifications."""
  try:
    path = find_file("country_cluster_summary.csv")
    if not path:
      raise HTTPException(
          status_code=404,
          detail="Dataset 'country_cluster_summary.csv' not found.",
      )
    df = pd.read_csv(path)
    return df.to_dict(orient="records")
  except Exception as e:
    raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/climate/search",
    tags=["Climate Intelligence"],
    summary="Search historical climate records by city and optional country",
)
def search_city_climate(
    city: str = Query(..., min_length=1),
    country: Optional[str] = Query(None),
) -> List[Dict]:
  """Find exact city climate records; disambiguate cities shared by countries."""
  path = find_file("city_month_features.csv")
  if not path:
    raise HTTPException(
        status_code=404, detail="Dataset 'city_month_features.csv' not found."
    )

  try:
    df = pd.read_csv(path)
  except (OSError, pd.errors.ParserError) as exc:
    raise HTTPException(
        status_code=500, detail="Unable to read the climate dataset."
    ) from exc

  if not {"City", "Country_dest"}.issubset(df.columns):
    raise HTTPException(
        status_code=500, detail="City or Country_dest column missing from climate dataset."
    )

  city_name = city.strip()
  if not city_name:
    raise HTTPException(status_code=422, detail="City must not be blank.")

  city_mask = (
      df["City"].astype("string").str.strip().str.casefold()
      .eq(city_name.casefold()).fillna(False)
  )
  country_name = country.strip() if country is not None else ""
  if country_name:
    country_mask = (
        df["Country_dest"].astype("string").str.strip().str.casefold()
        .eq(country_name.casefold()).fillna(False)
    )
    result = df.loc[city_mask & country_mask]
  else:
    result = df.loc[city_mask]
    countries = (
        result["Country_dest"].dropna().astype(str).str.strip()
        .loc[lambda values: values != ""].unique().tolist()
    )
    if len({name.casefold() for name in countries}) > 1:
      raise HTTPException(
          status_code=409,
          detail={
              "message": "This city exists in multiple countries. Specify country.",
              "countries": sorted(countries),
          },
      )

  if result.empty:
    raise HTTPException(
        status_code=404,
        detail=f"No climate records found for city '{city_name}'"
        + (f" in '{country_name}'." if country_name else "."),
    )

  # Retain all historical years; the frontend calculates one average per month.
  return result.to_dict(orient="records")


@app.get(
    "/climate/city/{city_name}",
    tags=["Climate Intelligence"],
    summary="Get Real-Time Monthly Climate Profiles for a City",
)
def get_city_climate(city_name: str) -> List[Dict]:
  """Retrieves comprehensive monthly meteorological features for a specified destination city."""
  try:
    path = find_file("city_month_features.csv")
    if not path:
      raise HTTPException(
          status_code=404, detail="Dataset 'city_month_features.csv' not found."
      )

    df = pd.read_csv(path)
    if "City" not in df.columns:
      raise HTTPException(
          status_code=500, detail="Column 'City' missing from climate dataset."
      )

    result = df[df["City"].str.lower() == city_name.lower().strip()]
    if result.empty:
      raise HTTPException(
          status_code=404,
          detail=f"City '{city_name}' not found in meteorological records.",
      )

    return result.to_dict(orient="records")
  except HTTPException as he:
    raise he
  except Exception as e:
    raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/attractions/country/{country_name}",
    tags=["Attractions & Clustering"],
    summary="Get Tourist Attractions & Spatial Clusters by Country",
)
def get_country_attractions(country_name: str) -> List[Dict]:
  """Retrieves all tourist attractions and associated DBSCAN cluster tags for a specific country."""
  try:
    path = find_file("attractions_with_clusters.csv")
    if not path:
      path = find_file("places_with_clusters.csv")

    if not path:
      raise HTTPException(
          status_code=404, detail="Attractions cluster dataset not found."
      )

    df = pd.read_csv(path)
    country_col = (
        "Country_dest"
        if "Country_dest" in df.columns
        else ("Country" if "Country" in df.columns else None)
    )

    if not country_col:
      raise HTTPException(
          status_code=500,
          detail="Country identifier column missing from attractions dataset.",
      )

    result = df[df[country_col].str.lower() == country_name.lower().strip()]
    if result.empty:
      raise HTTPException(
          status_code=404,
          detail=f"Country '{country_name}' not found in attractions database.",
      )

    return result.to_dict(orient="records")
  except HTTPException as he:
    raise he
  except Exception as e:
    raise HTTPException(status_code=500, detail=str(e))

# Website-facing equivalents of the Streamlit dashboard pages.
from website_api import router as website_router
app.include_router(website_router)
