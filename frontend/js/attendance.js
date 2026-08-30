const API_BASE = window.API_BASE || (window.location.origin.includes('http') ? (window.location.origin + '/api') : 'http://127.0.0.1:8000/api');

const token = localStorage.getItem('accessToken');
if (!token) window.location.href = 'auth.html';

function getHeaders(extra = {}) {
  return { 'Authorization': `Bearer ${token}`, ...extra };
}

function getActiveRole() {
  return (sessionStorage.getItem('activeRole') || localStorage.getItem('activeRole') || sessionStorage.getItem('userRole') || localStorage.getItem('userRole') || '').toLowerCase();
}

function getUserRoles() {
  try {
    const raw = sessionStorage.getItem('userRoles') || localStorage.getItem('userRoles');
    if (raw) return JSON.parse(raw);
    const primary = getActiveRole();
    return primary ? [primary] : [];
  } catch { return []; }
}

const ADMIN_ROLES = new Set([
  'admin', 'super_admin', 'headmaster', 'headmistress',
  'assistant_headmaster_academic', 'assistant_head_academic',
  'assistant_headmaster_admin', 'assistant_head_admin',
  'assistant_headmaster_domestic', 'assistant_head_domestic',
]);

const DOMESTIC_STAFF_ROLES = new Set([
  'admin', 'super_admin', 'headmaster', 'headmistress',
  'assistant_headmaster_domestic', 'assistant_head_domestic',
  'senior_housemaster', 'senior_housemistress', 'senior_house_master', 'senior_house_mistress',
  'house_master', 'house_mistress', 'assistant_house_master', 'assistant_house_mistress'
]);

function isDomesticStaff() {
  const active = getActiveRole();
  if (DOMESTIC_STAFF_ROLES.has(active)) return true;
  return getUserRoles().some(r => DOMESTIC_STAFF_ROLES.has(String(r).toLowerCase()));
}

function isAdmin() {
  const active = getActiveRole();
  if (ADMIN_ROLES.has(active)) return true;
  return getUserRoles().some(r => ADMIN_ROLES.has(String(r).toLowerCase()));
}
function isFormMaster() {
  const active = getActiveRole();
  if (['form_master', 'form_mistress'].includes(active)) return true;
  return getUserRoles().some(r => ['form_master', 'form_mistress'].includes(String(r).toLowerCase()));
}
function isSubjectTeacher() {
  const active = getActiveRole();
  if (active === 'teacher') return true;
  return getUserRoles().some(r => String(r).toLowerCase() === 'teacher');
}

// ── Tab Switching ──────────────────────────────────────────────────────────────
let activeTab = null;
function switchTab(tabId) {
  document.querySelectorAll('.tab-panel').forEach(p => p.style.display = 'none');
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  const panel = document.getElementById('panel' + tabId.charAt(0).toUpperCase() + tabId.slice(1));
  if (panel) panel.style.display = 'block';
  const btn = document.getElementById('tabBtn_' + tabId);
  if (btn) btn.classList.add('active');
  activeTab = tabId;
}

// ── Build Tab Nav By Role ──────────────────────────────────────────────────────
async function buildTabNav(formClassIds) {
  const nav = document.getElementById('tabNav');
  const tabs = [];

  const canMarkRegister = isAdmin() || formClassIds.length > 0;
  if (canMarkRegister) {
    tabs.push({ id: 'mark', label: '📋 Daily Register' });
  }
  if (isDomesticStaff()) {
    tabs.push({ id: 'houseRoll', label: '🏠 House & Dorm Roll Call' });
  }
  if (isAdmin() || isDomesticStaff()) {
    tabs.push({ id: 'audit', label: '🔍 Truancy Audit' });
  }
  if (isAdmin() || isSubjectTeacher() || isFormMaster()) {
    tabs.push({ id: 'period', label: '🚨 Period Absence Log' });
  }
  tabs.push({ id: 'scanner', label: '📷 Barcode / QR Scanner' });
  tabs.push({ id: 'records', label: '📊 Attendance Records' });

  nav.innerHTML = tabs.map(t =>
    `<button class="btn tab-btn" id="tabBtn_${t.id}" onclick="switchTab('${t.id}')">${t.label}</button>`
  ).join('');

  // Default active tab based on persona
  const activeRole = getActiveRole();
  if (DOMESTIC_STAFF_ROLES.has(activeRole) && !['admin', 'super_admin'].includes(activeRole)) {
    switchTab('houseRoll');
  } else if (tabs.length > 0) {
    switchTab(tabs[0].id);
  }
}

// ── Status Chip HTML ───────────────────────────────────────────────────────────
function statusChip(status) {
  const map = { Present: 'success', Absent: 'danger', Late: 'warning', Excused: 'info' };
  return `<span class="chip ${map[status] || ''}">${status}</span>`;
}

function typeChip(type) {
  if (type === 'period') return `<span class="chip warning" style="font-size:.75rem;">Period</span>`;
  return `<span class="chip info" style="font-size:.75rem;">Daily</span>`;
}

// ─────────────────────────────────────────────────────────────────────────────
// PANEL 1: Daily Class Register (Form Master / Admin)
// ─────────────────────────────────────────────────────────────────────────────
async function initDailyRegister() {
  const today = new Date().toISOString().slice(0, 10);
  document.getElementById('mark_date').value = today;

  try {
    const res = await fetch(`${API_BASE}/classes/my-form-classes`, { headers: getHeaders() });
    const classes = await res.json();

    if (!Array.isArray(classes) || classes.length === 0) {
      // Show info banner — no form master assignment
      const banner = document.getElementById('registerBanner');
      if (banner) banner.style.display = 'block';
      document.getElementById('mark_class_id').disabled = true;
    } else {
      const banner = document.getElementById('registerBanner');
      if (banner) banner.style.display = 'none';
      const select = document.getElementById('mark_class_id');
      if (select) {
        select.disabled = false;
        const opts = classes.map(c => `<option value="${c.id}">${c.name}</option>`).join('');
        select.innerHTML = '<option value="">Select Class...</option>' + opts;
      }
    }
  } catch (e) {
    console.error('Failed to load form classes:', e);
  }
}

async function loadClassRoll() {
  const classId = document.getElementById('mark_class_id').value;
  const date    = document.getElementById('mark_date').value;
  const rollMsg = document.getElementById('rollMsg');

  if (!classId || !date) {
    rollMsg.innerHTML = '<span style="color:var(--error-color)">Please select a class and date.</span>';
    return;
  }

  rollMsg.innerHTML = '<span style="opacity:.6">Loading students...</span>';

  try {
    const res = await fetch(`${API_BASE}/students/?class_id=${classId}`, { headers: getHeaders() });
    const allStudents = await res.json();
    const students = allStudents.filter(s => s.class_section_id == classId && s.is_active !== false);

    if (students.length === 0) {
      rollMsg.innerHTML = '<span style="opacity:.6">No active students found in this class.</span>';
      document.getElementById('rollCard').style.display = 'none';
      return;
    }

    // Pre-fill from existing daily records
    const attRes = await fetch(
      `${API_BASE}/attendance/class/${classId}?date_from=${date}&date_to=${date}`,
      { headers: getHeaders() }
    );
    const existing = attRes.ok ? await attRes.json() : [];
    const existingMap = {};
    existing.filter(r => !r.attendance_type || r.attendance_type === 'daily').forEach(r => { existingMap[r.student_id] = r.status; });

    const className = document.getElementById('mark_class_id').selectedOptions[0]?.text || '';
    document.getElementById('rollTitle').textContent = `${className} — ${date}`;
    document.getElementById('rollSubtitle').textContent = `${students.length} student${students.length !== 1 ? 's' : ''}`;

    document.getElementById('rollBody').innerHTML = students.map((s, i) => {
      const currentStatus = existingMap[s.id] || 'Present';
      return `
        <tr data-student-id="${s.id}" class="attendance-row">
          <td>${i + 1}</td>
          <td><strong>${escapeHtml(s.student_code)}</strong></td>
          <td style="font-weight:600;">${escapeHtml(s.full_name)}</td>
          <td>
            <input type="hidden" class="status-value" data-student-id="${s.id}" value="${currentStatus}">
            <div class="att-toggle-group" data-student-id="${s.id}">
              <button type="button" class="att-btn present ${currentStatus === 'Present' ? 'active' : ''}" onclick="setRowStatus(${s.id}, 'Present')">P</button>
              <button type="button" class="att-btn absent ${currentStatus === 'Absent' ? 'active' : ''}" onclick="setRowStatus(${s.id}, 'Absent')">A</button>
              <button type="button" class="att-btn late ${currentStatus === 'Late' ? 'active' : ''}" onclick="setRowStatus(${s.id}, 'Late')">L</button>
              <button type="button" class="att-btn excused ${currentStatus === 'Excused' ? 'active' : ''}" onclick="setRowStatus(${s.id}, 'Excused')">E</button>
            </div>
          </td>
        </tr>`;
    }).join('');

    document.getElementById('rollCard').style.display = 'block';
    updateAttendanceTally();
    rollMsg.innerHTML = '';
    document.getElementById('submitMsg').innerHTML = '';
  } catch (e) {
    rollMsg.innerHTML = `<span style="color:var(--error-color)">Error: ${e.message}</span>`;
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function setRowStatus(studentId, status) {
  const hiddenInput = document.querySelector(`.status-value[data-student-id="${studentId}"]`);
  if (hiddenInput) hiddenInput.value = status;

  const toggleGroup = document.querySelector(`.att-toggle-group[data-student-id="${studentId}"]`);
  if (toggleGroup) {
    toggleGroup.querySelectorAll('.att-btn').forEach(btn => btn.classList.remove('active'));
    const targetBtn = toggleGroup.querySelector(`.att-btn.${status.toLowerCase()}`);
    if (targetBtn) targetBtn.classList.add('active');
  }

  updateAttendanceTally();
}

function updateAttendanceTally() {
  const values = Array.from(document.querySelectorAll('.status-value')).map(el => el.value);
  const total = values.length;
  if (total === 0) return;

  const present = values.filter(v => v === 'Present').length;
  const absent  = values.filter(v => v === 'Absent').length;
  const late    = values.filter(v => v === 'Late').length;
  const excused = values.filter(v => v === 'Excused').length;

  const pct = Math.round(((present + late) / total) * 100);

  const elP = document.getElementById('tallyPresent');
  const elA = document.getElementById('tallyAbsent');
  const elL = document.getElementById('tallyLate');
  const elE = document.getElementById('tallyExcused');
  const elPct = document.getElementById('tallyPct');

  if (elP) elP.textContent = present;
  if (elA) elA.textContent = absent;
  if (elL) elL.textContent = late;
  if (elE) elE.textContent = excused;
  if (elPct) elPct.textContent = `${pct}% Present`;
}

function markAll(status) {
  document.querySelectorAll('.status-value').forEach(sel => { sel.value = status; });
  document.querySelectorAll('.att-toggle-group').forEach(group => {
    group.querySelectorAll('.att-btn').forEach(btn => btn.classList.remove('active'));
    const target = group.querySelector(`.att-btn.${status.toLowerCase()}`);
    if (target) target.classList.add('active');
  });
  updateAttendanceTally();
}

async function submitBulkAttendance() {
  const date    = document.getElementById('mark_date').value;
  const rows    = document.querySelectorAll('.status-value');
  const submitMsg = document.getElementById('submitMsg');

  if (rows.length === 0) {
    submitMsg.innerHTML = '<span style="opacity:.6">No students loaded.</span>';
    return;
  }

  submitMsg.innerHTML = '<span style="opacity:.6">Saving attendance...</span>';

  const records = Array.from(rows).map(sel => ({
    student_id: parseInt(sel.dataset.studentId),
    date: date,
    status: sel.value,
  }));

  try {
    const res = await fetch(`${API_BASE}/attendance/bulk`, {
      method: 'POST',
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(records),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Unknown error');
    }

    const data = await res.json();
    submitMsg.innerHTML = `<span style="color:var(--success-color)">✔ ${data.message} (${data.saved} records saved)</span>`;
  } catch (e) {
    submitMsg.innerHTML = `<span style="color:var(--error-color)">❌ Failed: ${e.message}</span>`;
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// PANEL 2: Period Absence Log (Subject Teachers)
// ─────────────────────────────────────────────────────────────────────────────
let subjectAssignments = [];

async function initPeriodPanel() {
  const today = new Date().toISOString().slice(0, 10);
  document.getElementById('period_date').value = today;

  try {
    const res = await fetch(`${API_BASE}/attendance/my-subject-assignments`, { headers: getHeaders() });
    subjectAssignments = await res.json();

    // Build unique class list
    const classMap = {};
    subjectAssignments.forEach(a => {
      if (!classMap[a.class_section_id]) {
        classMap[a.class_section_id] = a.class_name;
      }
    });

    const periodClassEl = document.getElementById('period_class_id');
    periodClassEl.innerHTML = '<option value="">Select Class...</option>' +
      Object.entries(classMap).map(([id, name]) => `<option value="${id}">${name}</option>`).join('');
  } catch (e) {
    console.error('Failed to load subject assignments:', e);
  }
}

function loadPeriodSubjects() {
  const classId = parseInt(document.getElementById('period_class_id').value);
  const subjectEl = document.getElementById('period_subject_id');
  const subjects = subjectAssignments.filter(a => a.class_section_id === classId && a.subject_id);

  if (subjects.length === 0) {
    subjectEl.innerHTML = '<option value="">All Subjects</option>';
  } else {
    subjectEl.innerHTML = '<option value="">Select Subject...</option>' +
      subjects.map(s => `<option value="${s.subject_id}">${s.subject_name}</option>`).join('');
  }

  document.getElementById('periodRollCard').style.display = 'none';
}

async function loadPeriodRoll() {
  const classId   = document.getElementById('period_class_id').value;
  const subjectId = document.getElementById('period_subject_id').value;
  const periodMsg = document.getElementById('periodMsg');

  if (!classId) {
    periodMsg.innerHTML = '<span style="color:var(--error-color)">Please select a class.</span>';
    return;
  }

  periodMsg.innerHTML = '<span style="opacity:.6">Loading students...</span>';

  try {
    const res = await fetch(`${API_BASE}/students/?class_id=${classId}`, { headers: getHeaders() });
    const allStudents = await res.json();
    const students = allStudents.filter(s => s.class_section_id == classId && s.is_active !== false);

    if (students.length === 0) {
      periodMsg.innerHTML = '<span style="opacity:.6">No active students found.</span>';
      document.getElementById('periodRollCard').style.display = 'none';
      return;
    }

    const className = document.getElementById('period_class_id').selectedOptions[0]?.text || '';
    const subjectName = document.getElementById('period_subject_id').selectedOptions[0]?.text || 'All Subjects';
    document.getElementById('periodRollTitle').textContent = `${className} – ${subjectName}`;
    document.getElementById('periodRollSubtitle').textContent = `${students.length} students — check those ABSENT from this lesson`;

    document.getElementById('periodRollBody').innerHTML = students.map(s => `
      <label style="display:flex; align-items:center; gap:10px; padding:10px 14px; border:1px solid var(--border-color); border-radius:8px; cursor:pointer; transition:background .15s;" 
             onmouseover="this.style.background='rgba(239,68,68,.07)'" onmouseout="this.style.background=''">
        <input type="checkbox" class="absent-check" data-student-id="${s.id}" 
               style="width:18px; height:18px; cursor:pointer; accent-color:var(--error-color,#ef4444);" />
        <span>
          <strong style="font-size:.9rem;">${s.full_name}</strong><br/>
          <span style="font-size:.78rem; opacity:.65;">${s.student_code}</span>
        </span>
      </label>
    `).join('');

    document.getElementById('periodRollCard').style.display = 'block';
    periodMsg.innerHTML = '';
    document.getElementById('periodSubmitMsg').innerHTML = '';
  } catch (e) {
    periodMsg.innerHTML = `<span style="color:var(--error-color)">Error: ${e.message}</span>`;
  }
}

async function submitPeriodAbsences() {
  const classId    = document.getElementById('period_class_id').value;
  const subjectId  = document.getElementById('period_subject_id').value;
  const date       = document.getElementById('period_date').value;
  const label      = document.getElementById('period_label').value.trim();
  const submitMsg  = document.getElementById('periodSubmitMsg');

  if (!classId || !date) {
    submitMsg.innerHTML = '<span style="color:var(--error-color)">Please select a class and date.</span>';
    return;
  }

  const absentIds = Array.from(document.querySelectorAll('.absent-check:checked'))
    .map(cb => parseInt(cb.dataset.studentId));

  if (absentIds.length === 0) {
    submitMsg.innerHTML = '<span style="opacity:.6">ℹ️ No students checked as absent. If all were present, no submission needed.</span>';
    return;
  }

  submitMsg.innerHTML = '<span style="opacity:.6">Submitting...</span>';

  try {
    const res = await fetch(`${API_BASE}/attendance/period-absence`, {
      method: 'POST',
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({
        class_section_id: parseInt(classId),
        subject_id: subjectId ? parseInt(subjectId) : null,
        date,
        period_label: label || null,
        absent_student_ids: absentIds,
      }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Unknown error');
    }

    const data = await res.json();
    submitMsg.innerHTML = `<span style="color:var(--success-color)">🚨 ${data.message} — Form Master has been notified.</span>`;

    // Uncheck all after submission
    document.querySelectorAll('.absent-check').forEach(cb => { cb.checked = false; });
  } catch (e) {
    submitMsg.innerHTML = `<span style="color:var(--error-color)">❌ Failed: ${e.message}</span>`;
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// PANEL 3: Attendance Records Browser (read-only)
// ─────────────────────────────────────────────────────────────────────────────
async function initRecordsPanel() {
  try {
    const res = await fetch(`${API_BASE}/classes/my-classes`, { headers: getHeaders() });
    const classes = await res.json();
    const opts = classes.map(c => `<option value="${c.id}">${c.name}</option>`).join('');
    document.getElementById('rec_class_id').innerHTML = '<option value="">Select Class...</option>' + opts;
  } catch (e) {
    console.error('Failed to load classes for records:', e);
  }
}

async function loadAttendanceRecords() {
  const classId  = document.getElementById('rec_class_id').value;
  const dateFrom = document.getElementById('rec_date_from').value;
  const dateTo   = document.getElementById('rec_date_to').value;
  const status   = document.getElementById('rec_status').value;
  const recType  = document.getElementById('rec_type').value;
  const tbody    = document.getElementById('recordsBody');

  if (!classId) {
    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:20px;opacity:.6">Please select a class.</td></tr>';
    return;
  }

  tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:20px;opacity:.6">Loading...</td></tr>';

  try {
    let url = `${API_BASE}/attendance/class/${classId}`;
    const params = [];
    if (dateFrom) params.push(`date_from=${dateFrom}`);
    if (dateTo)   params.push(`date_to=${dateTo}`);
    if (status)   params.push(`status=${status}`);
    if (params.length) url += '?' + params.join('&');

    const res = await fetch(url, { headers: getHeaders() });
    if (!res.ok) throw new Error('Failed to load records');
    let records = await res.json();

    // Filter by type client-side
    if (recType) records = records.filter(r => (r.attendance_type || 'daily') === recType);

    if (records.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:20px;opacity:.6">No records found for the selected filters.</td></tr>';
      renderRecordStats([]);
      return;
    }

    tbody.innerHTML = records.map(r => `
      <tr>
        <td>${r.date}</td>
        <td>${r.student_name}</td>
        <td><strong>${r.student_code}</strong></td>
        <td>${typeChip(r.attendance_type || 'daily')}</td>
        <td>${statusChip(r.status)}</td>
        <td>
          <button class="btn" style="padding:4px 10px; font-size:.8rem; color:var(--error-color); border-color:var(--error-color);"
            onclick="deleteRecord(${r.id}, this)">🗑 Delete</button>
        </td>
      </tr>
    `).join('');

    renderRecordStats(records);
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:20px;color:var(--error-color)">Error: ${e.message}</td></tr>`;
  }
}

function renderRecordStats(records) {
  const statsEl = document.getElementById('recordsStats');
  if (records.length === 0) { statsEl.style.display = 'none'; return; }
  const present  = records.filter(r => r.status === 'Present').length;
  const absent   = records.filter(r => r.status === 'Absent').length;
  const late     = records.filter(r => r.status === 'Late').length;
  const excused  = records.filter(r => r.status === 'Excused').length;
  const pct      = records.length > 0 ? ((present / records.length) * 100).toFixed(1) : 0;
  statsEl.style.display = 'flex';
  statsEl.innerHTML = `
    <span>📊 <strong>${records.length}</strong> records</span>
    <span>✅ Present: <strong>${present}</strong></span>
    <span>❌ Absent: <strong>${absent}</strong></span>
    <span>⏰ Late: <strong>${late}</strong></span>
    <span>🔵 Excused: <strong>${excused}</strong></span>
    <span>📈 Attendance Rate: <strong>${pct}%</strong></span>
  `;
}

async function deleteRecord(id, btn) {
  const ok = await (window.showConfirmDialog ? window.showConfirmDialog(
    '🗑️ Delete Attendance Record',
    'Are you sure you want to delete this student attendance log entry?',
    'Delete Record',
    'Cancel',
    'warning'
  ) : Promise.resolve(confirm('Delete this attendance record?')));

  if (!ok) return;
  btn.disabled = true;
  btn.textContent = '...';
  try {
    const res = await fetch(`${API_BASE}/attendance/${id}`, {
      method: 'DELETE',
      headers: getHeaders(),
    });
    if (!res.ok) throw new Error('Delete failed');
    btn.closest('tr').remove();
  } catch (e) {
    btn.disabled = false;
    btn.textContent = '🗑 Delete';
    alert('Failed to delete record: ' + e.message);
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// PANEL 4: House & Dormitory Nightly Roll Call (House Masters & Domestic Head)
// ─────────────────────────────────────────────────────────────────────────────
let loadedHouseStudents = [];
let allSchoolHouses = [];

async function initHouseRollPanel() {
  const dateInput = document.getElementById('hr_date');
  if (dateInput) dateInput.value = new Date().toISOString().slice(0, 10);

  try {
    const res = await fetch(`${API_BASE}/houses/`, { headers: getHeaders() });
    if (res.ok) {
      allSchoolHouses = await res.json();
      const houseSel = document.getElementById('hr_house_id');
      if (houseSel && Array.isArray(allSchoolHouses)) {
        houseSel.innerHTML = '<option value="">Select House...</option>' + 
          allSchoolHouses.map(h => `<option value="${h.id}">${h.name} (${h.gender_type || 'MIXED'})</option>`).join('');
      }
    }
  } catch (e) {
    console.error('Failed to load houses:', e);
  }
}

function onHouseChange() {
  const houseId = document.getElementById('hr_house_id').value;
  const dormSel = document.getElementById('hr_dorm_id');
  if (!dormSel) return;

  dormSel.innerHTML = '<option value="">All Dormitories</option>';
  if (!houseId) return;

  const house = allSchoolHouses.find(h => String(h.id) === String(houseId));
  if (house && Array.isArray(house.dormitories)) {
    dormSel.innerHTML += house.dormitories.map(d => `<option value="${d.id}">${d.name} (${d.gender_type || 'MIXED'})</option>`).join('');
  }
}

async function loadHouseRoll() {
  const houseId = document.getElementById('hr_house_id').value;
  const dormId = document.getElementById('hr_dorm_id').value;
  const dateVal = document.getElementById('hr_date').value;
  const houseMsg = document.getElementById('houseRollMsg');
  const houseCard = document.getElementById('houseRollCard');

  if (!houseId || !dateVal) {
    houseMsg.innerHTML = '<span style="color:var(--error-color,#ef4444);">Please select a Boarding House and Date.</span>';
    return;
  }

  houseMsg.innerHTML = '<span style="opacity:.6">Loading house boarders & verified exeat records...</span>';

  try {
    const [resStudents, resExeats] = await Promise.all([
      fetch(`${API_BASE}/students/?house_id=${houseId}`, { headers: getHeaders() }),
      fetch(`${API_BASE}/exeat/`, { headers: getHeaders() })
    ]);

    const allStudents = await resStudents.json();
    let boarders = Array.isArray(allStudents) ? allStudents.filter(s => String(s.house_id) === String(houseId) && s.is_active !== false) : [];

    if (dormId) {
      boarders = boarders.filter(s => String(s.dormitory_id) === String(dormId));
    }

    let activeExeats = [];
    if (resExeats.ok) {
      const exeats = await resExeats.json();
      if (Array.isArray(exeats)) {
        activeExeats = exeats.filter(e => ['Departed', 'Away', 'APPROVED'].includes(e.status));
      }
    }

    loadedHouseStudents = boarders;
    houseMsg.innerHTML = '';

    if (boarders.length === 0) {
      houseCard.style.display = 'block';
      document.getElementById('houseRollBody').innerHTML = '<tr><td colspan="7" style="text-align:center; padding:20px; opacity:.6;">No active boarders assigned to this house/dormitory.</td></tr>';
      return;
    }

    const houseObj = allSchoolHouses.find(h => String(h.id) === String(houseId));
    document.getElementById('houseRollTitle').textContent = `🏠 ${houseObj ? houseObj.name : 'House'} Boarding Roll Call`;
    document.getElementById('houseRollSubtitle').textContent = `Date: ${dateVal} | ${boarders.length} Active Boarder(s)`;

    const tbody = document.getElementById('houseRollBody');
    tbody.innerHTML = boarders.map((s, idx) => {
      const onExeat = activeExeats.some(e => String(e.student_id) === String(s.id));
      const defaultStatus = onExeat ? 'Away on Exeat' : 'Present in Dorm';
      const exeatBadge = onExeat
        ? `<span style="background:rgba(168,85,247,0.2); color:#c084fc; border:1px solid rgba(168,85,247,0.4); padding:2px 8px; border-radius:12px; font-size:0.75rem; font-weight:700;">✈️ AWAY ON EXEAT</span>`
        : `<span style="opacity:0.5; font-size:0.75rem;">On Campus</span>`;

      return `
        <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
          <td style="padding:10px 12px;">${idx + 1}</td>
          <td style="padding:10px 12px; font-family:monospace; color:#38bdf8;">${s.student_code || s.id}</td>
          <td style="padding:10px 12px; font-weight:600; color:#f8fafc;">${s.full_name}</td>
          <td style="padding:10px 12px; opacity:0.8;">${s.dormitory_name || 'Dorm Unassigned'}</td>
          <td style="padding:10px 12px;">${exeatBadge}</td>
          <td style="padding:10px 12px;">
            <select class="hr-status-select" data-student-id="${s.id}" style="padding:4px 8px; border-radius:6px; font-size:0.82rem; background:var(--card-bg,#1e293b); color:#f8fafc; border:1px solid rgba(255,255,255,0.15);">
              <option value="Present in Dorm" ${defaultStatus === 'Present in Dorm' ? 'selected' : ''}>✅ Present in Dorm</option>
              <option value="Away on Exeat" ${defaultStatus === 'Away on Exeat' ? 'selected' : ''}>✈️ Away on Exeat</option>
              <option value="Sickbay" ${defaultStatus === 'Sickbay' ? 'selected' : ''}>🏥 Sickbay / Medical</option>
              <option value="Absent / Unaccounted" ${defaultStatus === 'Absent / Unaccounted' ? 'selected' : ''}>🚨 Absent / Unaccounted</option>
            </select>
          </td>
          <td style="padding:10px 12px;">
            <input type="text" class="hr-remarks-input" data-student-id="${s.id}" placeholder="Optional remark..." style="padding:4px 8px; border-radius:6px; font-size:0.8rem; width:100%; border:1px solid rgba(255,255,255,0.1); background:rgba(0,0,0,0.2); color:white;" />
          </td>
        </tr>
      `;
    }).join('');

    houseCard.style.display = 'block';
  } catch (err) {
    console.error('Error loading house roll:', err);
    houseMsg.innerHTML = '<span style="color:var(--error-color,#ef4444);">Failed to load house boarders: ' + err.message + '</span>';
  }
}

function markAllHouse(status) {
  document.querySelectorAll('.hr-status-select').forEach(sel => sel.value = status);
}

async function submitHouseRollCall() {
  const dateVal = document.getElementById('hr_date').value;
  const msgEl = document.getElementById('houseSubmitMsg');

  if (!loadedHouseStudents.length) return;

  const records = loadedHouseStudents.map(s => {
    const statusSel = document.querySelector(`.hr-status-select[data-student-id="${s.id}"]`);
    const remarksInp = document.querySelector(`.hr-remarks-input[data-student-id="${s.id}"]`);
    return {
      student_id: s.id,
      status: statusSel ? statusSel.value : 'Present in Dorm',
      remarks: remarksInp ? remarksInp.value : ''
    };
  });

  msgEl.innerHTML = '<span style="opacity:.6">Saving house roll call records...</span>';

  try {
    let savedCount = 0;
    for (const r of records) {
      const res = await fetch(`${API_BASE}/attendance/`, {
        method: 'POST',
        headers: getHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({
          student_id: r.student_id,
          date: dateVal,
          status: r.status.includes('Present') ? 'Present' : (r.status.includes('Exeat') ? 'Excused' : (r.status.includes('Sickbay') ? 'Excused' : 'Absent')),
          attendance_type: 'daily',
          remarks: `[House Roll] ${r.status}${r.remarks ? ' - ' + r.remarks : ''}`
        })
      });
      if (res.ok) savedCount++;
    }

    msgEl.innerHTML = `<span style="color:#4ade80; font-weight:700;">✓ Nightly House Roll Call saved successfully for ${savedCount} boarder(s)!</span>`;
  } catch (err) {
    console.error('Error submitting house roll:', err);
    msgEl.innerHTML = `<span style="color:#ef4444;">Failed to submit house roll: ${err.message}</span>`;
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// PANEL 5: Attendance Reconciliation & Truancy Audit Desk
// ─────────────────────────────────────────────────────────────────────────────
async function initAuditPanel() {
  const auditDateInp = document.getElementById('audit_date');
  if (auditDateInp) auditDateInp.value = new Date().toISOString().slice(0, 10);

  try {
    const res = await fetch(`${API_BASE}/houses/`, { headers: getHeaders() });
    if (res.ok) {
      const houses = await res.json();
      const sel = document.getElementById('audit_house_id');
      if (sel && Array.isArray(houses)) {
        sel.innerHTML = '<option value="">All Boarding Houses</option>' +
          houses.map(h => `<option value="${h.id}">${h.name}</option>`).join('');
      }
    }
  } catch (e) {
    console.error('Failed to load audit houses:', e);
  }
}

async function loadReconciliationAudit() {
  const dateVal = document.getElementById('audit_date').value;
  const houseId = document.getElementById('audit_house_id').value;
  const tbody = document.getElementById('auditBody');
  const kpiSec = document.getElementById('auditKpiSection');

  if (!dateVal) return;
  tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; padding:20px; opacity:.6;">Running real-time cross-reconciliation audit...</td></tr>';

  try {
    let url = `${API_BASE}/attendance/reconciliation-audit?date_str=${dateVal}`;
    if (houseId) url += `&house_id=${houseId}`;

    const res = await fetch(url, { headers: getHeaders() });
    if (!res.ok) throw new Error('Failed to run audit');
    const data = await res.json();

    document.getElementById('kpiAudited').textContent = data.total_audited || 0;
    document.getElementById('kpiDayTruancy').textContent = data.day_truancy_count || 0;
    document.getElementById('kpiNightAbsence').textContent = data.night_absence_count || 0;
    document.getElementById('kpiUnapprovedExeat').textContent = data.unexcused_house_absence_count || 0;
    document.getElementById('kpiClean').textContent = data.reconciled_clean_count || 0;
    if (kpiSec) kpiSec.style.display = 'grid';

    if (!Array.isArray(data.discrepancies) || data.discrepancies.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding:20px; color:#4ade80; font-weight:600;">✓ All ${data.total_audited} boarders reconciled cleanly! No truancy or attendance discrepancies detected.</td></tr>`;
      return;
    }

    tbody.innerHTML = data.discrepancies.map(d => {
      let badge = `<span style="background:rgba(239,68,68,0.2); color:#f87171; border:1px solid rgba(239,68,68,0.4); padding:2px 8px; border-radius:12px; font-weight:700; font-size:0.75rem;">${d.discrepancy_label}</span>`;
      if (d.discrepancy_type === 'NIGHT_ABSENCE') {
        badge = `<span style="background:rgba(245,158,11,0.2); color:#fbbf24; border:1px solid rgba(245,158,11,0.4); padding:2px 8px; border-radius:12px; font-weight:700; font-size:0.75rem;">${d.discrepancy_label}</span>`;
      } else if (d.discrepancy_type === 'UNEXCUSED_HOUSE_ABSENCE') {
        badge = `<span style="background:rgba(168,85,247,0.2); color:#c084fc; border:1px solid rgba(168,85,247,0.4); padding:2px 8px; border-radius:12px; font-weight:700; font-size:0.75rem;">${d.discrepancy_label}</span>`;
      }

      const exeatStatusStr = d.has_active_exeat 
        ? `<span style="color:#c084fc; font-weight:600;">✈️ Active Exeat</span>`
        : `<span style="opacity:0.6;">No Exeat File</span>`;

      return `
        <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
          <td style="padding:10px 12px; font-family:monospace; color:#38bdf8;">${d.student_code}</td>
          <td style="padding:10px 12px; font-weight:600; color:#f8fafc;">${d.student_name}</td>
          <td style="padding:10px 12px;">🏠 ${d.house_name} | 📚 ${d.class_name}</td>
          <td style="padding:10px 12px;">${d.class_status}</td>
          <td style="padding:10px 12px;">${d.house_status}</td>
          <td style="padding:10px 12px;">${exeatStatusStr}</td>
          <td style="padding:10px 12px;">${badge}</td>
          <td style="padding:10px 12px; text-align:right;">
            <a href="discipline.html" class="btn sm" style="padding:4px 10px; font-size:0.75rem; background:rgba(239,68,68,0.2); color:#f87171; border:1px solid rgba(239,68,68,0.4); text-decoration:none; border-radius:6px; font-weight:600;">⚖️ Flag Discipline</a>
          </td>
        </tr>
      `;
    }).join('');

  } catch (err) {
    console.error('Failed to run reconciliation audit:', err);
    tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding:20px; color:#ef4444;">Failed to run audit: ${err.message}</td></tr>`;
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// PANEL 6: Barcode & QR Real-Time Scanner Check-In & Truancy SMS Dispatch
// ─────────────────────────────────────────────────────────────────────────────

let scanHistory = [];
let audioCtx = null;

function getAudioContext() {
  if (!audioCtx) {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (AudioContextClass) {
      audioCtx = new AudioContextClass();
    }
  }
  if (audioCtx && audioCtx.state === 'suspended') {
    audioCtx.resume();
  }
  return audioCtx;
}

function playAudioCue(type) {
  const toggle = document.getElementById('scanAudioToggle');
  if (toggle && !toggle.checked) return;

  try {
    const ctx = getAudioContext();
    if (!ctx) return;

    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);

    const now = ctx.currentTime;

    if (type === 'success') {
      // Pleasant high-pitch success chime
      osc.type = 'sine';
      osc.frequency.setValueAtTime(587.33, now); // D5
      osc.frequency.exponentialRampToValueAtTime(880.00, now + 0.15); // A5
      gain.gain.setValueAtTime(0.3, now);
      gain.gain.exponentialRampToValueAtTime(0.01, now + 0.25);
      osc.start(now);
      osc.stop(now + 0.25);
    } else if (type === 'late') {
      // Distinct double warning tone
      osc.type = 'triangle';
      osc.frequency.setValueAtTime(440, now);
      osc.frequency.setValueAtTime(349.23, now + 0.1);
      gain.gain.setValueAtTime(0.35, now);
      gain.gain.exponentialRampToValueAtTime(0.01, now + 0.3);
      osc.start(now);
      osc.stop(now + 0.3);
    } else if (type === 'already_scanned') {
      // Gentle double blip
      osc.type = 'sine';
      osc.frequency.setValueAtTime(523.25, now);
      gain.gain.setValueAtTime(0.2, now);
      gain.gain.exponentialRampToValueAtTime(0.01, now + 0.12);
      osc.start(now);
      osc.stop(now + 0.12);
    } else {
      // Error buzzer
      osc.type = 'sawtooth';
      osc.frequency.setValueAtTime(150, now);
      gain.gain.setValueAtTime(0.4, now);
      gain.gain.exponentialRampToValueAtTime(0.01, now + 0.35);
      osc.start(now);
      osc.stop(now + 0.35);
    }
  } catch (e) {
    console.warn('Audio cue failed:', e);
  }
}

async function handleScannerSubmit() {
  const inputEl = document.getElementById('scanner_input');
  if (!inputEl) return;
  const rawCode = inputEl.value.trim();
  if (!rawCode) return;

  const modeEl = document.getElementById('scanner_mode');
  const scanType = modeEl ? modeEl.value : 'Morning Roll Call';

  try {
    const res = await fetch(`${API_BASE}/attendance/scan-checkin`, {
      method: 'POST',
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({
        student_code: rawCode,
        scan_type: scanType
      })
    });

    if (!res.ok) {
      playAudioCue('error');
      const err = await res.json().catch(() => ({ detail: 'Student verification failed' }));
      alert(`⚠️ Scan Error: ${err.detail || 'Student not found in registry'}`);
      inputEl.value = '';
      inputEl.focus();
      return;
    }

    const data = await res.json();
    playAudioCue(data.audio_cue || 'success');

    // Render result card
    renderScanCard(data);

    // Add to history list
    scanHistory.unshift(data);
    renderScanHistory();

    // Reset input for next laser scan
    inputEl.value = '';
    inputEl.focus();

  } catch (err) {
    console.error('Scan check-in network error:', err);
    playAudioCue('error');
    alert('Network error while processing scan check-in.');
  }
}

function renderScanCard(data) {
  const card = document.getElementById('scanResultCard');
  if (!card) return;

  document.getElementById('scanCardName').textContent = data.full_name;
  document.getElementById('scanCardCode').textContent = data.student_code;
  document.getElementById('scanCardClass').textContent = data.class_name;
  document.getElementById('scanCardHouse').textContent = data.house_name;
  document.getElementById('scanCardTime').textContent = `${data.timestamp_str} (${data.scan_type})`;

  const badge = document.getElementById('scanCardBadge');
  if (data.status === 'Late') {
    badge.style.background = 'rgba(245,158,11,0.2)';
    badge.style.borderColor = '#f59e0b';
    badge.style.color = '#fbbf24';
    badge.textContent = '⏰ LATE ARRIVAL';
  } else {
    badge.style.background = 'rgba(16,185,129,0.2)';
    badge.style.borderColor = '#10b981';
    badge.style.color = '#34d399';
    badge.textContent = '✅ PRESENT (ON TIME)';
  }

  if (data.is_duplicate) {
    badge.textContent += ' [REPEAT SCAN]';
  }

  card.style.display = 'block';
}

function renderScanHistory() {
  const tbody = document.getElementById('scanHistoryBody');
  const countEl = document.getElementById('scanCount');
  if (countEl) countEl.textContent = scanHistory.length;
  if (!tbody) return;

  if (scanHistory.length === 0) {
    tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding:20px; opacity:.6;">No scans recorded yet in this session.</td></tr>';
    return;
  }

  tbody.innerHTML = scanHistory.map((item, idx) => {
    const statusClass = item.status === 'Late' ? 'warning' : 'success';
    return `
      <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
        <td style="text-align:center; opacity:0.6;">${idx + 1}</td>
        <td style="font-size:0.8rem; opacity:0.8;">${item.timestamp_str}</td>
        <td style="font-family:monospace; color:#38bdf8; font-weight:700;">${item.student_code}</td>
        <td style="font-weight:600;">${item.full_name}</td>
        <td>${item.class_name}</td>
        <td><span style="font-size:0.75rem; opacity:0.75;">${item.scan_type}</span></td>
        <td><span class="chip ${statusClass}">${item.status}</span></td>
      </tr>
    `;
  }).join('');
}

function clearScanHistory() {
  scanHistory = [];
  renderScanHistory();
  const card = document.getElementById('scanResultCard');
  if (card) card.style.display = 'none';
  const inputEl = document.getElementById('scanner_input');
  if (inputEl) {
    inputEl.value = '';
    inputEl.focus();
  }
}

async function dispatchTruancyAlerts() {
  const ok = await (window.showConfirmDialog ? window.showConfirmDialog(
    '📢 Dispatch Absence / Truancy SMS Alerts',
    'Are you sure you want to scan all unexcused absences recorded today and queue/dispatch personalized Hubtel SMS alerts to their parents/guardians?',
    'Dispatch Alerts',
    'Cancel'
  ) : Promise.resolve(confirm('Are you sure you want to dispatch SMS alerts to parents of absent students?')));

  if (!ok) return;

  try {
    const today = new Date().toISOString().slice(0, 10);
    const res = await fetch(`${API_BASE}/attendance/dispatch-truancy-alerts`, {
      method: 'POST',
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ date_str: today })
    });

    if (res.ok) {
      const data = await res.json();
      alert(`✅ ${data.message}`);
    } else {
      const err = await res.json().catch(() => ({ detail: 'Failed to dispatch alerts' }));
      alert(`⚠️ Error: ${err.detail || 'Could not send alerts'}`);
    }
  } catch (err) {
    console.error('Failed to dispatch truancy alerts:', err);
    alert('Network error while dispatching truancy SMS alerts.');
  }
}

async function downloadAttendanceLedgerPDF() {
  const classId = document.getElementById('mark_class_id')?.value || document.getElementById('rec_class_id')?.value;
  if (!classId) {
    alert('Please select a Class Section under "Daily Register" or "Attendance Records" first.');
    return;
  }

  const now = new Date();
  const month = now.getMonth() + 1;
  const year = now.getFullYear();

  try {
    const token = localStorage.getItem('accessToken') || sessionStorage.getItem('accessToken');
    const res = await fetch(`${API_BASE}/attendance/ledger-pdf/${classId}?month=${month}&year=${year}`, {
      headers: { 'Authorization': token ? `Bearer ${token}` : '' }
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to generate attendance ledger PDF' }));
      alert(`⚠️ Error: ${err.detail || 'Failed to download PDF ledger'}`);
      return;
    }

    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `Attendance_Register_Class_${classId}_${month}_${year}.pdf`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  } catch (err) {
    console.error('Failed to download attendance ledger:', err);
    alert('Network error while generating attendance ledger PDF.');
  }
}

// ── Init ───────────────────────────────────────────────────────────────────────
async function initPage() {
  let formClasses = [];
  try {
    const res = await fetch(`${API_BASE}/classes/my-form-classes`, { headers: getHeaders() });
    formClasses = await res.json();
  } catch (e) { /* ignore */ }

  await buildTabNav(formClasses);
  await initDailyRegister();
  await initHouseRollPanel();
  await initAuditPanel();
  await initPeriodPanel();
  await initRecordsPanel();
}

initPage();

