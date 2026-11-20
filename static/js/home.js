// HIGH 5 – homepage-only interactions (owner: Cross). Runs after high5.js,
// which already handles the nav, search bar, smooth scrolling and ripples.
// The seat map / ticket here is a demo that saves nothing.
(() => {
  "use strict";

  const { reduceMotion, $, $$ } = window.H5;
  document.body.classList.add("h5-js"); // CSS only hides reveal elements when JS runs

  /* ---------- scroll: progress bar, back-to-top, parallax ---------- */
  const progress = $(".h5-progress");
  const topBtn = $(".h5-top");
  const heroCopy = $(".h5-hero-copy");
  const parallax = $$(".h5-parallax");
  let ticking = false;
  function onScroll() {
    const y = window.scrollY;
    const max = document.documentElement.scrollHeight - window.innerHeight;
    progress.style.setProperty("--p", max > 0 ? (y / max).toFixed(4) : 0);
    topBtn.classList.toggle("is-shown", y > 700);
    if (!reduceMotion && y < window.innerHeight * 1.2) {
      parallax.forEach((g) => g.setAttribute("transform", `translate(0 ${(y * g.dataset.speed).toFixed(1)})`));
      heroCopy.style.transform = `translateY(${y * 0.25}px)`;
      heroCopy.style.opacity = Math.max(0, 1 - y / 600);
    }
    ticking = false;
  }
  window.addEventListener("scroll", () => {
    if (!ticking) { ticking = true; requestAnimationFrame(onScroll); }
  }, { passive: true });
  onScroll();
  topBtn.addEventListener("click", () => window.scrollTo({ top: 0, behavior: reduceMotion ? "auto" : "smooth" }));

  /* ---------- hero scene: show a closer, centred view on tablets and phones ---------- */
  const art = $(".h5-hero-art");
  const scene = art && $("svg", art);
  if (scene && art.dataset.viewboxMobile) {
    const wide = { box: scene.getAttribute("viewBox"), fit: scene.getAttribute("preserveAspectRatio") };
    const narrow = window.matchMedia("(max-width: 991.98px)");
    const frame = () => {
      scene.setAttribute("viewBox", narrow.matches ? art.dataset.viewboxMobile : wide.box);
      scene.setAttribute("preserveAspectRatio", narrow.matches ? "xMidYMax slice" : wide.fit);
    };
    narrow.addEventListener("change", frame);
    frame();
  }

  /* ---------- reveal on scroll ---------- */
  const revealObserver = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      const el = entry.target;
      el.classList.add("is-visible");
      revealObserver.unobserve(el);
      // after the entrance, drop the stagger delay so hover effects react instantly
      const delay = parseFloat(getComputedStyle(el).transitionDelay) * 1000 || 0;
      setTimeout(() => { el.style.transitionDelay = "0ms"; }, delay + 900);
    });
  }, { threshold: 0.15, rootMargin: "0px 0px -40px 0px" });
  $$(".h5-reveal").forEach((el) => revealObserver.observe(el));

  /* ---------- route cards: cursor glow ----------
     The cards are plain links to the trip search. Logged-out visitors are sent
     to the login page by the server (bookings.views.trip_search), not by JS. */
  $$(".h5-route").forEach((card) => {
    card.addEventListener("pointermove", (e) => {
      const r = card.getBoundingClientRect();
      card.style.setProperty("--mx", `${e.clientX - r.left}px`);
      card.style.setProperty("--my", `${e.clientY - r.top}px`);
    });
  });

  /* ---------- "how it works": steps light up one after another ---------- */
  const steps = $("#h5Steps");
  if (steps) {
    const items = $$(".h5-step", steps);
    let idx = 0;
    let timer = null;
    const show = (i) => items.forEach((s, j) => s.classList.toggle("is-on", j === i));
    const start = () => {
      if (timer) return;
      show(idx);
      if (!reduceMotion) timer = setInterval(() => { idx = (idx + 1) % items.length; show(idx); }, 2500);
    };
    const stop = () => { clearInterval(timer); timer = null; };
    items.forEach((s, i) => s.addEventListener("mouseenter", () => { stop(); idx = i; show(i); }));
    steps.addEventListener("mouseleave", start);
    new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) { steps.classList.add("is-visible"); start(); } else { stop(); }
    }, { threshold: 0.4 }).observe(steps);
  }

  /* ---------- demo seat map + live ticket ---------- */
  const stage = $("#h5Stage");
  const mini = $("#h5Mini");
  if (stage && mini) {
    const FARE = 24; // matches the first sample route; demo only
    const rows = ["A", "B", null, "C", "D"]; // null = aisle
    const taken = new Set(["1A", "1B", "2C", "3A", "3D", "4B", "5C", "5D", "6A", "8B", "8C", "9A", "9D", "10C", "11A", "11B"]);
    const selected = new Set(["7A", "7B"]);
    const seatsOut = $("#h5TSeats");
    const totalOut = $("#h5TTotal");
    let i = 0;

    rows.forEach((letter) => {
      if (!letter) { const gap = document.createElement("span"); gap.className = "h5-ms-gap"; mini.appendChild(gap); return; }
      for (let n = 1; n <= 11; n += 1) {
        const id = `${n}${letter}`;
        const b = document.createElement("button");
        b.type = "button";
        b.className = "h5-ms";
        b.style.setProperty("--i", i++);
        b.dataset.seat = id;
        if (taken.has(id)) { b.classList.add("is-taken"); b.disabled = true; b.setAttribute("aria-label", `Seat ${id}, taken`); }
        else {
          b.setAttribute("aria-label", `Seat ${id}`);
          b.setAttribute("aria-pressed", String(selected.has(id)));
          if (selected.has(id)) b.classList.add("is-sel");
        }
        mini.appendChild(b);
      }
    });

    const order = (a, b) => parseInt(a, 10) - parseInt(b, 10) || a.slice(-1).localeCompare(b.slice(-1));
    const bump = (el, text) => { el.textContent = text; el.classList.remove("is-changed"); void el.offsetWidth; el.classList.add("is-changed"); };
    mini.addEventListener("click", (e) => {
      const b = e.target.closest(".h5-ms");
      if (!b || b.disabled) return;
      const id = b.dataset.seat;
      if (selected.has(id)) selected.delete(id); else selected.add(id);
      b.classList.toggle("is-sel", selected.has(id));
      b.setAttribute("aria-pressed", String(selected.has(id)));
      bump(seatsOut, selected.size ? [...selected].sort(order).join(", ") : "–");
      bump(totalOut, (FARE * selected.size).toFixed(2));
    });

    new IntersectionObserver(([entry], obs) => {
      if (entry.isIntersecting) { stage.classList.add("is-visible"); obs.disconnect(); }
    }, { threshold: 0.3 }).observe(stage);

    const bars = $("#h5Bars");
    for (let k = 0; k < 28; k += 1) bars.appendChild(document.createElement("i"));

    // 3D tilt + light sheen following the pointer
    const ticket = $("#h5Ticket");
    if (!reduceMotion && window.matchMedia("(hover: hover)").matches) {
      stage.addEventListener("pointermove", (e) => {
        const r = ticket.getBoundingClientRect();
        const x = (e.clientX - r.left) / r.width - 0.5;
        const y = (e.clientY - r.top) / r.height - 0.5;
        ticket.style.setProperty("--ry", `${(x * 14).toFixed(2)}deg`);
        ticket.style.setProperty("--rx", `${(-y * 14).toFixed(2)}deg`);
        ticket.style.setProperty("--gx", `${((x + 0.5) * 100).toFixed(1)}%`);
        ticket.style.setProperty("--gy", `${((y + 0.5) * 100).toFixed(1)}%`);
      });
      stage.addEventListener("pointerleave", () => {
        ["--rx", "--ry"].forEach((p) => ticket.style.setProperty(p, "0deg"));
      });
    }
  }

  /* ---------- FAQ accordion (one open at a time) ---------- */
  const faqItems = $$(".h5-faq-item");
  faqItems.forEach((item) => {
    const btn = $("button", item);
    btn.addEventListener("click", () => {
      const willOpen = !item.classList.contains("is-open");
      faqItems.forEach((other) => { other.classList.remove("is-open"); $("button", other).setAttribute("aria-expanded", "false"); });
      item.classList.toggle("is-open", willOpen);
      btn.setAttribute("aria-expanded", String(willOpen));
    });
  });
})();
