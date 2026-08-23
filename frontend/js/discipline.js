// ── Config & Auth ────────────────────────────────────────────────────────────
const API_BASE = window.API_BASE || (window.location.origin.includes('http') ? (window.location.origin + '/api') : 'http://127.0.0.1:8000/api');
const token = localStorage.getItem('accessToken');
if (!token) window.location.href = 'auth.html';

function H(extra = {}) { return { 'Authorization': `Bearer ${token}`, ...extra }; }
function J(extra = {}) { return H({ 'Content-Type': 'application/json', ...extra }); }

// ── Constants ─────────────────────────────────────────────────────────────────
const TYPE_ICONS = {
  Warning:      '⚠️',
  Detention:    '🔒',
  Suspension:   '🚫',
  Commendation: '🏅',
  Expulsion:    '❌',
};

// ── State ────────────────────────────────────────────────────────────────────
let allRecords   = [];
let allStudents  = [];
let allClasses   = [];
let selectedType = 'Warning';

// ── Init ─────────────────────────────────────────────────────────────────────
async function init() {
  document.getElementById('fDate').value = todayISO();
  selectTypeByName('Warning');   // default chip selection
  await Promise.all([loadStudents(), loadClasses()]);
  await Promise.all([loadSummary(), loadRecords()]);
}

// ── Data Loaders ──────────────────────────────────────────────────────────────
async function loadStudents() {
  const res = await fetch(`${API_BASE}/students/`, { headers: H() });
  if (!res.ok) return;
  allStudents = await res.json();

  const opts = allStudents.map(s =>
    `<option value="${esc(s.full_name)} (${esc(s.student_code)})"></option>`
  ).join('');
  document.getElementById('studentDatalist').innerHTML = opts;
}

window.onStudentSearchChange = function() {
  const val = document.getElementById('fStudentSearch').value;
  const student = allStudents.find(s => `${s.full_name} (${s.student_code})` === val);
  const fStudent = document.getElementById('fStudent');
  if (student) {
    fStudent.value = student.id;
    onStudentChange(); // refresh quick info
  } else {
    fStudent.value = '';
    document.getElementById('studentQuick').classList.remove('visible');
  }
};

async function loadClasses() {
  const res = await fetch(`${API_BASE}/classes/my-classes`, { headers: H() });
  if (!res.ok) return;
  allClasses = await res.json();

  const filterOpts = '<option value="">All Classes</option>' +
    allClasses.map(c => `<option value="${c.id}">${esc(c.name)}</option>`).join('');
  document.getElementById('fFilterClass').innerHTML = filterOpts;
}

async function loadSummary() {
  try {
    const res = await fetch(`${API_BASE}/discipline/summary`, { headers: H() });
    if (!res.ok) return;
    const d = await res.json();
    document.getElementById('sTotal').textContent       = d.total;
    document.getElementById('sCommendation').textContent = d.Commendation;
    document.getElementById('sWarning').textContent     = d.Warning;
    document.getElementById('sDetention').textContent   = d.Detention;
    document.getElementById('sSuspension').textContent  = d.Suspension;
    document.getElementById('sExpulsion').textContent   = d.Expulsion;
  } catch (e) { console.error(e); }
}

window.loadRecords = async function() {
  document.getElementById('incidentFeed').innerHTML = '<div class="empty-state">Loading...</div>';
  try {
    const res = await fetch(`${API_BASE}/discipline/`, { headers: H() });
    if (!res.ok) {
      document.getElementById('incidentFeed').innerHTML = '<div class="empty-state">Failed to load records.</div>';
      return;
    }
    allRecords = await res.json();
    applyFilter();
  } catch (e) {
    document.getElementById('incidentFeed').innerHTML = '<div class="empty-state">Network error.</div>';
  }
};

// ── Student change — show quick info ─────────────────────────────────────────
function onStudentChange() {
  const sid = document.getElementById('fStudent').value;
  if (!sid) { document.getElementById('studentQuick').classList.remove('visible'); return; }
  const student = allStudents.find(s => String(s.id) === sid);
  if (!student) return;
  const cls = allClasses.find(c => c.id === student.class_section_id);
  const records = allRecords.filter(r => String(r.student_id) === sid);
  const el = document.getElementById('studentQuick');
  el.classList.add('visible');
  el.innerHTML = `<strong>${esc(student.full_name)}</strong> &nbsp;·&nbsp; ${esc(cls?.name || 'No class')} &nbsp;·&nbsp;
    <span style="color:var(--text-secondary)">${records.length} previous record(s)</span>`;
}

// ── Type chip selection ───────────────────────────────────────────────────────
window.selectType = function(btn) {
  document.querySelectorAll('.type-chip').forEach(c => c.classList.remove('active'));
  btn.classList.add('active');
  selectedType = btn.dataset.type;
  // Change button color for commendation
  const logBtn = document.getElementById('logBtn');
  if (selectedType === 'Commendation') {
    logBtn.classList.add('commendation');
    logBtn.textContent = 'Log Commendation';
  } else {
    logBtn.classList.remove('commendation');
    logBtn.textContent = 'Log Record';
  }
};

function selectTypeByName(name) {
  const chip = document.querySelector(`.type-chip[data-type="${name}"]`);
  if (chip) selectType(chip);
}

// ── Filter & Render ───────────────────────────────────────────────────────────
window.applyFilter = function() {
  const typeF    = document.getElementById('fFilterType').value;
  const classF   = document.getElementById('fFilterClass').value;
  const searchF  = document.getElementById('fSearch').value.toLowerCase();
  const dateFrom = document.getElementById('fDateFrom').value;
  const dateTo   = document.getElementById('fDateTo').value;

  let filtered = allRecords.filter(r => {
    if (typeF && r.incident_type !== typeF) return false;
    if (classF) {
      const s = allStudents.find(st => st.id === r.student_id);
      if (!s || String(s.class_section_id) !== classF) return false;
    }
    if (searchF) {
      const name = (r.student_name || '').toLowerCase();
      const code = (r.student_code || '').toLowerCase();
      if (!name.includes(searchF) && !code.includes(searchF)) return false;
    }
    if (dateFrom && r.incident_date && r.incident_date.split('T')[0] < dateFrom) return false;
    if (dateTo   && r.incident_date && r.incident_date.split('T')[0] > dateTo) return false;
    return true;
  });

  renderFeed(filtered);
  document.getElementById('feedCount').textContent =
    `Showing ${filtered.length} of ${allRecords.length} records`;
  onStudentChange(); // refresh quick info
};

function renderFeed(records) {
  const feed = document.getElementById('incidentFeed');
  if (!records.length) {
    feed.innerHTML = '<div class="empty-state">No discipline records match your filters.</div>';
    return;
  }

  feed.innerHTML = records.map(r => {
    const icon    = TYPE_ICONS[r.incident_type] || '📋';
    const typeKey = r.incident_type.toLowerCase();
    const date    = r.incident_date ? new Date(r.incident_date).toLocaleDateString('en-GB', {day:'2-digit',month:'short',year:'numeric'}) : '—';
    const classLabel = r.class_name ? `<span class="badge badge-class">${esc(r.class_name)}</span>` : '';
    const notifBadge = r.parent_notified ? '<span class="badge badge-notified">Parent Notified</span>' : '';
    const recorder   = r.recorder_name ? `by ${esc(r.recorder_name)}` : '';

    return `
    <div class="incident-card ${r.incident_type}" id="card-${r.id}">
      <div class="incident-icon">${icon}</div>
      <div class="incident-body">
        <div class="incident-header">
          <div>
            <div class="incident-student">${esc(r.student_name || '—')}
              <span style="font-weight:400;color:var(--text-secondary);font-size:0.78rem;">(${esc(r.student_code || '')})</span>
            </div>
            <div class="incident-meta">${date} ${recorder}</div>
          </div>
          <span class="badge badge-${typeKey}">${r.incident_type}</span>
        </div>
        <div class="incident-desc">${esc(r.description)}</div>
        ${r.action_taken ? `<div class="incident-action">→ ${esc(r.action_taken)}</div>` : ''}
        <div class="incident-footer">
          <div class="incident-badges">
            ${classLabel}
            ${notifBadge}
          </div>
          <div>
            <button class="del-btn-sm" style="color:var(--primary); margin-right:12px;" onclick="openEditDisciplineModal(${r.id})">Edit</button>
            <button class="del-btn-sm" onclick="deleteRecord(${r.id})">Delete</button>
          </div>
        </div>
      </div>
    </div>`;
  }).join('');
}

// ── Log Record ────────────────────────────────────────────────────────────────
window.logRecord = async function() {
  const studentId  = document.getElementById('fStudent').value;
  const desc       = document.getElementById('fDesc').value.trim();
  const action     = document.getElementById('fAction').value.trim();
  const date       = document.getElementById('fDate').value;
  const notify     = document.getElementById('fNotify').checked;

  if (!studentId || !desc) {
    showStatus('⚠️ Please select a student and enter a description.', 'warning');
    return;
  }

  const payload = {
    student_id:    parseInt(studentId),
    incident_type: selectedType,
    description:   desc,
    action_taken:  action || null,
    incident_date: date ? new Date(date).toISOString() : null,
    notify_parent: notify,
  };

  document.getElementById('logBtn').disabled = true;

  try {
    const res = await fetch(`${API_BASE}/discipline/`, {
      method: 'POST', headers: J(), body: JSON.stringify(payload)
    });

    if (res.ok || res.status === 201) {
      const rec = await res.json();
      const label = selectedType === 'Commendation' ? 'Commendation' : 'Record';
      showStatus(`✅ ${label} logged${notify ? ' — parent notified' : ''}.`, 'success');
      // Reset form
      document.getElementById('fStudentSearch').value = '';
      document.getElementById('fStudent').value = '';
      document.getElementById('fDesc').value   = '';
      document.getElementById('fAction').value = '';
      document.getElementById('fDate').value   = todayISO();
      document.getElementById('studentQuick').classList.remove('visible');
      await Promise.all([loadSummary(), loadRecords()]);
    } else {
      const err = await res.json();
      showStatus(`❌ ${err.detail || 'Failed to log record.'}`, 'danger');
    }
  } catch (e) {
    showStatus('❌ Network error.', 'danger');
  } finally {
    document.getElementById('logBtn').disabled = false;
  }
};

// ── Delete Record ─────────────────────────────────────────────────────────────
window.deleteRecord = async function(id) {
  const rec = allRecords.find(r => r.id === id);
  if (!confirm(`Delete ${rec?.incident_type || 'this'} record for ${rec?.student_name || 'student'}?`)) return;

  try {
    const res = await fetch(`${API_BASE}/discipline/${id}`, { method: 'DELETE', headers: H() });
    if (res.ok || res.status === 204) {
      allRecords = allRecords.filter(r => r.id !== id);
      applyFilter();
      await loadSummary();
    }
  } catch (e) { console.error(e); }
};

// ── Utilities ─────────────────────────────────────────────────────────────────
function todayISO() {
  return new Date().toISOString().split('T')[0];
}

function esc(str) {
  if (!str) return '';
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function showStatus(msg, type = 'info') {
  const el = document.getElementById('logStatus');
  const colors = { success: 'var(--success)', danger: 'var(--danger)', warning: 'var(--warning)', info: 'var(--text-secondary)' };
  el.style.color = colors[type] || 'var(--text-secondary)';
  el.textContent = msg;
  setTimeout(() => { el.textContent = ''; }, 5000);
}

// ── Edit Record Modal controls ────────────────────────────────────────────────
window.openEditDisciplineModal = function(id) {
  const rec = allRecords.find(r => r.id === id);
  if (!rec) return;

  document.getElementById('editRecId').value = rec.id;
  document.getElementById('editStudentName').value = `${rec.student_name || '—'} (${rec.student_code || ''})`;
  document.getElementById('editIncidentType').value = rec.incident_type;
  
  if (rec.incident_date) {
    document.getElementById('editIncidentDate').value = rec.incident_date.split('T')[0];
  } else {
    document.getElementById('editIncidentDate').value = '';
  }
  
  document.getElementById('editDesc').value = rec.description || '';
  document.getElementById('editAction').value = rec.action_taken || '';
  document.getElementById('editStatusMsg').textContent = '';
  
  document.getElementById('editDisciplineModal').classList.add('open');
};

window.closeEditDisciplineModal = function() {
  document.getElementById('editDisciplineModal').classList.remove('open');
};

window.saveEditDiscipline = async function(event) {
  event.preventDefault();
  const id = document.getElementById('editRecId').value;
  const incidentType = document.getElementById('editIncidentType').value;
  const dateVal = document.getElementById('editIncidentDate').value;
  const desc = document.getElementById('editDesc').value.trim();
  const action = document.getElementById('editAction').value.trim();

  const payload = {
    incident_type: incidentType,
    incident_date: dateVal ? new Date(dateVal).toISOString() : null,
    description: desc,
    action_taken: action || null
  };

  try {
    const res = await fetch(`${API_BASE}/discipline/${id}`, {
      method: 'PUT',
      headers: J(),
      body: JSON.stringify(payload)
    });

    if (res.ok) {
      const el = document.getElementById('editStatusMsg');
      el.style.color = 'var(--success)';
      el.textContent = '✔ Disciplinary record updated.';
      setTimeout(async () => {
        closeEditDisciplineModal();
        await Promise.all([loadSummary(), loadRecords()]);
      }, 500);
    } else {
      const err = await res.json();
      const el = document.getElementById('editStatusMsg');
      el.style.color = 'var(--danger)';
      el.textContent = `❌ ${err.detail || 'Failed to update record.'}`;
    }
  } catch (e) {
    const el = document.getElementById('editStatusMsg');
    el.style.color = 'var(--danger)';
    el.textContent = '❌ Network error.';
  }
};

// ── Bootstrap ─────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', init);

window.printSelectedStudentConductReport = function() {
  const fStudent = document.getElementById('fStudent');
  const studentId = fStudent ? parseInt(fStudent.value) : 0;
  
  let targetStudent = null;
  let recordsForStudent = allRecords;

  if (studentId) {
    targetStudent = allStudents.find(s => s.id === studentId);
    recordsForStudent = allRecords.filter(r => r.student_id === studentId);
  }

  const schoolName = localStorage.getItem('school_name') || 'REPUBLIC OF GHANA';
  const studentName = targetStudent ? targetStudent.full_name : 'All Enrolled Students';
  const studentCode = targetStudent ? targetStudent.student_code : 'GH-NETWORK';
  const className = targetStudent ? (targetStudent.class_name || 'N/A') : 'All Classes';

  const rows = recordsForStudent.map(r => `
    <tr>
      <td style="padding:6px; border-bottom:1px solid #ccc;">${r.incident_date || 'N/A'}</td>
      <td style="padding:6px; border-bottom:1px solid #ccc;"><strong>${r.student_name}</strong> (${r.student_code})</td>
      <td style="padding:6px; border-bottom:1px solid #ccc;">${r.incident_type}</td>
      <td style="padding:6px; border-bottom:1px solid #ccc;">${r.description || 'N/A'}</td>
      <td style="padding:6px; border-bottom:1px solid #ccc;">${r.action_taken || 'N/A'}</td>
    </tr>
  `).join('');

  const win = window.open('', '_blank', 'width=750,height=600');
  win.document.write(`
    <html>
      <head>
        <title>Conduct Certificate - ${studentName}</title>
        <style>
          body { font-family: sans-serif; padding: 24px; color: #000; }
          h2 { text-transform: uppercase; margin: 0; }
          table { width: 100%; border-collapse: collapse; margin-top: 16px; font-size: 0.85rem; }
          th { text-align: left; background: #f1f5f9; padding: 8px; border-bottom: 2px solid #000; }
        </style>
      </head>
      <body>
        <div style="text-align:center; border-bottom:2px solid #000; padding-bottom:12px; margin-bottom:16px;">
          <h2>${schoolName}</h2>
          <div style="font-size:0.9rem; font-weight:bold; margin-top:4px;">OFFICIAL STUDENT CONDUCT & DISCIPLINE REPORT</div>
          <div style="font-size:0.8rem; margin-top:4px;">Student: <strong>${studentName}</strong> | Code: <strong>${studentCode}</strong> | Class: <strong>${className}</strong></div>
        </div>
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>Student</th>
              <th>Type</th>
              <th>Incident Description</th>
              <th>Sanction / Action Taken</th>
            </tr>
          </thead>
          <tbody>
            ${rows || '<tr><td colspan="5" style="text-align:center; padding:12px;">No disciplinary records found. Clean conduct profile.</td></tr>'}
          </tbody>
        </table>
        <div style="margin-top:40px; display:flex; justify-content:space-between; font-size:0.85rem;">
          <div>_______________________<br>Discipline Committee Lead</div>
          <div>_______________________<br>Headmaster / Principal</div>
        </div>
        <script>window.onload = function() { window.print(); setTimeout(function() { window.close(); }, 500); };</script>
      </body>
    </html>
  `);
  win.document.close();
};
