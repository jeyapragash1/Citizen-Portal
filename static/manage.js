// Helper to populate the form for editing
async function populateServiceForm(id) {
    const res = await fetch(`/api/service/${id}`); // Using the public API to fetch service by ID
    const service = await res.json();

    if (service && service.id) {
        document.getElementById('service-id').value = service.id;
        document.getElementById('service-name-en').value = service.name.en || '';
        document.getElementById('service-name-si').value = service.name.si || '';
        document.getElementById('service-name-ta').value = service.name.ta || '';
        document.getElementById('service-subservices-json').value = JSON.stringify(service.subservices || [], null, 2);
    } else {
        alert("Service not found for ID: " + id);
    }
}


async function loadExistingServices() {
    const res = await fetch('/api/admin/services');
    const services = await res.json();
    const listEl = document.getElementById('existing-services-list');
    listEl.innerHTML = '';

    if (services.length === 0) {
        listEl.innerHTML = '<li class="service-item"><span>No services currently configured.</span></li>';
    } else {
        services.forEach(service => {
            const li = document.createElement('li');
            li.className = 'service-item';
            li.innerHTML = `
                <span>${service.name.en} (${service.id})</span>
                <div class="action-buttons">
                    <button class="edit-btn" data-id="${service.id}">
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" style="height:1em; width:1em; vertical-align:middle; margin-right:5px;">
                            <path d="M5.433 13.917C5.235 13.43 5.0 13 5 13c.091-2.181.725-5.334 1.756-6.843A3.75 3.75 0 0113.5 2.25c2.51 0 4.366 1.499 4.366 2.981 0 1.575-1.517 2.126-3.372 1.636a.75.75 0 00-.916.274l-1.353 2.083c-.702 1.08-.946 2.296-.519 3.32a3.073 3.073 0 01-1.764 3.077c-1.3.385-2.613-.232-2.96-1.48L5.433 13.917z" />
                            <path d="M11.75 14.25a.75.75 0 000 1.5h2.5a.75.75 0 000-1.5h-2.5z" />
                        </svg>
                        Edit
                    </button>
                    <button class="delete-btn" data-id="${service.id}">
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" style="height:1em; width:1em; vertical-align:middle; margin-right:5px;">
                            <path fill-rule="evenodd" d="M8.75 1A2.75 2.75 0 006 3.75v.443c-.795.077-1.584.176-2.365.278a.75.75 0 00.14 1.497l.116-.006c.866-.1 1.73-.209 2.583-.323l.11-.013c.355-.043.7-.091 1.033-.135V15.5a2.75 2.75 0 002.75 2.75h2.5a2.75 2.75 0 002.75-2.75V5.118c.333.044.67.092 1.034.136l.11.013c.854.114 1.718.223 2.584.322l.115.006a.75.75 0 00.14-1.497 12.793 12.793 0 00-2.366-.278V3.75A2.75 2.75 0 0011.25 1h-2.5zM10 4c.828 0 1.5.672 1.5 1.5v7.25a.75.75 0 01-1.5 0V5.5c0-.828-.672-1.5-1.5-1.5z" clip-rule="evenodd" />
                        </svg>
                        Delete
                    </button>
                </div>
            `;
            listEl.appendChild(li);
        });
        attachServiceEventListeners();
    }
}

function attachServiceEventListeners() {
    document.querySelectorAll('.edit-btn').forEach(button => {
        button.onclick = (e) => populateServiceForm(e.target.dataset.id);
    });
    document.querySelectorAll('.delete-btn').forEach(button => {
        button.onclick = (e) => deleteService(e.target.dataset.id);
    });
}

async function deleteService(id) {
    if (!confirm(`Are you sure you want to delete service ID: "${id}"? This action cannot be undone.`)) {
        return;
    }
    const res = await fetch(`/api/admin/services/${id}`, {
        method: 'DELETE'
    });
    if (res.ok) {
        alert(`Service "${id}" deleted successfully!`);
        loadExistingServices(); // Reload the list
    } else {
        const error = await res.json();
        alert(`Failed to delete service: ${error.error}`);
    }
}

document.getElementById('upsert-service-form').onsubmit = async (e) => {
    e.preventDefault();
    const form = e.target;
    const serviceId = form['service-id'].value.trim();
    const nameEn = form['service-name-en'].value.trim();
    const nameSi = form['service-name-si'].value.trim();
    const nameTa = form['service-name-ta'].value.trim();
    const subservicesJson = form['service-subservices-json'].value.trim();

    if (!serviceId || !nameEn) {
        alert("Service ID and English Name are required.");
        return;
    }

    let subservicesData = [];
    try {
        if (subservicesJson) {
            subservicesData = JSON.parse(subservicesJson);
            if (!Array.isArray(subservicesData)) {
                throw new Error("Subservices must be a JSON array.");
            }
        }
    } catch (error) {
        alert(`Invalid JSON for subservices. Please check the format. Error: ${error.message}`);
        console.error("JSON parsing error:", error);
        return;
    }

    const payload = {
        id: serviceId,
        name: {
            en: nameEn,
            si: nameSi,
            ta: nameTa
        },
        subservices: subservicesData
    };

    const res = await fetch('/api/admin/services', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
    });

    if (res.ok) {
        alert(`Service "${serviceId}" saved successfully!`);
        form.reset(); // Clear the form
        loadExistingServices(); // Reload the list
    } else {
        const error = await res.json();
        alert(`Failed to save service: ${error.error}`);
    }
};

window.onload = loadExistingServices;