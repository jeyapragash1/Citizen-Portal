async function loadOfficers() {
    const el = document.getElementById('officersList');
    el.innerHTML = 'Loading...';
    try {
        const res = await fetch('/api/admin/officers');
        if (!res.ok) throw new Error('Failed to load officers');
        const data = await res.json();
        renderOfficers(data);
    } catch (e) {
        el.innerHTML = '<div style="color:red">Error loading officers: ' + String(e) + '</div>';
    }
}

function renderOfficers(list) {
    const el = document.getElementById('officersList');
    if (!Array.isArray(list) || list.length === 0) {
        el.innerHTML = '<div>No officers found.</div>';
        return;
    }
    let html = '<table class="engagements-table" style="width:100%"><thead><tr><th>ID</th><th>Name</th><th>Role</th><th>Contact</th><th>Actions</th></tr></thead><tbody>';
    for (const o of list) {
        const id = o.id || '';
        const name = o.name || '';
        const role = o.role || '';
        const contact = ((o.email || '') + (o.phone ? (' / ' + o.phone) : '')) || '';
        html += `<tr><td><code>${id}</code></td><td>${escapeHtml(name)}</td><td>${escapeHtml(role)}</td><td>${escapeHtml(contact)}</td><td>`+
            `<button onclick="editOfficer('${encodeURIComponent(id)}')">Edit</button> `+
            `<button onclick="deleteOfficer('${encodeURIComponent(id)}')" style="background:#f44336;color:#fff">Delete</button>`+
            `</td></tr>`;
    }
    html += '</tbody></table>';
    el.innerHTML = html;
}

function escapeHtml(s){ if(!s) return ''; return String(s).replace(/[&<>"]+/g, function(m){ return ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'})[m]; }); }

async function saveOfficer(e){
    e.preventDefault();
    const id = document.getElementById('offId').value.trim();
    const name = document.getElementById('offName').value.trim();
    const role = document.getElementById('offRole').value.trim();
    const email = document.getElementById('offEmail').value.trim();
    const phone = document.getElementById('offPhone').value.trim();
    const errEl = document.getElementById('officerFormError');
    errEl.style.display = 'none';
    errEl.textContent = '';

    if(!id || !name) {
        errEl.textContent = 'ID and Name are required.';
        errEl.style.display = 'block';
        return false;
    }

    // Basic email validation (optional field)
    if (email) {
        const emailRe = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRe.test(email)) {
            errEl.textContent = 'Please enter a valid email address.';
            errEl.style.display = 'block';
            return false;
        }
    }

    // Basic phone validation (optional): digits, +, -, spaces, 6-20 chars
    if (phone) {
        const phoneRe = /^[0-9+\-\s()]{6,20}$/;
        if (!phoneRe.test(phone)) {
            errEl.textContent = 'Please enter a valid phone number (6-20 digits, can include +, -, spaces).';
            errEl.style.display = 'block';
            return false;
        }
    }
    try{
        const saveBtn = document.getElementById('officerSaveBtn');
        saveBtn.disabled = true;
        saveBtn.textContent = 'Saving...';

        const payload = { id: id, name: name, role: role, email: email, phone: phone };
        const res = await fetch('/api/admin/officers', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
        if(!res.ok) throw new Error('save failed');
        await loadOfficers();
        document.getElementById('officerForm').reset();
    }catch(err){
        const errEl = document.getElementById('officerFormError');
        errEl.textContent = 'Error saving officer: ' + (err.message || err);
        errEl.style.display = 'block';
    } finally {
        const saveBtn = document.getElementById('officerSaveBtn');
        saveBtn.disabled = false;
        saveBtn.textContent = 'Save Officer';
    }
    return false;
}

async function deleteOfficer(idEnc){
    const id = decodeURIComponent(idEnc);
    if(!confirm('Delete officer ' + id + '?')) return;
    try{
        const res = await fetch('/api/admin/officers?id=' + encodeURIComponent(id), {method:'DELETE'});
        if(!res.ok) throw new Error('delete failed');
        await loadOfficers();
    }catch(err){ alert('Error deleting officer: ' + err.message); }
}

async function editOfficer(idEnc){
    const id = decodeURIComponent(idEnc);
    try{
        const res = await fetch('/api/admin/officers');
        const list = await res.json();
        const found = list.find(x => x.id == id);
        if(!found) return alert('Officer not found');
        document.getElementById('offId').value = found.id || '';
        document.getElementById('offName').value = found.name || '';
        document.getElementById('offRole').value = found.role || '';
        document.getElementById('offEmail').value = found.email || '';
        document.getElementById('offPhone').value = found.phone || '';
        window.scrollTo(0,0);
    }catch(err){ alert('Error editing officer: ' + err.message); }
}

document.addEventListener('DOMContentLoaded', function(){ loadOfficers(); });
