// ── Config & Auth ────────────────────────────────────────────────────────────
var API_BASE = window.API_BASE || (window.location.origin.includes('http') ? (window.location.origin + '/api') : 'http://127.0.0.1:8000/api');
var token = sessionStorage.getItem('accessToken') || localStorage.getItem('accessToken') || localStorage.getItem('token');
if (!token && !window.location.pathname.includes('auth.html')) window.location.href = 'auth.html';

// ── Toast Notification System (UX-1 FIX: replaces all alert() calls) ─────────
if (!document.getElementById('_ttToastStyle')) {
  const _s = document.createElement('style');
  _s.id = '_ttToastStyle';
  _s.textContent = `
    #_ttToastContainer { position:fixed; bottom:24px; right:24px; z-index:99999; display:flex; flex-direction:column; gap:10px; pointer-events:none; }
    ._ttToast { pointer-events:all; min-width:280px; max-width:400px; padding:12px 18px; border-radius:10px; font-size:0.86rem; font-weight:600;
      display:flex; align-items:center; gap:10px; box-shadow:0 8px 32px rgba(0,0,0,0.35); animation:_ttSlideIn 0.3s ease;
      border-left:4px solid transparent; backdrop-filter:blur(12px); }
    ._ttToast.success { background:rgba(16,185,129,0.15); border-color:#10b981; color:#34d399; }
    ._ttToast.error   { background:rgba(239,68,68,0.15);  border-color:#ef4444; color:#f87171; }
    ._ttToast.warning { background:rgba(245,158,11,0.15); border-color:#f59e0b; color:#fbbf24; }
    ._ttToast.info    { background:rgba(99,102,241,0.15); border-color:#6366f1; color:#a5b4fc; }
    @keyframes _ttSlideIn { from { opacity:0; transform:translateX(40px); } to { opacity:1; transform:translateX(0); } }
    @keyframes _ttSlideOut { from { opacity:1; transform:translateX(0); } to { opacity:0; transform:translateX(40px); } }
  `;
  document.head.appendChild(_s);
}
if (!document.getElementById('_ttToastContainer')) {
  const _c = document.createElement('div');
  _c.id = '_ttToastContainer';
  document.body.appendChild(_c);
}
window.showToast = function(message, type = 'info', duration = 4000) {
  const c = document.getElementById('_ttToastContainer');
  const icons = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' };
  const t = document.createElement('div');
  t.className = `_ttToast ${type}`;
  t.innerHTML = `<span>${icons[type] || 'ℹ️'}</span><span style="flex:1;">${message}</span>`;
  c.appendChild(t);
  setTimeout(() => {
    t.style.animation = '_ttSlideOut 0.3s ease forwards';
    setTimeout(() => t.remove(), 310);
  }, duration);
};
// Keep window.showToast available to staff-conflicts.js and other modules
if (!window.showToast) window.showToast = showToast;

function H(extra = {}) {
  const currentToken = sessionStorage.getItem('accessToken') || localStorage.getItem('accessToken') || localStorage.getItem('token');
  const h = { 'Authorization': `Bearer ${currentToken}`, ...extra };
  const schId = sessionStorage.getItem('selectedSchoolId') || sessionStorage.getItem('school_id') || localStorage.getItem('school_id');
  if (schId && schId !== 'all') h['X-School-Id'] = String(schId);
  return h;
}
function J(extra = {}) { return H({ 'Content-Type': 'application/json', ...extra }); }

// ── Constants ────────────────────────────────────────────────────────────────
const DAYS     = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'];
const PERIODS  = [1, 2, 3, 4, 5, 6, 7, 8];
const COLORS   = ['#818cf8','#34d399','#fbbf24','#f87171','#22d3ee','#a78bfa','#fb923c','#4ade80'];

// ── State ────────────────────────────────────────────────────────────────────
let allClasses       = [];
let allSubjects      = [];
let allTeachers      = [];
let allSemesters     = [];
let currentView      = 'class';   // 'class' | 'teacher' | 'radar' | 'workloads'
let subjectColorMap  = {};
let profileConfig    = null;
let currentEditingSlotId = null;

// ── Init ─────────────────────────────────────────────────────────────────────
async function init() {
  await Promise.all([
    loadProfileConfig(),
    loadClasses(),
    loadSubjects(),
    loadTeachers(),
    loadSemesters()
  ]);

  populateFormDropdowns();

  // Auto-select first class for view
  if (allClasses.length) {
    document.getElementById('viewClassSelect').value = allClasses[0].id;
    await loadClassView();
  }
  await checkConflicts();
  await checkSnapshotStatus();
}

// ── Profile Config Loader ───────────────────────────────────────────────────
async function loadProfileConfig() {
  try {
    const res = await fetch(`${API_BASE}/timetable/profile-config`, { headers: H() });
    if (!res.ok) return;
    profileConfig = await res.json();

    // Populate preferences inputs
    if (document.getElementById('prefStartTime')) {
      document.getElementById('prefStartTime').value = profileConfig.start_time || '08:00';
      document.getElementById('prefDuration').value = profileConfig.period_duration_minutes || 45;
      document.getElementById('prefMonThu').value = profileConfig.periods_per_day || 8;
      document.getElementById('prefFri').value = profileConfig.friday_periods || 6;
    }
  } catch (err) {
    console.error('Failed to load timetable profile config:', err);
  }
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
  allSubjects.forEach((s, i) => { subjectColorMap[s.id] = i % COLORS.length; });
}

async function loadTeachers() {
  const res = await fetch(`${API_BASE}/auth/users`, { headers: H() });
  if (!res.ok) return;
  const users = await res.json();

  // Superadmin is a global platform account and is excluded from school teacher rosters
  allTeachers = users.filter(u => {
    const roles = (u.roles || []).map(r => (typeof r === 'string' ? r : (r.name || '')).toLowerCase());
    if (roles.includes('super_admin') || u.is_superadmin) return false;
    return roles.some(r => ['teacher', 'admin', 'headmaster', 'bursar', 'school_administrator', 'secretary', 'school_secretary'].includes(r));
  });

  if (!allTeachers.length) {
    allTeachers = users.filter(u => {
      const roles = (u.roles || []).map(r => (typeof r === 'string' ? r : (r.name || '')).toLowerCase());
      return !roles.includes('super_admin') && !u.is_superadmin;
    });
  }
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
  document.getElementById('viewClassSelect').innerHTML = classOpts;

  // Subjects in quick modal
  const subjectOpts = '<option value="">Select subject...</option>' +
    allSubjects.map(s => `<option value="${s.id}">${esc(s.name)}</option>`).join('');
  if (document.getElementById('mSlotSubject')) {
    document.getElementById('mSlotSubject').innerHTML = subjectOpts;
  }

  // Teachers in quick modal
  const teacherOpts = '<option value="">No teacher assigned</option>' +
    allTeachers.map(t => `<option value="${t.id}">${esc(t.username)}</option>`).join('');
  if (document.getElementById('mSlotTeacher')) {
    document.getElementById('mSlotTeacher').innerHTML = teacherOpts;
  }

  // Semesters
  const semOpts = '<option value="">All Semesters</option>' +
    allSemesters.map(s => `<option value="${s.id}">${esc(s.name)}</option>`).join('');
  document.getElementById('viewSemesterSelect').innerHTML = semOpts;
  if (document.getElementById('agSemesterSelect')) {
    document.getElementById('agSemesterSelect').innerHTML = semOpts;
  }

  // Teacher select in teacher-view controls & handover
  const viewTeacherOpts = '<option value="">Select teacher...</option>' +
    allTeachers.map(t => `<option value="${t.id}">${esc(t.username)}</option>`).join('');
  document.getElementById('viewTeacherSelect').innerHTML = viewTeacherOpts;

  if (document.getElementById('hoOutgoingTeacher')) {
    document.getElementById('hoOutgoingTeacher').innerHTML = viewTeacherOpts;
    document.getElementById('hoIncomingTeacher').innerHTML = viewTeacherOpts;
  }
  // UX-3 FIX: Auto-select current active semester so conflicts and views are
  // immediately scoped to the right semester (not "All Semesters" which mixes data).
  const _currentSem = allSemesters.find(s => s.is_current);
  if (_currentSem) {
    const _semSel = document.getElementById('viewSemesterSelect');
    if (_semSel) _semSel.value = String(_currentSem.id);
    const _agSemSel = document.getElementById('agSemesterSelect');
    if (_agSemSel) _agSemSel.value = String(_currentSem.id);
  }
}

// ── View Toggle ───────────────────────────────────────────────────────────────
// ── Radar auto-refresh timer (UX-5 FIX) ─────────────────────────────────────
let _radarRefreshTimer = null;

window.switchView = function(mode) {
  currentView = mode;
  document.getElementById('vBtnClass').classList.toggle('active', mode === 'class');
  document.getElementById('vBtnTeacher').classList.toggle('active', mode === 'teacher');
  document.getElementById('vBtnRadar').classList.toggle('active', mode === 'radar');
  document.getElementById('vBtnWorkloads').classList.toggle('active', mode === 'workloads');

  const isSchedule = (mode === 'class' || mode === 'teacher');
  document.getElementById('filterControlsCard').style.display = isSchedule ? 'block' : 'none';
  document.getElementById('scheduleSection').style.display   = isSchedule ? 'block' : 'none';
  document.getElementById('radarSection').style.display      = mode === 'radar' ? 'block' : 'none';
  document.getElementById('workloadsSection').style.display  = mode === 'workloads' ? 'block' : 'none';

  // UX-5 FIX: Clear radar auto-refresh when leaving radar tab
  if (mode !== 'radar' && _radarRefreshTimer) {
    clearInterval(_radarRefreshTimer);
    _radarRefreshTimer = null;
  }

  if (isSchedule) {
    document.getElementById('classControls').style.display   = mode === 'class'   ? 'flex' : 'none';
    document.getElementById('teacherControls').style.display = mode === 'teacher' ? 'flex' : 'none';
    if (mode === 'class') loadClassView();
    else loadTeacherView();
  } else if (mode === 'radar') {
    loadCampusRadar();
    // UX-5 FIX: Auto-refresh Campus Radar every 60 seconds
    _radarRefreshTimer = setInterval(loadCampusRadar, 60000);
  } else if (mode === 'workloads') {
    loadTeacherWorkloads();
  }
};

// ── Load Class Timetable Grid ────────────────────────────────────────────────
window.loadClassView = async function() {
  const classId    = document.getElementById('viewClassSelect').value;
  const semesterId = document.getElementById('viewSemesterSelect').value;
  if (!classId) {
    document.getElementById('gridContainer').innerHTML = '<div class="empty-state" style="text-align:center; padding:40px; color:var(--text-secondary);">Select a class to view its timetable.</div>';
    return;
  }

  // UX-2 FIX: Show skeleton loader immediately while fetching
  document.getElementById('gridContainer').innerHTML = `
    <div style="display:grid; grid-template-columns:80px repeat(5,1fr); gap:6px; padding:10px; opacity:0.5; pointer-events:none;">
      ${Array(48).fill('<div style="height:52px; border-radius:8px; background:var(--glass-bg,rgba(255,255,255,0.05)); animation:pulse 1.5s ease infinite;"></div>').join('')}
    </div>`;

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
    document.getElementById('gridContainer').innerHTML = '<div class="empty-state" style="text-align:center; padding:40px; color:var(--text-secondary);">Select a teacher to view their schedule.</div>';
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
  const map = {};
  slots.forEach(s => {
    if (!map[s.day_of_week]) map[s.day_of_week] = {};
    map[s.day_of_week][s.period_number] = s;
  });

  // Build period time label map from actual slot data
  const periodTimeMap = {};
  slots.forEach(s => {
    if (s.start_time && s.end_time) {
      periodTimeMap[s.period_number] = `${s.start_time}–${s.end_time}`;
    }
  });

  const usedPeriods = new Set(slots.map(s => s.period_number));
  const maxPeriod = usedPeriods.size ? Math.max(...usedPeriods, 6) : 8;
  const visiblePeriods = Array.from({length: maxPeriod}, (_, i) => i + 1);

  let html = `<table class="tt-table"><thead><tr>
    <th>Period</th>
    ${DAYS.map(d => `<th>${d}</th>`).join('')}
  </tr></thead><tbody>`;

  visiblePeriods.forEach(p => {
    const timeLabel = periodTimeMap[p] ? `<div style="font-size:0.68rem; color:var(--text-secondary); font-weight:400; margin-top:2px;">${periodTimeMap[p]}</div>` : '';
    html += `<tr><td>Period ${p}${timeLabel}</td>`;
    DAYS.forEach((_, dayIdx) => {
      const slot = map[dayIdx]?.[p];
      if (slot) {
        const colorIdx = subjectColorMap[slot.subject_id] ?? 0;
        const color = COLORS[colorIdx];
        const timeStr = slot.start_time && slot.end_time ? `${slot.start_time} – ${slot.end_time}` : '';
        const extra = viewMode === 'teacher'
          ? `<div class="slot-room" style="color:#38bdf8; font-weight:700;">🏫 ${esc(slot.class_name || '')}</div>`
          : (slot.teacher_name ? `<div class="slot-teacher">👤 ${esc(slot.teacher_name)}</div>` : '');

        html += `<td>
          <div class="slot-cell filled" style="border-left-color:${color}; cursor:pointer;" onclick="openEditSlot(${JSON.stringify(slot).replace(/"/g, '&quot;')})">
            <button class="del-btn" onclick="deleteSlot(event, ${slot.id})">✕</button>
            <div class="slot-subject" style="color:${color};">${esc(slot.subject_name || '—')}</div>
            ${extra}
            ${timeStr ? `<div class="slot-time">${timeStr}</div>` : ''}
            ${slot.room ? `<div class="slot-room">📍 ${esc(slot.room)}</div>` : ''}
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

// ── Quick Slot Edit/Add Modal ────────────────────────────────────────────────
window.prefill = function(day, period) {
  const classId = document.getElementById('viewClassSelect').value;
  if (!classId) {
    alert('Please select a Class Section first.');
    return;
  }
  currentEditingSlotId = null;
  document.getElementById('slotModalTitle').textContent = `➕ Add Slot – ${DAYS[day]} Period ${period}`;
  document.getElementById('mSlotDay').value = day;
  document.getElementById('mSlotPeriod').value = period;
  document.getElementById('mSlotSubject').value = '';
  document.getElementById('mSlotTeacher').value = '';
  document.getElementById('mSlotRoom').value = '';
  document.getElementById('mSlotStatus').textContent = '';
  // Filter subjects to those assigned to this class
  _populateClassSubjects(parseInt(classId));
  document.getElementById('slotEditModal').classList.add('open');
};

window.openEditSlot = function(slot) {
  currentEditingSlotId = slot.id;
  document.getElementById('slotModalTitle').textContent = `✏️ Edit Slot – ${DAYS[slot.day_of_week]} Period ${slot.period_number}`;
  document.getElementById('mSlotDay').value = slot.day_of_week;
  document.getElementById('mSlotPeriod').value = slot.period_number;
  document.getElementById('mSlotTeacher').value = slot.teacher_id || '';
  document.getElementById('mSlotRoom').value = slot.room || '';
  document.getElementById('mSlotStatus').textContent = '';
  // Filter subjects to class, then pre-select the current subject
  const classId = document.getElementById('viewClassSelect').value;
  _populateClassSubjects(parseInt(classId), slot.subject_id);
  document.getElementById('slotEditModal').classList.add('open');
};

// Populate subject dropdown filtered to a specific class
function _populateClassSubjects(classId, selectedSubjectId = null) {
  // Find subjects that appear in the current class timetable or are assigned to it
  const cls = allClasses.find(c => c.id === classId);
  const classSubjectIds = new Set();

  // Try to derive from current rendered slots in the grid
  document.querySelectorAll('.slot-subject').forEach(el => {
    // We don't have subject IDs from DOM easily, so fall back to allSubjects
  });

  // If class has a subjects array (from /my-classes), filter by that
  let subjectsToShow = allSubjects;
  if (cls && Array.isArray(cls.subjects) && cls.subjects.length > 0) {
    const csids = new Set(cls.subjects.map(s => s.id));
    subjectsToShow = allSubjects.filter(s => csids.has(s.id));
    if (!subjectsToShow.length) subjectsToShow = allSubjects; // fallback
  }

  const opts = '<option value="">Select subject...</option>' +
    subjectsToShow.map(s =>
      `<option value="${s.id}"${selectedSubjectId === s.id ? ' selected' : ''}>${esc(s.name)}</option>`
    ).join('');
  document.getElementById('mSlotSubject').innerHTML = opts;
}

window.closeSlotModal = function() {
  document.getElementById('slotEditModal').classList.remove('open');
};

window.saveSlotFromModal = async function() {
  const classId = document.getElementById('viewClassSelect').value;
  const day = parseInt(document.getElementById('mSlotDay').value);
  const period = parseInt(document.getElementById('mSlotPeriod').value);
  const subjectId = document.getElementById('mSlotSubject').value;
  const teacherId = document.getElementById('mSlotTeacher').value;
  const room = document.getElementById('mSlotRoom').value.trim();
  const statusEl = document.getElementById('mSlotStatus');

  if (!subjectId) {
    statusEl.style.color = '#ef4444';
    statusEl.textContent = 'Please select a subject.';
    return;
  }

  const payload = {
    class_section_id: parseInt(classId),
    subject_id: parseInt(subjectId),
    teacher_id: teacherId ? parseInt(teacherId) : null,
    day_of_week: day,
    period_number: period,
    room: room || null
  };

  const btn = document.getElementById('mSlotSaveBtn');
  btn.disabled = true;
  btn.textContent = 'Saving...';

  try {
    let res;
    if (currentEditingSlotId) {
      res = await fetch(`${API_BASE}/timetable/${currentEditingSlotId}`, {
        method: 'PUT',
        headers: J(),
        body: JSON.stringify({
          subject_id: payload.subject_id,
          teacher_id: payload.teacher_id,
          room: payload.room
        })
      });
    } else {
      res = await fetch(`${API_BASE}/timetable/`, {
        method: 'POST',
        headers: J(),
        body: JSON.stringify(payload)
      });
    }

    if (res.ok || res.status === 200 || res.status === 201) {
      closeSlotModal();
      if (currentView === 'class') await loadClassView();
      else await loadTeacherView();
      await checkConflicts();
    } else {
      const err = await res.json();
      statusEl.style.color = '#ef4444';
      statusEl.textContent = `❌ ${err.detail || 'Failed to save slot.'}`;
    }
  } catch (err) {
    statusEl.style.color = '#ef4444';
    statusEl.textContent = '❌ Network error.';
  } finally {
    btn.disabled = false;
    btn.textContent = 'Save Slot';
  }
};

// ── Delete Slot ───────────────────────────────────────────────────────────────
window.deleteSlot = async function(event, slotId) {
  event.stopPropagation();
  const ok = confirm('Remove this timetable slot?');
  if (!ok) return;

  const res = await fetch(`${API_BASE}/timetable/${slotId}`, {
    method: 'DELETE', headers: H()
  });

  if (res.ok || res.status === 204) {
    if (currentView === 'class') await loadClassView();
    else await loadTeacherView();
    await checkConflicts();
  }
};

// ── Clear Class Timetable ─────────────────────────────────────────────────────
window.clearClassTimetable = async function() {
  const classId = document.getElementById('viewClassSelect').value;
  if (!classId) {
    alert('Select a class first.');
    return;
  }
  const cls = allClasses.find(c => String(c.id) === classId);
  const ok = confirm(`Clear ALL timetable slots for ${cls?.name || 'this class'}?`);
  if (!ok) return;

  const res = await fetch(`${API_BASE}/timetable/class/${classId}`, {
    method: 'DELETE', headers: H()
  });

  if (res.ok || res.status === 204) {
    await loadClassView();
  }
};

// ── Campus Working Hours & Live Dismissal Utilities ───────────────────────────
let workingHoursTarget = 8.0;

function formatClockTime(h, m) {
  const period = h >= 12 ? 'PM' : 'AM';
  const displayH = h % 12 === 0 ? 12 : h % 12;
  return `${String(displayH).padStart(2, '0')}:${String(m).padStart(2, '0')} ${period}`;
}

function calculateDismissalTime(startTimeStr, periods, durationMins, snackMins = 20, lunchMins = 40) {
  if (!startTimeStr || !startTimeStr.includes(':')) return '15:00';
  const [startH, startM] = startTimeStr.split(':').map(Number);
  const totalMins = (startH * 60 + startM) + (periods * durationMins) + snackMins + lunchMins;
  const endH = Math.floor(totalMins / 60) % 24;
  const endM = totalMins % 60;
  return `${String(endH).padStart(2, '0')}:${String(endM).padStart(2, '0')}`;
}

window.calcPreFlightTimes = function() {
  const startEl = document.getElementById('agStartTime');
  const durEl = document.getElementById('agDuration');
  const pMonThuEl = document.getElementById('agPeriodsPerDay');
  const pFriEl = document.getElementById('agFridayPeriods');
  const snackEl = document.getElementById('agSnackMins');
  const lunchEl = document.getElementById('agLunchMins');
  const worshipEl = document.getElementById('agWorshipDay');

  if (!startEl) return;

  const startTime = startEl.value || '08:00';
  const dur = parseInt(durEl.value) || 45;
  const pMonThu = parseInt(pMonThuEl.value) || 8;
  const pFri = parseInt(pFriEl.value) || 6;
  const snack = parseInt(snackEl ? snackEl.value : 20) || 20;
  const lunch = parseInt(lunchEl ? lunchEl.value : 40) || 40;
  const worship = worshipEl ? worshipEl.value : 'wed_p1';

  // Format Start Time
  const [sh, sm] = startTime.split(':').map(Number);
  const startClock = formatClockTime(sh, sm);
  document.getElementById('agSumStart').textContent = startClock;
  document.getElementById('agSumDuration').textContent = `${dur} mins`;

  // Calculated Dismissal Times
  const closeMonThu = calculateDismissalTime(startTime, pMonThu, dur, snack, lunch);
  const closeFri = calculateDismissalTime(startTime, pFri, dur, snack, lunch);
  document.getElementById('agSumCloseMonThu').textContent = closeMonThu;
  document.getElementById('agSumCloseFri').textContent = closeFri;

  // Pills
  document.getElementById('agSumPeriodsPill').textContent = `🔔 ${pMonThu} Mon-Thu | ${pFri} Fri`;
  document.getElementById('agSumBreaksPill').textContent = `🥪 Snack (${snack}m) • 🍽️ Lunch (${lunch}m)`;

  let worshipLabel = '⛪ Wed Chapel (P1)';
  if (worship === 'fri_pm') worshipLabel = '🕌 Fri Jummah (PM)';
  else if (worship === 'none') worshipLabel = 'No Mid-Week Block';
  document.getElementById('agSumWorshipPill').textContent = worshipLabel;

  document.getElementById('agSumTeacherDayPill').textContent = `⏱️ Campus Day: ${workingHoursTarget.toFixed(1)} hrs`;
  const hoursValEl = document.getElementById('agWorkingHoursVal');
  if (hoursValEl) hoursValEl.textContent = `${workingHoursTarget.toFixed(1)} hrs`;
};

window.toggleBellsDrawer = function() {
  const drawer = document.getElementById('agBellsDrawer');
  const icon = document.getElementById('agBellsToggleIcon');
  const text = document.getElementById('agBellsToggleText');
  const isOpen = drawer.style.display !== 'none';

  drawer.style.display = isOpen ? 'none' : 'block';
  icon.textContent = isOpen ? '⚙️' : '▲';
  text.textContent = isOpen ? 'Edit Bells & Hours' : 'Close Bells Drawer';
};

window.stepWorkingHours = function(delta) {
  workingHoursTarget = Math.max(6.0, Math.min(10.0, workingHoursTarget + delta));
  calcPreFlightTimes();
};

window.calcPrefClosingTime = function() {
  const startEl = document.getElementById('prefStartTime');
  const durEl = document.getElementById('prefDuration');
  const pMonThuEl = document.getElementById('prefMonThu');
  const pFriEl = document.getElementById('prefFri');

  if (!startEl) return;

  const startTime = startEl.value || '08:00';
  const dur = parseInt(durEl.value) || 45;
  const pMonThu = parseInt(pMonThuEl.value) || 8;
  const pFri = parseInt(pFriEl.value) || 6;

  const closeMonThu = calculateDismissalTime(startTime, pMonThu, dur, 20, 40);
  const closeFri = calculateDismissalTime(startTime, pFri, dur, 20, 40);

  const monThuEl = document.getElementById('prefMonThuDismissal');
  const friEl = document.getElementById('prefFriDismissal');
  if (monThuEl) monThuEl.textContent = closeMonThu;
  if (friEl) friEl.textContent = closeFri;
};

let currentFacilities = [];

async function loadActiveFacilities() {
  const container = document.getElementById('agFacilitiesContainer');
  const section = document.getElementById('agFacilitiesSection');
  if (!container) return;

  try {
    const res = await fetch(`${API_BASE}/timetable/active-facilities`, { headers: H() });
    if (!res.ok) throw new Error('Failed to load facilities');
    const data = await res.json();
    currentFacilities = data.facilities || [];

    if (!data.has_specialized_facilities || !currentFacilities.length) {
      if (section) section.style.display = 'none';
      return;
    }
    if (section) section.style.display = 'block';

    let html = '';
    (data.categories || []).forEach(cat => {
      html += `
        <div style="margin-bottom:8px;">
          <div style="font-size:0.75rem; font-weight:700; color:var(--text-secondary); text-transform:uppercase; margin-bottom:4px; letter-spacing:0.5px;">
            ${esc(cat.title)}
          </div>
          <div style="display:flex; flex-direction:column; gap:6px;">
      `;
      cat.items.forEach(item => {
        const isMulti = item.id === 'multipurpose_science_lab';
        const bg = isMulti ? 'background:rgba(99,102,241,0.06); border:1px dashed rgba(99,102,241,0.3);' : 'background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.08);';
        const statusText = item.count === 0 ? '(Homeroom)' : (item.count === 1 ? '(1 Room)' : `(${item.count} Rooms)`);
        const statusColor = item.count === 0 ? 'var(--text-secondary)' : '#10b981';

        html += `
          <div style="${bg} border-radius:6px; padding:6px 10px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
            <div style="display:flex; align-items:center; gap:8px;">
              <span style="font-size:1.1rem;">${item.icon || '🏫'}</span>
              <div>
                <div style="font-weight:600; font-size:0.82rem; color:var(--text);">${esc(item.title)}</div>
                ${item.subtitle ? `<div style="font-size:0.7rem; color:var(--text-secondary);">${esc(item.subtitle)}</div>` : ''}
              </div>
            </div>
            <div style="display:flex; align-items:center; gap:6px;">
              <button type="button" class="btn" onclick="stepFacilityCount('${item.id}', -1)" style="padding:2px 8px; font-weight:700; font-size:0.8rem; min-width:28px;">-</button>
              <span id="fac_val_${item.id}" style="font-weight:700; font-size:0.85rem; min-width:24px; text-align:center;">${item.count}</span>
              <button type="button" class="btn" onclick="stepFacilityCount('${item.id}', 1)" style="padding:2px 8px; font-weight:700; font-size:0.8rem; min-width:28px;">+</button>
              <span id="fac_status_${item.id}" style="font-size:0.7rem; margin-left:4px; min-width:85px; color:${statusColor}; font-weight:600;">
                ${statusText}
              </span>
            </div>
          </div>
        `;
      });
      html += `</div></div>`;
    });
    container.innerHTML = html;
  } catch (e) {
    container.innerHTML = '<div style="color:var(--text-secondary); font-size:0.75rem;">Homeroom-based scheduling (Standard)</div>';
  }
}

window.stepFacilityCount = function(facId, delta) {
  const fac = currentFacilities.find(f => f.id === facId);
  if (!fac) return;
  fac.count = Math.max(0, Math.min(10, (fac.count || 0) + delta));
  const valEl = document.getElementById(`fac_val_${facId}`);
  const statEl = document.getElementById(`fac_status_${facId}`);
  if (valEl) valEl.textContent = fac.count;
  if (statEl) {
    statEl.textContent = fac.count === 0 ? '(Homeroom)' : (fac.count === 1 ? '(1 Room)' : `(${fac.count} Rooms)`);
    statEl.style.color = fac.count === 0 ? 'var(--text-secondary)' : '#10b981';
  }
};

async function checkSnapshotStatus() {
  const banner = document.getElementById('timetableUndoBanner');
  if (!banner) return;
  try {
    const res = await fetch(`${API_BASE}/timetable/snapshot-status`, { headers: H() });
    if (!res.ok) {
      banner.style.display = 'none';
      return;
    }
    const data = await res.json();
    if (data.has_snapshot) {
      banner.style.display = 'flex';
      const badge = document.getElementById('undoSlotCountBadge');
      if (badge) badge.textContent = `${data.slot_count} slots`;
      const subtitle = document.getElementById('undoBannerSubtitle');
      if (subtitle) {
        subtitle.textContent = `A backup snapshot exists from ${data.created_at || 'last generation'}. Undo will restore those exact slots.`;
      }
    } else {
      banner.style.display = 'none';
    }
  } catch (err) {
    banner.style.display = 'none';
  }
}

window.dismissUndoBanner = function() {
  const banner = document.getElementById('timetableUndoBanner');
  if (banner) banner.style.display = 'none';
};

window.executeUndoTimetable = async function() {
  if (!confirm('↩️ Revert Timetable:\n\nAre you sure you want to discard the current draft and restore your previous master timetable?')) {
    return;
  }
  try {
    const res = await fetch(`${API_BASE}/timetable/revert`, {
      method: 'POST',
      headers: J()
    });
    const data = await res.json();
    if (res.ok && data.status === 'SUCCESS') {
      alert(`✅ ${data.message}`);
      dismissUndoBanner();
      if (currentView === 'class') await loadClassView();
      else if (currentView === 'workloads') await loadTeacherWorkloads();
      else await loadTeacherView();
      await checkConflicts();
    } else {
      alert(`⚠️ ${data.detail || data.message || 'Failed to revert timetable.'}`);
    }
  } catch (err) {
    alert('Network error while reverting timetable.');
  }
};

window.executeDiscardDraft = async function() {
  if (!confirm('🗑️ Discard Draft:\n\nAre you sure you want to discard this generated timetable and clear all slots back to blank (0 slots)?')) {
    return;
  }
  try {
    const res = await fetch(`${API_BASE}/timetable/discard`, {
      method: 'POST',
      headers: J()
    });
    const data = await res.json();
    if (res.ok && data.status === 'SUCCESS') {
      alert(`✅ ${data.message}`);
      dismissUndoBanner();
      if (currentView === 'class') await loadClassView();
      else if (currentView === 'workloads') await loadTeacherWorkloads();
      else await loadTeacherView();
      await checkConflicts();
    } else {
      alert(`⚠️ ${data.detail || data.message || 'Failed to discard draft.'}`);
    }
  } catch (err) {
    alert('Network error while discarding draft.');
  }
};

window.executeClearTimetable = async function() {
  const semSelect = document.getElementById('semSelect');
  const semId = semSelect ? semSelect.value : null;

  if (!confirm('⚠️ Master Clear Timetable:\n\nAre you sure you want to completely clear the entire timetable back to blank (0 slots)?\n\nThis will remove all scheduled periods for this school.')) {
    return;
  }
  try {
    const url = semId ? `${API_BASE}/timetable/clear?semester_id=${semId}` : `${API_BASE}/timetable/clear`;
    const res = await fetch(url, {
      method: 'DELETE',
      headers: J()
    });
    const data = await res.json();
    if (res.ok && data.status === 'SUCCESS') {
      alert(`✅ ${data.message}`);
      dismissUndoBanner();
      if (currentView === 'class') await loadClassView();
      else if (currentView === 'workloads') await loadTeacherWorkloads();
      else await loadTeacherView();
      await checkConflicts();
    } else {
      alert(`⚠️ ${data.detail || data.message || 'Failed to clear timetable.'}`);
    }
  } catch (err) {
    alert('Network error while clearing timetable.');
  }
};

// ── Auto-Generate Modal & Pre-Flight Execution ───────────────────────────────
window.openAutoGenerateModal = async function() {
  const modal = document.getElementById('autoGenModal');

  // Populate semester selector
  const semSelect = document.getElementById('agSemesterSelect');
  if (semSelect) {
    let opts = '<option value="">Current Active Semester</option>';
    allSemesters.forEach(s => {
      opts += `<option value="${s.id}">${esc(s.name)}</option>`;
    });
    semSelect.innerHTML = opts;
  }

  // Pre-fill fields from profileConfig
  if (profileConfig) {
    if (document.getElementById('agStartTime')) {
      document.getElementById('agStartTime').value = profileConfig.start_time || '08:00';
    }
    if (document.getElementById('agDuration')) {
      document.getElementById('agDuration').value = profileConfig.period_duration_minutes || 45;
    }
    if (document.getElementById('agPeriodsPerDay')) {
      document.getElementById('agPeriodsPerDay').value = profileConfig.periods_per_day || 8;
    }
    if (document.getElementById('agFridayPeriods')) {
      document.getElementById('agFridayPeriods').value = profileConfig.friday_periods || 6;
    }
    const badge = document.getElementById('agProfileBadge');
    if (badge) {
      badge.textContent = profileConfig.derived_profile || 'SHS';
    }
  }

  // Hide progress and drawer
  document.getElementById('agProgressCard').style.display = 'none';
  document.getElementById('agBellsDrawer').style.display = 'none';
  document.getElementById('agBellsToggleIcon').textContent = '⚙️';
  document.getElementById('agBellsToggleText').textContent = 'Edit Bells & Hours';
  document.getElementById('agSubmitBtn').disabled = false;

  calcPreFlightTimes();
  await loadActiveFacilities();
  modal.classList.add('open');
};

window.closeAutoGenerateModal = function() {
  document.getElementById('autoGenModal').classList.remove('open');
};

window.runAutoGenerator = async function() {
  const semesterId = document.getElementById('agSemesterSelect').value;
  const startTime = document.getElementById('agStartTime').value || '08:00';
  const duration = parseInt(document.getElementById('agDuration').value) || 45;
  const periodsPerDay = parseInt(document.getElementById('agPeriodsPerDay').value) || 8;
  const fridayPeriods = parseInt(document.getElementById('agFridayPeriods').value) || 6;

  const progressCard = document.getElementById('agProgressCard');
  const progressText = document.getElementById('agProgressText');
  const submitBtn = document.getElementById('agSubmitBtn');

  progressCard.style.display = 'block';
  progressText.textContent = '🔍 Step 1 of 2: Running Pre-Flight Staff Workload & Capacity Audit...';
  submitBtn.disabled = true;

  try {
    // ── Pre-Flight Step: Scan for Staffing Overloads / Capacity Conflicts ──
    const auditUrl = `${API_BASE}/assignments/audit-staffing-conflicts${semesterId ? `?semester_id=${semesterId}` : ''}`;
    const auditRes = await fetch(auditUrl, { headers: H() }).catch(() => null);
    if (auditRes && auditRes.ok) {
      const auditData = await auditRes.json();
      if (auditData.conflicts && auditData.conflicts.length > 0) {
        progressText.innerHTML = `⚠️ <strong>Staffing Conflicts Detected:</strong> ${auditData.conflicts.length} subject(s) have teachers exceeding GES period limits. Opening Smart Distribute review...`;
        // UX-7 FIX: Keep submitBtn DISABLED while conflicts modal is open.
        // User must resolve conflicts first; the Smart Distribute flow re-enables when done.
        submitBtn.disabled = true;
        submitBtn.title = 'Resolve staffing conflicts first before generating';

        if (typeof openStaffingConflictsModal === 'function') {
          setTimeout(() => {
            openStaffingConflictsModal(auditData.conflicts, auditData.semester_id || (semesterId ? parseInt(semesterId) : null));
          }, 400);
        }
        return;
      }
    }

    progressText.textContent = '⚡ Step 2 of 2: Running Conflict-Free CSP Solver with facility allocation...';

    // 1. Collect facility counts
    const facilityCounts = {};
    currentFacilities.forEach(f => {
      facilityCounts[f.id] = f.count;
    });

    // 2. Sync updated bell preferences first so backend and generator are 100% aligned
    await fetch(`${API_BASE}/timetable/preferences`, {
      method: 'PUT',
      headers: J(),
      body: JSON.stringify({
        start_time: startTime,
        period_duration_minutes: duration,
        periods_per_day: periodsPerDay,
        friday_periods: fridayPeriods,
        facility_counts: facilityCounts
      })
    }).catch(() => {});

    // 3. Run the solver
    const res = await fetch(`${API_BASE}/timetable/auto-generate`, {
      method: 'POST',
      headers: J(),
      body: JSON.stringify({
        semester_id: semesterId ? parseInt(semesterId) : null,
        periods_per_day: periodsPerDay,
        friday_periods: fridayPeriods,
        facility_counts: facilityCounts
      })
    });

    const data = await res.json();
    if (res.ok && data.status === 'SUCCESS') {
      const qr = data.quality_report || {};
      const scoreBadge = qr.score ? `<span style="background:rgba(16,185,129,0.2); color:#10b981; padding:3px 10px; border-radius:12px; font-weight:700; font-size:0.8rem; margin-left:6px; border:1px solid #10b981;">Quality Score: ${qr.score}/100 (${qr.rating || 'Optimal'})</span>` : '';
      progressText.innerHTML = `🎉 Timetable Generated Successfully! ${scoreBadge}<br/><span style="font-size:0.85rem; font-weight:normal; margin-top:4px; display:inline-block;">Scheduled <strong>${data.total_slots} periods</strong> across all classes with 0 collisions.</span>`;

      await checkSnapshotStatus();

      setTimeout(async () => {
        closeAutoGenerateModal();
        await loadProfileConfig();
        if (currentView === 'class') await loadClassView();
        else if (currentView === 'workloads') await loadTeacherWorkloads();
        else await loadTeacherView();
        await checkConflicts();
      }, 1600);
    } else if (res.ok && data.status === 'PARTIAL') {
      const qr = data.quality_report || {};
      const scoreBadge = qr.score !== undefined ? `<span style="background:rgba(245,158,11,0.2); color:#f59e0b; padding:2px 8px; border-radius:12px; font-weight:700; font-size:0.8rem;">${qr.score}/100</span>` : '';
      const conflictLines = (data.conflicts || []).map(c => `<li style="margin:4px 0;">${esc(c)}</li>`).join('');
      const skippedLines = (data.skipped_classes || []).map(c => `<li style="margin:4px 0; color:#f59e0b;">${esc(c)}</li>`).join('');
      progressText.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
          <div style="color:#f59e0b; font-weight:700;">⚠️ Generated with ${data.unassigned_count} unplaced period(s)</div>
          ${scoreBadge}
        </div>
        <div style="font-size:0.82rem; color:var(--text-secondary); margin-bottom:10px;">${data.total_slots} periods placed. Items that could not be scheduled:</div>
        ${conflictLines ? `<ul style="font-size:0.78rem; color:#ef4444; text-align:left; margin:0; padding-left:16px; max-height:120px; overflow-y:auto;">${conflictLines}</ul>` : ''}
        ${skippedLines ? `<div style="font-size:0.78rem; color:#f59e0b; margin-top:6px; font-weight:600;">⚠️ Classes skipped (no subjects assigned):</div><ul style="font-size:0.76rem; color:#f59e0b; text-align:left; margin:0; padding-left:16px; max-height:80px; overflow-y:auto;">${skippedLines}</ul>` : ''}
        <div style="display:flex; gap:10px; margin-top:14px; flex-wrap:wrap;">
          <button type="button" class="btn primary" onclick="openStaffingConflictsModal(null, ${semesterId ? `'${semesterId}'` : 'null'})" style="flex:1; background:linear-gradient(135deg, #ef4444 0%, #dc2626 100%); border:none; font-weight:700; font-size:0.85rem; padding:8px 14px;">
            ⚡ Resolve with Smart Distribute
          </button>
          <button type="button" class="btn" onclick="closeAutoGenerateModal(); loadClassView(); checkConflicts();" style="flex:1;">View Current Placements</button>
        </div>
      `;
      await checkSnapshotStatus();
    } else {
      progressText.innerHTML = `⚠️ ${data.message || 'Generation failed. Check server logs.'}`;
    }
  } catch (err) {
    progressText.innerHTML = '❌ Network error while executing generator.';
  } finally {
    submitBtn.disabled = false;
  }
};

// ── Preferences Modal ────────────────────────────────────────────────────────
window.openPreferencesModal = function() {
  calcPrefClosingTime();
  document.getElementById('prefModal').classList.add('open');
};

window.closePreferencesModal = function() {
  document.getElementById('prefModal').classList.remove('open');
};

window.savePreferences = async function() {
  const startTime = document.getElementById('prefStartTime').value;
  const duration = parseInt(document.getElementById('prefDuration').value);
  const monThu = parseInt(document.getElementById('prefMonThu').value);
  const fri = parseInt(document.getElementById('prefFri').value);

  try {
    const res = await fetch(`${API_BASE}/timetable/preferences`, {
      method: 'PUT',
      headers: J(),
      body: JSON.stringify({
        start_time: startTime,
        period_duration_minutes: duration,
        periods_per_day: monThu,
        friday_periods: fri
      })
    });

    if (res.ok) {
      // UX-1 FIX: Replace alert() with toast
      showToast('Timetable preferences saved successfully!', 'success');
      closePreferencesModal();
      await loadProfileConfig();
    } else {
      showToast('Failed to save preferences.', 'error');
    }
  } catch (e) {
    showToast('Network error.', 'error');
  }
};

// ── Staff Handover Modal ──────────────────────────────────────────────────────
window.openHandoverModal = function() {
  document.getElementById('hoStatus').textContent = '';
  document.getElementById('handoverModal').classList.add('open');
};

window.closeHandoverModal = function() {
  document.getElementById('handoverModal').classList.remove('open');
};

window.executeHandover = async function() {
  const outgoingId = document.getElementById('hoOutgoingTeacher').value;
  const incomingId = document.getElementById('hoIncomingTeacher').value;
  const statusEl = document.getElementById('hoStatus');

  if (!outgoingId || !incomingId) {
    statusEl.style.color = '#ef4444';
    statusEl.textContent = 'Please select both outgoing and incoming teachers.';
    return;
  }
  if (outgoingId === incomingId) {
    statusEl.style.color = '#ef4444';
    statusEl.textContent = 'Outgoing and incoming teachers cannot be the same.';
    return;
  }

  const btn = document.getElementById('hoSubmitBtn');
  btn.disabled = true;
  btn.textContent = 'Transferring...';

  try {
    const res = await fetch(`${API_BASE}/timetable/handover`, {
      method: 'POST',
      headers: J(),
      body: JSON.stringify({
        outgoing_teacher_id: parseInt(outgoingId),
        incoming_teacher_id: parseInt(incomingId)
      })
    });

    const data = await res.json();
    if (res.ok && data.status === 'SUCCESS') {
      statusEl.style.color = '#10b981';
      statusEl.textContent = `✅ ${data.message}`;
      setTimeout(async () => {
        closeHandoverModal();
        if (currentView === 'teacher') await loadTeacherView();
        else if (currentView === 'workloads') await loadTeacherWorkloads();
        else await loadClassView();
      }, 1500);
    } else {
      statusEl.style.color = '#ef4444';
      statusEl.textContent = `⚠️ ${data.message || 'Failed to transfer slots.'}`;
    }
  } catch (err) {
    statusEl.style.color = '#ef4444';
    statusEl.textContent = '❌ Network error during handover.';
  } finally {
    btn.disabled = false;
    btn.textContent = 'Apply Handover';
  }
};

// ── Live Campus Radar Loader ─────────────────────────────────────────────────
window.loadCampusRadar = async function() {
  const labsContainer = document.getElementById('occupiedLabsContainer');
  const roomsContainer = document.getElementById('occupiedRoomsContainer');
  const freeContainer = document.getElementById('freeTeachersContainer');
  const freeBadge = document.getElementById('freeCountBadge');
  const liveTimeEl = document.getElementById('radarLiveTime');

  try {
    const res = await fetch(`${API_BASE}/timetable/campus-radar`, { headers: H() });
    if (!res.ok) return;
    const data = await res.json();

    liveTimeEl.textContent = `${data.current_day} &bull; Active Period: Period ${data.current_period} (${data.active_classes_count} classes in session)`;

    // 1. Occupied Labs
    if (data.occupied_labs && data.occupied_labs.length > 0) {
      labsContainer.innerHTML = data.occupied_labs.map(l => `
        <div style="background:rgba(56,189,248,0.1); border-left:4px solid #38bdf8; padding:8px 12px; border-radius:6px;">
          <div style="font-weight:700; color:#38bdf8; font-size:0.85rem;">🔬 ${esc(l.room)}</div>
          <div style="font-size:0.8rem; margin-top:2px;"><strong>${esc(l.class_name)}</strong> &bull; ${esc(l.subject_name)}</div>
          <div style="font-size:0.75rem; color:var(--text-secondary);">Teacher: ${esc(l.teacher_name)}</div>
        </div>
      `).join('');
    } else {
      labsContainer.innerHTML = '<div style="color:var(--text-secondary); font-size:0.85rem;">All laboratories are currently vacant / available.</div>';
    }

    // 2. Occupied Classrooms
    if (data.occupied_rooms && data.occupied_rooms.length > 0) {
      roomsContainer.innerHTML = data.occupied_rooms.map(r => `
        <div style="background:rgba(129,140,248,0.08); border-left:3px solid #818cf8; padding:8px 12px; border-radius:6px;">
          <div style="font-weight:700; font-size:0.85rem;">🏫 ${esc(r.class_name)} &bull; <span style="color:#818cf8;">${esc(r.subject_name)}</span></div>
          <div style="font-size:0.75rem; color:var(--text-secondary);">Instructor: ${esc(r.teacher_name)} [${esc(r.room)}]</div>
        </div>
      `).join('');
    } else {
      roomsContainer.innerHTML = '<div style="color:var(--text-secondary); font-size:0.85rem;">No academic classes currently scheduled in this period.</div>';
    }

    // 3. Free Staff Room Teachers
    freeBadge.textContent = `${data.free_teachers_count} Free`;
    if (data.free_teachers && data.free_teachers.length > 0) {
      freeContainer.innerHTML = data.free_teachers.map(t => `
        <div style="display:flex; justify-content:space-between; align-items:center; background:rgba(52,211,153,0.08); border-left:3px solid #34d399; padding:8px 12px; border-radius:6px;">
          <div>
            <div style="font-weight:700; font-size:0.85rem;">👤 ${esc(t.username)}</div>
            <div style="font-size:0.72rem; color:var(--text-secondary);">Role: ${esc(t.role.replace('_', ' '))}</div>
          </div>
          <span style="font-size:0.7rem; color:#34d399; font-weight:700; background:rgba(52,211,153,0.2); padding:2px 6px; border-radius:4px;">Available</span>
        </div>
      `).join('');
    } else {
      freeContainer.innerHTML = '<div style="color:var(--text-secondary); font-size:0.85rem;">All teachers are currently assigned in class.</div>';
    }

  } catch (err) {
    console.error('Failed to load campus radar:', err);
  }
};

// ── Teacher Workloads Audit Loader ───────────────────────────────────────────
window.loadTeacherWorkloads = async function() {
  const container = document.getElementById('workloadsTableContainer');
  try {
    const res = await fetch(`${API_BASE}/timetable/teacher-workloads`, { headers: H() });
    if (!res.ok) return;
    const workloads = await res.json();

    // 1. Update Quick Summary Metrics Cards
    const totalStaff = workloads.length;
    const optimalStaff = workloads.filter(w => !w.is_exempt && w.compliance_status === 'OPTIMAL').length;
    const underStaff = workloads.filter(w => !w.is_exempt && w.compliance_status === 'UNDERLOADED').length;
    const overStaff = workloads.filter(w => !w.is_exempt && w.compliance_status === 'OVERLOADED').length;
    const exemptStaff = workloads.filter(w => w.is_exempt).length;

    const elTotal = document.getElementById('statTotalStaff');
    const elOptimal = document.getElementById('statOptimalStaff');
    const elUnder = document.getElementById('statUnderStaff');
    const elOver = document.getElementById('statOverStaff');
    const elExempt = document.getElementById('statExemptStaff');

    if (elTotal) elTotal.textContent = totalStaff;
    if (elOptimal) elOptimal.textContent = optimalStaff;
    if (elUnder) elUnder.textContent = underStaff;
    if (elOver) elOver.textContent = overStaff;
    if (elExempt) elExempt.textContent = exemptStaff;

    if (!workloads.length) {
      container.innerHTML = '<div style="text-align:center; padding:30px; color:var(--text-secondary);">No teachers registered yet.</div>';
      return;
    }

    let html = `<table class="tt-table" style="width:100%;"><thead><tr>
      <th style="width:22%;">Staff Member &amp; ID</th>
      <th style="width:18%;">Permanent Subject Competency</th>
      <th style="width:18%;">GES Post &amp; Department</th>
      <th style="width:14%; text-align:center;">Weekly Load</th>
      <th style="width:13%; text-align:center;">Compliance</th>
      <th style="width:15%;">Utilization</th>
    </tr></thead><tbody>`;

    workloads.forEach(w => {
      const isExempt = w.is_exempt;
      const pct = Math.min(100, w.utilization_percent || 0);
      const barColor = isExempt ? '#64748b' : (pct > 90 ? '#ef4444' : (pct > 70 ? '#f59e0b' : '#10b981'));
      const badgeText = isExempt ? 'EXEMPT' : `${w.assigned_periods} / ${w.max_cap} P`;

      // Status pill badge
      let statusPill = '';
      if (isExempt) {
        statusPill = `<span style="background:rgba(100,116,139,0.15); color:#94a3b8; border:1px solid rgba(100,116,139,0.3); font-size:0.72rem; padding:2px 8px; border-radius:12px; font-weight:700;">🛡️ Exempt</span>`;
      } else if (w.compliance_status === 'OVERLOADED') {
        statusPill = `<span style="background:rgba(239,68,68,0.15); color:#ef4444; border:1px solid rgba(239,68,68,0.3); font-size:0.72rem; padding:2px 8px; border-radius:12px; font-weight:700;">⚠️ Overload</span>`;
      } else if (w.compliance_status === 'OPTIMAL') {
        statusPill = `<span style="background:rgba(16,185,129,0.15); color:#10b981; border:1px solid rgba(16,185,129,0.3); font-size:0.72rem; padding:2px 8px; border-radius:12px; font-weight:700;">✓ Optimal</span>`;
      } else {
        statusPill = `<span style="background:rgba(245,158,11,0.15); color:#f59e0b; border:1px solid rgba(245,158,11,0.3); font-size:0.72rem; padding:2px 8px; border-radius:12px; font-weight:700;">Underloaded</span>`;
      }

      // Subject tags
      let subjTags = '';
      if (w.primary_subject_name) {
        subjTags += `<div style="font-weight:700; color:var(--text); font-size:0.8rem;">🎓 ${esc(w.primary_subject_name)}</div>`;
      }
      if (w.qualified_subject_names && w.qualified_subject_names.length) {
        const others = w.qualified_subject_names.filter(s => s !== w.primary_subject_name);
        if (others.length) {
          subjTags += `<div style="font-size:0.7rem; color:var(--text-secondary); margin-top:2px;">+ ${others.map(s => esc(s)).join(', ')}</div>`;
        }
      }
      if (!subjTags) {
        subjTags = `<span style="color:var(--text-secondary); font-size:0.75rem;">(Unassigned Subject)</span>`;
      }

      html += `<tr>
        <td>
          <div style="font-weight:700; font-size:0.85rem; color:var(--text);">👤 ${esc(w.teacher_name)}</div>
          ${w.staff_id ? `<div style="font-size:0.7rem; color:var(--text-secondary); font-family:monospace;">ID: ${esc(w.staff_id)}</div>` : ''}
        </td>
        <td>${subjTags}</td>
        <td>
          <div style="font-size:0.8rem; font-weight:600;">${esc(w.role_title)}</div>
          <div style="font-size:0.7rem; color:var(--text-secondary);">${esc(w.department_name || 'General')}</div>
        </td>
        <td style="text-align:center; font-weight:700; font-size:0.85rem;">${badgeText}</td>
        <td style="text-align:center;">${statusPill}</td>
        <td>
          <div style="font-size:0.72rem; color:var(--text-secondary); display:flex; justify-content:space-between; margin-bottom:2px;">
            <span>${isExempt ? 'Admin' : `${pct}%`}</span>
          </div>
          <div class="workload-bar-container" style="height:6px; background:rgba(255,255,255,0.06); border-radius:3px; overflow:hidden;">
            <div class="workload-bar-fill" style="width:${isExempt ? 0 : pct}%; background:${barColor}; height:100%;"></div>
          </div>
        </td>
      </tr>`;
    });

    html += '</tbody></table>';
    container.innerHTML = html;
  } catch (err) {
    container.innerHTML = '<div style="color:var(--danger); text-align:center; padding:20px;">Failed to load workload audit.</div>';
  }
};

window.promptRolloverAssignments = async function() {
  const confirmed = confirm(
    "📋 1-Click Term Rollover:\n\n" +
    "Are you sure you want to copy all teacher-class subject allocations into the current semester?\n\n" +
    "This preserves staff specializations, avoids duplicate entries, and carries over teaching duties with 0 keystrokes."
  );
  if (!confirmed) return;

  try {
    const res = await fetch(`${API_BASE}/timetable/rollover-assignments`, {
      method: 'POST',
      headers: J(),
      body: JSON.stringify({})
    });
    const data = await res.json();
    if (res.ok && data.status === 'SUCCESS') {
      // UX-1 FIX: Replace alert() with toast
      showToast(`🎉 Rollover: ${data.message}`, 'success', 5000);
      await loadTeacherWorkloads();
    } else {
      showToast(data.detail || data.message || 'No changes made.', 'warning', 5000);
    }
  } catch (e) {
    showToast(`Network error: ${e.message}`, 'error');
  }
};

// ── Calendar Sync (.ics Export) ───────────────────────────────────────────────
window.syncTeacherCalendar = async function() {
  const teacherId = document.getElementById('viewTeacherSelect').value;
  if (!teacherId) {
    alert('Please select a teacher first.');
    return;
  }
  window.open(`${API_BASE}/timetable/calendar-sync/${teacherId}.ics`, '_blank');
};

// ── Official GES PDF Exports ─────────────────────────────────────────────────
window.downloadClassTimetablePDF = async function() {
  const classId = document.getElementById('viewClassSelect')?.value;
  const semesterId = document.getElementById('viewSemesterSelect')?.value;
  if (!classId) {
    // UX-4 FIX: Highlight the selector instead of blocking alert
    const sel = document.getElementById('viewClassSelect');
    if (sel) { sel.style.outline = '2px solid #ef4444'; setTimeout(() => sel.style.outline = '', 2000); sel.focus(); }
    showToast('Please select a Class Section first.', 'warning');
    return;
  }

  try {
    let pdfUrl = `${API_BASE}/timetable/class/${classId}/pdf`;
    if (semesterId) pdfUrl += `?semester_id=${semesterId}`;
    const res = await fetch(pdfUrl, { headers: H() });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to generate class timetable PDF' }));
      showToast(err.detail || 'Failed to download PDF', 'error');
      return;
    }

    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `Class_Timetable_${classId}.pdf`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast('Class timetable PDF downloaded!', 'success');
  } catch (err) {
    showToast('Network error while downloading class timetable PDF.', 'error');
  }
};

window.downloadTeacherTimetablePDF = async function() {
  const teacherId = document.getElementById('viewTeacherSelect')?.value;
  const semesterId = document.getElementById('viewSemesterSelect')?.value;
  if (!teacherId) {
    // UX-4 FIX: Highlight selector instead of alert
    const sel = document.getElementById('viewTeacherSelect');
    if (sel) { sel.style.outline = '2px solid #ef4444'; setTimeout(() => sel.style.outline = '', 2000); sel.focus(); }
    showToast('Please select a Teacher first.', 'warning');
    return;
  }

  try {
    let pdfUrl = `${API_BASE}/timetable/teacher/${teacherId}/pdf`;
    if (semesterId) pdfUrl += `?semester_id=${semesterId}`;
    const res = await fetch(pdfUrl, { headers: H() });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to generate teacher schedule PDF' }));
      showToast(err.detail || 'Failed to download PDF', 'error');
      return;
    }

    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `Teacher_Schedule_${teacherId}.pdf`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast('Teacher schedule PDF downloaded!', 'success');
  } catch (err) {
    showToast('Network error while downloading teacher schedule PDF.', 'error');
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
          `${c.teacher_name || 'Room ' + c.room} is double-booked on ${c.day} Period ${c.period}`
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

// ── Bootstrap ─────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', init);
