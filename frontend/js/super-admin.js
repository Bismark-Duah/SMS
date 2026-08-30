const API_BASE = window.API_BASE || (window.location.origin.includes('http') ? (window.location.origin + '/api') : 'http://127.0.0.1:8000/api');

const token = localStorage.getItem('accessToken');
if (!token) {
  window.location.href = 'auth.html';
}

function getHeaders(headers = {}) {
  const h = { ...headers };
  if (token) h['Authorization'] = `Bearer ${token}`;
  return h;
}

window.escapeJsQuotes = function(str) {
  if (!str) return '';
  return String(str).replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/"/g, '&quot;');
};

const modal = document.getElementById('newSchoolModal');
const form = document.getElementById('newSchoolForm');

window.openNewSchoolModal = function() {
  if (modal) modal.classList.add('active');
};

window.closeNewSchoolModal = function() {
  if (modal) modal.classList.remove('active');
  if (form) form.reset();
};

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
  try {
    const res = await fetch(`${API_BASE}/super-admin/dashboard`, { headers: getHeaders() });
    if (!res.ok) {
      if (res.status === 403) {
        alert('Super-Admin privileges required.');
        window.location.href = 'dashboard.html';
        return;
      }
      throw new Error('Failed to load Super-Admin dashboard');
    }

    const data = await res.json();
    window.allRegisteredSchools = data.schools || [];

    // Populate KPIs
    document.getElementById('kpiTotalSchools').textContent = data.total_schools || 0;
    const activeBadge = document.getElementById('kpiActiveSchoolsBadge');
    if (activeBadge) activeBadge.textContent = `${data.active_schools || 0} Active / ${data.total_schools || 0} Total`;

    document.getElementById('kpiTotalStudents').textContent = (data.total_students || 0).toLocaleString();
    const demoSplit = document.getElementById('kpiStudentsDemographics');
    if (demoSplit) {
      demoSplit.textContent = `Boys: ${data.total_boys || 0} | Girls: ${data.total_girls || 0} | Brdg: ${data.total_boarding || 0}`;
    }

    document.getElementById('kpiTotalUsers').textContent = (data.total_users || 0).toLocaleString();
    document.getElementById('kpiTotalFees').textContent = `GH₵ ${data.total_fees_collected ? data.total_fees_collected.toLocaleString('en-US', { minimumFractionDigits: 2 }) : '0.00'}`;
    
    const recRate = document.getElementById('kpiFeeRecoveryRate');
    if (recRate) {
      recRate.textContent = `Recovery: ${data.overall_collection_rate || 0}% of GH₵ ${(data.total_fees_billed || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
    }

    const diag = data.diagnostics || {};
    document.getElementById('kpiDbSize').textContent = `${diag.db_size_mb || 0} MB`;
    document.getElementById('kpiBackupStatus').textContent = `Backups: ${diag.backups_count || 0} | Last: ${diag.last_backup_time || 'None'}`;

    // Render Comparative Visual Analytics
    window.renderComparativeAnalytics(data);

    // Render Schools Directory Table
    window.filterSchoolsDirectory();

    // Load Real-Time Master Audit Feed
    window.loadMasterAuditStream();

  } catch (error) {
    console.error('Super-Admin dashboard error:', error);
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

    // Profile Badge
    let profileBadge = '';
    if (s.school_mode === 'BASIC_ONLY') {
      profileBadge = `<span class="badge-mode badge-basic" style="display:inline-flex; align-items:center; gap:4px; padding:4px 10px; font-size:0.8rem;" title="Basic School Profile (KG - JHS)">🎯 Basic School</span>`;
    } else if (s.school_mode === 'SHS_ONLY') {
      profileBadge = `<span class="badge-mode badge-shs" style="display:inline-flex; align-items:center; gap:4px; padding:4px 10px; font-size:0.8rem;" title="Senior High School Profile (SHS 1 - 3, CSSPS, WAEC)">🏛️ SHS Profile</span>`;
    } else {
      profileBadge = `<span class="badge-mode badge-combined" style="display:inline-flex; align-items:center; gap:4px; padding:4px 10px; font-size:0.8rem;" title="Combined Multi-Tier Profile (Basic + SHS)">🌐 Combined</span>`;
    }

    return `
      <tr style="border-bottom: 1px solid var(--border-color, #334155); transition: background 0.15s;">
        <!-- 1. School Identity -->
        <td style="padding:10px 12px;">
          <div style="font-weight:700; font-size:0.92rem; color:#fff; margin-bottom:3px;">${s.name}</div>
          <div style="display:flex; align-items:center; gap:6px; font-size:0.75rem; color:#94a3b8;">
            <code style="background:rgba(255,255,255,0.08); padding:1px 5px; border-radius:4px; font-weight:700; color:#cbd5e1;">${s.code}</code>
            <span>•</span>
            <span style="font-weight:600;">ID: #${s.id}</span>
          </div>
        </td>

        <!-- 2. Academic & Boarding Config -->
        <td style="padding:10px 12px; width:160px;">
          <div style="display:flex; flex-direction:column; gap:5px;">
            <select onchange="window.changeSchoolMode(${s.id}, this.value, this.closest('tr').querySelector('.boarding-select').value)"
                    style="width:100%; box-sizing:border-box; padding:4px 6px; font-size:0.78rem; border-radius:5px; background:#1e293b; color:#fff; border:1px solid #6366f1; cursor:pointer;" title="Academic Mode">
              <option value="SHS_ONLY"   ${s.school_mode === 'SHS_ONLY'   ? 'selected' : ''}>SHS Only</option>
              <option value="BASIC_ONLY" ${s.school_mode === 'BASIC_ONLY' ? 'selected' : ''}>Basic Only</option>
              <option value="COMBINED"   ${s.school_mode === 'COMBINED'   ? 'selected' : ''}>Combined</option>
            </select>
            <select class="boarding-select"
                    onchange="window.changeSchoolBoarding(${s.id}, this.value)"
                    style="width:100%; box-sizing:border-box; padding:4px 6px; font-size:0.78rem; border-radius:5px; background:#1e293b; color:#fff; border:1px solid #0891b2; cursor:pointer;" title="Boarding Setup">
              <option value="BOARDING_AND_DAY" ${boardingVal === 'BOARDING_AND_DAY' ? 'selected' : ''}>Boarding &amp; Day</option>
              <option value="DAY_ONLY"         ${boardingVal === 'DAY_ONLY'         ? 'selected' : ''}>Day Only</option>
              <option value="BOARDING_ONLY"     ${boardingVal === 'BOARDING_ONLY'     ? 'selected' : ''}>Boarding Only</option>
            </select>
          </div>
        </td>

        <!-- 3. Active Profile Badge -->
        <td style="padding:10px 12px; text-align:center; white-space:nowrap;">
          ${profileBadge}
        </td>

        <!-- 4. Enrollment & Staff Counts -->
        <td style="padding:10px 12px; text-align:center; white-space:nowrap;">
          <div style="font-size:0.92rem; font-weight:700; color:#fff;">${s.student_count} <span style="font-size:0.72rem; font-weight:500; opacity:0.7;">Students</span></div>
          <div style="font-size:0.75rem; color:#94a3b8; margin-top:2px;">${s.user_count} Staff</div>
        </td>

        <!-- 5. Status Pill -->
        <td style="padding:10px 12px; text-align:center; white-space:nowrap;">
          <span class="${statusClass}" style="display:inline-flex; align-items:center; gap:4px; font-size:0.8rem; font-weight:700;">● ${s.status}</span>
        </td>

        <!-- 6. Command Actions Toolbar -->
        <td style="padding:10px 12px; text-align:right; white-space:nowrap;">
          <div style="display:inline-flex; gap:5px; align-items:center; justify-content:flex-end;">
            <button class="btn primary" style="padding:5px 10px; font-size:0.78rem; font-weight:600;" onclick="window.enterSchoolView(${s.id}, '${window.escapeJsQuotes(s.name)}', '${s.school_mode}', '${window.escapeJsQuotes(s.code || '')}')" title="Enter live school view">👁 Enter</button>
            <button class="btn" style="padding:5px 8px; font-size:0.78rem; background:rgba(99,102,241,0.2); border-color:#6366f1; color:#a5b4fc;" onclick="window.openAccreditationModal(${s.id}, '${window.escapeJsQuotes(s.name)}', '${s.school_mode}')" title="Configure accredited tracks and active subjects">⚙️ Accredit</button>
            <button class="btn" style="padding:5px 8px; font-size:0.78rem; background:#0284c7; border-color:#0369a1; color:#fff;" onclick="window.downloadSchoolBackup(${s.id}, '${s.code}')" title="Download school backup snapshot">📥 Backup</button>
            <button class="btn" style="padding:5px 8px; font-size:0.78rem; background:${s.status === 'ACTIVE' ? '#d97706' : '#10b981'}; border-color:${s.status === 'ACTIVE' ? '#b45309' : '#059669'}; color:#fff;" onclick="window.toggleSchoolStatus(${s.id}, '${s.status}')" title="${s.status === 'ACTIVE' ? 'Suspend School Account' : 'Activate School'}">${s.status === 'ACTIVE' ? '⏸ Suspend' : '▶ Activate'}</button>
            <button class="btn danger" style="padding:5px 8px; font-size:0.78rem; background:#dc2626; border-color:#b91c1c;" onclick="window.openDeleteSchoolModal(${s.id}, '${window.escapeJsQuotes(s.name)}', '${window.escapeJsQuotes(s.code || '')}')" title="Permanently Purge School">🗑 Delete</button>
          </div>
        </td>
      </tr>
    `;
  }).join('');
};

window.loadMasterAuditStream = async function() {
  const container = document.getElementById('masterAuditStreamContainer');
  const actionFilter = document.getElementById('auditActionFilter')?.value || '';

  try {
    let url = `${API_BASE}/super-admin/audit-stream?limit=50`;
    if (actionFilter) url += `&action=${encodeURIComponent(actionFilter)}`;

    const res = await fetch(url, { headers: getHeaders() });
    if (!res.ok) throw new Error('Failed to load audit stream');
    const data = await res.json();

    if (!container) return;

    if (!data.logs || data.logs.length === 0) {
      container.innerHTML = '<p style="opacity:0.6; font-size:0.85rem; text-align:center; padding:16px;">No security or administrative activity recorded yet.</p>';
      return;
    }

    container.innerHTML = data.logs.map(log => {
      let actionBadgeColor = '#6366f1';
      if (log.action.includes('DELETE') || log.action.includes('DEPROVISION') || log.action.includes('PURGE')) actionBadgeColor = '#ef4444';
      else if (log.action.includes('UPDATE') || log.action.includes('EDIT')) actionBadgeColor = '#f59e0b';
      else if (log.action.includes('CREATE') || log.action.includes('PAYMENT') || log.action.includes('ENROLL')) actionBadgeColor = '#10b981';

      const timeFormatted = log.timestamp ? new Date(log.timestamp).toLocaleString() : 'Just now';

      return `
        <div style="display:flex; justify-content:space-between; align-items:center; background:rgba(255,255,255,0.02); padding:8px 12px; border-radius:8px; border:1px solid rgba(255,255,255,0.06); font-size:0.82rem;">
          <div style="display:flex; align-items:center; gap:10px;">
            <span style="background:rgba(255,255,255,0.08); font-weight:700; color:#e2e8f0; padding:2px 6px; border-radius:4px; font-size:0.74rem;">
              ${log.school_code}
            </span>
            <span style="font-weight:600; color:#fff;">${log.user_name}</span>
            <span style="font-size:0.74rem; padding:1px 6px; border-radius:4px; background:${actionBadgeColor}22; color:${actionBadgeColor}; font-weight:700;">
              ${log.action}
            </span>
            <span style="color:#94a3b8; font-size:0.8rem;">${log.details || ''}</span>
          </div>
          <div style="font-size:0.74rem; color:#64748b; white-space:nowrap; margin-left:12px;">
            ${timeFormatted}
          </div>
        </div>
      `;
    }).join('');

  } catch (err) {
    if (container) container.innerHTML = `<p style="color:#ef4444; font-size:0.85rem; padding:12px;">❌ Error loading audit stream: ${err.message}</p>`;
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

loadSuperAdminDashboard();

