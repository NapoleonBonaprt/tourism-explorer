/* WanderClimate's full Streamlit dashboard migration.
 * Each page queries the real Python datasets and itinerary engine via FastAPI.
 * Charts: Chart.js; maps: Leaflet/OpenStreetMap. */
(() => {
  "use strict";
  const PAGE = document.body.dataset.page || "overview";
  const HERE = window.location.hostname;
  const API_BASE = (window.WANDERCLIMATE_API_BASE ||
    (["localhost", "127.0.0.1"].includes(HERE) ? "http://127.0.0.1:8000" : window.location.origin)).replace(/\/$/, "");
  const PAGES = [
    ["overview", "Executive Overview", "overview.html"],
    ["climate", "Climate & TCI", "climate.html"],
    ["explorer", "Map Explorer", "explorer.html"],
    ["planner", "Itinerary Planner", "planner.html"],
    ["adaptive", "Adaptive Daily Itinerary", "adaptive.html"],
  ];
  const MONTHS = ["January", "February", "March", "April", "May", "June",
                  "July", "August", "September", "October", "November", "December"];
  const $ = (id) => document.getElementById(id);
  const safe = (value) => String(value ?? "").replace(/[&<>"']/g, ch =>
    ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));
  const pretty = (value, digits=1) => value === null || value === undefined ||
    !Number.isFinite(Number(value)) ? "N/A" : Number(value).toFixed(digits);
  const human = (n) => Number(n).toLocaleString("en-US");
  const query = (route, params={}) => {
    const url = new URL(API_BASE + "/website/" + route);
    Object.entries(params).forEach(([k,v]) => { if(v !== undefined && v !== null) url.searchParams.set(k, String(v)); });
    return url.toString();
  };
  async function request(route, params={}, options={}) {
    let response;
    try { response = await fetch(query(route, params), options); }
    catch { throw new Error("Cannot reach FastAPI. Start the server on port 8000 and check your connection."); }
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(typeof body.detail === "string" ? body.detail : `Server returned HTTP ${response.status}.`);
    }
    return response.json();
  }
  const status = (message, kind="") => {
    const el = $("pageStatus");
    if (!el) return;
    el.textContent = message || "";
    el.className = "status" + (kind ? " " + kind : "");
    el.hidden = !message;
  };
  const busy = (button, on) => { if(button) button.disabled = !!on; };
  const options = (values, selected) => values.map(value =>
    `<option value="${safe(value)}"${String(value)===String(selected) ? " selected" : ""}>${safe(value)}</option>`).join("");
  const monthOptions = (selected=8) => MONTHS.map((month,i) =>
    `<option value="${i+1}"${selected===i+1?" selected":""}>${month}</option>`).join("");

  async function setupForecastDate(id) {
    const info = await request("forecast-info");
    const field = $(id);
    field.min = info.min_date; field.max = info.max_date;
    const today = new Date();
    const localDate = new Date(today.getTime()-today.getTimezoneOffset()*60000).toISOString().slice(0,10);
    const requested = new URLSearchParams(location.search).get("date");
    if (requested && requested >= info.min_date && requested <= info.max_date) field.value = requested;
    else field.value = localDate > info.max_date ? info.max_date : (localDate < info.min_date ? info.min_date : localDate);
    if (localDate > info.max_date) throw new Error("The trained forecast window has expired. Update climate history and retrain the models.");
    window.WanderClimateCalendar?.enhance(field);
  }
  const forecastSummary = (f) => f ? `<section class="card section-gap">
    <h2>Monthly ML forecast reliability</h2>
    <div class="summary-grid">
      ${metric("Model",f.model)}
      ${metric("Forecast lead",f.horizon_months+" months","From "+f.origin)}
      ${metric("Historical success",pretty(f.within_10_pct,2)+"%","Within ±10 TCI points")}
      ${metric("Typical absolute error",pretty(f.mae,2)+" TCI points")}
    </div>
    <p class="note">${safe(f.definition)} Test samples: ${safe(f.test_n)}. 90th percentile absolute error: ${pretty(f.error_p90,2)} points. Historical-mean benchmark MAE: ${pretty(f.baseline_mae,2)}.</p>
    <p class="note">Monthly resolution: all dates in ${safe(f.target_month)} share the same forecast. ${safe(f.warning)}</p>
  </section>` : "";
  const weatherSummary = (w) => w ? `<section class="card section-gap">
    <h2>Predicted monthly weather</h2>
    <div class="summary-grid">${w.variables.map(v=>metric(v.label,pretty(v.prediction,2)+" "+v.unit)).join("")}</div>
    <details><summary>Model reliability by weather variable</summary>
    ${table(["Variable","MAE","Within tolerance","Tolerance","Historical mean MAE"],w.variables.map(v=>[v.label,pretty(v.mae,2)+" "+v.unit,pretty(v.within_tolerance_pct,1)+"%", "±"+v.tolerance+" "+v.unit,pretty(v.baseline_mae,2)+" "+v.unit]))}
    <p class="note">Residual Ridge · ${safe(w.test_year)} backtest · ${safe(w.horizon_months)}-month lead. ${safe(w.definition)}</p></details>
    <p class="note">Monthly estimates only; rainfall is the total for the month, not a daily prediction.</p>
  </section>`:"";
  const metric = (label, value, description="") =>
    `<div class="metric"><span>${safe(label)}</span><strong>${safe(value)}</strong>${description ? `<small>${safe(description)}</small>` : ""}</div>`;
  const table = (headers, rows) =>
    `<div class="table-scroller"><table><thead><tr>${headers.map(h=>`<th scope="col">${safe(h)}</th>`).join("")}</tr></thead>
    <tbody>${rows.map(row=>`<tr>${row.map(v=>`<td>${safe(v)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
  const pick = (arr) => [...new Set(arr)].sort((a,b)=>String(a).localeCompare(String(b)));
  const title = {
    overview: ["Executive Overview","An evidence-based view of global tourism, climate suitability, and geospatial insights."],
    climate: ["Climate & TCI Analytics","Explore how temperature, rainfall, humidity, and sunshine influence climate suitability month by month."],
    explorer: ["Spatial Clustering & Map Explorer","Explore date-based predicted TCI recommendations alongside geographic DBSCAN attraction clusters."],
    planner: ["Interactive Itinerary Planner","Select a destination and travel date to compute a monthly TCI prediction and recommended attractions."],
    adaptive: ["Adaptive Daily Itinerary","Build a 1–7 day itinerary using a short-range weather forecast, then re-check and adapt the plan."],
  };
  function renderShell() {
    document.title = `${title[PAGE][0]} | WanderClimate`;
    $("siteHeader").innerHTML = `<div class="nav-wrap">
      <a class="brand" href="index.html" aria-label="WanderClimate home"><span class="brand-emblem" aria-hidden="true"><img src="assets/wanderclimate-wordmark.webp" width="450" height="86" alt=""></span><span class="brand-label">Wander<span>Climate</span></span></a>
      <nav class="primary-nav" id="siteNav" aria-label="Main navigation">
        <a href="index.html">Home</a>
        ${PAGES.map(([key,label,href])=>`<a href="${href}"${key===PAGE ? ' aria-current="page"' : ""}>${label}</a>`).join("")}
      </nav>
      <div class="nav-actions">
        <button type="button" class="theme-toggle" data-theme-toggle aria-pressed="false" aria-label="Switch to dark mode"><span data-theme-icon aria-hidden="true">☾</span><span data-theme-label>Dark mode</span></button>
        <button id="navToggle" class="mobile-nav-toggle" type="button" aria-label="Toggle navigation" aria-controls="siteNav" aria-expanded="false">Menu</button>
      </div>
    </div>`;
    $("siteFooter").innerHTML = `<div class="footer-inner"><span>WanderClimate · Tourism Climate Index and spatial analytics</span>
       <span>Monthly models estimate TCI and monthly climate, not daily weather. Short-range plans use daily forecasts.</span></div>`;
    const actionText = {
      overview: "Explore the overview",
      climate: "Explore climate data",
      explorer: "Explore the map",
      planner: "Plan your itinerary",
      adaptive: "Build an itinerary",
    }[PAGE];
    const sectionLabel = {
      overview: "The bigger picture",
      climate: "Understand the seasons",
      explorer: "Discover the destinations",
      planner: "Plan with confidence",
      adaptive: "Weather-aware travel"
    }[PAGE];
    $("dashboardRoot").innerHTML = `<div class="page-heading">
      <div class="page-heading__content">
        <span class="eyebrow">${safe(sectionLabel)}</span>
        <h1>${safe(title[PAGE][0])}</h1>
        <p class="lead">${safe(title[PAGE][1])}</p>
        <a class="page-cta" href="#pageContent">${safe(actionText)}</a>
      </div>
    </div>
      <div class="status" id="pageStatus" role="status" aria-live="polite" hidden></div>
      <div id="pageContent"></div>`;
    const navToggle = $("navToggle");
    const siteNav = $("siteNav");
    function closeNav() {
      siteNav.classList.remove("open");
      navToggle.setAttribute("aria-expanded", "false");
    }
    navToggle.addEventListener("click", () => {
      const open = siteNav.classList.toggle("open");
      navToggle.setAttribute("aria-expanded", String(open));
    });
    siteNav.querySelectorAll("a").forEach(link => link.addEventListener("click", closeNav));
    document.addEventListener("keydown", event => { if (event.key === "Escape") closeNav(); });
    document.addEventListener("click", event => {
      if (siteNav.classList.contains("open") && !siteNav.contains(event.target) && !navToggle.contains(event.target)) closeNav();
    });
  }
  function syncChartTheme() {
    if (!window.Chart) return;
    const dark = document.documentElement.dataset.theme === "dark";
    const ink = dark ? "#d9e7dc" : "#435c4b";
    const grid = dark ? "#3b5145" : "#e8eee9";
    // Keep chart labels in the same font as dashboard headings and controls.
    Chart.defaults.font.family = "'Figtree', system-ui, sans-serif";
    Chart.defaults.font.size = 12;
    Chart.defaults.color = ink;
    Chart.defaults.borderColor = grid;
    for (const canvas of document.querySelectorAll("canvas")) {
      const chart = Chart.getChart(canvas);
      if (!chart) continue;
      const axes = chart.options?.scales || {};
      Object.values(axes).forEach(axis => {
        axis.ticks = {...axis.ticks, color: ink};
        axis.grid = {...axis.grid, color: grid};
        if (axis.title) axis.title.color = ink;
      });
      if (chart.options.plugins?.legend?.labels) chart.options.plugins.legend.labels.color = ink;
      chart.update("none");
    }
  }
  document.addEventListener("wanderclimate:themechange", syncChartTheme);
  function plot(id, cfg) {
    if (!window.Chart) { status("Charts could not load. Check the Chart.js network connection.", "warning"); return; }
    syncChartTheme();
    const canvas = $(id);
    if (canvas._chart) canvas._chart.destroy();
    canvas._chart = new Chart(canvas, cfg);
    syncChartTheme();
  }
  function baseChart(type, labels, datasets, extra={}) {
    return {type,data:{labels,datasets},options:{
      responsive:true,maintainAspectRatio:false,interaction:{mode:"index",intersect:false},
      plugins:{legend:{position:"bottom"},tooltip:{enabled:true}},
      scales:{y:{beginAtZero:type==="bar",grid:{color:"#edf0ed"}}},
      ...extra
    }};
  }
  let map = null;
  let basemapLayer = null;
  function setBasemap() {
    if (!map || !window.L) return;
    if (basemapLayer) map.removeLayer(basemapLayer);
    const dark = document.documentElement.dataset.theme === "dark";
    if (dark) {
      // Genuine dark cartography, not a brightness filter on OpenStreetMap tiles.
      // Esri World Dark Gray canvas, with a separate reference layer for labels.
      const base = L.tileLayer(
        "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}",
        { maxZoom:19, maxNativeZoom:16, attribution:
          'Map data &copy; Esri, HERE, Garmin, <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors and GIS user community' }
      );
      const labels = L.tileLayer(
        "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}",
        { maxZoom:19, maxNativeZoom:16 }
      );
      basemapLayer = L.layerGroup([base,labels]);
    } else {
      basemapLayer = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom:19,
        attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
      });
    }
    basemapLayer.addTo(map);
    if (basemapLayer.bringToBack) basemapLayer.bringToBack();
  }
  document.addEventListener("wanderclimate:themechange", setBasemap);
  function makeMap(id, points, center=[20,0], zoom=4) {
    if(map){map.remove();map=null;basemapLayer=null;}
    if(!window.L){status("Map library unavailable. Check the Leaflet connection.", "warning");return null;}
    map = L.map(id, {scrollWheelZoom:false}).setView(center,zoom);
    setBasemap();
    if(points.length) {
      const bounds=L.latLngBounds(points.filter(p=>Number.isFinite(+p.lat)&&Number.isFinite(+p.lon)).map(p=>[+p.lat,+p.lon]));
      if(bounds.isValid()) map.fitBounds(bounds.pad(.15),{maxZoom:12});
    }
    const thisMap=map;
    setTimeout(()=>{ if(map===thisMap) map.invalidateSize(); },100);
    return map;
  }
  const clusterColor = (cluster) => cluster==null || cluster===-1 ? "#808080"
    : `hsl(${Math.round((((cluster*0.61803398875)%1)+1)%1*360)},75%,48%)`;
  const escapePopup = (parts) => parts.map(safe).join("<br>");

  async function runOverview() {
    const holder = $("pageContent");
    status("Loading the analyzed datasets...");
    try {
      const data = await request("overview");
      status("");
      holder.innerHTML = `<div class="summary-grid">
        ${metric("Total Destinations",human(data.metrics.destinations))}
        ${metric("Analyzed Cities",human(data.metrics.cities))}
        ${metric("Covered Countries",human(data.metrics.countries))}
        ${metric("Avg Climate Index (TCI)",pretty(data.metrics.average_tci)+" / 100")}
        </div>
        <div class="two-columns section-gap">
          <section class="card prose"><h2>Project Mission & Objectives</h2><p>${safe(data.mission.description)}</p>
            <ul>${data.mission.objectives.map(x=>`<li>${safe(x)}</li>`).join("")}</ul></section>
          <section class="card"><h2>Dataset Quick Summary</h2>
            ${table(Object.keys(data.country_summary[0]||{}),
              data.country_summary.map(row=>Object.keys(data.country_summary[0]||{}).map(k=>row[k]??"N/A")))}
            <p class="note">First 10 country-cluster summary records, matching the Streamlit dashboard.</p>
          </section></div>
        <section class="card section-gap"><h2>TCI Category Distribution Across Records</h2>
          <div class="chart-box tall"><canvas id="overviewChart" role="img" aria-label="Distribution of TCI categories"></canvas></div>
          <p class="note">Counts reflect the tourism analysis dataset, not the number of unique destinations.</p></section>`;
      plot("overviewChart",baseChart("bar",data.categories.map(x=>x.category),
        [{label:"Record Count",data:data.categories.map(x=>x.count),
          backgroundColor:["#3f6b4a","#5b8f94","#e0b65a","#b5593a","#708d70","#8c6d54"]}]));
    } catch(e) {status(e.message,"error");holder.innerHTML="";}
  }

  let filtersCache=null;
  async function getFilters(){return filtersCache||(filtersCache=await request("filters"));}
  function bindCityFilter(countryId,cityId,locations,defaultCity="") {
    const country=$ (countryId),city=$ (cityId);
    const countries=pick(locations.map(x=>x.country));
    const queryParams=new URLSearchParams(location.search);
    const qcountry=queryParams.get("country");
    const qcity=queryParams.get("city");
    country.innerHTML=options(countries,countries.includes(qcountry)?qcountry:countries[0]);
    const update=()=>{
      const values=pick(locations.filter(x=>x.country===country.value).map(x=>x.city));
      const target=values.includes(qcity)?qcity:(values.includes(defaultCity)?defaultCity:values[0]);
      city.innerHTML=options(values,target);
    };
    country.addEventListener("change",()=>{
      const values=pick(locations.filter(x=>x.country===country.value).map(x=>x.city));
      city.innerHTML=options(values,values[0]);
    });
    update();
  }

  async function runClimate() {
    const holder=$("pageContent");
    holder.innerHTML=`<form id="climateForm" class="filters card">
       <div class="field"><label for="climateCountry">Select Country</label><select id="climateCountry"></select></div>
       <div class="field"><label for="climateCity">Select City</label><select id="climateCity"></select></div>
       <button class="btn" type="submit" id="climateButton">Analyze climate</button></form>
       <section class="card section-gap"><h2>Predict monthly climate suitability</h2>
        <div class="filters"><div class="field"><label for="climateTravelDate">Travel date</label><input type="date" id="climateTravelDate" required></div>
        <button type="button" id="climateForecastButton" class="btn">Predict TCI</button></div>
        <div id="climateForecastResult" aria-live="polite"></div></section>
       <div id="climateResults" class="section-gap"></div>`;
    status("Loading countries and cities...");
    try {
      const f=await getFilters();
      bindCityFilter("climateCountry","climateCity",f.climate_cities);
      try {
        await setupForecastDate("climateTravelDate");
        $("climateForecastButton").addEventListener("click",loadClimateForecast);
        ["climateCountry","climateCity","climateTravelDate"].forEach(id=>$(id).addEventListener("change",loadClimateForecast));
        loadClimateForecast();
      } catch(e) {
        $("climateForecastResult").textContent=e.message;
        $("climateForecastButton").disabled=true;
      }
      status("");
      $("climateForm").addEventListener("submit",e=>{e.preventDefault();loadClimate();});
      $("climateCountry").addEventListener("change",loadClimate);
      $("climateCity").addEventListener("change",loadClimate);
      await loadClimate();
    }catch(e){status(e.message,"error");}
  }
  let climateForecastSeq=0;
  async function loadClimateForecast() {
    const id=++climateForecastSeq;
    const holder=$("climateForecastResult"),button=$("climateForecastButton");
    if(!$("climateTravelDate").reportValidity()){holder.textContent="Choose a date in the forecast window.";return;}
    busy(button,true);holder.textContent="Calculating monthly prediction...";
    try {
      const d=await request("forecast",{country:$("climateCountry").value,city:$("climateCity").value,travel_date:$("climateTravelDate").value});
      if(id!==climateForecastSeq)return;
      const row=d.predictions[0];
      holder.innerHTML=`<div class="summary-grid">${metric("Predicted monthly TCI",pretty(row.predicted_tci,2)+" / 100")}${metric("Historical mean benchmark",pretty(row.historical_mean_tci,2)+" / 100")}</div>${weatherSummary(d.monthly_weather)}${forecastSummary(d.forecast)}`;
    } catch(e) {if(id===climateForecastSeq)holder.textContent=e.message;}
    finally {if(id===climateForecastSeq)busy(button,false);}
  }
  let climateSeq=0;
  async function loadClimate() {
    const sequence=++climateSeq;
    const button=$("climateButton");busy(button,true);status("Calculating historical monthly climate metrics...");
    try {
      const data=await request("climate",{country:$("climateCountry").value,city:$("climateCity").value});
      if(sequence!==climateSeq)return;
      const monthly=data.monthly;
      const body=$("climateResults");
      const columnNames=["Month","Temp_Max_Mean","Temp_Min_Mean","Temp_Mean","RH_Mean","Precip_Total_mm","Sunshine_h_per_day","TCI","TCI_Category"];
      const labels=monthly.map(r=>MONTHS[Number(r.Month)-1]);
      const formatCell=(r,col)=>col==="Month"? MONTHS[Number(r.Month)-1] : typeof r[col]==="number"?pretty(r[col],1):r[col]??"N/A";
      body.innerHTML=`<div class="chart-grid">
        <section class="card"><h2>Monthly Temperature & TCI Trend in ${safe(data.city)}</h2>
          <div class="chart-box"><canvas id="climateTCI" role="img" aria-label="Mean temperature and TCI over 12 months"></canvas></div></section>
        <section class="card"><h2>Sunshine & Precipitation in ${safe(data.city)}</h2>
          <div class="chart-box"><canvas id="climateRain" role="img" aria-label="Daily sunshine hours and precipitation"></canvas></div>
          <p class="note">Rainfall converted from millimeters to centimeters, matching the original chart.</p></section></div>
        <section class="card section-gap"><h2>Detailed Monthly Climate Metrics Table</h2>
          <p class="note">Monthly means across ${safe(data.years[0])}–${safe(data.years[data.years.length-1])}; ${data.history.length} historical records.</p>
          ${table(columnNames,monthly.map(r=>columnNames.map(col=>formatCell(r,col))))}
        </section>
        <section class="card section-gap">
          <details><summary><strong>View all ${data.history.length} historical year-by-month records</strong></summary>
            <div class="section-gap">${table(["Year",...columnNames],data.history.map(r=>[r.Year,...columnNames.map(c=>formatCell(r,c))]))}</div>
          </details>
        </section>`;
      plot("climateTCI",baseChart("line",labels,[
        {label:"Mean Temp (°C)",data:monthly.map(r=>r.Temp_Mean),borderColor:"#c07520",backgroundColor:"#c07520",pointRadius:4,yAxisID:"temperature",tension:.18},
        {label:"TCI Score",data:monthly.map(r=>r.TCI),borderColor:"#3975ab",backgroundColor:"#3975ab",borderDash:[6,4],pointRadius:4,yAxisID:"tci",tension:.18}
      ],{scales:{temperature:{type:"linear",position:"left",title:{display:true,text:"Temperature (°C)"},grid:{color:"#edf0ed"}},
                 tci:{type:"linear",position:"right",min:0,max:100,title:{display:true,text:"TCI Score"},grid:{drawOnChartArea:false}}}}));
      plot("climateRain",baseChart("bar",labels,[
        {label:"Sunshine (h/day)",data:monthly.map(r=>r.Sunshine_h_per_day),backgroundColor:"#e0b65a"},
        {label:"Precipitation (cm)",data:monthly.map(r=>r.Precip_Total_mm/10),backgroundColor:"#5b8fbd"}
      ]));
      status("");
    }catch(e){if(sequence===climateSeq)status(e.message,"error");}
    finally{if(sequence===climateSeq)busy(button,false);}
  }

  async function runExplorer() {
    $("pageContent").innerHTML=`<form id="explorerForm" class="filters card">
        <div class="field"><label for="mapCountry">Country</label><select id="mapCountry"></select></div>
        <div class="field"><label for="mapMonth">Travel Date</label><input type="date" id="mapMonth" required></div>
        <div class="field"><label for="mapLocation">City (optional)</label><select id="mapLocation"></select></div>
        <button class="btn" type="submit" id="explorerButton">Update map</button></form>
      <div id="explorerResults"></div>`;
    status("Loading spatial explorer filters...");
    try{
      const f=await getFilters();
      const params=new URLSearchParams(location.search);
      const countries=pick(f.climate_cities.map(x=>x.country));
      $("mapCountry").innerHTML=options(countries,countries.includes(params.get("country"))?params.get("country"):countries[0]);
      await setupForecastDate("mapMonth");
      const syncMapCities=()=>{
        const cities=pick(f.climate_cities.filter(x=>x.country===$("mapCountry").value).map(x=>x.city));
        $("mapLocation").innerHTML='<option value="">All cities</option>'+options(cities,"");
        if(cities.includes(params.get("city"))) $("mapLocation").value=params.get("city");
      };
      syncMapCities();
      $("mapCountry").addEventListener("change",syncMapCities);
      $("mapLocation").addEventListener("change",loadExplorer);
      $("explorerForm").addEventListener("submit",e=>{e.preventDefault();loadExplorer();});
      $("mapCountry").addEventListener("change",loadExplorer);
      $("mapMonth").addEventListener("change",loadExplorer);
      status("");
      await loadExplorer();
    }catch(e){status(e.message,"error");}
  }
  let explorerSeq=0;
  async function loadExplorer() {
    if (!$("mapMonth").reportValidity()) {$("explorerResults").innerHTML="";return;}
    const id=++explorerSeq; const button=$("explorerButton");busy(button,true);status("Filtering TCI rankings and mapping the DBSCAN clusters...");
    try{
      const data=await request("explorer",{country:$("mapCountry").value,travel_date:$("mapMonth").value,location:$("mapLocation").value.trim()});
      if(id!==explorerSeq)return;
      const rows=data.top5.map((r,i)=>[i+1,r.destination,r.city||"—",r.country,r.month,pretty(r.tci)]);
      const uniqueClusters=pick(data.points.filter(p=>p.cluster!==null && p.cluster!==-1).map(p=>p.cluster)).sort((a,b)=>a-b);
      $("explorerResults").innerHTML=`<div class="summary-grid">
        ${metric("Recommendations",data.counts.recommendations)}
        ${metric("Selected Month",data.month_name)}
        ${metric("Highest predicted TCI",data.top5.length?pretty(data.top5[0].tci):"N/A")}
        ${metric("Mapped Attractions",data.points.length)}
      </div>
      ${forecastSummary(data.forecast)}
      ${!data.forecast && data.warning?`<p class="status warning section-gap">${safe(data.warning)}</p>`:""}
      <section class="card section-gap"><h2>Top destinations · ${safe(data.country)} · ${safe(data.month_name)}</h2>
        ${data.top5.length?table(["Rank","Destination","City","Country","Month","Predicted TCI"],rows):'<p>No destinations found for these filters.</p>'}
      </section>
      <section class="card section-gap explorer-panel">
        <div class="map-section-heading">
          <div><h2>Interactive Attractions Map</h2><p class="note">Search the attractions and control which DBSCAN clusters are visible.</p></div>
          <div class="map-filter-actions">
            <button type="button" id="showMapClusters" class="btn secondary small">Show all</button>
            <button type="button" id="hideMapClusters" class="btn secondary small">Hide all</button>
          </div>
        </div>
        <div class="field map-search-field">
          <label for="attractionSearch">Find an attraction by name or city</label>
          <input id="attractionSearch" type="search" placeholder="Try Great Pyramid, Cairo..." autocomplete="off">
        </div>
        <fieldset class="cluster-controls" aria-label="Visible map clusters">
          <legend>Visible clusters</legend>
          ${uniqueClusters.map(c=>`<label class="cluster-chip"><input type="checkbox" data-map-cluster="${c}" checked><i style="background:${clusterColor(c)}"></i>Cluster ${c}</label>`).join("")}
          ${data.points.some(p=>p.cluster===-1)?'<label class="cluster-chip"><input id="mapNoise" type="checkbox" checked><i style="background:#808080"></i>Noise (-1)</label>':""}
          ${data.points.some(p=>p.cluster===null)?'<label class="cluster-chip"><input id="mapUnknown" type="checkbox" checked><i style="background:#808080"></i>Unknown</label>':""}
          <label class="cluster-chip featured"><input id="mapTopOnly" type="checkbox">Top 5 only</label>
        </fieldset>
        <p id="visibleAttractions" class="note" role="status" aria-live="polite"></p>
        <div id="mapSearchMatches" class="map-search-results" aria-label="Matching attractions"></div>
        <div id="explorerMap" class="map large" role="application" aria-label="Map of tourist attractions and spatial clusters"></div>
        <div class="legend">
          <span class="legend-item"><span class="marker-top"></span>Top 5 (black outline)</span>
          <span class="legend-item"><i style="background:#808080"></i>Noise / unknown</span>
        </div>
        <p class="note">Colored markers use DBSCAN cluster IDs; the score is calculated from the selected travel date. Google Maps links open the selected attraction in a new tab.</p>
      </section>
      <div class="summary-grid section-gap">
        ${metric("Top Recommendations on Map",data.counts.on_map)}
        ${metric("Other Clustered Attractions",data.counts.clustered)}
        ${metric("Noise Points",data.counts.noise)}
        ${metric("Cluster Unknown",data.counts.unknown)}
      </div>`;
      setupExplorerMap(data);
      status("");
    }catch(e){if(id===explorerSeq){$("explorerResults").innerHTML="";status(e.message,"error");}}
    finally{if(id===explorerSeq)busy(button,false);}
  }


  function googleMapsUrl(lat, lon) {
    // Coordinates are returned by the analyzed attractions dataset, not scraped text.
    return "https://www.google.com/maps/search/?api=1&query=" +
      encodeURIComponent(Number(lat) + "," + Number(lon));
  }

  function setupExplorerMap(data) {
    const mapInstance=makeMap("explorerMap",data.points);
    if(!mapInstance)return;
    const controls=$("explorerResults");
    const allCheckboxes=()=>Array.from(controls.querySelectorAll("[data-map-cluster], #mapNoise, #mapUnknown"));
    const markers=data.points.map((point,index)=>{
      const color=clusterColor(point.cluster);
      const mapsLink=googleMapsUrl(point.lat,point.lon);
      const clusterLabel=point.cluster===null?"Cluster unknown":
        point.cluster===-1?"Noise (-1)":`Cluster ${point.cluster}`;
      const extra=escapePopup([
        point.name,clusterLabel,`City: ${point.city}`,point.category,
        point.is_top?"Top 5 recommendation":"",
        point.tci!=null?`Predicted monthly TCI: ${pretty(point.tci)}`:"",
        point.within_10_pct!=null?`Historical success within ±10: ${pretty(point.within_10_pct,2)}%`:""
      ].filter(Boolean));
      const marker=L.circleMarker([point.lat,point.lon],{
        radius:point.is_top?7:4,color:point.is_top?"#111":color,
        weight:point.is_top?3:1,fillColor:color,fillOpacity:point.is_top?1:.85
      }).bindTooltip(safe(point.name))
        .bindPopup(extra+`<div class="popup-actions"><a href="${mapsLink}" target="_blank" rel="noopener noreferrer">Open in Google Maps</a></div>`);
      return {point,index,marker};
    });
    function updateVisibleMarkers() {
      const search=$("attractionSearch").value.trim().toLocaleLowerCase();
      const enabled=new Set(Array.from(controls.querySelectorAll("[data-map-cluster]:checked"))
        .map(el=>Number(el.dataset.mapCluster)));
      const noise=$("mapNoise")?.checked??false;
      const unknown=$("mapUnknown")?.checked??false;
      const topOnly=$("mapTopOnly").checked;
      const matched=[];
      for(const entry of markers){
        const p=entry.point;
        const allowed=p.cluster===null?unknown:p.cluster===-1?noise:enabled.has(p.cluster);
        const nameMatch=!search || (p.name+" "+p.city).toLocaleLowerCase().includes(search);
        const show=allowed && nameMatch && (!topOnly || p.is_top);
        if(show){
          if(!mapInstance.hasLayer(entry.marker))entry.marker.addTo(mapInstance);
          matched.push(entry);
        }else if(mapInstance.hasLayer(entry.marker)){
          mapInstance.removeLayer(entry.marker);
        }
      }
      $("visibleAttractions").textContent=`Showing ${matched.length} of ${markers.length} attractions` +
        (search?` matching "${search}"`:"");
      const suggestions=$("mapSearchMatches");
      if(!search){
        suggestions.innerHTML="";
      }else if(!matched.length){
        suggestions.innerHTML='<p class="note">No matching attractions in the selected clusters. Try showing more clusters or a different search.</p>';
      }else{
        suggestions.innerHTML=matched.slice(0,16).map(entry=>
          `<button type="button" class="map-result" data-attraction-index="${entry.index}">`+
          `<strong>${safe(entry.point.name)}</strong><small>${safe(entry.point.city)} · `+
          `${entry.point.cluster===-1?"Noise":entry.point.cluster===null?"Unclustered":"Cluster "+entry.point.cluster}</small></button>`
        ).join("")+(matched.length>16?`<p class="note">Showing the first 16 of ${matched.length} matches. Refine your search to narrow the results.</p>`:"");
      }
    }
    controls.querySelector(".cluster-controls").addEventListener("change",updateVisibleMarkers);
    $("attractionSearch").addEventListener("input",updateVisibleMarkers);
    $("showMapClusters").addEventListener("click",()=>{
      allCheckboxes().forEach(el=>{el.checked=true;});
      $("mapTopOnly").checked=false;
      updateVisibleMarkers();
    });
    $("hideMapClusters").addEventListener("click",()=>{
      allCheckboxes().forEach(el=>{el.checked=false;});
      $("mapTopOnly").checked=false;
      updateVisibleMarkers();
    });
    $("mapSearchMatches").addEventListener("click",event=>{
      const button=event.target.closest("[data-attraction-index]");
      if(!button)return;
      const entry=markers[Number(button.dataset.attractionIndex)];
      if(!entry || !mapInstance.hasLayer(entry.marker))return;
      mapInstance.setView(entry.marker.getLatLng(),Math.max(mapInstance.getZoom(),12),{animate:true});
      entry.marker.openPopup();
    });
    updateVisibleMarkers();
  }

  async function runPlanner(){
    $("pageContent").innerHTML=`<form id="plannerForm" class="filters card">
      <div class="field"><label for="planCountry">Destination Country</label><select id="planCountry"></select></div>
      <div class="field"><label for="planCity">Destination City</label><select id="planCity"></select></div>
      <div class="field"><label for="planMonth">Preferred Travel Date</label><input type="date" id="planMonth" required></div>
      <div class="field"><label for="planCategory">Attraction Category</label><select id="planCategory">${options(["All","Outdoor","Indoor"],"All")}</select></div>
      <button type="submit" id="plannerButton" class="btn">Find attractions</button></form>
      <div id="plannerResults"></div>`;
    status("Loading itinerary planner filters...");
    try {
      const f=await getFilters();
      bindCityFilter("planCountry","planCity",f.climate_cities);
      await setupForecastDate("planMonth");
      $("plannerForm").addEventListener("submit",e=>{e.preventDefault();loadPlanner();});
      ["planCountry","planCity","planMonth","planCategory"].forEach(el=>$(el).addEventListener("change",loadPlanner));
      status("");
      await loadPlanner();
    } catch(e){status(e.message,"error");}
  }
  let plannerSeq=0;
  async function loadPlanner(){
    if (!$("planMonth").reportValidity()) {$("plannerResults").innerHTML="";return;}
    const id=++plannerSeq,button=$("plannerButton");busy(button,true);status("Finding matching attractions and climate information...");
    try {
      const d=await request("planner",{country:$("planCountry").value,city:$("planCity").value,
        travel_date:$("planMonth").value,category:$("planCategory").value});
      if(id!==plannerSeq)return;
      const w=d.weather;
      $("plannerResults").innerHTML=`<section class="card">
        <h2>Recommended Itinerary for ${safe(d.city)} in ${safe(d.month_name)}</h2>
        ${w?`<div class="summary-grid">
          ${metric("Predicted monthly TCI",pretty(w.TCI)+" / 100")}
          ${metric("Suitability Category",w.TCI_Category||"N/A")}
          ${metric("Historical mean benchmark",pretty(w.historical_mean_tci)+" / 100","Comparison only")}
        </div><p class="note">${safe(w.source)}</p>`:
        '<p class="status warning">No monthly climate records available for this selected city.</p>'}
      </section>
      ${weatherSummary(d.monthly_weather)}
      ${forecastSummary(d.forecast)}
      <section class="card section-gap"><h2>Top Attractions to Visit</h2>
        <p class="note">${human(d.total_matching)} matching attractions; displaying ${d.attractions.length} ranked by predicted city TCI and popularity proxy.</p>
        <div class="stack">${d.attractions.length?d.attractions.map(a=>`
          <details class="attraction-card"><summary>${safe(a.name)} <small>${safe(a.type)} · ${safe(a.category)}</small></summary>
          <div class="inner">
            <p>Coordinates: Latitude ${pretty(a.latitude,5)}, Longitude ${pretty(a.longitude,5)}</p>
            <p>Predicted monthly Climate Index Rating: ${pretty(a.tci)} (${safe(a.tci_category)})</p>
            <p>${safe(d.tip)}</p>
          </div></details>`).join(""):'<p>No attractions matching your filters were found for this city.</p>'}
        </div></section>`;
      status("");
    }catch(e){if(id===plannerSeq){$("plannerResults").innerHTML="";status(e.message,"error");}}
    finally{if(id===plannerSeq)busy(button,false);}
  }

  let adaptiveState=null;
  let adaptiveMapFilter="all";
  let adaptiveMaxDate="";
  const localISODate=()=>{const now=new Date();return new Date(now.getTime()-now.getTimezoneOffset()*60000).toISOString().slice(0,10);};
  const addDateDays=(value,n)=>{const d=new Date(value+"T00:00:00Z");d.setUTCDate(d.getUTCDate()+n);return d.toISOString().slice(0,10);};
  async function runAdaptive(){
    $("pageContent").innerHTML=`
      <section class="card">
        <form id="adaptiveForm" class="filters" style="margin-bottom:0">
          <div class="field"><label for="adaptiveCity">City</label><select id="adaptiveCity"></select></div>
          <div class="field"><label for="adaptiveStartDate">Trip Start Date</label><input type="date" id="adaptiveStartDate" required></div>
          <div class="field"><label for="adaptiveDays">Days</label><select id="adaptiveDays">${options([1,2,3,4,5,6,7],5)}</select></div>
          <div class="field"><label for="adaptiveStops">Maximum Stops per Day</label><select id="adaptiveStops">${options([2,3,4,5],3)}</select></div>
          <button type="submit" class="btn" id="adaptiveBuild">Build itinerary</button>
        </form>
        <p class="note">Trips within the next seven days use Open-Meteo daily forecasts. Later trips use monthly ML predictions and a provisional route; daily weather is not predicted. Nearby stops are ordered geographically, not by road travel time.</p>
      </section>
      <div id="adaptiveResults" class="section-gap"><p class="status">Pick a city and press Build itinerary.</p></div>`;
    try {
      const [f,info]=await Promise.all([getFilters(),request("forecast-info")]);
      const cities=f.adaptive_cities;
      adaptiveMaxDate=info.max_date>addDateDays(localISODate(),6)?info.max_date:addDateDays(localISODate(),6);
      const start=$("adaptiveStartDate");start.min=localISODate();start.max=adaptiveMaxDate;
      const requestedDate=new URLSearchParams(location.search).get("date");
      start.value=requestedDate&&requestedDate>=start.min&&requestedDate<=start.max?requestedDate:start.min;
      window.WanderClimateCalendar?.enhance(start);
      const p=new URLSearchParams(location.search);
      $("adaptiveCity").innerHTML=options(cities,cities.includes(p.get("city"))?p.get("city"):
        cities.includes("London")?"London":cities[0]);
      $("adaptiveForm").addEventListener("submit",e=>{e.preventDefault();buildAdaptive();});
      status("");
    } catch(e){status(e.message,"error");}
  }
  const buildPayload=()=>({city:$("adaptiveCity").value,start_date:$("adaptiveStartDate").value,days:+$("adaptiveDays").value,stops:+$("adaptiveStops").value});
  const weatherCache=new Map();
  async function browserForecast(city, days, startDate, force=false) {
    const filters=await getFilters();
    const point=filters.adaptive_coordinates?.[city];
    if(!point || !Number.isFinite(point.latitude) || !Number.isFinite(point.longitude))
      throw new Error("Cannot locate the selected city for live forecast. Refresh the page and try again.");
    const key=city+"|"+startDate+"|"+days;
    const cached=weatherCache.get(key);
    if(!force && cached && Date.now()-cached.time<10*60*1000) return cached.forecast;
    const url=new URL("https://api.open-meteo.com/v1/forecast");
    Object.entries({
      latitude:point.latitude,longitude:point.longitude,start_date:startDate,end_date:addDateDays(startDate,days-1),
      daily:"temperature_2m_max,precipitation_sum,wind_speed_10m_max",timezone:"auto"
    }).forEach(([k,v])=>url.searchParams.set(k,String(v)));
    const controller=new AbortController();
    const timeout=setTimeout(()=>controller.abort(),15000);
    try {
      const response=await fetch(url.toString(),{signal:controller.signal,cache:"no-store"});
      if(response.status===429) throw new Error("Open-Meteo is limiting weather requests on your network (HTTP 429). Please try again later.");
      if(!response.ok) throw new Error("Open-Meteo forecast request failed (HTTP "+response.status+").");
      const data=(await response.json()).daily;
      const fields=["time","temperature_2m_max","precipitation_sum","wind_speed_10m_max"];
      if(!data || fields.some(field=>!Array.isArray(data[field]) || data[field].length!==days))
        throw new Error("Incomplete Open-Meteo forecast");
      if(data.time.some((d,i)=>d!==addDateDays(startDate,i))) throw new Error("Forecast dates do not match the selected trip");
      if(fields.slice(1).some(field=>data[field].some(n=>typeof n!=="number" || !Number.isFinite(n))))
        throw new Error("Invalid Open-Meteo weather values");
      const forecast=Object.fromEntries(fields.map(field=>[field,data[field]]));
      weatherCache.set(key,{time:Date.now(),forecast});
      return forecast;
    } finally {clearTimeout(timeout);}
  }
  async function adaptivePayload(payload, force=false) {
    // The hosted server shares a rate-limited outbound proxy on free hosting.
    // Show the original browser error rather than silently retrying via that proxy.
    if(addDateDays(payload.start_date,payload.days-1)>addDateDays(localISODate(),6)) return payload;
    const forecast=await browserForecast(payload.city,payload.days,payload.start_date,force);
    return {...payload,forecast};
  }
  async function buildAdaptive(){
    if(!$("adaptiveStartDate").reportValidity())return;
    const requested=buildPayload();
    if(addDateDays(requested.start_date,requested.days-1)>adaptiveMaxDate){status("The entire trip must fit within the supported forecast dates.","error");return;}
    const button=$("adaptiveBuild");busy(button,true);status("Getting the forecast and building the route...");
    try{
      const payload=await adaptivePayload(requested);
      const d=await request("adaptive/build",{},{
        method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)
      });
      adaptiveState=d;adaptiveMapFilter="all";renderAdaptive();
      status("");
    } catch(e){status(e.message,"error");}
    finally{busy(button,false);}
  }
  function renderAdaptive(){
    const d=adaptiveState;
    if(!d)return;
    window.WanderClimatePDF?.prepareCover?.(d.city);
    $("adaptiveResults").innerHTML=`
      ${d.warning?`<p class="status warning">${safe(d.warning)}</p>`:""}
      ${(d.monthly_forecasts||[]).map(f=>`<section class="card section-gap"><h2>${safe(f.target_month)} · Predicted monthly TCI</h2><div class="summary-grid">${metric("Predicted monthly TCI",pretty(f.predicted_tci,2)+" / 100")}${metric("Suitability",f.tci_category)}</div>${weatherSummary(f.monthly_weather)}${forecastSummary(f)}</section>`).join("")}
      <section class="card itinerary-actions-card"><div class="itinerary-actions-head">
        <div><h2>Save or Print Your Itinerary</h2><p class="note">Take a simple travel guide with your daily visits, weather tips and map links.</p></div>
        <div class="export-buttons">
          <button type="button" class="btn" id="downloadItineraryPdf">Download travel guide</button>
          <button type="button" class="btn secondary" id="printItinerary">Print / Save as PDF</button>
        </div>
      </div><p class="route-disclaimer"><strong>Route information:</strong> Lines connect stops in geographic order (straight-line distance). They are not actual driving, walking, public transport or turn-by-turn routes. The itinerary does not account for travel time, roads, traffic or attraction opening hours.</p>
      </section>
      ${d.mode==="monthly"?`<section class="card itinerary-interactions"><h2>Provisional long-range trip</h2><p class="note">Rebuild within seven days of travel for live daily adaptation. Attraction categories and opening hours should be checked before visiting.</p></section>`:`<section class="card itinerary-interactions"><h2>Re-check the Weather and Adapt the Plan</h2>
        <div class="filters" style="margin-bottom:12px">
          <label class="checkline"><input type="checkbox" id="simulateStorm"> Demo: simulate a storm</label>
          <div class="field hidden" id="stormDateWrap"><label for="stormDate">Day</label>
            <select id="stormDate">${d.days.map(day=>`<option value="${safe(day.date)}">${safe(day.date)}</option>`).join("")}</select></div>
          <div class="field hidden" id="stormRainWrap"><label for="stormRain">Rain (mm, 0–50)</label>
            <input type="number" id="stormRain" min="0" max="50" step="0.5" value="8"></div>
          <button type="button" class="btn secondary" id="adaptiveRecheck">Re-check weather & adapt</button>
        </div>
        <p class="note">A simulated storm is for demonstration only; the forecast values are not historical TCI observations.</p>
        <div id="adaptiveChanges">${d.changes===null?"":
          d.changes.length? `<p class="status warning">${d.changes.length} day(s) were re-planned:</p>
            ${table(["Date","Was","Now","Why"],d.changes.map(x=>[x.date,x.from,x.to,x.reason]))}`:
          '<p class="status">Forecast unchanged: the plan stays as it is.</p>'}</div>
      </section>`}
      <div class="day-layout section-gap">
        <section class="stack" id="adaptiveDayCards"><div class="itinerary-print-head"><h2>WanderClimate Trip Plan</h2><p>${safe(d.city)} · ${d.days.length} day(s)</p></div>
          ${d.days.map(day=>`<article class="day-card ${safe(day.day_type)}">
            <div class="day-meta"><h3>Day ${day.number} · ${safe(day.date)}</h3>
              <span class="day-type">${safe(day.day_type)}${d.mode==="monthly"?" preference":""}</span></div>
            <div class="day-weather">${d.mode==="monthly"?`<span>Monthly TCI: ${pretty(day.monthly_forecast.predicted_tci,2)} / 100</span><span>Monthly weather above · daily weather unavailable</span>`:`<span>High: ${pretty(day.weather.temperature_2m_max,0)}°C</span><span>Rain: ${pretty(day.weather.precipitation_sum)} mm</span><span>Wind: ${pretty(day.weather.wind_speed_10m_max,0)} km/h</span>`}</div>
            ${day.stops.length?day.stops.map(stop=>`<div class="stop"><span class="stop-num">${stop.order}</span>
              <span>${safe(stop.name)}</span><span class="stop-slot">${safe(stop.slot)}</span></div>`).join(""):
              '<p class="note">No more attractions available for this day.</p>'}
          </article>`).join("")}
        </section>
        <section class="card sticky"><h2>Daily Route Map</h2>
          <div class="field" style="margin-bottom:15px">
            <label for="adaptiveDayFilter">Show on map</label>
            <select id="adaptiveDayFilter"><option value="all">All days</option>
              ${d.days.map(day=>`<option value="${day.number}"${adaptiveMapFilter===String(day.number)?" selected":""}>Day ${day.number}</option>`).join("")}
            </select>
          </div>
          <div id="adaptiveMap" class="map" role="application" aria-label="Map of the route stops"></div>
          <div id="adaptiveLegend" class="legend"></div>
          <p class="note route-disclaimer">Straight lines join stops in visiting order. They do not follow actual roads or indicate travel time, traffic, access or walking/driving directions.</p>
        </section>
      </div>`;
    $("downloadItineraryPdf").addEventListener("click", downloadItineraryPdf);
    $("printItinerary").addEventListener("click", () => window.print());
    $("simulateStorm")?.addEventListener("change",e=>{
      $("stormDateWrap").classList.toggle("hidden",!e.target.checked);
      $("stormRainWrap").classList.toggle("hidden",!e.target.checked);
    });
    $("adaptiveRecheck")?.addEventListener("click",recheckAdaptive);
    $("adaptiveDayFilter").value=adaptiveMapFilter;
    $("adaptiveDayFilter").addEventListener("change",e=>{adaptiveMapFilter=e.target.value;drawAdaptiveMap();});
    drawAdaptiveMap();
  }
  async function downloadItineraryPdf() {
    if(!adaptiveState || !adaptiveState.days.length){
      status("Build an itinerary before exporting it.","warning");return;
    }
    const button=$("downloadItineraryPdf");
    busy(button,true);
    status("Preparing your travel guide...");
    if(window.WanderClimatePDF?.available()){
      try {
        await window.WanderClimatePDF.download(adaptiveState);
        status("");
        return;
      } catch(error){
        status("Browser PDF generation failed; trying server export...", "warning");
      } finally {
        busy(button,false);
      }
    }
    const days=adaptiveState.days.map(day=>({
      number:day.number,date:day.date,day_type:day.day_type,weather:day.weather,
      stops:day.stops.map(stop=>({
        order:stop.order,name:stop.name,category:stop.category,
        slot:stop.slot,lat:stop.lat,lon:stop.lon
      }))
    }));
    try{
      const response=await fetch(query("adaptive/export-pdf"),{
        method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({city:adaptiveState.city,days,
          warning:adaptiveState.warning||null,changes:adaptiveState.changes||null,
          monthly_forecasts:adaptiveState.monthly_forecasts||[]})
      });
      if(!response.ok){
        const body=await response.json().catch(()=>({}));
        throw new Error(typeof body.detail==="string"?body.detail:
          "The PDF server could not export this itinerary.");
      }
      const blob=await response.blob();
      if(!blob.size)throw new Error("The PDF returned from the server is empty.");
      const objectUrl=URL.createObjectURL(blob);
      const anchor=document.createElement("a");
      anchor.href=objectUrl;
      const cityslug=adaptiveState.city.replace(/[^a-z0-9_-]+/gi,"-").replace(/^-|-$/g,"");
      anchor.download=`WanderClimate-${cityslug}-Travel-Guide.pdf`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      setTimeout(()=>URL.revokeObjectURL(objectUrl),30000);
      status("");
    }catch(error){
      const networkFailure=error instanceof TypeError || /failed to fetch|networkerror/i.test(error.message||"");
      const message=networkFailure
        ? "Could not reach the PDF export server. Start or restart FastAPI on port 8000. If offline, use Print / Save as PDF."
        : (error.message||"Could not download the PDF. Try Print / Save as PDF instead.");
      status(message,"error");
    }finally{busy(button,false);}
  }

  const dayColors=["#d18f24","#3c89b2","#328e68","#b45977","#7964ab","#3c8b8c","#986a37"];
  function drawAdaptiveMap(){
    if(!adaptiveState)return;
    const days=adaptiveState.days.filter(day=>adaptiveMapFilter==="all"||String(day.number)===adaptiveMapFilter);
    const pts=days.flatMap(day=>day.stops);
    const m=makeMap("adaptiveMap",pts.map(x=>({lat:x.lat,lon:x.lon})),[20,0],4);
    if(!m)return;
    $("adaptiveLegend").innerHTML=days.map(day=>
      `<span class="legend-item"><i style="background:${dayColors[(day.number-1)%dayColors.length]}"></i>Day ${day.number}</span>`).join("");
    for(const day of days){
      const color=dayColors[(day.number-1)%dayColors.length];
      const coords=day.stops.map(x=>[x.lat,x.lon]);
      if(coords.length>1)L.polyline(coords,{color,weight:4,opacity:.86}).addTo(m);
      for(const stop of day.stops){
        L.marker([stop.lat,stop.lon],{
          icon:L.divIcon({
            className:"route-marker",
            html:`<span style="display:grid;place-items:center;width:27px;height:27px;background:${color};color:#fff;border:2px solid white;border-radius:50%;font-weight:800;font-size:12px;box-shadow:0 1px 6px #0005">${stop.order}</span>`,
            iconSize:[27,27],iconAnchor:[13,13]
          })
        })
         .bindTooltip(`Day ${day.number} · ${stop.order}. ${safe(stop.name)}`)
         .bindPopup(escapePopup([stop.name,`Day ${day.number}`,stop.category,stop.slot])).addTo(m);
      }
    }
  }
  async function recheckAdaptive(){
    if(!adaptiveState||adaptiveState.mode==="monthly")return;
    const button=$("adaptiveRecheck");
    const storm=$("simulateStorm").checked;
    const weatherDate=$("stormDate").value;
    const rain=Number($("stormRain").value);
    if(storm && (!Number.isFinite(rain)||rain<0||rain>50)){status("Rainfall must be between 0 and 50 mm.","error");return;}
    busy(button,true);status("Re-checking the latest forecast and adapting changed days...");
    const previous=adaptiveState.days.map(day=>({
      date:day.date,day_type:day.day_type,stops:day.stops.map(stop=>({
        raw_name:stop.raw_name,category:stop.category,slot:stop.slot,
        lat:stop.lat,lon:stop.lon,cluster:stop.cluster
      }))
    }));
    try{
      const payload=await adaptivePayload({city:adaptiveState.city,start_date:adaptiveState.days[0].date,days:adaptiveState.days.length,
        stops:adaptiveState.requested_stops,previous,simulate_storm:storm,storm_date:storm?weatherDate:null,rain_mm:rain},true);
      const d=await request("adaptive/recheck",{},{
        method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify(payload)
      });
      adaptiveState=d;
      renderAdaptive();
      status("");
    }catch(e){status(e.message,"error");busy(button,false);}
  }

  renderShell();
  if(PAGE==="overview")runOverview();
  else if(PAGE==="climate")runClimate();
  else if(PAGE==="explorer")runExplorer();
  else if(PAGE==="planner")runPlanner();
  else if(PAGE==="adaptive")runAdaptive();
})();
