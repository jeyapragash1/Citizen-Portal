async function loadAds() {
    const el = document.getElementById('adsList');
    el.innerHTML = 'Loading...';
    try {
        const res = await fetch('/api/admin/ads');
        if (!res.ok) throw new Error('Failed to load ads');
        const data = await res.json();
        renderAds(data);
    } catch (e) {
        el.innerHTML = '<div style="color:red">Error loading ads: ' + String(e) + '</div>';
    }
}

function renderAds(list) {
    const el = document.getElementById('adsList');
    if (!Array.isArray(list) || list.length === 0) {
        el.innerHTML = '<div>No ads found.</div>';
        return;
    }
    let html = '<table class="engagements-table" style="width:100%"><thead><tr><th>ID</th><th>Title</th><th>Body</th><th>Actions</th></tr></thead><tbody>';
    for (const a of list) {
        const id = a.id || '';
        const title = a.title || '';
        const body = a.body || '';
        html += `<tr><td><code>${id}</code></td><td>${escapeHtml(title)}</td><td>${escapeHtml(body)}</td><td>`+
            `<button onclick="editAd('${encodeURIComponent(id)}')">Edit</button> `+
            `<button onclick="deleteAd('${encodeURIComponent(id)}')" style="background:#f44336;color:#fff">Delete</button>`+
            `</td></tr>`;
    }
    html += '</tbody></table>';
    el.innerHTML = html;
}

function escapeHtml(s){ if(!s) return ''; return String(s).replace(/[&<>"]+/g, function(m){ return ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'})[m]; }); }

async function saveAd(e){
    e.preventDefault();
    const id = document.getElementById('adId').value.trim();
    const title = document.getElementById('adTitle').value.trim();
    const body = document.getElementById('adBody').value.trim();
    const errEl = document.getElementById('adFormError');
    errEl.style.display = 'none';
    errEl.textContent = '';

    if (!id || !title) {
        errEl.textContent = 'ID and Title are required.';
        errEl.style.display = 'block';
        return false;
    }

    try{
        const saveBtn = document.getElementById('adSaveBtn');
        saveBtn.disabled = true;
        saveBtn.textContent = 'Saving...';

        const payload = { id: id, title: title, body: body };
        const res = await fetch('/api/admin/ads', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
        if(!res.ok) throw new Error('save failed');
        await loadAds();
        document.getElementById('adForm').reset();
    }catch(err){
        errEl.textContent = 'Error saving ad: ' + (err.message || err);
        errEl.style.display = 'block';
    } finally {
        const saveBtn = document.getElementById('adSaveBtn');
        saveBtn.disabled = false;
        saveBtn.textContent = 'Save';
    }
    return false;
}

async function deleteAd(idEnc){
    const id = decodeURIComponent(idEnc);
    if(!confirm('Delete ad ' + id + '?')) return;
    try{
        const res = await fetch('/api/admin/ads?id=' + encodeURIComponent(id), {method:'DELETE'});
        if(!res.ok) throw new Error('delete failed');
        await loadAds();
    }catch(err){ alert('Error deleting ad: ' + err.message); }
}

async function editAd(idEnc){
    const id = decodeURIComponent(idEnc);
    try{
        const res = await fetch('/api/admin/ads');
        const list = await res.json();
        const found = list.find(x => x.id == id);
        if(!found) return alert('Ad not found');
        document.getElementById('adId').value = found.id || '';
        document.getElementById('adTitle').value = found.title || '';
        document.getElementById('adBody').value = found.body || '';
        window.scrollTo(0,0);
    }catch(err){ alert('Error editing ad: ' + err.message); }
}

document.addEventListener('DOMContentLoaded', function(){ loadAds(); });
