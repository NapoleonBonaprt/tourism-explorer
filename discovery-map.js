/* WanderClimate Interactive Map Discovery
 * Progressive enhancement: all original city buttons work without Leaflet.
 * Marker coordinates are obtained from /website/destination-coordinates.
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
    tilesUnavailable: false,
    resizeObserver: null,
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
    // A standard, unfiltered street map keeps country borders, place names
    // and roads readable in both light and dark UI themes.
    if (!state.map || !window.L || state.tileLayer) return;
    const layer = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      minZoom: 0,
      maxZoom: 19,
      tileSize: 256,
      detectRetina: false,
      updateWhenIdle: false, // Fetch neighboring tiles while dragging
      updateInterval: 150,
      keepBuffer: 4,         // Prevent empty edges during a quick pan
      noWrap: true,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    });
    state.tileLayer = layer;
    let tileFailures = 0;
    layer.on("tileerror", () => {
      tileFailures++;
      if (tileFailures >= 4 && !state.tilesUnavailable) {
        state.tilesUnavailable = true;
        setStatus("Map imagery is temporarily unavailable. City markers and the directory still work.");
      }
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
    marker.bindTooltip(escapeHtml(place.city), {
      direction: "top",
      offset: [0, -12],
      opacity: 0.96,
      className: "discovery-city-tooltip"
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

  // Render city pins individually at every zoom level. Visitors should
  // never have to click a numbered group just to reveal a location.
  function paintMarkers(recenter = false) {
    if (!state.map || !state.coordsReady) return;
    state.layer.clearLayers();
    state.markers.clear();

    const locations = [];
    for (const place of state.matching) {
      const point = state.coords.get(normalize(place.city));
      if (!validCoordinate(point)) continue;
      locations.push({
        place,
        position: [Number(point.latitude), Number(point.longitude)]
      });
    }

    if (!state.matching.length) {
      setStatus("No destinations match your search.");
      return;
    }
    if (!locations.length) {
      setStatus("City locations are unavailable. Use the searchable directory.");
      return;
    }

    if (recenter) {
      // Only an explicit search or View all recenters the map.
      const bounds = L.latLngBounds(locations.map(item => item.position));
      if (locations.length === 1) {
        state.map.setView(locations[0].position, 9, {animate: false});
      } else {
        state.map.fitBounds(bounds.pad(.16), {
          maxZoom: 7,
          animate: false,
          padding: [38, 38]
        });
      }
    }

    for (const item of locations) {
      const marker = makeMarker(item.place, item.position);
      marker.addTo(state.layer);
      state.markers.set(markerKey(item.place), marker);
    }

    if (!state.tilesUnavailable) {
      setStatus(
        locations.length + " destinations available. "
        + "Select a teal city pin, or move and zoom the map to explore."
      );
    }
  }

  async function loadCoordinates() {
    try {
      const response = await fetch(apiRoot + "/website/destination-coordinates", {
        headers: {Accept: "application/json"},
        cache: "default"
      });
      if (!response.ok) throw new Error("Coordinates API returned " + response.status);
      const data = await response.json();
      const coordinates = data && data.coordinates;
      if (!coordinates || typeof coordinates !== "object") throw new Error("No city coordinates");
      for (const [city, position] of Object.entries(coordinates)) {
        if (validCoordinate(position)) state.coords.set(normalize(city), position);
      }
      if (!state.coords.size) throw new Error("No usable coordinates");
      state.coordsReady = true;
      paintMarkers(false);
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
        // Open at a readable Eastern Mediterranean / Egypt regional scale,
        // rather than forcing the visitor to click a clustered number.
        center: [33, 29],
        zoom: window.matchMedia("(max-width: 760px)").matches ? 4.5 : 5.5,
        zoomSnap: .25,
        minZoom: 2,
        maxZoom: 14,
        scrollWheelZoom: false,
        worldCopyJump: false,
        maxBounds: [[-84, -179.9], [84, 179.9]],
        maxBoundsViscosity: .85,
        zoomControl: false
      });
      L.control.zoom({position: "bottomright"}).addTo(state.map);
      state.layer = L.layerGroup().addTo(state.map);
      // Markers are geographical points, so Leaflet maintains their correct
      // position automatically during drag and zoom (no regrouping required).
      makeTiles();

      // Leaflet must recalculate the viewport if its panel changes size.
      // The observer handles responsive layout and browser zoom changes.
      const refreshSize = () => {
        if (!state.map || !mapElement.getBoundingClientRect().width) return;
        state.map.invalidateSize({pan: false, animate: false});
      };
      if ("ResizeObserver" in window) {
        state.resizeObserver = new ResizeObserver(refreshSize);
        state.resizeObserver.observe(mapElement);
      }
      window.addEventListener("resize", refreshSize, {passive: true});
      document.addEventListener("visibilitychange", () => {
        if (!document.hidden) requestAnimationFrame(refreshSize);
      });
      requestAnimationFrame(refreshSize);
      state.map.whenReady(refreshSize);
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
      // Initial directory/API updates must not override the detailed first view.
      // Explicit search results should focus the matching locations.
      const query = document.getElementById("browseQuery")?.value.trim() || "";
      paintMarkers(Boolean(query));
    });

    document.getElementById("discoveryReset")?.addEventListener("click", () => {
      const input = document.getElementById("browseQuery");
      if (input) {
        input.value = "";
        input.dispatchEvent(new Event("input", {bubbles: true}));
      }
      // Unlike clearing the search manually, View all intentionally fits
      // every available destination into the viewport.
      paintMarkers(true);
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