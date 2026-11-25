# WanderClimate | Tourism Explorer

**Climate-aware destination discovery, tourism analytics, machine learning and adaptive trip planning.**

WanderClimate is the traveler-facing website of Tourism Explorer, a collaborative data-science project that combines historical climate observations, Tourism Climate Index (TCI), monthly machine-learning forecasts, geographic clustering and practical weather-aware itineraries.

[Website](https://mahmoudkh6.pythonanywhere.com/) · [Streamlit dashboard](https://tourism-explorer-eacdqv7bn7sw97tuhoyt.streamlit.app/) · [Development branch](https://github.com/NapoleonBonaprt/tourism-explorer/tree/forecast-development) · [Automated checks](https://github.com/NapoleonBonaprt/tourism-explorer/actions/workflows/forecast-checks.yml) · [EDA notebook](python%20files/EDA_Notebook.ipynb)

> **Version note:** This document describes the latest implementation on `forecast-development`. The default branch and the deployed website may lag behind it. Verify the deployed revision and the latest integration checks before treating a feature as live.

## What the website does

| Page | Features |
| --- | --- |
| [Home / city discovery](https://mahmoudkh6.pythonanywhere.com/) | Destination search, city photography, discovery map, historical monthly climate and date-based future city forecasts. |
| [Executive Overview](https://mahmoudkh6.pythonanywhere.com/overview.html) | Dataset KPIs, TCI distribution and country-level tourism insights. |
| [Climate & TCI Analytics](https://mahmoudkh6.pythonanywhere.com/climate.html) | Historical monthly averages, original yearly observations, future monthly TCI and weather estimates, model reliability. |
| [Map Explorer](https://mahmoudkh6.pythonanywhere.com/explorer.html) | Country/city filters, historical or date-based Top 5 recommendations, DBSCAN clusters, attraction search and interactive map. |
| [Itinerary Planner](https://mahmoudkh6.pythonanywhere.com/planner.html) | Country, city, date and attraction category selection; climate suitability, forecasts and matching attractions. |
| [Adaptive Daily Itinerary](https://mahmoudkh6.pythonanywhere.com/adaptive.html) | Exact trip dates, 1–7 days, 2–5 requested stops per day, weather-aware planning, daily cards, numbered map, recheck, storm simulation and PDF export. |

The native HTML/CSS/JavaScript pages use FastAPI, Chart.js, Leaflet and OpenStreetMap. No embedded Streamlit iframe is needed. The original integrated Streamlit dashboard remains available in `dashboard.py`.

### User experience

- Responsive layouts, shared navigation, consistent typography, city photography and light/dark themes.
- A shared themed travel calendar across forecast-enabled pages, with date validation and an available forecast range supplied by the API.
- City-level historical climate and future monthly forecasts on the ordinary city pages as well as the analytics pages.
- Interactive maps with city/attraction search, cluster visibility controls, Top 5 filters, markers, popups and Google Maps links.
- Light mode uses OpenStreetMap; dark mode uses Esri World Dark Gray tiles with attribution. Maps require connectivity.

## Climate intelligence and prediction

The project distinguishes three different sources of information:

| Source | Resolution | Use |
| --- | --- | --- |
| Historical climate records | Monthly observations and climatological averages | Seasonal comparison, historical TCI and recorded rankings |
| Machine-learning forecasts | Direct monthly estimates, up to 24 months from the model/data origin | Long-range destination selection and provisional trip planning |
| Open-Meteo forecast API | Daily short-range weather | Weather-aware daily itineraries and replanning within the supported seven-day window |

Monthly estimates are **not daily weather forecasts**. A travel date selects its target month; the model does not claim to know the weather on that specific future day. The valid forecast window comes from `GET /website/forecast-info`, not from a hard-coded calendar year.

### Historical analysis and TCI

The original [EDA notebook](python%20files/EDA_Notebook.ipynb) includes cleaning, climate visualization, geographic clustering and an offline KNN regression experiment. Its reported random held-out split used K = 7, MAE = 2.87, RMSE = 3.86 and R² = 0.970. These are historical regression results, **not future forecasting accuracy**.

The Tourism Climate Index combines daytime comfort (CID), daily comfort (CIA), precipitation, sunshine and wind scores:

```text
TCI = 2 × (4 × CID + CIA + 2 × P_score + 2 × S_score + W_score)
```

[`tci_scoring.py`](tci_scoring.py) reconstructs and verifies the component scores and TCI categories against the original historical observations. Rules for previously unobserved extreme temperature or wind conditions are explicit assumptions, not recovered original source code.

### Future TCI forecasting

[`forecast_service.py`](forecast_service.py) performs request-time prediction using city coordinates, seasonal features, lagged TCI and historical weather summaries. It does not serve precomputed values from `future_predictions.csv`.

- **Residual XGBoost** was selected using the lowest mean validation MAE across the original 12 monthly horizons, without selecting on the final test results.
- Horizons 1–12 load saved models. Horizons 13–24 use direct long-lead fitting and separately evaluated 2025 backtests.
- Feature construction uses observations available at the forecast origin; metadata checks prevent serving saved models against an incompatible history.
- The service reports lead-specific error metrics, historical performance within ±10 TCI points, and historical-mean benchmark comparisons.

Original 1–12-month experiment results from [model_summary.csv](python%20files/forecast_results/model_summary.csv):

| Model | Validation MAE | Test MAE | Test RMSE |
| --- | ---: | ---: | ---: |
| Residual XGBoost (selected) | 5.888 | 5.605 | 7.272 |
| XGBoost | 6.012 | 5.700 | 7.489 |
| Random Forest | 6.015 | 5.683 | 7.445 |
| Residual Ridge | 6.024 | 5.680 | 7.461 |
| Ridge Regression | 6.050 | 5.754 | 7.550 |
| Linear Regression | 6.071 | 5.758 | 7.518 |
| Historical Mean | 6.174 | 5.371 | 7.168 |
| KNN | 6.234 | 5.871 | 7.803 |
| Decision Tree | 6.422 | 5.875 | 7.663 |
| Seasonal Naive | 7.829 | 6.801 | 9.312 |

Residual XGBoost achieved a mean test R² of 0.893 and 84.62% of test predictions within 10 TCI points in this experiment. The historical mean had lower test MAE overall; the selected ML model is therefore **not uniformly superior to the baseline**. The website surfaces such limitations instead of presenting a historical success rate as a probability for an individual future prediction.

See [forecast results](python%20files/forecast_results/) for model artifacts, horizon-level evaluation, comparison plots and prediction outputs.

### Separate monthly weather models

[`weather_forecast.py`](weather_forecast.py) uses direct residual Ridge regression models for each of 24 horizons. The model estimates deviations from historical monthly weather averages, with per-variable regularization chosen on 2023 validation data and a temporally separated 2025 test.

| Variable | Error tolerance | Test MAE | Test RMSE | Within tolerance | Baseline MAE |
| --- | --- | ---: | ---: | ---: | ---: |
| Mean temperature | ±2 °C | 1.06 | 1.36 | 85.63% | 1.06 |
| Monthly rainfall | ±20 mm | 34.80 | 50.31 | 44.75% | 32.17 |
| Mean wind speed | ±1 m/s | 0.78 | 0.92 | 72.68% | 0.74 |
| Mean relative humidity | ±10 percentage points | 4.69 | 6.27 | 89.41% | 4.64 |
| Mean daily sunshine | ±1 h/day | 0.59 | 0.79 | 81.49% | 0.57 |

These figures are the aggregated results in the checked-in [weather model summary](python%20files/monthly_weather_results/weather_model_summary.csv), not live guarantees. The baseline is competitive or better for several variables, particularly rainfall. The model returns variable-specific tolerances, error metrics, historical comparison and reliability for the requested horizon. Cached model bundles are checked against the current history fingerprint and retrained if incompatible.

Train and export all 24 weather horizons from the repository root:

```bash
python scripts/train_weather_models.py
```

## Destination recommendations and geospatial analytics

- Historical mode ranks stored TCI values; forecast mode uses predicted city-level TCI for the selected month.
- Top 5 recommendations reflect climate suitability, not an individual attraction's independently predicted weather.
- DBSCAN cluster labels are precomputed using Haversine distance and displayed on interactive maps; noise points are labeled separately.
- The attraction catalog is deduplicated across historical records. Filters and attraction popularity help select relevant places.
- Map links use dataset coordinates. Geographic route lines represent the visit order, not road routing, walking directions or measured travel times.

## Adaptive itinerary planning

The adaptive planner combines [`itinerary_engine2.py`](itinerary_engine2.py), [`website_api.py`](website_api.py) and the website UI.

1. Choose the destination, start date, trip length and requested stops per day.
2. For a trip entirely inside the supported daily weather window, retrieve Open-Meteo forecasts for its actual travel dates.
3. Classify conditions as indoor, outdoor or mixed and select suitable nearby attractions while avoiding repeated visits where possible.
4. Order attractions using a nearest-neighbor Haversine-distance heuristic and balance morning/afternoon visit slots independently of attraction category.
5. For a trip outside the daily forecast window, generate a **provisional monthly TCI-based plan** with separate monthly weather estimates. Trips crossing a month boundary use the corresponding month's outlook.
6. Recheck weather and adjust affected days when conditions change. Rebuild long-range plans within seven days of travel to obtain daily forecasts.

Opening hours, bookings, actual transportation times and accessibility constraints are not automatically verified.

### Downloadable travel guides

Download a concise A4 travel guide from Adaptive Daily Itinerary. The redesigned PDF is intended for non-technical travelers rather than as a model evaluation report.

- Destination photograph in the cover with trip dates and number of places to discover.
- Daily itinerary cards with dates, morning/afternoon visits and simple labels such as **Indoor escapes**, **Outdoor discoveries** and **Flexible sightseeing**.
- Clickable attraction names linking directly to Google Maps.
- Rounded temperature values and concise weather or packing guidance.
- For long-range trips, a clear provisional-plan warning and a monthly climate outlook alongside each day's visits.
- No unnecessary technical model metrics or raw coordinate tables in the traveler guide.
- Browser generation using jsPDF, with a ReportLab server export fallback. Print / Save as PDF is also available from the browser.

The PDF cover pipeline uses local JPEGs in [`assets/cities/`](assets/cities/), not a required third-party image download. Images are cropped to 900 × 560 for consistent cover composition. Cairo, Lisbon, Paris, Rome and Tokyo have locally cached copies of their configured original photographs. Those five cities plus Madrid and Barcelona require a valid photo rather than silently exporting a placeholder; if both local and server photo retrieval fail, the export reports an error. Madrid and Barcelona intentionally share identical image bytes for now, so the Madrid cover is **not a verified photograph of Madrid**. Other destinations use local photographs when available, with an illustrated fallback for invalid or missing files.

The browser can use the local static image directly, with the same-origin cover endpoint as a fallback. A versioned URL avoids stale cached cover responses. PDF generation still requires access to the necessary image bytes and PDF library or server; it is not guaranteed to be fully offline.

See [`trip-pdf.js`](trip-pdf.js), [`trip_guide.py`](trip_guide.py) and [`guide_cover.py`](guide_cover.py).

## API and architecture

The website and API can be served from the same origin through [`web_server.py`](web_server.py). The application uses FastAPI, Pandas, NumPy, scikit-learn, XGBoost, Joblib, Pillow and ReportLab; the frontend uses native JavaScript, CSS, Chart.js, Leaflet and jsPDF.

| Method and route | Purpose |
| --- | --- |
| GET /health | Website health check |
| GET /docs | Interactive API documentation |
| GET /website/filters | Available countries, cities and filters |
| GET /website/destination-coordinates | City locations |
| GET /website/overview | Dashboard summary |
| GET /website/climate | Historical climate records and monthly statistics |
| GET /website/forecast-info | Supported forecast window and model metadata |
| GET /website/forecast | Monthly TCI and weather forecasts |
| GET /website/explorer | Historical or forecast-ranked destinations and map data |
| GET /website/planner | Climate suitability and matching attractions |
| POST /website/adaptive/build | Build dated daily or provisional monthly itinerary |
| POST /website/adaptive/recheck | Recheck and adapt the itinerary |
| GET /website/guide-cover?city=Paris | Local JPEG cover and X-Guide-Cover response header |
| POST /website/adaptive/export-pdf | Generate the travel-guide PDF on the server |

Legacy historical REST routes in `api.py` include `/overview/summary`, `/overview/countries`, `/climate/city/{city_name}` and `/attractions/country/{country_name}`.

## Repository structure

```text
tourism-explorer/
├── index.html                    # Home and city discovery
├── overview.html                  # Executive overview
├── climate.html                   # Historical and forecast analytics
├── explorer.html                  # Map and recommendations
├── planner.html                   # Interactive planner
├── adaptive.html                  # Adaptive trip planner
├── dashboard-site.js / .css       # Shared website UI
├── travel-calendar.js / .css      # Shared date picker
├── discovery-map.js / .css        # Destination discovery map
├── theme.js                       # Light/dark preferences
├── assets/cities/                 # Local city photographs
├── web_server.py                  # Same-origin website and ASGI service
├── api.py / website_api.py        # REST APIs
├── forecast_service.py            # Direct monthly TCI inference
├── weather_forecast.py            # Monthly weather prediction
├── tci_scoring.py                 # Historical TCI reconstruction
├── itinerary_engine2.py           # Trip selection and ordering
├── trip-pdf.js / trip_guide.py     # Browser/server PDF rendering
├── guide_cover.py                 # City cover preparation
├── dashboard.py / itinerary_page.py # Integrated Streamlit UI
├── app.py                         # Original standalone Streamlit app
├── cleaned_data/
│   ├── city_month_features.csv
│   └── tourism_final_clean.csv
├── full.csv
├── places_with_clusters.csv
├── python files/
│   ├── EDA_Notebook.ipynb
│   ├── forecast_results/
│   ├── monthly_weather_results/
│   └── processed_data/
├── scripts/                       # Refresh, training and testing utilities
├── .github/workflows/             # CI and image caching
├── requirements.txt
└── requirements-deploy.txt
```

## Run locally

Python 3.12 is recommended for the deployment environment and saved XGBoost 3.4.1 models. Use a virtual environment and install the deployment dependencies.

```bash
git clone https://github.com/NapoleonBonaprt/tourism-explorer.git
cd tourism-explorer
git switch forecast-development
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows PowerShell (instead of source):
# .venv\Scripts\Activate.ps1
python -m pip install -r requirements-deploy.txt
python -m uvicorn web_server:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000/ for the complete website, http://127.0.0.1:8000/docs for the API and http://127.0.0.1:8000/health for the health endpoint. Internet access is needed for Open-Meteo, external frontend libraries and map tiles.

### Streamlit dashboard

```bash
python -m pip install -r requirements.txt
python -m streamlit run dashboard.py
```

The integrated dashboard includes all five analytics sections and automatically reads repository CSVs. The original standalone `app.py` can still be launched with `python -m streamlit run app.py`, but requires uploading `full.csv` and `places_with_clusters.csv`. Streamlit Community Cloud uses `dashboard.py` as the main file on its configured branch. The advanced forecasting website and Streamlit are distinct interfaces; not every website feature is implemented in Streamlit.

## Data maintenance

[`scripts/refresh_climate.py`](scripts/refresh_climate.py) stages complete months of archive weather observations, validates all city-month records and reconstructs TCI before an explicitly requested append. The default operation stages data without modifying the canonical history.

```bash
python scripts/refresh_climate.py --through YYYY-MM
# Only after reviewing the staged data:
python scripts/refresh_climate.py --through YYYY-MM --apply
```

Replace YYYY-MM with the last available complete month. After applying updates, regenerate compatible TCI artifacts and selection metadata using the corresponding training workflow before restarting the website; retrain the monthly weather models using the command above. Do not deploy mismatched history/model files. The forecast service rejects incompatible TCI artifacts rather than silently serving them.

Refresh and validate city photographs if needed:

```bash
python scripts/cache_original_city_photos.py
python scripts/verify_city_assets.py
```

The cache script retrieves the five configured source photographs, validates the images and limits their dimensions. The asset audit reports duplicate content, including the known Madrid/Barcelona pair. See [image source details](assets/cities/README.md).

## Testing and deployment

The [Forecast integration checks](https://github.com/NapoleonBonaprt/tourism-explorer/actions/workflows/forecast-checks.yml) workflow uses Python 3.12, compiles source files, trains weather models and runs API, model, Chromium/Playwright and PDF integration tests against a local ASGI server. Test outputs and screenshots are uploaded as workflow artifacts.

```bash
python -m pip install -r requirements-deploy.txt httpx playwright pypdf
python -m playwright install chromium
python scripts/train_weather_models.py
python scripts/test_forecast.py
# Start uvicorn web_server:app on port 8000 in another terminal:
python scripts/test_forecast_browser.py
python scripts/test_site_full.py
```

Tests cover historical and forecast data, city pages, date limits, daily and month-crossing trips, map interactions, calendar accessibility and PDF output, including cover images and server fallback. Check the actual workflow result before deploying.

### PythonAnywhere (ASGI)

Public URL: [mahmoudkh6.pythonanywhere.com](https://mahmoudkh6.pythonanywhere.com/).

The deployment should use the repository working directory, its Python virtual environment and `web_server:app` as the ASGI application. Confirm the actual configured directory and branch first. Once the desired commit has passed integration checks, update the existing checkout without overwriting local changes:

```bash
git status --short
git branch --show-current
git pull --ff-only origin forecast-development
```

Install changed deployment dependencies in the existing virtual environment if necessary, then reload the configured ASGI website with PythonAnywhere's website management tools. If the deployed checkout uses another branch, review and merge/switch as appropriate rather than pulling a different branch blindly.

Post-deployment verification:

```bash
curl -fsS https://mahmoudkh6.pythonanywhere.com/health
for city in Cairo Lisbon Paris Rome Tokyo Madrid Barcelona; do
  echo "$city"
  curl -fsS -D - -o /dev/null \
    "https://mahmoudkh6.pythonanywhere.com/website/guide-cover?city=$city&v=6" \
    | grep -iE 'HTTP/|x-guide-cover:'
done
```

All seven should return a successful JPEG response with `X-Guide-Cover: photo`. Open the deployed city pages, build short-range and long-range itineraries, download their PDFs and inspect the actual cover and daily cards. The repository and CI results do not by themselves confirm a live deployment.

## Limitations and future work

- Long-range weather is monthly and uncertain; it cannot predict exact daily conditions.
- Historical performance is not a calibrated per-trip probability. Historical mean baselines can outperform ML predictions.
- TCI is a city-level climate suitability index, not a personalized guarantee of comfort or attraction quality.
- DBSCAN is precomputed; route ordering is not road routing or a booking service.
- Madrid's current photo duplicates Barcelona's and should eventually be replaced with a verified Madrid image.
- External weather, maps and frontend libraries require connectivity.
- Additional geographic validation, periodic archive updates, verified attraction hours and accessibility information would improve the system.

## Team and contributions

See the [commit history](https://github.com/NapoleonBonaprt/tourism-explorer/commits/forecast-development) for implementation details and attribution.

- [@NapoleonBonaprt](https://github.com/NapoleonBonaprt) — project repository, analysis, original Streamlit app and dashboard integration.
- [@shadzzzm48-ctrl](https://github.com/shadzzzm48-ctrl) — itinerary planning and dashboard contributions.
- [@basmala-dot](https://github.com/basmala-dot) — HTML frontend contributions.

---

*Tourism Explorer / WanderClimate is an educational data-science project. Verify local weather, travel arrangements and attraction information before traveling.*
