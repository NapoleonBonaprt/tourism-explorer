# 🌍 Tourism Explorer

### Climate-Aware Destination Recommendations, Geospatial Analytics & Adaptive Trip Planning

**Tourism Explorer** is a collaborative Python data science project that combines historical climate analysis, Tourism Climate Index (TCI) rankings, geospatial clustering, interactive maps, and weather-aware itinerary planning.

The project now includes a **multi-page Streamlit dashboard** that integrates the original Top 5 Recommendations & Dynamic Map page, a separate **FastAPI backend**, and an experimental **HTML frontend**.

**[🚀 Streamlit Dashboard](https://tourism-explorer-eacdqv7bn7swpw97tuhoyt.streamlit.app/)** · **[📓 EDA & ML Notebook](python%20files/EDA_Notebook.ipynb)** · **[🔌 API Source](api.py)**

> **Important:** The main dashboard is `dashboard.py`. The original `app.py` remains available as a standalone Streamlit app, but it still asks users to upload two CSV files. In the integrated dashboard, the corresponding recommendations page loads those files automatically from the repository.

## ✨ Main Dashboard Features

Start with `streamlit run dashboard.py`. The sidebar offers five sections:

| Page | Features |
| --- | --- |
| **Executive Overview** | Summary metrics, TCI category distribution, and country-level tourism insights. |
| **Climate & TCI Analytics** | Country/city selection, monthly temperature and TCI trends, and climate indicators such as humidity, rainfall, and sunshine. |
| **Spatial Clustering & Map Explorer** | **Integrated original Tourism Explorer page:** country and month filters, optional city/governorate filter, Top 5 destinations ranked by existing TCI values, and a **dynamic Folium map** that changes with the selected country. |
| **Interactive Itinerary Planner** | Choose a country, city, month, and Indoor/Outdoor preference to view historical monthly climate suitability and suggested attractions. |
| **Adaptive Daily Itinerary** | Build a 1–7 day trip using an Open-Meteo weather forecast, select a number of stops per day, show routes and locations on a map, and re-plan days when weather conditions change. |

### Top 5 Recommendations & Dynamic DBSCAN Map

The original `app.py` recommendation experience has been embedded directly into the dashboard's **Spatial Clustering & Map Explorer** section:

- Filters destination records by country and month, with an optional city/governorate filter when supported by the dataset.
- Ranks available destinations by their **recorded TCI scores** and displays the **Top 5**.
- Re-centers the Folium/OpenStreetMap map on attractions belonging to the selected country; it does **not** rely on a fixed, pre-generated Egypt map.
- Displays **precomputed DBSCAN spatial cluster labels** using distinct colors, highlights matching Top 5 locations with a dark outline, and shows noise points (`-1`) in gray.
- Includes interactive markers, popups, a cluster legend, and map summary metrics.
- Automatically reads `full.csv` and `places_with_clusters.csv` when used inside `dashboard.py`.

**Recommendation methodology:** The Top 5 list is a **ranking of existing TCI values**, not a live inference from the notebook's KNN model. The map displays **precomputed** DBSCAN labels; the dashboard does not rerun DBSCAN.

### Adaptive Daily Itinerary

The weather-adaptive planner is implemented in `itinerary_page.py` and `itinerary_engine2.py`.

- Retrieves a short-range daily forecast from the **Open-Meteo forecast API**.
- Classifies days as **outdoor**, **mixed**, or **indoor** based on weather conditions.
- Selects suitable nearby attractions, avoids repeating attractions across days where possible, and allocates available stops across the trip.
- Orders stops using a **nearest-neighbor heuristic** with Haversine distances.
- Displays daily cards and an interactive Folium map with stop order.
- Supports **re-checking the forecast**, rebuilding days whose weather category changes, and a **storm simulation** for demonstrations.

**Route limitation:** Lines drawn between stops are straight-line connections, not turn-by-turn road or walking directions. Forecasts apply to the adaptive planner; historical monthly TCI rankings are a separate dataset-driven feature.

## 🧪 Data Science & Machine Learning

The EDA notebook covers data cleaning, exploratory visualization, climate/TCI relationships, an **offline K-Nearest Neighbors regression experiment**, and **DBSCAN geographic clustering** using Haversine distance.

The existing notebook evaluation reports:

| Metric | Reported notebook result |
| --- | ---: |
| Best KNN `n_neighbors` | 7 |
| Mean Absolute Error (MAE) | 2.87 |
| Root Mean Squared Error (RMSE) | 3.86 |
| R² | 0.970 |

These metrics are from a random held-out split in the notebook; they are **not** proof of performance on future weather or unseen cities. Geographic and temporal validation would be useful next steps.

## 🧩 Other Application Components

### Standalone Streamlit app — `app.py`

The original Tourism Explorer interface remains in the repository for reference or independent use. It has country/month filtering, Top 5 recommendations, and an interactive cluster map. Unlike the integrated dashboard page, it **requires the user to upload** `full.csv` and `places_with_clusters.csv` in its sidebar.

Run it separately with:

```bash
python -m streamlit run app.py
```

### FastAPI backend — `api.py`

The backend serves **CSV-backed historical climate and clustering records** through REST endpoints:

| Endpoint | Purpose |
| --- | --- |
| `GET /` | Service status |
| `GET /overview/summary` | Cluster summary records |
| `GET /overview/countries` | Country-level cluster summary |
| `GET /climate/city/{city_name}` | Monthly climate/TCI records for a city |
| `GET /attractions/country/{country_name}` | Attractions and cluster labels for a country |
| `GET /docs` | Interactive Swagger API documentation |
| `GET /redoc` | ReDoc documentation |

These endpoints read project datasets; the monthly climate endpoint is **not a real-time weather forecast**. The adaptive Streamlit itinerary separately calls Open-Meteo.

### HTML frontend — `index.html`

**WanderClimate** is a separate HTML/CSS/JavaScript prototype for exploring the best time to visit a city, showing monthly climate values and TCI trends. It calls the FastAPI backend.

The HTML currently targets `http://127.0.0.1:8000`, so it is set up for **local development**. Publishing it on the internet requires deploying the backend and updating the API URL. A small Lisbon sample is available in the frontend as a fallback demonstration.

## 📁 Repository Structure

```text
tourism-explorer/
├── dashboard.py                    # Main multi-page Streamlit dashboard
├── app.py                          # Original standalone Streamlit interface
├── itinerary_page.py               # Adaptive itinerary UI
├── itinerary_engine2.py            # Weather classification and trip-planning logic
├── api.py                          # FastAPI backend
├── index.html                      # Separate WanderClimate frontend
├── requirements.txt                # Main Streamlit dashboard dependencies
├── full.csv                        # Destination ranking data
├── places_with_clusters.csv        # Attraction coordinates and DBSCAN labels
├── cleaned_data/
│   ├── tourism_final_clean.csv
│   └── city_month_features.csv
├── python files/
│   ├── EDA_Notebook.ipynb          # EDA, KNN experiment, and clustering
│   ├── Destinations.py
│   ├── weather_py.file.py
│   └── processed_data/
│       ├── attractions_with_clusters.csv
│       ├── cluster_summary.csv
│       ├── country_cluster_summary.csv
│       └── selected_country_map.html
├── raw_data/                       # Input data
├── .devcontainer/                  # Development-container configuration
└── README.md
```

## 💻 Run Locally

**Requirements:** Python 3.11+ is recommended, along with Git and an internet connection for forecast requests.

1. Clone the repository:

   ```bash
   git clone https://github.com/NapoleonBonaprt/tourism-explorer.git
   cd tourism-explorer
   ```

2. Install the dashboard dependencies:

   ```bash
   python -m pip install -r requirements.txt
   ```

3. Start the **integrated Streamlit dashboard**:

   ```bash
   python -m streamlit run dashboard.py
   ```

4. Open the Streamlit local address, usually **http://localhost:8501**, and navigate to **Spatial Clustering & Map Explorer** to use the integrated Top 5 Recommendations & Dynamic Map. **No CSV uploads are required in this dashboard.**

The dashboard reads its CSV files from the project directory. Its file discovery uses the location of `dashboard.py`, rather than a Windows user-specific absolute path.

### Run the FastAPI + HTML website locally

The API dependencies are **separate** from the dashboard's `requirements.txt`:

```bash
python -m pip install fastapi uvicorn
python -m uvicorn api:app --reload
```

Check **http://127.0.0.1:8000/docs** and try **http://127.0.0.1:8000/climate/city/Cairo**.

Then, in another terminal at the repository root:

```bash
python -m http.server 5500
```

Open **http://127.0.0.1:5500/index.html**. Keep both servers running while using this frontend.

### Notebook dependencies

Running the EDA/ML notebook separately may require **Jupyter, Scikit-learn**, and the data-science packages used in the notebook. The primary `requirements.txt` is intended for the Streamlit dashboard, not the full development/ML environment.

### Development container note

The included `.devcontainer` currently starts `app.py` by default. To use the integrated experience in a development container, run `python -m streamlit run dashboard.py` instead.

## ☁️ Streamlit Deployment

For the **integrated dashboard**, select these settings in Streamlit Community Cloud:

- **Repository:** `NapoleonBonaprt/tourism-explorer`
- **Branch:** `main`
- **Main file path:** `dashboard.py`

The original standalone application uses `app.py` instead. Changing the repository files alone does not change the main-file setting of an existing deployment.

**Dashboard URL:** [Tourism Explorer on Streamlit Cloud](https://tourism-explorer-eacdqv7bn7swpw97tuhoyt.streamlit.app/).

## ⚠️ Current Limitations & Next Steps

- **No live KNN inference:** KNN is evaluated offline in the notebook; recommendation ranking uses stored TCI values.
- **Precomputed clustering:** DBSCAN labels are loaded from CSV rather than fitted during each dashboard session.
- **Different time horizons:** Monthly TCI records describe historical climate suitability; the adaptive itinerary uses a short-range weather forecast.
- **Simple route ordering:** The itinerary uses geographic proximity rather than travel times, roads, attraction opening hours, or bookings.
- **Separate HTML/API deployment:** The HTML frontend expects a locally running backend until a public API URL and deployment are configured.
- **Model evaluation:** Add location-based/time-based testing to assess generalization.
- **Product improvements:** Consider richer traveler preferences, automated testing, clearer data-source documentation, and performance improvements for large maps.

## 👥 Team & Contributions

This repository reflects contributions from multiple collaborators. See the [commit history](https://github.com/NapoleonBonaprt/tourism-explorer/commits/main) for attribution and implementation details.

- [@NapoleonBonaprt](https://github.com/NapoleonBonaprt) — project repository, analysis, original Streamlit app, and dashboard integration.
- [@shadzzzm48-ctrl](https://github.com/shadzzzm48-ctrl) — itinerary planning and dashboard contributions.
- [@basmala-dot](https://github.com/basmala-dot) — HTML frontend contributions.

---

*Tourism Explorer is an educational data-science and application-integration project. Recommendations and forecast-driven plans are illustrative; verify local conditions and attraction details before traveling.*
