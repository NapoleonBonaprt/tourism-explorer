import colorsys
import html

import folium
import pandas as pd
import streamlit as st
from branca.element import Element
from streamlit_folium import st_folium


# --------------------------------------------------
# 1. Streamlit page configuration
# --------------------------------------------------
st.set_page_config(
    page_title="Tourism Explorer",
    page_icon="🌍",
    layout="wide",
)

st.title("🌍 Tourism Explorer")
st.caption(
    "Find destinations ranked by the existing Tourism Climate Index (TCI)."
)


# --------------------------------------------------
# 2. Sidebar: Upload files
# --------------------------------------------------
with st.sidebar:
    st.header("Search")

    full_file = st.file_uploader(
        "Upload recommendations data (CSV)",
        type=["csv"],
        key="full",
    )

    places_file = st.file_uploader(
        "Upload attractions/map data (CSV)",
        type=["csv"],
        key="places",
    )

    st.info(
        "Upload your full dataframe and "
        "places_with_clusters dataframe as CSV files."
    )


# --------------------------------------------------
# 3. Helper functions
# --------------------------------------------------
def clean_col(df, candidates):
    """Return the first matching column name."""
    for col in candidates:
        if col in df.columns:
            return col
    return None


def get_cluster_color(cluster_id):
    """Return a consistent color for each DBSCAN cluster."""
    cluster_id = int(cluster_id)

    if cluster_id == -1:
        return "#808080"

    # Golden-ratio hue spacing gives clusters distinct, repeatable colors.
    hue = (cluster_id * 0.61803398875) % 1
    r, g, b = colorsys.hsv_to_rgb(hue, 0.75, 0.9)
    return "#{:02x}{:02x}{:02x}".format(
        int(r * 255), int(g * 255), int(b * 255)
    )


# --------------------------------------------------
# 4. Load recommendations data
# --------------------------------------------------
if full_file is None:
    st.info("Start by uploading the CSV exported from your full dataframe.")
    st.code(
        "full.to_csv('full.csv', index=False)\n"
        "places_with_clusters.to_csv("
        "'places_with_clusters.csv', index=False)",
        language="python",
    )
    st.stop()

try:
    full = pd.read_csv(full_file)
except Exception as e:
    st.error(f"Could not read recommendations CSV: {e}")
    st.stop()


country_col = clean_col(full, ["Country", "Country_dest", "country"])
month_col = clean_col(full, ["Month", "month"])
destination_col = clean_col(
    full, ["Destination Name", "destination", "Destination", "Place", "Name"]
)
tci_col = clean_col(full, ["TCI", "tci"])

if not all([country_col, month_col, destination_col, tci_col]):
    st.error(
        "Required columns were not found. "
        "Need country, month, destination name, and TCI."
    )
    st.write("Columns found:", list(full.columns))
    st.stop()

countries = sorted(
    full[country_col]
    .dropna()
    .astype(str)
    .str.strip()
    .unique()
    .tolist()
)

if not countries:
    st.error("No country values found in the uploaded data.")
    st.stop()


# --------------------------------------------------
# 5. Sidebar filters
# --------------------------------------------------
country = st.sidebar.selectbox("Country", countries)

month_options = [
    ("January", 1),
    ("February", 2),
    ("March", 3),
    ("April", 4),
    ("May", 5),
    ("June", 6),
    ("July", 7),
    ("August", 8),
    ("September", 9),
    ("October", 10),
    ("November", 11),
    ("December", 12),
]

month_label = st.sidebar.selectbox(
    "Month",
    [x[0] for x in month_options],
    index=7,
)
month = dict(month_options)[month_label]

location = st.sidebar.text_input(
    "City or governorate (optional)",
    placeholder="Leave blank to skip",
).strip()


# --------------------------------------------------
# 6. Filter recommendations
# --------------------------------------------------
filtered = full[
    full[country_col].astype(str).str.strip().str.casefold().eq(country.casefold())
    & pd.to_numeric(full[month_col], errors="coerce").eq(month)
].copy()

if location:
    location_cols = [
        c
        for c in [
            "City", "Governorate", "Province", "Region",
            "city", "governorate",
        ]
        if c in filtered.columns
    ]

    if location_cols:
        mask = pd.Series(False, index=filtered.index)
        for col in location_cols:
            mask |= (
                filtered[col]
                .astype("string")
                .str.strip()
                .str.casefold()
                .eq(location.casefold())
            )
        filtered = filtered[mask].copy()
    else:
        st.warning(
            "The recommendations CSV has no city/governorate column. "
            "Showing results without location filtering."
        )

filtered[tci_col] = pd.to_numeric(filtered[tci_col], errors="coerce")
filtered = filtered.dropna(subset=[tci_col])


# --------------------------------------------------
# 7. Select top 5 recommendations
# --------------------------------------------------
st.subheader(f"Top destinations — {country} · {month_label}")

if filtered.empty:
    st.warning("No destinations found for these filters.")
    st.stop()

top5 = (
    filtered.sort_values(tci_col, ascending=False)
    .drop_duplicates(subset=[destination_col])
    .head(5)
    .reset_index(drop=True)
)

c1, c2, c3 = st.columns(3)
c1.metric("Recommendations", len(top5))
c2.metric("Month", month_label)
c3.metric(
    "Highest TCI",
    f"{top5[tci_col].max():.1f}" if not top5.empty else "—",
)

display_cols = [
    c
    for c in [
        destination_col,
        clean_col(top5, ["City", "city"]),
        country_col,
        month_col,
        tci_col,
    ]
    if c
]

st.dataframe(
    top5[display_cols].rename(
        columns={destination_col: "Destination", tci_col: "TCI"}
    ),
    use_container_width=True,
    hide_index=True,
)


# --------------------------------------------------
# 8. Interactive attractions map
# --------------------------------------------------
st.subheader("🗺️ Interactive attractions map")

if places_file is None:
    st.info(
        "Upload your places_with_clusters CSV in the sidebar "
        "to show the interactive map."
    )
else:
    try:
        places = pd.read_csv(places_file)

        name_col = clean_col(
            places, ["Destination Name", "destination", "Destination", "Place", "Name"]
        )
        lat_col = clean_col(places, ["Latitude", "latitude", "lat", "Lat"])
        lon_col = clean_col(
            places, ["Longitude", "longitude", "lon", "lng", "Long"]
        )
        places_country_col = clean_col(
            places, ["Country_dest", "Country", "country"]
        )
        cluster_col = clean_col(
            places, ["spatial_cluster", "cluster", "Cluster"]
        )

        if not all([name_col, lat_col, lon_col]):
            st.error(
                "Map CSV needs destination name and coordinate columns."
            )
            st.write("Columns found:", list(places.columns))
            st.stop()

        if cluster_col is None:
            st.warning(
                "No cluster column found. All points will be shown as "
                "unclustered because DBSCAN labels are unavailable."
            )

        # Convert coordinates and remove invalid values.
        places[lat_col] = pd.to_numeric(places[lat_col], errors="coerce")
        places[lon_col] = pd.to_numeric(places[lon_col], errors="coerce")
        places = places.dropna(subset=[lat_col, lon_col]).copy()
        places = places[
            places[lat_col].between(-90, 90)
            & places[lon_col].between(-180, 180)
        ].copy()

        # Filter map by selected country.
        if places_country_col:
            country_places = places[
                places[places_country_col]
                .astype(str)
                .str.strip()
                .str.casefold()
                .eq(country.casefold())
            ].copy()

            if country_places.empty:
                st.warning(f"No attractions found for {country} in the map CSV.")
                st.stop()

            places = country_places

        if places.empty:
            st.warning("No valid map coordinates found for this selection.")
            st.stop()

        # Normalize cluster IDs; missing IDs are treated as unknown.
        if cluster_col:
            places[cluster_col] = pd.to_numeric(
                places[cluster_col], errors="coerce"
            )

        # Match Top 5 names case-insensitively.
        top_names = set(
            top5[destination_col]
            .dropna()
            .astype(str)
            .str.strip()
            .str.casefold()
        )

        m = folium.Map(
            location=[places[lat_col].mean(), places[lon_col].mean()],
            zoom_start=6,
            tiles="OpenStreetMap",
            control_scale=True,
        )

        top_count = 0
        clustered_count = 0
        noise_count = 0
        unknown_count = 0

        # Draw attractions. Cluster colors stay intact for Top 5 markers.
        for _, row in places.iterrows():
            name = str(row[name_col]).strip()
            is_top = name.casefold() in top_names

            cluster_value = row[cluster_col] if cluster_col else None
            has_cluster = (
                cluster_col is not None and pd.notna(cluster_value)
            )
            cluster_id = int(cluster_value) if has_cluster else None
            is_noise = has_cluster and cluster_id == -1

            if is_noise:
                fill_color = "#808080"
                label = "Noise (not assigned to a cluster)"
                noise_count += 1
            elif has_cluster:
                fill_color = get_cluster_color(cluster_id)
                label = f"Cluster {cluster_id}"
                clustered_count += 1
            else:
                fill_color = "#808080"
                label = "Cluster unknown"
                unknown_count += 1

            if is_top:
                top_count += 1
                label += " · Top 5 recommendation"

            city_col = clean_col(places, ["City", "city"])
            city = html.escape(str(row.get(city_col, ""))) if city_col else ""
            safe_name = html.escape(name)
            popup = (
                f"<b>{safe_name}</b><br>"
                f"{label}<br>"
                f"City: {city}"
            )

            if is_top:
                matching = top5[
                    top5[destination_col]
                    .astype(str)
                    .str.strip()
                    .str.casefold()
                    .eq(name.casefold())
                ]
                if not matching.empty:
                    tci_value = matching.iloc[0][tci_col]
                    popup += f"<br>TCI: {tci_value}"

            folium.CircleMarker(
                location=[row[lat_col], row[lon_col]],
                radius=7 if is_top else 4,
                color="#000000" if is_top else fill_color,
                fill=True,
                fill_color=fill_color,
                fill_opacity=1.0 if is_top else 0.85,
                weight=3 if is_top else 1,
                tooltip=name,
                popup=folium.Popup(popup, max_width=320),
            ).add_to(m)

        # Dynamic legend: one entry for every cluster in the selected country.
        cluster_ids = []
        if cluster_col:
            cluster_ids = sorted(
                int(value)
                for value in places[cluster_col].dropna().unique()
                if int(value) != -1
            )

        legend_items = []
        legend_items.append(
            '<span style="color:#000000;font-size:17px;">◉</span> '
            'Top 5 recommendations (black outline)<br>'
        )

        for cluster_id in cluster_ids:
            color = get_cluster_color(cluster_id)
            legend_items.append(
                f'<span style="color:{color};">●</span> '
                f'Cluster {cluster_id}<br>'
            )

        if cluster_col and (places[cluster_col] == -1).any():
            legend_items.append(
                '<span style="color:#808080;">●</span> '
                'Noise (-1)<br>'
            )

        legend_html = """
        <div style="
            position: fixed;
            bottom: 25px;
            left: 25px;
            z-index: 9999;
            background: white;
            padding: 12px 15px;
            border: 1px solid #bbb;
            border-radius: 8px;
            color: #222;
            font-size: 13px;
            line-height: 1.7;
            max-height: 300px;
            overflow-y: auto;
            box-shadow: 0 2px 6px rgba(0,0,0,0.2);
        ">
            <b>Map Legend</b><br>
            """ + "".join(legend_items) + """
        </div>
        """
        m.get_root().html.add_child(Element(legend_html))

        st_folium(
            m,
            use_container_width=True,
            height=550,
            returned_objects=[],
        )

        st.caption(
            "Each cluster has its own color · "
            "Top 5 recommendations have a black outline · "
            "Gray indicates DBSCAN noise."
        )

        col1, col2, col3 = st.columns(3)
        col1.metric("Top recommendations on map", top_count)
        col2.metric("Other clustered attractions", clustered_count)
        col3.metric("Noise points", noise_count)

        if unknown_count:
            st.info(
                f"{unknown_count} attraction(s) have no usable cluster label."
            )

        if cluster_col is None:
            st.info(
                "Upload a map CSV containing DBSCAN cluster labels "
                "to show cluster colors and identify noise points accurately."
            )
        elif noise_count == 0:
            st.info(
                "No noise points were found for this country in the uploaded "
                "map data. Check whether spatial_cluster contains -1 values."
            )

    except Exception as e:
        st.error(f"Could not read map CSV: {e}")
