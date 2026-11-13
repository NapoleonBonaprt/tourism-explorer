/* Shared WanderClimate theme preference, loaded early to prevent a flash. */
(() => {
  "use strict";
  const KEY = "wanderclimate-theme";
  const root = document.documentElement;
  const media = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;

  function savedTheme() {
    try {
      const value = localStorage.getItem(KEY);
      return value === "dark" || value === "light" ? value : null;
    } catch (_) {
      return null;
    }
  }

  function setTheme(theme, persist = false) {
    const next = theme === "dark" ? "dark" : "light";
    root.dataset.theme = next;
    root.style.colorScheme = next;
    if (persist) {
      try { localStorage.setItem(KEY, next); } catch (_) { /* private mode */ }
    }
    document.querySelectorAll("[data-theme-toggle]").forEach(button => {
      const dark = next === "dark";
      button.setAttribute("aria-pressed", String(dark));
      button.setAttribute("aria-label", dark ? "Switch to light mode" : "Switch to dark mode");
      button.setAttribute("title", dark ? "Switch to light mode" : "Switch to dark mode");
      const icon = button.querySelector("[data-theme-icon]");
      const label = button.querySelector("[data-theme-label]");
      if (icon) icon.textContent = dark ? "☀" : "☾";
      if (label) label.textContent = dark ? "Light mode" : "Dark mode";
    });
    document.dispatchEvent(new CustomEvent("wanderclimate:themechange", { detail: { theme: next } }));
  }

  setTheme(savedTheme() || (media && media.matches ? "dark" : "light"));

  document.addEventListener("click", event => {
    const button = event.target.closest("[data-theme-toggle]");
    if (!button) return;
    setTheme(root.dataset.theme === "dark" ? "light" : "dark", true);
  });

  document.addEventListener("DOMContentLoaded", () => setTheme(root.dataset.theme));
  if (media) {
    const handleSystemTheme = event => {
      if (!savedTheme()) setTheme(event.matches ? "dark" : "light");
    };
    if (media.addEventListener) media.addEventListener("change", handleSystemTheme);
    else if (media.addListener) media.addListener(handleSystemTheme);
  }
})();
