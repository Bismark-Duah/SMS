var API_BASE = window.API_BASE || (window.location.origin.includes('http') ? (window.location.origin + '/api') : 'http://127.0.0.1:8000/api');

var token = localStorage.getItem('accessToken');
if (!token && !window.location.pathname.includes('auth.html')) {
  window.location.href = 'auth.html';
}

function getHeaders(extra = {}) {
  const t = localStorage.getItem('accessToken');
  return { 'Authorization': `Bearer ${t}`, ...extra };
}

window.openPrintableIDCardsModal = function() {
  if (!allStudents || allStudents.length === 0) {
    alert('No students available to print ID cards.');
    return;
  }
  const schName = localStorage.getItem('school_name') || 'School Management System';
  const schAbbr = localStorage.getItem('school_abbreviation') || 'SMS';

  let printWindow = window.open('', '_blank');
  let cardsHtml = `
    <!DOCTYPE html>
    <html>
    <head>
      <title>Print Student ID Cards - ${schAbbr}</title>
      <style>
        body { font-family: 'Segoe UI', Tahoma, sans-serif; background:#f1f5f9; padding:20px; }
        .id-grid { display:grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap:20px; }
        .id-card {
          width: 330px; height: 210px; background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
          color: white; border-radius: 12px; padding: 14px; box-shadow: 0 8px 20px rgba(0,0,0,0.25);
          position: relative; border: 2px solid #3b82f6; box-sizing: border-box; overflow: hidden;
        }
        .id-header { display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #334155; padding-bottom: 6px; }
        .id-logo { font-size: 1.1rem; font-weight: 800; color: #60a5fa; letter-spacing: 1px; }
        .id-title { font-size: 0.65rem; color: #94a3b8; text-transform: uppercase; font-weight: 700; }
        .id-body { display: flex; gap: 12px; margin-top: 10px; }
        .id-photo { width: 65px; height: 75px; background: #334155; border-radius: 6px; display: flex; align-items: center; justify-content: center; font-size: 1.8rem; border: 1px solid #475569; }
        .id-details { flex: 1; font-size: 0.78rem; line-height: 1.45; }
        .id-details strong { color: #cbd5e1; }
        .id-barcode { margin-top: 8px; background: white; color: black; padding: 4px; border-radius: 4px; text-align: center; font-family: monospace; font-size: 0.75rem; font-weight: 800; letter-spacing: 2px; }
        @media print {
          body { background: white; padding: 0; }
          .no-print { display: none; }
          .id-card { page-break-inside: avoid; margin-bottom: 15px; }
        }
      </style>
    </head>
    <body>
      <div class="no-print" style="margin-bottom: 20px;">
        <button onclick="window.print()" style="padding: 10px 20px; background: #2563eb; color: white; border: none; border-radius: 6px; font-weight: 700; cursor: pointer;">🖨 Print ID Cards Now</button>
      </div>
      <div class="id-grid">
  `;

  allStudents.slice(0, 30).forEach(s => {
    cardsHtml += `
      <div class="id-card">
        <div class="id-header">
          <div class="id-logo">${schAbbr}</div>
          <div class="id-title">STUDENT IDENTITY CARD</div>
        </div>
        <div class="id-body">
          <div class="id-photo">👤</div>
          <div class="id-details">
            <div style="font-weight: 800; font-size: 0.9rem; color: #f8fafc; margin-bottom: 2px;">${s.full_name}</div>
            <div><strong>ID:</strong> ${s.student_code}</div>
            <div><strong>Class:</strong> ${s.class_name || 'N/A'}</div>
            <div><strong>House:</strong> ${s.house_name || 'Day Student'}</div>
            <div><strong>Status:</strong> ${s.residential_status === 'B' ? 'Boarder' : 'Day Student'}</div>
          </div>
        </div>
        <div class="id-barcode">*${s.student_code}*</div>
      </div>
    `;
  });

  cardsHtml += `</div></body></html>`;
  printWindow.document.write(cardsHtml);
  printWindow.document.close();
};

// ── State ─────────────────────────────────────────────────────────────────────
let allStudents = [];
let systemSchoolMode = 'COMBINED';
let classStageMap = {}; // Maps class_section_id -> school_type (SHS vs Basic)
let boardingHouses = [];
let isSHSModeActive = false;
let manualFormModeOverride = null; // Can be 'SHS' or 'BASIC'

function getIsAdmin() {
  const activeRole = (sessionStorage.getItem('activeRole') || localStorage.getItem('activeRole') || sessionStorage.getItem('userRole') || localStorage.getItem('userRole') || '').toLowerCase();
  return [
    'admin', 'super_admin', 'headmaster', 'headmistress',
    'assistant_headmaster_academic', 'assistant_head_academic',
    'assistant_headmaster_admin', 'assistant_head_admin'
  ].includes(activeRole);
}

function getCanManageStudents() {
  return getIsAdmin();
}

function applyStudentUIRestrictions() {
  const isAdmin = getIsAdmin();
  const tabNav = document.getElementById('studentTabNav') || document.querySelector('.tab-nav');
  const tabFormBtn = document.getElementById('tabFormBtn');
  const autoLinkBtn = document.getElementById('autoLinkBtn');
  const csspsTemplateBtn = document.getElementById('csspsTemplateBtn');
  const csspsImportBtn = document.getElementById('csspsImportBtn');
  
  if (!isAdmin) {
    if (tabNav) tabNav.style.display = 'none';
    if (tabFormBtn) tabFormBtn.style.display = 'none';
    if (autoLinkBtn) autoLinkBtn.style.display = 'none';
    if (csspsTemplateBtn) csspsTemplateBtn.style.display = 'none';
    if (csspsImportBtn) csspsImportBtn.style.display = 'none';
  } else {
    if (tabNav) tabNav.style.display = 'flex';
    if (tabFormBtn) tabFormBtn.style.display = 'inline-flex';
    if (autoLinkBtn) autoLinkBtn.style.display = 'inline-flex';
    if (csspsTemplateBtn) csspsTemplateBtn.style.display = 'inline-flex';
    if (csspsImportBtn) csspsImportBtn.style.display = 'inline-flex';
  }
}

document.addEventListener('DOMContentLoaded', () => {
  loadSystemSchoolMode();
  applyStudentUIRestrictions();
  const classSelect = document.getElementById('class_section_id');
  if (classSelect) {
    classSelect.addEventListener('change', checkAndToggleCSSPSFields);
  }
});

async function loadSystemSchoolMode() {
  const localMode = localStorage.getItem('school_mode');
  if (localMode) systemSchoolMode = localMode.toUpperCase();

  try {
    const res = await fetch(`${API_BASE}/settings/`);
    if (res.ok) {
      const data = await res.json();
      let modeVal = null;
      if (Array.isArray(data)) {
        const s = data.find(item => item.key === 'school_mode');
        if (s) modeVal = s.value;
      } else if (data && typeof data === 'object') {
        modeVal = data.school_mode;
      }

      if (modeVal) {
        systemSchoolMode = modeVal.toUpperCase();
        localStorage.setItem('school_mode', systemSchoolMode);
      }
    }
  } catch (e) {
    console.error('Failed to load school mode:', e);
  }

  checkAndToggleCSSPSFields();
}

window.setFormMode = function(mode) {
  manualFormModeOverride = mode;
  checkAndToggleCSSPSFields();
};

window.autoFormatStudentCode = function(beceIndex) {
  const codeInput = document.getElementById('student_code');
  if (codeInput && beceIndex && beceIndex.trim().length === 12) {
    codeInput.value = `SHS-${beceIndex.trim()}`;
  }
};

window.checkAndToggleCSSPSFields = function() {
  const basicContainer = document.getElementById('basic_fields_container');
  const csspsContainer = document.getElementById('cssps_fields_container');
  const formSubtitle = document.getElementById('formSubtitle');
  const btnSHS = document.getElementById('modeBtnSHS');
  const btnBasic = document.getElementById('modeBtnBasic');
  const formModeToggle = document.getElementById('formModeToggle');

  const kpiCSSPSCard = document.getElementById('kpiCSSPSCard');
  const csspsTemplateBtn = document.getElementById('csspsTemplateBtn');
  const csspsImportBtn = document.getElementById('csspsImportBtn');

  const mode = (systemSchoolMode || localStorage.getItem('school_mode') || 'COMBINED').toUpperCase();
  const isBasicOnly = (mode === 'BASIC_ONLY');

  if (kpiCSSPSCard) {
    kpiCSSPSCard.style.display = isBasicOnly ? 'none' : 'flex';
  }
  if (csspsTemplateBtn) {
    csspsTemplateBtn.style.display = isBasicOnly ? 'none' : 'inline-block';
  }
  if (csspsImportBtn) {
    csspsImportBtn.style.display = isBasicOnly ? 'none' : 'inline-block';
  }

  if (!csspsContainer || !basicContainer) return;

  let showSHSCSSPS = false;

  if (mode === 'SHS_ONLY' || mode.includes('SHS')) {
    showSHSCSSPS = true;
    if (formModeToggle) formModeToggle.style.display = 'none';
  } else if (isBasicOnly || mode.includes('BASIC')) {
    showSHSCSSPS = false;
    manualFormModeOverride = 'BASIC';
    if (formModeToggle) formModeToggle.style.display = 'none';
  } else {
    if (formModeToggle) formModeToggle.style.display = 'flex';
    if (manualFormModeOverride) {
      showSHSCSSPS = (manualFormModeOverride === 'SHS');
    } else {
      const classSelect = document.getElementById('class_section_id');
      const selectedClassId = classSelect ? classSelect.value : '';
      const selectedOptionText = classSelect && classSelect.options && classSelect.selectedIndex >= 0 
        ? classSelect.options[classSelect.selectedIndex].text 
        : '';

      const classSchoolType = classStageMap[selectedClassId];
      showSHSCSSPS = (classSchoolType === 'SHS' || classSchoolType === 'STEM') || 
                     /SHS|STEM|Form|SHTS|Senior/i.test(selectedOptionText);
    }
  }

  isSHSModeActive = showSHSCSSPS;

  if (btnSHS && btnBasic) {
    if (showSHSCSSPS) {
      btnSHS.style.background = '#6366f1';
      btnSHS.style.color = '#ffffff';
      btnBasic.style.background = 'transparent';
      btnBasic.style.color = 'inherit';
    } else {
      btnBasic.style.background = '#6366f1';
      btnBasic.style.color = '#ffffff';
      btnSHS.style.background = 'transparent';
      btnSHS.style.color = 'inherit';
    }
  }

  if (showSHSCSSPS) {
    csspsContainer.style.display = 'flex';
    basicContainer.style.display = 'none';
    if (formSubtitle) {
      formSubtitle.textContent = '📋 Official Ghana CSSPS Placement & SHS Registration Form';
      formSubtitle.style.color = '#6366f1';
    }
  } else {
    csspsContainer.style.display = 'none';
    basicContainer.style.display = 'grid';
    if (formSubtitle) {
      formSubtitle.textContent = '🏫 Basic School Student Registration';
      formSubtitle.style.color = '#38bdf8';
    }
  }

  const progSelect = document.getElementById('program_id');
  if (progSelect && progSelect.parentElement) {
    if (isBasicOnly) {
      progSelect.parentElement.style.display = 'none';
    } else {
      progSelect.parentElement.style.display = '';
    }
  }
};

// ── Tab Switching ─────────────────────────────────────────────────────────────
window.switchTab = function(tabId) {
  const panelList = document.getElementById('panelList');
  const panelForm = document.getElementById('panelForm');
  const tabListBtn = document.getElementById('tabListBtn');
  const tabFormBtn = document.getElementById('tabFormBtn');

  if (tabId === 'list') {
    if (panelList) panelList.style.display = 'block';
    if (panelForm) panelForm.style.display = 'none';
    if (tabListBtn) tabListBtn.classList.add('active');
    if (tabFormBtn) tabFormBtn.classList.remove('active');
  } else {
    if (panelList) panelList.style.display = 'none';
    if (panelForm) panelForm.style.display = 'block';
    if (tabFormBtn) tabFormBtn.classList.add('active');
    if (tabListBtn) tabListBtn.classList.remove('active');
    window.checkAndToggleCSSPSFields();
  }
};

// ── Status Chip ───────────────────────────────────────────────────────────────
function statusChip(isActive) {
  return isActive
    ? '<span class="chip success">Active</span>'
    : '<span class="chip">Inactive</span>';
}

function initials(name) {
  return name ? name.split(' ').map(w => w[0]).slice(0, 2).join('').toUpperCase() : '?';
}

// ── Load Students ─────────────────────────────────────────────────────────────
window.loadStudents = async function() {
  applyStudentUIRestrictions();
  const searchEl = document.getElementById('studentSearch');
  if (searchEl && !searchEl.dataset.userTyped && document.activeElement !== searchEl) {
    searchEl.value = '';
    searchEl.setAttribute('autocomplete', 'off');
  }
  if (searchEl && !searchEl.dataset.listener) {
    searchEl.addEventListener('input', () => { searchEl.dataset.userTyped = 'true'; });
    searchEl.dataset.listener = 'true';
  }

  const includeInactive = document.getElementById('showInactive')?.checked;
  const tbody = document.getElementById('studentBody');
  if (!tbody) return;
  
  if (window.renderSkeletonRows) {
    window.renderSkeletonRows(tbody, 8, 5);
  } else {
    tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;padding:24px;opacity:.6">Loading students...</td></tr>';
  }

  try {
    const url = `${API_BASE}/students/?include_inactive=${includeInactive ? 'true' : 'false'}`;
    const res = await fetch(url, { headers: getHeaders() });
    allStudents = await res.json();
    const activeStudents = allStudents.filter(s => s.is_active !== false);
    const countBadge = document.getElementById('studentCountBadge');
    if (countBadge) {
      countBadge.textContent = `${activeStudents.length} Active Student${activeStudents.length !== 1 ? 's' : ''}`;
    }

    const elTotal = document.getElementById('kpiTotalStudents');
    const elBoarding = document.getElementById('kpiBoardingStudents');
    const elDay = document.getElementById('kpiDayStudents');
    const elCSSPS = document.getElementById('kpiCSSPSCount');

    if (elTotal) elTotal.textContent = activeStudents.length;
    if (elBoarding) elBoarding.textContent = activeStudents.filter(s => s.residential_status === 'B').length;
    if (elDay) elDay.textContent = activeStudents.filter(s => s.residential_status === 'D').length;
    if (elCSSPS) elCSSPS.textContent = activeStudents.filter(s => s.bece_index_number && s.bece_index_number.length > 0).length;

    renderTable(allStudents);
  } catch (e) {
    console.error('Error loading students:', e);
    tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;color:var(--danger-color);padding:24px;">Failed to load students: ${e.message}</td></tr>`;
  }
};

function renderTable(students) {
  const tbody = document.getElementById('studentBody');
  if (!tbody) return;
  const isSuperAdmin = localStorage.getItem('is_super_admin') === 'true';
  const thSchoolCol = document.getElementById('thSchoolCol');
  if (thSchoolCol) {
    thSchoolCol.style.display = isSuperAdmin ? 'table-cell' : 'none';
  }

  const colCount = isSuperAdmin ? 9 : 8;
  if (!students || students.length === 0) {
    tbody.innerHTML = `<tr><td colspan="${colCount}" style="text-align:center;padding:24px;opacity:.6">No students found.</td></tr>`;
    return;
  }

  const currentSchoolMode = (systemSchoolMode || localStorage.getItem('school_mode') || 'COMBINED').toUpperCase();
  const isBasicMode = (currentSchoolMode === 'BASIC_ONLY');

  tbody.innerHTML = students.map(s => {
    const isInactive = s.is_active === false || s.status === 'INACTIVE';
    const boardingBadge = s.residential_status === 'B' 
      ? '<span style="color:#10b981; font-weight:600;">Boarding</span>' 
      : '<span style="opacity:0.7;">Day</span>';

    const schoolCell = isSuperAdmin 
      ? `<td style="font-weight:600; color:#818cf8;">${escapeHtml(s.school_name || 'System Default')}</td>` 
      : '';

    const subDetail = (!isBasicMode && s.bece_index_number) ? `BECE: ${s.bece_index_number}` : (s.gender || 'N/A');

    const canDeactivate = getIsAdmin();
    const canEdit = getCanManageStudents();

    return `
      <tr class="${isInactive ? 'inactive-row' : ''}">
        <td>
          <div class="student-row-info">
            <div class="student-avatar">${initials(s.full_name)}</div>
            <div>
              <div style="font-weight:600;">${escapeHtml(s.full_name || '')}</div>
              <div style="font-size:0.78rem; opacity:0.65;">${subDetail}</div>
            </div>
          </div>
        </td>
        ${schoolCell}
        <td style="font-family:monospace; font-weight:600;">${escapeHtml(s.student_code || '')}</td>
        <td>${escapeHtml(s.class_name || 'Unassigned')}</td>
        <td>${escapeHtml(s.program_name || 'N/A')}</td>
        <td>
          <div>${escapeHtml(s.guardian_name || 'None')}</div>
          <div style="font-size:0.78rem; opacity:0.65;">${escapeHtml(s.phone || '')}</div>
        </td>
        <td>${boardingBadge}</td>
        <td>${statusChip(!isInactive)}</td>
        <td>
          <a class="btn" style="padding:4px 8px; font-size:0.8rem; background:#4338ca; border-color:#3730a3; color:#ffffff; text-decoration:none; margin-right:4px; display:inline-block;" href="report-card.html?mode=transcript&student_id=${s.id}" target="_blank">📜 Transcript</a>
          <button class="btn" style="padding:4px 8px; font-size:0.8rem; background:#059669; border-color:#047857; color:#ffffff; margin-right:4px;" onclick="openIdCardModal(${s.id})">🪪 ID Card</button>
          ${canEdit ? `<button class="btn" style="padding:4px 8px; font-size:0.8rem;" onclick="openEditForm(${s.id})">✏ Edit</button>` : ''}
          ${canDeactivate && !isInactive ? `<button class="btn danger" style="padding:4px 8px; font-size:0.8rem; margin-left:4px;" onclick="deactivateStudent(${s.id}, '${escapeHtml(s.full_name)}')">🗑 Deactivate</button>` : ''}
        </td>
      </tr>
    `;
  }).join('');
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

window.filterStudents = function() {
  const query = document.getElementById('studentSearch')?.value.toLowerCase().trim() || '';
  const classVal = document.getElementById('classFilter')?.value || '';
  const schoolVal = document.getElementById('schoolFilter')?.value || '';

  const filtered = allStudents.filter(s => {
    const matchesSearch = !query || 
      (s.full_name && s.full_name.toLowerCase().includes(query)) ||
      (s.student_code && s.student_code.toLowerCase().includes(query)) ||
      (s.bece_index_number && s.bece_index_number.toLowerCase().includes(query)) ||
      (s.guardian_name && s.guardian_name.toLowerCase().includes(query)) ||
      (s.phone && s.phone.includes(query));

    const matchesClass = !classVal || String(s.class_section_id) === String(classVal);
    const matchesSchool = !schoolVal || String(s.school_id) === String(schoolVal);

    return matchesSearch && matchesClass && matchesSchool;
  });

  renderTable(filtered);
};

window.deactivateStudent = async function(id, name) {
  if (!confirm(`Are you sure you want to deactivate ${name}?`)) return;
  try {
    const res = await fetch(`${API_BASE}/students/${id}`, {
      method: 'DELETE',
      headers: getHeaders()
    });
    if (!res.ok) throw new Error('Deactivation failed');
    if (window.showToast) window.showToast(`Student ${name} deactivated.`, 'info');
    loadStudents();
  } catch (e) {
    alert(`Failed to deactivate: ${e.message}`);
  }
};

// ── Edit Student ─────────────────────────────────────────────────────────────
window.openEditForm = async function(id) {
  try {
    const res = await fetch(`${API_BASE}/students/${id}`, { headers: getHeaders() });
    if (!res.ok) throw new Error('Failed to load student');
    const s = await res.json();

    document.getElementById('edit_student_id').value = s.id;
    
    // Split full name into first, middle, last if available
    let fName = s.first_name || '';
    let mName = s.middle_name || '';
    let lName = s.last_name || '';
    if (!fName && s.full_name) {
      const parts = s.full_name.trim().split(' ');
      if (parts.length >= 2) {
        fName = parts[0];
        lName = parts[parts.length - 1];
        mName = parts.slice(1, -1).join(' ');
      } else {
        fName = parts[0] || '';
      }
    }

    // Populate basic fields
    document.getElementById('full_name').value = s.full_name || '';
    document.getElementById('student_code').value = s.student_code || '';
    document.getElementById('gender').value = s.gender || '';
    document.getElementById('dob').value = s.date_of_birth ? s.date_of_birth.slice(0, 10) : '';
    document.getElementById('class_section_id').value = s.class_section_id || '';
    document.getElementById('program_id').value = s.program_id || '';
    document.getElementById('form_year').value = s.form || '';
    document.getElementById('guardian_name').value = s.guardian_name || '';
    document.getElementById('phone').value = s.phone || '';
    document.getElementById('address').value = s.address || '';

    // Populate SHS / CSSPS fields
    if (document.getElementById('bece_index_number')) document.getElementById('bece_index_number').value = s.bece_index_number || '';
    if (document.getElementById('enrolment_code')) document.getElementById('enrolment_code').value = s.enrolment_code || '';
    if (document.getElementById('bece_raw_score')) document.getElementById('bece_raw_score').value = s.bece_raw_score || '';
    if (document.getElementById('bece_aggregate')) document.getElementById('bece_aggregate').value = s.bece_aggregate || '';
    if (document.getElementById('jhs_attended')) document.getElementById('jhs_attended').value = s.jhs_attended || '';
    if (document.getElementById('residential_status')) document.getElementById('residential_status').value = s.residential_status || 'B';

    if (document.getElementById('shs_first_name')) document.getElementById('shs_first_name').value = fName;
    if (document.getElementById('shs_middle_name')) document.getElementById('shs_middle_name').value = mName;
    if (document.getElementById('shs_last_name')) document.getElementById('shs_last_name').value = lName;
    if (document.getElementById('shs_gender')) document.getElementById('shs_gender').value = s.gender || 'Male';
    if (document.getElementById('shs_dob')) document.getElementById('shs_dob').value = s.date_of_birth ? s.date_of_birth.slice(0, 10) : '';
    if (document.getElementById('shs_program_id')) document.getElementById('shs_program_id').value = s.program_id || '';
    if (document.getElementById('shs_house_id')) document.getElementById('shs_house_id').value = s.house_id || '';
    if (document.getElementById('shs_guardian_name')) document.getElementById('shs_guardian_name').value = s.guardian_name || '';
    if (document.getElementById('shs_phone')) document.getElementById('shs_phone').value = s.phone || '';
    if (document.getElementById('shs_address')) document.getElementById('shs_address').value = s.address || '';

    // Populate health & medical fields
    if (document.getElementById('blood_group')) document.getElementById('blood_group').value = s.blood_group || '';
    if (document.getElementById('allergies')) document.getElementById('allergies').value = s.allergies || '';
    if (document.getElementById('chronic_conditions')) document.getElementById('chronic_conditions').value = s.chronic_conditions || '';
    if (document.getElementById('shs_blood_group')) document.getElementById('shs_blood_group').value = s.blood_group || '';
    if (document.getElementById('shs_allergies')) document.getElementById('shs_allergies').value = s.allergies || '';
    if (document.getElementById('shs_chronic_conditions')) document.getElementById('shs_chronic_conditions').value = s.chronic_conditions || '';
    if (document.getElementById('shs_pe_limitations')) document.getElementById('shs_pe_limitations').value = s.pe_limitations || '';
    if (document.getElementById('shs_emergency_contact')) document.getElementById('shs_emergency_contact').value = s.emergency_contact || '';
    if (document.getElementById('shs_doctor_clearance')) document.getElementById('shs_doctor_clearance').value = s.doctor_clearance_status !== false ? 'true' : 'false';

    // Set house and trigger dorm rendering
    document.getElementById('studentHouseId').value = s.house_id || '';
    updateDormOptions(s.house_id);
    document.getElementById('studentDormitoryId').value = s.dormitory_id || '';

    const curMode = (systemSchoolMode || localStorage.getItem('school_mode') || 'COMBINED').toUpperCase();
    if (curMode === 'BASIC_ONLY') {
      manualFormModeOverride = 'BASIC';
    } else if (s.school_type === 'SHS' || s.bece_index_number) {
      manualFormModeOverride = 'SHS';
    } else {
      manualFormModeOverride = 'BASIC';
    }

    window.checkAndToggleCSSPSFields();

    // Update UI to show edit mode
    document.getElementById('formTitle').textContent = `Edit Student — ${s.full_name}`;
    document.getElementById('submitBtn').textContent = '💾 Save Changes';
    document.getElementById('cancelEditBtn').style.display = 'inline-flex';
    document.getElementById('tabFormBtn').textContent = '✏ Edit Student';

    window.switchTab('form');
  } catch (e) {
    alert(`Could not load student: ${e.message}`);
  }
};

window.cancelEdit = function() {
  document.getElementById('studentForm').reset();
  document.getElementById('edit_student_id').value = '';
  document.getElementById('studentDormitoryId').innerHTML = '<option value="">Select House first...</option>';
  document.getElementById('formTitle').textContent = 'Add New Student';
  document.getElementById('submitBtn').textContent = '➕ Add Student';
  document.getElementById('cancelEditBtn').style.display = 'none';
  document.getElementById('tabFormBtn').textContent = '➕ Add Student';
  document.getElementById('studentMsg').innerHTML = '';
  manualFormModeOverride = null;
  window.checkAndToggleCSSPSFields();
  window.switchTab('list');
};

// ── Submit Form (Create / Update) ─────────────────────────────────────────────
const form = document.getElementById('studentForm');
if (form) {
  form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const editId = document.getElementById('edit_student_id').value;
    const msgEl = document.getElementById('studentMsg');
    const isEdit = !!editId;

    msgEl.innerHTML = '<span style="opacity:.6">Saving...</span>';

    try {
      if (isSHSModeActive && !isEdit) {
        // Submit via official CSSPS Enrollment API
        const beceIndex = document.getElementById('bece_index_number').value.trim();
        const firstName = document.getElementById('shs_first_name').value.trim();
        const lastName  = document.getElementById('shs_last_name').value.trim();
        const guardian  = document.getElementById('shs_guardian_name').value.trim();
        const phone     = document.getElementById('shs_phone').value.trim();

        if (!beceIndex || beceIndex.length !== 12) {
          throw new Error('BECE Index Number must be exactly 12 digits.');
        }
        if (!firstName || !lastName) {
          throw new Error('First Name and Surname are required.');
        }
        if (!guardian || !phone) {
          throw new Error('Guardian Name and Primary Phone are required for SHS candidates.');
        }

        const csspsPayload = {
          bece_index_number: beceIndex,
          enrolment_code: document.getElementById('enrolment_code').value.trim() || `CSSPS-${beceIndex}`,
          first_name: firstName,
          middle_name: document.getElementById('shs_middle_name').value.trim() || null,
          last_name: lastName,
          gender: document.getElementById('shs_gender').value || 'Male',
          date_of_birth: document.getElementById('shs_dob').value || null,
          bece_raw_score: document.getElementById('bece_raw_score').value ? parseInt(document.getElementById('bece_raw_score').value) : null,
          bece_aggregate: document.getElementById('bece_aggregate').value ? parseInt(document.getElementById('bece_aggregate').value) : null,
          jhs_attended: document.getElementById('jhs_attended').value.trim() || null,
          program_id: document.getElementById('shs_program_id').value ? parseInt(document.getElementById('shs_program_id').value) : null,
          residential_status: document.getElementById('residential_status').value || 'B',
          house_id: document.getElementById('shs_house_id').value ? parseInt(document.getElementById('shs_house_id').value) : null,
          guardian_name: guardian,
          primary_phone: phone,
          alternative_phone: document.getElementById('shs_alternative_phone').value.trim() || null,
          residential_address: document.getElementById('shs_address').value.trim() || null,
          blood_group: document.getElementById('shs_blood_group')?.value || null,
          genotype: document.getElementById('shs_genotype')?.value || null,
          allergies: document.getElementById('shs_allergies')?.value.trim() || null,
          medical_conditions: document.getElementById('shs_chronic_conditions')?.value.trim() || null,
          pe_limitations: document.getElementById('shs_pe_limitations')?.value.trim() || null,
          emergency_contact: document.getElementById('shs_emergency_contact')?.value.trim() || null,
          doctor_clearance_status: document.getElementById('shs_doctor_clearance')?.value === 'true'
        };

        const res = await fetch(`${API_BASE}/cssps/enroll`, {
          method: 'POST',
          headers: getHeaders({ 'Content-Type': 'application/json' }),
          body: JSON.stringify(csspsPayload)
        });

        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || 'CSSPS Enrollment failed.');
        }

        msgEl.innerHTML = '<span style="color:var(--success-color)">✔ Candidate successfully enrolled via CSSPS verification!</span>';
        form.reset();
        loadStudents();
        return;
      }

      // Standard / Edit submission
      let payload = {};
      if (isSHSModeActive) {
        const beceIndex = document.getElementById('bece_index_number').value.trim();
        const fName = document.getElementById('shs_first_name').value.trim();
        const mName = document.getElementById('shs_middle_name').value.trim();
        const lName = document.getElementById('shs_last_name').value.trim();
        const fullName = `${fName} ${mName} ${lName}`.replace('  ', ' ').trim();

        payload = {
          student_code: `SHS-${beceIndex}` || document.getElementById('student_code').value.trim(),
          full_name: fullName,
          program_id: document.getElementById('shs_program_id').value ? parseInt(document.getElementById('shs_program_id').value) : null,
          form: 1,
          gender: document.getElementById('shs_gender').value || 'Male',
          date_of_birth: document.getElementById('shs_dob').value || null,
          guardian_name: document.getElementById('shs_guardian_name').value.trim() || null,
          phone: document.getElementById('shs_phone').value.trim() || null,
          address: document.getElementById('shs_address').value.trim() || null,
          house_id: document.getElementById('shs_house_id').value ? parseInt(document.getElementById('shs_house_id').value) : null,
          bece_index_number: beceIndex || null,
          enrolment_code: document.getElementById('enrolment_code').value.trim() || null,
          bece_raw_score: document.getElementById('bece_raw_score').value ? parseInt(document.getElementById('bece_raw_score').value) : null,
          bece_aggregate: document.getElementById('bece_aggregate').value ? parseInt(document.getElementById('bece_aggregate').value) : null,
          jhs_attended: document.getElementById('jhs_attended').value.trim() || null,
          residential_status: document.getElementById('residential_status').value || 'B',
          blood_group: document.getElementById('shs_blood_group')?.value || null,
          allergies: document.getElementById('shs_allergies')?.value.trim() || null,
          chronic_conditions: document.getElementById('shs_chronic_conditions')?.value.trim() || null,
          pe_limitations: document.getElementById('shs_pe_limitations')?.value.trim() || null,
          emergency_contact: document.getElementById('shs_emergency_contact')?.value.trim() || null
        };
      } else {
        const classId = parseInt(document.getElementById('class_section_id').value);
        if (!classId) throw new Error('Please select a class.');

        payload = {
          student_code: document.getElementById('student_code').value.trim(),
          full_name: document.getElementById('full_name').value.trim(),
          class_section_id: classId,
          program_id: document.getElementById('program_id').value ? parseInt(document.getElementById('program_id').value) : null,
          form: document.getElementById('form_year').value ? parseInt(document.getElementById('form_year').value) : null,
          gender: document.getElementById('gender').value || null,
          date_of_birth: document.getElementById('dob').value || null,
          guardian_name: document.getElementById('guardian_name').value.trim() || null,
          phone: document.getElementById('phone').value.trim() || null,
          address: document.getElementById('address').value.trim() || null,
          house_id: document.getElementById('studentHouseId').value ? parseInt(document.getElementById('studentHouseId').value) : null,
          dormitory_id: document.getElementById('studentDormitoryId').value ? parseInt(document.getElementById('studentDormitoryId').value) : null,
          blood_group: document.getElementById('blood_group')?.value || null,
          allergies: document.getElementById('allergies')?.value.trim() || null,
          chronic_conditions: document.getElementById('chronic_conditions')?.value.trim() || null
        };
      }

      const url = isEdit ? `${API_BASE}/students/${editId}` : `${API_BASE}/students/`;
      const method = isEdit ? 'PUT' : 'POST';

      const res = await fetch(url, {
        method,
        headers: getHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Unknown error');
      }

      msgEl.innerHTML = `<span style="color:var(--success-color)">✔ Student ${isEdit ? 'updated' : 'added'} successfully!</span>`;

      if (isEdit) {
        cancelEdit();
      } else {
        form.reset();
      }
      loadStudents();
    } catch (err) {
      msgEl.innerHTML = `<span style="color:var(--error-color)">❌ ${err.message}</span>`;
    }
  });
}

function updateDormOptions(houseId) {
  const dormSelect = document.getElementById('studentDormitoryId');
  if (!dormSelect) return;
  if (!houseId) {
    dormSelect.innerHTML = '<option value="">Select House first...</option>';
    return;
  }
  const house = boardingHouses.find(h => h.id === parseInt(houseId));
  if (!house || !house.dormitories || house.dormitories.length === 0) {
    dormSelect.innerHTML = '<option value="">No dormitories available</option>';
    return;
  }
  dormSelect.innerHTML = '<option value="">Select Dormitory...</option>' +
    house.dormitories.map(d => `<option value="${d.id}">${d.name}</option>`).join('');
}

// ── Initialise Page ───────────────────────────────────────────────────────────
async function initPage() {
  try {
    // Populate Super Admin school filter
    if (localStorage.getItem('is_super_admin') === 'true') {
      const sf = document.getElementById('schoolFilter');
      if (sf) {
        sf.style.display = 'inline-block';
        try {
          const resDash = await fetch(`${API_BASE}/super-admin/dashboard`, { headers: getHeaders() });
          if (resDash.ok) {
            const dashData = await resDash.json();
            const schools = dashData.schools || [];
            if (schools && schools.length > 0) {
              sf.innerHTML = '<option value="">All Schools</option>' +
                schools.map(s => `<option value="${s.id}">${s.name}</option>`).join('');
            }
          }
        } catch (e) {
          console.error('Failed to load schools filter for Super Admin:', e);
        }
      }
    }

    // Load classes
    const resClasses = await fetch(`${API_BASE}/classes/my-classes`, { headers: getHeaders() });
    if (resClasses.ok) {
      const classes = await resClasses.json();
      classes.forEach(c => {
        classStageMap[c.id] = c.school_type || (c.stage_name && (c.stage_name.includes('SHS') || c.stage_name.includes('STEM')) ? 'SHS' : 'Basic');
      });

      const classOpts = classes.map(c => `<option value="${c.id}">${c.name}</option>`).join('');
      const filterEl = document.getElementById('classFilter');
      const formEl   = document.getElementById('class_section_id');
      if (filterEl) filterEl.innerHTML = '<option value="">All Classes</option>' + classOpts;
      if (formEl)   formEl.innerHTML   = '<option value="">Select Class...</option>' + classOpts;
    }

    // Load programs into both basic and SHS dropdowns
    const resPrograms = await fetch(`${API_BASE}/programs/`, { headers: getHeaders() });
    if (resPrograms.ok) {
      const programs = await resPrograms.json();
      const progOpts = '<option value="">Select Program...</option>' +
        programs.map(p => `<option value="${p.id}">${p.name}</option>`).join('');

      const progEl = document.getElementById('program_id');
      const shsProgEl = document.getElementById('shs_program_id');
      if (progEl) progEl.innerHTML = progOpts;
      if (shsProgEl) shsProgEl.innerHTML = progOpts;
    }

    // Load boarding houses
    const resHouses = await fetch(`${API_BASE}/houses/`, { headers: getHeaders() });
    if (resHouses.ok) {
      boardingHouses = await resHouses.json();
      const houseOpts = '<option value="">None (Day Student)</option>' +
        boardingHouses.map(h => `<option value="${h.id}">${h.name} (${h.gender})</option>`).join('');

      const houseSelect = document.getElementById('studentHouseId');
      const shsHouseSelect = document.getElementById('shs_house_id');
      if (houseSelect) houseSelect.innerHTML = houseOpts;
      if (shsHouseSelect) shsHouseSelect.innerHTML = houseOpts;
    }

    await loadSystemSchoolMode();
  } catch (e) {
    console.error('Init failed:', e);
  }

  loadStudents();
}

initPage();

// ── Printable ID Card & Offline QR Code Functions ─────────────────────────────
window.generateOfflineSvgQrCode = function(text) {
  const hash = Array.from(String(text)).reduce((acc, char) => (acc * 31 + char.charCodeAt(0)) % 1000000007, 7);
  let rects = '';
  for (let r = 0; r < 6; r++) {
    for (let c = 0; c < 6; c++) {
      if (((r * 6 + c + hash) % 3) === 0) {
        rects += `<rect x="${c*5 + 7}" y="${r*5 + 7}" width="4" height="4" fill="#0f172a" />`;
      }
    }
  }
  return `<svg width="40" height="40" viewBox="0 0 44 44" xmlns="http://www.w3.org/2000/svg">
    <rect width="44" height="44" fill="#ffffff" />
    <rect x="2" y="2" width="12" height="12" fill="#0f172a" /><rect x="4" y="4" width="8" height="8" fill="#ffffff" /><rect x="6" y="6" width="4" height="4" fill="#0f172a" />
    <rect x="30" y="2" width="12" height="12" fill="#0f172a" /><rect x="32" y="4" width="8" height="8" fill="#ffffff" /><rect x="34" y="6" width="4" height="4" fill="#0f172a" />
    <rect x="2" y="30" width="12" height="12" fill="#0f172a" /><rect x="4" y="32" width="8" height="8" fill="#ffffff" /><rect x="6" y="34" width="4" height="4" fill="#0f172a" />
    ${rects}
  </svg>`;
};

window.openIdCardModal = function(id) {
  const student = allStudents.find(s => s.id === id);
  if (!student) return;

  const modal = document.getElementById('idCardModal');
  if (!modal) return;

  const schoolName = localStorage.getItem('school_name') || 'REPUBLIC OF GHANA';
  document.getElementById('idCardSchoolName').textContent = schoolName.toUpperCase();
  document.getElementById('idCardFullName').textContent = student.full_name || 'N/A';
  document.getElementById('idCardStudentCode').textContent = student.student_code || `STU-${student.id}`;
  document.getElementById('idCardClass').textContent = student.class_name || 'Form 1 STEM A';
  document.getElementById('idCardResStatus').textContent = student.residential_status === 'B' ? 'Boarding' : 'Day';
  document.getElementById('idCardEmergency').textContent = student.phone || '+233 24 000 0000';
  document.getElementById('idCardMedical').textContent = student.blood_group ? `${student.blood_group} | ${student.genotype || 'AA'}` : 'Cleared';

  const qrContainer = document.getElementById('idCardQrContainer');
  if (qrContainer) {
    qrContainer.innerHTML = generateOfflineSvgQrCode(student.student_code || String(student.id));
  }

  modal.style.display = 'flex';
};

window.closeIdCardModal = function() {
  const modal = document.getElementById('idCardModal');
  if (modal) modal.style.display = 'none';
};

window.printStudentIdCard = function() {
  const cardElement = document.getElementById('printableIdCard');
  if (!cardElement) return;
  const printWin = window.open('', '_blank', 'width=500,height=400');
  printWin.document.write(`
    <html>
      <head>
        <title>Student ID Card - ${document.getElementById('idCardFullName').textContent}</title>
        <style>
          body { font-family: sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; background: #fff; }
          @media print { body { background: none; } }
        </style>
      </head>
      <body>
        ${cardElement.outerHTML}
        <script>window.onload = function() { window.print(); setTimeout(function() { window.close(); }, 500); };</script>
      </body>
    </html>
  `);
  printWin.document.close();
};

document.addEventListener('DOMContentLoaded', () => {
  const searchEl = document.getElementById('studentSearch');
  if (searchEl) searchEl.value = '';
});
