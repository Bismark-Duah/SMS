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

async function initFilters() {
  try {
    const isShsMode = (localStorage.getItem('school_mode') || '').toUpperCase() === 'SHS_ONLY';
    const subUrl = `${API_BASE}/subjects/my-assignments`;
    const [resClasses, resSubjects, resSemesters] = await Promise.all([
      fetch(`${API_BASE}/classes/my-classes`, { headers: getHeaders() }),
      fetch(subUrl, { headers: getHeaders() }),
      fetch(`${API_BASE}/academic/semesters`, { headers: getHeaders() }),
    ]);

    const classes = await resClasses.json();
    const subjects = await resSubjects.json();
    const semesters = await resSemesters.json();

    document.getElementById('class_section_id').innerHTML = '<option value="">Select Class...</option>' + 
      classes.map(c => `<option value="${c.id}">${c.name}</option>`).join('');

    document.getElementById('subject_id').innerHTML = '<option value="">Select Subject...</option>' + 
      subjects.map(s => `<option value="${s.id}">${s.name}</option>`).join('');

    document.getElementById('semester_id').innerHTML = '<option value="">Select Term...</option>' + 
      semesters.map(s => `<option value="${s.id}">${s.name}</option>`).join('');

  } catch (error) {
    console.error('Error initializing filters:', error);
  }
}

let currentMode = 'simple';

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
  if (grade === 'A1') pillClass = 'grade-a1';
  else if (grade.startsWith('B')) pillClass = 'grade-b';
  else if (grade.startsWith('C')) pillClass = 'grade-c';
  else if (grade.startsWith('D') || grade.startsWith('E')) pillClass = 'grade-d';
  return `<span class="grade-pill ${pillClass}">${grade}</span>`;
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

async function loadStudentList() {
  const classId = document.getElementById('class_section_id').value;
  const subjectId = document.getElementById('subject_id').value;
  const semesterId = document.getElementById('semester_id').value;

  if (!classId || !subjectId || !semesterId) {
    alert('Please select Class Section, Subject, and Term first.');
    return;
  }

  const body = document.getElementById('studentListBody');
  body.innerHTML = `<tr><td colspan="10" style="text-align:center; padding:20px;">Loading student list...</td></tr>`;

  const { classWeight, examWeight } = getScoreWeights();
  const caHeader = document.getElementById('caHeader');
  const examHeader = document.getElementById('examHeader');
  if (caHeader) caHeader.textContent = `CA Score (0 - ${classWeight})`;
  if (examHeader) examHeader.textContent = `Exam Score (0 - ${examWeight})`;

  let students = [];

  try {
    const res = await fetch(`${API_BASE}/results/class/${classId}/students?semester_id=${semesterId}&subject_id=${subjectId}`, {
      headers: getHeaders()
    });

    if (res.ok) {
      students = await res.json();
      if (window.OfflineStore) {
        window.OfflineStore.cacheRoster(classId, subjectId, semesterId, students);
      }
    } else {
      throw new Error(`Server returned ${res.status}`);
    }
  } catch (netErr) {
    console.warn("Network fetch failed, checking offline cache...", netErr);
    if (window.OfflineStore) {
      const cached = await window.OfflineStore.getCachedRoster(classId, subjectId, semesterId);
      if (cached && cached.length > 0) {
        students = cached;
      }
    }
    if (!students || students.length === 0) {
      body.innerHTML = `<tr><td colspan="10" style="text-align:center; padding:20px; color:var(--danger-color);">Unable to load students online or from offline cache.</td></tr>`;
      return;
    }
  }

  if (students.length === 0) {
    body.innerHTML = `<tr><td colspan="10" style="text-align:center; padding:20px; color:var(--text-secondary);">No enrolled students found for this class and subject.</td></tr>`;
    return;
  }

  body.innerHTML = students.map(s => {
    const sc = s.score || {};
    const ex1 = sc.ex1 || 0;
    const ex2 = sc.ex2 || 0;
    const ass1 = sc.ass1 || 0;
    const grp = sc.grp_work || 0;
    const mid = sc.mid_sem || 0;
    const caVal = sc.class_score !== undefined && sc.class_score !== null ? sc.class_score : (ex1 + ex2 + ass1 + grp + mid);
    const examVal = sc.exam_score || 0;
    const totalVal = (sc.total_score !== undefined && sc.total_score !== null ? sc.total_score : (caVal + examVal)).toFixed(2);
    const gradeVal = sc.grade || calculateGrade(parseFloat(totalVal));

    return `
      <tr data-student-id="${s.id}">
        <td style="font-weight:600; padding:10px 8px;">${escapeHtml(s.full_name || s.name)}</td>
        <td class="simple-col" style="${currentMode === 'detailed' ? 'display:none;' : ''}">
          <input type="number" class="spreadsheet-input class-score" min="0" max="${classWeight}" step="0.1" value="${caVal}" data-max="${classWeight}">
        </td>
        <td class="detailed-col" style="${currentMode === 'simple' ? 'display:none;' : ''}">
          <input type="number" class="spreadsheet-input ex1-score" min="0" max="10" step="0.5" value="${ex1}" data-max="10" style="width:62px;">
        </td>
        <td class="detailed-col" style="${currentMode === 'simple' ? 'display:none;' : ''}">
          <input type="number" class="spreadsheet-input ex2-score" min="0" max="10" step="0.5" value="${ex2}" data-max="10" style="width:62px;">
        </td>
        <td class="detailed-col" style="${currentMode === 'simple' ? 'display:none;' : ''}">
          <input type="number" class="spreadsheet-input ass1-score" min="0" max="10" step="0.5" value="${ass1}" data-max="10" style="width:62px;">
        </td>
        <td class="detailed-col" style="${currentMode === 'simple' ? 'display:none;' : ''}">
          <input type="number" class="spreadsheet-input grp-score" min="0" max="10" step="0.5" value="${grp}" data-max="10" style="width:62px;">
        </td>
        <td class="detailed-col" style="${currentMode === 'simple' ? 'display:none;' : ''}">
          <input type="number" class="spreadsheet-input mid-score" min="0" max="20" step="0.5" value="${mid}" data-max="20" style="width:62px;">
        </td>
        <td>
          <input type="number" class="spreadsheet-input exam-score" min="0" max="${examWeight}" step="0.5" value="${examVal}" data-max="${examWeight}">
        </td>
        <td class="total-preview tabular-num" style="font-weight:700; color:#818cf8; text-align:center;">${totalVal}</td>
        <td class="grade-preview" style="text-align:center;">${formatGradePill(gradeVal)}</td>
      </tr>
    `;
  }).join('');

  // Keyboard navigation and dynamic total recalculation
  const allRows = Array.from(body.querySelectorAll('tr[data-student-id]'));
  allRows.forEach((row, rowIndex) => {
    const inputsInRow = Array.from(row.querySelectorAll('.spreadsheet-input'));
    inputsInRow.forEach((input) => {
      input.addEventListener('input', () => {
        const ex1 = parseFloat(row.querySelector('.ex1-score')?.value) || 0;
        const ex2 = parseFloat(row.querySelector('.ex2-score')?.value) || 0;
        const ass1 = parseFloat(row.querySelector('.ass1-score')?.value) || 0;
        const grp = parseFloat(row.querySelector('.grp-score')?.value) || 0;
        const mid = parseFloat(row.querySelector('.mid-score')?.value) || 0;
        const caVal = (currentMode === 'detailed') ? (ex1 + ex2 + ass1 + grp + mid) : (parseFloat(row.querySelector('.class-score')?.value) || 0);
        const examVal = parseFloat(row.querySelector('.exam-score')?.value) || 0;
        const total = caVal + examVal;
        const grade = calculateGrade(total);

        const totalEl = row.querySelector('.total-preview');
        const gradeEl = row.querySelector('.grade-preview');
        if (totalEl) totalEl.textContent = total.toFixed(2);
        if (gradeEl) gradeEl.innerHTML = formatGradePill(grade);
      });
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
    const ex1 = parseFloat(row.querySelector('.ex1-score')?.value) || 0;
    const ex2 = parseFloat(row.querySelector('.ex2-score')?.value) || 0;
    const ass1 = parseFloat(row.querySelector('.ass1-score')?.value) || 0;
    const grp = parseFloat(row.querySelector('.grp-score')?.value) || 0;
    const mid = parseFloat(row.querySelector('.mid-score')?.value) || 0;
    const classScore = (currentMode === 'detailed') ? (ex1 + ex2 + ass1 + grp + mid) : (parseFloat(row.querySelector('.class-score')?.value) || 0);
    const examScore = parseFloat(row.querySelector('.exam-score')?.value) || 0;

    payloads.push({
      student_id: parseInt(studentId),
      subject_id: parseInt(subjectId),
      semester_id: parseInt(semesterId),
      ex1: ex1,
      ex2: ex2,
      ass1: ass1,
      grp_work: grp,
      mid_sem: mid,
      class_score: classScore,
      exam_score: examScore
    });
  }

  const saveBtn = document.getElementById('saveBulkBtn');
  if (saveBtn) saveBtn.disabled = true;

  let successCount = 0;
  let offlineFallback = false;

  if (navigator.onLine) {
    for (const p of payloads) {
      try {
        const res = await fetch(`${API_BASE}/results/`, {
          method: 'POST',
          headers: getHeaders({ 'Content-Type': 'application/json' }),
          body: JSON.stringify(p)
        });
        if (res.ok) {
          successCount++;
        } else {
          offlineFallback = true;
        }
      } catch (err) {
        offlineFallback = true;
      }
    }
  } else {
    offlineFallback = true;
  }

  if (offlineFallback && window.OfflineStore) {
    await window.OfflineStore.queueScores(payloads);
    const msg = document.getElementById('bulkMsg');
    if (msg) msg.innerHTML = `<span style="color:#f59e0b; font-weight:700;">💾 Offline Queue: ${payloads.length} scores saved locally in IndexedDB! Will auto-sync when online.</span>`;
    alert(`Saved ${payloads.length} student scores to offline local store!`);
  } else {
    const msg = document.getElementById('bulkMsg');
    if (msg) msg.innerHTML = `<span style="color:#34d399; font-weight:700;">✅ Successfully saved ${successCount} out of ${payloads.length} student scores to server.</span>`;
    alert(`Successfully saved ${successCount} out of ${payloads.length} scores to server.`);
  }

  if (saveBtn) saveBtn.disabled = false;
}

initFilters();
