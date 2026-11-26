// HIGH 5 – site-wide JavaScript (owner: Cross). Loaded on every page.
// IMPORTANT: JavaScript checks are for convenience. All real validation
// (seat availability, prices, permissions) happens on the server.
(() => {
  "use strict";

  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  window.H5 = { reduceMotion, $, $$ };

  /* ---------- nav: solid background after scrolling ---------- */
  const nav = $("#h5Nav");
  if (nav) {
    const update = () => nav.classList.toggle("is-scrolled", window.scrollY > 20);
    window.addEventListener("scroll", update, { passive: true });
    update();
  }

  /* ---------- nav pill: glider follows the hovered link ---------- */
  const pill = $(".h5-pill-nav");
  if (pill) {
    const glider = $(".h5-pill-glider", pill);
    const moveTo = (link) => {
      if (!link) { glider.style.opacity = 0; return; }
      glider.style.width = `${link.offsetWidth}px`;
      glider.style.transform = `translateX(${link.offsetLeft}px)`;
      glider.style.opacity = 1;
    };
    const active = () => $("a.is-active", pill);
    $$("a", pill).forEach((l) => {
      l.addEventListener("mouseenter", () => moveTo(l));
      l.addEventListener("focus", () => moveTo(l));
    });
    pill.addEventListener("mouseleave", () => moveTo(active()));
    window.addEventListener("resize", () => moveTo(active()));
    window.addEventListener("load", () => moveTo(active()));
    window.addEventListener("h5:navchange", () => moveTo(active()));  // a page changed which link is active
    moveTo(active());
  }

  /* ---------- mobile menu ---------- */
  const burger = $(".h5-burger");
  const mobileMenu = $("#h5MobileMenu");
  const closeMobileMenu = () => {
    if (!burger) return;
    burger.setAttribute("aria-expanded", "false");
    mobileMenu.hidden = true;
  };
  burger?.addEventListener("click", () => {
    const open = burger.getAttribute("aria-expanded") === "true";
    burger.setAttribute("aria-expanded", String(!open));
    mobileMenu.hidden = open;
  });

  /* ---------- smooth scroll for links to a section on this page ---------- */
  document.addEventListener("click", (e) => {
    const a = e.target.closest("a[href*='#']");
    if (!a || a.pathname !== location.pathname || !a.hash) return;
    const target = document.getElementById(a.hash.slice(1));
    if (!target) return;
    e.preventDefault();
    closeMobileMenu();
    const changed = location.hash !== a.hash;
    history.replaceState(null, "", a.hash);
    // replaceState does not fire "hashchange"; send it so pages that react to the
    // hash (e.g. My Bookings: History opens the "Past & cancelled" tab) still do.
    if (changed) window.dispatchEvent(new HashChangeEvent("hashchange"));
    const top = target.getBoundingClientRect().top + window.scrollY - 80;
    window.scrollTo({ top, behavior: reduceMotion ? "auto" : "smooth" });
  });

  /* ---------- auto-close success messages ---------- */
  $$(".alert-success.alert-dismissible").forEach((el) => {
    setTimeout(() => window.bootstrap?.Alert.getOrCreateInstance(el).close(), 5000);
  });

  /* ---------- password fields: show / hide button ---------- */
  const eye = '<svg viewBox="0 0 24 24"><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></svg>';
  const eyeOff = '<svg viewBox="0 0 24 24"><path d="M3 3l18 18M10.6 5.1A10 10 0 0112 5c6.4 0 10 7 10 7a17 17 0 01-3.2 4.1M6.6 6.6A17 17 0 002 12s3.6 7 10 7a9.8 9.8 0 005.4-1.6"/><path d="M9.9 9.9a3 3 0 004.2 4.2"/></svg>';
  $$("input[type='password'].form-control").forEach((input) => {
    const wrap = document.createElement("div");
    wrap.className = "h5-pw";
    input.parentNode.insertBefore(wrap, input);
    wrap.appendChild(input);
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "h5-pw-toggle";
    btn.setAttribute("aria-label", "Show password");
    btn.innerHTML = eye;
    btn.addEventListener("click", () => {
      const show = input.type === "password";
      input.type = show ? "text" : "password";
      btn.innerHTML = show ? eyeOff : eye;
      btn.setAttribute("aria-label", show ? "Hide password" : "Show password");
    });
    wrap.appendChild(btn);
  });

  /* ---------- trip search bar (partials/search_bar.html) ---------- */
  const form = $("#h5Search");
  const flashField = (input) => {
    const field = input.closest(".h5-field");
    field.classList.remove("is-filled");
    void field.offsetWidth; // restart the CSS animation
    field.classList.add("is-filled");
  };
  window.H5.flashField = flashField;
  if (form) {
    const origin = $("#s-origin");
    const dest = $("#s-dest");
    const date = $("#s-date");
    const pax = $("#s-pax");
    const today = new Date();
    const iso = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
    date.min = iso;
    if (!date.value) date.value = iso;

    // homepage only: friendly date label under the field ("Today · Thu, 19 Nov")
    const dateHint = $("#s-date-hint");
    if (dateHint) {
      const describeDate = () => {
        if (!date.value) { dateHint.textContent = "Pick a day"; return; }
        const d = new Date(`${date.value}T00:00`);
        const diff = Math.round((d - new Date(`${iso}T00:00`)) / 86400000);
        const label = d.toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" });
        dateHint.textContent = diff === 0 ? `Today · ${label}` : diff === 1 ? `Tomorrow · ${label}` : label;
      };
      date.addEventListener("change", describeDate);
      describeDate();
    }

    let turns = 0;
    $(".h5-swap", form).addEventListener("click", (e) => {
      turns += 1;
      e.currentTarget.style.setProperty("--r", `${turns * 180}deg`);
      [origin.value, dest.value] = [dest.value, origin.value];
      [origin, dest].forEach(flashField);
    });

    $$(".h5-stepper button", form).forEach((b) => b.addEventListener("click", () => {
      pax.value = Math.min(10, Math.max(1, (parseInt(pax.value, 10) || 1) + Number(b.dataset.step)));
      flashField(pax);
    }));

    form.addEventListener("submit", (e) => {
      if (origin.value.trim() && origin.value.trim().toLowerCase() === dest.value.trim().toLowerCase()) {
        e.preventDefault();
        dest.setCustomValidity("Destination must be different from departure.");
        dest.reportValidity();
      }
    });
    dest.addEventListener("input", () => dest.setCustomValidity(""));
  }

  /* ---------- click ripple on buttons ---------- */
  if (!reduceMotion) {
    document.addEventListener("pointerdown", (e) => {
      const btn = e.target.closest(".h5-go, .h5-btn-white, .h5-btn-outline, .btn");
      if (!btn) return;
      const r = btn.getBoundingClientRect();
      const size = Math.max(r.width, r.height);
      const dot = document.createElement("span");
      dot.className = "h5-ripple";
      dot.style.cssText = `width:${size}px;height:${size}px;left:${e.clientX - r.left - size / 2}px;top:${e.clientY - r.top - size / 2}px`;
      btn.appendChild(dot);
      dot.addEventListener("animationend", () => dot.remove());
    });
  }

  /* ---------- verification code: digits only, never more than 6 ---------- */
  $$(".h5-code-input").forEach((input) => {
    const max = Number(input.getAttribute("maxlength")) || 6;
    // Let a pasted "251 070" or "Code: 251070" through first, then keep only the
    // first 6 digits (maxlength alone would cut before removing spaces/letters).
    input.removeAttribute("maxlength");
    input.addEventListener("input", () => {
      const digits = input.value.replace(/\D/g, "").slice(0, max);
      if (input.value !== digits) input.value = digits;
    });
  });
})();
