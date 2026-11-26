// HIGH 5 – My Bookings tabs (Upcoming / Past & cancelled).
// Without JavaScript both lists stay visible. "#history" (the nav's History
// link) opens the second tab.
(() => {
  "use strict";

  const box = document.querySelector("[data-trip-tabs]");
  if (!box) return;
  const tabs = Array.from(box.querySelectorAll("[role='tab']"));

  function show(panelId, focus) {
    tabs.forEach((tab) => {
      const on = tab.getAttribute("aria-controls") === panelId;
      tab.setAttribute("aria-selected", String(on));
      tab.tabIndex = on ? 0 : -1;
      document.getElementById(tab.getAttribute("aria-controls")).hidden = !on;
      if (on && focus) tab.focus();
    });
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
