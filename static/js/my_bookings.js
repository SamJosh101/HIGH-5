// HIGH 5 – My Bookings tabs (Upcoming / Past & cancelled).
// Without JavaScript both lists stay visible. "#history" (the nav's History
// link) opens the second tab.
(() => {
  "use strict";

  const box = document.querySelector("[data-trip-tabs]");
  if (!box) return;
  const tabs = Array.from(box.querySelectorAll("[role='tab']"));

  // Top menu (desktop pill and mobile menu): "History" is lit on the past tab,
  // "My Bookings" on the upcoming tab. The server can't see "#history", so JS does it.
  const navLinks = Array.from(document.querySelectorAll(".h5-pill-nav a, .h5-mobile-menu a"))
    .filter((a) => a.pathname === location.pathname);

  function markNav(panelId) {
    navLinks.forEach((a) => {
      const on = (a.hash === "#history") === (panelId === "history");
      a.classList.toggle("is-active", on);
      if (on) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
    });
    window.dispatchEvent(new Event("h5:navchange"));
  }

  function show(panelId, focus) {
    tabs.forEach((tab) => {
      const on = tab.getAttribute("aria-controls") === panelId;
      tab.setAttribute("aria-selected", String(on));
      tab.tabIndex = on ? 0 : -1;
      document.getElementById(tab.getAttribute("aria-controls")).hidden = !on;
      if (on && focus) tab.focus();
    });
    markNav(panelId);
  }

  tabs.forEach((tab, i) => {
    tab.addEventListener("click", () => {
      show(tab.getAttribute("aria-controls"));
      history.replaceState(null, "", tab.getAttribute("aria-controls") === "history" ? "#history" : location.pathname);
    });
    // arrow keys move between tabs (WAI-ARIA tabs pattern)
    tab.addEventListener("keydown", (e) => {
      if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
      const next = tabs[(i + (e.key === "ArrowRight" ? 1 : tabs.length - 1)) % tabs.length];
      show(next.getAttribute("aria-controls"), true);
    });
  });

  const fromHash = () => show(location.hash === "#history" ? "history" : "upcoming");
  window.addEventListener("hashchange", fromHash);
  fromHash();
})();
