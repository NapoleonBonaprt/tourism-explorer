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
  const metric = (label, value, description="") =>
    `<div class="metric"><span>${safe(label)}</span><strong>${safe(value)}</strong>${description ? `<small>${safe(description)}</small>` : ""}</div>`;
  const table = (headers, rows) =>
    `<div class="table-scroller"><table><thead><tr>${headers.map(h=>`<th scope="col">${safe(h)}</th>`).join("")}</tr></thead>
    <tbody>${rows.map(row=>`<tr>${row.map(v=>`<td>${safe(v)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
  const pick = (arr) => [...new Set(arr)].sort((a,b)=>String(a).localeCompare(String(b)));
  const title = {
    overview: ["Executive Overview","An evidence-based view of global tourism, climate suitability, and geospatial insights."],
    climate: ["Climate & TCI Analytics","Explore how temperature, rainfall, humidity, and sunshine influence climate suitability month by month."],
    explorer: ["Spatial Clustering & Map Explorer","Browse the original Top 5 TCI recommendations alongside precomputed DBSCAN attraction clusters."],
    planner: ["Interactive Itinerary Planner","Select a destination and travel month to explore climate suitability and recommended attractions."],
    adaptive: ["Adaptive Daily Itinerary","Build a 1–7 day itinerary using a short-range weather forecast, then re-check and adapt the plan."],
  };
  function renderShell() {
    document.title = `${title[PAGE][0]} | WanderClimate`;
    $("siteHeader").innerHTML = `<div class="nav-wrap">
      <a class="brand" href="index.html"><img src="assets/wanderclimate-logo.svg" width="38" height="38" alt="" aria-hidden="true">WanderClimate</a>
      <button id="navToggle" class="mobile-nav-toggle" type="button" aria-label="Toggle navigation" aria-controls="siteNav" aria-expanded="false">Menu</button>
      <nav class="primary-nav" id="siteNav" aria-label="Main navigation">
        <a href="index.html">Home</a>
        ${PAGES.map(([key,label,href])=>`<a href="${href}"${key===PAGE ? ' aria-current="page"' : ""}>${label}</a>`).join("")}
      </nav>
    </div>`;
    $("siteFooter").innerHTML = `<div class="footer-inner"><span>WanderClimate · Tourism Climate Index and spatial analytics</span>
       <span>Historical climate suitability is not a live forecast. Adaptive planning uses forecast data.</span></div>`;
    $("dashboardRoot").innerHTML = `<div class="page-heading">
      <span class="eyebrow">Tourism Intelligence Platform</span><h1>${safe(title[PAGE][0])}</h1>
      <p class="lead">${safe(title[PAGE][1])}</p></div>
      <div class="status" id="pageStatus" role="status" aria-live="polite" hidden></div>
      <div id="pageContent"></div>`;
    $("navToggle").addEventListener("click", () => {
      const open = $("siteNav").classList.toggle("open");
      $("navToggle").setAttribute("aria-expanded", String(open));
    });
  }
  function plot(id, cfg) {
    if (!window.Chart) { status("Charts could not load. Check the Chart.js network connection.", "warning"); return; }
    const canvas = $(id);
    if (canvas._chart) canvas._chart.destroy();
    canvas._chart = new Chart(canvas, cfg);
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
  function makeMap(id, points, center=[20,0], zoom=4) {
    if(map){map.remove();map=null;}
    if(!window.L){status("Map library unavailable. Check the Leaflet connection.", "warning");return null;}
    map = L.map(id, {scrollWheelZoom:false}).setView(center,zoom);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",{
      maxZoom:19,attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);
    if(points.length) {
      const bounds=L.latLngBounds(points.filter(p=>Number.isFinite(+p.lat)&&Number.isFinite(+p.lon)).map(p=>[+p.lat,+p.lon]));
      if(bounds.isValid()) map.fitBounds(bounds.pad(.15),{maxZoom:12});
    }
    setTimeout(()=>map?.invalidateSize(),100);
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
       <div id="climateResults"></div>`;
    status("Loading countries and cities...");
    try {
      const f=await getFilters();
      bindCityFilter("climateCountry","climateCity",f.climate_cities);
      status("");
      $("climateForm").addEventListener("submit",e=>{e.preventDefault();loadClimate();});
      $("climateCountry").addEventListener("change",loadClimate);
      $("climateCity").addEventListener("change",loadClimate);
      await loadClimate();
    }catch(e){status(e.message,"error");}
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
        <div class="field"><label for="mapMonth">Month</label><select id="mapMonth">${monthOptions(8)}</select></div>
        <div class="field"><label for="mapLocation">City or governorate (optional)</label><input id="mapLocation" placeholder="Leave blank for all locations"></div>
        <button class="btn" type="submit" id="explorerButton">Update map</button></form>
      <div id="explorerResults"></div>`;
    status("Loading spatial explorer filters...");
    try{
      const f=await getFilters();
      const params=new URLSearchParams(location.search);
      const countries=f.map_countries;
      $("mapCountry").innerHTML=options(countries,countries.includes(params.get("country"))?params.get("country"):countries[0]);
      if(params.has("month"))$("mapMonth").value=params.get("month");
      if(params.has("city"))$("mapLocation").value=params.get("city");
      $("explorerForm").addEventListener("submit",e=>{e.preventDefault();loadExplorer();});
      $("mapCountry").addEventListener("change",loadExplorer);
      $("mapMonth").addEventListener("change",loadExplorer);
      status("");
      await loadExplorer();
    }catch(e){status(e.message,"error");}
  }
  let explorerSeq=0;
  async function loadExplorer() {
    const id=++explorerSeq; const button=$("explorerButton");busy(button,true);status("Filtering TCI rankings and mapping the DBSCAN clusters...");
    try{
      const data=await request("explorer",{country:$("mapCountry").value,month:$("mapMonth").value,location:$("mapLocation").value.trim()});
      if(id!==explorerSeq)return;
      const rows=data.top5.map((r,i)=>[i+1,r.destination,r.city||"—",r.country,r.month,pretty(r.tci)]);
      const uniqueClusters=pick(data.points.filter(p=>p.cluster!==null && p.cluster!==-1).map(p=>p.cluster)).sort((a,b)=>a-b);
      $("explorerResults").innerHTML=`<div class="summary-grid">
        ${metric("Recommendations",data.counts.recommendations)}
        ${metric("Selected Month",data.month_name)}
        ${metric("Highest TCI",data.top5.length?pretty(data.top5[0].tci):"N/A")}
        ${metric("Mapped Attractions",data.points.length)}
      </div>
      ${data.warning?`<p class="status warning section-gap">${safe(data.warning)}</p>`:""}
      <section class="card section-gap"><h2>Top destinations · ${safe(data.country)} · ${safe(data.month_name)}</h2>
        ${data.top5.length?table(["Rank","Destination","City","Country","Month","TCI"],rows):'<p>No destinations found for these filters.</p>'}
      </section>
      <section class="card section-gap"><h2>Interactive Attractions Map</h2>
        <div id="explorerMap" class="map large" role="application" aria-label="Map of tourist attractions and spatial clusters"></div>
        <div id="clusterLegend" class="legend">
          <span class="legend-item"><span class="marker-top"></span>Top 5 (black outline)</span>
          ${uniqueClusters.map(c=>`<span class="legend-item"><i style="background:${clusterColor(c)}"></i>Cluster ${c}</span>`).join("")}
          ${data.points.some(p=>p.cluster===-1)?'<span class="legend-item"><i style="background:#808080"></i>Noise (-1)</span>':""}
        </div>
        <p class="note">Points are precomputed DBSCAN labels. Top 5 have a black border; gray means noise or unknown cluster.</p>
      </section>
      <div class="summary-grid section-gap">
        ${metric("Top Recommendations on Map",data.counts.on_map)}
        ${metric("Other Clustered Attractions",data.counts.clustered)}
        ${metric("Noise Points",data.counts.noise)}
        ${metric("Cluster Unknown",data.counts.unknown)}
      </div>`;
      const m=makeMap("explorerMap",data.points);
      if(m){
        for(const p of data.points){
          const color=clusterColor(p.cluster);
          L.circleMarker([p.lat,p.lon],{radius:p.is_top?7:4,color:p.is_top?"#111":color,
            weight:p.is_top?3:1,fillColor:color,fillOpacity:p.is_top?1:.85})
            .bindTooltip(safe(p.name))
            .bindPopup(escapePopup([
              p.name,
              p.cluster===null?"Cluster unknown":p.cluster===-1?"Noise (-1)":`Cluster ${p.cluster}`,
              `City: ${p.city}`,p.is_top?"Top 5 recommendation":"",
              p.tci!=null?`TCI: ${pretty(p.tci)}`:""
            ].filter(Boolean))).addTo(m);
        }
      }
      status("");
    }catch(e){if(id===explorerSeq)status(e.message,"error");}
    finally{if(id===explorerSeq)busy(button,false);}
  }

  async function runPlanner(){
    $("pageContent").innerHTML=`<form id="plannerForm" class="filters card">
      <div class="field"><label for="planCountry">Destination Country</label><select id="planCountry"></select></div>
      <div class="field"><label for="planCity">Destination City</label><select id="planCity"></select></div>
      <div class="field"><label for="planMonth">Preferred Travel Month</label><select id="planMonth">${monthOptions(1)}</select></div>
      <div class="field"><label for="planCategory">Attraction Category</label><select id="planCategory">${options(["All","Outdoor","Indoor"],"All")}</select></div>
      <button type="submit" id="plannerButton" class="btn">Find attractions</button></form>
      <div id="plannerResults"></div>`;
    status("Loading itinerary planner filters...");
    try {
      const f=await getFilters();
      bindCityFilter("planCountry","planCity",f.planner_cities);
      $("plannerForm").addEventListener("submit",e=>{e.preventDefault();loadPlanner();});
      ["planCountry","planCity","planMonth","planCategory"].forEach(el=>$(el).addEventListener("change",loadPlanner));
      status("");
      await loadPlanner();
    } catch(e){status(e.message,"error");}
  }
  let plannerSeq=0;
  async function loadPlanner(){
    const id=++plannerSeq,button=$("plannerButton");busy(button,true);status("Finding matching attractions and climate information...");
    try {
      const d=await request("planner",{country:$("planCountry").value,city:$("planCity").value,
        month:$("planMonth").value,category:$("planCategory").value});
      if(id!==plannerSeq)return;
      const w=d.weather;
      $("plannerResults").innerHTML=`<section class="card">
        <h2>Recommended Itinerary for ${safe(d.city)} in ${safe(d.month_name)}</h2>
        ${w?`<div class="summary-grid">
          ${metric("Average Temperature",pretty(w.Temp_Mean)+" °C")}
          ${metric("Monthly TCI Score",pretty(w.TCI)+" / 100")}
          ${metric("Suitability Category",w.TCI_Category||"N/A")}
          ${metric("Sunshine Hours/Day",pretty(w.Sunshine_h_per_day)+" h")}
        </div><p class="note">${safe(w.source)}</p>`:
        '<p class="status warning">No monthly climate records available for this selected city.</p>'}
      </section>
      <section class="card section-gap"><h2>Top Attractions to Visit</h2>
        <p class="note">${human(d.total_matching)} matching attractions; displaying the first ${d.attractions.length}, as in the original planner.</p>
        <div class="stack">${d.attractions.length?d.attractions.map(a=>`
          <details class="attraction-card"><summary>${safe(a.name)} <small>${safe(a.type)} · ${safe(a.category)}</small></summary>
          <div class="inner">
            <p>Coordinates: Latitude ${pretty(a.latitude,5)}, Longitude ${pretty(a.longitude,5)}</p>
            <p>Climate Index Rating: ${pretty(a.tci)} (${safe(a.tci_category)})</p>
            <p>${safe(d.tip)}</p>
          </div></details>`).join(""):'<p>No attractions matching your filters were found for this city.</p>'}
        </div></section>`;
      status("");
    }catch(e){if(id===plannerSeq)status(e.message,"error");}
    finally{if(id===plannerSeq)busy(button,false);}
  }

  let adaptiveState=null;
  let adaptiveMapFilter="all";
  async function runAdaptive(){
    $("pageContent").innerHTML=`
      <section class="card">
        <form id="adaptiveForm" class="filters" style="margin-bottom:0">
          <div class="field"><label for="adaptiveCity">City</label><select id="adaptiveCity"></select></div>
          <div class="field"><label for="adaptiveDays">Days</label><select id="adaptiveDays">${options([1,2,3,4,5,6,7],5)}</select></div>
          <div class="field"><label for="adaptiveStops">Maximum Stops per Day</label><select id="adaptiveStops">${options([2,3,4,5],3)}</select></div>
          <button type="submit" class="btn" id="adaptiveBuild">Build itinerary</button>
        </form>
        <p class="note">Live forecast: Open-Meteo. Nearby places are ordered by geographical proximity, not road travel time.</p>
      </section>
      <div id="adaptiveResults" class="section-gap"><p class="status">Pick a city and press Build itinerary.</p></div>`;
    try {
      const f=await getFilters();
      const cities=f.adaptive_cities;
      const p=new URLSearchParams(location.search);
      $("adaptiveCity").innerHTML=options(cities,cities.includes(p.get("city"))?p.get("city"):
        cities.includes("London")?"London":cities[0]);
      $("adaptiveForm").addEventListener("submit",e=>{e.preventDefault();buildAdaptive();});
      status("");
    } catch(e){status(e.message,"error");}
  }
  const buildPayload=()=>({city:$("adaptiveCity").value,days:+$("adaptiveDays").value,stops:+$("adaptiveStops").value});
  async function buildAdaptive(){
    const button=$("adaptiveBuild");busy(button,true);status("Getting the forecast and building the route...");
    try{
      const d=await request("adaptive/build",{},{
        method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(buildPayload())
      });
      adaptiveState=d;adaptiveMapFilter="all";renderAdaptive();
      status("");
    } catch(e){status(e.message,"error");}
    finally{busy(button,false);}
  }
  function renderAdaptive(){
    const d=adaptiveState;
    if(!d)return;
    $("adaptiveResults").innerHTML=`
      ${d.warning?`<p class="status warning">${safe(d.warning)}</p>`:""}
      <section class="card"><h2>Re-check the Weather and Adapt the Plan</h2>
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
      </section>
      <div class="day-layout section-gap">
        <section class="stack" id="adaptiveDayCards">
          ${d.days.map(day=>`<article class="day-card ${safe(day.day_type)}">
            <div class="day-meta"><h3>Day ${day.number} · ${safe(day.date)}</h3>
              <span class="day-type">${safe(day.day_type)}</span></div>
            <div class="day-weather">
              <span>High: ${pretty(day.weather.temperature_2m_max,0)}°C</span>
              <span>Rain: ${pretty(day.weather.precipitation_sum)} mm</span>
              <span>Wind: ${pretty(day.weather.wind_speed_10m_max,0)} km/h</span>
            </div>
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
          <p class="note">Straight lines join the attractions in visiting order. They are not street directions.</p>
        </section>
      </div>`;
    $("simulateStorm").addEventListener("change",e=>{
      $("stormDateWrap").classList.toggle("hidden",!e.target.checked);
      $("stormRainWrap").classList.toggle("hidden",!e.target.checked);
    });
    $("adaptiveRecheck").addEventListener("click",recheckAdaptive);
    $("adaptiveDayFilter").value=adaptiveMapFilter;
    $("adaptiveDayFilter").addEventListener("change",e=>{adaptiveMapFilter=e.target.value;drawAdaptiveMap();});
    drawAdaptiveMap();
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
    if(!adaptiveState)return;
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
      const d=await request("adaptive/recheck",{},{
        method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({city:adaptiveState.city,days:adaptiveState.days.length,stops:adaptiveState.requested_stops,previous,simulate_storm:storm,storm_date:storm?weatherDate:null,rain_mm:rain})
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
