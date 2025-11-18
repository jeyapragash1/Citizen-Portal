async function loadCategories() {
    const el = document.getElementById('categoriesList');
    if (!el) return; // nothing to do when embedded container isn't present
    el.innerHTML = 'Loading...';
    // Prevent rapid repeated calls from the client
    if (!window._lastCategoriesLoad) window._lastCategoriesLoad = 0;
    const now = Date.now();
    if (now - window._lastCategoriesLoad < 1500) {
        el.innerHTML = '<div style="color:#666">Please wait a moment before reloading categories.</div>';
        return;
    }
    window._lastCategoriesLoad = now;
    try {
        const res = await fetch('/api/admin/categories');
        if (res.status === 429) {
            // Rate limited: show friendly message using Retry-After if present
            const retry = res.headers.get('Retry-After');
            const wait = retry ? `Retry after ${retry} seconds.` : 'Please wait a moment and try again.';
            el.innerHTML = `<div style="color:#d9534f">Too many requests. ${wait}</div>`;
            return;
        }
        if (!res.ok) throw new Error('Failed to load categories: ' + res.status);
        const data = await res.json();
        renderCategories(data);
    } catch (e) {
        console.error('loadCategories error', e);
        el.innerHTML = '<div style="color:red">Error loading categories: ' + String(e) + '</div>';
    }
}

function renderCategories(list) {
    const el = document.getElementById('categoriesList');
    if (!Array.isArray(list) || list.length === 0) {
        el.innerHTML = '<div>No categories found.</div>';
        return;
    }
    let html = '<table class="engagements-table" style="width:100%"><thead><tr><th>ID</th><th>Name</th><th>Actions</th></tr></thead><tbody>';
    for (const c of list) {
        const id = c.id || '';
        const name = (c.name && (typeof c.name === 'string' ? c.name : (c.name.en || JSON.stringify(c.name)))) || '';
        html += `<tr><td><code>${id}</code></td><td>${escapeHtml(name)}</td><td>`+
            `<button onclick="editCategory('${encodeURIComponent(id)}')">Edit</button> `+
            `<button onclick="deleteCategory('${encodeURIComponent(id)}')" style="background:#f44336;color:#fff">Delete</button>`+
            `</td></tr>`;
    }
    html += '</tbody></table>';
    el.innerHTML = html;
}

function escapeHtml(s){
    if(!s) return '';
    return String(s).replace(/[&<>"]+/g, function(m){
        return ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'})[m];
    });
}

async function saveCategory(e){
    e.preventDefault();
    const id = document.getElementById('catId').value.trim();
    const name = document.getElementById('catName').value.trim();
    const errEl = document.getElementById('categoryFormError');
    errEl.style.display = 'none';
    errEl.textContent = '';

    if (!id || !name) {
        errEl.textContent = 'ID and Name are required.';
        errEl.style.display = 'block';
        return false;
    }

    try{
        const saveBtn = document.getElementById('categorySaveBtn');
        saveBtn.disabled = true;
        saveBtn.textContent = 'Saving...';

        const payload = { id: id, name: name };
        const res = await fetch('/api/admin/categories', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
        if(!res.ok) throw new Error('save failed');
        await loadCategories();
        document.getElementById('categoryForm').reset();
    } catch(err) {
        errEl.textContent = 'Error saving category: ' + (err.message || err);
        errEl.style.display = 'block';
    } finally {
        const saveBtn = document.getElementById('categorySaveBtn');
        saveBtn.disabled = false;
        saveBtn.textContent = 'Save';
    }
    return false;
}

async function deleteCategory(idEnc){
    const id = decodeURIComponent(idEnc);
    if(!confirm('Delete category ' + id + '?')) return;
    try{
        const res = await fetch('/api/admin/categories?id=' + encodeURIComponent(id), {method:'DELETE'});
        if(!res.ok) throw new Error('delete failed');
        await loadCategories();
    }catch(err){
        alert('Error deleting category: ' + err.message);
    }
}

async function editCategory(idEnc){
    const id = decodeURIComponent(idEnc);
    // Fetch full list and find
    try{
        const res = await fetch('/api/admin/categories');
        const list = await res.json();
        const found = list.find(x => x.id == id);
        if(!found) return alert('Category not found');
        document.getElementById('catId').value = found.id || '';
        // try to set a friendly string name
        const n = (found.name && (typeof found.name === 'string' ? found.name : (found.name.en || ''))) || '';
        document.getElementById('catName').value = n;
        window.scrollTo(0,0);
    }catch(err){
        alert('Error editing category: ' + err.message);
    }
}

// Boot
// Removed automatic load on DOMContentLoaded to avoid accidental rapid calls
// The dashboard embeds/categories trigger `loadCategories()` when needed.
