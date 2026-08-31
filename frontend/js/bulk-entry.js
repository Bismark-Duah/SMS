const API_BASE = window.API_BASE || (window.location.origin.includes('http') ? (window.location.origin + '/api') : 'http://127.0.0.1:8000/api');

const token = localStorage.getItem('accessToken');
if (!token) {
  window.location.href = 'auth.html';
}

function getHeaders(headers = {}) {
  const h = { ...headers };
  if (token) h['Authorization'] = `Bearer ${token}`;
  const schoolId = localStorage.getItem('school_id');
  if (schoolId) h['X-School-Id'] = schoolId;
  return h;
}

function getScoreWeights() {
  const classWeight = parseFloat(localStorage.getItem('class_score_weight')) || 30;
  const examWeight = parseFloat(localStorage.getItem('exam_score_weight')) || 70;
  return { classWeight, examWeight };
}

function calculateGrade(total) {
  if (total >= 80) return 'A1';
  if (total >= 70) return 'B2';
  if (total >= 60) return 'B3';
  if (total >= 55) return 'C4';
  if (total >= 50) return 'C5';
  if (total >= 45) return 'C6';
  if (total >= 40) return 'D7';
  if (total >= 35) return 'E8';
  return 'F9';
}

let deskMode = 'single';
let currentMode = 'simple';
let cachedClasses = [];
let cachedSubjects = [];
let broadsheetSubjects = [];
let broadsheetStudents = [];

function switchDeskMode(mode) {
  deskMode = mode;
  const tabSingle = document.getElementById('tabSingleSubject');
  const tabBroadsheet = document.getElementById('tabClassBroadsheet');
  const subWrapper = document.getElementById('subjectFieldWrapper');
  const subSelect = document.getElementById('subject_id');
  const singleSec = document.getElementById('bulkEntrySection');
  const broadSec = document.getElementById('broadsheetEntrySection');

  if (mode === 'broadsheet') {
    if (tabBroadsheet) {
      tabBroadsheet.className = 'btn sm primary';
      tabBroadsheet.style.background = 'linear-gradient(135deg, #10b981, #059669)';
      tabBroadsheet.style.color = 'white';
    }
    if (tabSingle) {
      tabSingle.className = 'btn sm';
      tabSingle.style.background = '';
      tabSingle.style.color = '';
    }
    if (subWrapper) subWrapper.style.display = 'none';
    if (subSelect) subSelect.removeAttribute('required');
    if (singleSec) singleSec.style.display = 'none';
  } else {
    if (tabSingle) {
      tabSingle.className = 'btn sm primary';
      tabSingle.style.background = '';
      tabSingle.style.color = '';
    }
    if (tabBroadsheet) {
      tabBroadsheet.className = 'btn sm';
      tabBroadsheet.style.background = 'rgba(16,185,129,0.15)';
      tabBroadsheet.style.color = '#34d399';
    }
    if (subWrapper) subWrapper.style.display = 'block';
    if (subSelect) subSelect.setAttribute('required', 'required');
    if (broadSec) broadSec.style.display = 'none';
  }
}

async function initFilters() {
  try {
    const schoolMode = (localStorage.getItem('school_mode') || 'COMBINED').toUpperCase();
    const subUrl = `${API_BASE}/subjects/my-assignments`;
    const [resClasses, resSubjects, resSemesters] = await Promise.all([
      fetch(`${API_BASE}/classes/my-classes`, { headers: getHeaders() }),
      fetch(subUrl, { headers: getHeaders() }),
      fetch(`${API_BASE}/academic/semesters`, { headers: getHeaders() }),
    ]);

    cachedClasses = await resClasses.json();
    cachedSubjects = await resSubjects.json();
    const semesters = await resSemesters.json();

    document.getElementById('class_section_id').innerHTML = '<option value="">Select Class Section...</option>' + 
      cachedClasses.map(c => `<option value="${c.id}">${c.name}</option>`).join('');

    document.getElementById('subject_id').innerHTML = '<option value="">Select Subject...</option>' + 
      cachedSubjects.map(s => `<option value="${s.id}">${s.name}</option>`).join('');

    document.getElementById('semester_id').innerHTML = '<option value="">Select Term...</option>' + 
      semesters.map(s => `<option value="${s.id}">${s.name}</option>`).join('');

    // Default to broadsheet if school is basic only
    if (schoolMode === 'BASIC_ONLY') {
      switchDeskMode('broadsheet');
    }

  } catch (error) {
    console.error('Error initializing filters:', error);
  }
}

function handleClassChange(classId) {
  const selectedCls = cachedClasses.find(c => String(c.id) === String(classId));
  if (selectedCls) {
    const isBasic = !((selectedCls.name || '').toUpperCase().includes('SHS') || (selectedCls.stage_name || '').toUpperCase().includes('SHS'));
    const tabBroadsheet = document.getElementById('tabClassBroadsheet');
    if (tabBroadsheet) {
      tabBroadsheet.style.display = isBasic ? 'inline-block' : 'none';
    }
  }
}

function toggleEntryMode(mode) {
  currentMode = mode;
  const simpleCols = document.querySelectorAll('.simple-col');
  const detailedCols = document.querySelectorAll('.detailed-col');

  if (mode === 'detailed') {
    simpleCols.forEach(el => el.style.display = 'none');
    detailedCols.forEach(el => el.style.display = 'table-cell');
  } else {
    simpleCols.forEach(el => el.style.display = 'table-cell');
    detailedCols.forEach(el => el.style.display = 'none');
  }
}

function formatGradePill(grade) {
  if (!grade) return '—';
  let pillClass = 'grade-f';
  if (grade === 'A1' || grade === '1') pillClass = 'grade-a1';
  else if (grade.startsWith('B') || grade === '2' || grade === '3') pillClass = 'grade-b';
  else if (grade.startsWith('C') || grade === '4' || grade === '5' || grade === '6') pillClass = 'grade-c';
  else if (grade.startsWith('D') || grade.startsWith('E') || grade === '7' || grade === '8') pillClass = 'grade-d';
  return `<span class="grade-pill ${pillClass}">${grade}</span>`;
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function handleFilterSubmit(event) {
  event.preventDefault();
  if (deskMode === 'broadsheet') {
    loadBroadsheetStudentGrid();
  } else {
    loadStudentList();
  }
}

// ── Single Subject Flow ───────────────────────────────────────────────────
async function loadStudentList() {
  const classId = document.getElementById('class_section_id').value;
  const subjectId = document.getElementById('subject_id').value;
  const semesterId = document.getElementById('semester_id').value;

  if (!classId || !subjectId || !semesterId) {
    alert('Please select Class Section, Subject, and Term first.');
    return;
  }

  const tbody = document.getElementById('studentListBody');
  tbody.innerHTML = '<tr><td colspan="10" style="text-align:center; padding:20px;">Loading student list and previous scores...</td></tr>';
  document.getElementById('bulkEntrySection').style.display = 'block';
  document.getElementById('broadsheetEntrySection').style.display = 'none';

  try {
    const [resStudents, resScores] = await Promise.all([
      fetch(`${API_BASE}/students/?class_section_id=${classId}`, { headers: getHeaders() }),
      fetch(`${API_BASE}/results/class/${classId}?semester_id=${semesterId}&subject_id=${subjectId}`, { headers: getHeaders() })
    ]);

    const students = await resStudents.json();
    const scores = await resScores.json();

    const scoreMap = {};
    if (Array.isArray(scores)) {
      scores.forEach(s => { scoreMap[s.student_id] = s; });
    }

    if (!Array.isArray(students) || students.length === 0) {
      tbody.innerHTML = '<tr><td colspan="10" style="text-align:center; padding:20px; color:var(--text-secondary);">No active students found in this class section.</td></tr>';
      return;
    }

    tbody.innerHTML = students.map((st, idx) => {
      const existing = scoreMap[st.id] || {};
      const classScore = existing.class_score !== undefined ? existing.class_score : '';
      const examScore = existing.exam_score !== undefined ? existing.exam_score : '';
      const total = (parseFloat(classScore) || 0) + (parseFloat(examScore) || 0);
      const grade = calculateGrade(total);

      return `
        <tr data-student-id="${st.id}" data-row-index="${idx}">
          <td style="font-weight:600; text-align:left;">
            ${escapeHtml(st.full_name || `${st.first_name || ''} ${st.last_name || ''}`.trim())}
            <small style="display:block; opacity:0.6; font-size:0.75rem;">${escapeHtml(st.student_code || '')}</small>
          </td>
          <td class="simple-col">
            <input type="number" step="0.1" min="0" max="100" class="score-input class-score" data-col="0" data-row="${idx}" value="${classScore}" placeholder="0" style="width:75px; text-align:center; padding:6px; border-radius:4px; border:1px solid var(--border-color); background:var(--card-bg); color:var(--text-primary);" />
          </td>
          <td class="detailed-col" style="display:none;"><input type="number" step="0.1" min="0" max="20" class="score-input ex1-score" data-col="1" data-row="${idx}" value="${existing.ex1 || ''}" style="width:55px; text-align:center;" /></td>
          <td class="detailed-col" style="display:none;"><input type="number" step="0.1" min="0" max="20" class="score-input ex2-score" data-col="2" data-row="${idx}" value="${existing.ex2 || ''}" style="width:55px; text-align:center;" /></td>
          <td class="detailed-col" style="display:none;"><input type="number" step="0.1" min="0" max="20" class="score-input ass1-score" data-col="3" data-row="${idx}" value="${existing.ass1 || ''}" style="width:55px; text-align:center;" /></td>
          <td class="detailed-col" style="display:none;"><input type="number" step="0.1" min="0" max="20" class="score-input grp-score" data-col="4" data-row="${idx}" value="${existing.grp_work || ''}" style="width:55px; text-align:center;" /></td>
          <td class="detailed-col" style="display:none;"><input type="number" step="0.1" min="0" max="20" class="score-input mid-score" data-col="5" data-row="${idx}" value="${existing.mid_sem || ''}" style="width:55px; text-align:center;" /></td>
          <td>
            <input type="number" step="0.1" min="0" max="100" class="score-input exam-score" data-col="6" data-row="${idx}" value="${examScore}" placeholder="0" style="width:75px; text-align:center; padding:6px; border-radius:4px; border:1px solid var(--border-color); background:var(--card-bg); color:var(--text-primary);" />
          </td>
          <td class="total-preview" style="font-weight:700;">${total > 0 ? total.toFixed(1) : '—'}</td>
          <td class="grade-preview">${total > 0 ? formatGradePill(grade) : '—'}</td>
        </tr>
      `;
    }).join('');

    setupKeyboardNavigation();
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="10" style="text-align:center; padding:20px; color:#ef4444;">Error loading data: ${err.message}</td></tr>`;
  }
}

function setupKeyboardNavigation() {
  const inputs = document.querySelectorAll('.spreadsheet-table input.score-input');
  inputs.forEach(input => {
    input.addEventListener('keydown', e => {
      const row = parseInt(input.dataset.row);
      const col = parseInt(input.dataset.col);

      if (e.key === 'ArrowDown' || e.key === 'Enter') {
        e.preventDefault();
        const nextInput = document.querySelector(`.score-input[data-row="${row + 1}"][data-col="${col}"]`);
        if (nextInput) nextInput.focus();
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        const prevInput = document.querySelector(`.score-input[data-row="${row - 1}"][data-col="${col}"]`);
        if (prevInput) prevInput.focus();
      } else if (e.key === 'ArrowRight') {
        const nextCol = document.querySelector(`.score-input[data-row="${row}"][data-col="${col + 1}"]`);
        if (nextCol && input.selectionEnd === input.value.length) {
          e.preventDefault();
          nextCol.focus();
        }
      } else if (e.key === 'ArrowLeft') {
        const prevCol = document.querySelector(`.score-input[data-row="${row}"][data-col="${col - 1}"]`);
        if (prevCol && input.selectionStart === 0) {
          e.preventDefault();
          prevCol.focus();
        }
      }
    });

    input.addEventListener('input', () => {
      const tr = input.closest('tr');
      if (!tr) return;
      const cScore = parseFloat(tr.querySelector('.class-score')?.value) || 0;
      const eScore = parseFloat(tr.querySelector('.exam-score')?.value) || 0;
      const total = cScore + eScore;
      const totalEl = tr.querySelector('.total-preview');
      const gradeEl = tr.querySelector('.grade-preview');
      if (totalEl) totalEl.textContent = total > 0 ? total.toFixed(1) : '—';
      if (gradeEl) gradeEl.innerHTML = total > 0 ? formatGradePill(calculateGrade(total)) : '—';
    });
  });
}

async function saveAllScores() {
  const subjectId = document.getElementById('subject_id').value;
  const semesterId = document.getElementById('semester_id').value;
  if (!subjectId || !semesterId) return alert('Please select subject and semester.');

  const rows = document.querySelectorAll('#studentListBody tr[data-student-id]');
  if (rows.length === 0) return alert('No students to save.');

  const payloads = [];
  for (const row of rows) {
    const studentId = row.dataset.studentId;
    const classScore = parseFloat(row.querySelector('.class-score')?.value) || 0;
    const examScore = parseFloat(row.querySelector('.exam-score')?.value) || 0;

    payloads.push({
      student_id: parseInt(studentId),
      subject_id: parseInt(subjectId),
      semester_id: parseInt(semesterId),
      class_score: classScore,
      exam_score: examScore
    });
  }

  const saveBtn = document.getElementById('saveBulkBtn');
  if (saveBtn) { saveBtn.disabled = true; saveBtn.textContent = '⏳ Saving Scores...'; }

  try {
    let successCount = 0;
    for (const p of payloads) {
      const res = await fetch(`${API_BASE}/results/`, {
        method: 'POST',
        headers: getHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(p)
      });
      if (res.ok) successCount++;
    }

    const msg = document.getElementById('bulkMsg');
    if (msg) msg.innerHTML = `<span style="color:#34d399; font-weight:700;">✅ Successfully saved ${successCount} student score(s).</span>`;
    if (window.showToast) window.showToast(`Saved ${successCount} score records!`, 'success');
  } catch (err) {
    alert('Error saving scores: ' + err.message);
  } finally {
    if (saveBtn) { saveBtn.disabled = false; saveBtn.textContent = '💾 Save All Results'; }
  }
}

// ── Primary All-in-One Class Broadsheet Flow ──────────────────────────────
async function loadBroadsheetStudentGrid() {
  const classId = document.getElementById('class_section_id').value;
  const semesterId = document.getElementById('semester_id').value;

  if (!classId || !semesterId) {
    alert('Please select Class Section and Semester / Term first.');
    return;
  }

  const selectedCls = cachedClasses.find(c => String(c.id) === String(classId));
  const classNameHeader = document.getElementById('broadsheetClassName');
  if (classNameHeader && selectedCls) {
    classNameHeader.textContent = `📋 Primary All-in-One Grid: ${selectedCls.name}`;
  }

  document.getElementById('bulkEntrySection').style.display = 'none';
  document.getElementById('broadsheetEntrySection').style.display = 'block';

  const thead = document.getElementById('broadsheetHeader');
  const tbody = document.getElementById('broadsheetBody');
  thead.innerHTML = '<tr><th>Loading columns...</th></tr>';
  tbody.innerHTML = '<tr><td style="text-align:center; padding:20px;">Loading class roster and subject scores...</td></tr>';

  try {
    // 1. Fetch class students, active subjects, and existing scores
    const [resStudents, resSubjects, resScores] = await Promise.all([
      fetch(`${API_BASE}/students/?class_section_id=${classId}`, { headers: getHeaders() }),
      fetch(`${API_BASE}/subjects/`, { headers: getHeaders() }),
      fetch(`${API_BASE}/results/class/${classId}?semester_id=${semesterId}`, { headers: getHeaders() })
    ]);

    broadsheetStudents = await resStudents.json();
    const allSubs = await resSubjects.json();
    const existingScores = await resScores.json();

    // Filter relevant Basic subjects (exclude SHS electives)
    broadsheetSubjects = allSubs.filter(s => {
      const n = (s.name || '').toUpperCase();
      const sl = (s.school_level || '').toUpperCase();
      if (sl === 'SHS') return false;
      if (n.includes('PHYSICS') || n.includes('CHEMISTRY') || n.includes('BIOLOGY') || n.includes('GOVERNMENT') || n.includes('ACCOUNTING') || n.includes('ECONOMICS')) return false;
      return true;
    });

    if (broadsheetSubjects.length === 0) {
      broadsheetSubjects = allSubs.slice(0, 8); // fallback
    }

    if (!Array.isArray(broadsheetStudents) || broadsheetStudents.length === 0) {
      tbody.innerHTML = '<tr><td style="text-align:center; padding:20px; color:var(--text-secondary);">No active pupils found in this class.</td></tr>';
      return;
    }

    // Map existing scores: key = `${student_id}_${subject_id}`
    const scoreMap = {};
    if (Array.isArray(existingScores)) {
      existingScores.forEach(s => {
        scoreMap[`${s.student_id}_${s.subject_id}`] = s;
      });
    }

    // 2. Render Header
    thead.innerHTML = `
      <tr style="background:var(--card-bg, #1e293b); border-bottom:2px solid rgba(255,255,255,0.1);">
        <th style="padding:10px 12px; text-align:left; min-width:180px; position:sticky; left:0; background:var(--card-bg); z-index:3;">Pupil Name</th>
        ${broadsheetSubjects.map((sub, colIdx) => `
          <th style="padding:10px 8px; text-align:center; min-width:85px;">
            <div style="font-weight:700; font-size:0.8rem;">${escapeHtml(sub.name)}</div>
            <div style="font-size:0.68rem; opacity:0.6;">(100%)</div>
          </th>
        `).join('')}
        <th style="padding:10px 8px; text-align:center; min-width:70px; background:rgba(99,102,241,0.1); color:#818cf8;">Total</th>
        <th style="padding:10px 8px; text-align:center; min-width:65px; background:rgba(16,185,129,0.1); color:#34d399;">Avg %</th>
      </tr>
    `;

    // 3. Render Body Rows
    tbody.innerHTML = broadsheetStudents.map((st, rIdx) => {
      let rowTotal = 0;
      let subjectCount = 0;

      const subInputs = broadsheetSubjects.map((sub, cIdx) => {
        const sc = scoreMap[`${st.id}_${sub.id}`];
        const val = sc ? (sc.total_score !== undefined ? sc.total_score : ((sc.class_score || 0) + (sc.exam_score || 0))) : '';
        if (val !== '') {
          rowTotal += parseFloat(val) || 0;
          subjectCount++;
        }

        return `
          <td style="padding:4px; text-align:center;">
            <input type="number" step="0.5" min="0" max="100" class="score-input bs-input"
              data-student-id="${st.id}" data-subject-id="${sub.id}"
              data-row="${rIdx}" data-col="${cIdx}"
              value="${val}" placeholder="—"
              style="width:100%; max-width:75px; text-align:center; padding:6px 4px; border-radius:4px; border:1px solid var(--border-color); background:rgba(0,0,0,0.2); color:var(--text-primary); font-weight:600; font-size:0.85rem;" />
          </td>
        `;
      }).join('');

      const rowAvg = subjectCount > 0 ? (rowTotal / broadsheetSubjects.length).toFixed(1) : '—';

      return `
        <tr data-student-id="${st.id}" data-row="${rIdx}" style="border-bottom:1px solid rgba(255,255,255,0.05);">
          <td style="padding:8px 12px; font-weight:600; text-align:left; position:sticky; left:0; background:var(--card-bg); z-index:2; white-space:nowrap;">
            ${escapeHtml(st.full_name || `${st.first_name || ''} ${st.last_name || ''}`.trim())}
            <small style="display:block; opacity:0.6; font-size:0.72rem;">${escapeHtml(st.student_code || '')}</small>
          </td>
          ${subInputs}
          <td class="bs-total" style="padding:6px; font-weight:700; text-align:center; color:#818cf8; background:rgba(99,102,241,0.05);">${rowTotal > 0 ? rowTotal.toFixed(1) : '—'}</td>
          <td class="bs-avg" style="padding:6px; font-weight:700; text-align:center; color:#34d399; background:rgba(16,185,129,0.05);">${rowAvg !== '—' ? `${rowAvg}%` : '—'}</td>
        </tr>
      `;
    }).join('');

    setupBroadsheetKeyboardNav();
    updateBroadsheetStats();

  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="20" style="text-align:center; padding:20px; color:#ef4444;">Error loading class broadsheet: ${err.message}</td></tr>`;
  }
}

function setupBroadsheetKeyboardNav() {
  const inputs = document.querySelectorAll('.bs-input');
  inputs.forEach(input => {
    input.addEventListener('keydown', e => {
      const row = parseInt(input.dataset.row);
      const col = parseInt(input.dataset.col);

      if (e.key === 'ArrowDown' || e.key === 'Enter') {
        e.preventDefault();
        const nextInput = document.querySelector(`.bs-input[data-row="${row + 1}"][data-col="${col}"]`);
        if (nextInput) nextInput.focus();
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        const prevInput = document.querySelector(`.bs-input[data-row="${row - 1}"][data-col="${col}"]`);
        if (prevInput) prevInput.focus();
      } else if (e.key === 'ArrowRight') {
        if (input.selectionEnd === input.value.length) {
          const nextCol = document.querySelector(`.bs-input[data-row="${row}"][data-col="${col + 1}"]`);
          if (nextCol) { e.preventDefault(); nextCol.focus(); }
        }
      } else if (e.key === 'ArrowLeft') {
        if (input.selectionStart === 0) {
          const prevCol = document.querySelector(`.bs-input[data-row="${row}"][data-col="${col - 1}"]`);
          if (prevCol) { e.preventDefault(); prevCol.focus(); }
        }
      }
    });

    input.addEventListener('input', () => {
      const tr = input.closest('tr');
      if (!tr) return;
      let total = 0;
      let count = 0;
      tr.querySelectorAll('.bs-input').forEach(inp => {
        const v = parseFloat(inp.value);
        if (!isNaN(v)) {
          total += v;
          count++;
        }
      });

      const totalEl = tr.querySelector('.bs-total');
      const avgEl = tr.querySelector('.bs-avg');
      if (totalEl) totalEl.textContent = count > 0 ? total.toFixed(1) : '—';
      if (avgEl) avgEl.textContent = count > 0 && broadsheetSubjects.length > 0 ? `${(total / broadsheetSubjects.length).toFixed(1)}%` : '—';
      updateBroadsheetStats();
    });
  });
}

function updateBroadsheetStats() {
  const statsEl = document.getElementById('broadsheetStats');
  if (!statsEl) return;
  const inputs = document.querySelectorAll('.bs-input');
  let enteredCount = 0;
  inputs.forEach(inp => { if (inp.value.trim() !== '') enteredCount++; });
  const totalSlots = inputs.length;
  const pct = totalSlots > 0 ? Math.round((enteredCount / totalSlots) * 100) : 0;
  statsEl.innerHTML = `📊 Entry Progress: <strong>${enteredCount} / ${totalSlots}</strong> scores entered (<strong>${pct}%</strong> complete)`;
}

async function saveBroadsheetScores() {
  const classId = parseInt(document.getElementById('class_section_id').value);
  const semesterId = parseInt(document.getElementById('semester_id').value);

  if (!classId || !semesterId) return alert('Please select Class Section and Term.');

  const inputs = document.querySelectorAll('.bs-input');
  const records = [];

  inputs.forEach(inp => {
    const valStr = inp.value.trim();
    if (valStr !== '') {
      const totalScore = parseFloat(valStr) || 0.0;
      const sId = parseInt(inp.dataset.studentId);
      const subId = parseInt(inp.dataset.subjectId);

      // Split 50% CA / 50% Exam or 30% CA / 70% Exam
      const caPart = Math.round(totalScore * 0.5 * 10) / 10;
      const exPart = Math.round((totalScore - caPart) * 10) / 10;

      records.push({
        student_id: sId,
        subject_id: subId,
        class_score: caPart,
        exam_score: exPart
      });
    }
  });

  if (records.length === 0) {
    return alert('No scores have been entered yet.');
  }

  const btn = document.getElementById('saveBroadsheetBtn');
  const msg = document.getElementById('broadsheetMsg');
  if (btn) { btn.disabled = true; btn.textContent = '⏳ Saving All Class Marks...'; }
  if (msg) msg.innerHTML = '';

  try {
    const res = await fetch(`${API_BASE}/results/batch-class-matrix`, {
      method: 'POST',
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({
        class_section_id: classId,
        semester_id: semesterId,
        records: records
      })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || data.message || 'Saving failed');

    if (msg) {
      msg.innerHTML = `
        <div style="background:rgba(16,185,129,0.15); color:#34d399; border:1px solid rgba(16,185,129,0.3); padding:10px 16px; border-radius:8px; font-weight:600;">
          ✓ <strong>Success:</strong> ${data.message}
        </div>
      `;
    }

    if (window.showToast) window.showToast(data.message || 'All class scores saved successfully!', 'success');
  } catch (err) {
    if (msg) {
      msg.innerHTML = `
        <div style="background:rgba(239,68,68,0.15); color:#f87171; border:1px solid rgba(239,68,68,0.3); padding:10px 16px; border-radius:8px;">
          ❌ <strong>Error:</strong> ${err.message}
        </div>
      `;
    }
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = '💾 Save All Class Marks'; }
  }
}

window.switchDeskMode = switchDeskMode;
window.handleFilterSubmit = handleFilterSubmit;
window.handleClassChange = handleClassChange;
window.toggleEntryMode = toggleEntryMode;
window.saveAllScores = saveAllScores;
window.saveBroadsheetScores = saveBroadsheetScores;

initFilters();
