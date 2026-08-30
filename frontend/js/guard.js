/* ================================================================
   guard.js — Central Auth & Role Guard
   Imported by ALL pages that require authentication.

   Features:
   1. Token presence check → redirect to auth.html if missing
   2. JWT client-side expiry check → auto-logout when token expires
   3. Role-based page access → 403 page if wrong role
   4. Session inactivity timeout (30 min) → auto-logout
   5. "Change Password" modal available on every protected page
   ================================================================ */

(function () {
  'use strict';

  const API_BASE = window.API_BASE || (window.location.origin.includes('http') ? (window.location.origin + '/api') : 'http://127.0.0.1:8000/api');
  const INACTIVITY_LIMIT_MS = 30 * 60 * 1000; // 30 minutes
  const STORAGE_KEYS = ['accessToken', 'userRole', 'username', 'userId'];

  // Executive role helper sets
  const EXEC_ACADEMIC = ['admin', 'super_admin', 'headmaster', 'headmistress', 'assistant_headmaster_academic', 'assistant_head_academic', 'assistant_headmaster_admin', 'assistant_head_admin'];
  const EXEC_DOMESTIC = ['admin', 'super_admin', 'headmaster', 'headmistress', 'assistant_headmaster_domestic', 'assistant_head_domestic', 'assistant_headmaster_admin', 'assistant_head_admin'];
  const EXEC_ADMIN = ['admin', 'super_admin', 'headmaster', 'headmistress', 'assistant_headmaster_admin', 'assistant_head_admin'];
  const HOUSE_STAFF = ['senior_housemaster', 'senior_housemistress', 'senior_house_master', 'senior_house_mistress', 'house_master', 'house_mistress', 'assistant_house_master', 'assistant_house_mistress'];
  const FORM_STAFF = ['form_master', 'form_mistress'];

  // ── Page → allowed roles map ────────────────────────────────────
  // Pages NOT listed here are accessible to all authenticated users.
  const PAGE_ROLES = {
    'super-admin.html':   ['super_admin'],
    'users.html':         ['admin', 'super_admin', ...EXEC_ADMIN],
    'students.html':      ['admin', 'super_admin', ...EXEC_ACADEMIC, ...EXEC_DOMESTIC, 'bursar', ...FORM_STAFF, 'teacher'],
    'classes.html':       ['admin', 'super_admin', ...EXEC_ACADEMIC, 'hod'],
    'subjects.html':      ['admin', 'super_admin', ...EXEC_ACADEMIC, 'hod', 'teacher', ...FORM_STAFF],
    'programs.html':      ['admin', 'super_admin', ...EXEC_ACADEMIC],
    'departments.html':   ['admin', 'super_admin', ...EXEC_ACADEMIC, 'hod'],
    'academic.html':      ['admin', 'super_admin', ...EXEC_ACADEMIC],
    'assignments.html':   ['admin', 'super_admin', ...EXEC_ACADEMIC, 'hod'],
    'promotions.html':    ['admin', 'super_admin', ...EXEC_ACADEMIC, ...FORM_STAFF],
    'fees.html':          ['admin', 'super_admin', ...EXEC_ADMIN, 'bursar'],
    'assets.html':        ['admin', 'super_admin', ...EXEC_ADMIN, 'storekeeper'],
    'houses.html':        ['admin', 'super_admin', ...EXEC_DOMESTIC, ...HOUSE_STAFF],
    'exeat.html':         ['admin', 'super_admin', ...EXEC_DOMESTIC, ...HOUSE_STAFF, 'security_officer', 'teacher'],
    'discipline.html':    ['admin', 'super_admin', ...EXEC_DOMESTIC, ...HOUSE_STAFF, ...FORM_STAFF, 'hod', 'teacher'],
    'data-tools.html':    ['admin', 'super_admin', ...EXEC_ADMIN, 'storekeeper'],
    'settings.html':      ['admin', 'super_admin', ...EXEC_ADMIN],
    'bulk-entry.html':    ['admin', 'super_admin', ...EXEC_ACADEMIC, 'hod', 'teacher'],
    'results.html':       ['admin', 'super_admin', ...EXEC_ACADEMIC, 'hod', 'teacher'],
    'broadsheet.html':    ['admin', 'super_admin', ...EXEC_ACADEMIC, ...FORM_STAFF, 'hod'],
    'reports.html':       ['admin', 'super_admin', ...EXEC_ACADEMIC, ...FORM_STAFF, 'teacher', 'parent', 'student'],
    'announcements.html': ['admin', 'super_admin', ...EXEC_ADMIN, ...EXEC_DOMESTIC],
    'timetable.html':     ['admin', 'super_admin', ...EXEC_ACADEMIC, 'teacher', ...FORM_STAFF, 'hod'],
    'attendance.html':    ['admin', 'super_admin', ...EXEC_ACADEMIC, ...EXEC_DOMESTIC, ...HOUSE_STAFF, ...FORM_STAFF, 'teacher'],
    'parent-view.html':   ['admin', 'super_admin', ...EXEC_ACADEMIC, 'teacher', 'parent'],
    'dashboard.html':     ['admin', 'super_admin', ...EXEC_ACADEMIC, ...EXEC_DOMESTIC, ...HOUSE_STAFF, ...FORM_STAFF, 'hod', 'teacher', 'bursar', 'storekeeper', 'security_officer', 'parent', 'student'],
    'cumulative-record.html': ['admin', 'super_admin', ...EXEC_ACADEMIC, ...FORM_STAFF],
    'report-card.html':   ['admin', 'super_admin', ...EXEC_ACADEMIC, ...FORM_STAFF, 'teacher', 'parent', 'student'],
    'clearance.html':     ['admin', 'super_admin', ...EXEC_ACADEMIC, ...EXEC_DOMESTIC, 'bursar', 'storekeeper', ...HOUSE_STAFF],
  };

  // ── Helpers ─────────────────────────────────────────────────────
  function getPageName() {
    return window.location.pathname.split('/').pop() || 'index.html';
  }

  function clearSession() {
    STORAGE_KEYS.forEach(k => localStorage.removeItem(k));
    localStorage.removeItem('_lastActivity');
  }

  function redirectToLogin(reason) {
    clearSession();
    // Preserve the page they wanted to visit
    const dest = encodeURIComponent(window.location.href);
    window.location.href = 'auth.html?next=' + dest + (reason ? '&msg=' + encodeURIComponent(reason) : '');
  }

  function show403(page, role) {
    document.body.innerHTML = `
      <div style="
        display:flex; flex-direction:column; align-items:center; justify-content:center;
        min-height:100vh; font-family:sans-serif; background:#0f172a; color:#f8fafc;
        text-align:center; padding:32px;
      ">
        <div style="font-size:4rem; margin-bottom:16px;">🚫</div>
        <h1 style="font-size:1.8rem; margin:0 0 8px;">Access Denied</h1>
        <p style="color:#94a3b8; margin:0 0 24px;">
          Your role (<strong style="color:#f8fafc;">${role}</strong>) does not have permission
          to access <strong style="color:#f8fafc;">${page}</strong>.
        </p>
        <a href="dashboard.html"
           style="background:#3b82f6; color:#fff; padding:12px 28px; border-radius:8px;
                  text-decoration:none; font-weight:600; font-size:0.95rem;">
          ← Back to Dashboard
        </a>
      </div>`;
  }

  // ── Decode JWT payload (no verification — server already verified) ──
  function decodeJwtPayload(token) {
    try {
      const parts = token.split('.');
      if (parts.length !== 3) return null;
      const padding = '='.repeat((4 - parts[1].length % 4) % 4);
      return JSON.parse(atob(parts[1].replace(/-/g, '+').replace(/_/g, '/') + padding));
    } catch {
      return null;
    }
  }

  // ── Inactivity tracker ──────────────────────────────────────────
  let _inactivityTimer = null;

  function resetInactivityTimer() {
    localStorage.setItem('_lastActivity', Date.now().toString());
    clearTimeout(_inactivityTimer);
    _inactivityTimer = setTimeout(() => {
      redirectToLogin('Your session expired due to inactivity. Please log in again.');
    }, INACTIVITY_LIMIT_MS);
  }

  function startActivityListeners() {
    ['mousemove', 'keydown', 'click', 'scroll', 'touchstart'].forEach(evt => {
      document.addEventListener(evt, resetInactivityTimer, { passive: true });
    });
    resetInactivityTimer();

    // Also check on visibility change (e.g., returning to a tab)
    document.addEventListener('visibilitychange', () => {
      if (!document.hidden) {
        const last = parseInt(localStorage.getItem('_lastActivity') || '0', 10);
        if (Date.now() - last > INACTIVITY_LIMIT_MS) {
          redirectToLogin('Your session expired due to inactivity. Please log in again.');
        }
      }
    });
  }

  // ── Change Password Modal ───────────────────────────────────────
  function injectPasswordModal() {
    const modal = document.createElement('div');
    modal.id = 'changePasswordModal';
    modal.style.cssText = `
      display:none; position:fixed; inset:0; z-index:9999;
      background:rgba(0,0,0,0.6); backdrop-filter:blur(4px);
      align-items:center; justify-content:center;
    `;
    modal.innerHTML = `
      <div style="
        background:#1e293b; border:1px solid #334155; border-radius:16px;
        padding:32px; width:100%; max-width:400px; margin:16px;
        box-shadow:0 24px 48px rgba(0,0,0,0.5);
      ">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:24px;">
          <h3 style="margin:0; color:#f8fafc; font-size:1.1rem;">🔐 Change Password</h3>
          <button onclick="document.getElementById('changePasswordModal').style.display='none'"
            style="background:none; border:none; color:#94a3b8; font-size:1.4rem; cursor:pointer; line-height:1;">×</button>
        </div>

        <div id="cpwMsg" style="display:none; padding:10px 14px; border-radius:8px; margin-bottom:16px; font-size:0.88rem;"></div>

        <label style="display:block; color:#94a3b8; font-size:0.8rem; font-weight:700; text-transform:uppercase; letter-spacing:.06em; margin-bottom:4px;">Current Password</label>
        <input id="cpwOld" type="password" placeholder="Enter current password"
          style="width:100%; box-sizing:border-box; padding:10px 14px; border-radius:8px; border:1px solid #334155;
                 background:#0f172a; color:#f8fafc; font-size:0.95rem; margin-bottom:16px; outline:none;" />

        <label style="display:block; color:#94a3b8; font-size:0.8rem; font-weight:700; text-transform:uppercase; letter-spacing:.06em; margin-bottom:4px;">New Password</label>
        <input id="cpwNew" type="password" placeholder="At least 6 characters"
          style="width:100%; box-sizing:border-box; padding:10px 14px; border-radius:8px; border:1px solid #334155;
                 background:#0f172a; color:#f8fafc; font-size:0.95rem; margin-bottom:16px; outline:none;" />

        <label style="display:block; color:#94a3b8; font-size:0.8rem; font-weight:700; text-transform:uppercase; letter-spacing:.06em; margin-bottom:4px;">Confirm New Password</label>
        <input id="cpwConfirm" type="password" placeholder="Repeat new password"
          style="width:100%; box-sizing:border-box; padding:10px 14px; border-radius:8px; border:1px solid #334155;
                 background:#0f172a; color:#f8fafc; font-size:0.95rem; margin-bottom:24px; outline:none;" />

        <button id="cpwSubmitBtn" onclick="window.Guard.submitPasswordChange()"
          style="width:100%; padding:12px; border-radius:8px; border:none;
                 background:#3b82f6; color:#fff; font-size:0.95rem; font-weight:700; cursor:pointer;">
          Change Password
        </button>
      </div>
    `;
    document.body.appendChild(modal);
  }

  async function submitPasswordChange() {
    const old_password = document.getElementById('cpwOld').value.trim();
    const new_password = document.getElementById('cpwNew').value.trim();
    const confirm     = document.getElementById('cpwConfirm').value.trim();
    const msgEl       = document.getElementById('cpwMsg');

    function showMsg(text, isError) {
      msgEl.textContent = text;
      msgEl.style.display = 'block';
      msgEl.style.background = isError ? 'rgba(239,68,68,0.15)' : 'rgba(34,197,94,0.15)';
      msgEl.style.color = isError ? '#f87171' : '#4ade80';
      msgEl.style.border = `1px solid ${isError ? 'rgba(239,68,68,0.3)' : 'rgba(34,197,94,0.3)'}`;
    }

    if (!old_password || !new_password || !confirm) {
      showMsg('All fields are required.', true); return;
    }
    if (new_password.length < 6) {
      showMsg('New password must be at least 6 characters.', true); return;
    }
    if (new_password !== confirm) {
      showMsg('New passwords do not match.', true); return;
    }

    const btn = document.getElementById('cpwSubmitBtn');
    btn.disabled = true;
    btn.textContent = 'Changing…';

    try {
      const res = await fetch(`${API_BASE}/auth/change-password`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer ' + localStorage.getItem('accessToken'),
        },
        body: JSON.stringify({ old_password, new_password }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Change failed');

      showMsg('✔ Password changed successfully!', false);
      document.getElementById('cpwOld').value = '';
      document.getElementById('cpwNew').value = '';
      document.getElementById('cpwConfirm').value = '';
      setTimeout(() => {
        document.getElementById('changePasswordModal').style.display = 'none';
        msgEl.style.display = 'none';
      }, 2000);
    } catch (err) {
      showMsg(err.message, true);
    } finally {
      btn.disabled = false;
      btn.textContent = 'Change Password';
    }
  }

  function getStored(key) {
    return sessionStorage.getItem(key) || localStorage.getItem(key);
  }

  // ── Inject topbar user pill (shown on all pages) ────────────────
  function injectUserPill() {
    try {
      if (document.getElementById('guardUserPill')) return;

    const username = getStored('username') || '?';
    const primaryRole = getStored('userRole') || '';
    const rawRolesStr = getStored('userRoles');
    const userRoles = rawRolesStr ? JSON.parse(rawRolesStr).map(r => String(r).toLowerCase()) : [primaryRole.toLowerCase()];
    const hasAssistantHeadRole = userRoles.some(r => r.includes('assistant_head'));
    const isSuperAdmin = userRoles.includes('super_admin');
    
    // Sanitize selectable roles for persona switching
    const selectableRoles = (hasAssistantHeadRole && !isSuperAdmin)
      ? userRoles.filter(r => r !== 'admin')
      : userRoles;

    const rolePriorityMap = {
      super_admin: 100, headmaster: 85, headmistress: 85,
      assistant_headmaster_academic: 80, assistant_head_academic: 80,
      assistant_headmaster_domestic: 80, assistant_head_domestic: 80,
      assistant_headmaster_admin: 80, assistant_head_admin: 80,
      admin: (hasAssistantHeadRole && !isSuperAdmin) ? 0 : 90,
      hod: 70, senior_housemaster: 60, senior_housemistress: 60,
      senior_house_master: 60, senior_house_mistress: 60,
      house_master: 55, house_mistress: 55, assistant_house_master: 55, assistant_house_mistress: 55,
      form_master: 50, form_mistress: 50, bursar: 40, storekeeper: 40, security_officer: 40,
      teacher: 30, parent: 20, student: 10
    };
    let topRole = userRoles[0];
    let maxScore = -1;
    userRoles.forEach(r => {
      const score = rolePriorityMap[r] || 0;
      if (score > maxScore) { maxScore = score; topRole = r; }
    });
    let activeRole = (getStored('activeRole') || topRole || primaryRole || userRoles[0]).toLowerCase();
    if (hasAssistantHeadRole && !isSuperAdmin && activeRole === 'admin') {
      const assistHeadRole = userRoles.find(r => r.includes('assistant_head')) || userRoles[0];
      activeRole = assistHeadRole;
      sessionStorage.setItem('activeRole', activeRole);
      sessionStorage.setItem('userRole', activeRole);
      localStorage.setItem('activeRole', activeRole);
      localStorage.setItem('userRole', activeRole);
    }

    const ROLE_DISPLAY_NAMES = {
      'admin': 'Admin',
      'super_admin': 'Super Admin',
      'headmaster': 'Headmaster / Principal',
      'headmistress': 'Headmistress / Principal',
      'assistant_headmaster_academic': 'Assistant Head (Academic)',
      'assistant_head_academic': 'Assistant Head (Academic)',
      'assistant_headmaster_domestic': 'Assistant Head (Domestic)',
      'assistant_head_domestic': 'Assistant Head (Domestic)',
      'assistant_headmaster_admin': 'Assistant Head (Admin)',
      'assistant_head_admin': 'Assistant Head (Admin)',
      'hod': 'Head of Department (HOD)',
      'form_master': 'Form Master / Mistress',
      'form_mistress': 'Form Master / Mistress',
      'senior_housemaster': 'Senior House Master / Mistress',
      'senior_house_master': 'Senior House Master / Mistress',
      'house_master': 'House Master / Mistress',
      'house_mistress': 'House Master / Mistress',
      'teacher': 'Subject Teacher',
      'bursar': 'Bursar / Accountant',
      'storekeeper': 'Storekeeper',
      'security_officer': 'Security Officer',
      'student': 'Student',
      'parent': 'Parent'
    };

    const displayRoleName = ROLE_DISPLAY_NAMES[activeRole] || activeRole.toUpperCase();

    // Render Impersonation Banner if active
    const isImpersonating = getStored('is_impersonating') === 'true';
    const impersonatorUsername = getStored('impersonator_username') || 'Administrator';
    if (isImpersonating && !document.getElementById('impersonationBanner')) {
      const impBanner = document.createElement('div');
      impBanner.id = 'impersonationBanner';
      impBanner.style.cssText = `
        position: fixed !important;
        top: 0 !important;
        left: 0 !important;
        right: 0 !important;
        width: 100vw !important;
        height: 38px !important;
        background: linear-gradient(90deg, #b91c1c, #dc2626) !important;
        color: #ffffff !important;
        padding: 4px 20px !important;
        font-size: 0.83rem !important;
        font-weight: 700 !important;
        display: flex !important;
        justify-content: space-between !important;
        align-items: center !important;
        z-index: 999999 !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3) !important;
        font-family: system-ui, -apple-system, sans-serif !important;
        box-sizing: border-box !important;
      `;
      impBanner.innerHTML = `
        <div style="display:flex; align-items:center; gap:10px;">
          <span style="font-size:1.1rem;">⚠️</span>
          <span><strong>IMPERSONATION MODE:</strong> Viewing portal as <strong>${username}</strong> (${displayRoleName}) • Initiated by Admin <strong>${impersonatorUsername}</strong></span>
        </div>
        <button id="exitImpersonationBtn" style="background:#ffffff; color:#991b1b; border:none; padding:4px 12px; border-radius:6px; font-weight:800; font-size:0.8rem; cursor:pointer; transition:all 0.15s ease; box-shadow:0 2px 6px rgba(0,0,0,0.2);">
          ❌ Exit View Mode
        </button>
      `;
      document.body.prepend(impBanner);
      document.body.classList.add('has-impersonation-banner');

      document.getElementById('exitImpersonationBtn')?.addEventListener('click', () => {
        const adminBackup = getStored('_admin_backup_session');
        if (adminBackup) {
          try {
            const data = JSON.parse(adminBackup);
            Object.keys(data).forEach(k => {
              sessionStorage.setItem(k, data[k]);
              localStorage.setItem(k, data[k]);
            });
          } catch (e) {}
          sessionStorage.removeItem('_admin_backup_session');
          localStorage.removeItem('_admin_backup_session');
          sessionStorage.removeItem('is_impersonating');
          localStorage.removeItem('is_impersonating');
          sessionStorage.removeItem('impersonator_username');
          localStorage.removeItem('impersonator_username');
        }
        window.location.href = 'dashboard.html';
      });
    }

    const roleColors = {
      admin: '#6366f1', teacher: '#0ea5e9', parent: '#10b981', student: '#f59e0b', hod: '#818cf8', bursar: '#10b981'
    };
    const color = roleColors[activeRole] || '#6b7280';

    const topbar = document.querySelector('.topbar');

    const pillWrapper = document.createElement('div');
    pillWrapper.id = 'guardUserWrapper';
    pillWrapper.style.cssText = `
      position: relative;
      display: flex;
      align-items: center;
      margin-left: auto;
      z-index: 9500;
    `;

    const pill = document.createElement('div');
    pill.id = 'guardUserPill';
    pill.style.cssText = `
      display:flex; align-items:center; gap:8px;
      background:rgba(15,23,42,0.7); border:1px solid rgba(255,255,255,0.12);
      border-radius:50px; padding:4px 12px 4px 6px;
      backdrop-filter:blur(8px); box-shadow:0 4px 16px rgba(0,0,0,0.25);
      font-family:sans-serif; cursor:pointer; user-select:none;
      transition:all .2s ease;
    `;
    pill.title = 'Click for account & system options';
    pill.innerHTML = `
      <span style="
        width:26px; height:26px; border-radius:50%;
        background:${color}22; border:2px solid ${color};
        display:flex; align-items:center; justify-content:center;
        font-size:0.75rem; font-weight:800; color:${color};
        text-transform:uppercase; flex-shrink:0;
      ">${username.charAt(0)}</span>
      <span style="color:#f8fafc; font-size:0.82rem; font-weight:600;">${username}</span>
      <span style="
        background:${color}33; color:${color};
        font-size:0.65rem; font-weight:800; text-transform:uppercase;
        padding:2px 6px; border-radius:20px;
      ">${displayRoleName}</span>
      <span style="font-size:0.7rem; opacity:0.6;">▾</span>
    `;

    const activeTheme = localStorage.getItem('system_theme') || 'midnight';
    const activeLayout = localStorage.getItem('system_layout_mode') || 'sidebar';

    // Unified Dropdown menu
    const menu = document.createElement('div');
    menu.id = 'guardPillMenu';
    menu.style.cssText = `
      display:none; position:absolute; top:calc(100% + 8px); right:0; z-index:9501;
      background:#1e293b; border:1px solid #334155; border-radius:12px;
      padding:10px; min-width:230px;
      box-shadow:0 12px 32px rgba(0,0,0,0.5);
      font-family:sans-serif;
    `;

    const roleSelectHtml = selectableRoles.length > 1 ? `
      <div style="padding:4px 8px 2px; font-size:0.72rem; color:#818cf8; font-weight:700; text-transform:uppercase;">🎭 Switch Active Persona</div>
      <div style="padding:0 8px 8px;">
        <select id="guardRoleSelect" style="width:100%; padding:6px 8px; font-size:0.82rem; background:#0f172a; color:#f8fafc; border:1px solid #6366f1; border-radius:6px; cursor:pointer; font-weight:600;">
          ${selectableRoles.map(r => `<option value="${r}" ${r===activeRole?'selected':''}>${ROLE_DISPLAY_NAMES[r]||r.toUpperCase()}</option>`).join('')}
        </select>
      </div>
      <hr style="border:none; border-top:1px solid #334155; margin:6px 0;">
    ` : '';

    menu.innerHTML = `
      <div style="padding:4px 8px 8px; font-size:0.72rem; color:#94a3b8; font-weight:700; text-transform:uppercase; letter-spacing:.06em; border-bottom:1px solid #334155; margin-bottom:8px;">
        👤 ${username} <span style="color:${color};">(${displayRoleName})</span>
      </div>

      ${roleSelectHtml}

      <div style="padding:4px 8px 2px; font-size:0.72rem; color:#64748b; font-weight:700; text-transform:uppercase;">🎨 Color Theme</div>
      <div style="padding:0 8px 8px;">
        <select id="guardThemeSelect" style="width:100%; padding:6px 8px; font-size:0.82rem; background:#0f172a; color:#f8fafc; border:1px solid #334155; border-radius:6px; cursor:pointer;">
          <option value="midnight" ${activeTheme==='midnight'?'selected':''}>🌙 Midnight Dark</option>
          <option value="light" ${activeTheme==='light'?'selected':''}>☀️ Clean Light</option>
          <option value="emerald" ${activeTheme==='emerald'?'selected':''}>🌲 Emerald Oasis</option>
          <option value="ocean" ${activeTheme==='ocean'?'selected':''}>🌊 Ocean Sapphire</option>
        </select>
      </div>

      <hr style="border:none; border-top:1px solid #334155; margin:6px 0;">

      <button id="guardChangePwBtn"
        style="display:block; width:100%; text-align:left; padding:8px 10px; border:none;
               background:none; color:#f8fafc; font-size:0.85rem; border-radius:6px; cursor:pointer;">
        🔑 Change Password
      </button>
      <button id="guardLogoutBtn"
        style="display:block; width:100%; text-align:left; padding:8px 10px; border:none;
               background:none; color:#f87171; font-size:0.85rem; border-radius:6px; cursor:pointer; margin-top:2px;">
        🚪 Logout
      </button>
    `;

    pillWrapper.appendChild(pill);
    pillWrapper.appendChild(menu);

    if (topbar) {
      const actionsContainer = topbar.querySelector('div[style*="margin-left:auto"]') || (topbar.children.length > 1 ? topbar.children[topbar.children.length - 1] : null);
      if (actionsContainer && actionsContainer !== topbar.firstElementChild) {
        pillWrapper.style.marginLeft = '0';
        actionsContainer.appendChild(pillWrapper);
      } else {
        topbar.appendChild(pillWrapper);
      }
    } else {
      pillWrapper.style.position = 'fixed';
      pillWrapper.style.top = '12px';
      pillWrapper.style.right = '16px';
      document.body.appendChild(pillWrapper);
    }

    // Role switcher listener
    const roleSelect = document.getElementById('guardRoleSelect');
    if (roleSelect) {
      roleSelect.addEventListener('change', (e) => {
        const selectedRole = e.target.value;
        sessionStorage.setItem('activeRole', selectedRole);
        sessionStorage.setItem('userRole', selectedRole);
        localStorage.setItem('activeRole', selectedRole);
        localStorage.setItem('userRole', selectedRole);
        if (window.mountSidebarNav) window.mountSidebarNav();
        window.location.reload();
      });
    }

    // Toggle menu
    pill.addEventListener('click', (e) => {
      e.stopPropagation();
      const visible = menu.style.display === 'block';
      menu.style.display = visible ? 'none' : 'block';
    });
    document.addEventListener('click', () => { menu.style.display = 'none'; });
    menu.addEventListener('click', e => e.stopPropagation());

    // Theme selector handler
    const themeSelect = document.getElementById('guardThemeSelect');
    if (themeSelect) {
      themeSelect.addEventListener('change', (e) => {
        if (window.SMSStateBus && window.SMSStateBus.setTheme) {
          window.SMSStateBus.setTheme(e.target.value);
        } else if (window.setTheme) {
          window.setTheme(e.target.value);
        } else if (window.applyTheme) {
          window.applyTheme(e.target.value);
        }
      });
    }

    // Layout selector handler
    const layoutSelect = document.getElementById('guardLayoutSelect');
    if (layoutSelect) {
      layoutSelect.addEventListener('change', (e) => {
        if (window.applyLayout) window.applyLayout(e.target.value);
        localStorage.setItem('system_layout_mode', e.target.value);
      });
    }

    // Change password handler
    document.getElementById('guardChangePwBtn').addEventListener('click', () => {
      menu.style.display = 'none';
      const modal = document.getElementById('changePasswordModal');
      if (modal) {
        modal.style.display = 'flex';
        const oldField = document.getElementById('cpwOld');
        if (oldField) oldField.focus();
      }
    });

    // Logout handler (Cross-Tab sync)
    document.getElementById('guardLogoutBtn')?.addEventListener('click', () => {
      if (window.SMSStateBus && window.SMSStateBus.broadcastLogout) {
        window.SMSStateBus.broadcastLogout();
      } else {
        clearSession();
        window.location.href = 'auth.html';
      }
    });
    } catch (err) {
      console.error('Error in injectUserPill:', err);
    }

  }

  function injectSuperAdminBanner() {
    const isViewing = (sessionStorage.getItem('is_super_admin_viewing') || localStorage.getItem('is_super_admin_viewing')) === 'true';
    if (isViewing) {
      const schoolName = sessionStorage.getItem('school_name') || localStorage.getItem('school_name') || 'School View';
      let banner = document.getElementById('superAdminBanner');
      if (!banner) {
        banner = document.createElement('div');
        banner.id = 'superAdminBanner';
        document.body.prepend(banner);
      }
      banner.style.cssText = 'position: fixed !important; top: 0 !important; left: 0 !important; right: 0 !important; width: 100vw !important; height: 38px !important; background: linear-gradient(135deg, #4f46e5 0%, #6366f1 100%); color: #ffffff; text-align: center; padding: 6px 16px; font-size: 0.85rem; font-weight: 600; z-index: 999999 !important; display: flex; justify-content: center; align-items: center; gap: 16px; border-bottom: 1px solid rgba(255,255,255,0.2); box-shadow: 0 2px 8px rgba(0,0,0,0.3); box-sizing: border-box !important;';
      banner.innerHTML = `
        <span>👁️ Viewing <strong>${escapeHtml(schoolName)}</strong> as Platform Super-Admin</span>
        <button onclick="window.exitSchoolView ? window.exitSchoolView() : (sessionStorage.removeItem('is_super_admin_viewing'), sessionStorage.removeItem('school_id'), localStorage.removeItem('is_super_admin_viewing'), localStorage.removeItem('school_id'), localStorage.setItem('school_name','Master System Portal'), localStorage.setItem('school_abbreviation','SUPER ADMIN'), window.location.href='super-admin.html')" style="background: rgba(255,255,255,0.25); color: #fff; padding: 3px 12px; border-radius: 4px; border: 1px solid rgba(255,255,255,0.4); font-size: 0.8rem; font-weight: 700; cursor: pointer;">← Return to Master Portal</button>
      `;
      document.body.classList.add('has-superadmin-banner');
    } else {
      const banner = document.getElementById('superAdminBanner');
      if (banner) banner.remove();
      document.body.classList.remove('has-superadmin-banner');
    }
  }
  window.updateSuperAdminBanner = injectSuperAdminBanner;

  // ── Main guard function ─────────────────────────────────────────
  function guard(options = {}) {
    const token = localStorage.getItem('accessToken');
    const role  = localStorage.getItem('userRole') || '';
    const page  = getPageName();

    // 1. No token → redirect to login
    if (!token) {
      redirectToLogin();
      return false;
    }

    // 2. Check JWT expiry (client-side only — server also validates)
    const payload = decodeJwtPayload(token);
    if (payload && payload.exp && payload.exp < Math.floor(Date.now() / 1000)) {
      redirectToLogin('Your session has expired. Please log in again.');
      return false;
    }

    // 3. Role-based access check
    const activeRole = (localStorage.getItem('activeRole') || localStorage.getItem('userRole') || '').toLowerCase();
    const allowedRoles = PAGE_ROLES[page];
    if (allowedRoles) {
      const hasPermission = ['admin', 'super_admin'].includes(activeRole) || allowedRoles.includes(activeRole);
      if (!hasPermission) {
        show403(page, activeRole);
        return false;
      }
    }

    // 4. Start inactivity timer
    startActivityListeners();

    // 5. Sync system settings from DB into localStorage & Inject UI
    syncSystemSettings();

    function initGuardUI() {
      injectPasswordModal();
      injectUserPill();
      injectSuperAdminBanner();
    }

    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', initGuardUI);
    } else {
      initGuardUI();
    }

    return true;
  }

  async function syncSystemSettings() {
    const token = sessionStorage.getItem('accessToken') || localStorage.getItem('accessToken');
    if (!token) return;
    try {
      const headers = window.getAuthHeaders ? window.getAuthHeaders() : { 'Authorization': `Bearer ${token}` };

      const res = await fetch(`${API_BASE}/settings/`, { headers });
      if (res.ok) {
        const data = await res.json();
        const isViewing = (sessionStorage.getItem('is_super_admin_viewing') || localStorage.getItem('is_super_admin_viewing')) === 'true';
        const isSuperAdmin = ((sessionStorage.getItem('userRole') || localStorage.getItem('userRole')) === 'super_admin' || localStorage.getItem('is_super_admin') === 'true') && (sessionStorage.getItem('userRole') || localStorage.getItem('userRole')) !== 'admin' && !isViewing;

        if (data.boarding_status) {
          sessionStorage.setItem('boarding_status', data.boarding_status);
          localStorage.setItem('boarding_status', data.boarding_status);
        }
        if (data.school_logo) {
          sessionStorage.setItem('school_logo', data.school_logo);
          localStorage.setItem('school_logo', data.school_logo);
        }
        if (data.system_theme) {
          sessionStorage.setItem('system_theme', data.system_theme);
          localStorage.setItem('system_theme', data.system_theme);
        }
        if (data.class_score_weight) {
          sessionStorage.setItem('class_score_weight', String(data.class_score_weight));
          localStorage.setItem('class_score_weight', String(data.class_score_weight));
        }
        if (data.exam_score_weight) {
          sessionStorage.setItem('exam_score_weight', String(data.exam_score_weight));
          localStorage.setItem('exam_score_weight', String(data.exam_score_weight));
        }

        if (isSuperAdmin && !isViewing) {
          sessionStorage.setItem('school_name', 'Master System Portal');
          sessionStorage.setItem('school_abbreviation', 'SUPER ADMIN');
          sessionStorage.setItem('school_mode', 'COMBINED');
          localStorage.setItem('school_name', 'Master System Portal');
          localStorage.setItem('school_abbreviation', 'SUPER ADMIN');
          localStorage.setItem('school_mode', 'COMBINED');
        } else if (!isSuperAdmin || isViewing) {
          if (data.school_mode) {
            sessionStorage.setItem('school_mode', data.school_mode);
            localStorage.setItem('school_mode', data.school_mode);
          }
          if (data.school_name) {
            sessionStorage.setItem('school_name', data.school_name);
            localStorage.setItem('school_name', data.school_name);
          }
          if (data.school_abbreviation || data.school_code) {
            const abb = data.school_abbreviation || data.school_code;
            sessionStorage.setItem('school_abbreviation', abb);
            localStorage.setItem('school_abbreviation', abb);
          } else if (localStorage.getItem('school_abbreviation') === 'SUPER ADMIN') {
            sessionStorage.removeItem('school_abbreviation');
            localStorage.removeItem('school_abbreviation');
          }
        }

        if (window.SMSStateBus && window.SMSStateBus.updateTabTitle) {
          window.SMSStateBus.updateTabTitle();
        }
      }

      // Sync active user roles from backend to upgrade live sessions automatically
      const meRes = await fetch(`${API_BASE}/auth/me`, { headers });
      if (meRes.ok) {
        const meData = await meRes.json();
        if (Array.isArray(meData.roles) && meData.roles.length > 0) {
          const storedRolesStr = localStorage.getItem('userRoles');
          const storedRoles = storedRolesStr ? JSON.parse(storedRolesStr).map(r => r.toLowerCase()) : [];

          const missingRoles = meData.roles.some(r => !storedRoles.includes(r.toLowerCase()));
          if (missingRoles || storedRoles.length !== meData.roles.length) {
            localStorage.setItem('userRoles', JSON.stringify(meData.roles));

            const rolePriorityMap = {
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
            let topRole = meData.roles[0];
            let maxScore = -1;
            meData.roles.forEach(r => {
              const score = rolePriorityMap[(r || '').toLowerCase()] || 0;
              if (score > maxScore) { maxScore = score; topRole = (r || '').toLowerCase(); }
            });

            if (!localStorage.getItem('activeRole') || localStorage.getItem('userRole') === 'teacher') {
              localStorage.setItem('userRole', topRole);
              localStorage.setItem('activeRole', topRole);
            }
          }
        }
      }
    } catch (_) {}
  }

  // ── Expose public API ───────────────────────────────────────────
  window.Guard = {
    guard,
    submitPasswordChange,
    clearSession,
    API_BASE,
    getRole: () => localStorage.getItem('userRole') || '',
    getUserId: () => localStorage.getItem('userId'),
    getToken: () => localStorage.getItem('accessToken'),
    getHeaders: (extra = {}) => {
      const h = {
        'Authorization': 'Bearer ' + localStorage.getItem('accessToken'),
        ...extra
      };
      const sid = localStorage.getItem('school_id');
      if (sid && !h['X-School-Id']) h['X-School-Id'] = sid;
      return h;
    },
    getJsonHeaders: () => {
      const h = {
        'Authorization': 'Bearer ' + localStorage.getItem('accessToken'),
        'Content-Type': 'application/json',
      };
      const sid = localStorage.getItem('school_id');
      if (sid && !h['X-School-Id']) h['X-School-Id'] = sid;
      return h;
    },
    showAlertDialog: (...args) => window.showAlertDialog ? window.showAlertDialog(...args) : Promise.resolve(),
    showConfirmDialog: (...args) => window.showConfirmDialog ? window.showConfirmDialog(...args) : Promise.resolve(true),
    showToast: (...args) => window.showToast ? window.showToast(...args) : null,
  };

  // ── Navigation & Unsaved Changes Guard ─────────────────────────
  document.addEventListener('click', async (e) => {
    const link = e.target.closest('a[href]');
    if (!link) return;
    const href = link.getAttribute('href');
    if (!href || href.startsWith('#') || href.startsWith('javascript:') || href.startsWith('mailto:') || href.startsWith('tel:')) return;
    if (link.target === '_blank') return;

    if (window.__hasUnsavedChanges) {
      e.preventDefault();
      const confirmLeave = await (window.showConfirmDialog ? window.showConfirmDialog(
        'Unsaved Changes Warning',
        'You have unsaved work on this page. If you leave now, unsaved changes may be lost. Are you sure you want to proceed?',
        'Leave Without Saving',
        'Stay on Page',
        'warning'
      ) : Promise.resolve(confirm('You have unsaved changes. Leave anyway?')));

      if (confirmLeave) {
        window.__hasUnsavedChanges = false;
        window.location.href = href;
      }
    }
  });

  // ── Enterprise In-App Modal & Toast Engine Fallback / Init ────
  function ensureEnterpriseDialogs() {
    if (window.showAlertDialog && window.showConfirmDialog && window.showToast) return;

    function getToastContainer() {
      let c = document.querySelector('.enterprise-toast-container');
      if (!c) {
        c = document.createElement('div');
        c.className = 'enterprise-toast-container';
        document.body.appendChild(c);
      }
      return c;
    }

    function escapeHtml(text) {
      if (!text) return '';
      return String(text).replace(/[&<>"']/g, function(m) {
        return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[m];
      });
    }

    window.showToast = function(message, type = 'info', duration = 3500) {
      const container = getToastContainer();
      const item = document.createElement('div');
      item.className = `enterprise-toast-item type-${type}`;

      let icon = 'ℹ️';
      if (type === 'success') icon = '✅';
      else if (type === 'warning') icon = '⚠️';
      else if (type === 'danger' || type === 'error') icon = '🚫';

      item.innerHTML = `
        <div style="display:flex; align-items:center; gap:8px;">
          <span style="font-size:1.1rem;">${icon}</span>
          <span>${escapeHtml(message)}</span>
        </div>
        <button type="button" style="background:none; border:none; color:inherit; font-size:1.1rem; cursor:pointer; opacity:0.6; padding:0 4px;" onclick="this.parentElement.remove()">✕</button>
      `;

      container.appendChild(item);
      setTimeout(() => {
        item.style.opacity = '0';
        item.style.transform = 'translateY(10px) scale(0.95)';
        setTimeout(() => item.remove(), 250);
      }, duration);
    };

    window.showAlertDialog = function(titleOrMessage, messageOrType, type = 'info', options = {}) {
      return new Promise((resolve) => {
        let title = 'System Notification';
        let message = '';
        let dialogType = type;

        if (messageOrType && typeof messageOrType === 'string' && !['info', 'success', 'warning', 'danger', 'error'].includes(messageOrType)) {
          title = titleOrMessage;
          message = messageOrType;
        } else if (['info', 'success', 'warning', 'danger', 'error'].includes(messageOrType)) {
          message = titleOrMessage;
          dialogType = messageOrType;
        } else {
          message = titleOrMessage;
        }

        const schoolName = localStorage.getItem('school_name') || 'School Management System';
        let icon = 'ℹ️';
        let badgeClass = '';
        if (dialogType === 'success' || message.includes('✅') || message.includes('success') || message.includes('Success')) {
          icon = '✅';
          badgeClass = 'type-success';
        } else if (dialogType === 'warning' || message.includes('⚠️') || message.includes('Warning') || message.includes('Curfew')) {
          icon = '⚠️';
          badgeClass = 'type-warning';
        } else if (dialogType === 'danger' || dialogType === 'error' || message.includes('🔴') || message.includes('Failed') || message.includes('Denied') || message.includes('Error')) {
          icon = '🚫';
          badgeClass = 'type-danger';
        }

        document.querySelectorAll('.enterprise-modal-backdrop').forEach(el => el.remove());

        const backdrop = document.createElement('div');
        backdrop.className = 'enterprise-modal-backdrop';

        backdrop.innerHTML = `
          <div class="enterprise-modal-card" role="dialog" aria-modal="true">
            <div class="enterprise-modal-header">
              <div class="enterprise-modal-icon-badge ${badgeClass}">
                ${icon}
              </div>
              <div>
                <h3 class="enterprise-modal-title">${escapeHtml(title)}</h3>
                <div style="font-size:0.75rem; opacity:0.65;">${escapeHtml(schoolName)}</div>
              </div>
            </div>
            <div class="enterprise-modal-body">${escapeHtml(message)}</div>
            <div class="enterprise-modal-actions">
              <button class="enterprise-modal-btn btn-primary" id="btnEntModalConfirm">
                <span>OK</span>
              </button>
            </div>
          </div>
        `;

        function cleanup() {
          window.removeEventListener('keydown', handleKey);
          backdrop.style.opacity = '0';
          setTimeout(() => backdrop.remove(), 180);
          resolve();
        }

        function handleKey(e) {
          if (e.key === 'Enter' || e.key === 'Escape') {
            e.preventDefault();
            cleanup();
          }
        }

        backdrop.querySelector('#btnEntModalConfirm').addEventListener('click', cleanup);
        backdrop.addEventListener('click', (e) => {
          if (e.target === backdrop) cleanup();
        });

        document.body.appendChild(backdrop);
        window.addEventListener('keydown', handleKey);
        setTimeout(() => {
          const btn = backdrop.querySelector('#btnEntModalConfirm');
          if (btn) btn.focus();
        }, 50);
      });
    };

    window.showConfirmDialog = function(titleOrMessage, message, confirmText = 'Confirm', cancelText = 'Cancel', type = 'confirm') {
      return new Promise((resolve) => {
        let title = 'Confirmation Required';
        let bodyText = message || titleOrMessage;
        if (message) {
          title = titleOrMessage;
        }

        const schoolName = localStorage.getItem('school_name') || 'School Management System';
        let icon = '❓';
        let badgeClass = '';
        if (type === 'warning' || bodyText.toLowerCase().includes('delete') || bodyText.toLowerCase().includes('reject')) {
          icon = '⚠️';
          badgeClass = 'type-warning';
        }

        document.querySelectorAll('.enterprise-modal-backdrop').forEach(el => el.remove());

        const backdrop = document.createElement('div');
        backdrop.className = 'enterprise-modal-backdrop';

        backdrop.innerHTML = `
          <div class="enterprise-modal-card" role="dialog" aria-modal="true">
            <div class="enterprise-modal-header">
              <div class="enterprise-modal-icon-badge ${badgeClass}">
                ${icon}
              </div>
              <div>
                <h3 class="enterprise-modal-title">${escapeHtml(title)}</h3>
                <div style="font-size:0.75rem; opacity:0.65;">${escapeHtml(schoolName)}</div>
              </div>
            </div>
            <div class="enterprise-modal-body">${escapeHtml(bodyText)}</div>
            <div class="enterprise-modal-actions">
              <button class="enterprise-modal-btn btn-secondary" id="btnEntModalCancel">
                <span>${escapeHtml(cancelText)}</span>
              </button>
              <button class="enterprise-modal-btn btn-primary" id="btnEntModalConfirm">
                <span>${escapeHtml(confirmText)}</span>
              </button>
            </div>
          </div>
        `;

        function closeWith(val) {
          window.removeEventListener('keydown', handleKey);
          backdrop.style.opacity = '0';
          setTimeout(() => backdrop.remove(), 180);
          resolve(val);
        }

        function handleKey(e) {
          if (e.key === 'Enter') {
            e.preventDefault();
            closeWith(true);
          } else if (e.key === 'Escape') {
            e.preventDefault();
            closeWith(false);
          }
        }

        backdrop.querySelector('#btnEntModalConfirm').addEventListener('click', () => closeWith(true));
        backdrop.querySelector('#btnEntModalCancel').addEventListener('click', () => closeWith(false));
        backdrop.addEventListener('click', (e) => {
          if (e.target === backdrop) closeWith(false);
        });

        document.body.appendChild(backdrop);
        window.addEventListener('keydown', handleKey);
        setTimeout(() => {
          const btn = backdrop.querySelector('#btnEntModalConfirm');
          if (btn) btn.focus();
        }, 50);
      });
    };

    window.showPromptDialog = function(title, message, defaultValue = '', placeholder = '') {
      return new Promise((resolve) => {
        const schoolName = localStorage.getItem('school_name') || 'School Management System';
        document.querySelectorAll('.enterprise-modal-backdrop').forEach(el => el.remove());

        const backdrop = document.createElement('div');
        backdrop.className = 'enterprise-modal-backdrop';

        backdrop.innerHTML = `
          <div class="enterprise-modal-card" role="dialog" aria-modal="true">
            <div class="enterprise-modal-header">
              <div class="enterprise-modal-icon-badge">
                ✏️
              </div>
              <div>
                <h3 class="enterprise-modal-title">${escapeHtml(title)}</h3>
                <div style="font-size:0.75rem; opacity:0.65;">${escapeHtml(schoolName)}</div>
              </div>
            </div>
            <div class="enterprise-modal-body">
              <div>${escapeHtml(message)}</div>
              <input type="text" class="enterprise-modal-input" id="entPromptInput" value="${escapeHtml(defaultValue)}" placeholder="${escapeHtml(placeholder)}" />
            </div>
            <div class="enterprise-modal-actions">
              <button class="enterprise-modal-btn btn-secondary" id="btnEntPromptCancel">Cancel</button>
              <button class="enterprise-modal-btn btn-primary" id="btnEntPromptSubmit">Submit</button>
            </div>
          </div>
        `;

        function closeWith(val) {
          window.removeEventListener('keydown', handleKey);
          backdrop.style.opacity = '0';
          setTimeout(() => backdrop.remove(), 180);
          resolve(val);
        }

        const input = backdrop.querySelector('#entPromptInput');

        function handleKey(e) {
          if (e.key === 'Enter') {
            e.preventDefault();
            closeWith(input.value);
          } else if (e.key === 'Escape') {
            e.preventDefault();
            closeWith(null);
          }
        }

        backdrop.querySelector('#btnEntPromptSubmit').addEventListener('click', () => closeWith(input.value));
        backdrop.querySelector('#btnEntPromptCancel').addEventListener('click', () => closeWith(null));
        backdrop.addEventListener('click', (e) => {
          if (e.target === backdrop) closeWith(null);
        });

        document.body.appendChild(backdrop);
        window.addEventListener('keydown', handleKey);
        setTimeout(() => {
          input.focus();
          input.select();
        }, 60);
      });
    };

    // ── Global Interceptors for legacy window.alert, confirm, prompt ──
    window.alert = function(msg) {
      return window.showAlertDialog(msg);
    };
    window.confirm = function(msg) {
      return window.showConfirmDialog('Confirmation', msg);
    };
    window.prompt = function(msg, def) {
      return window.showPromptDialog('Input Required', msg, def || '');
    };
  }

  ensureEnterpriseDialogs();

  // Auto-run guard immediately when script is loaded
  guard();

})();
