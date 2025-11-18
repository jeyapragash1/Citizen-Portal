// --- Profile Table Elements ---
const profileTableBody = document.createElement('tbody');
let profileTableEl = null;

// --- DOM Element References ---
const loginBoxEl = document.getElementById("login-box");
const dashboardEl = document.getElementById("dashboard");
const loginForm = document.getElementById("login-form");
const logoutBtn = document.getElementById("logoutBtn");
const rebuildIndexBtn = document.getElementById("rebuildIndexBtn");
const exportCsvBtn = document.getElementById("exportCsv");
const premiumListEl = document.getElementById("premiumList");
const engTableBody = document.querySelector("#engTable tbody");

// Helper that ensures cookies (session) are included on same-origin admin requests
const apiFetch = (url, opts = {}) => {
    const defaultOpts = { credentials: 'same-origin' };
    // Merge headers without overwriting entire headers object if provided
    const merged = Object.assign({}, defaultOpts, opts || {});
    return fetch(url, merged);
};

// Store chart instances to destroy them before re-rendering
let chartInstances = {};

// --- Login / Logout ---
loginForm.onsubmit = async (e) => {
    e.preventDefault();
    const form = new FormData(e.target);
    const res = await apiFetch('/admin/login', { method:'POST', body: form });
    
    // Flask redirect will be handled automatically by the browser if 302
    if (res.redirected) {
        window.location = res.url;
    } else {
        const text = await res.text(); // Read text to check for "Login failed"
        if (text.includes("Login failed")) {
            alert("Login failed. Please check your credentials.");
        } else {
            // If not redirected, but login was successful (e.g., direct API call),
            // attempt to load dashboard to verify session
            loadDashboard();
        }
    }
};

logoutBtn?.addEventListener('click', async ()=>{
    await apiFetch('/api/admin/logout', {method:'POST'});
    window.location="/admin"; // Redirect to admin page, which will show login form
});

// --- Dashboard Loading ---
async function loadDashboard(){
    // Destroy previous chart instances to prevent Chart.js errors on re-render
    Object.values(chartInstances).forEach(chart => chart.destroy());
    chartInstances = {};

    try {
        const insightsRes = await apiFetch('/api/admin/insights');
        if (insightsRes.status === 401) {
            // Not authorized, show login form
            loginBoxEl.style.display = "block";
            dashboardEl.style.display = "none";
            return;
        }
        let insightsData = null;
        if (!insightsRes.ok) {
            // Show admin error banner with error id if present
            try {
                const err = await insightsRes.json();
                const errId = err.error_id || err.error || insightsRes.status;
                const adminErrorEl = document.getElementById('adminError');
                const adminErrorText = document.getElementById('adminErrorText');
                if (adminErrorEl && adminErrorText) {
                    adminErrorText.textContent = `Server error (${errId}). Some data may be unavailable.`;
                    adminErrorEl.style.display = 'block';
                }
            } catch(e){
                // ignore parse errors
            }
            // Use safe empty defaults so the UI still renders
            insightsData = { age_groups: {}, jobs: {}, services: {}, questions: {}, premium_suggestions: [], ads_clicked: {} };
        } else {
            try {
                insightsData = await insightsRes.json();
            } catch (parseErr) {
                console.error('Failed to parse insights JSON', parseErr);
                insightsData = { age_groups: {}, jobs: {}, services: {}, questions: {}, premium_suggestions: [], ads_clicked: {} };
            }
        }

        loginBoxEl.style.display = "none";
        dashboardEl.style.display = "block";

        // Try to fetch richer dashboard analytics for stat cards (use apiFetch so cookies are included)
        try {
            const analyticsRes = await apiFetch('/api/dashboard/analytics');
            if (analyticsRes.status === 401) {
                // session expired - show login
                loginBoxEl.style.display = "block";
                dashboardEl.style.display = "none";
                return;
            }
            if (analyticsRes.ok) {
                try {
                    const analytics = await analyticsRes.json();
                    // Populate stat cards if elements exist
                    const totalUsersEl = document.getElementById('totalUsersValue');
                    const totalEngEl = document.getElementById('totalEngagementsValue');
                    const totalOrdersEl = document.getElementById('totalOrdersValue');
                    const aiSearchesEl = document.getElementById('aiSearchesValue');
                    if (totalUsersEl && analytics.user_metrics) totalUsersEl.textContent = analytics.user_metrics.total_users || '0';
                    if (totalEngEl && analytics.engagement_metrics) totalEngEl.textContent = analytics.engagement_metrics.total_engagements || '0';
                    if (totalOrdersEl && analytics.store_metrics) totalOrdersEl.textContent = analytics.store_metrics.total_orders || '0';
                    if (aiSearchesEl && analytics.engagement_metrics) aiSearchesEl.textContent = analytics.engagement_metrics.recent_engagements || '0';
                } catch (aParseErr) {
                    console.error('Failed to parse analytics JSON', aParseErr);
                }
            }
        } catch (e) {
            console.warn('Analytics request failed', e);
        }

        // Render Charts (insightsData still useful for charts)
        try {
            renderCharts(insightsData || { age_groups: {}, jobs:{}, services:{}, questions:{}, premium_suggestions: [] });
        } catch (chartErr) {
            console.error('Chart rendering failed', chartErr);
            const adminErrorEl = document.getElementById('adminError');
            const adminErrorText = document.getElementById('adminErrorText');
            if (adminErrorEl && adminErrorText) {
                adminErrorText.textContent = `Chart rendering error: ${chartErr.message || chartErr}`;
                adminErrorEl.style.display = 'block';
            }
        }

        // Populate Premium Suggestions
        try {
            premiumListEl.innerHTML = insightsData && insightsData.premium_suggestions && insightsData.premium_suggestions.length ?
                insightsData.premium_suggestions.map(p => `<div>User:<b>${p.user || 'Unknown'}</b> Question: "<span>${p.question}</span>" (Engagements: ${p.count})</div>`).join("") :
                "<div>No premium suggestions at this time.</div>";
        } catch (pErr) {
            console.warn('Failed to populate premium suggestions', pErr);
        }

        // Load Recent Engagements
        await loadEngagements();

        // Load All User Profiles
        await loadProfiles();
        // Load Index Jobs
        await loadIndexJobs();

    } catch (err) {
        console.error("Failed to load dashboard:", err);
        loginBoxEl.style.display = "block"; // Show login on error
        dashboardEl.style.display = "none";
        // Show error banner with the message to help debugging
        const adminErrorEl = document.getElementById('adminError');
        const adminErrorText = document.getElementById('adminErrorText');
        if (adminErrorEl && adminErrorText) {
            adminErrorText.textContent = `An error occurred loading the dashboard: ${err.message || err}`;
            adminErrorEl.style.display = 'block';
        } else {
            alert("An error occurred loading the dashboard. Please try logging in again.");
        }
    }
}
async function loadIndexJobs() {
    const tableBody = document.querySelector('#indexJobsTable tbody');
    if (!tableBody) return;
    tableBody.innerHTML = '<tr><td colspan="6">Loading...</td></tr>';
    try {
            const res = await apiFetch('/api/admin/index_jobs');
        if (!res.ok) {
            tableBody.innerHTML = '<tr><td colspan="6" class="text-danger">Failed to load jobs</td></tr>';
            return;
        }
        const data = await res.json();
        const jobs = data.jobs || [];
        if (!jobs.length) {
            tableBody.innerHTML = '<tr><td colspan="6" class="text-muted">No recent jobs</td></tr>';
            return;
        }
        tableBody.innerHTML = '';
        jobs.forEach(j => {
            const summary = j.result ? (j.result.count ? `docs:${j.result.count}` : JSON.stringify(j.result)) : '';
            const jobId = j.job_id || j.jobId || j._id;
            const row = document.createElement('tr');
            row.dataset.jobId = jobId;
            row.innerHTML = `
                <td style="font-family:monospace">${jobId}</td>
                <td>${j.status || ''}</td>
                <td>${j.created_at || ''}</td>
                <td>${j.started_at || ''}</td>
                <td>${j.finished_at || ''}</td>
                <td>${summary}</td>
            `;
            row.addEventListener('click', ()=> loadJobDetails(jobId));
            tableBody.appendChild(row);
        });
    } catch (err) {
        console.error('Failed to load index jobs', err);
        tableBody.innerHTML = '<tr><td colspan="6" class="text-danger">Error loading jobs</td></tr>';
    }
}


async function loadJobDetails(jobId) {
    const modal = document.getElementById('indexJobModal');
    const title = document.getElementById('indexJobModalTitle');
    const content = document.getElementById('indexJobModalContent');
    if (!modal || !content) return;
    title.textContent = `Job: ${jobId}`;
    content.textContent = 'Loading...';
    modal.style.display = 'block';
    try {
        const res = await apiFetch(`/api/admin/index_job/${encodeURIComponent(jobId)}`);
        if (!res.ok) {
            content.textContent = `Failed to load job: ${res.status}`;
            return;
        }
        const data = await res.json();
        const job = data.job || {};
        // Build HTML view: key/value pairs + logs if present
        let html = '<div style="font-family:monospace; font-size:13px;">';
        html += `<div><strong>Status:</strong> ${job.status || ''}</div>`;
        html += `<div><strong>Created:</strong> ${job.created_at || ''}</div>`;
        html += `<div><strong>Started:</strong> ${job.started_at || ''}</div>`;
        html += `<div><strong>Finished:</strong> ${job.finished_at || ''}</div>`;
        if (job.result) {
            html += `<div><strong>Result:</strong> <pre style="white-space:pre-wrap; background:#f0f0f0; padding:6px;">${JSON.stringify(job.result, null, 2)}</pre></div>`;
        }
        if (job.logs && Array.isArray(job.logs) && job.logs.length) {
            html += '<div style="margin-top:8px;"><strong>Logs:</strong><table style="width:100%; border-collapse:collapse; margin-top:6px;">';
            job.logs.forEach(l => {
                const ts = l.ts || '';
                const msg = (l.msg || '').replace(/</g,'&lt;').replace(/>/g,'&gt;');
                html += `<tr style="border-top:1px solid #eee;"><td style="width:160px; vertical-align:top; padding:6px; font-size:12px; color:#666">${ts}</td><td style="padding:6px; font-size:13px;">${msg}</td></tr>`;
            });
            html += '</table></div>';
        } else {
            html += '<div style="margin-top:8px; color:#666">No logs available.</div>';
        }
        html += '</div>';
        content.innerHTML = html;
    } catch (err) {
        content.textContent = `Error loading job: ${err.message}`;
    }
}
async function loadProfiles() {
    // Create table if not exists
    if (!profileTableEl) {
        // Use the existing dashboard table styles by applying `data-table`.
        // Also wrap the table in a `.table-responsive` container so it matches
        // other tables on the admin dashboard and avoids layout issues.
        profileTableEl = document.createElement('table');
        profileTableEl.className = 'data-table engagements-table';
        profileTableEl.innerHTML = `<thead><tr><th>Profile ID</th><th>Name</th><th>Age</th><th>Email</th><th>Phone</th><th>Job</th><th>Desires</th><th>Created</th><th>Updated</th></tr></thead>`;
        profileTableEl.appendChild(profileTableBody);

        const wrapper = document.createElement('div');
        wrapper.className = 'table-responsive';
        wrapper.appendChild(profileTableEl);

        // Choose a reliable insertion point: prefer the Recent Engagements section
        // (`#recentEngagements`) or the closest `.table-section` so the created
        // table inherits the dashboard table styles and layout.
        let section = null;
        const engTable = document.getElementById('engTable');
        if (engTable) {
            section = engTable.closest('.table-section') || document.getElementById('recentEngagements') || engTable.parentElement || null;
        }
        if (!section) {
            section = document.getElementById('recentEngagements') || document.querySelector('.table-section') || document.getElementById('dashboard') || document.body;
        }

        // Append a header and the profiles table inside the chosen section.
        const header = document.createElement('h3');
        header.id = 'profilesHeader';
        header.textContent = 'All User Profiles';

        // Prefer inserting right after the section header so the table appears
        // with the same spacing as other sections. If not available, append at end.
        const sectionHeaderEl = section.querySelector('.section-header');
        if (sectionHeaderEl && sectionHeaderEl.parentNode) {
            sectionHeaderEl.parentNode.insertBefore(header, sectionHeaderEl.nextSibling);
            sectionHeaderEl.parentNode.insertBefore(wrapper, header.nextSibling);
        } else {
            section.appendChild(header);
            section.appendChild(wrapper);
        }

        // Add export button
        const exportProfilesBtn = document.createElement('button');
        exportProfilesBtn.className = 'export-csv-button';
        exportProfilesBtn.innerHTML = '<i class="fas fa-file-csv"></i> Export Profiles CSV';
        exportProfilesBtn.onclick = () => { window.location = '/api/admin/export_profiles'; };
        if (sectionHeaderEl && sectionHeaderEl.parentNode) {
            sectionHeaderEl.parentNode.insertBefore(exportProfilesBtn, wrapper.nextSibling);
        } else {
            section.appendChild(exportProfilesBtn);
        }
    }

    // Ensure we have a timeframe selector for profiles (create it once)
    // Insert it near the engagements controls when possible
    if (!document.getElementById('profilesTimeframe')) {
        let insertBeforeEl = null;
        const engSection = document.getElementById('engTable') ? (document.getElementById('engTable').closest('.table-section') || document.getElementById('recentEngagements')) : null;
        if (engSection) insertBeforeEl = engSection.querySelector('h3')?.nextSibling || engSection.firstChild;
        const wrapper = document.createElement('div');
        wrapper.style.display = 'flex';
        wrapper.style.gap = '8px';
        wrapper.style.alignItems = 'center';
        wrapper.style.marginBottom = '8px';
        const lbl = document.createElement('label');
        lbl.textContent = 'Timeframe:';
        lbl.style.margin = '0';
        lbl.style.fontWeight = '600';
        lbl.style.color = '#424242';
        const sel = document.createElement('select');
        sel.id = 'profilesTimeframe';
        sel.style.padding = '6px';
        sel.style.borderRadius = '4px';
        sel.style.border = '1px solid var(--border-color)';
        ['today','week','month','year','all'].forEach(v => {
            const o = document.createElement('option'); o.value = v; o.textContent = v.charAt(0).toUpperCase() + v.slice(1); if (v==='all') o.selected = true; sel.appendChild(o);
        });
        sel.addEventListener('change', () => loadProfiles());
        wrapper.appendChild(lbl);
        wrapper.appendChild(sel);

        // Prefer to insert near engagements section; otherwise, put before profiles header
        const profilesHeader = document.getElementById('profilesHeader');
        if (insertBeforeEl && insertBeforeEl.parentNode) {
            insertBeforeEl.parentNode.insertBefore(wrapper, insertBeforeEl);
        } else if (profilesHeader && profilesHeader.parentNode) {
            profilesHeader.parentNode.insertBefore(wrapper, profilesHeader.nextSibling);
        } else {
            (document.getElementById('dashboard') || document.body).insertBefore(wrapper, profileTableEl);
        }
    }

    const timeframeSelect = document.getElementById('profilesTimeframe');
    const timeframe = timeframeSelect ? timeframeSelect.value : 'all';
    let res;
    try {
        res = await apiFetch(`/api/admin/profiles?timeframe=${encodeURIComponent(timeframe)}&limit=500`);
    } catch (err) {
        console.error('Network error fetching profiles', err);
        profileTableBody.innerHTML = '<tr><td colspan="9" class="text-center text-danger">Network error loading profiles.</td></tr>';
        return;
    }
    if (res.status === 401) {
        // Not authorized - show login
        profileTableBody.innerHTML = '<tr><td colspan="9" class="text-center text-danger">Not authorized. Please login.</td></tr>';
        // Show login box to prompt re-login
        loginBoxEl.style.display = 'block';
        dashboardEl.style.display = 'none';
        return;
    }
    if (!res.ok) {
        // Try to parse JSON error with error_id
        try {
            const err = await res.json();
            console.error('Server error loading profiles', err);
            const adminErrorEl = document.getElementById('adminError');
            const adminErrorText = document.getElementById('adminErrorText');
            if (adminErrorEl && adminErrorText) {
                const id = err.error_id || err.error || res.status;
                adminErrorText.textContent = `Failed to load profiles (server error: ${id}).`;
                adminErrorEl.style.display = 'block';
            }
            profileTableBody.innerHTML = `<tr><td colspan="9" class="text-center text-danger">Failed to load profiles (server error).</td></tr>`;
            return;
        } catch (parseErr) {
            console.error('Failed to parse error response for profiles', parseErr);
            profileTableBody.innerHTML = '<tr><td colspan="9" class="text-center text-danger">Failed to load profiles.</td></tr>';
            return;
        }
    }
    const profiles = await res.json();
    if (!profiles || !profiles.length) {
        profileTableBody.innerHTML = '<tr><td colspan="9" class="text-center text-muted">No profiles found.</td></tr>';
        return;
    }
    profileTableBody.innerHTML = "";
    profiles.forEach(u => {
        const pid = u._id || 'N/A';
        const profile = u.profile || {};
        const name = profile.name || u.name || '';
        const age = profile.age || u.age || '';
        const email = u.email || '';
        const phone = u.phone || '';
        const job = profile.job || u.job || '';
        const desires = Array.isArray(profile.desires) ? profile.desires.join(', ') : (Array.isArray(u.desires) ? u.desires.join(', ') : (profile.desires || u.desires || ''));
        const created = u.created || '';
        const updated = u.updated || '';
        const row = `<tr>
            <td>${pid}</td>
            <td>${name}</td>
            <td>${age}</td>
            <td>${email}</td>
            <td>${phone}</td>
            <td>${job}</td>
            <td>${desires}</td>
            <td>${created}</td>
            <td>${updated}</td>
        </tr>`;
        profileTableBody.insertAdjacentHTML('beforeend', row);
    });
}

function renderCharts(data) {
    // Age Chart
    const ageEl = document.getElementById("ageChart") || document.getElementById('engagementChart');
    if (ageEl) {
        chartInstances.ageChart = new Chart(ageEl, {
        type: 'bar',
        data:{
            labels:Object.keys(data.age_groups),
            datasets:[{
                label:"Users",
                data:Object.values(data.age_groups),
                backgroundColor: 'rgba(13, 71, 161, 0.7)',
                borderColor: 'rgba(13, 71, 161, 1)',
                borderWidth: 1
            }]
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { title: { display: true, text: 'Age Groups Distribution' } }, scales: { y: { beginAtZero: true } } }
        });
    }

    // Jobs Chart
    // Use only an explicit `jobChart` canvas when present. Avoid falling back to
    // `serviceChart` because that can cause two Chart instances to be created
    // on the same canvas (Chart.js throws "Canvas is already in use").
    const jobEl = document.getElementById("jobChart");
    if (jobEl) {
        chartInstances.jobChart = new Chart(jobEl, {
        type:'pie',
        data:{
            labels:Object.keys(data.jobs),
            datasets:[{
                label:"Jobs",
                data:Object.values(data.jobs),
                backgroundColor: ['#42a5f5', '#26a69a', '#66bb6a', '#ffee58', '#ffa726', '#ef5350', '#ab47bc', '#78909c', '#d4e157', '#8d6e63']
            }]
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { title: { display: true, text: 'Jobs Distribution' } } }
        });
    }

    // Services Chart
    const serviceEl = document.getElementById("serviceChart");
    if (serviceEl) {
        chartInstances.serviceChart = new Chart(serviceEl, {
        type:'doughnut',
        data:{
            labels:Object.keys(data.services),
            datasets:[{
                label:"Services",
                data:Object.values(data.services),
                backgroundColor: ['#0d47a1', '#1976d2', '#2196f3', '#42a5f5', '#64b5f6', '#90caf9', '#bbdefb', '#e3f2fd', '#9e9e9e', '#757575']
            }]
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { title: { display: true, text: 'Service Engagements' } } }
        });
    }

    // Questions Chart
    // Use only an explicit `questionChart` canvas to avoid accidentally
    // reusing `engagementChart` which may already be rendered.
    const questionEl = document.getElementById("questionChart");
    if (questionEl) {
        chartInstances.questionChart = new Chart(questionEl, {
        type:'bar',
        data:{
            labels:Object.keys(data.questions).slice(0,10),
            datasets:[{
                label:"Top Questions",
                data:Object.values(data.questions).slice(0,10),
                backgroundColor: 'rgba(255, 152, 0, 0.7)',
                borderColor: 'rgba(255, 152, 0, 1)',
                borderWidth: 1
            }]
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { title: { display: true, text: 'Most Clicked Questions (Top 10)' } }, indexAxis: 'y', scales: { x: { beginAtZero: true } } }
        });
    }
    
    // If you add ads_clicked to admin_insights API, you would add another chart here
    // For now, we'll just log it.
    if (data.ads_clicked && Object.keys(data.ads_clicked).length > 0) {
        console.log("Ad Clicks:", data.ads_clicked);
        // You could create a chart for ads_clicked similarly
    }
}

async function loadEngagements() {
    // Fetch engagements JSON from the new endpoint (supports timeframe)
    const timeframeSelect = document.getElementById('engTimeframe');
    const timeframe = timeframeSelect ? timeframeSelect.value : 'all';
    const res = await apiFetch(`/api/admin/engagements?timeframe=${encodeURIComponent(timeframe)}&limit=500`);
    if (!res.ok) {
        engTableBody.innerHTML = '<tr><td colspan="9" class="text-center text-danger">Failed to load engagements.</td></tr>';
        return;
    }
    const items = await res.json();
    if (!items || !items.length) {
        engTableBody.innerHTML = '<tr><td colspan="9" class="text-center text-muted">No recent engagements found.</td></tr>';
        return;
    }
    engTableBody.innerHTML = "";
    items.forEach(e => {
        const user = e.user_id || e.user || 'N/A';
        const age = e.age || '';
        const job = e.job || '';
        const desires = Array.isArray(e.desires) ? e.desires.join(', ') : (e.desires || '');
        const question = e.question_clicked || e.question || '';
        const service = e.service || '';
        const ad = e.ad || '';
        const source = e.source || '';
        const ts = e.timestamp || '';
        const row = `<tr>
            <td>${user}</td>
            <td>${age}</td>
            <td>${job}</td>
            <td>${desires}</td>
            <td>${question}</td>
            <td>${service}</td>
            <td>${ad}</td>
            <td>${source}</td>
            <td>${ts}</td>
        </tr>`;
        engTableBody.insertAdjacentHTML('beforeend', row);
    });
}

// Re-load engagements when timeframe select changes
const engTimeframeEl = document.getElementById('engTimeframe');
if (engTimeframeEl) engTimeframeEl.addEventListener('change', () => loadEngagements());


// --- AI Index Management ---
rebuildIndexBtn?.addEventListener('click', rebuildIndex);

async function pollIndexJobs(jobId, interval = 2000, timeout = 10 * 60 * 1000) {
    const start = Date.now();
    return new Promise((resolve, reject) => {
        const iv = setInterval(async () => {
            if (Date.now() - start > timeout) {
                clearInterval(iv);
                reject(new Error('Index build timed out'));
                return;
            }
            try {
                    const res = await apiFetch('/api/admin/index_status');
                if (!res.ok) {
                    console.warn('index_status returned', res.status);
                    return;
                }
                const data = await res.json();
                const jobs = data.jobs || {};
                const job = jobs[jobId];
                if (!job) {
                    // job might not be visible yet
                    console.debug('job not found yet');
                    return;
                }
                if (job.status === 'pending' || job.status === 'running') {
                    console.log('Index job running...', job);
                    return;
                }
                clearInterval(iv);
                if (job.status === 'completed') {
                    resolve(job);
                } else if (job.status === 'error') {
                    reject(new Error(job.error || 'Index job failed'));
                } else {
                    // unknown final state
                    resolve(job);
                }
            } catch (err) {
                console.error('Error polling index_status', err);
            }
        }, interval);
    });
}

async function rebuildIndex(){
    if (!confirm("Are you sure you want to rebuild the AI Search Index? This may take some time.")) {
        return;
    }
    alert("Starting AI Index build in background. You'll be notified when it completes.");
    try {
        const res = await apiFetch('/api/admin/build_index_async', {method:'POST'});
        if (!res.ok) throw new Error('failed to start async build: ' + res.status);
        const data = await res.json();
        const jobId = data.job_id;
        console.log('Started async index build job:', jobId, data.status);
        // Poll job status until completion
        try {
            const job = await pollIndexJobs(jobId);
            console.log('Index build finished:', job);
            alert('AI Index build completed successfully');
        } catch (err) {
            console.error('Index build error or timeout:', err);
            alert('AI Index build failed or timed out: ' + err.message);
        }
    } catch (error) {
        console.error("Error starting AI index rebuild:", error);
        alert("Failed to start AI Search Index rebuild. Check console for details.");
    }
}

// --- CSV Export ---
exportCsvBtn?.addEventListener('click', ()=> {
    window.location = '/api/admin/export_csv';
});


// --- Initial Load ---
window.onload = loadDashboard;