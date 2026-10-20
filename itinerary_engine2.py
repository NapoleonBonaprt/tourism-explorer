import numpy as np, pandas as pd

def haversine(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    a = np.sin((lat2-lat1)/2)**2 + np.cos(lat1)*np.cos(lat2)*np.sin((lon2-lon1)/2)**2
    return 6371 * 2 * np.arcsin(np.sqrt(a))

def prepare_city(places, city, merge_km=0.3):
    """Clean one city's places: drop city-centre rows, merge near-duplicates."""
    c = places[places.City == city].copy()
    c = c[c["Destination Name"] != f"{city} ({city})"]          # not a real attraction
    keep = []
    for i, r in c.iterrows():
        if all(haversine(r.Latitude, r.Longitude, c.loc[j, "Latitude"], c.loc[j, "Longitude"]) > merge_km
               for j in keep if c.loc[j, "Category"] == r.Category):
            keep.append(i)
    return c.loc[keep].reset_index(drop=True)

def order_route(stops):
    """Nearest-neighbour order, starting from the northern-most stop."""
    stops = stops.reset_index(drop=True)
    left = list(stops.index); cur = stops.Latitude.idxmax(); route = [cur]; left.remove(cur)
    while left:
        nxt = min(left, key=lambda j: haversine(stops.Latitude[cur], stops.Longitude[cur],
                                                stops.Latitude[j], stops.Longitude[j]))
        route.append(nxt); left.remove(nxt); cur = nxt
    return stops.loc[route]

def pick_nearby(pool, n, anchor=None):
    """Take n places that are close together (start from the biggest cluster)."""
    if pool.empty or n <= 0: return pool.head(0)
    if anchor is None:
        cl = pool[pool.spatial_cluster != -1].spatial_cluster.value_counts()
        seed = pool[pool.spatial_cluster == cl.index[0]] if len(cl) else pool
        anchor = (seed.Latitude.mean(), seed.Longitude.mean())
    d = haversine(anchor[0], anchor[1], pool.Latitude, pool.Longitude)
    return pool.loc[d.sort_values().index[:n]]

def build_day(city_places, day_type, used, n_stops=4):
    avail = city_places[~city_places["Destination Name"].isin(used)]
    out, ind = avail[avail.Category == "Outdoor"], avail[avail.Category == "Indoor"]
    if day_type == "outdoor":   n_out, n_in = n_stops, 0
    elif day_type == "indoor":  n_out, n_in = 0, n_stops
    else:                       n_out, n_in = n_stops // 2, n_stops - n_stops // 2
    morning = pick_nearby(out, n_out)
    anchor = (morning.Latitude.mean(), morning.Longitude.mean()) if len(morning) else None
    afternoon = pick_nearby(ind, n_in, anchor)
    # fallback: not enough places of the wanted type -> fill from the other type
    short = n_stops - len(morning) - len(afternoon)
    if short > 0 and day_type != "indoor":   # never push people outdoors on a bad-weather day
        rest = avail[~avail["Destination Name"].isin(pd.concat([morning, afternoon])["Destination Name"])]
        extra = pick_nearby(rest, short, anchor)
        morning = pd.concat([morning, extra[extra.Category == "Outdoor"]])
        afternoon = pd.concat([afternoon, extra[extra.Category == "Indoor"]])
    parts = []
    if len(morning):   parts.append(order_route(morning).assign(slot="morning"))
    if len(afternoon): parts.append(order_route(afternoon).assign(slot="afternoon"))
    if not parts:      # no places left -> empty day, but keep the 'slot' column
        return avail.head(0).assign(slot=pd.Series(dtype="object"))
    return pd.concat(parts)

def build_itinerary(places, city, weather_df, n_stops=4):
    cp, used, plan = prepare_city(places, city), set(), {}
    for _, w in weather_df.iterrows():
        day = build_day(cp, w.day_type, used, n_stops)
        used |= set(day["Destination Name"]); plan[w.time] = (w.day_type, day)
    return plan


# ---------------------------------------------------------------
# Weather helpers (so the Streamlit app can import everything from here)
# ---------------------------------------------------------------
def get_daily_weather(lat, lon, days=7):
    import requests
    r = requests.get("https://api.open-meteo.com/v1/forecast", params={
        "latitude": lat, "longitude": lon, "forecast_days": days,
        "daily": "temperature_2m_max,precipitation_sum,wind_speed_10m_max",
        "timezone": "auto"}, timeout=30)
    return r.json()["daily"]

def classify_day(temp_max, precip_mm, wind_kmh):
    if precip_mm >= 2 or temp_max >= 35 or wind_kmh >= 40:
        return "indoor"
    if precip_mm >= 0.5 or temp_max >= 32:
        return "mixed"
    return "outdoor"

def add_day_type(df_w):
    df_w = df_w.copy()
    df_w["day_type"] = [classify_day(t, p, w) for t, p, w in
                        zip(df_w.temperature_2m_max, df_w.precipitation_sum, df_w.wind_speed_10m_max)]
    return df_w

# ---------------------------------------------------------------
# Step 6: adaptive re-planning
# ---------------------------------------------------------------
def explain(w):
    why = []
    if w.precipitation_sum >= 0.5: why.append(f"rain {w.precipitation_sum:.1f} mm")
    if w.temperature_2m_max >= 32: why.append(f"heat {w.temperature_2m_max:.0f} C")
    if w.wind_speed_10m_max >= 40: why.append(f"wind {w.wind_speed_10m_max:.0f} km/h")
    return ", ".join(why) or "clear weather"

def replan(plan, places, city, new_weather_df, n_stops=4):
    """Keep days whose weather type did not change; rebuild only the days that did.
    Returns (new_plan, changes)."""
    cp, new_plan, changes, used = prepare_city(places, city), {}, [], set()
    for _, w in new_weather_df.iterrows():                       # 1) keep unchanged days
        old = plan.get(w.time)
        if old is not None and old[0] == w.day_type:
            new_plan[w.time] = old; used |= set(old[1]["Destination Name"])
    for _, w in new_weather_df.iterrows():                       # 2) rebuild changed days
        if w.time in new_plan: continue
        old = plan.get(w.time)
        day = build_day(cp, w.day_type, used, n_stops)
        used |= set(day["Destination Name"])
        new_plan[w.time] = (w.day_type, day)
        changes.append({"date": w.time, "from": old[0] if old else "new",
                        "to": w.day_type, "reason": explain(w)})
    new_plan = {w.time: new_plan[w.time] for _, w in new_weather_df.iterrows()}
    return new_plan, changes

PLAN_COLS=["day_no","date","day_type","order","name","category","slot","lat","lon","clister"]
def plan_to_frame(plan):
    rows=[]
    for i , (date,(dtype,day)) in enumerate(plan.items(),1):
        for k,(_,r) in enumerate(day.iterrows(),1):
            rows.append(dict(day_no=i ,date=date,day_type=dtype,order=k,name=r["Destination Name"].rsplit(" (", 1)[0],
                             category=r["Category"], slot=r["slot"],
                             lat=r["Latitude"], lon=r["Longitude"], cluster=r["spatial_cluster"]))
    return pd.DataFrame(rows, columns=PLAN_COLS) 
# =====  v2: these definitions replace the older versions above  =====

def build_day(city_places, day_type, used, n_stops=4):
    avail = city_places[~city_places["Destination Name"].isin(used)]
    out, ind = avail[avail.Category == "Outdoor"], avail[avail.Category == "Indoor"]
    if day_type == "outdoor":   n_out, n_in = n_stops, 0
    elif day_type == "indoor":  n_out, n_in = 0, n_stops
    else:                       n_out, n_in = n_stops // 2, n_stops - n_stops // 2
    morning = pick_nearby(out, n_out)
    anchor = (morning.Latitude.mean(), morning.Longitude.mean()) if len(morning) else None
    afternoon = pick_nearby(ind, n_in, anchor)
    # fallback: not enough places of the wanted type -> fill from the other type
    short = n_stops - len(morning) - len(afternoon)
    if day_type == "indoor":
        # bad weather: stay indoors, borrow outdoor places only to reach 2 stops (never an empty day)
        short = max(0, min(short, min(n_stops, 2) - len(afternoon)))
    if short > 0:
        rest = avail[~avail["Destination Name"].isin(pd.concat([morning, afternoon])["Destination Name"])]
        extra = pick_nearby(rest, short, anchor)
        morning = pd.concat([morning, extra[extra.Category == "Outdoor"]])
        afternoon = pd.concat([afternoon, extra[extra.Category == "Indoor"]])
    parts = []
    if len(morning):   parts.append(order_route(morning).assign(slot="morning"))
    if len(afternoon): parts.append(order_route(afternoon).assign(slot="afternoon"))
    if not parts:      # no places left -> empty day, but keep the 'slot' column
        return avail.head(0).assign(slot=pd.Series(dtype="object"))
    return pd.concat(parts)


PRIORITY = {"indoor": 0, "mixed": 1, "outdoor": 2}   # scarce indoor places go to indoor days first


def stops_per_day(n_days, n_stops, available):
    """Spread the places evenly so that no day is left empty (e.g. 17 places / 5 days -> 4,4,3,3,3)."""
    total = min(n_days * n_stops, available)
    base, extra = divmod(total, n_days)
    return [base + (1 if i < extra else 0) for i in range(n_days)]


def _fill_days(cp, weather_df, counts, used, keep):
    rows = [w for _, w in weather_df.iterrows()]
    plan = dict(keep)
    todo = [(w, n) for w, n in zip(rows, counts) if w.time not in keep]
    for w, n in sorted(todo, key=lambda t: PRIORITY[t[0].day_type]):
        day = build_day(cp, w.day_type, used, n)
        used |= set(day["Destination Name"])
        plan[w.time] = (w.day_type, day)
    return {w.time: plan[w.time] for w in rows}


def build_itinerary(places, city, weather_df, n_stops=4):
    cp = prepare_city(places, city)
    counts = stops_per_day(len(weather_df), n_stops, len(cp))
    return _fill_days(cp, weather_df, counts, set(), {})


def replan(plan, places, city, new_weather_df, n_stops=4):
    """Keep days whose weather type did not change; rebuild only the days that did.
    Returns (new_plan, changes)."""
    cp, keep, used, changes = prepare_city(places, city), {}, set(), []
    for _, w in new_weather_df.iterrows():
        old = plan.get(w.time)
        if old is not None and old[0] == w.day_type:
            keep[w.time] = old
            used |= set(old[1]["Destination Name"])
    counts = [len(plan[w.time][1]) if w.time in plan else n_stops for _, w in new_weather_df.iterrows()]
    new_plan = _fill_days(cp, new_weather_df, counts, used, keep)
    for _, w in new_weather_df.iterrows():
        if w.time not in keep:
            old = plan.get(w.time)
            changes.append({"date": w.time, "from": old[0] if old else "new",
                            "to": w.day_type, "reason": explain(w)})
    return new_plan, changes
