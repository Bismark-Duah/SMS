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
}

// ── View Toggle ───────────────────────────────────────────────────────────────
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

  if (isSchedule) {
    document.getElementById('classControls').style.display   = mode === 'class'   ? 'flex' : 'none';
    document.getElementById('teacherControls').style.display = mode === 'teacher' ? 'flex' : 'none';
    if (mode === 'class') loadClassView();
    else loadTeacherView();
  } else if (mode === 'radar') {
    loadCampusRadar();
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

  const usedPeriods = new Set(slots.map(s => s.period_number));
  const maxPeriod = usedPeriods.size ? Math.max(...usedPeriods, 6) : 8;
  const visiblePeriods = Array.from({length: maxPeriod}, (_, i) => i + 1);

  let html = `<table class="tt-table"><thead><tr>
    <th>Period</th>
    ${DAYS.map(d => `<th>${d}</th>`).join('')}
  </tr></thead><tbody>`;

  visiblePeriods.forEach(p => {
    html += `<tr><td>Period ${p}</td>`;
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
  document.getElementById('slotEditModal').classList.add('open');
};

window.openEditSlot = function(slot) {
  currentEditingSlotId = slot.id;
  document.getElementById('slotModalTitle').textContent = `✏️ Edit Slot – ${DAYS[slot.day_of_week]} Period ${slot.period_number}`;
  document.getElementById('mSlotDay').value = slot.day_of_week;
  document.getElementById('mSlotPeriod').value = slot.period_number;
  document.getElementById('mSlotSubject').value = slot.subject_id || '';
  document.getElementById('mSlotTeacher').value = slot.teacher_id || '';
  document.getElementById('mSlotRoom').value = slot.room || '';
  document.getElementById('mSlotStatus').textContent = '';
  document.getElementById('slotEditModal').classList.add('open');
};

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

// ── Auto-Generate Modal & Solver Execution ────────────────────────────────────
window.openAutoGenerateModal = function() {
  const modal = document.getElementById('autoGenModal');
  const summary = document.getElementById('wizardProfileSummary');
  if (summary && profileConfig) {
    summary.innerHTML = `<strong>${profileConfig.school_name}</strong> &bull; Profile: <em>${profileConfig.derived_profile}</em> (${profileConfig.ownership_type})`;
  }
  document.getElementById('agProgressCard').style.display = 'none';
  modal.classList.add('open');
};

window.closeAutoGenerateModal = function() {
  document.getElementById('autoGenModal').classList.remove('open');
};

window.runAutoGenerator = async function() {
  const semesterId = document.getElementById('agSemesterSelect').value;
  const periodsPerDay = parseInt(document.getElementById('agPeriodsPerDay').value) || 8;
  const fridayPeriods = parseInt(document.getElementById('agFridayPeriods').value) || 6;

  const progressCard = document.getElementById('agProgressCard');
  const progressText = document.getElementById('agProgressText');
  const submitBtn = document.getElementById('agSubmitBtn');

  progressCard.style.display = 'block';
  progressText.textContent = '⚡ Running Pure-Python CSP Solver...';
  submitBtn.disabled = true;

  try {
    const res = await fetch(`${API_BASE}/timetable/auto-generate`, {
      method: 'POST',
      headers: J(),
      body: JSON.stringify({
        semester_id: semesterId ? parseInt(semesterId) : null,
        periods_per_day: periodsPerDay,
        friday_periods: fridayPeriods
      })
    });

    const data = await res.json();
    if (res.ok && data.status === 'SUCCESS') {
      progressText.innerHTML = `🎉 Timetable Generated Successfully!<br/><span style="font-size:0.85rem; font-weight:normal;">Created <strong>${data.total_slots} periods</strong> across all classes with 0 collisions.</span>`;
      setTimeout(async () => {
        closeAutoGenerateModal();
        if (currentView === 'class') await loadClassView();
        else if (currentView === 'workloads') await loadTeacherWorkloads();
        else await loadTeacherView();
        await checkConflicts();
      }, 1500);
    } else {
      progressText.innerHTML = `⚠️ Generation Finished with Warnings:<br/><span style="font-size:0.8rem; color:#ef4444;">${(data.conflicts || []).join('<br/>') || data.message || 'Partial generation'}</span>`;
    }
  } catch (err) {
    progressText.innerHTML = '❌ Network error while executing generator.';
  } finally {
    submitBtn.disabled = false;
  }
};

// ── Preferences Modal ────────────────────────────────────────────────────────
window.openPreferencesModal = function() {
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
      alert('✅ Timetable preferences saved successfully!');
      closePreferencesModal();
      await loadProfileConfig();
    } else {
      alert('⚠️ Failed to save preferences.');
    }
  } catch (e) {
    alert('❌ Network error.');
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

    if (!workloads.length) {
      container.innerHTML = '<div style="text-align:center; padding:30px; color:var(--text-secondary);">No teachers registered yet.</div>';
      return;
    }

    let html = `<table class="tt-table" style="width:100%;"><thead><tr>
      <th style="width:25%;">Teacher Name</th>
      <th style="width:25%;">Responsibility Post</th>
      <th style="width:20%; text-align:center;">Weekly Load</th>
      <th style="width:30%;">Workload Utilization</th>
    </tr></thead><tbody>`;

    workloads.forEach(w => {
      const isExempt = w.is_exempt;
      const pct = Math.min(100, w.utilization_percent || 0);
      const barColor = isExempt ? '#64748b' : (pct > 90 ? '#ef4444' : (pct > 70 ? '#f59e0b' : '#10b981'));
      const badgeText = isExempt ? 'EXEMPT (0 Periods)' : `${w.assigned_periods} / ${w.max_cap} Periods`;

      html += `<tr>
        <td style="font-weight:700; font-size:0.85rem;">👤 ${esc(w.teacher_name)}</td>
        <td style="font-size:0.8rem;"><span style="background:rgba(255,255,255,0.06); padding:2px 8px; border-radius:4px;">${esc(w.role_title)}</span></td>
        <td style="text-align:center; font-weight:700; font-size:0.85rem;">${badgeText}</td>
        <td>
          <div style="font-size:0.75rem; color:var(--text-secondary); display:flex; justify-content:space-between;">
            <span>${isExempt ? 'Administrative Duty' : `${pct}% of max capacity`}</span>
          </div>
          <div class="workload-bar-container">
            <div class="workload-bar-fill" style="width:${isExempt ? 0 : pct}%; background:${barColor};"></div>
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
  if (!classId) {
    alert('Please select a Class Section first.');
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/timetable/class/${classId}/pdf`, { headers: H() });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to generate class timetable PDF' }));
      alert(`⚠️ Error: ${err.detail || 'Failed to download PDF'}`);
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
  } catch (err) {
    alert('Network error while downloading class timetable PDF.');
  }
};

window.downloadTeacherTimetablePDF = async function() {
  const teacherId = document.getElementById('viewTeacherSelect')?.value;
  if (!teacherId) {
    alert('Please select a Teacher first.');
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/timetable/teacher/${teacherId}/pdf`, { headers: H() });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to generate teacher schedule PDF' }));
      alert(`⚠️ Error: ${err.detail || 'Failed to download PDF'}`);
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
  } catch (err) {
    alert('Network error while downloading teacher schedule PDF.');
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
