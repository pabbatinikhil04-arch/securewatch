// If frontend and backend are on the same origin (e.g. local docker-compose with
// nginx proxying /api/* to the backend container), this stays '/api' and just works.
// If they're deployed separately (e.g. Render static site + Render web service),
// set window.__API_BASE_URL__ in config.js to the backend's full URL before app.js loads.
const API_URL = (window.__API_BASE_URL__ ? window.__API_BASE_URL__.replace(/\/$/, '') : '') + '/api';

let authToken = sessionStorage.getItem('authToken');
let currentUser = null;

function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

/* ---------------------------------------------------------------------
   View / tab navigation
   The nav links (and a couple of in-page "View all" links) carry a
   data-view attribute pointing at the <section id="..."> to show.
   We intercept clicks, toggle the "active" class, keep the URL hash in
   sync so links/back-button/bookmarks work, and re-run the loaders for
   the view being shown so its data is fresh.
--------------------------------------------------------------------- */
const VIEWS = ['dashboard-view', 'websites-view', 'alerts-view'];

function showView(viewId, { pushHash = true } = {}) {
    if (!VIEWS.includes(viewId)) viewId = 'dashboard-view';

    VIEWS.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.classList.toggle('active', id === viewId);
    });

    document.querySelectorAll('.nav-links .nav-link').forEach(link => {
        link.classList.toggle('active', link.dataset.view === viewId);
    });

    if (pushHash) {
        const hash = '#' + viewId.replace('-view', '');
        if (window.location.hash !== hash) {
            history.pushState(null, '', hash);
        }
    }

    if (viewId === 'websites-view') loadWebsites();
    if (viewId === 'alerts-view') loadAllAlerts();
    if (viewId === 'dashboard-view') {
        loadDashboardStats();
        loadRecentAlerts();
        loadDashboardWebsites();
    }
}

function viewIdFromHash() {
    const hash = (window.location.hash || '#dashboard').replace('#', '');
    const match = VIEWS.find(v => v === `${hash}-view`);
    return match || 'dashboard-view';
}

document.addEventListener('click', (e) => {
    const link = e.target.closest('[data-view]');
    if (link) {
        e.preventDefault();
        showView(link.dataset.view);
    }
});

window.addEventListener('popstate', () => showView(viewIdFromHash(), { pushHash: false }));

document.addEventListener('DOMContentLoaded', () => {
    if (authToken) loadUserData();
    showView(viewIdFromHash(), { pushHash: false });
});

document.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal')) e.target.classList.remove('show');
});

function getHeaders(json = true) {
    const headers = {};
    if (json) headers['Content-Type'] = 'application/json';
    if (authToken) headers['Authorization'] = `Bearer ${authToken}`;
    return headers;
}

function loadUserData() {
    const stored = sessionStorage.getItem('currentUser');
    if (stored) {
        try {
            currentUser = JSON.parse(stored);
            updateUI();
        } catch {
            sessionStorage.removeItem('currentUser');
        }
    }
}

function updateUI() {
    document.getElementById('userName').textContent = currentUser ? `👤 ${currentUser.username}` : 'Guest';
    document.getElementById('loginBtn').style.display = currentUser ? 'none' : 'inline-block';
    document.getElementById('registerBtn').style.display = currentUser ? 'none' : 'inline-block';
    document.getElementById('logoutBtn').style.display = currentUser ? 'inline-block' : 'none';
}

function refreshAllData() {
    loadDashboardStats();
    loadDashboardWebsites();
    loadRecentAlerts();
    const active = document.querySelector('.view.active');
    if (active && active.id === 'websites-view') loadWebsites();
    if (active && active.id === 'alerts-view') loadAllAlerts();
}

async function register(e) {
    e.preventDefault();
    const username = document.getElementById('registerUsername').value;
    const email = document.getElementById('registerEmail').value;
    const password = document.getElementById('registerPassword').value;
    try {
        const res = await fetch(`${API_URL}/auth/register`, {
            method: 'POST',
            headers: getHeaders(),
            body: JSON.stringify({ username, email, password }),
        });
        if (res.ok) {
            closeModal('registerModal');
            showToast('Account created! Please log in.');
            showLoginModal();
        } else {
            const err = await res.json().catch(() => ({}));
            showToast(err.detail || 'Registration failed', 'error');
        }
    } catch (err) {
        showToast('Network error', 'error');
    }
}

async function login(e) {
    e.preventDefault();
    const username = document.getElementById('loginUsername').value;
    const password = document.getElementById('loginPassword').value;
    try {
        const res = await fetch(`${API_URL}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: new URLSearchParams({ username, password }),
        });
        if (res.ok) {
            const data = await res.json();
            authToken = data.access_token;
            currentUser = data.user;
            // sessionStorage (not localStorage): token is cleared when the tab closes,
            // which limits the window an XSS bug or a shared/public machine could abuse it.
            sessionStorage.setItem('authToken', authToken);
            sessionStorage.setItem('currentUser', JSON.stringify(currentUser));
            closeModal('loginModal');
            document.getElementById('loginUsername').value = '';
            document.getElementById('loginPassword').value = '';
            updateUI();
            showToast('Login successful!');
            refreshAllData();
        } else {
            showToast('Login failed', 'error');
        }
    } catch (err) {
        showToast('Network error', 'error');
    }
}

function logout() {
    sessionStorage.removeItem('authToken');
    sessionStorage.removeItem('currentUser');
    authToken = null;
    currentUser = null;
    updateUI();
    showToast('Logged out');
    refreshAllData();
}

async function loadDashboardStats() {
    if (!authToken) {
        ['totalWebsites', 'activeWebsites', 'totalAlerts', 'criticalAlerts'].forEach(id => {
            document.getElementById(id).textContent = 0;
        });
        return;
    }
    try {
        const res = await fetch(`${API_URL}/dashboard/stats`, { headers: getHeaders() });
        if (res.ok) {
            const data = await res.json();
            document.getElementById('totalWebsites').textContent = data.total_websites || 0;
            document.getElementById('activeWebsites').textContent = data.active_websites || 0;
            document.getElementById('totalAlerts').textContent = data.total_alerts || 0;
            document.getElementById('criticalAlerts').textContent = data.critical_alerts || 0;
        }
    } catch (err) {
        console.error(err);
    }
}

function renderWebsiteCard(w) {
    return `
        <div class="website-card">
            <div><strong>${escapeHtml(w.name)}</strong><br><small>${escapeHtml(w.url)}</small></div>
            <div class="website-card-actions">
                <span class="status-pill status-${escapeHtml(w.status)}">● ${escapeHtml(w.status)}</span>
                <button class="btn btn-small" onclick="scanWebsite(${Number(w.id)})">🔍 Scan</button>
            </div>
        </div>
    `;
}

async function fetchWebsites() {
    if (!authToken) return null;
    const res = await fetch(`${API_URL}/websites`, { headers: getHeaders() });
    if (!res.ok) return null;
    return res.json();
}

async function loadWebsites() {
    const grid = document.getElementById('websitesGrid');
    if (!authToken) {
        grid.innerHTML = '<div class="empty-state">Log in to see your websites</div>';
        return;
    }
    const websites = await fetchWebsites();
    if (websites === null) return;
    grid.innerHTML = websites.length
        ? websites.map(renderWebsiteCard).join('')
        : '<div class="empty-state">No websites added</div>';
}

async function loadDashboardWebsites() {
    const grid = document.getElementById('dashboardWebsitesGrid');
    if (!authToken) {
        grid.innerHTML = '<div class="empty-state">Log in to see your websites</div>';
        return;
    }
    const websites = await fetchWebsites();
    if (websites === null) return;
    grid.innerHTML = websites.length
        ? websites.slice(0, 5).map(renderWebsiteCard).join('')
        : '<div class="empty-state">No websites added</div>';
}

async function addWebsite(e) {
    e.preventDefault();
    if (!authToken) {
        showToast('Please login first', 'warning');
        return;
    }
    const url = document.getElementById('websiteUrl').value;
    const name = document.getElementById('websiteName').value;
    try {
        const res = await fetch(`${API_URL}/websites`, {
            method: 'POST',
            headers: getHeaders(),
            body: JSON.stringify({ url, name }),
        });
        if (res.ok) {
            closeModal('addWebsiteModal');
            document.getElementById('websiteUrl').value = '';
            document.getElementById('websiteName').value = '';
            showToast('Website added!');
            refreshAllData();
        } else {
            const err = await res.json().catch(() => ({}));
            showToast(err.detail || 'Failed to add', 'error');
        }
    } catch (err) {
        showToast('Network error', 'error');
    }
}

async function scanWebsite(id) {
    try {
        const res = await fetch(`${API_URL}/websites/${id}/scan`, { headers: getHeaders() });
        if (res.ok) {
            showToast('Scan started!');
            setTimeout(refreshAllData, 3000);
        }
    } catch (err) {
        showToast('Error', 'error');
    }
}

async function scanAllWebsites() {
    if (!authToken) {
        showToast('Please login first', 'warning');
        return;
    }
    const websites = await fetchWebsites();
    if (!websites || websites.length === 0) {
        showToast('No websites to scan', 'warning');
        return;
    }
    showToast('Scanning all websites...');
    await Promise.all(websites.map(w =>
        fetch(`${API_URL}/websites/${w.id}/scan`, { headers: getHeaders() }).catch(() => null)
    ));
    setTimeout(() => {
        refreshAllData();
        showToast('Scan complete!');
    }, 3000);
}

function renderAlertItem(a) {
    const critical = a.severity === 'critical' || a.severity === 'high';
    return `
        <div class="alert-item ${critical ? 'critical' : ''}">
            <span class="alert-icon">🚨</span>
            <div>
                <strong>${escapeHtml(a.website_name)}</strong>: ${escapeHtml(a.title)} — ${escapeHtml(a.description)}
                <div class="alert-meta">Severity: ${escapeHtml(a.severity)}${a.detected_at ? ' · ' + new Date(a.detected_at).toLocaleString() : ''}</div>
            </div>
        </div>
    `;
}

async function fetchAlerts() {
    if (!authToken) return null;
    const res = await fetch(`${API_URL}/alerts`, { headers: getHeaders() });
    if (!res.ok) return null;
    return res.json();
}

async function loadRecentAlerts() {
    const box = document.getElementById('recentAlerts');
    if (!authToken) {
        box.innerHTML = '<div class="empty-state">Log in to see alerts</div>';
        return;
    }
    const alerts = await fetchAlerts();
    if (alerts === null) return;
    box.innerHTML = alerts.length
        ? alerts.slice(0, 5).map(renderAlertItem).join('')
        : '<div class="empty-state">No alerts</div>';
}

async function loadAllAlerts() {
    const box = document.getElementById('allAlerts');
    if (!authToken) {
        box.innerHTML = '<div class="empty-state">Log in to see alerts</div>';
        return;
    }
    const alerts = await fetchAlerts();
    if (alerts === null) return;
    box.innerHTML = alerts.length
        ? alerts.map(renderAlertItem).join('')
        : '<div class="empty-state">No alerts</div>';
}

// Kept for backwards compatibility with any inline handlers referencing the old name.
const loadAlerts = loadRecentAlerts;

function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 5000);
}

function showAddWebsiteModal() {
    if (!authToken) {
        showToast('Please login first', 'warning');
        return;
    }
    document.getElementById('addWebsiteModal').classList.add('show');
}

function showLoginModal() {
    document.getElementById('loginModal').classList.add('show');
}

function showRegisterModal() {
    document.getElementById('registerModal').classList.add('show');
}

function closeModal(id) {
    document.getElementById(id).classList.remove('show');
}
