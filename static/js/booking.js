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

  const money = (n) => `${currency}${n.toFixed(2)}`;
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
    }));

    passengerFields.innerHTML = "";

    for (let i = 1; i <= passengerCount; i++) {
      const prev = saved[i - 1] || { name: "", phone: "", email: "" };
      const passengerCard = document.createElement("div");
      passengerCard.className = "h5-passenger-card";

      passengerCard.innerHTML = `
        <h3>Passenger ${i}</h3>

        <div class="h5-form-group">
          <label for="passenger-name-${i}">Full name</label>
          <input
            type="text"
            id="passenger-name-${i}"
            name="passenger_name"
            placeholder="Enter passenger's full name"
            maxlength="150"
            required
          >
        </div>

        <div class="h5-form-group">
          <label for="passenger-phone-${i}">Phone number</label>
          <input
            type="tel"
            id="passenger-phone-${i}"
            name="passenger_phone"
            placeholder="Enter passenger's phone number"
            maxlength="16"
            required
          >
        </div>

        <div class="h5-form-group">
          <label for="passenger-email-${i}">Email address (optional)</label>
          <input
            type="email"
            id="passenger-email-${i}"
            name="passenger_email"
            placeholder="Enter passenger's email"
          >
        </div>
      `;

      passengerFields.appendChild(passengerCard);

      passengerCard.querySelector("[name='passenger_name']").value = prev.name;
      passengerCard.querySelector("[name='passenger_phone']").value = prev.phone;
      passengerCard.querySelector("[name='passenger_email']").value = prev.email;
    }
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

    const passengers = passengerCards.map((card) => ({
      full_name: card.querySelector("[name='passenger_name']").value.trim(),
      phone: card.querySelector("[name='passenger_phone']").value.trim(),
      email: card.querySelector("[name='passenger_email']").value.trim()
    }));

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
        const errorMessage = formatApiError(data);
        throw new Error(errorMessage);
      }

      renderBookingConfirmation(data);

      goBtn.textContent = "Booking confirmed";
      goBtn.disabled = true;

    } catch (error) {
      showMessage(
        error.message || "Something went wrong. Please try again.",
        true
      );

      goBtn.disabled = false;
      goBtn.textContent = originalButtonText;
    }
  });

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
        `${currency}${Number(booking.total_amount || 0).toFixed(2)}`
      )
    );

    const status = document.createElement("p");
    status.textContent = `Booking status: ${booking.status || "CONFIRMED"}`;

    const passengerHeading = document.createElement("h3");
    passengerHeading.textContent = "Passenger details";

    const passengerList = document.createElement("ul");

    (booking.passengers || []).forEach((passenger) => {
      const item = document.createElement("li");
      item.textContent = `${passenger.full_name} — ${passenger.phone}`;
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