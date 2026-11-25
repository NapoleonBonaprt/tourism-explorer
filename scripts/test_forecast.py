"""Run from repository root: python scripts/test_forecast.py.
The reference CSV is used only for offline parity testing, not by runtime inference.
"""
import sys
from pathlib import Path
from datetime import date
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from forecast_service import predict_tci, forecast_info, catalog
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

    def test_folium_html_structure(self):
        import re
        html=(ROOT/'python files/forecast_results/forecast_map.html').read_text(encoding='utf-8')
        self.assertGreater(len(re.findall(r'L.circleMarker\(',html)),0)
        self.assertEqual(len(re.findall(r'L.circleMarker\(',html)),len(re.findall(r'L.popup\(',html)))
        self.assertIn('L.control.layers(',html)
        self.assertIn('.fitBounds(',html)


if __name__ == '__main__':
    unittest.main(verbosity=2)
