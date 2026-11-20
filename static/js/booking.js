// HIGH 5 – Book a Trip page: seat picking, passenger count and booking summary
// (owner: Sam/Cross). Runs after high5.js.
// IMPORTANT: this only helps the passenger fill in the form. The server must
// check again that the seats are free, the passenger count is allowed and the
// total is fare × seats when the booking is saved (docs/DATABASE.md §4).
(() => {
  "use strict";

  const { $, $$ } = window.H5;
  const form = $("#h5Book");
  if (!form) return;

  const fare = Number(form.dataset.fare);
  const currency = form.dataset.currency || "";
  const maxPassengers = Number(form.dataset.maxPassengers) || 1;
  const paxInput = $("#b-pax");
  const seatsInput = $("#b-seats");
  const goBtn = $("#b-go");
  const paxRow = $(".h5-sum-pax");
  const seats = $$(".h5-seat[data-seat]");
  const previewMsg = $("[data-preview-msg]");
  let picked = [];

  const money = (n) => `${currency}${n.toFixed(2)}`;
  const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;
  // order seats the way people read them: 7A, 7B, 12C …
  const bySeat = (a, b) => parseInt(a, 10) - parseInt(b, 10) || a.slice(-1).localeCompare(b.slice(-1));
  const restart = (el, cls) => { el.classList.remove(cls); void el.offsetWidth; el.classList.add(cls); };

  function render() {
    const pax = Number(paxInput.value);
    seats.forEach((s) => {
      const mine = picked.includes(s.dataset.seat);
      s.classList.toggle("is-mine", mine);
      s.setAttribute("aria-pressed", String(mine));
    });

    const list = [...picked].sort(bySeat).join(", ");
    const missing = pax - picked.length;
    $("[data-selected]").textContent = list || "–";
    const seatsOut = $("[data-seats-summary]");
    seatsOut.textContent = !picked.length ? `Pick ${plural(pax, "seat")}`
      : missing > 0 ? `${list} · pick ${missing} more` : list;
    seatsOut.classList.toggle("is-pending", missing > 0);

    $("[data-pax]").textContent = pax;
    $$("[data-pax-label]").forEach((el) => { el.textContent = plural(pax, "passenger"); });
    $("[data-fare-line]").textContent = `${money(fare)} × ${pax}`;
    $("[data-total]").textContent = money(fare * pax);
    $("[data-pax-step='-1']").disabled = pax <= 1;
    $("[data-pax-step='1']").disabled = pax >= maxPassengers;

    seatsInput.value = picked.join(",");
    goBtn.disabled = missing !== 0;
  }

  seats.forEach((seat) => seat.addEventListener("click", () => {
    const code = seat.dataset.seat;
    if (picked.includes(code)) {
      picked = picked.filter((c) => c !== code);
    } else if (picked.length < Number(paxInput.value)) {
      picked.push(code);
    } else {
      // every passenger already has a seat: point at the passenger count
      restart(seat, "is-refused");
      restart(paxRow, "is-flash");
      return;
    }
    render();
  }));

  $$("[data-pax-step]").forEach((btn) => btn.addEventListener("click", () => {
    const pax = Math.min(maxPassengers, Math.max(1, Number(paxInput.value) + Number(btn.dataset.paxStep)));
    paxInput.value = pax;
    if (picked.length > pax) picked = picked.slice(0, pax); // drop the most recent picks
    render();
  }));

  form.addEventListener("submit", (e) => {
    if (form.dataset.preview === "true") {
      // sample trip: there is nothing real to book yet
      e.preventDefault();
      previewMsg.hidden = false;
    }
  });

  render();
})();
