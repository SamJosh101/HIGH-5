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
  const passengerFields = $("#h5PassengerFields");

  let picked = [];

  // Same format as the server pages: ₦10,000 or ₦10,000.50 (display only).
  const money = (n) => {
    const kobo = Math.round(n * 100);
    return `${currency}${(kobo / 100).toLocaleString("en-US", {
      minimumFractionDigits: kobo % 100 ? 2 : 0, maximumFractionDigits: 2,
    })}`;
  };
  const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;
  // order seats the way people read them: 7A, 7B, 12C …
  const bySeat = (a, b) => parseInt(a, 10) - parseInt(b, 10) || a.slice(-1).localeCompare(b.slice(-1));
  const restart = (el, cls) => { el.classList.remove(cls); void el.offsetWidth; el.classList.add(cls); };

  function renderPassengerForms() {
    if (!passengerFields) return;
    const passengerCount = Number(paxInput.value);

    // Save existing values so changing count doesn't wipe typed fields
    const saved = Array.from(passengerFields.querySelectorAll(".h5-passenger-card")).map((card) => ({
      name: card.querySelector("[name='passenger_name']")?.value || "",
      phone: card.querySelector("[name='passenger_phone']")?.value || "",
      email: card.querySelector("[name='passenger_email']")?.value || "",
      me: card.querySelector(".h5-me-toggle")?.getAttribute("aria-pressed") === "true",
    }));

    passengerFields.innerHTML = "";

    for (let i = 1; i <= passengerCount; i++) {
      const prev = saved[i - 1] || { name: "", phone: "", email: "", me: false };
      const passengerCard = document.createElement("div");
      passengerCard.className = "h5-passenger-card";

      const seat = picked[i - 1];
      const seatChip = seats.length === 0
        ? ""
        : seat
          ? `<span class="h5-pax-seat">Seat ${seat}</span>`
          : `<span class="h5-pax-seat is-missing">Pick a seat</span>`;
      // Only Passenger 1 offers "I'm travelling": nothing is filled unless the
      // booker taps it, so booking for other people works as before.
      const meToggle = i === 1 && me.name
        ? `<button type="button" class="h5-me-toggle" aria-pressed="false">
             <i aria-hidden="true">✓</i><span>I'm travelling – use my details</span><em>Clear</em>
           </button>`
        : "";
      passengerCard.innerHTML = `
        <h3>Passenger ${i}${seatChip}</h3>
        ${meToggle}

        <div class="h5-form-group">
          <label for="passenger-name-${i}">Full name</label>
          <input
            type="text"
            id="passenger-name-${i}"
            name="passenger_name"
            placeholder="As on their ID"
            maxlength="150"
            autocomplete="off"
            required
          >
        </div>

        <div class="h5-form-row">
          <div class="h5-form-group">
            <label for="passenger-phone-${i}">Phone number</label>
            <input
              type="tel"
              id="passenger-phone-${i}"
              name="passenger_phone"
              placeholder="+234 801 234 5678"
              maxlength="16"
              autocomplete="off"
              required
            >
          </div>

          <div class="h5-form-group">
            <label for="passenger-email-${i}">Email (optional)</label>
            <input
              type="email"
              id="passenger-email-${i}"
              name="passenger_email"
              placeholder="For their own ticket"
              autocomplete="off"
            >
          </div>
        </div>
      `;

      passengerFields.appendChild(passengerCard);

      passengerCard.querySelector("[name='passenger_name']").value = prev.name;
      passengerCard.querySelector("[name='passenger_phone']").value = prev.phone;
      passengerCard.querySelector("[name='passenger_email']").value = prev.email;

      const toggle = passengerCard.querySelector(".h5-me-toggle");
      if (toggle) {
        toggle.setAttribute("aria-pressed", String(prev.me));
        toggle.addEventListener("click", () => useMyDetails(passengerCard, toggle));
      }
    }
  }

  // The logged-in user's own details (from the page), for "I'm travelling".
  const me = {
    name: form.dataset.meName || "",
    phone: form.dataset.mePhone || "",
  };

  function useMyDetails(card, toggle) {
    const on = toggle.getAttribute("aria-pressed") !== "true";
    const name = card.querySelector("[name='passenger_name']");
    const phone = card.querySelector("[name='passenger_phone']");
    toggle.setAttribute("aria-pressed", String(on));
    name.value = on ? me.name : "";
    phone.value = on ? me.phone : "";
    // no phone on the account yet: let them type it
    if (on && !me.phone) phone.focus();
    if (!on) name.focus();
  }

  function render() {
    const pax = Number(paxInput.value);
    seats.forEach((s) => {
      const mine = picked.includes(s.dataset.seat);
      s.classList.toggle("is-mine", mine);
      s.setAttribute("aria-pressed", String(mine));
    });

    const list = [...picked].sort(bySeat).join(", ");
    const missing = seats.length > 0
      ? pax - picked.length
      : 0;
    $("[data-selected]").textContent = list || "–";
    const seatsOut = $("[data-seats-summary]");
    seatsOut.textContent = seats.length === 0
      ? "Seat numbers assigned after booking"
      : !picked.length
        ? `Pick ${plural(pax, "seat")}`
        : missing > 0
          ? `${list} · pick ${missing} more`
          : list;
    seatsOut.classList.toggle("is-pending", missing > 0);

    $("[data-pax]").textContent = pax;
    renderPassengerForms();

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

  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    // Sample trips are for preview only.
    if (form.dataset.preview === "true") {
      if (previewMsg) {
        previewMsg.hidden = false;
      }
      return;
    }

    // Let the browser check required passenger fields.
    if (!form.reportValidity()) {
      return;
    }

    const passengerCards = Array.from(
      passengerFields.querySelectorAll(".h5-passenger-card")
    );

    const passengers = passengerCards.map((card, index) => ({
      full_name: card.querySelector("[name='passenger_name']").value.trim(),
      phone: card.querySelector("[name='passenger_phone']").value.trim(),
      email: card.querySelector("[name='passenger_email']").value.trim(),
      seat: picked[index] || ""
    }));

    if (seats.length > 0 && picked.length !== passengers.length) {
      showMessage("Pick a seat for every passenger on the seat map.", true);
      return;
    }

    // Confirm that every passenger has the required details.
    if (
      passengers.length < 1 ||
      passengers.some((p) => !p.full_name || !p.phone)
    ) {
      showMessage("Please complete the name and phone number for every passenger.", true);
      return;
    }

    const csrfToken = form.querySelector(
      "[name='csrfmiddlewaretoken']"
    )?.value;

    const scheduleId = Number(form.dataset.scheduleId);
    const createUrl = form.dataset.createUrl;

    if (!csrfToken || !scheduleId || !createUrl) {
      showMessage("The booking form is missing required information. Please refresh the page.", true);
      return;
    }

    const originalButtonText = goBtn.textContent;

    goBtn.disabled = true;
    goBtn.textContent = "Processing booking...";

    try {
      const response = await fetch(createUrl, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "Accept": "application/json",
          "X-CSRFToken": csrfToken
        },
        body: JSON.stringify({
          schedule_id: scheduleId,
          passengers: passengers
        })
      });

      const data = await response.json();

      if (!response.ok) {
        markSeatsTaken(data && data.taken_seats);
        const errorMessage = formatApiError(data && data.booking ? { booking: data.booking } : data);
        throw new Error(errorMessage);
      }

      goBtn.textContent = "Booking confirmed";
      goBtn.disabled = true;

      // Show the virtual ticket ("You're booked"), drawn by the server so it
      // matches the ticket page and the email. Older responses without a
      // ticket_url fall back to the short in-page confirmation.
      if (data.ticket_url) {
        window.location.assign(`${data.ticket_url}?booked=1`);
      } else {
        renderBookingConfirmation(data);
      }

    } catch (error) {
      showMessage(
        error.message || "Something went wrong. Please try again.",
        true
      );

      goBtn.disabled = false;
      goBtn.textContent = originalButtonText;
    }
  });

  function markSeatsTaken(codes) {
    if (!Array.isArray(codes) || !codes.length) return;
    codes.forEach((code) => {
      const seat = seats.find((s) => s.dataset.seat === code);
      if (!seat) return;
      seat.classList.add("is-taken");
      seat.disabled = true;
      seat.setAttribute("aria-label", `Seat ${code}, booked`);
      seat.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 7l10 10M17 7L7 17"/></svg>';
    });
    picked = picked.filter((code) => !codes.includes(code));
    render();
  }

  function showMessage(message, isError) {
    let messageBox = document.querySelector("#bookingMessage");

    if (!messageBox) {
      messageBox = document.createElement("div");
      messageBox.id = "bookingMessage";
      messageBox.setAttribute("role", "status");
      messageBox.setAttribute("aria-live", "polite");

      form.parentNode.insertBefore(messageBox, form);
    }

    messageBox.textContent = message;
    messageBox.className = isError
      ? "h5-booking-error"
      : "h5-booking-success";

    messageBox.scrollIntoView({
      behavior: "smooth",
      block: "center"
    });
  }

  function formatApiError(data) {
    if (!data || typeof data !== "object") {
      return "The booking could not be completed.";
    }

    const messages = [];

    function collectErrors(value) {
      if (typeof value === "string") {
        messages.push(value);
      } else if (Array.isArray(value)) {
        value.forEach(collectErrors);
      } else if (value && typeof value === "object") {
        Object.values(value).forEach(collectErrors);
      }
    }

    collectErrors(data);

    return messages.length
      ? messages.join(" ")
      : "The booking could not be completed. Please try again.";
  }

  function renderBookingConfirmation(booking) {
    const confirmation = document.createElement("section");

    confirmation.className = "h5-book-panel h5-booking-confirmation";
    confirmation.setAttribute("aria-labelledby", "bookingConfirmationTitle");

    const heading = document.createElement("h2");
    heading.id = "bookingConfirmationTitle";
    heading.textContent = "Booking confirmed!";

    const description = document.createElement("p");
    description.textContent = "Your booking has been created successfully.";

    const reference = document.createElement("p");
    const referenceLabel = document.createElement("strong");
    referenceLabel.textContent = "Booking reference: ";

    reference.append(
      referenceLabel,
      document.createTextNode(booking.booking_ref || "Unavailable")
    );

    const amount = document.createElement("p");
    const amountLabel = document.createElement("strong");
    amountLabel.textContent = "Total amount: ";

    amount.append(
      amountLabel,
      document.createTextNode(
        money(Number(booking.total_amount || 0))
      )
    );

    const status = document.createElement("p");
    status.textContent = `Booking status: ${booking.status || "CONFIRMED"}`;

    const passengerHeading = document.createElement("h3");
    passengerHeading.textContent = "Passenger details";

    const passengerList = document.createElement("ul");

    (booking.passengers || []).forEach((passenger) => {
      const item = document.createElement("li");
      item.textContent = `${passenger.full_name} — ${passenger.phone}${passenger.seat_number ? ` — Seat ${passenger.seat_number}` : ""}`;
      passengerList.appendChild(item);
    });

    const historyLink = document.createElement("a");
    historyLink.href = "/bookings/dashboard/";
    historyLink.textContent = "Go to passenger dashboard";
    historyLink.className = "h5-sum-go";

    confirmation.append(
      heading,
      description,
      reference,
      amount,
      status,
      passengerHeading,
      passengerList,
      historyLink
    );

    form.replaceWith(confirmation);

    confirmation.scrollIntoView({
      behavior: "smooth",
      block: "center"
    });
  }

  render();


const cancelButton = document.querySelector("#cancelBookingBtn");

if (cancelButton) {
    cancelButton.addEventListener("click", async () => {

        const confirmed = window.confirm(
            "Are you sure you want to cancel this booking?"
        );

        if (!confirmed) {
            return;
        }

        const cancelUrl = cancelButton.dataset.cancelUrl;

        const csrfToken = document.querySelector(
            "[name='csrfmiddlewaretoken']"
        )?.value;

        // Ticket pages may not contain a form with a CSRF token.
        // Read the token from the Django CSRF cookie if necessary.
        function getCookie(name) {
            const cookies = document.cookie.split(";");

            for (const cookie of cookies) {
                const trimmed = cookie.trim();

                if (trimmed.startsWith(name + "=")) {
                    return decodeURIComponent(
                        trimmed.substring(name.length + 1)
                    );
                }
            }

            return null;
        }

        const token = csrfToken || getCookie("csrftoken");

        if (!token) {
            document.querySelector("#cancelBookingMessage").textContent =
                "Security token unavailable. Please refresh the page.";
            return;
        }

        cancelButton.disabled = true;
        cancelButton.textContent = "Cancelling...";

        const message = document.querySelector(
            "#cancelBookingMessage"
        );

        try {
            const response = await fetch(cancelUrl, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Accept": "application/json",
                    "X-CSRFToken": token
                }
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(
                    data.error ||
                    formatApiError(data) ||
                    "Unable to cancel this booking."
                );
            }

            message.textContent =
                "Booking cancelled successfully. Your booking history will be updated.";

            cancelButton.textContent = "Booking cancelled";
            cancelButton.disabled = true;

            const statusLabel = document.querySelector(
                ".h5-book-head span"
            );

            if (statusLabel) {
                statusLabel.textContent = "Cancelled";
            }

        } catch (error) {
            message.textContent = error.message;

            cancelButton.disabled = false;
            cancelButton.textContent = "Cancel this booking";
        }
    });
}


})();
// "All trips" filters: apply as soon as a choice changes (the Show button is the no-JS fallback).
document.documentElement.classList.add("js");
document.querySelectorAll("form[data-autosubmit] select").forEach((select) => {
    select.addEventListener("change", () => select.form.submit());
});
