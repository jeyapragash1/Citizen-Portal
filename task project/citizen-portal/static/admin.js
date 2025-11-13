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

// Store chart instances to destroy them before re-rendering
let chartInstances = {};

// --- Login / Logout ---
loginForm.onsubmit = async (e) => {
    e.preventDefault();
    const form = new FormData(e.target);
    const res = await fetch('/admin/login', { method:'POST', body: form });
    
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
    await fetch('/api/admin/logout', {method:'POST'});
    window.location="/admin"; // Redirect to admin page, which will show login form
});

// --- Dashboard Loading ---
async function loadDashboard(){
    // Destroy previous chart instances to prevent Chart.js errors on re-render
    Object.values(chartInstances).forEach(chart => chart.destroy());
    chartInstances = {};

    try {
        const insightsRes = await fetch('/api/admin/insights');
        if (insightsRes.status === 401) {
            // Not authorized, show login form
            loginBoxEl.style.display = "block";
            dashboardEl.style.display = "none";
            return;
        }
        const insightsData = await insightsRes.json();
        
        loginBoxEl.style.display = "none";
        dashboardEl.style.display = "block";

        // Render Charts
        renderCharts(insightsData);
        
        // Populate Premium Suggestions
        premiumListEl.innerHTML = insightsData.premium_suggestions.length ?
            insightsData.premium_suggestions.map(p => `<div>User:<b>${p.user || 'Unknown'}</b> Question: "<span>${p.question}</span>" (Engagements: ${p.count})</div>`).join("") :
            "<div>No premium suggestions at this time.</div>";

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
        alert("An error occurred loading the dashboard. Please try logging in again.");
    }
}
async function loadIndexJobs() {
    const tableBody = document.querySelector('#indexJobsTable tbody');
    if (!tableBody) return;
    tableBody.innerHTML = '<tr><td colspan="6">Loading...</td></tr>';
    try {
        const res = await fetch('/api/admin/index_jobs');
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
        const res = await fetch(`/api/admin/index_job/${encodeURIComponent(jobId)}`);
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
        profileTableEl = document.createElement('table');
        profileTableEl.className = 'engagements-table';
        profileTableEl.innerHTML = `<thead><tr><th>Profile ID</th><th>Name</th><th>Age</th><th>Email</th><th>Phone</th><th>Job</th><th>Desires</th><th>Created</th><th>Updated</th></tr></thead>`;
        profileTableEl.appendChild(profileTableBody);
        // Insert after engagements table
        const dashboard = document.getElementById('dashboard');
        const section = dashboard.querySelector('.dashboard-section:last-of-type');
        section.appendChild(document.createElement('h3')).textContent = 'All User Profiles';
        section.appendChild(profileTableEl);
        // Add export button
        const exportProfilesBtn = document.createElement('button');
        exportProfilesBtn.className = 'export-csv-button';
        exportProfilesBtn.innerHTML = '<i class="fas fa-file-csv"></i> Export Profiles CSV';
        exportProfilesBtn.onclick = () => { window.location = '/api/admin/export_profiles'; };
        section.appendChild(exportProfilesBtn);
    }
    // Fetch profiles CSV
    const res = await fetch('/api/admin/export_profiles');
    if (!res.ok) {
        profileTableBody.innerHTML = '<tr><td colspan="9" class="text-center text-danger">Failed to load profiles.</td></tr>';
        return;
    }
    const csvText = await res.text();
    const rows = csvText.trim().split(/\r?\n/);
    if (rows.length <= 1) {
        profileTableBody.innerHTML = '<tr><td colspan="9" class="text-center text-muted">No profiles found.</td></tr>';
        return;
    }
    rows.shift(); // Remove header
    profileTableBody.innerHTML = "";
    rows.forEach(line => {
        const cols = line.match(/\s*("[^"]*"|[^,]*)\s*(,|$)/g).map(s => s.replace(/^,|,$|^"|"$/g, ''));
        const row = `<tr>
            <td>${cols[0] || "N/A"}</td>
            <td>${cols[1] || ""}</td>
            <td>${cols[2] || ""}</td>
            <td>${cols[3] || ""}</td>
            <td>${cols[4] || ""}</td>
            <td>${cols[5] || ""}</td>
            <td>${cols[6] || ""}</td>
            <td>${cols[7] || ""}</td>
            <td>${cols[8] || ""}</td>
        </tr>`;
        profileTableBody.insertAdjacentHTML('beforeend', row);
    });
}

function renderCharts(data) {
    // Age Chart
    chartInstances.ageChart = new Chart(document.getElementById("ageChart"), {
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

    // Jobs Chart
    chartInstances.jobChart = new Chart(document.getElementById("jobChart"), {
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

    // Services Chart
    chartInstances.serviceChart = new Chart(document.getElementById("serviceChart"), {
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

    // Questions Chart
    chartInstances.questionChart = new Chart(document.getElementById("questionChart"), {
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
    
    // If you add ads_clicked to admin_insights API, you would add another chart here
    // For now, we'll just log it.
    if (data.ads_clicked && Object.keys(data.ads_clicked).length > 0) {
        console.log("Ad Clicks:", data.ads_clicked);
        // You could create a chart for ads_clicked similarly
    }
}

async function loadEngagements() {
    // Use the CSV export endpoint and parse CSV to table
    const res = await fetch('/api/admin/export_csv');
    if (!res.ok) {
        engTableBody.innerHTML = '<tr><td colspan="9" class="text-center text-danger">Failed to load engagements.</td></tr>';
        return;
    }
    const csvText = await res.text();
    const rows = csvText.trim().split(/\r?\n/);
    if (rows.length <= 1) {
        engTableBody.innerHTML = '<tr><td colspan="9" class="text-center text-muted">No recent engagements found.</td></tr>';
        return;
    }
    // Remove header
    rows.shift();
    engTableBody.innerHTML = "";
    rows.forEach(line => {
        // Split CSV line, handling commas inside quotes
        const cols = line.match(/\s*("[^"]*"|[^,]*)\s*(,|$)/g).map(s => s.replace(/^,|,$|^"|"$/g, ''));
        const row = `<tr>
            <td>${cols[0] || "N/A"}</td>
            <td>${cols[1] || ""}</td>
            <td>${cols[2] || ""}</td>
            <td>${cols[3] || ""}</td>
            <td>${cols[4] || ""}</td>
            <td>${cols[5] || ""}</td>
            <td>${cols[6] || ""}</td>
            <td>${cols[7] || ""}</td>
            <td>${cols[8] || ""}</td>
        </tr>`;
        engTableBody.insertAdjacentHTML('beforeend', row);
    });
}


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
                const res = await fetch('/api/admin/index_status');
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
        const res = await fetch('/api/admin/build_index_async', {method:'POST'});
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