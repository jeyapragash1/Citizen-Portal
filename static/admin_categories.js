async function loadCategories() {
    const el = document.getElementById('categoriesList');
    el.innerHTML = 'Loading...';
    try {
        const res = await fetch('/api/admin/categories');
        if (!res.ok) throw new Error('Failed to load categories');
        const data = await res.json();
        renderCategories(data);
    } catch (e) {
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
document.addEventListener('DOMContentLoaded', function(){
    loadCategories();
});
