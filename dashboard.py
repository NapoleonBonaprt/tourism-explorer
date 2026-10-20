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
ROOT_DIR = r"C:\Users\HP\Downloads\tourism-explorer-main\tourism-explorer-main"

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
            df_attractions = smart_read_csv('cleaned_data/attractions_with_clusters.csv')
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
    st.title("📍 Spatial Clustering & Interactive Map Explorer")
    st.markdown("Examine spatial groupings (DBSCAN clusters) of attractions and top recommendations.")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("Cluster Insights")
        st.write("""
        Using spatial density clustering algorithms (**DBSCAN**), attractions are grouped into geographic clusters to identify tourism hubs, secondary regions, and isolated points of interest.
        """)
        selected_cluster_country = st.selectbox("Filter Clusters by Country:", sorted(df_attractions['Country_dest'].unique()))
        country_attractions = df_attractions[df_attractions['Country_dest'] == selected_cluster_country]
        
        st.metric("Total Attractions in Country", len(country_attractions))
        st.metric("Unique Clusters Found", country_attractions['spatial_cluster'].nunique())
        
        st.markdown("### Top Attractions Sample")
        st.dataframe(country_attractions[['Destination Name', 'City', 'Type', 'TCI_Category']].head(10), use_container_width=True)
        
    with col2:
        st.subheader("🗺️ Geographic Distribution Map")
        map_file = find_file('selected_country_map.html')
        if map_file and os.path.exists(map_file):
            with open(map_file, 'r', encoding='utf-8') as f:
                map_html = f.read()
            components.html(map_html, height=670, scrolling=True)
        else:
            st.error("Map HTML file ('selected_country_map.html') not found.")

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
