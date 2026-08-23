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

function formatGradePill(grade) {
  if (!grade) return '—';
  let pillClass = 'grade-f';
  if (grade === 'A1') pillClass = 'grade-a1';
  else if (grade.startsWith('B')) pillClass = 'grade-b';
  else if (grade.startsWith('C')) pillClass = 'grade-c';
  else if (grade.startsWith('D') || grade.startsWith('E')) pillClass = 'grade-d';
  return `<span class="grade-pill ${pillClass}">${grade}</span>`;
}

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
          <td style="font-weight:600; padding:10px 8px;">${escapeHtml(s.full_name)}</td>
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

    // Spreadsheet Keyboard Navigation & Live Validation
    const allRows = Array.from(body.querySelectorAll('tr[data-student-id]'));
    
    allRows.forEach((row, rowIndex) => {
      const inputsInRow = Array.from(row.querySelectorAll('.spreadsheet-input'));

      inputsInRow.forEach((input, colIndex) => {
        // Auto-select entire number on focus for fast replacement
        input.addEventListener('focus', () => {
          setTimeout(() => input.select(), 10);
        });

        // Keyboard Arrow & Enter spreadsheet navigation
        input.addEventListener('keydown', (e) => {
          if (e.key === 'ArrowDown' || e.key === 'Enter') {
            e.preventDefault();
            const nextRow = allRows[rowIndex + 1];
            if (nextRow) {
              const targetInput = nextRow.querySelectorAll('.spreadsheet-input')[colIndex];
              if (targetInput) { targetInput.focus(); targetInput.select(); }
            }
          } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            const prevRow = allRows[rowIndex - 1];
            if (prevRow) {
              const targetInput = prevRow.querySelectorAll('.spreadsheet-input')[colIndex];
              if (targetInput) { targetInput.focus(); targetInput.select(); }
            }
          } else if (e.key === 'ArrowRight' && input.selectionEnd === input.value.length) {
            const nextInput = inputsInRow[colIndex + 1];
            if (nextInput) { nextInput.focus(); nextInput.select(); }
          } else if (e.key === 'ArrowLeft' && input.selectionStart === 0) {
            const prevInput = inputsInRow[colIndex - 1];
            if (prevInput) { prevInput.focus(); prevInput.select(); }
          }
        });

        // Live validation & score calculations
        input.addEventListener('input', () => {
          const val = parseFloat(input.value);
          const maxVal = parseFloat(input.dataset.max || 100);

          // Validation check
          if (val > maxVal || val < 0) {
            input.classList.add('score-invalid');
            input.title = `Score exceeds maximum allowed (${maxVal})`;
          } else {
            input.classList.remove('score-invalid');
            input.removeAttribute('title');
          }

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
          if (gradeEl) gradeEl.innerHTML = formatGradePill(grade);
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
