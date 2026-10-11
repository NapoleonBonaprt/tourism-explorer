 
import os
import re
import time
 
import pandas as pd
import requests
 
PLACES_PER_CITY = 25          
MIN_SITELINKS = 12            
DEFAULT_RADIUS_KM = 20
RADIUS_OVERRIDE_KM = {       
    "Cairo": 30,
    "Aswan": 30,
    "Luxor": 25,
}
OUTPUT_FILE = os.path.join(
    os.path.expanduser("~"), "Desktop", "Global_Destinations.csv"
)
 
WIKIDATA_URL = "https://query.wikidata.org/sparql"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
HEADERS = {
   
    "User-Agent": "ClimateSmartTourismProject/1.0 (student data science project)"
}
 
CITIES = [
    ("Cairo", "Egypt", 30.0444, 31.2357),
    ("Alexandria", "Egypt", 31.2001, 29.9187),
    ("Luxor", "Egypt", 25.6872, 32.6396),
    ("Aswan", "Egypt", 24.0889, 32.8998),
    ("Dubai", "UAE", 25.2048, 55.2708),
    ("Istanbul", "Turkey", 41.0082, 28.9784),
    ("Paris", "France", 48.8566, 2.3522),
    ("London", "UK", 51.5074, -0.1278),
    ("Rome", "Italy", 41.9028, 12.4964),
    ("Tokyo", "Japan", 35.6762, 139.6503),
    ("New York", "USA", 40.7128, -74.0060),
    ("Madrid", "Spain", 40.4168, -3.7038),
    ("Barcelona", "Spain", 41.3851, 2.1734),
    ("Berlin", "Germany", 52.5200, 13.4050),
    ("Munich", "Germany", 48.1351, 11.5820),
    ("Amsterdam", "Netherlands", 52.3676, 4.9041),
    ("Vienna", "Austria", 48.2082, 16.3738),
    ("Prague", "Czechia", 50.0755, 14.4378),
    ("Athens", "Greece", 37.9838, 23.7275),
    ("Lisbon", "Portugal", 38.7223, -9.1393),
    ("Budapest", "Hungary", 47.4979, 19.0402),
    ("Venice", "Italy", 45.4408, 12.3155),
    ("Florence", "Italy", 43.7696, 11.2558),
    ("Kyoto", "Japan", 35.0116, 135.7681),
    ("Beijing", "China", 39.9042, 116.4074),
    ("Shanghai", "China", 31.2304, 121.4737),
    ("Bangkok", "Thailand", 13.7563, 100.5018),
    ("Singapore", "Singapore", 1.3521, 103.8198),
    ("Seoul", "South Korea", 37.5665, 126.9780),
    ("Kuala Lumpur", "Malaysia", 3.1390, 101.6869),
    ("Sydney", "Australia", -33.8688, 151.2093),
    ("Cape Town", "South Africa", -33.9249, 18.4241),
    ("Rio de Janeiro", "Brazil", -22.9068, -43.1729),
    ("Buenos Aires", "Argentina", -34.6037, -58.3816),
    ("Toronto", "Canada", 43.6532, -79.3832),
    ("Los Angeles", "USA", 34.0522, -118.2437),
    ("San Francisco", "USA", 37.7749, -122.4194),
    ("Mexico City", "Mexico", 19.4326, -99.1332),
    ("Amman", "Jordan", 31.9454, 35.9284),
    ("Marrakesh", "Morocco", 31.6295, -7.9811),
    ("Riyadh", "Saudi Arabia", 24.7136, 46.6753),
    ("Nairobi", "Kenya", -1.2921, 36.8219),
    ("Lagos", "Nigeria", 6.5244, 3.3792),
    ("Vancouver", "Canada", 49.2827, -123.1207),
    ("Chicago", "USA", 41.8781, -87.6298),
    ("Lima", "Peru", -12.0464, -77.0428),
    ("Bogota", "Colombia", 4.7110, -74.0721),
    ("Zurich", "Switzerland", 47.3769, 8.5417),
    ("Stockholm", "Sweden", 59.3293, 18.0686),
    ("Melbourne", "Australia", -37.8136, 144.9631),
    ("Hong Kong", "Hong Kong", 22.3193, 114.1694),
    ("Delhi", "India", 28.6139, 77.2090),
]
 

WD_CLASSES = {
    "Q33506": ("museum", "Indoor"),               # museum
    "Q839954": ("archaeological_site", "Outdoor"),  # archaeological site
    "Q570116": ("attraction", "Outdoor"),         # tourist attraction
    "Q16560": ("attraction", "Indoor"),           # palace
    "Q32815": ("attraction", "Indoor"),           # mosque
    "Q16970": ("attraction", "Indoor"),           # church building
    "Q44539": ("attraction", "Indoor"),           # temple
    "Q23413": ("attraction", "Outdoor"),          # castle
    "Q22698": ("attraction", "Outdoor"),          # park
    "Q4989906": ("attraction", "Outdoor"),        # monument
    "Q12518": ("attraction", "Outdoor"),          # tower
    "Q174782": ("attraction", "Outdoor"),         # square
    "Q12280": ("attraction", "Outdoor"),          # bridge
}

TYPE_PRIORITY = ["Q33506", "Q839954", "Q16560", "Q32815", "Q16970",
                 "Q44539", "Q23413", "Q570116", "Q22698", "Q4989906",
                 "Q12518", "Q174782", "Q12280"]
 
 
def request_with_retry(method, url, retries=4, **kwargs):
    """HTTP request with backoff. Returns the response or None (never hides
    the failure silently: it prints the reason)."""
    for attempt in range(retries):
        try:
            r = requests.request(method, url, headers=HEADERS, timeout=90,
                                 **kwargs)
            if r.status_code == 200:
                return r
            print(f"   HTTP {r.status_code} (attempt {attempt + 1}/{retries})")
        except requests.RequestException as e:
            print(f"   {type(e).__name__}: {e} (attempt {attempt + 1}/{retries})")
        time.sleep(5 * (attempt + 1))
    return None
 
 
def wikidata_places(city, lat, lon, radius_km):
    values = " ".join(f"wd:{q}" for q in WD_CLASSES)
    query = f"""
    SELECT ?item ?itemLabel ?coord ?sitelinks ?type WHERE {{
      SERVICE wikibase:around {{
        ?item wdt:P625 ?coord .
        bd:serviceParam wikibase:center "Point({lon} {lat})"^^geo:wktLiteral .
        bd:serviceParam wikibase:radius "{radius_km}" .
      }}
      ?item wikibase:sitelinks ?sitelinks .
      FILTER(?sitelinks >= {MIN_SITELINKS})
      VALUES ?type {{ {values} }}
      ?item wdt:P31/wdt:P279* ?type .
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }}
    ORDER BY DESC(?sitelinks)
    LIMIT 600
    """
    r = request_with_retry(
        "GET", WIKIDATA_URL, params={"query": query, "format": "json"}
    )
    if r is None:
        return []
 
    best = {}  
    for b in r.json()["results"]["bindings"]:
        qid = b["item"]["value"].rsplit("/", 1)[-1]
        name = b["itemLabel"]["value"]
        if re.fullmatch(r"Q\d+", name):     
            continue
        m = re.match(r"Point\(([-\d.eE]+) ([-\d.eE]+)\)", b["coord"]["value"])
        if not m:
            continue
        type_q = b["type"]["value"].rsplit("/", 1)[-1]
        rank = TYPE_PRIORITY.index(type_q)
        if qid not in best or rank < best[qid]["rank"]:
            best[qid] = {
                "rank": rank,
                "Destination Name": name,
                "Type": WD_CLASSES[type_q][0],
                "Category": WD_CLASSES[type_q][1],
                "Latitude": round(float(m.group(2)), 5),
                "Longitude": round(float(m.group(1)), 5),
                "Wikidata_ID": qid,
                "Sitelinks": int(b["sitelinks"]["value"]),
                "Source": "wikidata",
            }
    rows = sorted(best.values(), key=lambda x: -x["Sitelinks"])
    for row in rows:
        row.pop("rank")
    return rows
 
 
def osm_places(city, lat, lon, radius_km):
    """Notable OSM places (must have a wikipedia/wikidata tag)."""
    rad = int(radius_km * 1000)
    query = f"""
    [out:json][timeout:60];
    (
      nwr["tourism"~"^(attraction|museum|viewpoint)$"]["name"]["wikidata"](around:{rad},{lat},{lon});
      nwr["historic"~"^(archaeological_site|castle|monument)$"]["name"]["wikidata"](around:{rad},{lat},{lon});
    );
    out center tags 300;
    """
    r = request_with_retry("POST", OVERPASS_URL, data={"data": query})
    if r is None:
        return []
 
    rows = []
    for el in r.json().get("elements", []):
        tags = el.get("tags", {})
        name = tags.get("name:en") or tags.get("name")
        e_lat = el.get("lat") or el.get("center", {}).get("lat")
        e_lon = el.get("lon") or el.get("center", {}).get("lon")
        if not name or e_lat is None or e_lon is None:
            continue
        if tags.get("tourism") == "museum":
            t, c = "museum", "Indoor"
        elif tags.get("historic") == "archaeological_site":
            t, c = "archaeological_site", "Outdoor"
        elif tags.get("tourism") == "viewpoint":
            t, c = "viewpoint", "Outdoor"
        else:
            t, c = "attraction", "Outdoor"
        rows.append({
            "Destination Name": name,
            "Type": t,
            "Category": c,
            "Latitude": round(e_lat, 5),
            "Longitude": round(e_lon, 5),
            "Wikidata_ID": tags.get("wikidata"),
            "Sitelinks": None,
            "Source": "osm",
        })
    return rows
 
 
def normalize(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())
 
 
def dedupe(rows):
    """Drop duplicates by normalized name or by ~100 m location + Wikidata ID."""
    seen_names, seen_ids, seen_pos, out = set(), set(), set(), []
    for row in rows:
        n = normalize(row["Destination Name"])
        pos = (round(row["Latitude"], 3), round(row["Longitude"], 3))
        qid = row.get("Wikidata_ID")
        if n in seen_names or pos in seen_pos or (qid and qid in seen_ids):
            continue
        seen_names.add(n)
        seen_pos.add(pos)
        if qid:
            seen_ids.add(qid)
        out.append(row)
    return out
 
 
def main():
    all_rows, failed = [], []
 
    for city, country, lat, lon in CITIES:
        radius = RADIUS_OVERRIDE_KM.get(city, DEFAULT_RADIUS_KM)
        print(f"{city}: querying Wikidata (radius {radius} km)...")
        rows = dedupe(wikidata_places(city, lat, lon, radius))
        print(f"   Wikidata -> {len(rows)} places")
 
        if len(rows) < PLACES_PER_CITY:
            print("   Not enough, adding OpenStreetMap places...")
            time.sleep(2)
            osm = osm_places(city, lat, lon, radius)
            print(f"   OSM -> {len(osm)} candidates")
            rows = dedupe(rows[:] + osm)
 
        rows = rows[:PLACES_PER_CITY]
        if len(rows) < PLACES_PER_CITY:
            failed.append((city, len(rows)))
 
        for row in rows:
            row["City"] = city
            row["Country"] = country
            row["City_Center_Lat"] = lat
            row["City_Center_Lon"] = lon
        all_rows.extend(rows)
        time.sleep(2)  
 
    df = pd.DataFrame(all_rows)
    df["Destination Name"] = df["Destination Name"] + " (" + df["City"] + ")"
    df = df.drop_duplicates(subset=["Destination Name"])
    df = df[[
        "Destination Name", "Type", "Category", "Latitude", "Longitude",
        "City", "Country", "Wikidata_ID", "Sitelinks", "Source",
        "City_Center_Lat", "City_Center_Lon",
    ]]
 
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
 
    print("\n" + "=" * 60)
    print(f"Saved {len(df)} places -> {OUTPUT_FILE}")
    print(df["Source"].value_counts().to_string())
    print(df["Type"].value_counts().to_string())
    if failed:
        print("\nCities with fewer than "
              f"{PLACES_PER_CITY} places (check them manually):")
        for city, n in failed:
            print(f"   {city}: {n}")
    print("=" * 60)
 
 
if __name__ == "__main__":
    main()