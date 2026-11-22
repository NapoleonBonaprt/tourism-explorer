/* WanderClimate Interactive Map Discovery
 * Progressive enhancement: all original city buttons work without Leaflet.
 * Marker coordinates are obtained from the existing /website/filters API.
 */
(() => {
  "use strict";

  const section = document.getElementById("browse");
  const mapElement = document.getElementById("discoveryMap");
  const statusElement = document.getElementById("discoveryMapStatus");
  if (!section || !mapElement || !statusElement) return;

  const state = {
    map: null,
    layer: null,
    tileLayer: null,
    tileFallback: false,
    coords: new Map(),
    matching: [],
    markers: new Map(),
    initStarted: false,
    coordsReady: false
  };

  const normalize = value => String(value || "").trim().toLocaleLowerCase();
  const markerKey = place => normalize(place.city) + "|" + normalize(place.country);
  const escapeHtml = value => String(value || "").replace(/[&<>"']/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[char]));
  const validCoordinate = point => point && Number.isFinite(Number(point.latitude))
    && Number.isFinite(Number(point.longitude))
    && Number(point.latitude) >= -90 && Number(point.latitude) <= 90
    && Number(point.longitude) >= -180 && Number(point.longitude) <= 180;

  const apiRoot = (window.WANDERCLIMATE_API_BASE ||
    (["localhost", "127.0.0.1"].includes(location.hostname) && location.port !== "8000"
      ? "http://127.0.0.1:8000" : location.origin)).replace(/\/$/, "");

  function setStatus(message) {
    statusElement.textContent = message;
  }

  function makeTiles() {
    if (!state.map || !window.L) return;
    const dark = document.documentElement.getAttribute("data-theme") === "dark";
    const url = dark
      ? "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
      : "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png";
    if (state.tileLayer) state.map.removeLayer(state.tileLayer);
    const layer = L.tileLayer(url, {
      maxZoom: 19, subdomains: "abcd",
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
    });
    state.tileLayer = layer;
    state.tileFallback = false;
    layer.on("tileerror", () => {
      if (state.tileFallback || state.tileLayer !== layer) return;
      state.tileFallback = true;
      state.map.removeLayer(layer);
      state.tileLayer = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
      }).addTo(state.map);
    });
    layer.addTo(state.map);
  }

  function makeMarker(place, position) {
    const marker = L.marker(position, {
      title: [place.city, place.country].filter(Boolean).join(", "),
      icon: L.divIcon({
        className: "wc-map-pin",
        html: "<span aria-hidden=\"true\"></span>",
        iconSize: [22, 22],
        iconAnchor: [11, 11]
      })
    });
    marker.bindPopup(
      '<div class="discovery-popup"><strong>' + escapeHtml(place.city) + '</strong>'
      + '<small>' + escapeHtml(place.country || "Country unavailable") + '</small>'
      + '<button type="button">View climate details</button></div>'
    );
    marker.on("popupopen", event => {
      const popup = event.popup.getElement();
      const button = popup && popup.querySelector(".discovery-popup button");
      if (!button) return;
      button.addEventListener("click", () => {
        const search = document.getElementById("city");
        if (search) search.value = [place.city, place.country].filter(Boolean).join(", ");
        if (typeof window.explore === "function") {
          window.explore(place.city, false, place.country || "");
        }
      }, {once: true});
    });
    return marker;
  }

  function paintMarkers() {
    if (!state.map || !state.coordsReady) return;
    state.layer.clearLayers();
    state.markers.clear();

    const bounds = [];
    for (const place of state.matching) {
      const point = state.coords.get(normalize(place.city));
      if (!validCoordinate(point)) continue;
      const position = [Number(point.latitude), Number(point.longitude)];
      const marker = makeMarker(place, position);
      marker.addTo(state.layer);
      state.markers.set(markerKey(place), marker);
      bounds.push(position);
    }

    if (!state.matching.length) {
      setStatus("No destinations match your search.");
    } else if (!bounds.length) {
      setStatus("Map locations are unavailable for these cities. Use the directory.");
    } else {
      setStatus("Showing " + bounds.length + " of " + state.matching.length
        + " matching cities on the map. Select a pin to explore.");
      if (bounds.length === 1) {
        state.map.setView(bounds[0], 6, {animate: false});
      } else {
        state.map.fitBounds(L.latLngBounds(bounds).pad(.18), {maxZoom: 5, animate: false});
      }
    }
  }

  async function loadCoordinates() {
    try {
      const response = await fetch(apiRoot + "/website/filters", {
        headers: {Accept: "application/json"},
        cache: "default"
      });
      if (!response.ok) throw new Error("Coordinates API returned " + response.status);
      const data = await response.json();
      const coordinates = data && data.adaptive_coordinates;
      if (!coordinates || typeof coordinates !== "object") throw new Error("No city coordinates");
      for (const [city, position] of Object.entries(coordinates)) {
        if (validCoordinate(position)) state.coords.set(normalize(city), position);
      }
      if (!state.coords.size) throw new Error("No usable coordinates");
      state.coordsReady = true;
      paintMarkers();
    } catch (error) {
      setStatus("Map locations are temporarily unavailable. The city search still works.");
      console.warn("Destination map coordinates unavailable:", error);
    }
  }

  function initializeMap() {
    if (state.initStarted) return;
    state.initStarted = true;
    if (typeof window.L === "undefined") {
      setStatus("Map could not load. You can still search and select every city.");
      return;
    }

    try {
      state.map = L.map(mapElement, {
        center: [22, 12],
        zoom: 2,
        zoomSnap: .25,
        minZoom: 1.5,
        maxZoom: 12,
        scrollWheelZoom: false,
        worldCopyJump: true,
        zoomControl: false
      });
      L.control.zoom({position: "bottomright"}).addTo(state.map);
      state.layer = L.layerGroup().addTo(state.map);
      makeTiles();
      const themeObserver = new MutationObserver(mutations => {
        if (mutations.some(mutation => mutation.attributeName === "data-theme")) makeTiles();
      });
      themeObserver.observe(document.documentElement, {
        attributes: true, attributeFilter: ["data-theme"]
      });
      window.addEventListener("resize", () => state.map.invalidateSize(), {passive: true});
      setStatus("Loading city locations...");
      loadCoordinates();
    } catch (error) {
      setStatus("Map could not initialize. You can still browse every city below.");
      console.warn("Destination map could not initialize:", error);
    }
  }

  function highlightMarker(placeKey, highlighted) {
    const marker = state.markers.get(placeKey);
    const element = marker && marker.getElement();
    if (element) element.classList.toggle("is-highlighted", highlighted);
  }

  function setup() {
    document.addEventListener("wanderclimate:directory-updated", event => {
      state.matching = Array.isArray(event.detail?.matching) ? event.detail.matching : [];
      paintMarkers();
    });

    document.getElementById("discoveryReset")?.addEventListener("click", () => {
      const input = document.getElementById("browseQuery");
      if (input) {
        input.value = "";
        input.dispatchEvent(new Event("input", {bubbles: true}));
      }
    });

    const list = document.getElementById("browseGrid");
    list?.addEventListener("pointerover", event => {
      const item = event.target.closest(".browse-place");
      if (item && list.contains(item)) highlightMarker(
        normalize(item.dataset.city) + "|" + normalize(item.dataset.country), true
      );
    });
    list?.addEventListener("pointerout", event => {
      const item = event.target.closest(".browse-place");
      if (item && list.contains(item)) highlightMarker(
        normalize(item.dataset.city) + "|" + normalize(item.dataset.country), false
      );
    });

    // Request the current directory again: its initial render may have
    // happened before this deferred script was evaluated.
    document.dispatchEvent(new Event("wanderclimate:map-ready"));

    // Keep first load fast by deferring Leaflet's map setup until the user
    // approaches the discovery section. The city list remains usable.
    if ("IntersectionObserver" in window) {
      const observer = new IntersectionObserver(entries => {
        if (entries.some(entry => entry.isIntersecting)) {
          observer.disconnect();
          initializeMap();
        }
      }, {rootMargin: "300px 0px", threshold: 0});
      observer.observe(section);
    } else {
      initializeMap();
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", setup, {once: true});
  } else {
    setup();
  }
})();