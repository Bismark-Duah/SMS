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

      let data;
      try {
        data = await response.json();
      } catch (_) {
        data = null;
      }

      if (!response.ok) {
        const errMsg = (data && data.detail) || (response.status >= 500 ? 'Server error occurred. Please check backend console.' : 'Login failed');
        throw new Error(errMsg);
      }

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

      // Store all session data (sessionStorage for tab isolation, localStorage for persist)
      const sessionMap = {
        'userRole': topRole || data.role,
        'activeRole': topRole || data.role,
        'username': data.username,
        'userId': String(data.user_id),
        'accessToken': data.access_token,
        'userRoles': JSON.stringify(rolesList),
        'is_first_login': data.is_first_login ? 'true' : 'false',
        'phone_number': data.phone_number || '',
        'email': data.email || '',
        'contact_verified': data.contact_verified ? 'true' : 'false',
        '_lastActivity': Date.now().toString()
      };

      if (data.is_super_admin) {
        sessionMap['is_super_admin'] = 'true';
        sessionMap['school_name'] = 'Master System Portal';
        sessionMap['school_abbreviation'] = 'SUPER ADMIN';
        sessionStorage.removeItem('is_super_admin_viewing');
        sessionStorage.removeItem('school_id');
        sessionStorage.removeItem('school_logo');
        localStorage.removeItem('is_super_admin_viewing');
        localStorage.removeItem('school_id');
        localStorage.removeItem('school_logo');
      } else {
        sessionStorage.removeItem('is_super_admin');
        sessionStorage.removeItem('is_super_admin_viewing');
        localStorage.removeItem('is_super_admin');
        localStorage.removeItem('is_super_admin_viewing');
        if (data.school_id) sessionMap['school_id'] = String(data.school_id);
        if (data.school_name) sessionMap['school_name'] = data.school_name;
        if (data.school_code) sessionMap['school_abbreviation'] = data.school_code;
        if (data.school_mode) sessionMap['school_mode'] = data.school_mode;
      }

      for (const [k, v] of Object.entries(sessionMap)) {
        sessionStorage.setItem(k, v);
        localStorage.setItem(k, v);
      }

      if (msgEl) {
        msgEl.textContent = `✔ Login successful. Redirecting…`;
        msgEl.style.color = '#4ade80';
      }

      // ── Fetch tenant configuration immediately after login ──────────────
      // Populates boarding_status, boarding_hierarchy_mode etc. into
      // sessionStorage & localStorage BEFORE redirect, preventing flash of wrong features.
      if (!data.is_super_admin) {
        try {
          const settingsHeaders = { 'Authorization': `Bearer ${data.access_token}` };
          if (data.school_id) settingsHeaders['X-School-Id'] = String(data.school_id);
          const settingsRes = await fetch(`${API_BASE}/settings/`, { headers: settingsHeaders });
          if (settingsRes.ok) {
            const s = await settingsRes.json();
            const configKeys = ['boarding_status', 'boarding_hierarchy_mode', 'school_mode', 'school_name', 'school_logo', 'class_score_weight', 'exam_score_weight', 'system_theme'];
            configKeys.forEach(ck => {
              if (s[ck] !== undefined && s[ck] !== null) {
                sessionStorage.setItem(ck, String(s[ck]));
                localStorage.setItem(ck, String(s[ck]));
              }
            });
            // Refresh feature gate with accurate tenant config
            if (window.FeatureGate && window.FeatureGate.refresh) {
              window.FeatureGate.refresh();
            }
          }
        } catch (_) {
          // Non-critical — guard.js will sync settings on next page load
        }
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
