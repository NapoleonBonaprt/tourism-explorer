/* WanderClimate / VISTA EXPERIENCE
   Lightweight progressive enhancement. No changes to API/itinerary logic. */
(() => {
  "use strict";
  const reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const page = document.body.dataset.page || "home";

  function scrollProgress() {
    const bar = document.getElementById("vista-progress");
    if (!bar) return;
    const doc = document.documentElement;
    const max = Math.max(1, doc.scrollHeight - window.innerHeight);
    const fraction = Math.min(1, Math.max(0, window.scrollY / max));
    bar.style.transform = "scaleX(" + fraction + ")";
  }

  function initReveal() {
    if (reduced || !("IntersectionObserver" in window)) return;
    const obs = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          entry.target.classList.add("vista-visible");
          obs.unobserve(entry.target);
        }
      }
    }, {rootMargin:"0px 0px -30px 0px",threshold:.06});
    const seen = new WeakSet();
    function register() {
      const selector = page === "home"
        ? ".home-intro,.section-heading,.place,.browse-head,#analytics .steps>div,#how .steps>div,.browse-place"
        : ".page-heading,.metric,.card,.day-card,.dest-card,.attraction-card";
      document.querySelectorAll(selector).forEach(element => {
        if (seen.has(element)) return;
        seen.add(element);
        if (!element.getBoundingClientRect().width) return;
        if (element.getBoundingClientRect().top < window.innerHeight * .93) return;
        element.classList.add("vista-reveal","vista-ready");
        obs.observe(element);
      });
    }
    register();
    const target = page === "home" ? document.querySelector("main") : document.getElementById("dashboardRoot");
    if (target && "MutationObserver" in window) {
      let scheduled = false;
      new MutationObserver(() => {
        if (scheduled) return;
        scheduled = true;
        requestAnimationFrame(() => {scheduled = false;register();});
      }).observe(target,{childList:true,subtree:true});
    }
  }

  function dockIcon(name) {
    const paths = {
      home:'<path d="m3 10 9-7 9 7v10H3z"/><path d="M9 20v-7h6v7"/>',
      climate:'<path d="M4 18v-5m5 5V7m5 11v-8m5 8V4"/><path d="M2 21h20"/>',
      explore:'<circle cx="12" cy="12" r="9"/><path d="m15 9-2 5-4 2 2-5z"/>',
      planner:'<rect x="3" y="4" width="18" height="17" rx="2"/><path d="M3 10h18M8 2v4m8-4v4m-9 9h3m-3 3h3"/>',
      adaptive:'<path d="M12 3a9 9 0 1 0 9 9"/><path d="M12 3v9l6 3M17 2h5v5"/>'
    };
    return '<svg viewBox="0 0 24 24" aria-hidden="true" stroke-linecap="round" stroke-linejoin="round">'+paths[name]+'</svg>';
  }

  function initMobileDock() {
    if (page === "home") return;
    const links = [
      ["home","Home","index.html"],
      ["climate","Climate","climate.html"],
      ["explore","Explore","explorer.html"],
      ["planner","Planner","planner.html"],
      ["adaptive","Trips","adaptive.html"]
    ];
    const dock = document.createElement("nav");
    dock.className = "vista-dock";
    dock.setAttribute("aria-label","Quick navigation");
    dock.innerHTML = links.map(([key,label,url]) =>
      '<a href="'+url+'"'+(key===page?' aria-current="page"':'')+'>'+dockIcon(key)+'<span>'+label+'</span></a>'
    ).join("");
    document.body.appendChild(dock);
  }

  function initBannerSubtitle() {
    const heading = document.querySelector(".page-heading");
    if (!heading) return;
    const subtitle = document.createElement("span");
    subtitle.className = "vista-signpost";
    subtitle.textContent = ({
      overview:"Discover the world through data",
      climate:"Every season has a story",
      explorer:"Find places beyond the ordinary",
      planner:"Turn inspiration into an adventure",
      adaptive:"Let the weather shape your journey"
    })[page] || "Your world, better explored";
    heading.appendChild(subtitle);
  }

  function init() {
    const progress = document.createElement("div");
    progress.id = "vista-progress";
    progress.setAttribute("aria-hidden","true");
    document.body.appendChild(progress);
    scrollProgress();
    window.addEventListener("scroll",scrollProgress,{passive:true});
    window.addEventListener("resize",scrollProgress,{passive:true});
    initMobileDock();
    initBannerSubtitle();
    initReveal();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded",init,{once:true});
  else init();
})();