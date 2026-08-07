document.addEventListener("DOMContentLoaded", function () {
    const input = document.getElementById("user-search");
    const tbody = document.getElementById("users-tbody");
    let debounceTimer = null;

    function renderRows(users) {
        if (users.length === 0) {
            tbody.innerHTML = '<tr><td colspan="3" class="muted">No matching users.</td></tr>';
            return;
        }
        tbody.innerHTML = users.map(function (user) {
            return `<tr>
                <td>${user.name}</td>
                <td class="muted">${user.email}</td>
                <td class="status">${user.role}</td>
            </tr>`;
        }).join("");
    }

    async function search() {
        const q = input.value;
        try {
            const response = await fetch(`/api/admin/users/search?q=${encodeURIComponent(q)}`);
            const data = await response.json();
            renderRows(data.users);
        } catch (err) {
            tbody.innerHTML = '<tr><td colspan="3" class="muted">Search failed.</td></tr>';
        }
    }

    input.addEventListener("input", function () {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(search, 250);
    });
});
