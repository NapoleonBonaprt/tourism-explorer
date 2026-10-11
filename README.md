# Tourism Explorer — Streamlit

## 1. Export your notebook data
Run this in the notebook after `full` and `places_with_clusters` exist:

```python
full.to_csv("full.csv", index=False)
places_with_clusters.to_csv("places_with_clusters.csv", index=False)
```

## 2. Install and run
```bash
pip install -r requirements.txt
streamlit run app.py
```

## 3. In the app
Upload `full.csv` and `places_with_clusters.csv` in the sidebar. The app ranks the existing TCI values; it does not use KNN predictions.

The map needs a destination-name column and latitude/longitude columns. The app recognizes common names such as `Latitude`/`Longitude`, `lat`/`lon`, and `Destination Name`.
