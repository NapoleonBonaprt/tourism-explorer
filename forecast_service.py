"""Request-time monthly TCI inference; never reads future_predictions.csv."""
from functools import lru_cache
from pathlib import Path
import json
import numpy as np
import pandas as pd
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "python files" / "forecast_results"
WEATHER = ['Temp_Max_Mean','Temp_Min_Mean','Temp_Mean','RH_Mean','RH_Min_Mean',
           'Precip_Total_mm','Sunshine_h_per_day','Wind_Mean_ms']
KEY = ['Country_dest','City']
BASE = ['latitude','longitude','month_sin','month_cos','season_lag1','season_lag2',
        'season_mean','season_recent3','last_tci','recent3_tci']
FEATURES = BASE + [f'{p}_{w}' for p in ['season_last','season_mean','recent3'] for w in WEATHER]


@lru_cache(maxsize=1)
def history():
    df = pd.read_csv(ROOT / 'cleaned_data' / 'city_month_features.csv')
    df['date'] = pd.to_datetime(dict(year=df.Year, month=df.Month, day=1)).dt.to_period('M')
    df = df.sort_values(KEY + ['date'])
    if df.duplicated(KEY + ['date']).any() or df[WEATHER + ['TCI','City_Center_Lat','City_Center_Lon']].isna().any().any():
        raise ValueError('Invalid climate history')
    return df


@lru_cache(maxsize=1)
def metadata():
    selection = json.loads((RESULTS / 'selection.json').read_text())
    origin = pd.Period(selection['origin'], 'M')
    if history().date.max() != origin or not history().groupby(KEY).date.max().eq(origin).all():
        raise ValueError('Climate history and model origin differ; retrain and restart the server')
    return selection, origin, pd.read_csv(RESULTS / 'horizon_metrics.csv')


@lru_cache(maxsize=12)
def load_model(name, horizon):
    import joblib
    # Load only trusted repository artifacts, never user-supplied paths.
    model = joblib.load(RESULTS / f'{name.replace(" ", "_")}_{horizon:02d}m.joblib')
    if model['features'] != FEATURES or model['model_name'] != name or model['horizon_months'] != horizon or model['origin'] != str(metadata()[1]):
        raise ValueError('Model metadata mismatch')
    return model


def forecast_info():
    try:
        selection, origin, metrics = metadata()
        return {'origin': str(origin), 'min_date': str((origin+1).start_time.date()),
                'max_date': str((origin+12).end_time.date()), 'model': selection['best_climate_ml'],
                'resolution': 'monthly', 'baseline_test_better': bool(metrics.loc[metrics.Model.eq('Historical Mean'), 'MAE'].mean() < metrics.loc[metrics.Model.eq(selection['best_climate_ml']), 'MAE'].mean())}
    except (OSError, ValueError, KeyError, ImportError) as exc:
        raise HTTPException(503, 'Forecast artifacts unavailable or inconsistent. Retrain and deploy them together.') from exc


def predict_tci(country, travel_date, city=None):
    info = forecast_info()
    selection, origin, metrics = metadata()
    target = pd.Period(travel_date, 'M')
    h = target.ordinal - origin.ordinal
    if not 1 <= h <= 12:
        raise HTTPException(422, f'Choose a date from {info["min_date"]} to {info["max_date"]}.')
    name = selection['best_climate_ml']
    df = history()
    mask = df.Country_dest.str.strip().str.casefold().eq(country.strip().casefold())
    if city:
        mask &= df.City.str.strip().str.casefold().eq(city.strip().casefold())
    keys, features = [], []
    for key, g in df.loc[mask].groupby(KEY, sort=True):
        g = g.sort_values('date')
        y, w = g.TCI.to_numpy(float), g[WEATHER].to_numpy(float)
        m = target.month
        idx = np.flatnonzero(g.Month.to_numpy() == m)
        if len(idx) < 2 or len(g) < 25 or not np.all(np.diff(g.date.astype('int64')) == 1):
            raise HTTPException(503, 'Incomplete climate history for the selected city.')
        x = [g.City_Center_Lat.iloc[0], g.City_Center_Lon.iloc[0],
             np.sin(2*np.pi*m/12), np.cos(2*np.pi*m/12), y[idx[-1]], y[idx[-2]],
             y[idx].mean(), y[idx[-3:]].mean(), y[-1], y[-3:].mean()]
        x += list(w[idx[-1]]) + list(w[idx].mean(axis=0)) + list(w[-3:].mean(axis=0))
        keys.append(key)
        features.append(x)
    if not keys:
        raise HTTPException(404, 'No climate history for this destination.')
    X = pd.DataFrame(features, columns=FEATURES)
    try:
        bundle = load_model(name, h)
        values = bundle['model'].predict(X)
        if bundle['add_season_mean']:
            values = values + X.season_mean.to_numpy()
        values = np.clip(values, 0, 100)
        if not np.isfinite(values).all():
            raise ValueError('Non-finite model output')
        metric = metrics.loc[metrics.Model.eq(name) & metrics.Horizon_months.eq(h)].iloc[0]
        baseline = metrics.loc[metrics.Model.eq('Historical Mean') & metrics.Horizon_months.eq(h)].iloc[0]
    except Exception as exc:
        raise HTTPException(503, 'Model inference unavailable. Check model files and installed dependencies.') from exc
    reliability = {'model': name, 'origin': str(origin), 'target_month': str(target),
        'horizon_months': h, 'within_10_pct': float(metric.Within_10_pct),
        'mae': float(metric.MAE), 'error_p90': float(metric.Error_P90), 'test_n': int(metric.Test_n),
        'baseline_mae': float(baseline.MAE), 'resolution': 'monthly',
        'definition': 'Historical 2025 test share within +/-10 TCI points across all cities; not an individual probability.',
        'warning': ('The historical mean had lower MAE on the 2025 test for this lead. ' if float(baseline.MAE) < float(metric.MAE) else '') + 'Daily weather is not predicted by this model.'}
    result = pd.DataFrame(keys, columns=KEY)
    result['predicted_tci'] = values
    result['historical_mean_tci'] = X.season_mean.to_numpy()
    return result, reliability


@lru_cache(maxsize=1)
def catalog():
    # Full attraction catalog, deduplicated across historical months.
    wanted = set(KEY + ['Country','Destination Name','Latitude','Longitude','Type','Category','Sitelinks'])
    df = pd.read_csv(ROOT / 'cleaned_data' / 'tourism_final_clean.csv', usecols=lambda c: c in wanted)
    if 'Country_dest' not in df:
        df = df.rename(columns={'Country':'Country_dest'})
    for k in KEY + ['Destination Name']:
        df[k] = df[k].astype('string').str.strip()
    if 'Sitelinks' not in df:
        df['Sitelinks'] = -1
    if 'Type' not in df:
        df['Type'] = ''
    df['Sitelinks'] = pd.to_numeric(df.Sitelinks, errors='coerce').fillna(-1)
    for col in ['Latitude','Longitude']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df = df.dropna(subset=KEY + ['Destination Name'])
    df = df[df.Latitude.between(-90,90) & df.Longitude.between(-180,180)]
    df = df.drop_duplicates(KEY + ['Destination Name']).copy()
    # Same geographic algorithm and coordinate universe as the notebook.
    from sklearn.cluster import DBSCAN
    coord_key = ['Country_dest','Latitude','Longitude']
    old = pd.read_csv(ROOT / 'places_with_clusters.csv', usecols=coord_key)
    coords = pd.concat([old, df[coord_key]], ignore_index=True).dropna().drop_duplicates()
    for _, g in coords.groupby('Country_dest', sort=True):
        coords.loc[g.index, 'spatial_cluster'] = DBSCAN(eps=5/6371.0088, min_samples=3,
            metric='haversine', algorithm='ball_tree').fit_predict(np.radians(g[['Latitude','Longitude']]))
    return df.merge(coords, on=coord_key, validate='many_to_one')


def recommend(country, travel_date, city=None, category='All'):
    scores, reliability = predict_tci(country, travel_date, city)
    data = catalog()
    selected = data.merge(scores, on=KEY, validate='many_to_one')
    if selected.empty and not city:
        raise HTTPException(404, 'No matching attractions for this country.')
    if category != 'All':
        selected = selected[selected.Category.eq(category)]
    selected = selected.sort_values(['predicted_tci','Sitelinks','Destination Name'], ascending=[False,False,True])
    return selected, reliability


def tci_label(score):
    for limit, label in [(90,'Ideal'),(80,'Excellent'),(70,'Very Good'),(60,'Good'),
                         (50,'Acceptable'),(40,'Marginal'),(30,'Unfavorable'),(20,'Very Unfavorable')]:
        if score >= limit:
            return label
    return 'Extremely Unfavorable'
