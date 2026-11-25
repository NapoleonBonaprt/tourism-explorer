"""Browser smoke test for the real Leaflet website and exported Folium map.

Run with the website at http://127.0.0.1:8000:
  python -m pip install playwright
  python -m playwright install chromium
  python scripts/test_forecast_browser.py
An internet connection is required for the Leaflet/Folium CDN assets.
"""
from pathlib import Path
import os
import re
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
BASE = os.getenv("WANDERCLIMATE_TEST_URL","http://127.0.0.1:8000").rstrip("/")


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width":1440,"height":1000})
        errors=[]
        page.on("pageerror",lambda e:errors.append(str(e)))
        info=page.request.get(BASE+"/website/forecast-info").json()
        target=info["max_date"]
        # Explorer: country/city, date, map search, layer controls and marker popups.
        page.goto(BASE+"/explorer.html?country=Egypt&date="+target)
        expect(page.locator("#mapCountry")).to_have_value("Egypt",timeout=60000)
        expect(page.locator("#explorerResults")).to_contain_text("Monthly ML forecast reliability",timeout=60000)
        expect(page.locator("#explorerMap .leaflet-interactive").first).to_be_visible(timeout=60000)
        expect(page.locator("#visibleAttractions")).to_contain_text(re.compile(r"Showing [1-9]\d* of [1-9]\d* attractions"))
        page.locator("#hideMapClusters").click()
        expect(page.locator("#visibleAttractions")).to_contain_text("Showing 0 of")
        page.locator("#showMapClusters").click()
        page.locator("#mapTopOnly").check()
        expect(page.locator("#visibleAttractions")).to_contain_text("Showing 5 of")
        page.locator("#mapTopOnly").uncheck()
        page.locator("#attractionSearch").fill("Cairo")
        expect(page.locator("#mapSearchMatches .map-result").first).to_be_visible()
        page.locator("#mapSearchMatches .map-result").first.click()
        expect(page.locator(".leaflet-popup-content")).to_contain_text("Predicted monthly TCI")
        expect(page.locator(".leaflet-popup-content")).to_contain_text("Historical success")
        expect(page.locator(".leaflet-popup-content a")).to_have_attribute("href",re.compile(r"https://www.google.com/maps/"))
        page.locator("#attractionSearch").fill("")
        page.locator("#mapLocation").select_option("Cairo")
        expect(page.locator("#explorerResults h2").first).to_contain_text("Monthly ML forecast reliability",timeout=60000)
        expect(page.locator("#explorerMap .leaflet-interactive").first).to_be_visible(timeout=60000)
        # Change date and wait for the corresponding API response and new result.
        with page.expect_response(lambda r:"/website/explorer?" in r.url and r.status==200) as response:
            page.locator("#mapMonth").fill(info["min_date"])
        assert response.value.json()["forecast"]["horizon_months"]==1
        expect(page.locator("#explorerResults")).to_contain_text("1 months",timeout=60000)
        # Planner and climate forecast panels.
        page.goto(BASE+"/planner.html?country=Egypt&city=Cairo&date="+target)
        expect(page.locator("#plannerResults")).to_contain_text("Predicted monthly TCI",timeout=60000)
        expect(page.locator("#plannerResults")).to_contain_text("Historical success")
        with page.expect_response(lambda r:"/website/planner?" in r.url and r.status==200) as response:
            page.locator("#planCategory").select_option("Indoor")
        assert all(r["category"]=="Indoor" for r in response.value.json()["attractions"])
        page.goto(BASE+"/climate.html?country=Egypt&city=Cairo&date="+target)
        expect(page.locator("#climateForecastResult")).to_contain_text("Predicted monthly TCI",timeout=60000)
        expect(page.locator("#climateResults")).to_contain_text("Historical",timeout=60000,ignore_case=True)
        # Original Folium export: real browser rendering, popup, zoom, and layer toggle.
        page.goto((ROOT/"python files/forecast_results/forecast_map.html").as_uri())
        expect(page.locator(".leaflet-interactive").first).to_be_visible(timeout=60000)
        before=page.locator(".leaflet-interactive").count()
        assert before>0
        page.locator(".leaflet-interactive").first.click()
        expect(page.locator(".leaflet-popup-content")).to_contain_text("TCI")
        page.locator(".leaflet-popup-close-button").click()
        page.locator(".leaflet-control-zoom-in").click()
        layer=page.locator(".leaflet-control-layers-overlays input").first
        layer.uncheck()
        expect(layer).not_to_be_checked()
        assert page.locator(".leaflet-interactive").count()<before
        layer.check()
        assert page.locator(".leaflet-interactive").count()==before
        browser.close()
        assert not errors, errors
        print("PASS: date-based website inference and interactive Leaflet/Folium smoke tests")


if __name__=="__main__":
    main()
