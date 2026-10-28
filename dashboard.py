import os
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import streamlit.components.v1 as components
from itinerary_page import render as render_itinerary

# --- Page Configuration ---
st.set_page_config(
    page_title="Climate-Smart Tourism Intelligence",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Custom Styling & CSS (Fixed for Cards Text Visibility) ---
st.markdown("""
    <style>
        .main { background-color: #0e1117; }
        /* تعديل الـ metrics لتناسب الوضع المظلم وتظهر النصوص بوضوح */
        div[data-testid="stMetric"] { 
            background-color: #1e293b !important; 
            padding: 15px; 
            border-radius: 10px; 
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            border: 1px solid #334155;
        }
        div[data-testid="stMetric"] label {
            color: #94a3b8 !important; /* لون عنوان الـ metric */
        }
        div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
            color: #f8fafc !important; /* لون الرقم داخل الـ metric */
        }
        h1, h2, h3 { color: #38bdf8 !important; }
    </style>
""", unsafe_allow_html=True)

# --- Universal Recursive File Finder ---
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

def find_file(filename):
    for root, dirs, files in os.walk(ROOT_DIR):
        if filename in files:
            return os.path.join(root, filename)
    return None

def smart_read_csv(filename):
    file_path = find_file(filename)
    if file_path and os.path.exists(file_path):
        return pd.read_csv(file_path)
    else:
        raise FileNotFoundError(f"Could not find required file: {filename} anywhere in {ROOT_DIR}")

@st.cache_data
def load_data():
    try:
        df_tourism = smart_read_csv('tourism_final_clean.csv')
        
        try:
            df_attractions = smart_read_csv('attractions_with_clusters.csv')
        except:
            df_attractions = smart_read_csv('places_with_clusters.csv')
            
        df_city_month = smart_read_csv('city_month_features.csv')
        df_cluster_sum = smart_read_csv('cluster_summary.csv')
        df_country_sum = smart_read_csv('country_cluster_summary.csv')
        
        return df_tourism, df_attractions, df_city_month, df_cluster_sum, df_country_sum
    except Exception as e:
        st.error(f"Error loading datasets: {e}")
        return None, None, None, None, None

df_tourism, df_attractions, df_city_month, df_cluster_sum, df_country_sum = load_data()

if df_tourism is None:
    st.stop()

# --- Sidebar Navigation ---
st.sidebar.image("https://img.icons8.com/color/96/globe-earth.png", width=80)
st.sidebar.title("Navigation Hub")
page = st.sidebar.radio("Go to:", [
    "🏠 Executive Overview", 
    "🌤️ Climate & TCI Analytics", 
    "📍 Spatial Clustering & Map Explorer", 
    "🗺️ Interactive Itinerary Planner",
    "Adaptive Daily Itinerary"
])

st.sidebar.markdown("---")
st.sidebar.info("💡 **Project Tip:** Use filters on each page to customize your analysis by Country, City, or TCI Category.")

# ==========================================
# PAGE 1: EXECUTIVE OVERVIEW
# ==========================================
if page == "🏠 Executive Overview":
    st.title("🌍 Climate-Smart Tourism Intelligence Platform")
    st.markdown("### Empowering sustainable travel planning and destination management through advanced climate data and spatial analytics.")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(label="Total Destinations", value=f"{df_attractions['Destination Name'].nunique():,}")
    with col2:
        st.metric(label="Analyzed Cities", value=f"{df_city_month['City'].nunique():,}")
    with col3:
        st.metric(label="Covered Countries", value=f"{df_attractions['Country_dest'].nunique():,}")
    with col4:
        st.metric(label="Avg Climate Index (TCI)", value=f"{df_tourism['TCI'].mean():.1f} / 100")
    
    st.markdown("---")
    
    c1, c2 = st.columns([2, 1])
    with c1:
        st.subheader("📌 Project Mission & Objectives")
        st.write("""
        Climate plays a pivotal role in global tourism satisfaction, safety, and operational sustainability. 
        This platform leverages multi-year meteorological metrics, spatial clustering (DBSCAN), and the **Tourism Climatic Index (TCI)** 
        to evaluate destinations worldwide. 
        
        * **Climate Suitability Assessment:** Evaluate thermal comfort, precipitation, sunshine hours, and wind speeds.
        * **Spatial Attraction Clustering:** Discover dense tourism clusters and outlier hotspots.
        * **Smart Recommendations:** Plan trips optimized for ideal weather windows.
        """)
        
        st.subheader("🏆 TCI Category Distribution Across Records")
        fig, ax = plt.subplots(figsize=(10, 4))
        cat_counts = df_tourism['TCI_Category'].value_counts()
        sns.barplot(x=cat_counts.index, y=cat_counts.values, palette="viridis", ax=ax)
        ax.set_ylabel("Record Count")
        ax.set_xlabel("TCI Rating Category")
        plt.xticks(rotation=15)
        st.pyplot(fig)
        
    with c2:
        st.subheader("📊 Dataset Quick Summary")
        st.dataframe(df_country_sum.head(10), use_container_width=True)

# ==========================================
# PAGE 2: CLIMATE & TCI ANALYTICS
# ==========================================
elif page == "🌤️ Climate & TCI Analytics":
    st.title("🌤️ Climate & Tourism Climatic Index (TCI) Analytics")
    st.markdown("Explore how environmental variables—such as temperature, humidity, and sunshine—influence destination ratings month by month.")
    
    selected_country = st.selectbox("Select Country:", sorted(df_city_month['Country_dest'].unique()))
    cities_in_country = sorted(df_city_month[df_city_month['Country_dest'] == selected_country]['City'].unique())
    selected_city = st.selectbox("Select City:", cities_in_country)
    
    city_data = df_city_month[df_city_month['City'] == selected_city].sort_values('Month')
    
    if not city_data.empty:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader(f"🌡️ Monthly Temperature & TCI Trend in {selected_city}")
            fig, ax1 = plt.subplots(figsize=(8, 4))
            
            ax1.plot(city_data['Month'], city_data['Temp_Mean'], color='orange', marker='o', label='Mean Temp (°C)')
            ax1.set_ylabel('Temperature (°C)', color='orange')
            ax1.tick_params(axis='y', labelcolor='orange')
            ax1.set_xlabel('Month')
            
            ax2 = ax1.twinx()
            ax2.plot(city_data['Month'], city_data['TCI'], color='blue', marker='s', linestyle='--', label='TCI Score')
            ax2.set_ylabel('TCI Score (0-100)', color='blue')
            ax2.tick_params(axis='y', labelcolor='blue')
            ax2.set_ylim(0, 100)
            
            plt.title(f"Temperature vs. TCI in {selected_city}")
            st.pyplot(fig)
            
        with col2:
            st.subheader(f"☀️ Sunshine & Precipitation in {selected_city}")
            fig, ax = plt.subplots(figsize=(8, 4))
            ax.bar(city_data['Month'] - 0.2, city_data['Sunshine_h_per_day'], width=0.4, label='Sunshine (h/day)', color='gold')
            ax.bar(city_data['Month'] + 0.2, city_data['Precip_Total_mm'] / 10, width=0.4, label='Precipitation (cm)', color='cornflowerblue')
            ax.set_xlabel('Month')
            ax.set_ylabel('Metrics Scale')
            ax.legend(loc='upper right')
            plt.title("Solar Radiation & Rainfall Distribution")
            st.pyplot(fig)
            
        st.subheader("📋 Detailed Monthly Climate Metrics Table")
        display_cols = ['Month', 'Temp_Max_Mean', 'Temp_Min_Mean', 'Temp_Mean', 'RH_Mean', 'Precip_Total_mm', 'Sunshine_h_per_day', 'TCI', 'TCI_Category']
        st.dataframe(city_data[display_cols].reset_index(drop=True), use_container_width=True)
    else:
        st.warning("No data available for the selected city.")

# ==========================================
# PAGE 3: SPATIAL CLUSTERING & MAP EXPLORER
# ==========================================
elif page == "📍 Spatial Clustering & Map Explorer":
    # Original app.py page, embedded in the team's Dashboard.
    # All helper functions and the Top 5 / DBSCAN Folium code are preserved.
    import colorsys
    import html
    import folium
    from pathlib import Path
    from branca.element import Element
    from streamlit_folium import st_folium

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

    @st.cache_data(show_spinner="Loading recommendations...")
    def _load_original_app_data():
        folder = Path(__file__).resolve().parent
        full_df = pd.read_csv(folder / "full.csv")
        places_df = pd.read_csv(folder / "places_with_clusters.csv")
        return full_df, places_df

    st.title("🌍 Tourism Explorer")
    st.caption("Find destinations ranked by the existing Tourism Climate Index (TCI).")
    try:
        full, places_data = _load_original_app_data()
    except Exception as exc:
        st.error(f"Could not load full.csv and places_with_clusters.csv: {exc}")
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

    try:
        places = places_data.copy()
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
            key=f"top5_dynamic_map_{country}_{month}",
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

# ==========================================
# PAGE 4: INTERACTIVE ITINERARY PLANNER
# ==========================================
elif page == "🗺️ Interactive Itinerary Planner":
    st.title("🗺️ Climate-Smart Itinerary & Destination Recommendation")
    st.markdown("Pick your destination city and preferred travel month to receive tailored attraction recommendations based on real-time climate suitability!")
    
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        dest_country = st.selectbox("Destination Country:", sorted(df_attractions['Country_dest'].unique()), key='plan_country')
        available_cities = sorted(df_attractions[df_attractions['Country_dest'] == dest_country]['City'].unique())
        dest_city = st.selectbox("Destination City:", available_cities, key='plan_city')
    with col_f2:
        travel_month = st.selectbox("Preferred Travel Month:", list(range(1, 13)), format_func=lambda x: pd.to_datetime(str(x), format='%m').strftime('%B'), key='plan_month')
        category_filter = st.selectbox("Attraction Category:", ['All', 'Outdoor', 'Indoor'], key='plan_cat')
        
    filtered_attrs = df_attractions[df_attractions['City'] == dest_city]
    if category_filter != 'All':
        filtered_attrs = filtered_attrs[filtered_attrs['Category'] == category_filter]
        
    city_m_weather = df_city_month[(df_city_month['City'] == dest_city) & (df_city_month['Month'] == travel_month)]
    
    st.markdown("---")
    st.subheader(f"🌟 Recommended Itinerary for {dest_city} in {pd.to_datetime(str(travel_month), format='%m').strftime('%B')}")
    
    if not city_m_weather.empty:
        w_row = city_m_weather.iloc[0]
        mcol1, mcol2, mcol3, mcol4 = st.columns(4)
        mcol1.metric("Average Temperature", f"{w_row['Temp_Mean']:.1f} °C")
        mcol2.metric("Monthly TCI Score", f"{w_row['TCI']:.1f} / 100")
        mcol3.metric("Suitability Category", f"{w_row['TCI_Category']}")
        mcol4.metric("Sunshine Hours/Day", f"{w_row['Sunshine_h_per_day']:.1f} h")
    
    st.markdown("### Top Attractions to Visit:")
    if not filtered_attrs.empty:
        for idx, row in filtered_attrs.head(10).iterrows():
            with st.expander(f"📍 {row['Destination Name']} ({row['Type']} - {row['Category']})"):
                st.write(f"**Coordinates:** Latitude {row['Latitude']}, Longitude {row['Longitude']}")
                st.write(f"**Climate Index Rating:** {row['TCI']} ({row['TCI_Category']})")
                st.write("✨ *Tip: Ideal spot for photography and cultural exploration during your selected travel month!*")
    else:
        st.info("No attractions matching your filters were found for this city.")

if page == "Adaptive Daily Itinerary":
    render_itinerary()
