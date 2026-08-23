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

function calculateGrade(total) {
  if (total >= 80) return 'A1';
  if (total >= 70) return 'B2';
  if (total >= 65) return 'B3';
  if (total >= 60) return 'C4';
  if (total >= 55) return 'C5';
  if (total >= 50) return 'C6';
  if (total >= 45) return 'D7';
  if (total >= 40) return 'E8';
  return 'F9';
}

async function loadStudentList() {
  const classId = document.getElementById('class_section_id').value;
  const subjectId = document.getElementById('subject_id').value;
  const semesterId = document.getElementById('semester_id').value;

  if (!classId) return alert('Please select a class section.');

  const body = document.getElementById('studentListBody');
  body.innerHTML = '<tr><td colspan="10" style="text-align:center; padding:20px;">Loading students & existing scores...</td></tr>';

  try {
    const [resStudents, resScores] = await Promise.all([
      fetch(`${API_BASE}/students/`, { headers: getHeaders() }),
      fetch(`${API_BASE}/results/`, { headers: getHeaders() })
    ]);

    const allStudents = await resStudents.json();
    const allScores = resScores.ok ? await resScores.json() : [];

    const filteredStudents = allStudents.filter(s => String(s.class_section_id) === String(classId));

    if (filteredStudents.length === 0) {
      body.innerHTML = '<tr><td colspan="10" style="text-align:center; padding:20px; color:var(--text-secondary);">No students found in this class section.</td></tr>';
      return;
    }

    const { classWeight, examWeight } = getScoreWeights();
    const caHeader = document.getElementById('caHeader');
    const examHeader = document.getElementById('examHeader');
    if (caHeader) caHeader.textContent = `CA Score (0 - ${classWeight})`;
    if (examHeader) examHeader.textContent = `Exam Score (0 - ${examWeight})`;

    // Map existing scores by student_id
    const scoreMap = {};
    allScores.forEach(sc => {
      if (String(sc.subject_id) === String(subjectId) && String(sc.semester_id) === String(semesterId)) {
        scoreMap[sc.student_id] = sc;
      }
    });

    body.innerHTML = filteredStudents.map(s => {
      const sc = scoreMap[s.id] || {};
      const ex1 = sc.ex1 || 0;
      const ex2 = sc.ex2 || 0;
      const ass1 = sc.ass1 || 0;
      const grp = sc.grp_work || 0;
      const mid = sc.mid_sem || 0;
      const caVal = sc.class_score || (ex1 + ex2 + ass1 + grp + mid);
      const examVal = sc.exam_score || 0;
      const totalVal = (sc.total_score || (caVal + examVal)).toFixed(2);
      const gradeVal = sc.grade || calculateGrade(parseFloat(totalVal));

      return `
        <tr data-student-id="${s.id}">
          <td style="font-weight:600;">${escapeHtml(s.full_name)}</td>
          <td class="simple-col" style="${currentMode === 'detailed' ? 'display:none;' : ''}">
            <input type="number" class="class-score" min="0" max="${classWeight}" step="0.1" value="${caVal}">
          </td>
          <td class="detailed-col" style="${currentMode === 'simple' ? 'display:none;' : ''}">
            <input type="number" class="ex1-score" min="0" max="10" step="0.5" value="${ex1}" style="width:60px;">
          </td>
          <td class="detailed-col" style="${currentMode === 'simple' ? 'display:none;' : ''}">
            <input type="number" class="ex2-score" min="0" max="10" step="0.5" value="${ex2}" style="width:60px;">
          </td>
          <td class="detailed-col" style="${currentMode === 'simple' ? 'display:none;' : ''}">
            <input type="number" class="ass1-score" min="0" max="10" step="0.5" value="${ass1}" style="width:60px;">
          </td>
          <td class="detailed-col" style="${currentMode === 'simple' ? 'display:none;' : ''}">
            <input type="number" class="grp-score" min="0" max="10" step="0.5" value="${grp}" style="width:60px;">
          </td>
          <td class="detailed-col" style="${currentMode === 'simple' ? 'display:none;' : ''}">
            <input type="number" class="mid-score" min="0" max="20" step="0.5" value="${mid}" style="width:60px;">
          </td>
          <td>
            <input type="number" class="exam-score" min="0" max="${examWeight}" step="0.5" value="${examVal}">
          </td>
          <td class="total-preview" style="font-weight:700; color:#818cf8;">${totalVal}</td>
          <td class="grade-preview" style="font-weight:700; color:#34d399;">${gradeVal}</td>
        </tr>
      `;
    }).join('');

    // Add event listeners for real-time live total & grade preview
    body.querySelectorAll('tr[data-student-id]').forEach(row => {
      row.querySelectorAll('input').forEach(input => {
        input.addEventListener('input', () => {
          let caVal = 0;
          if (currentMode === 'detailed') {
            const ex1 = parseFloat(row.querySelector('.ex1-score')?.value) || 0;
            const ex2 = parseFloat(row.querySelector('.ex2-score')?.value) || 0;
            const ass1 = parseFloat(row.querySelector('.ass1-score')?.value) || 0;
            const grp = parseFloat(row.querySelector('.grp-score')?.value) || 0;
            const mid = parseFloat(row.querySelector('.mid-score')?.value) || 0;
            caVal = ex1 + ex2 + ass1 + grp + mid;
            const classInput = row.querySelector('.class-score');
            if (classInput) classInput.value = caVal;
          } else {
            caVal = parseFloat(row.querySelector('.class-score')?.value) || 0;
          }

          const examVal = parseFloat(row.querySelector('.exam-score')?.value) || 0;
          const total = caVal + examVal;
          const grade = calculateGrade(total);

          const totalEl = row.querySelector('.total-preview');
          const gradeEl = row.querySelector('.grade-preview');
          if (totalEl) totalEl.textContent = total.toFixed(2);
          if (gradeEl) gradeEl.textContent = grade;
        });
      });
    });

  } catch (error) {
    console.error('Error loading students:', error);
    body.innerHTML = `<tr><td colspan="10" style="text-align:center; padding:20px; color:var(--danger-color);">Error loading students: ${error.message}</td></tr>`;
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

async function saveAllScores() {
  const subjectId = document.getElementById('subject_id').value;
  const semesterId = document.getElementById('semester_id').value;

  if (!subjectId || !semesterId) return alert('Please select subject and semester.');

  const rows = document.querySelectorAll('#studentListBody tr[data-student-id]');
  if (rows.length === 0) return alert('No students to save.');

  let successCount = 0;
  for (const row of rows) {
    const studentId = row.dataset.studentId;
    const ex1 = parseFloat(row.querySelector('.ex1-score')?.value) || 0;
    const ex2 = parseFloat(row.querySelector('.ex2-score')?.value) || 0;
    const ass1 = parseFloat(row.querySelector('.ass1-score')?.value) || 0;
    const grp = parseFloat(row.querySelector('.grp-score')?.value) || 0;
    const mid = parseFloat(row.querySelector('.mid-score')?.value) || 0;
    const classScore = (currentMode === 'detailed') ? (ex1 + ex2 + ass1 + grp + mid) : (parseFloat(row.querySelector('.class-score')?.value) || 0);
    const examScore = parseFloat(row.querySelector('.exam-score')?.value) || 0;

    const payload = {
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
    };

    try {
      const res = await fetch(`${API_BASE}/results/`, {
        method: 'POST',
        headers: getHeaders({ 
          'Content-Type': 'application/json'
        }),
        body: JSON.stringify(payload)
      });
      if (res.ok) successCount++;
    } catch (e) {
      console.error(`Failed to save for student ${studentId}`, e);
    }
  }

  const msg = document.getElementById('bulkMsg');
  if (msg) msg.innerHTML = `<span style="color:#34d399; font-weight:700;">✅ Successfully saved ${successCount} out of ${rows.length} student scores.</span>`;
  alert(`Successfully saved ${successCount} out of ${rows.length} scores.`);
}

initFilters();
