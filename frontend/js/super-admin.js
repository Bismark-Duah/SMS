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

    // Populate KPIs
    document.getElementById('kpiTotalSchools').textContent = data.total_schools || 0;
    document.getElementById('kpiTotalStudents').textContent = data.total_students || 0;
    document.getElementById('kpiTotalUsers').textContent = data.total_users || 0;
    document.getElementById('kpiTotalFees').textContent = `GH₵ ${data.total_fees_collected ? data.total_fees_collected.toLocaleString('en-US', { minimumFractionDigits: 2 }) : '0.00'}`;

    const diag = data.diagnostics || {};
    document.getElementById('kpiDbSize').textContent = `${diag.db_size_mb || 0} MB`;
    document.getElementById('kpiBackupStatus').textContent = `Backups: ${diag.backups_count || 0} | Last: ${diag.last_backup_time || 'None'}`;

    // Mode Distribution
    const dist = data.mode_distribution || {};
    document.getElementById('modeDistributionLabel').innerHTML = `
      <span class="badge-mode badge-shs">SHS Only: ${dist.SHS_ONLY || 0}</span>
      <span class="badge-mode badge-basic">Basic Only: ${dist.BASIC_ONLY || 0}</span>
      <span class="badge-mode badge-combined">Combined: ${dist.COMBINED || 0}</span>
    `;

    // Render Schools Table
    const tbody = document.getElementById('schoolsTableBody');
    if (!data.schools || data.schools.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" style="padding:20px; text-align:center; opacity:0.7;">No registered schools found. Click "+ Register New School" to add one.</td></tr>';
      return;
    }

    const sortedSchools = [...data.schools].sort((a, b) => a.id - b.id);
    tbody.innerHTML = sortedSchools.map(s => {
      const statusClass = s.status === 'ACTIVE' ? 'status-active' : 'status-suspended';
      const boardingVal = s.boarding_type || 'BOARDING_AND_DAY';
      const boardingLabel = boardingVal === 'DAY_ONLY' ? 'Day Only' : (boardingVal === 'BOARDING_ONLY' ? 'Boarding Only' : 'Boarding & Day');

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
          <!-- 1. School Identity (Name + Code + ID) -->
          <td style="padding:10px 12px;">
            <div style="font-weight:700; font-size:0.92rem; color:#fff; margin-bottom:3px;">${s.name}</div>
            <div style="display:flex; align-items:center; gap:6px; font-size:0.75rem; color:#94a3b8;">
              <code style="background:rgba(255,255,255,0.08); padding:1px 5px; border-radius:4px; font-weight:700; color:#cbd5e1;">${s.code}</code>
              <span>•</span>
              <span style="font-weight:600;">ID: #${s.id}</span>
            </div>
          </td>

          <!-- 2. Academic & Boarding Config (Compact Stacked Selects) -->
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


  } catch (error) {
    console.error('Super-Admin dashboard error:', error);
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
  localStorage.setItem('school_id', String(schoolId));
  localStorage.setItem('school_name', schoolName);
  localStorage.setItem('school_mode', schoolMode);
  if (schoolCode) {
    localStorage.setItem('school_abbreviation', schoolCode);
  }
  localStorage.setItem('is_super_admin_viewing', 'true');
  window.location.href = 'dashboard.html';
};

window.toggleSchoolStatus = async function(schoolId, currentStatus) {
  const newStatus = currentStatus === 'ACTIVE' ? 'SUSPENDED' : 'ACTIVE';
  if (!confirm(`Are you sure you want to change school status to ${newStatus}?`)) return;

  try {
    const res = await fetch(`${API_BASE}/super-admin/schools/${schoolId}/status`, {
      method: 'PUT',
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ status: newStatus })
    });
    if (res.ok) {
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
  if (!confirm(`Change school mode to: ${profileName}?\n\nThis will immediately affect what features are available to this school's administrators and staff.`)) return;

  try {
    const res = await fetch(`${API_BASE}/super-admin/schools/${schoolId}/mode`, {
      method: 'PUT',
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ school_mode: newMode })
    });

    if (res.ok) {
      window.loadSuperAdminDashboard();
    } else {
      alert('Could not update school mode.');
      window.loadSuperAdminDashboard(); // Reset dropdown to actual value
    }
  } catch (err) {
    alert('Failed to update mode.');
    window.loadSuperAdminDashboard();
  }
};

window.changeSchoolBoarding = async function(schoolId, newBoarding) {
  const profileName = window.FeatureGate
    ? window.FeatureGate.getProfileName('COMBINED', newBoarding)
    : newBoarding;
  if (!confirm(`Change boarding status to: ${newBoarding === 'DAY_ONLY' ? 'Day Only' : 'Boarding & Day'}?\n\nThis affects Exeat Management, Houses & Dormitories, boarding staff roles, and boarding fee categories.`)) {
    window.loadSuperAdminDashboard(); // Reset dropdown
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/super-admin/schools/${schoolId}/boarding`, {
      method: 'PUT',
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ boarding_status: newBoarding })
    });

    if (res.ok) {
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

