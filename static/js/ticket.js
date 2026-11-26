
(() => {
    "use strict";

    const cancelButton = document.querySelector("#cancelBookingBtn");

    if (!cancelButton) {
        return;
    }

    const message = document.querySelector("#cancelBookingMessage");

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

    cancelButton.addEventListener("click", async () => {

        const confirmed = window.confirm(
            "Are you sure you want to cancel this booking?"
        );

        if (!confirmed) {
            return;
        }

        const csrfToken = getCookie("csrftoken");

        if (!csrfToken) {
            message.textContent =
                "Security token unavailable. Please refresh the page.";
            return;
        }

        cancelButton.disabled = true;
        cancelButton.textContent = "Cancelling...";

        try {
            const response = await fetch(
                cancelButton.dataset.cancelUrl,
                {
                    method: "POST",
                    credentials: "same-origin",
                    headers: {
                        "Accept": "application/json",
                        "X-CSRFToken": csrfToken
                    }
                }
            );

            const data = await response.json();

            if (!response.ok) {
                const errorMessage =
                    data.error ||
                    data.booking ||
                    "Unable to cancel this booking.";

                throw new Error(
                    typeof errorMessage === "string"
                        ? errorMessage
                        : JSON.stringify(errorMessage)
                );
            }

            message.textContent =
                "Booking cancelled successfully.";

            cancelButton.textContent = "Booking cancelled";

            // Reload so the ticket, chips and refund line come from the server.
            window.location.reload();

        } catch (error) {
            message.textContent = error.message;

            cancelButton.disabled = false;
            cancelButton.textContent = "Cancel booking…";
        }
    });
})();
