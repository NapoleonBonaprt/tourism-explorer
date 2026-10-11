import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="Tourism Explorer", page_icon="🌍", layout="wide")

st.title("🌍 Tourism Explorer")
st.caption("Find destinations ranked by the existing Tourism Climate Index (TCI).")

with st.sidebar:
    st.header("Search")
    full_file = st.file_uploader("Upload recommendations data (CSV)", type=["csv"], key="full")
    places_file = st.file_uploader("Upload attractions/map data (CSV)", type=["csv"], key="places")
    st.info("Upload your `full` dataframe and `places_with_clusters` dataframe as CSV files.")

def clean_col(df, candidates):
    for col in candidates:
        if col in df.columns:
            return col
    return None

if full_file is None:
    st.info("Start by uploading the CSV exported from your `full` dataframe.")
    st.code("full.to_csv('full.csv', index=False)\nplaces_with_clusters.to_csv('places_with_clusters.csv', index=False)", language="python")
    st.stop()

try:
    full = pd.read_csv(full_file)
except Exception as e:
    st.error(f"Could not read recommendations CSV: {e}")
    st.stop()

country_col = clean_col(full, ["Country", "Country_dest", "country"])
month_col = clean_col(full, ["Month", "month"])
destination_col = clean_col(full, ["Destination Name", "destination", "Destination", "Place", "Name"])
tci_col = clean_col(full, ["TCI", "tci"])

if not all([country_col, month_col, destination_col, tci_col]):
    st.error("Required columns were not found. Need country, month, destination name, and TCI.")
    st.write("Columns found:", list(full.columns))
    st.stop()

countries = sorted(full[country_col].dropna().astype(str).str.strip().unique().tolist())
if not countries:
    st.error("No country values found in the uploaded data.")
    st.stop()

country = st.sidebar.selectbox("Country", countries)
month_options = [
    ("January", 1), ("February", 2), ("March", 3), ("April", 4),
    ("May", 5), ("June", 6), ("July", 7), ("August", 8),
    ("September", 9), ("October", 10), ("November", 11), ("December", 12)
]
month_label = st.sidebar.selectbox("Month", [x[0] for x in month_options], index=7)
month = dict(month_options)[month_label]
location = st.sidebar.text_input("City or governorate (optional)", placeholder="Leave blank to skip").strip()

filtered = full[
    full[country_col].astype(str).str.strip().str.casefold().eq(country.casefold())
    & pd.to_numeric(full[month_col], errors="coerce").eq(month)
].copy()

if location:
    location_cols = [c for c in ["City", "Governorate", "Province", "Region", "city", "governorate"] if c in filtered.columns]
    if location_cols:
        mask = pd.Series(False, index=filtered.index)
        for col in location_cols:
            mask |= filtered[col].astype("string").str.strip().str.casefold().eq(location.casefold())
        filtered = filtered[mask].copy()
    else:
        st.warning("The recommendations CSV has no city/governorate column. Showing results without location filtering.")

filtered[tci_col] = pd.to_numeric(filtered[tci_col], errors="coerce")
filtered = filtered.dropna(subset=[tci_col])

st.subheader(f"Top destinations — {country} · {month_label}")
if filtered.empty:
    st.warning("No destinations found for these filters.")
    st.stop()

top5 = (filtered.sort_values(tci_col, ascending=False)
        .drop_duplicates(subset=[destination_col])
        .head(5)
        .reset_index(drop=True))

c1, c2, c3 = st.columns(3)
c1.metric("Recommendations", len(top5))
c2.metric("Month", month_label)
c3.metric("Highest TCI", f"{top5[tci_col].max():.1f}" if not top5.empty else "—")

display_cols = [c for c in [destination_col, clean_col(top5, ["City", "city"]), country_col, month_col, tci_col] if c]
st.dataframe(top5[display_cols].rename(columns={destination_col:"Destination", tci_col:"TCI"}), use_container_width=True, hide_index=True)

st.subheader("🗺️ Interactive attractions map")
if places_file is None:
    st.info("Upload your `places_with_clusters` CSV in the sidebar to show the real interactive map.")
else:
    try:
        places = pd.read_csv(places_file)
        name_col = clean_col(places, ["Destination Name", "destination", "Destination", "Place", "Name"])
        lat_col = clean_col(places, ["Latitude", "latitude", "lat", "Lat"])
        lon_col = clean_col(places, ["Longitude", "longitude", "lon", "lng", "Long"])
        places_country_col = clean_col(places, ["Country_dest", "Country", "country"])
        if not all([name_col, lat_col, lon_col]):
            st.error("Map CSV needs destination name and coordinate columns (Latitude and Longitude).")
            st.write("Columns found:", list(places.columns))
        else:
            places[lat_col] = pd.to_numeric(places[lat_col], errors="coerce")
            places[lon_col] = pd.to_numeric(places[lon_col], errors="coerce")
            places = places.dropna(subset=[lat_col, lon_col])
            if places_country_col:
                country_places = places[places[places_country_col].astype(str).str.strip().str.casefold().eq(country.casefold())]
                if not country_places.empty:
                    places = country_places
            if places.empty:
                st.warning("No valid map coordinates found for this selection.")
            else:
                top_names = set(top5[destination_col].dropna().astype(str).str.strip().str.casefold())
                m = folium.Map(
                    location=[places[lat_col].mean(), places[lon_col].mean()],
                    zoom_start=6,
                    tiles="OpenStreetMap"
                )
                for _, row in places.iterrows():
                    name = str(row[name_col]).strip()
                    is_top = name.casefold() in top_names
                    popup = f"<b>{name}</b>"
                    if is_top:
                        popup += f"<br><b>Top 5 recommendation</b>"
                        matching = top5[top5[destination_col].astype(str).str.strip().str.casefold().eq(name.casefold())]
                        if not matching.empty:
                            popup += f"<br>TCI: {matching.iloc[0][tci_col]}"
                    folium.Marker(
                        [row[lat_col], row[lon_col]],
                        tooltip=name,
                        popup=folium.Popup(popup, max_width=280),
                        icon=folium.Icon(color="red" if is_top else "blue",
                                         icon="star" if is_top else "info-sign")
                    ).add_to(m)
                st_folium(m, use_container_width=True, height=550, returned_objects=[])
                st.caption("Red markers are top recommendations when attraction names match; blue markers are other mapped places.")
    except Exception as e:
        st.error(f"Could not read map CSV: {e}")
