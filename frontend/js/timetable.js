// ── Config & Auth ────────────────────────────────────────────────────────────
const API_BASE = window.API_BASE || (window.location.origin.includes('http') ? (window.location.origin + '/api') : 'http://127.0.0.1:8000/api');
const token = localStorage.getItem('accessToken');
if (!token) window.location.href = 'auth.html';

function H(extra = {}) { return { 'Authorization': `Bearer ${token}`, ...extra }; }
function J(extra = {}) { return H({ 'Content-Type': 'application/json', ...extra }); }

// ── Constants ────────────────────────────────────────────────────────────────
const DAYS     = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'];
const PERIODS  = [1, 2, 3, 4, 5, 6, 7, 8];
const COLORS   = ['#818cf8','#34d399','#fbbf24','#f87171','#22d3ee','#a78bfa','#fb923c','#4ade80'];

// ── State ────────────────────────────────────────────────────────────────────
let allClasses   = [];
let allSubjects  = [];
let allTeachers  = [];
let allSemesters = [];
let currentView  = 'class';   // 'class' | 'teacher'
let subjectColorMap = {};     // subject_id → color index

// ── Init ─────────────────────────────────────────────────────────────────────
async function init() {
  await Promise.all([loadClasses(), loadSubjects(), loadTeachers(), loadSemesters()]);
  populateFormDropdowns();
  // Auto-select first class for view
  if (allClasses.length) {
    document.getElementById('viewClassSelect').value = allClasses[0].id;
    await loadClassView();
  }
  await checkConflicts();
}

// ── Data Loaders ─────────────────────────────────────────────────────────────
async function loadClasses() {
  const res = await fetch(`${API_BASE}/classes/my-classes`, { headers: H() });
  if (!res.ok) return;
  allClasses = await res.json();
}

async function loadSubjects() {
  const schoolId = localStorage.getItem('school_id');
  const headers = schoolId ? { 'Authorization': `Bearer ${token}`, 'X-School-Id': schoolId } : H();
  const res = await fetch(`${API_BASE}/subjects/`, { headers });
  if (!res.ok) return;
  allSubjects = await res.json();
  // Assign stable colours to subjects
  allSubjects.forEach((s, i) => { subjectColorMap[s.id] = i % COLORS.length; });
}

async function loadTeachers() {
  const res = await fetch(`${API_BASE}/auth/users`, { headers: H() });
  if (!res.ok) return;
  const users = await res.json();
  allTeachers = users.filter(u => u.roles && u.roles.some(r => r === 'teacher' || r.name === 'teacher'));
  if (!allTeachers.length) allTeachers = users; // fallback: show all users
}

async function loadSemesters() {
  const res = await fetch(`${API_BASE}/academic/semesters`, { headers: H() });
  if (!res.ok) return;
  allSemesters = await res.json();
}

// ── Populate Form Dropdowns ───────────────────────────────────────────────────
function populateFormDropdowns() {
  // Classes
  const classOpts = '<option value="">Select class...</option>' +
    allClasses.map(c => `<option value="${c.id}">${esc(c.name)}</option>`).join('');
  document.getElementById('fClass').innerHTML = classOpts;
  document.getElementById('viewClassSelect').innerHTML = classOpts;

  // Subjects
  document.getElementById('fSubject').innerHTML =
    '<option value="">Select subject...</option>' +
    allSubjects.map(s => `<option value="${s.id}">${esc(s.name)}</option>`).join('');

  // Teachers
  document.getElementById('fTeacher').innerHTML =
    '<option value="">No teacher assigned</option>' +
    allTeachers.map(t => `<option value="${t.id}">${esc(t.username)}</option>`).join('');

  // Semesters
  const semOpts = '<option value="">Any / All semesters</option>' +
    allSemesters.map(s => `<option value="${s.id}">${esc(s.name)}</option>`).join('');
  document.getElementById('fSemester').innerHTML = semOpts;

  const viewSemOpts = '<option value="">All Semesters</option>' +
    allSemesters.map(s => `<option value="${s.id}">${esc(s.name)}</option>`).join('');
  document.getElementById('viewSemesterSelect').innerHTML = viewSemOpts;

  // Teacher select in teacher-view controls
  document.getElementById('viewTeacherSelect').innerHTML =
    '<option value="">Select teacher...</option>' +
    allTeachers.map(t => `<option value="${t.id}">${esc(t.username)}</option>`).join('');
}

// ── View Toggle ───────────────────────────────────────────────────────────────
window.switchView = function(mode) {
  currentView = mode;
  document.getElementById('vBtnClass').classList.toggle('active', mode === 'class');
  document.getElementById('vBtnTeacher').classList.toggle('active', mode === 'teacher');
  document.getElementById('classControls').style.display   = mode === 'class'   ? 'flex' : 'none';
  document.getElementById('teacherControls').style.display = mode === 'teacher' ? 'flex' : 'none';
  document.getElementById('leftPanel').style.display       = mode === 'class'   ? 'block' : 'none';
  document.getElementById('gridContainer').innerHTML = '<div class="empty-state">Select a class or teacher above.</div>';
  document.getElementById('subjectLegend').innerHTML = '';
  if (mode === 'teacher') document.getElementById('addStatus').textContent = '';
};

// ── Class timetable sync when form class changes ───────────────────────────
window.onClassChange = function() {
  const cid = document.getElementById('fClass').value;
  document.getElementById('viewClassSelect').value = cid;
  if (cid) loadClassView();
};

// ── Load Class Timetable Grid ────────────────────────────────────────────────
window.loadClassView = async function() {
  const classId    = document.getElementById('viewClassSelect').value;
  const semesterId = document.getElementById('viewSemesterSelect').value;
  if (!classId) {
    document.getElementById('gridContainer').innerHTML = '<div class="empty-state">Select a class to view its timetable.</div>';
    return;
  }

  let url = `${API_BASE}/timetable/class/${classId}`;
  if (semesterId) url += `?semester_id=${semesterId}`;

  const res = await fetch(url, { headers: H() });
  if (!res.ok) {
    document.getElementById('gridContainer').innerHTML = '<div class="empty-state">Failed to load timetable.</div>';
    return;
  }
  const slots = await res.json();
  renderGrid(slots, 'class');
  renderLegend(slots);
};

// ── Load Teacher Schedule ────────────────────────────────────────────────────
window.loadTeacherView = async function() {
  const teacherId = document.getElementById('viewTeacherSelect').value;
  if (!teacherId) {
    document.getElementById('gridContainer').innerHTML = '<div class="empty-state">Select a teacher to view their schedule.</div>';
    return;
  }

  const res = await fetch(`${API_BASE}/timetable/teacher/${teacherId}`, { headers: H() });
  if (!res.ok) {
    document.getElementById('gridContainer').innerHTML = '<div class="empty-state">Failed to load schedule.</div>';
    return;
  }
  const slots = await res.json();
  renderGrid(slots, 'teacher');
  renderLegend(slots);
};

// ── Render Grid ───────────────────────────────────────────────────────────────
function renderGrid(slots, viewMode) {
  // Build lookup: day → period → slot
  const map = {};
  slots.forEach(s => {
    if (!map[s.day_of_week]) map[s.day_of_week] = {};
    map[s.day_of_week][s.period_number] = s;
  });

  // Determine which periods to show (show all 8 or just filled ones + 1 empty)
  const usedPeriods = new Set(slots.map(s => s.period_number));
  const maxPeriod = usedPeriods.size ? Math.max(...usedPeriods, 6) : 6;
  const visiblePeriods = Array.from({length: maxPeriod}, (_, i) => i + 1);

  let html = `<table class="tt-table"><thead><tr>
    <th>Period</th>
    ${DAYS.map(d => `<th>${d}</th>`).join('')}
  </tr></thead><tbody>`;

  visiblePeriods.forEach(p => {
    html += `<tr><td>P${p}</td>`;
    DAYS.forEach((_, dayIdx) => {
      const slot = map[dayIdx]?.[p];
      if (slot) {
        const colorIdx = subjectColorMap[slot.subject_id] ?? 0;
        const color = COLORS[colorIdx];
        const timeStr = slot.start_time && slot.end_time
          ? `${slot.start_time} – ${slot.end_time}` : '';
        const extra = viewMode === 'teacher'
          ? `<div class="slot-room" style="color:var(--secondary);">${esc(slot.class_name || '')}</div>`
          : (slot.teacher_name ? `<div class="slot-teacher">👤 ${esc(slot.teacher_name)}</div>` : '');

        html += `<td>
          <div class="slot-cell filled" style="border-left-color:${color};"
               onclick="openEdit(${slot.id}, ${dayIdx}, ${p})">
            <button class="del-btn" onclick="deleteSlot(event, ${slot.id})">✕</button>
            <div class="slot-subject" style="color:${color};">${esc(slot.subject_name || '—')}</div>
            ${extra}
            ${timeStr ? `<div class="slot-time">${timeStr}</div>` : ''}
            ${slot.room ? `<div class="slot-room">${esc(slot.room)}</div>` : ''}
          </div></td>`;
      } else {
        html += `<td>
          <div class="slot-cell empty" onclick="prefill(${dayIdx}, ${p})">
            <span class="slot-add">+</span>
          </div></td>`;
      }
    });
    html += '</tr>';
  });
  html += '</tbody></table>';
  document.getElementById('gridContainer').innerHTML = html;
}

// ── Legend ───────────────────────────────────────────────────────────────────
function renderLegend(slots) {
  const seenIds = new Set();
  const items = [];
  slots.forEach(s => {
    if (!seenIds.has(s.subject_id)) {
      seenIds.add(s.subject_id);
      const color = COLORS[subjectColorMap[s.subject_id] ?? 0];
      items.push(`<div class="legend-item">
        <div class="legend-dot" style="background:${color};"></div>
        <span>${esc(s.subject_name || '')}</span></div>`);
    }
  });
  document.getElementById('subjectLegend').innerHTML = items.join('');
}

// ── Prefill form when clicking empty cell ─────────────────────────────────────
window.prefill = function(day, period) {
  document.getElementById('fDay').value    = day;
  document.getElementById('fPeriod').value = period;
  document.getElementById('fClass').value  = document.getElementById('viewClassSelect').value;
  document.getElementById('addStatus').textContent = '';
  // Scroll to form
  document.getElementById('leftPanel').scrollIntoView({ behavior: 'smooth', block: 'start' });
};

// ── Open Edit (future enhancement placeholder) ─────────────────────────────
window.openEdit = function(slotId, day, period) {
  // Currently a no-op — clicking a filled cell doesn't open anything
  // (use the ✕ button to delete and re-add)
};

// ── Add Slot ──────────────────────────────────────────────────────────────────
window.addSlot = async function() {
  const classId    = document.getElementById('fClass').value;
  const subjectId  = document.getElementById('fSubject').value;
  const teacherId  = document.getElementById('fTeacher').value;
  const semesterId = document.getElementById('fSemester').value;
  const day        = parseInt(document.getElementById('fDay').value);
  const period     = parseInt(document.getElementById('fPeriod').value);
  const start      = document.getElementById('fStart').value;
  const end        = document.getElementById('fEnd').value;
  const room       = document.getElementById('fRoom').value.trim();

  if (!classId || !subjectId) {
    showStatus('⚠️ Please select a class and subject.', 'warning');
    return;
  }

  const payload = {
    class_section_id: parseInt(classId),
    subject_id:       parseInt(subjectId),
    teacher_id:       teacherId  ? parseInt(teacherId)  : null,
    semester_id:      semesterId ? parseInt(semesterId) : null,
    day_of_week:      day,
    period_number:    period,
    start_time:       start || null,
    end_time:         end   || null,
    room:             room  || null,
  };

  document.getElementById('addBtn').disabled = true;
  document.getElementById('addBtn').textContent = 'Adding...';

  try {
    const res = await fetch(`${API_BASE}/timetable/`, {
      method: 'POST', headers: J(), body: JSON.stringify(payload)
    });

    if (res.ok || res.status === 201) {
      showStatus('✅ Slot added!', 'success');
      // Sync the view class selector and refresh grid
      document.getElementById('viewClassSelect').value = classId;
      await loadClassView();
      await checkConflicts();
    } else {
      const err = await res.json();
      showStatus(`❌ ${err.detail || 'Failed to add slot.'}`, 'danger');
    }
  } catch (e) {
    showStatus('❌ Network error.', 'danger');
  } finally {
    document.getElementById('addBtn').disabled = false;
    document.getElementById('addBtn').textContent = 'Add to Timetable';
  }
};

// ── Delete Slot ───────────────────────────────────────────────────────────────
window.deleteSlot = async function(event, slotId) {
  event.stopPropagation();  // prevent prefill from firing
  const ok = await (window.showConfirmDialog ? window.showConfirmDialog(
    '🗑️ Remove Timetable Slot',
    'Are you sure you want to remove this timetable slot?',
    'Remove Slot',
    'Cancel',
    'warning'
  ) : Promise.resolve(confirm('Remove this timetable slot?')));

  if (!ok) return;

  const res = await fetch(`${API_BASE}/timetable/${slotId}`, {
    method: 'DELETE', headers: H()
  });

  if (res.ok || res.status === 204) {
    if (window.showToast) window.showToast('Timetable slot removed.', 'info');
    if (currentView === 'class') await loadClassView();
    else await loadTeacherView();
    await checkConflicts();
  }
};

// ── Clear Class Timetable ─────────────────────────────────────────────────────
window.clearClassTimetable = async function() {
  const classId = document.getElementById('fClass').value;
  if (!classId) {
    showStatus('⚠️ Select a class first.', 'warning');
    return;
  }
  const cls = allClasses.find(c => String(c.id) === classId);
  const ok = await (window.showConfirmDialog ? window.showConfirmDialog(
    '🗑️ Clear Class Timetable',
    `Clear ALL timetable periods and slots for ${cls?.name || 'this class'}? This cannot be undone.`,
    'Clear All Slots',
    'Cancel',
    'warning'
  ) : Promise.resolve(confirm(`Clear ALL timetable slots for ${cls?.name || 'this class'}? This cannot be undone.`)));

  if (!ok) return;

  const res = await fetch(`${API_BASE}/timetable/class/${classId}`, {
    method: 'DELETE', headers: H()
  });

  if (res.ok || res.status === 204) {
    showStatus('✅ Timetable cleared.', 'success');
    await loadClassView();
  }
};

// ── Conflict Detection ────────────────────────────────────────────────────────
async function checkConflicts() {
  try {
    const res = await fetch(`${API_BASE}/timetable/conflicts`, { headers: H() });
    if (!res.ok) return;
    const conflicts = await res.json();
    const el = document.getElementById('conflictAlert');
    if (conflicts.length > 0) {
      el.classList.add('visible');
      el.innerHTML = `⚠️ <strong>${conflicts.length} conflict(s) detected:</strong><br>` +
        conflicts.map(c =>
          `${c.teacher_name} is double-booked on ${c.day} Period ${c.period}`
        ).join('<br>');
    } else {
      el.classList.remove('visible');
    }
  } catch (e) { /* silent fail */ }
}

// ── Utilities ─────────────────────────────────────────────────────────────────
function esc(str) {
  if (!str) return '';
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function showStatus(msg, type = 'info') {
  const el = document.getElementById('addStatus');
  const colors = { success: 'var(--success)', danger: 'var(--danger)', warning: 'var(--warning)', info: 'var(--text-secondary)' };
  el.style.color = colors[type] || 'var(--text-secondary)';
  el.textContent = msg;
  setTimeout(() => { el.textContent = ''; }, 5000);
}

// ── Bootstrap ─────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', init);
