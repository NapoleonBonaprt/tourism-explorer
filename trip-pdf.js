/* Client-side PDF writer for WanderClimate Adaptive Itinerary.
 * Uses the plan already loaded on the page, so a user can download it even
 * if the backend becomes unreachable after the itinerary was built.
 */
(() => {
  "use strict";

  function plain(value) {
    return String(value === null || value === undefined ? "" : value)
      .replace(/[\u2013\u2014]/g, "-")
      .replace(/[\u2018\u2019]/g, "'")
      .replace(/[\u201C\u201D]/g, '"')
      .replace(/\u2022/g, "-")
      .replace(/\s+/g, " ").trim();
  }

  function fileSlug(value) {
    return plain(value).replace(/[^a-z0-9_-]+/gi, "-").replace(/^-|-$/g, "").slice(0,65) || "Trip";
  }

  function available() {
    return Boolean(window.jspdf && typeof window.jspdf.jsPDF === "function");
  }

  function download(plan) {
    if (!available()) {
      throw new Error("The browser PDF library is unavailable.");
    }
    if (!plan || !Array.isArray(plan.days) || !plan.days.length) {
      throw new Error("Build an itinerary before downloading it.");
    }

    const pdf = new window.jspdf.jsPDF({
      orientation: "portrait", unit: "mm", format: "a4", compress: true
    });
    const PAGE_WIDTH = 210;
    const PAGE_HEIGHT = 297;
    const MARGIN = 17;
    const CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN;
    const BOTTOM = PAGE_HEIGHT - 24;
    const colors = {
      dark: [30, 43, 34],
      green: [63, 107, 74],
      teal: [65, 124, 130],
      muted: [83, 102, 90],
      cream: [241, 246, 240],
      white: [255, 255, 255],
      line: [217, 231, 220],
      amber: [196, 146, 59],
    };
    const paint = (rgb, method) => pdf[method](...rgb);
    let y = 0;

    function header() {
      paint(colors.dark, "setFillColor");
      pdf.rect(0, 0, PAGE_WIDTH, 35, "F");
      paint(colors.white, "setTextColor");
      pdf.setFont("helvetica", "bold");
      pdf.setFontSize(16);
      pdf.text("WANDERCLIMATE", MARGIN, 19);
      pdf.setFont("helvetica", "normal");
      pdf.setFontSize(8);
      pdf.text("CLIMATE-DRIVEN TOURISM INTELLIGENCE", MARGIN, 26);
      y = 47;
    }

    function page() {
      pdf.addPage();
      header();
    }

    function room(height) {
      if (y + height > BOTTOM) page();
    }

    function paragraph(text, x=MARGIN, width=CONTENT_WIDTH, fontSize=10,
                       color=colors.dark, lineHeight=5) {
      pdf.setFont("helvetica", "normal");
      pdf.setFontSize(fontSize);
      paint(color, "setTextColor");
      const lines = pdf.splitTextToSize(plain(text), width);
      if (!lines.length) return;
      for (const line of lines) {
        room(lineHeight + 2);
        pdf.text(String(line), x, y);
        y += lineHeight;
      }
    }

    function heading(text) {
      const lines = pdf.splitTextToSize(plain(text), CONTENT_WIDTH);
      const height = Math.max(1, lines.length) * 9 + 6;
      room(height + 6);
      paint(colors.cream, "setFillColor");
      pdf.roundedRect(MARGIN, y - 7, CONTENT_WIDTH, height, 2.5, 2.5, "F");
      paint(colors.green, "setTextColor");
      pdf.setFont("helvetica", "bold");
      pdf.setFontSize(13);
      for (const line of lines) {
        pdf.text(String(line), MARGIN + 4, y);
        y += 9;
      }
      y += 3;
    }

    function note(text) {
      y += 1;
      paragraph(text, MARGIN, CONTENT_WIDTH, 9, colors.muted, 4.6);
      y += 3;
    }

    header();
    paint(colors.dark, "setTextColor");
    pdf.setFont("helvetica", "bold");
    pdf.setFontSize(22);
    const tripName = `Your trip to ${plain(plan.city || "your destination")}`;
    const tripLines = pdf.splitTextToSize(tripName, CONTENT_WIDTH);
    tripLines.forEach(line => { room(11); pdf.text(line, MARGIN, y); y += 11; });
    note(`${plan.days.length} day(s) - weather-aware travel plan`);
    note(`Downloaded ${new Date().toLocaleDateString("en-GB", {day:"numeric",month:"long",year:"numeric"})}`);
    if (plan.warning) {
      note("Planning note: " + plan.warning);
    }

    for (const day of plan.days) {
      y += 7;
      heading(`DAY ${day.number}  |  ${day.date}  |  ${plain(day.day_type).toUpperCase()}`);
      const weather = day.weather || {};
      note([
        `Temperature: ${weather.temperature_2m_max === null || weather.temperature_2m_max === undefined ? "N/A" : Number(weather.temperature_2m_max).toFixed(1) + " C"}`,
        `Rain: ${weather.precipitation_sum === null || weather.precipitation_sum === undefined ? "N/A" : Number(weather.precipitation_sum).toFixed(1) + " mm"}`,
        `Wind: ${weather.wind_speed_10m_max === null || weather.wind_speed_10m_max === undefined ? "N/A" : Number(weather.wind_speed_10m_max).toFixed(1) + " km/h"}`,
      ].join("     |     "));

      if (!Array.isArray(day.stops) || !day.stops.length) {
        paragraph("No attractions available for this day.");
        continue;
      }
      for (const stop of day.stops) {
        room(18);
        paint(colors.green, "setTextColor");
        pdf.setFont("helvetica", "bold");
        pdf.setFontSize(10.5);
        const lines = pdf.splitTextToSize(
          `${stop.order}. ${plain(stop.name)}`, CONTENT_WIDTH - 8);
        for (const line of lines) {
          room(5.5);
          pdf.text(String(line), MARGIN + 2, y);
          y += 5.5;
        }
        paragraph(`${plain(stop.category)} | ${plain(stop.slot)}`,
                  MARGIN + 4, CONTENT_WIDTH - 8, 9, colors.muted, 4.5);
        if (Number.isFinite(Number(stop.lat)) && Number.isFinite(Number(stop.lon))) {
          paragraph(`Coordinates: ${Number(stop.lat).toFixed(5)}, ${Number(stop.lon).toFixed(5)}`,
                    MARGIN + 4, CONTENT_WIDTH - 8, 8.3, colors.muted, 4.3);
        }
        y += 3;
      }
    }

    if (Array.isArray(plan.changes) && plan.changes.length) {
      y += 7;
      heading("FORECAST RECHECK: CHANGES TO THE PLAN");
      for (const change of plan.changes) {
        paragraph(`${plain(change.date)}: ${plain(change.from)} to ${plain(change.to)}. ${plain(change.reason)}`,
                  MARGIN + 2, CONTENT_WIDTH - 4, 9.2, colors.dark, 4.7);
      }
    }

    y += 7;
    heading("ROUTE INFORMATION");
    paragraph("The map connects attractions with straight lines to show stop order. These are not driving, walking or public transport directions, and do not represent travel time, road access or traffic.",
              MARGIN + 2, CONTENT_WIDTH - 4, 9.4, colors.dark, 5);
    y += 3;
    paragraph("Weather forecasts can change. Check current conditions and attraction opening hours before travel.",
              MARGIN + 2, CONTENT_WIDTH - 4, 9, colors.muted, 5);

    const total = pdf.internal.getNumberOfPages();
    for (let number=1; number<=total; number++) {
      pdf.setPage(number);
      paint(colors.line, "setDrawColor");
      pdf.line(MARGIN, PAGE_HEIGHT - 16, PAGE_WIDTH - MARGIN, PAGE_HEIGHT - 16);
      pdf.setFont("helvetica", "normal");
      pdf.setFontSize(8);
      paint(colors.muted, "setTextColor");
      pdf.text("WanderClimate | Forecast-informed travel plan", MARGIN, PAGE_HEIGHT - 10);
      pdf.text(`Page ${number} of ${total}`, PAGE_WIDTH - MARGIN, PAGE_HEIGHT - 10,
               {align:"right"});
    }

    pdf.save(`WanderClimate-${fileSlug(plan.city)}-Itinerary.pdf`);
  }

  window.WanderClimatePDF = {available, download};
})();
