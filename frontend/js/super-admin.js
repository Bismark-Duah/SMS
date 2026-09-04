const API_BASE = window.API_BASE || (window.location.origin.includes('http') ? (window.location.origin + '/api') : 'http://127.0.0.1:8000/api');

function getHeaders(headers = {}) {
  if (window.getAuthHeaders) return window.getAuthHeaders(headers);
  const h = { ...headers };
  const t = sessionStorage.getItem('accessToken') || localStorage.getItem('accessToken');
  if (t) h['Authorization'] = `Bearer ${t}`;
  return h;
}

function escapeHtml(text) {
  if (text === null || text === undefined) return '';
  const div = document.createElement('div');
  div.textContent = String(text);
  return div.innerHTML;
}
window.escapeHtml = escapeHtml;

window.escapeJsQuotes = function(str) {
  if (!str) return '';
  return String(str).replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/"/g, '&quot;');
};

// ── Enterprise 4-Tab Navigation Controller ─────────────────────────────────
window.switchSuperAdminTab = function(tabName) {
  const tabPanes = document.querySelectorAll('.sa-tab-pane');
  const tabBtns = document.querySelectorAll('.sa-tab-btn');

  tabPanes.forEach(pane => pane.classList.remove('active'));
  tabBtns.forEach(btn => btn.classList.remove('active'));

  const targetPane = document.getElementById(`tab-${tabName}`);
  if (targetPane) targetPane.classList.add('active');

  const activeBtn = Array.from(tabBtns).find(b => b.getAttribute('onclick')?.includes(tabName));
  if (activeBtn) activeBtn.classList.add('active');

  try {
    localStorage.setItem('superadmin_active_tab', tabName);
    if (window.history && window.history.replaceState) {
      window.history.replaceState(null, '', `#${tabName}`);
    }
  } catch (_) {}

  if (tabName === 'operations' && window.loadSMSGatewayStatus) {
    window.loadSMSGatewayStatus();
  }
  if (tabName === 'security' && window.loadMasterAuditStream) {
    window.loadMasterAuditStream();
  }
};

// Initialize active tab from hash or localStorage
document.addEventListener('DOMContentLoaded', () => {
  const hashTab = (window.location.hash || '').replace('#', '');
  const storedTab = localStorage.getItem('superadmin_active_tab');
  const validTabs = ['overview', 'schools', 'security', 'operations'];
  const activeTab = validTabs.includes(hashTab) ? hashTab : (validTabs.includes(storedTab) ? storedTab : 'overview');
  window.switchSuperAdminTab(activeTab);
});

window.logoutSuperAdmin = function() {
  const keysToPurge = [
    'accessToken', 'token', 'user', 'userRole', 'activeRole', 'username', 'userId',
    'logo_theme_colors', 'school_logo', 'system_theme', 'school_name',
    'school_abbreviation', 'school_mode', 'school_id', 'is_super_admin',
    'is_super_admin_viewing', 'is_impersonating', 'boarding_status',
    'boarding_hierarchy_mode', 'user_roles', '_lastActivity'
  ];
  keysToPurge.forEach(k => {
    localStorage.removeItem(k);
    sessionStorage.removeItem(k);
  });
  sessionStorage.clear();
  window.location.href = 'auth.html?msg=Logged+out+successfully';
};

const modal = document.getElementById('newSchoolModal');
const form = document.getElementById('newSchoolForm');

window.openNewSchoolModal = function() {
  if (form) form.reset();
  const uInput = document.getElementById('adminUsername');
  if (uInput && !uInput.dataset.userTyped) uInput.value = '';
  const pInput = document.getElementById('adminPassword');
  if (pInput && !pInput.dataset.userTyped) pInput.value = '';
  if (modal) modal.style.display = 'flex';
};

window.closeNewSchoolModal = function() {
  if (modal) modal.style.display = 'none';
  if (form) form.reset();
};

function resetSuperAdminAutofills() {
  try {
    const sSearch = document.getElementById('schoolSearchInput');
    if (sSearch && !sSearch.dataset.userTyped) sSearch.value = '';
    if (form) form.reset();
  } catch (_) {}
}
resetSuperAdminAutofills();
setTimeout(resetSuperAdminAutofills, 100);
setTimeout(resetSuperAdminAutofills, 500);

window.toggleRegisterPasswordVisibility = function() {
  const input = document.getElementById('adminPassword');
  const btn = document.getElementById('toggleAdminPassBtn');
  if (!input) return;
  if (input.type === 'password') {
    input.type = 'text';
    if (btn) btn.textContent = '🙈';
  } else {
    input.type = 'password';
    if (btn) btn.textContent = '👁️';
  }
};

window.allRegisteredSchools = [];

window.loadSuperAdminDashboard = async function() {
  const token = sessionStorage.getItem('accessToken') || localStorage.getItem('accessToken');
  if (!token) {
    window.location.href = 'auth.html';
    return;
  }

  const tbody = document.getElementById('schoolsTableBody');

  try {
    const res = await fetch(`${API_BASE}/super-admin/dashboard`, { headers: getHeaders() });
    if (!res.ok) {
      if (res.status === 401) {
        if (tbody) tbody.innerHTML = '<tr><td colspan="6" style="padding:24px; text-align:center; color:#f87171;">⚠️ Session expired. <a href="auth.html" style="color:#60a5fa; text-decoration:underline; font-weight:700;">Click here to log in again</a></td></tr>';
        setTimeout(() => { window.location.href = 'auth.html?msg=Session+expired'; }, 1500);
        return;
      }
      if (res.status === 403) {
        alert('Super-Admin privileges required.');
        window.location.href = 'dashboard.html';
        return;
      }
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `Server returned HTTP ${res.status}`);
    }

    const data = await res.json();
    window.allRegisteredSchools = data.schools || [];

    // Populate KPIs
    if (document.getElementById('kpiTotalSchools')) document.getElementById('kpiTotalSchools').textContent = data.total_schools || 0;
    if (document.getElementById('tabBadgeSchoolCount')) document.getElementById('tabBadgeSchoolCount').textContent = data.total_schools || 0;
    const activeBadge = document.getElementById('kpiActiveSchoolsBadge');
    if (activeBadge) activeBadge.textContent = `${data.active_schools || 0} Active / ${data.total_schools || 0} Total`;

    if (document.getElementById('kpiTotalStudents')) document.getElementById('kpiTotalStudents').textContent = (data.total_students || 0).toLocaleString();
    const demoSplit = document.getElementById('kpiStudentsDemographics');
    if (demoSplit) {
      demoSplit.textContent = `Boys: ${data.total_boys || 0} | Girls: ${data.total_girls || 0} | Brdg: ${data.total_boarding || 0}`;
    }

    if (document.getElementById('kpiTotalUsers')) document.getElementById('kpiTotalUsers').textContent = (data.total_users || 0).toLocaleString();
    if (document.getElementById('kpiTotalFees')) document.getElementById('kpiTotalFees').textContent = `GH₵ ${data.total_fees_collected ? data.total_fees_collected.toLocaleString('en-US', { minimumFractionDigits: 2 }) : '0.00'}`;
    
    const recRate = document.getElementById('kpiFeeRecoveryRate');
    if (recRate) {
      recRate.textContent = `Recovery: ${data.overall_collection_rate || 0}% of GH₵ ${(data.total_fees_billed || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
    }

    const diag = data.diagnostics || {};
    if (document.getElementById('kpiDbSize')) document.getElementById('kpiDbSize').textContent = `${diag.db_size_mb || 0} MB`;
    if (document.getElementById('kpiBackupStatus')) document.getElementById('kpiBackupStatus').textContent = `Backups: ${diag.backups_count || 0} | Last: ${diag.last_backup_time || 'None'}`;

    // Render Comparative Visual Analytics
    window.renderComparativeAnalytics(data);

    // Render Schools Directory Table
    window.filterSchoolsDirectory();

    // Load Multi-Tenant Real-Time Sync Telemetry Monitor
    window.loadSuperAdminSyncMonitor();

    // Load Real-Time Master Audit Feed
    window.loadMasterAuditStream();

  } catch (error) {
    console.error('Super-Admin dashboard error, attempting fallback to /schools:', error);
    try {
      const fallbackRes = await fetch(`${API_BASE}/super-admin/schools`, { headers: getHeaders() });
      if (fallbackRes.ok) {
        const schoolsData = await fallbackRes.json();
        window.allRegisteredSchools = schoolsData || [];
        if (document.getElementById('kpiTotalSchools')) {
          document.getElementById('kpiTotalSchools').textContent = window.allRegisteredSchools.length;
        }
        window.filterSchoolsDirectory();
        window.loadSuperAdminSyncMonitor();
        window.loadMasterAuditStream();
        return;
      }
    } catch (fallbackErr) {
      console.error('Fallback /schools failed:', fallbackErr);
    }

    if (tbody) {
      tbody.innerHTML = `
        <tr>
          <td colspan="6" style="padding:28px; text-align:center; background:rgba(239, 68, 68, 0.08); border-radius:8px;">
            <div style="font-size:1.1rem; color:#f87171; font-weight:700; margin-bottom:8px;">⚠️ Could not load registered schools</div>
            <p style="margin:0 0 12px; font-size:0.85rem; opacity:0.8;">${error.message}</p>
            <button class="btn primary" onclick="window.loadSuperAdminDashboard()" style="padding:6px 14px; font-size:0.82rem;">🔄 Retry Connection</button>
          </td>
        </tr>
      `;
    }
  }
};

window.renderComparativeAnalytics = function(data) {
  const compEnrolment = document.getElementById('comparativeEnrolmentContainer');
  const compFees = document.getElementById('comparativeFeesContainer');
  const networkDemo = document.getElementById('networkDemographicsContainer');
  const enrolHeader = document.getElementById('enrolmentTotalHeader');
  const feeHeader = document.getElementById('feesCollectedHeader');

  const analytics = data.comparative_analytics || [];
  const totalStudents = data.total_students || 0;
  const totalFeesCollected = data.total_fees_collected || 0;

  if (enrolHeader) enrolHeader.textContent = `Network Total: ${totalStudents.toLocaleString()} Students`;
  if (feeHeader) feeHeader.textContent = `GH₵ ${totalFeesCollected.toLocaleString('en-US', { minimumFractionDigits: 2 })}`;

  // 1. Enrollment Comparison Bars
  if (compEnrolment) {
    if (analytics.length === 0) {
      compEnrolment.innerHTML = '<p style="opacity:0.6; font-size:0.85rem; text-align:center; padding:16px;">No school enrollment records available.</p>';
    } else {
      const maxStudents = Math.max(...analytics.map(a => a.students), 1);
      compEnrolment.innerHTML = analytics.map(s => {
        const pct = Math.round((s.students / maxStudents) * 100);
        const sharePct = totalStudents > 0 ? Math.round((s.students / totalStudents) * 100) : 0;
        return `
          <div style="display:flex; flex-direction:column; gap:4px;">
            <div style="display:flex; justify-content:space-between; align-items:center; font-size:0.83rem;">
              <span style="font-weight:600; color:#fff;">${s.name} <code style="font-size:0.72rem; opacity:0.7;">(${s.code})</code></span>
              <div style="display:flex; gap:8px; align-items:center;">
                <span style="font-size:0.74rem; color:#94a3b8;">👦 ${s.boys} | 👧 ${s.girls}</span>
                <strong style="color:#10b981;">${s.students} (${sharePct}%)</strong>
              </div>
            </div>
            <div style="width:100%; background:rgba(255,255,255,0.06); height:7px; border-radius:4px; overflow:hidden;">
              <div style="width:${pct}%; background:linear-gradient(90deg, #10b981, #059669); height:100%; border-radius:4px; transition:width 0.4s ease;"></div>
            </div>
          </div>
        `;
      }).join('');
    }
  }

  // 2. Fee Recovery Comparison Bars
  if (compFees) {
    if (analytics.length === 0) {
      compFees.innerHTML = '<p style="opacity:0.6; font-size:0.85rem; text-align:center; padding:16px;">No financial records found.</p>';
    } else {
      compFees.innerHTML = analytics.map(s => {
        const rate = s.rate || 0;
        let barColor = '#10b981'; // green
        if (rate < 50) barColor = '#ef4444'; // red
        else if (rate < 80) barColor = '#f59e0b'; // amber

        return `
          <div style="display:flex; flex-direction:column; gap:4px;">
            <div style="display:flex; justify-content:space-between; align-items:center; font-size:0.83rem;">
              <span style="font-weight:600; color:#fff;">${s.name}</span>
              <div style="display:flex; gap:8px; align-items:center;">
                <span style="font-size:0.74rem; color:#94a3b8;">Billed: GH₵ ${s.billed.toLocaleString('en-US', { minimumFractionDigits: 0 })}</span>
                <strong style="color:${barColor};">${rate}%</strong>
              </div>
            </div>
            <div style="width:100%; background:rgba(255,255,255,0.06); height:7px; border-radius:4px; overflow:hidden;">
              <div style="width:${Math.min(100, rate)}%; background:${barColor}; height:100%; border-radius:4px; transition:width 0.4s ease;"></div>
            </div>
          </div>
        `;
      }).join('');
    }
  }

  // 3. Network Demographics & Profiles
  if (networkDemo) {
    const totalBoys = data.total_boys || 0;
    const totalGirls = data.total_girls || 0;
    const boysPct = totalStudents > 0 ? Math.round((totalBoys / totalStudents) * 100) : 50;
    const girlsPct = 100 - boysPct;

    const totalBoarding = data.total_boarding || 0;
    const totalDay = data.total_day || 0;
    const brdPct = totalStudents > 0 ? Math.round((totalBoarding / totalStudents) * 100) : 0;
    const dayPct = 100 - brdPct;

    const modes = data.mode_distribution || {};

    networkDemo.innerHTML = `
      <!-- Gender Split -->
      <div>
        <div style="display:flex; justify-content:space-between; font-size:0.82rem; margin-bottom:4px;">
          <span style="color:#38bdf8;">👦 Boys: ${totalBoys} (${boysPct}%)</span>
          <span style="color:#f472b6;">👧 Girls: ${totalGirls} (${girlsPct}%)</span>
        </div>
        <div style="display:flex; width:100%; height:8px; border-radius:4px; overflow:hidden; background:rgba(255,255,255,0.08);">
          <div style="width:${boysPct}%; background:#0284c7;"></div>
          <div style="width:${girlsPct}%; background:#db2777;"></div>
        </div>
      </div>

      <!-- Boarding vs Day Split -->
      <div>
        <div style="display:flex; justify-content:space-between; font-size:0.82rem; margin-bottom:4px;">
          <span style="color:#0891b2;">🏠 Boarding: ${totalBoarding} (${brdPct}%)</span>
          <span style="color:#d97706;">🎒 Day: ${totalDay} (${dayPct}%)</span>
        </div>
        <div style="display:flex; width:100%; height:8px; border-radius:4px; overflow:hidden; background:rgba(255,255,255,0.08);">
          <div style="width:${brdPct}%; background:#0891b2;"></div>
          <div style="width:${dayPct}%; background:#d97706;"></div>
        </div>
      </div>

      <!-- Mode Badges -->
      <div style="display:flex; flex-wrap:wrap; gap:6px; padding-top:4px;">
        <span class="badge-mode badge-shs" style="font-size:0.75rem;">🏛️ SHS Only: ${modes.SHS_ONLY || 0}</span>
        <span class="badge-mode badge-basic" style="font-size:0.75rem;">🎯 Basic Only: ${modes.BASIC_ONLY || 0}</span>
        <span class="badge-mode badge-combined" style="font-size:0.75rem;">🌐 Combined: ${modes.COMBINED || 0}</span>
      </div>
    `;
  }
};

window.filterSchoolsDirectory = function() {
  const search = (document.getElementById('schoolSearchInput')?.value || '').toLowerCase().trim();
  const modeFilter = document.getElementById('schoolModeFilter')?.value || 'ALL';
  const boardingFilter = document.getElementById('schoolBoardingFilter')?.value || 'ALL';

  let filtered = [...(window.allRegisteredSchools || [])];

  if (search) {
    filtered = filtered.filter(s =>
      (s.name || '').toLowerCase().includes(search) ||
      (s.code || '').toLowerCase().includes(search) ||
      (s.address || '').toLowerCase().includes(search)
    );
  }

  if (modeFilter !== 'ALL') {
    filtered = filtered.filter(s => s.school_mode === modeFilter);
  }

  if (boardingFilter !== 'ALL') {
    filtered = filtered.filter(s => (s.boarding_type || 'BOARDING_AND_DAY') === boardingFilter);
  }

  const subtitle = document.getElementById('directorySummarySubtitle');
  if (subtitle) {
    subtitle.textContent = `Showing ${filtered.length} of ${window.allRegisteredSchools.length} registered institutions.`;
  }

  window.renderSchoolsDirectory(filtered);
};

window.renderSchoolsDirectory = function(schoolsList) {
  const tbody = document.getElementById('schoolsTableBody');
  if (!tbody) return;

  if (!schoolsList || schoolsList.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" style="padding:24px; text-align:center; opacity:0.7;">No matching schools found for the active filter.</td></tr>';
    return;
  }

  const sortedSchools = [...schoolsList].sort((a, b) => a.id - b.id);
  tbody.innerHTML = sortedSchools.map(s => {
    const statusClass = s.status === 'ACTIVE' ? 'status-active' : 'status-suspended';
    const boardingVal = s.boarding_type || 'BOARDING_AND_DAY';

    // Profile & Stage Badge
    let stageBadge = '';
    if (s.school_mode === 'BASIC_ONLY') {
      stageBadge = `<span class="badge-mode badge-basic" title="Basic School (KG - JHS)">🎯 Basic School</span>`;
    } else if (s.school_mode === 'SHS_ONLY') {
      stageBadge = `<span class="badge-mode badge-shs" title="Senior High School (SHS 1 - 3)">🏛️ Senior High</span>`;
    } else {
      stageBadge = `<span class="badge-mode badge-combined" title="Combined (Basic + SHS)">🌐 Combined</span>`;
    }

    let boardingLabel = boardingVal === 'BOARDING_AND_DAY' ? 'Boarding & Day' : (boardingVal === 'BOARDING_ONLY' ? 'Boarding Only' : 'Day Only');

    return `
      <tr style="border-bottom: 1px solid var(--sa-card-border); transition: background 0.15s;">
        <!-- 1. School Identity -->
        <td style="padding:12px 14px;">
          <div style="font-weight:700; font-size:0.92rem; color:#fff; display:flex; align-items:center; gap:8px;">
            <span>🏫</span>
            <span style="white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:320px;" title="${s.name}">${s.name}</span>
          </div>
          <div style="display:flex; align-items:center; gap:8px; font-size:0.75rem; color:var(--sa-text-muted); margin-top:3px;">
            <code style="background:rgba(255,255,255,0.06); padding:1px 6px; border-radius:4px; font-weight:700; color:#cbd5e1;">${s.code}</code>
            <span>•</span>
            <span>ID: #${s.id}</span>
            ${s.subdomain ? `<span>•</span> <span style="color:#38bdf8;">${s.subdomain}.domain</span>` : ''}
          </div>
        </td>

        <!-- 2. Stage & Mode -->
        <td style="padding:12px 14px;">
          <div style="display:flex; flex-direction:column; gap:3px;">
            <div>${stageBadge}</div>
            <div style="font-size:0.75rem; color:var(--sa-text-muted);">${boardingLabel}</div>
          </div>
        </td>

        <!-- 3. Enrollment -->
        <td style="padding:12px 14px; text-align:center;">
          <div style="font-size:0.92rem; font-weight:700; color:#fff;">${(s.student_count || 0).toLocaleString()} <span style="font-size:0.72rem; font-weight:500; opacity:0.7;">Students</span></div>
          <div style="font-size:0.72rem; color:var(--sa-text-muted); margin-top:2px;">Enrolled Capacity</div>
        </td>

        <!-- 4. Staff & Users -->
        <td style="padding:12px 14px; text-align:center;">
          <div style="font-size:0.88rem; font-weight:600; color:#cbd5e1;">${s.user_count || 0} Staff</div>
          <div style="font-size:0.72rem; color:var(--sa-text-muted); margin-top:2px;">Accounts</div>
        </td>

        <!-- 5. Status Pill -->
        <td style="padding:12px 14px; text-align:center; white-space:nowrap;">
          <span class="${statusClass}">● ${s.status}</span>
        </td>

        <!-- 6. Actions -->
        <td style="padding:12px 14px; text-align:right; white-space:nowrap;">
          <div style="display:inline-flex; gap:6px; align-items:center; justify-content:flex-end;">
            <button class="btn-manage" onclick="window.openEditSchoolModal(${s.id})" title="Configure School Governance & Profile">
              ⚙️ Manage School
            </button>
            <button class="btn-enter" onclick="window.enterSchoolView(${s.id}, '${window.escapeJsQuotes(s.name)}', '${s.school_mode}', '${window.escapeJsQuotes(s.code || '')}')" title="Enter live school view">
              👁️ Enter View
            </button>
          </div>
        </td>
      </tr>
    `;
  }).join('');
};

let currentAuditPage = 1;
let totalAuditPages = 1;

window.loadMasterAuditStream = async function(page = 1) {
  const container = document.getElementById('masterAuditStreamContainer');
  if (!container) return;

  currentAuditPage = page;
  const actionFilter = document.getElementById('auditActionFilter')?.value || '';

  try {
    let url = `${API_BASE}/super-admin/audit-stream?page=${currentAuditPage}&limit=15`;
    if (actionFilter) url += `&action=${encodeURIComponent(actionFilter)}`;

    const res = await fetch(url, { headers: getHeaders() });
    if (!res.ok) {
      container.innerHTML = `<p style="color:#f87171; text-align:center; padding:18px;">Could not load audit stream (HTTP ${res.status}).</p>`;
      return;
    }

    const data = await res.json();
    const logs = Array.isArray(data) ? data : (Array.isArray(data.logs) ? data.logs : []);
    const totalCount = data.total !== undefined ? data.total : logs.length;
    totalAuditPages = data.total_pages !== undefined ? data.total_pages : 1;

    if (!logs || logs.length === 0) {
      container.innerHTML = `
        <div style="text-align:center; padding:30px; color:var(--sa-text-muted);">
          <div style="font-size:2rem; margin-bottom:8px;">🛡️</div>
          <p style="margin:0; font-size:0.9rem;">No security or operational events found matching the filter.</p>
        </div>
      `;
      window.renderAuditPagination(0, 1, 1);
      return;
    }

    container.innerHTML = logs.map(l => {
      // Resolve action badge color
      let actionBg = 'rgba(99, 102, 241, 0.15)';
      let actionColor = '#a5b4fc';
      let actionBorder = 'rgba(99, 102, 241, 0.3)';

      const act = (l.action || '').toUpperCase();
      if (act.includes('LOGIN')) {
        actionBg = 'rgba(16, 185, 129, 0.15)'; actionColor = '#34d399'; actionBorder = 'rgba(16, 185, 129, 0.3)';
      } else if (act.includes('PAYMENT') || act.includes('FEE')) {
        actionBg = 'rgba(6, 182, 212, 0.15)'; actionColor = '#38bdf8'; actionBorder = 'rgba(6, 182, 212, 0.3)';
      } else if (act.includes('SCORE') || act.includes('RESULT')) {
        actionBg = 'rgba(168, 85, 247, 0.15)'; actionColor = '#c084fc'; actionBorder = 'rgba(168, 85, 247, 0.3)';
      } else if (act.includes('PURGE') || act.includes('DELETE') || act.includes('SUSPEND')) {
        actionBg = 'rgba(239, 68, 68, 0.15)'; actionColor = '#f87171'; actionBorder = 'rgba(239, 68, 68, 0.3)';
      } else if (l.is_super_admin_action) {
        actionBg = 'rgba(245, 158, 11, 0.15)'; actionColor = '#fbbf24'; actionBorder = 'rgba(245, 158, 11, 0.3)';
      }

      // Device icon
      let deviceIcon = '💻';
      if (l.device_category === 'Mobile') deviceIcon = '📱';
      else if (l.device_category === 'Tablet') deviceIcon = '📱';
      else if (l.device_category === 'Bot') deviceIcon = '🤖';

      // Explicit Ghana GMT Timezone Formatting
      const timeVal = l.created_at || l.timestamp;
      let timeFormatted = 'Recent';
      try {
        if (timeVal) {
          timeFormatted = new Intl.DateTimeFormat('en-GB', {
            timeZone: 'Africa/Accra',
            day: '2-digit', month: 'short', year: 'numeric',
            hour: '2-digit', minute: '2-digit', second: '2-digit',
            hour12: true
          }).format(new Date(timeVal));
        }
      } catch (_) {
        timeFormatted = timeVal || 'Recent';
      }

      const schoolBadge = l.school_code ? `[ 🏫 ${escapeHtml(l.school_code)} ]` : `[ 🌐 PLATFORM ]`;
      const actorName = l.actor_username || l.user_name || 'System Operator';
      const actorRole = l.actor_role || l.user_role || 'user';

      return `
        <div class="audit-card" style="display:flex; flex-direction:column; gap:8px;">
          <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
            <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
              <span class="audit-badge" style="background:${actionBg}; color:${actionColor}; border:1px solid ${actionBorder};">
                ${escapeHtml(l.action)}
              </span>
              <strong style="color:#f8fafc; font-size:0.85rem;">${escapeHtml(actorName)}</strong>
              <span style="font-size:0.75rem; color:var(--sa-text-muted); background:rgba(255,255,255,0.05); padding:1px 6px; border-radius:4px;">
                ${escapeHtml(actorRole)}
              </span>
              <span style="font-size:0.75rem; color:#818cf8; font-weight:600;">
                ${schoolBadge}
              </span>
            </div>
            <div style="font-size:0.75rem; color:var(--sa-text-muted); font-family:monospace;">
              🕒 ${timeFormatted}
            </div>
          </div>

          <div style="font-size:0.82rem; color:#cbd5e1; line-height:1.4;">
            ${escapeHtml(l.details || l.action)}
          </div>

          <!-- Forensic Telemetry Badges -->
          <div style="display:flex; flex-wrap:wrap; gap:6px; font-size:0.73rem; align-items:center; padding-top:4px; border-top:1px solid rgba(255,255,255,0.04);">
            <span style="background:#090d16; color:#e2e8f0; padding:2px 8px; border-radius:4px; border:1px solid #334155; display:inline-flex; align-items:center; gap:4px;">
              ${deviceIcon} <b>${escapeHtml(l.device_brand || 'Personal Computer')}</b> • ${escapeHtml(l.browser_name || 'Web Browser')}
            </span>
            <span style="background:#090d16; color:#94a3b8; padding:2px 6px; border-radius:4px; border:1px solid #1e293b;">
              ${escapeHtml(l.os_name || 'Operating System')}
            </span>
            <span style="background:#090d16; color:#38bdf8; padding:2px 6px; border-radius:4px; border:1px solid rgba(14,165,233,0.3); font-family:monospace;">
              📍 ${escapeHtml(l.ip_address || '127.0.0.1')}
            </span>
          </div>
        </div>
      `;
    }).join('');

    window.renderAuditPagination(totalCount, currentAuditPage, totalAuditPages);

  } catch (err) {
    container.innerHTML = `<p style="color:#f87171; text-align:center; padding:18px;">Error loading audit feed: ${err.message}</p>`;
  }
};

window.renderAuditPagination = function(total, currentPage, totalPages) {
  const infoEl = document.getElementById('auditPaginationInfo');
  const btnsEl = document.getElementById('auditPaginationBtns');
  if (!infoEl || !btnsEl) return;

  if (total === 0) {
    infoEl.textContent = 'No records';
    btnsEl.innerHTML = '';
    return;
  }

  infoEl.innerHTML = `Showing Page <strong>${currentPage}</strong> of <strong>${totalPages}</strong> (${total} total events)`;

  let btnsHtml = `
    <button class="btn" style="padding:5px 10px; font-size:0.78rem; opacity:${currentPage <= 1 ? '0.4' : '1'}; cursor:${currentPage <= 1 ? 'not-allowed' : 'pointer'};"
            onclick="window.loadMasterAuditStream(${currentPage - 1})" ${currentPage <= 1 ? 'disabled' : ''}>
      &laquo; Previous
    </button>
  `;

  // Numeric page buttons
  const startP = Math.max(1, currentPage - 2);
  const endP = Math.min(totalPages, currentPage + 2);
  for (let p = startP; p <= endP; p++) {
    const isActive = p === currentPage;
    btnsHtml += `
      <button class="btn" style="padding:5px 10px; font-size:0.78rem; ${isActive ? 'background:#6366f1; color:#fff; font-weight:700;' : 'background:#090d16; color:#94a3b8;'}"
              onclick="window.loadMasterAuditStream(${p})">
        ${p}
      </button>
    `;
  }

  btnsHtml += `
    <button class="btn" style="padding:5px 10px; font-size:0.78rem; opacity:${currentPage >= totalPages ? '0.4' : '1'}; cursor:${currentPage >= totalPages ? 'not-allowed' : 'pointer'};"
            onclick="window.loadMasterAuditStream(${currentPage + 1})" ${currentPage >= totalPages ? 'disabled' : ''}>
      Next &raquo;
    </button>
  `;

  btnsEl.innerHTML = btnsHtml;
};

window.openPurgeAuditModal = function() {
  const modal = document.getElementById('purgeAuditModal');
  const btn = document.getElementById('btnConfirmPurgeAudit');
  if (btn) {
    btn.disabled = false;
    btn.innerHTML = '🗑️ Yes, Purge Audit Trail';
  }
  if (modal) modal.style.display = 'flex';
};

window.closePurgeAuditModal = function() {
  const modal = document.getElementById('purgeAuditModal');
  if (modal) modal.style.display = 'none';
};

window.executePurgeAuditStream = async function() {
  const btn = document.getElementById('btnConfirmPurgeAudit');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '⏳ Purging Audit Records...';
  }

  try {
    const res = await fetch(`${API_BASE}/super-admin/audit-stream/purge`, {
      method: 'DELETE',
      headers: getHeaders()
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Failed to clear audit trail');

    window.closePurgeAuditModal();
    if (window.showToast) {
      window.showToast(data.message || 'Audit trail successfully cleared.', 'success');
    } else {
      alert(`✔ ${data.message || 'Audit trail successfully cleared.'}`);
    }
    window.loadMasterAuditStream(1);
  } catch (err) {
    alert(`❌ Purge Failed: ${err.message}`);
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '🗑️ Yes, Purge Audit Trail';
    }
  }
};

// ── Curriculum Accreditation & Subject Activation Handlers ───────────────

let currentAccreditationData = null;

window.openAccreditationModal = async function(schoolId, schoolName, schoolMode) {
  const modal = document.getElementById('accreditationModal');
  const title = document.getElementById('accreditationModalTitle');
  const subtitle = document.getElementById('accreditationModalSubtitle');
  const idInput = document.getElementById('accreditationSchoolId');
  const container = document.getElementById('accreditationCatalogContainer');

  if (idInput) idInput.value = String(schoolId);
  if (title) title.innerHTML = `<span>⚙️</span> Curriculum Accreditation — ${schoolName}`;
  if (subtitle) subtitle.textContent = `Mode: ${schoolMode} | Select accredited learning areas and active subjects for this institution.`;
  if (container) container.innerHTML = '<p style="opacity:0.7; text-align:center; padding:20px;">Loading national subject catalog...</p>';

  if (modal) modal.style.display = 'flex';

  try {
    const res = await fetch(`${API_BASE}/super-admin/schools/${schoolId}/accreditation`, { headers: getHeaders() });
    if (!res.ok) throw new Error('Failed to load school accreditation data');
    const data = await res.json();
    currentAccreditationData = data;
    window.renderAccreditationPresets(data.presets);
    window.renderAccreditationCatalog(data);
  } catch (err) {
    if (container) container.innerHTML = `<p style="color:#ef4444; padding:20px;">❌ ${err.message}</p>`;
  }
};

window.closeAccreditationModal = function() {
  const modal = document.getElementById('accreditationModal');
  if (modal) modal.style.display = 'none';
};

window.renderAccreditationPresets = function(presets) {
  const container = document.getElementById('accreditationPresetsToolbar');
  if (!container || !presets) return;

  const presetKeys = Object.keys(presets);
  if (presetKeys.length === 0) {
    container.innerHTML = '';
    return;
  }

  container.innerHTML = presetKeys.map(key => {
    const p = presets[key];
    return `
      <button type="button" class="preset-pill-btn" onclick="window.applyAccreditationPreset('${key}')">
        ${p.name}
      </button>
    `;
  }).join('');
};

window.applyAccreditationPreset = function(presetKey) {
  if (!currentAccreditationData || !currentAccreditationData.presets) return;
  const preset = currentAccreditationData.presets[presetKey];
  if (!preset || !Array.isArray(preset.subject_ids)) return;

  const targetIds = new Set(preset.subject_ids);
  const checkboxes = document.querySelectorAll('.accred-sub-chk');
  checkboxes.forEach(cb => {
    const subId = parseInt(cb.value);
    cb.checked = targetIds.has(subId);
  });

  // Update group parent checkboxes
  const grouped = currentAccreditationData.grouped_catalog || {};
  const groupKeys = Object.keys(grouped);
  groupKeys.forEach((_, idx) => {
    const groupCbs = document.querySelectorAll(`.group-sub-${idx}`);
    const groupChecked = Array.from(groupCbs).every(cb => cb.checked);
    const parentCb = document.getElementById(`group_chk_${idx}`);
    if (parentCb) parentCb.checked = groupChecked && groupCbs.length > 0;
  });

  window.updateAccreditationSummaryBadge();

  // Smooth Scroll & Spotlight Pulse to the Matching Group Card
  const presetToGroupMap = {
    'cross_cutting': 'Cross-Cutting',
    'shs_core': 'Core Curriculum',
    'general_science': 'General Science',
    'stem_tech': 'STEM',
    'business': 'Business',
    'general_arts': 'General Arts',
    'visual_arts': 'Visual Arts',
    'home_economics': 'Home Economics',
    'technical': 'Technical',
    'tvet_vocational': 'TVET',
    'agriculture': 'Agricultural',
    'basic_core': 'Basic'
  };

  const targetKeyword = presetToGroupMap[presetKey];
  let targetIdx = -1;
  if (targetKeyword) {
    targetIdx = groupKeys.findIndex(k => k.includes(targetKeyword));
  }

  if (targetIdx >= 0) {
    const targetCard = document.getElementById(`group_card_${targetIdx}`);
    if (targetCard) {
      targetCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
      targetCard.classList.remove('spotlight-active');
      void targetCard.offsetWidth; // Trigger reflow for animation restart
      targetCard.classList.add('spotlight-active');
      setTimeout(() => targetCard.classList.remove('spotlight-active'), 1400);
    }
  } else if (presetKey === 'comprehensive_shs') {
    const container = document.getElementById('accreditationCatalogContainer');
    if (container) container.scrollTo({ top: 0, behavior: 'smooth' });
  }
};

window.renderAccreditationCatalog = function(data) {
  const container = document.getElementById('accreditationCatalogContainer');
  if (!container) return;

  const grouped = data.grouped_catalog || {};
  const groupKeys = Object.keys(grouped);

  if (groupKeys.length === 0) {
    container.innerHTML = '<p style="opacity:0.7; text-align:center;">No subjects found in national catalog.</p>';
    return;
  }

  let html = '';

  groupKeys.forEach((groupName, idx) => {
    const subjects = grouped[groupName] || [];
    const activeCount = subjects.filter(s => s.is_active_for_school).length;
    const allChecked = activeCount === subjects.length && subjects.length > 0;

    html += `
      <div class="catalog-group-card" id="group_card_${idx}">
        <div class="catalog-group-header">
          <label class="catalog-group-title" for="group_chk_${idx}">
            <input type="checkbox" id="group_chk_${idx}" onchange="window.toggleGroupSubjects('${idx}', this.checked)" ${allChecked ? 'checked' : ''} />
            <span>${groupName}</span>
          </label>
          <span class="catalog-group-badge" id="group_badge_${idx}">
            ${activeCount} / ${subjects.length} Active
          </span>
        </div>
        <div class="catalog-grid">
          ${subjects.map(s => {
            const checkedAttr = s.is_active_for_school ? 'checked' : '';
            return `
              <label class="subject-tile-card">
                <input type="checkbox" class="accred-sub-chk group-sub-${idx}" value="${s.id}" ${checkedAttr} onchange="window.updateAccreditationSummaryBadge()" />
                <div class="subject-tile-info">
                  <div class="subject-tile-name">${s.name}</div>
                  <div class="subject-tile-meta">
                    <span class="subject-tile-code">${s.code || 'SUB'}</span>
                    <span>${s.category || (s.is_core ? 'Core' : 'Elective')}</span>
                  </div>
                </div>
              </label>
            `;
          }).join('')}
        </div>
      </div>
    `;
  });

  container.innerHTML = html;
  window.updateAccreditationSummaryBadge();
};

window.toggleGroupSubjects = function(groupIdx, isChecked) {
  const checkboxes = document.querySelectorAll(`.group-sub-${groupIdx}`);
  checkboxes.forEach(cb => cb.checked = isChecked);
  window.updateAccreditationSummaryBadge();
};

window.toggleAllAccreditationSubjects = function(isChecked) {
  const checkboxes = document.querySelectorAll('.accred-sub-chk');
  checkboxes.forEach(cb => cb.checked = isChecked);
  const groupBoxes = document.querySelectorAll('[id^="group_chk_"]');
  groupBoxes.forEach(gb => gb.checked = isChecked);
  window.updateAccreditationSummaryBadge();
};

window.updateAccreditationSummaryBadge = function() {
  const checked = document.querySelectorAll('.accred-sub-chk:checked');
  const all = document.querySelectorAll('.accred-sub-chk');
  const badge = document.getElementById('accreditationSummaryBadge');
  if (badge) {
    badge.textContent = `✔ ${checked.length} of ${all.length} Total Subjects Activated for this School`;
  }
};

window.handleSaveAccreditation = async function() {
  const schoolId = document.getElementById('accreditationSchoolId')?.value;
  const btn = document.getElementById('saveAccreditationBtn');
  if (!schoolId) return;

  const checkedIds = Array.from(document.querySelectorAll('.accred-sub-chk:checked')).map(cb => parseInt(cb.value));

  btn.disabled = true;
  btn.innerHTML = '⏳ Saving Accreditation...';

  try {
    const res = await fetch(`${API_BASE}/super-admin/schools/${schoolId}/accreditation`, {
      method: 'PUT',
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({
        subject_ids: checkedIds
      })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Could not update accreditation');

    alert(`✔ ${data.message}`);
    window.closeAccreditationModal();
    window.loadSuperAdminDashboard();
  } catch (err) {
    alert(`❌ Save Failed: ${err.message}`);
  } finally {
    btn.disabled = false;
    btn.innerHTML = 'Save Accreditation & Active Catalog';
  }
};

window.escapeJsQuotes = function(str) {
  return String(str || '').replace(/'/g, "\\'");
};

window.openDeleteSchoolModal = function(schoolId, schoolName, schoolCode) {
  const modal = document.getElementById('deleteSchoolModal');
  if (!modal) return;
  const targetCode = (schoolCode || String(schoolId)).trim();
  document.getElementById('deleteSchoolModalId').value = String(schoolId);
  document.getElementById('deleteSchoolModalTargetCode').value = targetCode;
  document.getElementById('deleteSchoolModalName').textContent = `${schoolName} (${targetCode})`;
  document.getElementById('deleteSchoolModalCodePrompt').textContent = targetCode;
  
  const inputEl = document.getElementById('deleteSchoolConfirmInput');
  inputEl.value = '';
  
  const btn = document.getElementById('deleteSchoolConfirmBtn');
  btn.disabled = true;
  btn.style.opacity = '0.5';
  btn.style.cursor = 'not-allowed';
  
  modal.style.display = 'flex';
  setTimeout(() => inputEl.focus(), 50);
};

window.closeDeleteSchoolModal = function() {
  const modal = document.getElementById('deleteSchoolModal');
  if (modal) modal.style.display = 'none';
};

window.onDeleteSchoolInput = function(inputEl) {
  const targetCode = (document.getElementById('deleteSchoolModalTargetCode').value || '').trim();
  const typed = (inputEl.value || '').trim();
  const btn = document.getElementById('deleteSchoolConfirmBtn');
  if (typed.toUpperCase() === targetCode.toUpperCase()) {
    btn.disabled = false;
    btn.style.opacity = '1';
    btn.style.cursor = 'pointer';
  } else {
    btn.disabled = true;
    btn.style.opacity = '0.5';
    btn.style.cursor = 'not-allowed';
  }
};

window.handleConfirmDeleteSchool = async function(event) {
  event.preventDefault();
  const schoolId = document.getElementById('deleteSchoolModalId').value;
  const targetCode = document.getElementById('deleteSchoolModalTargetCode').value;
  const typed = document.getElementById('deleteSchoolConfirmInput').value.trim();

  if (typed.toUpperCase() !== targetCode.toUpperCase()) {
    alert(`❌ Input did not match required code '${targetCode}'.`);
    return;
  }

  const btn = document.getElementById('deleteSchoolConfirmBtn');
  btn.disabled = true;
  btn.textContent = 'Purging...';

  try {
    const res = await fetch(`${API_BASE}/super-admin/schools/${schoolId}`, {
      method: 'DELETE',
      headers: getHeaders()
    });
    const data = await res.json();
    if (res.ok) {
      window.closeDeleteSchoolModal();
      alert(`✔ ${data.message}\n\nPre-deletion backup saved to:\n${data.backup_saved_to}`);
      window.loadSuperAdminDashboard();
    } else {
      alert(data.detail || 'Could not delete school.');
    }
  } catch (err) {
    alert('Failed to delete school. Check server logs.');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Purge School';
  }
};

window.enterSchoolView = function(schoolId, schoolName, schoolMode, schoolCode) {
  // 1. Strict Tab-Isolated Scope (sessionStorage)
  sessionStorage.setItem('school_id', String(schoolId));
  sessionStorage.setItem('school_name', schoolName);
  sessionStorage.setItem('school_mode', schoolMode);
  if (schoolCode) {
    sessionStorage.setItem('school_abbreviation', schoolCode);
  }
  sessionStorage.setItem('is_super_admin_viewing', 'true');

  // 2. Global Storage Scope (localStorage fallback)
  localStorage.setItem('school_id', String(schoolId));
  localStorage.setItem('school_name', schoolName);
  localStorage.setItem('school_mode', schoolMode);
  if (schoolCode) {
    localStorage.setItem('school_abbreviation', schoolCode);
  }
  localStorage.setItem('is_super_admin_viewing', 'true');

  window.location.href = 'dashboard.html';
};

window.exitSchoolView = function() {
  sessionStorage.removeItem('school_id');
  sessionStorage.removeItem('school_name');
  sessionStorage.removeItem('school_mode');
  sessionStorage.removeItem('school_abbreviation');
  sessionStorage.removeItem('is_super_admin_viewing');

  localStorage.removeItem('school_id');
  localStorage.removeItem('school_name');
  localStorage.removeItem('school_mode');
  localStorage.removeItem('school_abbreviation');
  localStorage.removeItem('is_super_admin_viewing');

  window.location.href = 'super-admin.html';
};

window.toggleSchoolStatus = async function(schoolId, currentStatus) {
  const newStatus = currentStatus === 'ACTIVE' ? 'SUSPENDED' : 'ACTIVE';
  const ok = await (window.showConfirmDialog ? window.showConfirmDialog(
    '🏛️ Change School Status',
    `Are you sure you want to change school status to ${newStatus}?`,
    `Set to ${newStatus}`,
    'Cancel',
    'warning'
  ) : Promise.resolve(confirm(`Are you sure you want to change school status to ${newStatus}?`)));

  if (!ok) return;

  try {
    const res = await fetch(`${API_BASE}/super-admin/schools/${schoolId}/status`, {
      method: 'PUT',
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ status: newStatus })
    });
    if (res.ok) {
      if (window.showToast) window.showToast(`School status updated to ${newStatus}`, 'success');
      window.loadSuperAdminDashboard();
    } else {
      alert('Could not update school status.');
    }
  } catch (err) {
    alert('Failed to update status.');
  }
};

window.changeSchoolMode = async function(schoolId, newMode, currentBoarding) {
  const profileName = window.FeatureGate
    ? window.FeatureGate.getProfileName(newMode, currentBoarding || 'BOARDING_AND_DAY')
    : newMode;
  const ok = await (window.showConfirmDialog ? window.showConfirmDialog(
    '⚙️ Change School Curriculum Mode',
    `Change school mode to: ${profileName}?\n\nThis will immediately affect what features are available to this school's administrators and staff.`,
    'Apply Mode Change',
    'Cancel',
    'warning'
  ) : Promise.resolve(confirm(`Change school mode to: ${profileName}?\n\nThis will immediately affect what features are available to this school's administrators and staff.`)));

  if (!ok) return;

  try {
    const res = await fetch(`${API_BASE}/super-admin/schools/${schoolId}/mode`, {
      method: 'PUT',
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ school_mode: newMode })
    });

    if (res.ok) {
      if (window.showToast) window.showToast(`School mode updated to ${profileName}`, 'success');
      window.loadSuperAdminDashboard();
    } else {
      alert('Could not update school mode.');
      window.loadSuperAdminDashboard();
    }
  } catch (err) {
    alert('Failed to update mode.');
    window.loadSuperAdminDashboard();
  }
};

window.changeSchoolBoarding = async function(schoolId, newBoarding) {
  const ok = await (window.showConfirmDialog ? window.showConfirmDialog(
    '🏠 Change Boarding Profile',
    `Change boarding status to: ${newBoarding === 'DAY_ONLY' ? 'Day Only' : 'Boarding & Day'}?\n\nThis affects Exeat Management, Houses & Dormitories, boarding staff roles, and boarding fee categories.`,
    'Apply Boarding Status',
    'Cancel',
    'warning'
  ) : Promise.resolve(confirm(`Change boarding status to: ${newBoarding === 'DAY_ONLY' ? 'Day Only' : 'Boarding & Day'}?\n\nThis affects Exeat Management, Houses & Dormitories, boarding staff roles, and boarding fee categories.`)));

  if (!ok) {
    window.loadSuperAdminDashboard();
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/super-admin/schools/${schoolId}/boarding`, {
      method: 'PUT',
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ boarding_status: newBoarding })
    });

    if (res.ok) {
      if (window.showToast) window.showToast('Boarding status updated successfully!', 'success');
      window.loadSuperAdminDashboard();
    } else {
      const err = await res.json().catch(() => ({}));
      alert(err.detail || 'Could not update boarding status.');
      window.loadSuperAdminDashboard();
    }
  } catch (err) {
    alert('Failed to update boarding status.');
    window.loadSuperAdminDashboard();
  }
};


window.downloadSchoolBackup = async function(schoolId, schoolCode) {
  try {
    const res = await fetch(`${API_BASE}/super-admin/schools/${schoolId}/backup`, {
      headers: getHeaders()
    });

    if (!res.ok) {
      alert('Could not download backup.');
      return;
    }

    const data = await res.json();
    const jsonStr = JSON.stringify(data, null, 2);
    const blob = new Blob([jsonStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `backup_${schoolCode}_${new Date().toISOString().split('T')[0]}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  } catch (err) {
    alert('Failed to download backup data.');
  }
};

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const payload = {
    name: document.getElementById('schoolName').value.trim(),
    code: document.getElementById('schoolCode').value.trim().toUpperCase(),
    school_mode: document.getElementById('schoolMode').value,
    boarding_type: document.getElementById('schoolBoarding').value,
    address: document.getElementById('schoolAddress').value.trim() || null,
    phone: document.getElementById('schoolPhone').value.trim() || null,
    email: document.getElementById('schoolEmail').value.trim() || null,
    admin_username: document.getElementById('adminUsername').value.trim(),
    admin_email: document.getElementById('adminEmail').value.trim(),
    admin_password: document.getElementById('adminPassword').value
  };

  try {
    const res = await fetch(`${API_BASE}/super-admin/schools`, {
      method: 'POST',
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    if (!res.ok) {
      alert(data.detail || 'Could not register school.');
      return;
    }

    alert(`✔ School '${data.school.name}' onboarded successfully!`);
    closeNewSchoolModal();
    loadSuperAdminDashboard();
  } catch (err) {
    alert('Failed to onboard new school.');
  }
});

// ── 1-Click Master Cloud Sync ────────────────────────────────────────────────
window.openCloudSyncModal = function() {
  const modal = document.getElementById('cloudSyncModal');
  const urlInput = document.getElementById('cloudSyncRemoteUrl');
  const pwdInput = document.getElementById('cloudSyncPassword');
  const statusMsg = document.getElementById('cloudSyncStatusMsg');

  if (urlInput) {
    const savedUrl = localStorage.getItem('last_cloud_sync_url') || 'https://sms-1-4g9s.onrender.com';
    urlInput.value = savedUrl;
  }
  if (pwdInput) pwdInput.value = '';
  if (statusMsg) {
    statusMsg.style.display = 'none';
    statusMsg.innerHTML = '';
  }

  if (modal) modal.style.display = 'flex';
};

window.closeCloudSyncModal = function() {
  const modal = document.getElementById('cloudSyncModal');
  if (modal) modal.style.display = 'none';
};

window.handleStartCloudSync = async function(event) {
  event.preventDefault();

  const remoteUrl = document.getElementById('cloudSyncRemoteUrl').value.trim();
  const password = document.getElementById('cloudSyncPassword').value;
  const syncMode = document.getElementById('cloudSyncMode').value;
  const statusMsg = document.getElementById('cloudSyncStatusMsg');
  const submitBtn = document.getElementById('cloudSyncSubmitBtn');

  if (!remoteUrl || !password) {
    alert('Please provide both the Remote Cloud URL and your Super-Admin password.');
    return;
  }

  submitBtn.disabled = true;
  submitBtn.style.opacity = '0.6';
  submitBtn.innerHTML = '⏳ Synchronizing with Cloud...';

  if (statusMsg) {
    statusMsg.style.display = 'block';
    statusMsg.style.background = 'rgba(2, 132, 199, 0.15)';
    statusMsg.style.border = '1px solid #0284c7';
    statusMsg.style.color = '#38bdf8';
    statusMsg.innerHTML = 'Connecting to Render Cloud server, downloading live database snapshot...';
  }

  try {
    const res = await fetch(`${API_BASE}/super-admin/sync-from-cloud`, {
      method: 'POST',
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({
        remote_url: remoteUrl,
        username: 'superadmin',
        password: password,
        sync_mode: syncMode
      })
    });

    const data = await res.json();

    if (!res.ok) {
      if (statusMsg) {
        statusMsg.style.display = 'block';
        statusMsg.style.background = 'rgba(239, 68, 68, 0.15)';
        statusMsg.style.border = '1px solid #ef4444';
        statusMsg.style.color = '#f87171';
        statusMsg.innerHTML = `<strong>Sync Failed:</strong> ${data.detail || 'Could not synchronize with cloud.'}`;
      } else {
        alert(data.detail || 'Could not synchronize with cloud.');
      }
      return;
    }

    // Save URL for future convenience
    localStorage.setItem('last_cloud_sync_url', remoteUrl);

    if (statusMsg) {
      statusMsg.style.display = 'block';
      statusMsg.style.background = 'rgba(16, 185, 129, 0.15)';
      statusMsg.style.border = '1px solid #10b981';
      statusMsg.style.color = '#34d399';
      statusMsg.innerHTML = `<strong>✔ Sync Succeeded!</strong> ${data.message || 'All cloud data imported.'}`;
    }

    setTimeout(() => {
      closeCloudSyncModal();
      loadSuperAdminDashboard();
    }, 1200);

  } catch (err) {
    if (statusMsg) {
      statusMsg.style.display = 'block';
      statusMsg.style.background = 'rgba(239, 68, 68, 0.15)';
      statusMsg.style.border = '1px solid #ef4444';
      statusMsg.style.color = '#f87171';
      statusMsg.innerHTML = `<strong>Network Error:</strong> ${err.message}`;
    }
  } finally {
    submitBtn.disabled = false;
    submitBtn.style.opacity = '1';
    submitBtn.innerHTML = 'Start Cloud Sync';
  }
};


// ── Enterprise Delete / Purge School Modal Handlers ─────────────────────────

window.openDeleteSchoolModal = function(schoolId, schoolName, schoolCode) {
  const modal = document.getElementById('deleteSchoolModal');
  const modalIdInput = document.getElementById('deleteSchoolModalId');
  const modalTargetCodeInput = document.getElementById('deleteSchoolModalTargetCode');
  const modalNameEl = document.getElementById('deleteSchoolModalName');
  const modalCodePromptEl = document.getElementById('deleteSchoolModalCodePrompt');
  const confirmInput = document.getElementById('deleteSchoolConfirmInput');
  const confirmBtn = document.getElementById('deleteSchoolConfirmBtn');

  if (modalIdInput) modalIdInput.value = String(schoolId);
  if (modalTargetCodeInput) modalTargetCodeInput.value = (schoolCode || '').toUpperCase();
  if (modalNameEl) modalNameEl.textContent = schoolName;
  if (modalCodePromptEl) modalCodePromptEl.textContent = (schoolCode || '').toUpperCase();
  
  if (confirmInput) {
    confirmInput.value = '';
    confirmInput.placeholder = `Type "${(schoolCode || '').toUpperCase()}" to confirm`;
  }
  if (confirmBtn) {
    confirmBtn.disabled = true;
    confirmBtn.style.opacity = '0.5';
    confirmBtn.style.cursor = 'not-allowed';
  }

  if (modal) modal.style.display = 'flex';
  if (confirmInput) setTimeout(() => confirmInput.focus(), 100);
};

window.closeDeleteSchoolModal = function() {
  const modal = document.getElementById('deleteSchoolModal');
  if (modal) modal.style.display = 'none';
};

window.onDeleteSchoolInput = function(inputEl) {
  const targetCode = (document.getElementById('deleteSchoolModalTargetCode')?.value || '').trim().toUpperCase();
  const typed = (inputEl.value || '').trim().toUpperCase();
  const confirmBtn = document.getElementById('deleteSchoolConfirmBtn');

  if (confirmBtn) {
    if (typed === targetCode && targetCode.length > 0) {
      confirmBtn.disabled = false;
      confirmBtn.style.opacity = '1';
      confirmBtn.style.cursor = 'pointer';
    } else {
      confirmBtn.disabled = true;
      confirmBtn.style.opacity = '0.5';
      confirmBtn.style.cursor = 'not-allowed';
    }
  }
};

window.handleConfirmDeleteSchool = async function(event) {
  event.preventDefault();
  const schoolId = document.getElementById('deleteSchoolModalId')?.value;
  const confirmBtn = document.getElementById('deleteSchoolConfirmBtn');

  if (!schoolId) return;

  confirmBtn.disabled = true;
  confirmBtn.innerHTML = '⏳ Purging School...';

  try {
    const res = await fetch(`${API_BASE}/super-admin/schools/${schoolId}`, {
      method: 'DELETE',
      headers: getHeaders()
    });

    const data = await res.json();

    if (!res.ok) {
      alert(`❌ Purge Failed: ${data.detail || 'Could not delete school.'}`);
      confirmBtn.disabled = false;
      confirmBtn.innerHTML = 'Purge School';
      return;
    }

    alert(`✔ ${data.message || 'School permanently deleted.'}`);
    closeDeleteSchoolModal();
    loadSuperAdminDashboard();

  } catch (err) {
    alert(`❌ Network error: ${err.message}`);
    confirmBtn.disabled = false;
    confirmBtn.innerHTML = 'Purge School';
  }
};

// ── Enterprise Edit School Profile Modal Handlers ───────────────────────────

window.updateEditModeNotice = function() {
  const mode = document.getElementById('editSchoolMode')?.value;
  const noticeEl = document.getElementById('editSchoolModeNotice');
  if (!noticeEl) return;

  if (mode === 'BASIC_ONLY') {
    noticeEl.style.background = 'rgba(16, 185, 129, 0.12)';
    noticeEl.style.borderColor = 'rgba(16, 185, 129, 0.3)';
    noticeEl.style.color = '#a7f3d0';
    noticeEl.innerHTML = `<strong>🎯 Basic School Profile Activated:</strong> Uses <em>BECE Standard Grading (Grades 1–9)</em> and Cumulative Record Folder. SHS Electives, CSSPS &amp; Transcripts will be hidden. Existing students, staff, and past academic records are 100% preserved.`;
  } else if (mode === 'SHS_ONLY') {
    noticeEl.style.background = 'rgba(99, 102, 241, 0.12)';
    noticeEl.style.borderColor = 'rgba(99, 102, 241, 0.3)';
    noticeEl.style.color = '#c7d2fe';
    noticeEl.innerHTML = `<strong>🏛️ Senior High School Profile Activated:</strong> Uses <em>WAEC/WASSCE Standard Grading (A1–F9)</em>, CSSPS Placement, Programs, and Departments. Cumulative Record Folder will be hidden.`;
  } else {
    noticeEl.style.background = 'rgba(14, 165, 233, 0.12)';
    noticeEl.style.borderColor = 'rgba(14, 165, 233, 0.3)';
    noticeEl.style.color = '#bae6fd';
    noticeEl.innerHTML = `<strong>🌐 Combined Profile Activated:</strong> Full multi-tier access enabled for both Basic and Senior High School levels.`;
  }
};

window.openEditSchoolModal = async function(schoolId) {
  const modal = document.getElementById('editSchoolModal');
  const statusMsg = document.getElementById('editSchoolStatusMsg');
  if (statusMsg) statusMsg.style.display = 'none';

  try {
    const res = await fetch(`${API_BASE}/super-admin/schools/${schoolId}`, {
      headers: getHeaders()
    });
    if (!res.ok) {
      alert('Failed to load school details.');
      return;
    }
    const school = await res.json();

    const setVal = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.value = val !== undefined && val !== null ? val : '';
    };

    setVal('editSchoolId', school.id);
    const labelEl = document.getElementById('editSchoolIdLabel');
    if (labelEl) labelEl.textContent = `${school.id} (${school.code || ''})`;
    setVal('editSchoolName', school.name);
    setVal('editSchoolCode', school.code);
    setVal('editSchoolMode', school.school_mode || 'COMBINED');
    setVal('editSchoolBoarding', school.boarding_type || 'BOARDING_AND_DAY');
    setVal('editSchoolPhone', school.phone);
    setVal('editSchoolEmail', school.email);
    setVal('editSchoolAddress', school.address);
    setVal('editSchoolSubdomain', school.subdomain);
    setVal('editSchoolLogoUrl', school.logo_url);

    // Update Crest Preview
    const imgEl = document.getElementById('editSchoolLogoImg');
    const defaultEl = document.getElementById('editSchoolDefaultCrest');
    const removeBtn = document.getElementById('btnRemoveEditLogo');

    if (school.logo_url) {
      if (imgEl) { imgEl.src = school.logo_url; imgEl.style.display = 'block'; }
      if (defaultEl) defaultEl.style.display = 'none';
      if (removeBtn) removeBtn.style.display = 'inline-block';
    } else {
      if (imgEl) { imgEl.src = ''; imgEl.style.display = 'none'; }
      if (defaultEl) defaultEl.style.display = 'block';
      if (removeBtn) removeBtn.style.display = 'none';
    }

    if (window.updateEditModeNotice) window.updateEditModeNotice();
    if (modal) modal.style.display = 'flex';

  } catch (err) {
    alert(`Network Error: ${err.message}`);
  }
};

window.closeEditSchoolModal = function() {
  const modal = document.getElementById('editSchoolModal');
  if (modal) modal.style.display = 'none';
};

window.handleEditLogoFileSelect = function(event) {
  const file = event.target.files?.[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = function(e) {
    const dataUri = e.target.result;
    document.getElementById('editSchoolLogoUrl').value = dataUri;
    const imgEl = document.getElementById('editSchoolLogoImg');
    const defaultEl = document.getElementById('editSchoolDefaultCrest');
    const removeBtn = document.getElementById('btnRemoveEditLogo');
    if (imgEl) { imgEl.src = dataUri; imgEl.style.display = 'block'; }
    if (defaultEl) defaultEl.style.display = 'none';
    if (removeBtn) removeBtn.style.display = 'inline-block';
  };
  reader.readAsDataURL(file);
};

window.handleRemoveEditLogo = function() {
  document.getElementById('editSchoolLogoUrl').value = '';
  document.getElementById('editSchoolLogoFile').value = '';
  const imgEl = document.getElementById('editSchoolLogoImg');
  const defaultEl = document.getElementById('editSchoolDefaultCrest');
  const removeBtn = document.getElementById('btnRemoveEditLogo');
  if (imgEl) { imgEl.src = ''; imgEl.style.display = 'none'; }
  if (defaultEl) defaultEl.style.display = 'block';
  if (removeBtn) removeBtn.style.display = 'none';
};

window.handleEditLogoUrlInput = function(val) {
  const imgEl = document.getElementById('editSchoolLogoImg');
  const defaultEl = document.getElementById('editSchoolDefaultCrest');
  const removeBtn = document.getElementById('btnRemoveEditLogo');
  const trimmed = (val || '').trim();

  if (trimmed) {
    if (imgEl) { imgEl.src = trimmed; imgEl.style.display = 'block'; }
    if (defaultEl) defaultEl.style.display = 'none';
    if (removeBtn) removeBtn.style.display = 'inline-block';
  } else {
    if (imgEl) { imgEl.src = ''; imgEl.style.display = 'none'; }
    if (defaultEl) defaultEl.style.display = 'block';
    if (removeBtn) removeBtn.style.display = 'none';
  }
};

window.handleSaveEditSchool = async function(event) {
  event.preventDefault();
  const schoolId = document.getElementById('editSchoolId')?.value;
  const btn = document.getElementById('btnSaveEditSchool');
  const statusMsg = document.getElementById('editSchoolStatusMsg');
  if (!schoolId) return;

  const payload = {
    name: document.getElementById('editSchoolName')?.value?.trim(),
    code: document.getElementById('editSchoolCode')?.value?.trim()?.toUpperCase(),
    school_mode: document.getElementById('editSchoolMode')?.value,
    boarding_type: document.getElementById('editSchoolBoarding')?.value,
    phone: document.getElementById('editSchoolPhone')?.value?.trim() || null,
    email: document.getElementById('editSchoolEmail')?.value?.trim() || null,
    address: document.getElementById('editSchoolAddress')?.value?.trim() || null,
    subdomain: document.getElementById('editSchoolSubdomain')?.value?.trim()?.toLowerCase() || null,
    logo_url: document.getElementById('editSchoolLogoUrl')?.value?.trim() || null
  };

  if (!payload.name || !payload.code) {
    alert('Please fill in both the School Name and Code.');
    return;
  }

  btn.disabled = true;
  btn.innerHTML = '⏳ Saving Changes...';
  if (statusMsg) statusMsg.style.display = 'none';

  try {
    const res = await fetch(`${API_BASE}/super-admin/schools/${schoolId}`, {
      method: 'PUT',
      headers: {
        ...getHeaders(),
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    });

    const data = await res.json();

    if (!res.ok) {
      if (statusMsg) {
        statusMsg.style.display = 'block';
        statusMsg.style.background = 'rgba(239, 68, 68, 0.15)';
        statusMsg.style.border = '1px solid #ef4444';
        statusMsg.style.color = '#f87171';
        statusMsg.innerHTML = `<strong>Update Failed:</strong> ${data.detail || 'Could not update school profile.'}`;
      }
      return;
    }

    if (statusMsg) {
      statusMsg.style.display = 'block';
      statusMsg.style.background = 'rgba(16, 185, 129, 0.15)';
      statusMsg.style.border = '1px solid #10b981';
      statusMsg.style.color = '#34d399';
      statusMsg.innerHTML = `<strong>Success!</strong> ${data.message || 'School profile updated successfully.'}`;
    }

    setTimeout(() => {
      closeEditSchoolModal();
      loadSuperAdminDashboard();
    }, 1000);

  } catch (err) {
    if (statusMsg) {
      statusMsg.style.display = 'block';
      statusMsg.style.background = 'rgba(239, 68, 68, 0.15)';
      statusMsg.style.border = '1px solid #ef4444';
      statusMsg.style.color = '#f87171';
      statusMsg.innerHTML = `<strong>Network Error:</strong> ${err.message}`;
    }
  } finally {
    btn.disabled = false;
    btn.innerHTML = '💾 Save Profile Changes';
  }
};

// ── Multi-Tenant Sync & Telemetry Monitor Handlers ─────────────────────────

window.loadSuperAdminSyncMonitor = async function() {
  const tbody = document.getElementById('syncMonitorTableBody');
  const badge = document.getElementById('syncMonitorNetworkBadge');
  const kpiPending = document.getElementById('syncKpiPending');
  const kpiSynced = document.getElementById('syncKpiSynced');
  const kpiCloud = document.getElementById('syncKpiCloudGateway');
  const kpiSub = document.getElementById('syncKpiGatewaySubtitle');

  try {
    const res = await fetch(`${API_BASE}/sync/super-admin/overview`, { headers: getHeaders() });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    if (kpiPending) kpiPending.textContent = (data.total_network_pending || 0).toLocaleString();
    if (kpiSynced) kpiSynced.textContent = (data.total_network_synced || 0).toLocaleString();
    if (kpiCloud) {
      kpiCloud.textContent = data.is_cloud_configured ? 'Central Cloud Connected' : 'Local Standalone Engine';
      kpiCloud.style.color = data.is_cloud_configured ? '#38bdf8' : '#a78bfa';
    }
    if (kpiSub) {
      kpiSub.textContent = data.cloud_sync_url || 'Local Delta Store-and-Forward';
    }

    if (badge) {
      if (data.total_network_pending === 0) {
        badge.textContent = '● All Nodes Synchronized';
        badge.style.background = '#10b981';
      } else {
        badge.textContent = `● ${data.total_network_pending} Queued Offline Changes`;
        badge.style.background = '#f59e0b';
      }
    }

    window.renderSuperAdminSyncMonitor(data.schools || []);

  } catch (err) {
    if (tbody) {
      tbody.innerHTML = `<tr><td colspan="6" style="padding:16px; text-align:center; color:#f87171;">⚠️ Could not retrieve sync telemetry: ${err.message}</td></tr>`;
    }
    if (badge) {
      badge.textContent = '● Telemetry Offline';
      badge.style.background = '#ef4444';
    }
  }
};

window.renderSuperAdminSyncMonitor = function(schools) {
  const tbody = document.getElementById('syncMonitorTableBody');
  if (!tbody) return;

  if (!schools || schools.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" style="padding:16px; text-align:center; opacity:0.7;">No school nodes found.</td></tr>';
    return;
  }

  tbody.innerHTML = schools.map(s => {
    let stateBadge = '<span class="badge-mode" style="background:#10b981; font-size:0.72rem;">● SYNCHRONIZED</span>';
    if (s.health_state === 'PENDING_SYNC') {
      stateBadge = `<span class="badge-mode" style="background:#f59e0b; font-size:0.72rem;">● ${s.pending_count} QUEUED</span>`;
    } else if (s.health_state === 'IDLE') {
      stateBadge = '<span class="badge-mode" style="background:#64748b; font-size:0.72rem;">● IDLE</span>';
    }

    const lastSyncTime = s.last_synced_at ? new Date(s.last_synced_at).toLocaleString() : 'Never';

    return `
      <tr style="border-bottom:1px solid var(--border-color, #334155); transition:background 0.15s;">
        <td style="padding:8px 10px;">
          <div style="font-weight:700; color:#fff;">${s.school_name}</div>
          <div style="font-size:0.72rem; color:#94a3b8;"><code style="color:#cbd5e1;">${s.school_code}</code> • ID: #${s.school_id}</div>
        </td>
        <td style="padding:8px 10px; text-align:center; font-weight:700; color:${s.pending_count > 0 ? '#f59e0b' : '#10b981'};">
          ${s.pending_count}
        </td>
        <td style="padding:8px 10px; text-align:center; color:#cbd5e1;">
          ${s.total_synced_count}
        </td>
        <td style="padding:8px 10px; text-align:center; font-size:0.75rem; color:#94a3b8;">
          ${lastSyncTime}
        </td>
        <td style="padding:8px 10px; text-align:center;">
          ${stateBadge}
        </td>
        <td style="padding:8px 10px; text-align:right;">
          <button type="button" class="btn" style="padding:4px 9px; font-size:0.75rem; background:rgba(14,165,233,0.2); border-color:#0ea5e9; color:#38bdf8; font-weight:600;" onclick="window.triggerSingleSchoolSync(${s.school_id})">
            ⚡ Force Sync
          </button>
        </td>
      </tr>
    `;
  }).join('');
};

window.triggerSingleSchoolSync = async function(schoolId) {
  try {
    const res = await fetch(`${API_BASE}/sync/super-admin/trigger-school/${schoolId}`, {
      method: 'POST',
      headers: getHeaders()
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Sync failed');
    if (window.showToast) {
      window.showToast(data.message, 'success');
    } else {
      alert(`✔ ${data.message}`);
    }
    window.loadSuperAdminSyncMonitor();
  } catch (err) {
    alert(`❌ Sync failed for school #${schoolId}: ${err.message}`);
  }
};

window.triggerAllSchoolsSync = async function() {
  const btn = document.getElementById('btnSyncAllSchools');
  if (btn) {
    btn.disabled = true;
    btn.textContent = '⏳ Syncing All Nodes...';
  }

  try {
    const res = await fetch(`${API_BASE}/sync/super-admin/trigger-all`, {
      method: 'POST',
      headers: getHeaders()
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Global sync failed');
    if (window.showToast) {
      window.showToast(data.message, 'success');
    } else {
      alert(`✔ ${data.message}`);
    }
    window.loadSuperAdminSyncMonitor();
  } catch (err) {
    alert(`❌ Global Sync Failed: ${err.message}`);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = '🔄 Sync All Network Nodes';
    }
  }
};

// ── Enterprise SMS Multi-Gateway Handlers ────────────────────────────────────

window.loadSMSGatewayStatus = async function() {
  const statusPill = document.getElementById('smsGatewayStatusPill');
  const primarySelect = document.getElementById('smsPrimaryGateway');
  const senderInput = document.getElementById('smsMasterSenderId');
  const mnotifyInput = document.getElementById('mnotifyApiKey');
  const hubtelIdInput = document.getElementById('hubtelClientId');
  const hubtelSecretInput = document.getElementById('hubtelClientSecret');

  try {
    const res = await fetch(`${API_BASE}/super-admin/sms-gateway/status`, {
      headers: getHeaders()
    });
    if (!res.ok) return;
    const data = await res.json();

    if (primarySelect && data.primary_gateway) primarySelect.value = data.primary_gateway;
    if (senderInput && data.mnotify?.sender_id) senderInput.value = data.mnotify.sender_id;
    if (hubtelIdInput && data.hubtel?.client_id_masked && data.hubtel.client_id_masked !== 'Missing') {
      hubtelIdInput.placeholder = data.hubtel.client_id_masked;
    }
    if (mnotifyInput && data.mnotify?.api_key_masked && data.mnotify.api_key_masked !== 'Missing') {
      mnotifyInput.placeholder = `Configured (${data.mnotify.api_key_masked})`;
    }

    if (statusPill) {
      if (data.mnotify?.is_configured) {
        statusPill.innerHTML = '🟢 mNotify Active &bull; Hubtel Failover Ready';
        statusPill.style.background = 'rgba(16, 185, 129, 0.15)';
        statusPill.style.color = '#34d399';
        statusPill.style.borderColor = 'rgba(16, 185, 129, 0.3)';
      } else if (data.hubtel?.is_configured) {
        statusPill.innerHTML = '🟡 Hubtel Active &bull; mNotify Awaiting Key';
        statusPill.style.background = 'rgba(245, 158, 11, 0.15)';
        statusPill.style.color = '#fbbf24';
        statusPill.style.borderColor = 'rgba(245, 158, 11, 0.3)';
      } else {
        statusPill.innerHTML = '💾 Offline WAL Outbox Active (Plug Keys to Go Live)';
        statusPill.style.background = 'rgba(99, 102, 241, 0.15)';
        statusPill.style.color = '#a5b4fc';
        statusPill.style.borderColor = 'rgba(99, 102, 241, 0.3)';
      }
    }
  } catch (err) {
    console.warn('Could not load SMS gateway status:', err);
  }
};

window.handleSaveSMSGatewayConfig = async function(event) {
  event.preventDefault();
  const btn = document.getElementById('btnSaveSMSGateway');
  const statusMsg = document.getElementById('smsGatewayStatusMsg');

  const payload = {
    primary_gateway: document.getElementById('smsPrimaryGateway')?.value || 'mnotify',
    mnotify_sender_id: (document.getElementById('smsMasterSenderId')?.value || 'EDUMANAGE').trim().toUpperCase(),
    mnotify_api_key: document.getElementById('mnotifyApiKey')?.value?.trim() || undefined,
    hubtel_client_id: document.getElementById('hubtelClientId')?.value?.trim() || undefined,
    hubtel_client_secret: document.getElementById('hubtelClientSecret')?.value?.trim() || undefined,
    auto_failover: true
  };

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '⏳ Saving Settings...';
  }

  try {
    const res = await fetch(`${API_BASE}/super-admin/sms-gateway/config`, {
      method: 'PUT',
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Could not update SMS gateway configuration');

    if (statusMsg) {
      statusMsg.style.display = 'block';
      statusMsg.style.background = 'rgba(16, 185, 129, 0.15)';
      statusMsg.style.border = '1px solid #10b981';
      statusMsg.style.color = '#34d399';
      statusMsg.innerHTML = `<strong>✔ Success:</strong> ${data.message}`;
      setTimeout(() => { statusMsg.style.display = 'none'; }, 4000);
    }

    if (window.showToast) window.showToast('SMS Gateway settings updated successfully!', 'success');
    window.loadSMSGatewayStatus();
  } catch (err) {
    if (statusMsg) {
      statusMsg.style.display = 'block';
      statusMsg.style.background = 'rgba(239, 68, 68, 0.15)';
      statusMsg.style.border = '1px solid #ef4444';
      statusMsg.style.color = '#f87171';
      statusMsg.innerHTML = `<strong>Update Failed:</strong> ${err.message}`;
    }
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '💾 Save Gateway Settings';
    }
  }
};

window.checkSMSBalance = async function() {
  try {
    const res = await fetch(`${API_BASE}/super-admin/sms-gateway/status`, {
      headers: getHeaders()
    });
    if (!res.ok) throw new Error('Could not fetch balance');
    const data = await res.json();

    const mnotifyBal = data.mnotify?.balance_info?.sms_balance ?? 'N/A';
    const msg = `📱 SMS Gateway Telemetry:\n\n• Primary Gateway: ${data.primary_gateway.toUpperCase()}\n• mNotify Live Balance: ${mnotifyBal} credits\n• Total Global Messages Sent: ${data.telemetry?.total_sent || 0}\n• Offline Outbox Queued: ${data.telemetry?.total_offline_queued || 0}`;
    alert(msg);
  } catch (err) {
    alert(`Could not verify balance: ${err.message}`);
  }
};

window.openTestSMSModal = async function() {
  const phone = prompt('Enter a Ghanaian phone number (e.g. 0244123456) to send a test message:');
  if (!phone) return;

  try {
    const res = await fetch(`${API_BASE}/super-admin/sms-gateway/test`, {
      method: 'POST',
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({
        test_phone: phone.trim(),
        message: 'eduManage360: Live test dispatch from your Enterprise Multi-Gateway SMS Engine.'
      })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Test dispatch failed');

    alert(`✔ Test Dispatch Result:\nStatus: ${data.status}\nGateway: ${data.gateway || 'OFFLINE_QUEUE'}\nRecipient: ${data.recipient}\nMessage ID: ${data.message_id}`);
    window.loadSMSGatewayStatus();
  } catch (err) {
    alert(`❌ Test Dispatch Failed: ${err.message}`);
  }
};

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => window.loadSuperAdminDashboard());
} else {
  window.loadSuperAdminDashboard();
}


