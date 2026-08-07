document.addEventListener("DOMContentLoaded", function () {
    const providerSelect = document.getElementById("provider_id");
    const dateInput = document.getElementById("date");
    const timeSelect = document.getElementById("time");
    const statusText = document.getElementById("slot-status");
    const doctorSearch = document.getElementById("doctor-search");
    let doctorDebounce = null;

    function renderDoctorOptions(doctors) {
        const previousValue = providerSelect.value;
        providerSelect.innerHTML = "";

        const placeholder = document.createElement("option");
        placeholder.value = "";
        placeholder.textContent = doctors.length ? "Select a doctor" : "No doctors match your search";
        placeholder.disabled = true;
        placeholder.selected = true;
        providerSelect.appendChild(placeholder);

        doctors.forEach(function (doc) {
            const option = document.createElement("option");
            option.value = doc.id;
            option.textContent = `Dr. ${doc.name} — ${doc.specialty || "General"}`;
            providerSelect.appendChild(option);
        });

        // Keep the previous selection if it's still in the filtered list
        if (doctors.some(function (d) { return String(d.id) === previousValue; })) {
            providerSelect.value = previousValue;
        }
    }

    async function searchDoctors() {
        const q = doctorSearch.value;
        try {
            const response = await fetch(`/api/doctors/search?q=${encodeURIComponent(q)}`);
            const data = await response.json();
            renderDoctorOptions(data.doctors);
        } catch (err) {
            // Leave the existing list in place if the search fails
        }
    }

    if (doctorSearch) {
        doctorSearch.addEventListener("input", function () {
            clearTimeout(doctorDebounce);
            doctorDebounce = setTimeout(searchDoctors, 250);
        });
    }

    function clearSlots(message) {
        timeSelect.innerHTML = "";
        timeSelect.disabled = true;
        statusText.textContent = message || "";
    }

    async function loadSlots() {
        const providerId = providerSelect.value;
        const dateValue = dateInput.value;

        if (!providerId || !dateValue) {
            clearSlots("Choose a doctor and date to see available times.");
            return;
        }

        clearSlots("Loading available times...");

        try {
            const response = await fetch(`/api/availability/${providerId}?date=${dateValue}`);
            const data = await response.json();

            if (!response.ok) {
                clearSlots(data.error || "Could not load availability.");
                return;
            }

            if (data.slots.length === 0) {
                clearSlots("No open slots for this doctor on this date.");
                return;
            }

            timeSelect.innerHTML = "";
            const placeholder = document.createElement("option");
            placeholder.value = "";
            placeholder.textContent = "Select a time";
            placeholder.disabled = true;
            placeholder.selected = true;
            timeSelect.appendChild(placeholder);

            data.slots.forEach(function (slot) {
                const option = document.createElement("option");
                option.value = slot;
                option.textContent = slot;
                timeSelect.appendChild(option);
            });

            timeSelect.disabled = false;
            statusText.textContent = `${data.slots.length} slot(s) available.`;
        } catch (err) {
            clearSlots("Something went wrong loading availability.");
        }
    }

    providerSelect.addEventListener("change", loadSlots);
    dateInput.addEventListener("change", loadSlots);

    clearSlots("Choose a doctor and date to see available times.");
});
