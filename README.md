# 🌍 Tourism Explorer

### Climate-Aware Tourism Recommendations & Geospatial Analysis

**Tourism Explorer** is a data science project that explores how historical climate conditions affect destination suitability. It combines data cleaning, exploratory data analysis (EDA), a machine-learning experiment, geospatial clustering, and a Streamlit application for exploring destinations.

**[🚀 Open Live Streamlit App](https://tourism-explorer-batn4sweatqgcua6fkr7bm.streamlit.app/)** · **[📓 Explore the EDA Notebook](python%20files/EDA_Notebook.ipynb)**

> **Current app behavior:** The deployed app ranks destinations using **existing Tourism Climate Index (TCI) values** from an uploaded CSV. It does **not** run the KNN model to generate predictions. Visitors must upload the two project CSV files to use all app features.

## ✨ Key Features

- **Climate-aware exploration:** Filter destination records by country and month, with an optional city/governorate filter.
- **Top 5 recommendations:** Rank available destinations by their recorded TCI values.
- **Interactive maps:** Explore attraction coordinates using Folium and OpenStreetMap.
- **Geospatial clustering:** Visualize precomputed DBSCAN clusters with distinct marker colors; noise points are shown in gray.
- **Easy interpretation:** Highlight top-ranked attractions on the map and show TCI and cluster information.
- **Separate analysis notebook:** Investigate seasonal climate patterns, data quality, KNN regression, and geospatial clustering.

## 🧭 How It Works

1. **Prepare the data.** Clean and validate tourism/climate records, including missing values and geographic coordinates.
2. **Explore climate suitability.** Analyze weather-related variables and the Tourism Climate Index (TCI), including seasonal patterns.
3. **Experiment with ML (offline).** Train and evaluate a K-Nearest Neighbors regression model for estimating TCI in the analysis notebook.
4. **Cluster attractions (offline).** Apply DBSCAN using Haversine distance to group attractions by geographic proximity.
5. **Explore in Streamlit.** Upload the prepared CSVs, choose a country and month, view the top five destinations by recorded TCI, and inspect their locations on a color-coded map.

**Important distinction:** KNN modeling and DBSCAN clustering are performed in the notebook. The Streamlit app reads **precomputed** TCI values and cluster labels; it does not retrain models or forecast real-time weather.

## 📊 Offline Machine Learning Evaluation

The EDA notebook uses a standardized **KNeighborsRegressor**, with `GridSearchCV` to select the number of neighbors and a random 80/20 train/test split.

| Metric | Notebook result |
| --- | ---: |
| Best `n_neighbors` | `7` |
| Mean Absolute Error (MAE) | `2.87` |
| Root Mean Squared Error (RMSE) | `3.86` |
| R² | `0.970` |

These values describe the notebook's held-out random split, **not** accuracy on future weather or entirely unseen locations. Since TCI is derived from climate variables, a geographically or temporally separated evaluation would be an important next step.

## 🛠️ Technology Stack

| Purpose | Tools |
| --- | --- |
| Data manipulation and EDA | Python, Pandas, NumPy, Jupyter Notebook |
| Charts and visualization | Matplotlib, Seaborn |
| Machine learning | Scikit-learn (KNN, GridSearchCV) |
| Geospatial clustering | DBSCAN, Haversine distance |
| Interactive mapping | Folium, OpenStreetMap |
| Web interface | Streamlit, streamlit-folium |

## 📁 Repository Structure

```text
tourism-explorer/
├── app.py                       # Streamlit web app
├── requirements.txt             # Web app dependencies
├── full.csv                     # Data for destination ranking
├── places_with_clusters.csv     # Attraction coordinates and cluster labels
├── python files/
│   ├── EDA_Notebook.ipynb       # Analysis, KNN experiment and clustering
│   ├── Destinations.py
│   └── weather_py.file.py
├── cleaned_data/                # Prepared datasets
├── raw_data/                    # Input dataset(s)
└── README.md
```

## 🚀 Try the Live App

1. Open the **[Tourism Explorer live demo](https://tourism-explorer-batn4sweatqgcua6fkr7bm.streamlit.app/)**.
2. Download the repository's [`full.csv`](full.csv) and [`places_with_clusters.csv`](places_with_clusters.csv) files to your device.
3. In the app sidebar, upload **`full.csv`** as the recommendations dataset.
4. Upload **`places_with_clusters.csv`** as the attractions/map dataset.
5. Select a country and a month. Optionally enter a city or governorate if that field exists in the recommendations dataset.
6. View the **top five destinations** and explore the interactive clustered map.

> The CSV upload step is currently required for visitors, even though both files are stored in this repository. For a smoother public demo, loading a default dataset automatically is a planned improvement.

## 💻 Run Locally

**1. Clone the repository**

```bash
git clone https://github.com/NapoleonBonaprt/tourism-explorer.git
cd tourism-explorer
```

**2. Install the web app dependencies**

```bash
python -m pip install -r requirements.txt
```

**3. Start Streamlit**

```bash
streamlit run app.py
```

Open the local URL displayed by Streamlit (typically `http://localhost:8501`), then upload the two CSV files from the repository root in the sidebar.

`requirements.txt` covers the **Streamlit app**. Running the analysis notebook separately may require additional packages such as NumPy, Matplotlib, Seaborn, and Scikit-learn.

## ⚠️ Scope and Limitations

- Recommendations reflect **climate suitability indicated by existing TCI data**, not attraction quality, travel safety, or personalized satisfaction.
- The app does not retrieve live weather or make real-time climate forecasts.
- Destinations may share the same climate index, so the top-five ranking does not necessarily differentiate attractions within the same city.
- The optional city/governorate filter looks for matching values in the uploaded data; it is not a free-form geographic search engine.
- The live app requires manual CSV uploads in its current version.

## 🔭 Possible Next Improvements

- Load a small default sample dataset so visitors can try the live demo immediately.
- Add richer recommendations using attraction categories and user preferences.
- Evaluate the KNN model with country- or time-based held-out splits.
- Add application screenshots and concise insights from the EDA.
- Reduce app startup time and improve loading feedback for larger datasets.

## 👤 Author

**Mahmoud Khaled** — Computer Science student interested in Data Science, Machine Learning, and analytics.

- [GitHub](https://github.com/NapoleonBonaprt)
- [LinkedIn](https://www.linkedin.com/in/mahmoud-khaled-225379409/)

---

*Created as a practical data science and interactive analytics project.*
