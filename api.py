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