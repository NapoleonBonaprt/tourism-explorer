"""Train all 24 direct monthly weather horizons and export model/metric artifacts.
Run from repository root: python scripts/train_weather_models.py
"""
from pathlib import Path
import sys
import json
import joblib
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from weather_forecast import train_weather, history_fingerprint, SCHEMA_VERSION, ARTIFACTS, MAX_HORIZON
from forecast_service import history

def main():
    ARTIFACTS.mkdir(parents=True,exist_ok=True)
    origin=str(history().date.max())
    fingerprint=history_fingerprint()
    rows=[]
    for h in range(1,MAX_HORIZON+1):
        models,metrics=train_weather(h)
        bundle=dict(models=models,metrics=metrics,horizon=h,origin=origin,
                    schema=SCHEMA_VERSION,history_sha256=fingerprint)
        temp=ARTIFACTS/f'weather_{h:02d}m.tmp'
        joblib.dump(bundle,temp)
        temp.replace(ARTIFACTS/f'weather_{h:02d}m.joblib')
        rows.extend(dict(horizon_months=h,origin=origin,**m) for m in metrics)
        print(f'Trained {h}/{MAX_HORIZON} months',flush=True)
    metrics=pd.DataFrame(rows)
    metrics.to_csv(ARTIFACTS/'weather_horizon_metrics.csv',index=False)
    summary=metrics.groupby('field',as_index=False).agg(mae=('mae','mean'),rmse=('rmse','mean'),
             within_tolerance_pct=('within_tolerance_pct','mean'),baseline_mae=('baseline_mae','mean'))
    summary.to_csv(ARTIFACTS/'weather_model_summary.csv',index=False)
    (ARTIFACTS/'selection.json').write_text(json.dumps({'origin':origin,'model':'Residual Ridge',
         'horizons':MAX_HORIZON,'test_year':2025,'history_sha256':fingerprint,
         'selection':'Per-variable alpha selected only on 2023 validation with purged training'},indent=2))
    print(summary.to_string(index=False))

if __name__=='__main__':
    main()
