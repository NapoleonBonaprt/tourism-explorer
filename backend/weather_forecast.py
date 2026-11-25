"""Direct monthly weather forecasts with per-variable out-of-sample reliability.

Uses only observations at or before each forecast origin. The TCI predictor remains
separate. No daily values are fabricated from monthly estimates.
"""
from functools import lru_cache
from threading import Lock
from pathlib import Path
import hashlib
import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from fastapi import HTTPException
from backend.forecast_service import history, KEY, WEATHER, MAX_HORIZON

TARGETS = {
    "Temp_Mean": ("Mean temperature", "°C", 2.0, -100., 65.),
    "Precip_Total_mm": ("Monthly rainfall", "mm/month", 20., 0., np.inf),
    "Wind_Mean_ms": ("Mean wind speed", "m/s", 1., 0., np.inf),
    "RH_Mean": ("Mean relative humidity", "%", 10., 0., 100.),
    "Sunshine_h_per_day": ("Mean daily sunshine", "h/day", 1., 0., 24.),
}
COLS=list(TARGETS)
INDICES=[WEATHER.index(c) for c in COLS]
TOL=np.array([v[2] for v in TARGETS.values()])
LOW=np.array([v[3] for v in TARGETS.values()])
HIGH=np.array([v[4] for v in TARGETS.values()])
LOCK=Lock()
ROOT=Path(__file__).resolve().parents[1]
ARTIFACTS=ROOT/'python files'/'monthly_weather_results'
SCHEMA_VERSION=1


def features(w, months, lat, lon, i, target_month):
    idx=np.flatnonzero(months[:i+1]==target_month)
    if len(idx)<2 or i<24:
        return None
    base=w[idx].mean(axis=0)
    x=np.r_[lat,lon,np.sin(2*np.pi*target_month/12),np.cos(2*np.pi*target_month/12),
            w[idx[-1]],w[idx[-2]],base,w[idx[-3:]].mean(axis=0),
            w[i],w[i-2:i+1].mean(axis=0)]
    return x,base[INDICES]


@lru_cache(maxsize=24)
def train_weather(h):
    if not 1<=h<=MAX_HORIZON:
        raise ValueError("Invalid weather forecast lead")
    xs,ys,bases,origins,targets=[],[],[],[],[]
    for _,g in history().groupby(KEY,sort=True):
        g=g.sort_values("date")
        w=g[WEATHER].to_numpy(float); months=g.Month.to_numpy()
        dates=g.date.to_list()
        if not np.all(np.diff(g.date.astype("int64"))==1):
            raise ValueError("Gap in observed weather")
        for i in range(24,len(g)-h):
            row=features(w,months,g.City_Center_Lat.iloc[0],g.City_Center_Lon.iloc[0],i,dates[i+h].month)
            if row is None: continue
            x,b=row
            xs.append(x);bases.append(b);ys.append(w[i+h,INDICES])
            origins.append(dates[i]);targets.append(dates[i+h])
    X,y,B=np.array(xs),np.array(ys),np.array(bases)
    origins,targets=pd.PeriodIndex(origins,freq="M"),pd.PeriodIndex(targets,freq="M")
    # Same fixed years as the TCI experiment, but purge overlapping labels
    # for every horizon, including 13–24 months.
    val=targets.year==2023; test=targets.year==2025
    tv=targets<origins[val].min(); tt=targets<origins[test].min()
    if not (tv.any() and tt.any() and val.any() and test.any()):
        raise ValueError("Insufficient weather history")
    # Choose one alpha per target, using validation only. Historical monthly
    # climatology is reported as a benchmark, never silently substituted.
    alphas=[10.,100.,1000.]
    losses=[]
    for alpha in alphas:
        model=make_pipeline(StandardScaler(),Ridge(alpha=alpha))
        model.fit(X[tv],(y-B)[tv])
        pred=np.clip(B[val]+model.predict(X[val]),LOW,HIGH)
        losses.append(np.abs(y[val]-pred).mean(axis=0))
    selected=np.argmin(np.array(losses),axis=0)
    models=[]; metrics=[]
    for j,col in enumerate(COLS):
        alpha=alphas[selected[j]]
        eval_model=make_pipeline(StandardScaler(),Ridge(alpha=alpha))
        eval_model.fit(X[tt],(y-B)[tt,j])
        pred=np.clip(B[test,j]+eval_model.predict(X[test]),LOW[j],HIGH[j])
        err=np.abs(y[test,j]-pred)
        baseline_err=np.abs(y[test,j]-B[test,j])
        final=make_pipeline(StandardScaler(),Ridge(alpha=alpha))
        final.fit(X,(y-B)[:,j]);models.append(final)
        metrics.append(dict(field=col,model="Residual Ridge",alpha=alpha,
                            mae=float(err.mean()),rmse=float(np.sqrt(np.mean(err**2))),
                            within_tolerance_pct=float(100*np.mean(err<=TOL[j])),
                            error_p90=float(np.quantile(err,.9)),baseline_mae=float(baseline_err.mean()),
                            test_n=int(test.sum())))
    return models,metrics


@lru_cache(maxsize=1)
def history_fingerprint():
    return hashlib.sha256((ROOT/'cleaned_data'/'city_month_features.csv').read_bytes()).hexdigest()


@lru_cache(maxsize=24)
def weather_bundle(h):
    path=ARTIFACTS/f'weather_{h:02d}m.joblib'
    if path.is_file():
        bundle=joblib.load(path)
        if (bundle.get('schema')==SCHEMA_VERSION and bundle.get('horizon')==h
                and bundle.get('history_sha256')==history_fingerprint()):
            return bundle['models'],bundle['metrics']
    return train_weather(h)


def predict_weather(country,city,travel_date):
    df=history()
    target=pd.Period(travel_date,"M"); origin=df.date.max(); h=target.ordinal-origin.ordinal
    if not 1<=h<=MAX_HORIZON:
        raise HTTPException(422,"Monthly weather date is outside the trained forecast window.")
    g=df[df.Country_dest.str.strip().str.casefold().eq(country.strip().casefold()) &
         df.City.str.strip().str.casefold().eq(city.strip().casefold())].sort_values("date")
    if g.empty: raise HTTPException(404,"No observations for this city.")
    try:
        with LOCK:
            models,metrics=weather_bundle(h)
        row=features(g[WEATHER].to_numpy(float),g.Month.to_numpy(),g.City_Center_Lat.iloc[0],
                     g.City_Center_Lon.iloc[0],len(g)-1,target.month)
        x,b=row
        result=[]
        for j,(col,model,metric) in enumerate(zip(COLS,models,metrics)):
            label,unit,tolerance,_,_=TARGETS[col]
            p=float(np.clip(b[j]+model.predict(x.reshape(1,-1))[0],LOW[j],HIGH[j]))
            if not np.isfinite(p): raise ValueError("Nonfinite weather forecast")
            result.append({**metric,"label":label,"unit":unit,"tolerance":tolerance,
                           "prediction":p,"historical_mean":float(b[j])})
    except Exception as exc:
        raise HTTPException(503,"Monthly weather model unavailable.") from exc
    return {"target_month":str(target),"origin":str(origin),"horizon_months":h,
            "variables":result,"resolution":"monthly","test_year":2025,
            "definition":"Historical test share within each stated tolerance, across all cities; not an individual probability."}
