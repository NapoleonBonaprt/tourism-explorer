"""End-to-end checks against a running WanderClimate website.

Run after starting web_server:app on port 8000. Uses real API/model data.
Daily weather responses are controlled fixtures, so weather/storm assertions
are deterministic; the external provider probe is reported separately.
"""
from datetime import date, timedelta
from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import math
import os
import re
import unittest
import httpx
from pypdf import PdfReader
from playwright.sync_api import sync_playwright, expect

BASE=os.getenv("WANDERCLIMATE_TEST_URL","http://127.0.0.1:8000").rstrip("/")
OUT=Path("site-test-artifacts")
OUT.mkdir(exist_ok=True)
PAGES=["index.html","overview.html","climate.html","explorer.html","planner.html","adaptive.html"]

def pdf_text(raw):
    assert raw.startswith(b"%PDF-"), "Not a PDF"
    doc=PdfReader(BytesIO(raw))
    assert len(doc.pages)>0
    return " ".join(" ".join(p.extract_text() or "" for p in doc.pages).split())

class API(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.http=httpx.Client(base_url=BASE,timeout=90,follow_redirects=True)
        cls.info=cls.http.get("/website/forecast-info").json()
        cls.filters=cls.http.get("/website/filters").json()

    @classmethod
    def tearDownClass(cls):
        cls.http.close()

    def get(self,path,params=None,status=200):
        r=self.http.get(path,params=params)
        self.assertEqual(r.status_code,status,r.text[:1000])
        return r

    def post(self,path,body,status=200):
        r=self.http.post(path,json=body)
        self.assertEqual(r.status_code,status,r.text[:1000])
        return r

    def test_01_public_pages_assets_and_private_files(self):
        self.assertEqual(self.get("/health").json()["status"],"ok")
        for page in ["/",*["/"+p for p in PAGES]]:
            with self.subTest(page=page):
                self.assertIn("text/html",self.get(page).headers["content-type"])
        for path in ["/dashboard-site.js","/dashboard-site.css","/theme.js",
                     "/discovery-map.js","/landing.css","/trip-pdf.js",
                     "/experience-v4.js","/assets/wanderclimate-wordmark.webp"]:
            with self.subTest(asset=path):
                self.assertGreater(len(self.get(path).content),50)
        for path in ["/website_api.py","/forecast_service.py","/cleaned_data/city_month_features.csv",
                     "/python%20files/EDA_Notebook.ipynb","/.git/config"]:
            self.get(path,status=404)

    def test_02_directory_overview_and_legacy_endpoints(self):
        cities=self.get("/cities").json()
        self.assertGreater(len(cities),30)
        overview=self.get("/website/overview").json()
        self.assertEqual(overview["metrics"]["cities"],len({x["city"] for x in self.filters["climate_cities"]}))
        self.assertGreater(overview["metrics"]["destinations"],0)
        self.assertTrue(0<=overview["metrics"]["average_tci"]<=100)
        self.assertTrue(overview["categories"] and overview["country_summary"])
        coords=self.get("/website/destination-coordinates").json()["coordinates"]
        self.assertIn("Cairo",coords)
        for point in coords.values():
            self.assertTrue(-90<=point["latitude"]<=90 and -180<=point["longitude"]<=180)
        for path in ["/overview/summary","/overview/countries","/climate/city/Cairo","/attractions/country/Egypt"]:
            with self.subTest(path=path):
                self.assertTrue(self.get(path).json())
        rows=self.get("/climate/search",{"city":" cairo ","country":"Egypt"}).json()
        self.assertTrue(rows)
        self.assertEqual({r["City"] for r in rows},{"Cairo"})
        self.get("/climate/search",{"city":"NotARealCity123"},404)

    def test_03_every_city_forecasts_and_history(self):
        target=self.info["max_date"]
        locations=self.filters["climate_cities"]
        self.assertGreaterEqual(len(locations),41)
        for loc in locations:
            with self.subTest(**loc):
                history=self.get("/website/climate",loc).json()
                self.assertEqual(len(history["monthly"]),12)
                data=self.get("/website/forecast",{**loc,"travel_date":target}).json()
                self.assertEqual(len(data["predictions"]),1)
                self.assertTrue(0<=data["predictions"][0]["predicted_tci"]<=100)
                self.assertEqual(data["forecast"]["target_month"],target[:7])
                variables=data["monthly_weather"]["variables"]
                self.assertEqual(len(variables),5)
                for v in variables:
                    self.assertTrue(math.isfinite(v["prediction"]))
                    self.assertTrue(0<=v["within_tolerance_pct"]<=100)
        print(f"PASS: {len(locations)} cities, historical data and long-lead forecasts",flush=True)

    def test_04_country_maps_and_planner(self):
        target=self.info["max_date"]
        for country in self.filters["map_countries"]:
            with self.subTest(country=country):
                result=self.get("/website/explorer",{"country":country,"travel_date":target}).json()
                self.assertTrue(result["points"])
                self.assertEqual(len(result["top5"]),min(5,len(result["points"])))
                self.assertEqual(sum(p["is_top"] for p in result["points"]),len(result["top5"]))
                self.assertEqual(sum(result["counts"][k] for k in ["clustered","noise","unknown"]),len(result["points"]))
        for city,country in [("Cairo","Egypt"),("London","UK"),("Paris","France")]:
            for category in ["All","Indoor","Outdoor"]:
                with self.subTest(city=city,category=category):
                    d=self.get("/website/planner",dict(city=city,country=country,travel_date=target,category=category)).json()
                    self.assertEqual(len(d["monthly_weather"]["variables"]),5)
                    self.assertLessEqual(len(d["attractions"]),10)
                    self.assertTrue(all(category=="All" or a["category"]==category for a in d["attractions"]))
        print(f"PASS: {len(self.filters['map_countries'])} country maps",flush=True)

    def test_05_invalid_input(self):
        self.get("/website/climate",dict(country="Egypt",city="UnknownCity123"),404)
        self.get("/website/forecast",dict(country="Egypt",city="Cairo",travel_date="2099-01-01"),422)
        self.get("/website/forecast",dict(country="Egypt",city="Cairo",travel_date="bad-date"),422)
        self.get("/website/planner",dict(country="Egypt",city="Cairo",category="BadCategory"),422)
        self.get("/website/explorer",dict(country="Egypt",month=13),422)
        self.post("/website/adaptive/build",dict(city="Cairo",days=8),422)
        self.post("/website/adaptive/build",dict(city="Cairo",days=3,start_date="2000-01-01"),422)
        self.post("/website/adaptive/export-pdf",dict(city="Cairo",days=[]),422)

    def test_07_destination_cover_images(self):
        import hashlib
        from PIL import Image
        hashes = {}
        for loc in self.filters["climate_cities"]:
            with self.subTest(city=loc["city"]):
                response = self.get("/website/guide-cover",{"city":loc["city"]})
                self.assertEqual(response.headers["content-type"],"image/jpeg")
                self.assertEqual(response.headers["x-guide-cover"],"photo")
                with Image.open(BytesIO(response.content)) as img:
                    img.load()
                    self.assertEqual(img.size,(900,560))
                digest = hashlib.sha256(response.content).hexdigest()
                hashes.setdefault(digest, []).append(loc["city"])
        duplicates = [set(cities) for cities in hashes.values() if len(cities) > 1]
        self.assertEqual(duplicates, [{"Madrid", "Barcelona"}])
        self.assertEqual(len(hashes), len(self.filters["climate_cities"]) - 1)
        self.get("/website/guide-cover",{"city":"../../etc/passwd"},404)
        self.assertEqual(self.get("/website/guide-cover",{"city":"London"}).headers["x-guide-cover"],"photo")
        self.assertEqual(self.get("/website/guide-cover",{"city":"Madrid"}).headers["x-guide-cover"],"photo")
        self.assertEqual(self.get("/website/guide-cover",{"city":"Barcelona"}).headers["x-guide-cover"],"photo")

    def test_06_monthly_pdf_content(self):
        start=date.fromisoformat(self.info["max_date"]).replace(day=1)-timedelta(days=2)
        if start<=date.today()+timedelta(days=6):
            self.skipTest("Forecast fixture expired")
        plan=self.post("/website/adaptive/build",dict(city="London",start_date=start.isoformat(),days=4,stops=3)).json()
        raw=self.post("/website/adaptive/export-pdf",plan)
        self.assertIn("application/pdf",raw.headers["content-type"])
        content=pdf_text(raw.content).lower()
        for term in ["discover london",start.strftime("%d %b %Y").lstrip("0").lower(),"what to expect","monthly estimates","morning","afternoon"]:
            self.assertIn(term,content)
        for day in plan["days"]:
            for stop in day["stops"]:
                self.assertIn(" ".join(stop["name"].lower().split()),content)
        for term in ["historical success","predicted monthly tci","mae","rmse","coordinates:"]:
            self.assertNotIn(term,content)
        doc=PdfReader(BytesIO(raw.content))
        self.assertGreater(len(doc.pages[0].images),0)
        self.assertGreaterEqual(sum(len(p.get("/Annots",[])) for p in doc.pages),sum(len(d["stops"]) for d in plan["days"]))
        self.assertEqual(len(plan["monthly_forecasts"]),2)
        assert_daily_monthly_outlooks(self,raw.content,plan)
        (OUT/"monthly-server.pdf").write_bytes(raw.content)

def assert_daily_monthly_outlooks(case, raw, plan):
    # Content is emitted day-by-day, with a monthly outlook inside every card.
    content=pdf_text(raw).lower()
    case.assertEqual(content.count("what to expect"),len(plan["days"]))
    blocks=re.split(r"\bday\s+(\d+)\b",content)
    case.assertEqual(len(blocks),1+2*len(plan["days"]))
    forecasts={f["target_month"]:f for f in plan["monthly_forecasts"]}
    for i,day in enumerate(plan["days"]):
        case.assertEqual(int(blocks[2*i+1]),day["number"])
        block=blocks[2*i+2]
        case.assertIn("what to expect",block)
        case.assertIn(date.fromisoformat(day["date"]).strftime("%B %Y").lower(),block)
        f=forecasts[day["date"][:7]]
        temp=next(v["prediction"] for v in f["monthly_weather"]["variables"] if v["label"]=="Mean temperature")
        case.assertIn(f"around {math.floor(temp+.5)}",block)
        case.assertIn("monthly",block)


class Browser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw=sync_playwright().start()
        cls.browser=cls.pw.chromium.launch(headless=True)
        cls.info=httpx.get(BASE+"/website/forecast-info").json()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()

    def setUp(self):
        self.context=self.browser.new_context(viewport={"width":1440,"height":1000},timezone_id="UTC",accept_downloads=True)
        self.page=self.context.new_page()
        self.errors=[]
        self.page.on("pageerror",lambda e:self.errors.append(str(e)))
        self.page.set_default_timeout(30000)
        self.page.set_default_navigation_timeout(60000)

    def tearDown(self):
        try:
            self.page.screenshot(path=str(OUT/(self._testMethodName+".png")),full_page=True,timeout=15000)
        finally:
            self.context.close()
        self.assertFalse(self.errors,self.errors)

    def goto(self,path):
        response=self.page.goto(BASE+path,wait_until="domcontentloaded")
        self.assertEqual(response.status,200)

    def test_01_home_search_map_and_months(self):
        p=self.page
        self.goto("/")
        expect(p.locator("#api")).to_contain_text("server online")
        expect(p.locator("#browseCount")).to_contain_text(re.compile(r"Showing [3-9]\d of [3-9]\d destinations"))
        p.locator("#browseQuery").scroll_into_view_if_needed()
        p.locator("#browseQuery").fill("Cairo")
        expect(p.locator("#browseGrid .browse-place")).to_have_count(1)
        expect(p.locator("#discoveryMap .wc-map-pin")).to_have_count(1,timeout=60000)
        p.locator("#discoveryMap .wc-map-pin").click()
        expect(p.locator(".discovery-popup")).to_contain_text("Cairo")
        p.get_by_role("button",name="View climate details").click()
        expect(p.locator("#rTitle")).to_contain_text("Cairo")
        expect(p.locator("#out .mt")).to_have_count(12)
        expect(p.locator("#rSub")).to_contain_text("Historical monthly averages")
        p.locator("#out .mt[data-m='6']").click()
        expect(p.locator("#out .detail h3")).to_have_text("July")
        expect(p.locator("#out .mt[data-m='6']")).to_have_attribute("aria-pressed","true")
        c=p.locator("#out .fact strong").first.inner_text()
        p.locator("[data-unit='F']").click()
        self.assertNotEqual(c,p.locator("#out .fact strong").first.inner_text())
        p.locator("[data-unit='C']").click()
        self.assertEqual(c,p.locator("#out .fact strong").first.inner_text())
        p.locator(".logo").click()
        expect(p.locator("body")).to_have_class(re.compile("is-home"))
        p.locator("#city").fill("Egypt")
        p.locator("#city").press("Enter")
        expect(p.locator("#out")).to_contain_text("is a country")
        p.locator("#out .country-option").filter(has_text="Cairo").click()
        expect(p.locator("#out .mt")).to_have_count(12)
        p.locator("#city").fill("NotARealCity123")
        p.locator("#city").press("Enter")
        expect(p.locator("#out")).to_contain_text("No matching city")
        p.locator(".logo").click()
        p.locator("#browseQuery").fill("NotARealCity123")
        expect(p.locator("#browseGrid")).to_contain_text("No destinations match")
        p.locator("#discoveryReset").click()
        expect(p.locator("#browseQuery")).to_have_value("")
        expect(p.locator("#browseGrid .browse-place").first).to_be_visible()

    def test_02_overview_navigation_theme_and_mobile(self):
        p=self.page
        self.goto("/overview.html")
        expect(p.locator("#pageContent")).to_contain_text("Total Destinations")
        expect(p.locator("#overviewChart")).to_be_visible()
        p.wait_for_function("window.Chart && Chart.getChart(document.querySelector('#overviewChart'))")
        initial=p.locator("html").get_attribute("data-theme")
        p.locator("[data-theme-toggle]").click()
        changed="dark" if initial=="light" else "light"
        expect(p.locator("html")).to_have_attribute("data-theme",changed)
        p.reload(wait_until="domcontentloaded")
        expect(p.locator("html")).to_have_attribute("data-theme",changed)
        expect(p.locator("#siteNav a[aria-current='page']")).to_have_attribute("href","overview.html")
        for path in PAGES[2:]:
            expect(p.locator("#siteNav a[href='"+path+"']")).to_be_visible()
        p.set_viewport_size({"width":390,"height":844})
        expect(p.locator("#navToggle")).to_be_visible()
        p.locator("#navToggle").click()
        expect(p.locator("#navToggle")).to_have_attribute("aria-expanded","true")
        p.keyboard.press("Escape")
        expect(p.locator("#navToggle")).to_have_attribute("aria-expanded","false")
        p.locator("#navToggle").click()
        p.locator("#siteNav a[href='climate.html']").click()
        expect(p).to_have_url(re.compile(r"/climate\.html"))
        expect(p.locator("html")).to_have_attribute("data-theme",changed)
        expect(p.locator("#climateCountry")).to_be_visible()
        expect(p.locator("#navToggle")).to_have_attribute("aria-expanded","false")
        self.goto("/")
        expect(p.locator("#homeMenuToggle")).to_be_visible()
        p.locator("#homeMenuToggle").click()
        expect(p.locator("#homeMenuToggle")).to_have_attribute("aria-expanded","true")
        p.keyboard.press("Escape")
        expect(p.locator("#homeMenuToggle")).to_have_attribute("aria-expanded","false")

    def test_03_climate_and_planner_interactions(self):
        p=self.page
        target=self.info["max_date"]
        self.goto("/climate.html?country=Egypt&city=Cairo&date="+target)
        expect(p.locator("#climateResults")).to_contain_text("Cairo",timeout=60000)
        expect(p.locator("#climateForecastResult")).to_contain_text("Predicted monthly weather",timeout=60000)
        p.wait_for_function("window.Chart && Chart.getChart(document.querySelector('#climateTCI'))")
        expect(p.locator("#climateRain")).to_be_visible()
        p.locator("#climateCountry").select_option("UK")
        expect(p.locator("#climateCity")).to_have_value("London")
        expect(p.locator("#climateResults")).to_contain_text("London",timeout=60000)
        expect(p.locator("#climateForecastResult")).to_contain_text("Predicted monthly weather",timeout=60000)
        p.locator("#climateForecastResult summary").filter(has_text="Model reliability").click()
        expect(p.locator("#climateForecastResult table")).to_be_visible()
        self.goto("/planner.html?country=Egypt&city=Cairo&date="+target)
        expect(p.locator("#plannerResults")).to_contain_text("Predicted monthly weather",timeout=60000)
        p.locator("#planCategory").select_option("Indoor")
        expect(p.locator("#plannerResults .attraction-card").first).to_be_visible(timeout=60000)
        p.locator("#plannerResults .attraction-card summary").first.click()
        expect(p.locator("#plannerResults .attraction-card .inner").first).to_be_visible()
        expect(p.locator("#plannerResults .attraction-card .inner").first).to_contain_text("Coordinates")
        p.locator("#planCategory").select_option("Outdoor")
        expect(p.locator("#plannerResults .attraction-card summary").first).to_contain_text("Outdoor",timeout=60000)

    def fixture_weather(self,route):
        self.weather_calls+=1
        q=parse_qs(urlparse(route.request.url).query)
        start=date.fromisoformat(q["start_date"][0])
        end=date.fromisoformat(q["end_date"][0])
        dates=[(start+timedelta(days=i)).isoformat() for i in range((end-start).days+1)]
        n=len(dates)
        route.fulfill(status=200,headers={"Access-Control-Allow-Origin":"*"},json={"daily":{
            "time":dates,"temperature_2m_max":[24]*n,
            "precipitation_sum":[0]*n,"wind_speed_10m_max":[10]*n}})

    def test_04_daily_replanning_and_pdf_download(self):
        p=self.page
        self.weather_calls=0
        p.route("https://api.open-meteo.com/v1/forecast**",self.fixture_weather)
        start=(date.today()+timedelta(days=1)).isoformat()
        self.goto("/adaptive.html?city=Cairo&date="+start)
        expect(p.locator("#adaptiveStartDate")).to_have_value(start,timeout=60000)
        p.locator("#adaptiveDays").select_option("3")
        p.locator("#adaptiveStops").select_option("3")
        with p.expect_response(lambda r:"/website/adaptive/build" in r.url and r.request.method=="POST") as built:
            p.locator("#adaptiveBuild").click()
        self.assertEqual(built.value.status,200)
        original=built.value.json()
        self.assertEqual(original["mode"],"daily")
        expect(p.locator("#adaptiveDayCards .day-card")).to_have_count(3)
        expect(p.locator("#adaptiveMap .route-marker").first).to_be_visible()
        p.locator("#adaptiveDayFilter").select_option("2")
        expect(p.locator("#adaptiveLegend")).to_have_text("Day 2")
        p.locator("#adaptiveRecheck").click()
        expect(p.locator("#adaptiveChanges")).to_contain_text("Forecast unchanged")
        self.assertEqual(self.weather_calls,2,"Re-check must request fresh weather")
        p.locator("#simulateStorm").check()
        expect(p.locator("#stormDate")).to_be_visible()
        p.locator("#stormDate").select_option(start)
        p.locator("#stormRain").fill("8")
        with p.expect_response(lambda r:"/website/adaptive/recheck" in r.url and r.request.method=="POST") as replanned:
            p.locator("#adaptiveRecheck").click()
        self.assertEqual(replanned.value.status,200)
        updated=replanned.value.json()
        self.assertEqual(updated["days"][0]["day_type"],"indoor")
        self.assertEqual(updated["days"][0]["weather"]["precipitation_sum"],8)
        self.assertEqual(updated["days"][1]["stops"],original["days"][1]["stops"])
        self.assertEqual(self.weather_calls,3)
        expect(p.locator("#adaptiveChanges")).to_contain_text("re-planned")
        expect(p.locator("#adaptiveDayCards .day-card").first).to_contain_text("indoor")
        # Test the browser's actual downloadable PDF and server fallback.
        p.wait_for_function("window.WanderClimatePDF && WanderClimatePDF.available()")
        with p.expect_download() as d:
            p.locator("#downloadItineraryPdf").click()
        raw=Path(d.value.path()).read_bytes()
        content=pdf_text(raw)
        self.assertIn(date.fromisoformat(start).strftime("%d %b %Y").lstrip("0"),content)
        self.assertIn("Cairo",content)
        self.assertGreater(len(PdfReader(BytesIO(raw)).pages[0].images),0)
        (OUT/"daily-browser.pdf").write_bytes(raw)
        p.evaluate("window.WanderClimatePDF={available:()=>false}")
        with p.expect_download() as fallback:
            p.locator("#downloadItineraryPdf").click()
        raw2=Path(fallback.value.path()).read_bytes()
        self.assertIn(date.fromisoformat(start).strftime("%d %b %Y").lstrip("0"),pdf_text(raw2))
        (OUT/"daily-fallback.pdf").write_bytes(raw2)
        p.evaluate("window.print=()=>{window.__printCalled=true}")
        p.locator("#printItinerary").click()
        self.assertTrue(p.evaluate("window.__printCalled===true"))

    def test_05_monthly_download_and_date_validation(self):
        p=self.page
        end=self.info["max_date"]
        start=(date.fromisoformat(end).replace(day=1)-timedelta(days=2)).isoformat()
        if date.fromisoformat(start)<=date.today()+timedelta(days=6):
            self.skipTest("Forecast fixture expired")
        self.goto("/adaptive.html?city=London&date="+start)
        expect(p.locator("#adaptiveStartDate")).to_have_value(start,timeout=60000)
        p.locator("#adaptiveDays").select_option("4")
        with p.expect_response(lambda r:"/website/adaptive/build" in r.url and r.request.method=="POST") as built:
            p.locator("#adaptiveBuild").click()
        plan=built.value.json()
        expect(p.locator("#adaptiveResults")).to_contain_text("Predicted monthly weather",timeout=120000)
        expect(p.locator("#adaptiveDayCards .day-card")).to_have_count(4)
        expect(p.locator("#adaptiveRecheck")).to_have_count(0)
        p.wait_for_function("window.WanderClimatePDF && WanderClimatePDF.available()")
        with p.expect_download() as download:
            p.locator("#downloadItineraryPdf").click()
        raw=Path(download.value.path()).read_bytes()
        content=pdf_text(raw).lower()
        self.assertIn("what to expect",content)
        self.assertIn("monthly estimates",content)
        self.assertIn(date.fromisoformat(start).strftime("%d %b %Y").lstrip("0").lower(),content)
        for term in ["historical success","predicted monthly tci","mae","rmse","coordinates:"]:
            self.assertNotIn(term,content)
        self.assertTrue(any(p.get("/Annots") for p in PdfReader(BytesIO(raw)).pages))
        self.assertGreater(len(PdfReader(BytesIO(raw)).pages[0].images),0)
        self.assertEqual(len(plan["monthly_forecasts"]),2)
        assert_daily_monthly_outlooks(self,raw,plan)
        (OUT/"monthly-browser.pdf").write_bytes(raw)
        p.locator("#adaptiveStartDate").fill(end)
        p.locator("#adaptiveDays").select_option("7")
        p.locator("#adaptiveBuild").click()
        expect(p.locator("#pageStatus")).to_contain_text("entire trip must fit")


    def test_07_shared_date_calendar(self):
        p=self.page
        from calendar import monthrange
        minimum=date.fromisoformat(self.info["min_date"])
        maximum=date.fromisoformat(self.info["max_date"])
        target=maximum.replace(day=15)
        for route,field in [("climate","climateTravelDate"),("explorer","mapMonth"),
                            ("planner","planMonth"),("adaptive","adaptiveStartDate")]:
            with self.subTest(page=route):
                self.goto("/"+route+".html?country=Egypt&city=Cairo&date="+target.isoformat())
                expect(p.locator("#"+field)).to_have_value(target.isoformat(),timeout=60000)
                trigger=p.locator(".wc-date-trigger")
                dialog=p.locator("#"+field+"Calendar")
                expect(trigger).to_be_visible()
                trigger.click()
                expect(dialog).to_be_visible()
                expect(dialog.locator(".wc-cal-month")).to_have_value(str(target.month-1))
                expect(dialog.locator(".wc-cal-year")).to_have_value(str(target.year))
                expect(dialog.locator(".wc-cal-next")).to_be_disabled()
                selected=dialog.locator("[data-date='"+target.isoformat()+"']")
                expect(selected).to_have_attribute("aria-pressed","true")
                selected.press("ArrowRight")
                chosen=target+timedelta(days=1)
                expect(dialog.locator("[data-date='"+chosen.isoformat()+"']")).to_be_focused()
                dialog.locator("[data-date='"+chosen.isoformat()+"']").press("Enter")
                expect(p.locator("#"+field)).to_have_value(chosen.isoformat())
                expect(dialog).to_be_hidden()
                trigger.click()
                p.keyboard.press("Escape")
                expect(dialog).to_be_hidden()
                expect(trigger).to_be_focused()
                trigger.click()
                # Jump directly to the earliest available year/month.
                low=date.fromisoformat(p.locator("#"+field).get_attribute("min"))
                dialog.locator(".wc-cal-year").select_option(str(low.year))
                dialog.locator(".wc-cal-month").select_option(str(low.month-1))
                expect(dialog.locator(".wc-cal-prev")).to_be_disabled()
                if low.day>1:
                    expect(dialog.locator("[data-date='"+low.replace(day=1).isoformat()+"']")).to_be_disabled()
                dialog.locator("[data-date='"+low.isoformat()+"']").click()
                expect(p.locator("#"+field)).to_have_value(low.isoformat())
                expect(dialog).to_be_hidden()
        # Mobile and dark mode: calendar stays entirely inside the viewport.
        p.set_viewport_size({"width":390,"height":844})
        p.evaluate("document.documentElement.dataset.theme='dark'")
        trigger=p.locator(".wc-date-trigger")
        trigger.click()
        dialog=p.locator("#adaptiveStartDateCalendar")
        expect(dialog).to_be_visible()
        box=dialog.bounding_box()
        self.assertGreaterEqual(box["x"],0)
        self.assertGreaterEqual(box["y"],0)
        self.assertLessEqual(box["x"]+box["width"],391)
        self.assertLessEqual(box["y"]+box["height"],845)
        p.screenshot(path=str(OUT/"calendar-mobile-dark.png"),full_page=False)
        dialog.locator(".wc-cal-close").click()
        expect(dialog).to_be_hidden()

    def test_08_city_page_future_forecast(self):
        p=self.page
        self.goto("/")
        expect(p.locator("#api")).to_contain_text("server online")
        p.locator("#city").fill("London")
        p.locator("#city").press("Enter")
        expect(p.locator("#out .mt")).to_have_count(12)
        expect(p.locator("#cityClimateModes")).to_be_visible()
        p.locator("#cityForecastMode").click()
        expect(p.locator("#cityForecastResult")).to_contain_text("MONTHLY FORECAST",timeout=90000)
        expect(p.locator("#out")).to_be_hidden()
        target=date.fromisoformat(self.info["max_date"]).replace(day=15)
        p.locator("#cityTravelDate").fill(target.isoformat())
        expect(p.locator("#cityForecastResult")).to_contain_text(target.strftime("%B %Y"),timeout=90000)
        data=httpx.get(BASE+"/website/forecast",params={"country":"UK","city":"London","travel_date":target.isoformat()},timeout=90).json()
        self.assertIn(str(math.floor(data["predictions"][0]["predicted_tci"]+.5)),p.locator(".city-forecast-score").inner_text())
        expect(p.locator(".city-forecast-facts .fact")).to_have_count(5)
        p.locator("#cityForecastPanel .wc-date-trigger").click()
        expect(p.locator("#cityTravelDateCalendar")).to_be_visible()
        p.keyboard.press("Escape")
        expect(p.locator("#cityTravelDateCalendar")).to_be_hidden()
        p.locator("[data-unit='F']").click()
        expect(p.locator(".city-forecast-facts .fact").first).to_contain_text("°F")
        p.locator(".city-forecast-reliability summary").click()
        expect(p.locator(".city-forecast-table")).to_be_visible()
        expect(p.locator(".city-forecast-primary")).to_have_attribute("href",re.compile(r"adaptive\.html\?.*city=London.*date="+target.isoformat()))
        p.locator("#cityHistoryMode").click()
        expect(p.locator("#out .mt")).to_have_count(12)
        expect(p.locator("#out")).to_be_visible()
        expect(p.locator("#cityForecastPanel")).to_be_hidden()
        p.locator("#cityForecastMode").click()
        expect(p.locator("#cityForecastResult")).to_contain_text(target.strftime("%B %Y"))
        p.locator(".logo").click()
        expect(p.locator("#cityClimateModes")).to_be_hidden()
        p.locator("#city").fill("Cairo")
        p.locator("#city").press("Enter")
        expect(p.locator("#out .mt")).to_have_count(12)
        expect(p.locator("#cityHistoryMode")).to_have_attribute("aria-pressed","true")
        p.locator("#cityForecastMode").click()
        expect(p.locator("#cityForecastResult")).to_contain_text("MONTHLY FORECAST",timeout=90000)
        expect(p.locator("#rTitle")).to_contain_text("Cairo")
        expect(p.locator(".city-forecast-primary")).to_have_attribute("href",re.compile(r"city=Cairo"))
        p.set_viewport_size({"width":390,"height":844})
        p.locator("#cityForecastPanel").scroll_into_view_if_needed()
        p.screenshot(path=str(OUT/"city-forecast-mobile.png"),full_page=False)

    def test_06_weather_provider_error(self):
        p=self.page
        p.route("https://api.open-meteo.com/v1/forecast**",
                lambda r:r.fulfill(status=429,headers={"Access-Control-Allow-Origin":"*"},body="Rate limited"))
        start=(date.today()+timedelta(days=1)).isoformat()
        self.goto("/adaptive.html?city=Cairo&date="+start)
        expect(p.locator("#adaptiveStartDate")).to_have_value(start,timeout=60000)
        p.locator("#adaptiveDays").select_option("2")
        p.locator("#adaptiveBuild").click()
        expect(p.locator("#pageStatus")).to_contain_text("HTTP 429")
        expect(p.locator("#adaptiveDayCards")).to_have_count(0)
        expect(p.locator("#adaptiveBuild")).to_be_enabled()

def live_provider_probe():
    try:
        r=httpx.get("https://api.open-meteo.com/v1/forecast",params={
            "latitude":30.04,"longitude":31.24,"forecast_days":2,
            "daily":"temperature_2m_max,precipitation_sum,wind_speed_10m_max","timezone":"UTC"},timeout=15)
        r.raise_for_status()
        d=r.json()["daily"]
        assert len(d["time"])==2
        assert all(len(d[k])==2 and all(isinstance(v,(int,float)) and math.isfinite(v) for v in d[k])
                   for k in ["temperature_2m_max","precipitation_sum","wind_speed_10m_max"])
        print("LIVE_PROVIDER: PASS (real Open-Meteo request)",flush=True)
    except Exception as e:
        print("LIVE_PROVIDER: UNVERIFIED ("+str(e)+")",flush=True)

if __name__=="__main__":
    live_provider_probe()
    unittest.main(verbosity=2)
