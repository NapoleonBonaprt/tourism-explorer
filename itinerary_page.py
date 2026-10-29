"""Adaptive Daily Itinerary - a section you can plug into the team's Streamlit app.

Use it from app.py:
    from itinerary_page import render as render_itinerary
    ...
    elif page == "Adaptive Daily Itinerary":
        render_itinerary()

Needs (same folder): itinerary_engine.py (or itinerary_engine2.py) and places_with_clusters.csv
"""
import sys
from html import escape as esc
from pathlib import Path

import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

try:
    from itinerary_engine import (  # noqa: E402
        add_day_type, build_itinerary, get_daily_weather,
        plan_to_frame, prepare_city, replan,
    )
except ModuleNotFoundError:
    from itinerary_engine2 import (  # noqa: E402
        add_day_type, build_itinerary, get_daily_weather,
        plan_to_frame, prepare_city, replan,
    )

ICONS = {"outdoor": "☀️", "mixed": "⛅", "indoor": "🌧️"}
COLORS = ["#E8742C", "#2F80B7", "#2E9E6B", "#D6457A", "#7B5CC4", "#0F9DA0", "#8B5A2B"]

CSS = """
<style>
.hero{background:linear-gradient(120deg,#FFD9A8 0%,#FBE9CF 45%,#BFE3F5 100%);
      border-radius:20px;padding:22px 28px;margin-bottom:18px;border:1px solid #F0D3AA}
.hero h1{margin:0;padding:0;font-size:2rem;color:#7A3410 !important}
.hero p{margin:6px 0 0;color:#5B4636}
.day{background:#fff;border-radius:16px;padding:14px 16px;margin-bottom:14px;
     box-shadow:0 2px 10px rgba(120,70,20,.10);border-left:6px solid #E8742C}
.day.outdoor{border-left-color:#F4A52A}
.day.mixed{border-left-color:#4FA3D1}
.day.indoor{border-left-color:#3B6EA8}
.dhead{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.dtitle{font-weight:700;font-size:1.05rem;color:#3B2F2F}
.ddate{color:#8a7560;font-size:.85rem}
.badge{margin-left:auto;padding:2px 10px;border-radius:999px;font-size:.8rem;font-weight:600}
.badge.outdoor{background:#FFE9C2;color:#9A5B00}
.badge.mixed{background:#D9EEFA;color:#1F6C94}
.badge.indoor{background:#DCE6F6;color:#2B4C7E}
.chips{display:flex;gap:8px;margin:8px 0 6px;flex-wrap:wrap}
.chips span{background:#FBF4E9;border-radius:8px;padding:2px 8px;font-size:.8rem;color:#5B4636}
.stop{display:flex;align-items:center;gap:10px;padding:7px 0;border-top:1px dashed #EAD9BF}
.num{width:24px;height:24px;border-radius:50%;color:#fff;font-weight:700;font-size:.8rem;
     display:flex;align-items:center;justify-content:center;flex:none}
.sname{flex:1;color:#3B2F2F}
.pill{font-size:.72rem;padding:1px 8px;border-radius:999px}
.pill.morning{background:#FFF0C9;color:#8A6100}
.pill.afternoon{background:#FFDCCB;color:#9C3B12}
.empty{color:#8a7560;font-style:italic;padding-top:6px}
div.stButton > button{border-radius:12px;font-weight:600}
section[data-testid="stSidebar"]{border-right:1px solid #EAD3AE}
button[kind="primary"], button[data-testid="stBaseButton-primary"]{
  background:#E8742C;border-color:#E8742C;color:#fff}
button[kind="primary"]:hover, button[data-testid="stBaseButton-primary"]:hover{
  background:#CF5F1B;border-color:#CF5F1B}
</style>
"""


def day_card(i, date, dtype, w, rows):
    """One day as an HTML card (single-line pieces so Markdown does not break it)."""
    color = COLORS[(i - 1) % len(COLORS)]
    stops = "".join(
        f'<div class="stop"><span class="num" style="background:{color}">{r["order"]}</span>'
        f'<span class="sname">{esc(str(r["name"]))}</span>'
        f'<span class="pill {esc(str(r["slot"]))}">{esc(str(r["slot"]))}</span></div>'
        for _, r in rows.iterrows()
    ) or '<div class="empty">No more attractions available for this day.</div>'
    return (
        f'<div class="day {dtype}">'
        f'<div class="dhead"><span class="dtitle">Day {i}</span><span class="ddate">{date}</span>'
        f'<span class="badge {dtype}">{ICONS[dtype]} {dtype}</span></div>'
        f'<div class="chips"><span>🌡️ {w.temperature_2m_max:.0f}°C</span>'
        f'<span>💧 {w.precipitation_sum:.1f} mm</span>'
        f'<span>💨 {w.wind_speed_10m_max:.0f} km/h</span></div>'
        f'{stops}</div>'
    )


@st.cache_data
def load_places():
    path = ROOT / "places_with_clusters.csv"
    if not path.exists():
        return None
    return pd.read_csv(path)


def fetch_weather(places, city, days):
    c = places[places.City == city]
    data = get_daily_weather(c.Latitude.mean(), c.Longitude.mean(), days)
    return add_day_type(pd.DataFrame(data))


@st.fragment
def map_panel(flat, n_days):
    """Changing 'Show on map' re-draws only the map, not the whole page."""
    choice = st.selectbox("Show on map", ["All days"] + [f"Day {i}" for i in range(1, n_days + 1)])
    view = flat if choice == "All days" else flat[flat.day_no == int(choice.split()[1])]
    if view.empty:
        st.info("Nothing to show on the map for this selection.")
        return
    m = folium.Map(location=[view.lat.mean(), view.lon.mean()], zoom_start=11,
                   tiles="OpenStreetMap", control_scale=True, prefer_canvas=True)
    for day_no, g in view.groupby("day_no"):
        color = COLORS[(day_no - 1) % len(COLORS)]
        g = g.sort_values("order")
        if len(g) > 1:
            folium.PolyLine(g[["lat", "lon"]].values.tolist(), color=color, weight=4, opacity=0.85).add_to(m)
        for _, r in g.iterrows():
            html = (f'<div style="background:{color};color:#fff;border-radius:50%;width:24px;'
                    f'height:24px;line-height:24px;text-align:center;font-weight:700;'
                    f'border:2px solid #fff;box-shadow:0 0 3px #000">{r["order"]}</div>')
            folium.Marker(
                [r.lat, r.lon], icon=folium.DivIcon(html=html, icon_size=(24, 24), icon_anchor=(12, 12)),
                tooltip=f"Day {day_no} · {r['order']}. {r['name']}",
                popup=folium.Popup(f"<b>{esc(str(r['name']))}</b><br>{r['category']} · {r['slot']}", max_width=250),
            ).add_to(m)
    if len(view) > 1:
        m.fit_bounds([[view.lat.min(), view.lon.min()], [view.lat.max(), view.lon.max()]])
    st_folium(m, use_container_width=True, height=560, returned_objects=[], key=f"itinerary_map_{choice}")
    st.markdown(" &nbsp; ".join(f'<span style="color:{COLORS[(d - 1) % len(COLORS)]}">●</span> Day {d}'
                                for d in sorted(view.day_no.unique())), unsafe_allow_html=True)
    st.caption("Lines connect the stops in visiting order (straight lines, not street routes).")


def render():
    """Draw the whole itinerary section (call it inside the team's navigation)."""
    S = st.session_state.setdefault("itin", {})   # own namespace: no clashes with the team's keys

    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="hero"><h1>🧭 Adaptive Daily Itinerary</h1>'
        '<p>Routes that adapt to the weather forecast: outdoor sights on sunny days, '
        'indoor ones when it rains.</p></div>',
        unsafe_allow_html=True,
    )

    places = load_places()
    if places is None:
        st.error("places_with_clusters.csv was not found next to app.py.")
        return

    cities = sorted(places.City.dropna().unique())
    with st.sidebar:
        st.markdown("### 🧳 Trip")
        city = st.selectbox("City", cities, key="itin_city",
                            index=cities.index("London") if "London" in cities else 0)
        days = st.slider("Days", 1, 7, 5, key="itin_days")
        n_stops = st.slider("Maximum Stops per day", 2, 5, 3, key="itin_stops")
        build = st.button("Build itinerary", type="primary", use_container_width=True, key="itin_build")

    if build:
        try:
            weather = fetch_weather(places, city, days)
        except Exception as e:  # network / API problem
            st.error(f"Could not get the forecast: {e}")
            return
        S.update(city=city, n_stops=n_stops, weather=weather,
                 plan=build_itinerary(places, city, weather, n_stops), changes=None)

    if "plan" not in S:
        st.info("Pick a city in the sidebar and press **Build itinerary**.")
        return

    plan, weather = S["plan"], S["weather"]

    available = len(prepare_city(places, S["city"]))
    if False:
        st.warning(f"{S['city']} has only {available} distinct attractions, "
                   f"so some days will have fewer stops than requested.")

    with st.expander("🔄 Re-check the weather and adapt the plan", expanded=S.get("changes") is not None):
        sim = st.checkbox("Demo: simulate a storm (the real forecast rarely changes during a demo)",
                          key="itin_sim")
        sim_date, sim_rain = None, 8.0
        if sim:
            c1, c2 = st.columns(2)
            sim_date = c1.selectbox("Day", list(weather.time), key="itin_sim_day")
            sim_rain = c2.number_input("Rain (mm)", 0.0, 50.0, 8.0, key="itin_sim_rain")
        if st.button("Re-check weather & adapt", key="itin_recheck"):
            try:
                new_w = fetch_weather(places, S["city"], len(weather))
            except Exception as e:
                st.error(f"Could not get the forecast: {e}")
                return
            if sim:
                new_w.loc[new_w.time == sim_date, "precipitation_sum"] = sim_rain
                new_w = add_day_type(new_w)
            new_plan, changes = replan(plan, places, S["city"], new_w, S["n_stops"])
            S.update(plan=new_plan, weather=new_w, changes=changes)
            st.rerun()

        if S.get("changes") is not None:
            if S["changes"]:
                st.warning(f"{len(S['changes'])} day(s) were re-planned:")
                st.dataframe(pd.DataFrame(S["changes"]).rename(columns={
                    "date": "Date", "from": "Was", "to": "Now", "reason": "Why"}),
                    hide_index=True, use_container_width=True)
            else:
                st.success("Forecast unchanged - the plan stays as it is.")

    flat = plan_to_frame(plan)
    left, right = st.columns([1, 2])
    wx = weather.set_index("time")

    with left:
        for i, (date, (dtype, day)) in enumerate(plan.items(), 1):
            st.markdown(day_card(i, date, dtype, wx.loc[date], flat[flat.day_no == i]),
                        unsafe_allow_html=True)
    with right:
        map_panel(flat, len(plan))
