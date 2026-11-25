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
        with page.expect_response(lambda r:"/website/explorer?" in r.url and "location=Cairo" in r.url and r.status==200, timeout=60000) as city_response:
            page.locator("#mapLocation").select_option("Cairo")
        assert all(p["city"]=="Cairo" for p in city_response.value.json()["points"])
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
        # Adaptive: choose an explicit future date (the whole trip fits inside the model window).
        from datetime import date, timedelta
        trip = (date.fromisoformat(target)-timedelta(days=6)).isoformat()
        if date.fromisoformat(trip)>date.today()+timedelta(days=6):
            page.goto(BASE+"/adaptive.html?city=Cairo&date="+trip)
            expect(page.locator("#adaptiveStartDate")).to_have_value(trip,timeout=60000)
            page.locator("#adaptiveDays").select_option("3")
            page.locator("#adaptiveBuild").click()
            expect(page.locator("#adaptiveResults")).to_contain_text("Provisional long-range trip",timeout=120000)
            expect(page.locator("#adaptiveResults")).to_contain_text("Historical success")
            expect(page.locator("#adaptiveDayCards")).to_contain_text(trip)
            expect(page.locator("#adaptiveDayCards")).to_contain_text("daily weather unavailable")
            expect(page.locator("#adaptiveResults")).to_contain_text("Predicted monthly weather")
            expect(page.locator("#adaptiveResults")).to_contain_text("Monthly rainfall")
            expect(page.locator("#adaptiveRecheck")).to_have_count(0)
            expect(page.locator("#adaptiveMap .leaflet-marker-icon").first).to_be_visible(timeout=60000)
            page.locator("#adaptiveDayFilter").select_option("1")
            expect(page.locator("#adaptiveLegend")).to_contain_text("Day 1")
        # Original Folium export: real browser rendering, popup, zoom, and layer toggle.
        page.goto((ROOT/"python files/forecast_results/forecast_map.html").as_uri())
        expect(page.locator(".leaflet-interactive").first).to_be_visible(timeout=60000)
        before=page.locator(".leaflet-interactive").count()
        assert before>0
        # Dense attractions overlap at the initial zoom. Select an actual exposed
        # SVG marker and click its visible centre rather than an obscured path.
        page.wait_for_function("""() => [...document.querySelectorAll('path.leaflet-interactive')].some(el => {
            const r=el.getBoundingClientRect(), x=r.left+r.width/2, y=r.top+r.height/2;
            return r.width>0 && r.height>0 && document.elementFromPoint(x,y)===el;
        })""")
        point=page.evaluate("""() => {
            for(const el of [...document.querySelectorAll('path.leaflet-interactive')].reverse()){
                const r=el.getBoundingClientRect(), x=r.left+r.width/2, y=r.top+r.height/2;
                if(r.width>0 && r.height>0 && document.elementFromPoint(x,y)===el) return {x,y};
            }
            return null;
        }""")
        assert point is not None, "No clickable Folium marker found"
        page.mouse.click(point["x"],point["y"])
        expect(page.locator(".leaflet-popup-content")).to_contain_text("TCI")
        page.locator(".leaflet-popup-close-button").click()
        page.locator(".leaflet-control-zoom-in").click()
        layer=page.locator(".leaflet-control-layers-overlays input").first
        layer.uncheck()
        expect(layer).not_to_be_checked()
        page.wait_for_function("(n) => document.querySelectorAll(\x27.leaflet-interactive\x27).length < n",arg=before)
        layer.check()
        expect(page.locator(".leaflet-interactive")).to_have_count(before)
        browser.close()
        assert not errors, errors
        print("PASS: date-based website inference and interactive Leaflet/Folium smoke tests")


if __name__=="__main__":
    main()
