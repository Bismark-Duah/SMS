/* auth.js — Login page logic */
const API_BASE = window.API_BASE || (window.location.origin.includes('http') ? (window.location.origin + '/api') : 'http://127.0.0.1:8000/api');

// Show any redirect message (e.g., "session expired")
const params = new URLSearchParams(window.location.search);
const msgParam = params.get('msg');
const msgEl = document.getElementById('authMessage');
if (msgParam && msgEl) {
  msgEl.textContent = decodeURIComponent(msgParam);
  msgEl.style.color = '#f59e0b';
}

const form = document.getElementById('authForm');

if (form) {
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (msgEl) { msgEl.textContent = ''; msgEl.style.color = ''; }

    const payload = {
      username: document.getElementById('username').value.trim(),
      password: document.getElementById('password').value,
    };

    const submitBtn = form.querySelector('button[type="submit"]') || form.querySelector('button');
    if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = 'Signing in…'; }

    try {
      const response = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Login failed');

      // Resolve highest priority leadership persona
      const rolesList = data.roles || [data.role];
      const rolePriority = {
        super_admin: 100, admin: 90, headmaster: 85, headmistress: 85,
        assistant_headmaster_academic: 80, assistant_head_academic: 80,
        assistant_headmaster_domestic: 80, assistant_head_domestic: 80,
        assistant_headmaster_admin: 80, assistant_head_admin: 80,
        hod: 70, senior_housemaster: 60, senior_housemistress: 60,
        senior_house_master: 60, senior_house_mistress: 60,
        house_master: 55, house_mistress: 55, assistant_house_master: 55, assistant_house_mistress: 55,
        form_master: 50, form_mistress: 50, bursar: 40, storekeeper: 40, security_officer: 40,
        teacher: 30, parent: 20, student: 10
      };
      let topRole = rolesList[0];
      let maxScore = -1;
      rolesList.forEach(r => {
        const score = rolePriority[(r || '').toLowerCase()] || 0;
        if (score > maxScore) { maxScore = score; topRole = (r || '').toLowerCase(); }
      });

      // Store all session data
      localStorage.setItem('userRole',     topRole || data.role);
      localStorage.setItem('activeRole',   topRole || data.role);
      localStorage.setItem('username',     data.username);
      localStorage.setItem('userId',       data.user_id);
      localStorage.setItem('accessToken',  data.access_token);
      localStorage.setItem('userRoles',    JSON.stringify(rolesList));
      if (data.is_super_admin) {
        localStorage.setItem('is_super_admin', 'true');
        localStorage.removeItem('is_super_admin_viewing');
        localStorage.setItem('school_name', 'Master System Portal');
        localStorage.setItem('school_abbreviation', 'SUPER ADMIN');
        localStorage.removeItem('school_id');
        localStorage.removeItem('school_logo');
      } else {
        localStorage.removeItem('is_super_admin');
        localStorage.removeItem('is_super_admin_viewing');
        if (data.school_id) localStorage.setItem('school_id', String(data.school_id));
        if (data.school_name) localStorage.setItem('school_name', data.school_name);
        if (data.school_code) localStorage.setItem('school_abbreviation', data.school_code);
        else localStorage.removeItem('school_abbreviation');
        if (data.school_mode) localStorage.setItem('school_mode', data.school_mode);
      }
      localStorage.setItem('_lastActivity', Date.now().toString());

      if (msgEl) {
        msgEl.textContent = `✔ Login successful. Redirecting…`;
        msgEl.style.color = '#4ade80';
      }

      // Super-Admin ALWAYS routes directly to super-admin.html (Master Portal)
      let dest = 'dashboard.html';
      if (data.is_super_admin) {
        dest = 'super-admin.html';
      } else {
        const nextParam = params.get('next');
        if (nextParam) dest = decodeURIComponent(nextParam);
      }
      setTimeout(() => { window.location.href = dest; }, 400);

    } catch (error) {
      if (msgEl) { msgEl.textContent = error.message; msgEl.style.color = '#f87171'; }
    } finally {
      if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = 'Login'; }
    }
  });
}
