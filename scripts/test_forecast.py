"""Run from repository root: python scripts/test_forecast.py.
The reference CSV is used only for offline parity testing, not by runtime inference.
"""
import sys
from pathlib import Path
from datetime import date, timedelta
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from forecast_service import predict_tci, forecast_info, catalog, history
from tci_scoring import verify_original
from weather_forecast import predict_weather, TARGETS
from itinerary_engine2 import build_day
from web_server import app
from fastapi.testclient import TestClient


class ForecastTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.reference = pd.read_csv(ROOT / "python files/forecast_results/future_predictions.csv")
        cls.info = forecast_info()

    def test_all_12_models_against_notebook(self):
        reference = self.reference
        reference = reference[reference.Model.eq(self.info['model'])]
        for (country, target), g in reference.groupby(['Country_dest','target']):
            with self.subTest(country=country, target=target):
                data, reliability = predict_tci(country, target + '-01')
                merged = g.merge(data, on=['Country_dest','City'], validate='one_to_one')
                self.assertEqual(len(g),len(merged))
                np.testing.assert_allclose(merged.Predicted_TCI, merged.predicted_tci, atol=0.0005)
                self.assertTrue(0 <= reliability['within_10_pct'] <= 100)
                self.assertEqual(reliability['horizon_months'], int(g.Horizon_months.iloc[0]))

    def test_prediction_does_not_read_reference(self):
        original = pd.read_csv
        def guard(path,*args,**kwargs):
            if str(path).endswith('future_predictions.csv'):
                raise AssertionError('Runtime must not read stored predictions')
            return original(path,*args,**kwargs)
        with patch('pandas.read_csv', side_effect=guard):
            response = self.client.get('/website/forecast',params={'country':'Egypt','city':'Cairo','travel_date':self.info['min_date']})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(len(response.json()['predictions']),1)

    def test_date_range(self):
        for target in ['2000-01-01','2099-01-01','bad']:
            r = self.client.get('/website/forecast',params={'country':'Egypt','city':'Cairo','travel_date':target})
            self.assertEqual(r.status_code,422,r.text)

    def test_planner_and_map_agree(self):
        args = {'country':'Egypt','travel_date':self.info['max_date']}
        r = self.client.get('/website/explorer',params=args)
        self.assertEqual(r.status_code,200,r.text)
        data=r.json()
        self.assertEqual(len(data['top5']),5)
        self.assertEqual(sum(p['is_top'] for p in data['points']),5)
        self.assertTrue(all(-90<=p['lat']<=90 and -180<=p['lon']<=180 for p in data['points']))
        for category in ['All','Indoor','Outdoor']:
            r=self.client.get('/website/planner',params={**args,'city':'Cairo','category':category})
            self.assertEqual(r.status_code,200,r.text)
            d=r.json()
            city_points=[p for p in data['points'] if p['city']=='Cairo']
            self.assertTrue(city_points)
            self.assertAlmostEqual(city_points[0]['tci'],d['weather']['TCI'],places=2)
            if category!='All':
                self.assertTrue(all(p['category']==category for p in d['attractions']))
        self.assertEqual(data['counts']['clustered']+data['counts']['noise'],len(data['points']))

    def test_extended_forecast_uses_separate_model_and_metrics(self):
        origin = pd.Period(self.info["origin"], "M")
        self.assertEqual(self.info["max_horizon_months"],24)
        for lead in (13,18,24):
            target = str((origin+lead).start_time.date())
            with self.subTest(lead=lead):
                response = self.client.get("/website/forecast",params={"country":"Egypt","city":"Cairo","travel_date":target})
                self.assertEqual(response.status_code,200,response.text)
                data = response.json()
                forecast = data["forecast"]
                self.assertEqual(forecast["horizon_months"],lead)
                self.assertEqual(forecast["training_mode"],"direct_long_lead_fit")
                self.assertEqual(forecast["test_n"],492)
                self.assertTrue(0<=forecast["within_10_pct"]<=100)
                self.assertTrue(0<=data["predictions"][0]["predicted_tci"]<=100)
        outside = str((origin+25).start_time.date())
        response = self.client.get("/website/forecast",params={"country":"Egypt","city":"Cairo","travel_date":outside})
        self.assertEqual(response.status_code,422)

    def test_adaptive_selected_live_dates(self):
        start = date.today()+timedelta(days=1)
        times = [(start+timedelta(days=i)).isoformat() for i in range(2)]
        body = {"city":"Cairo","start_date":start.isoformat(),"days":2,"stops":2,
                "forecast":{"time":times,"temperature_2m_max":[24,27],
                            "precipitation_sum":[0,3],"wind_speed_10m_max":[10,15]}}
        response = self.client.post("/website/adaptive/build",json=body)
        self.assertEqual(response.status_code,200,response.text)
        result = response.json()
        self.assertEqual(result["mode"],"daily")
        self.assertEqual([d["date"] for d in result["days"]],times)
        self.assertEqual(result["days"][1]["weather"]["precipitation_sum"],3)
        body["forecast"]["time"] = [(start+timedelta(days=i+1)).isoformat() for i in range(2)]
        response = self.client.post("/website/adaptive/build",json=body)
        self.assertEqual(response.status_code,422,response.text)

    def test_adaptive_future_monthly_trip(self):
        origin = pd.Period(self.info["origin"],"M")
        start = (origin+18).end_time.date()-timedelta(days=1)
        # Keep this test future-facing even as the fixture ages.
        if start <= date.today()+timedelta(days=6):
            self.skipTest("Fixture travel date no longer in long-range future")
        response = self.client.post("/website/adaptive/build",json={
            "city":"Cairo","start_date":start.isoformat(),"days":4,"stops":2})
        self.assertEqual(response.status_code,200,response.text)
        result=response.json()
        self.assertEqual(result["mode"],"monthly")
        self.assertEqual(len(result["monthly_forecasts"]),2)
        self.assertTrue(all(len(m["monthly_weather"]["variables"])==5 for m in result["monthly_forecasts"]))
        self.assertEqual([d["date"] for d in result["days"]],[(start+timedelta(days=i)).isoformat() for i in range(4)])
        self.assertTrue(all(all(v is None for v in d["weather"].values()) for d in result["days"]))
        self.assertTrue(all(d["monthly_forecast"]["training_mode"]=="direct_long_lead_fit" for d in result["days"]))
        self.assertTrue(all(d["monthly_forecast"]["target_month"]==d["date"][:7] for d in result["days"]))

    def test_tci_scoring_matches_original(self):
        self.assertTrue(all(v==0 for v in verify_original(history()).values()))

    def test_weather_variables_and_reliability(self):
        origin=pd.Period(self.info["origin"],"M")
        for lead in (1,12,24):
            target=str((origin+lead).start_time.date())
            with self.subTest(lead=lead):
                data=predict_weather("UK","London",target)
                self.assertEqual(data["horizon_months"],lead)
                self.assertEqual({v["field"] for v in data["variables"]},set(TARGETS))
                for v in data["variables"]:
                    self.assertTrue(np.isfinite(v["prediction"]))
                    self.assertTrue(0<=v["within_tolerance_pct"]<=100)
                    self.assertTrue(v["mae"]>=0 and v["baseline_mae"]>=0)
                    self.assertEqual(v["test_n"],492)

    def test_indoor_visit_slots(self):
        data=catalog()
        city=data.loc[data.City.eq("London")]
        plan=build_day(city,"indoor",set(),3)
        self.assertEqual(len(plan),3)
        self.assertEqual(set(plan.slot),{"morning","afternoon"})
        self.assertTrue(plan.Category.eq("Indoor").all())

    def test_folium_html_structure(self):
        import re
        html=(ROOT/'python files/forecast_results/forecast_map.html').read_text(encoding='utf-8')
        self.assertGreater(len(re.findall(r'L.circleMarker\(',html)),0)
        self.assertEqual(len(re.findall(r'L.circleMarker\(',html)),len(re.findall(r'L.popup\(',html)))
        self.assertIn('L.control.layers(',html)
        self.assertIn('.fitBounds(',html)


if __name__ == '__main__':
    unittest.main(verbosity=2)
