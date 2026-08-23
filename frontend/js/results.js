const API_BASE = window.API_BASE || (window.location.origin.includes('http') ? (window.location.origin + '/api') : 'http://127.0.0.1:8000/api');

const token = localStorage.getItem('accessToken');
if (!token) window.location.href = 'auth.html';

function getHeaders(extra = {}) {
  return { 'Authorization': `Bearer ${token}`, ...extra };
}

function getScoreWeights() {
  const classWeight = parseFloat(localStorage.getItem('class_score_weight')) || 30;
  const examWeight = parseFloat(localStorage.getItem('exam_score_weight')) || 70;
  return { classWeight, examWeight };
}

// ── Grade Calculation (mirrors GradingService WAEC logic) ─────────────────────
function calcGrade(total) {
  if (total >= 80) return { grade: 'A1', remark: 'Excellent' };
  if (total >= 70) return { grade: 'B2', remark: 'Very Good' };
  if (total >= 60) return { grade: 'B3', remark: 'Good' };
  if (total >= 55) return { grade: 'C4', remark: 'Credit' };
  if (total >= 50) return { grade: 'C5', remark: 'Credit' };
  if (total >= 45) return { grade: 'C6', remark: 'Credit' };
  if (total >= 40) return { grade: 'D7', remark: 'Pass' };
  if (total >= 35) return { grade: 'E8', remark: 'Pass' };
  return { grade: 'F9', remark: 'Fail' };
}

function gradeChipHTML(grade) {
  return `<span class="grade-chip grade-${grade}">${grade}</span>`;
}

// ── Tab Switching ──────────────────────────────────────────────────────────────
function switchTab(tabId) {
  document.querySelectorAll('.tab-panel').forEach(p => p.style.display = 'none');
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  if (tabId === 'entry') {
    document.getElementById('panelEntry').style.display = 'block';
    document.getElementById('tabEntryBtn').classList.add('active');
  } else {
    document.getElementById('panelBrowser').style.display = 'block';
    document.getElementById('tabBrowserBtn').classList.add('active');
  }
}

let allClasses = [];
let allSemesters = [];
let allSubjects = [];

async function handleClassChange(classId, prefix) {
  const semSelect = document.getElementById(`${prefix}_semester_id`);
  const subSelect = document.getElementById(`${prefix}_subject_id`);

  if (!classId) {
    semSelect.innerHTML = '<option value="">Select Class first...</option>';
    semSelect.disabled = true;
    subSelect.innerHTML = prefix === 'br' ? '<option value="">All Subjects</option>' : '<option value="">Select Class first...</option>';
    subSelect.disabled = true;
    return;
  }

  const selectedClass = allClasses.find(c => c.id == classId);
  const schoolType = selectedClass ? selectedClass.school_type : null;

  // Filter Semesters / Terms based on school type
  let filteredSemesters = [];
  if (schoolType === 'SHS') {
    filteredSemesters = allSemesters.filter(s => s.name.toLowerCase().includes('semester'));
  } else {
    filteredSemesters = allSemesters.filter(s => s.name.toLowerCase().includes('term'));
  }

  if (filteredSemesters.length === 0) {
    semSelect.innerHTML = '<option value="">No matching Semesters/Terms found</option>';
    semSelect.disabled = true;
  } else {
    semSelect.innerHTML = '<option value="">Select Term / Semester...</option>' +
      filteredSemesters.map(s => `<option value="${s.id}">${s.name} (${s.academic_year?.label || ''})</option>`).join('');
    semSelect.disabled = false;
  }

  // Fetch only class-assigned subjects
  subSelect.innerHTML = '<option value="">Loading subjects...</option>';
  subSelect.disabled = true;

  try {
    const res = await fetch(`${API_BASE}/classes/${classId}/subjects`, { headers: getHeaders() });
    if (!res.ok) throw new Error('Failed to fetch subjects');
    const assignedSubjects = await res.json();

    if (assignedSubjects.length === 0) {
      subSelect.innerHTML = '<option value="">No subjects assigned to this class</option>';
      subSelect.disabled = true;
    } else {
      const defaultOpt = prefix === 'br' ? '<option value="">All Subjects</option>' : '<option value="">Select Subject...</option>';
      subSelect.innerHTML = defaultOpt + assignedSubjects.map(s => `<option value="${s.id}">${s.name}</option>`).join('');
      subSelect.disabled = false;
    }
  } catch (error) {
    console.error('Error fetching subjects for class:', error);
    subSelect.innerHTML = '<option value="">Error loading subjects</option>';
    subSelect.disabled = true;
  }
}

// ── Populate Dropdowns ────────────────────────────────────────────────────────
async function initPage() {
  try {
    const [resClasses, resSemesters, resSubjects] = await Promise.all([
      fetch(`${API_BASE}/classes/my-classes`, { headers: getHeaders() }),
      fetch(`${API_BASE}/academic/semesters`, { headers: getHeaders() }),
      fetch(`${API_BASE}/subjects/my-assignments`, { headers: getHeaders() }),
    ]);

    allClasses   = await resClasses.json();
    allSemesters = await resSemesters.json();
    allSubjects  = await resSubjects.json();

    const classOpts = '<option value="">Select Class...</option>' +
      allClasses.map(c => `<option value="${c.id}">${c.name}</option>`).join('');

    ['entry_class_id', 'br_class_id'].forEach(id => {
      document.getElementById(id).innerHTML = classOpts;
    });

    // Set initial states
    ['entry_semester_id', 'br_semester_id'].forEach(id => {
      const el = document.getElementById(id);
      el.innerHTML = '<option value="">Select Class first...</option>';
      el.disabled = true;
    });

    document.getElementById('entry_subject_id').innerHTML = '<option value="">Select Class first...</option>';
    document.getElementById('entry_subject_id').disabled = true;

    document.getElementById('br_subject_id').innerHTML = '<option value="">All Subjects</option>';
    document.getElementById('br_subject_id').disabled = true;

    // Attach listeners
    document.getElementById('entry_class_id').addEventListener('change', (e) => handleClassChange(e.target.value, 'entry'));
    document.getElementById('br_class_id').addEventListener('change', (e) => handleClassChange(e.target.value, 'br'));

  } catch (e) {
    console.error('Failed to initialize page:', e);
  }
}

// ── PANEL 1: Bulk Score Entry ─────────────────────────────────────────────────
let isBreakdownMode = false;
let currentStudentsData = [];

function toggleBreakdownMode(checked) {
  isBreakdownMode = checked;
  if (currentEntryContext.classId) {
    renderEntryTable();
  }
}

async function loadStudentsForEntry() {
  const classId    = document.getElementById('entry_class_id').value;
  const semesterId = document.getElementById('entry_semester_id').value;
  const subjectId  = document.getElementById('entry_subject_id').value;
  const entryMsg   = document.getElementById('entryMsg');

  if (!classId || !semesterId || !subjectId) {
    entryMsg.innerHTML = '<span style="color:var(--error-color)">Select class, semester, and subject.</span>';
    return;
  }

  entryMsg.innerHTML = '<span style="opacity:.6">Loading students...</span>';
  currentEntryContext = { classId, semesterId, subjectId };

  try {
    const res = await fetch(
      `${API_BASE}/results/class/${classId}/students?semester_id=${semesterId}&subject_id=${subjectId}`,
      { headers: getHeaders() }
    );
    if (!res.ok) throw new Error(await res.text());
    currentStudentsData = await res.json();

    if (currentStudentsData.length === 0) {
      entryMsg.innerHTML = '<span style="opacity:.6">No active students found in this class.</span>';
      document.getElementById('entryCard').style.display = 'none';
      return;
    }

    const className   = document.getElementById('entry_class_id').selectedOptions[0]?.text || '';
    const semName     = document.getElementById('entry_semester_id').selectedOptions[0]?.text || '';
    const subjectName = document.getElementById('entry_subject_id').selectedOptions[0]?.text || '';

    document.getElementById('entryTitle').textContent = `${className} · ${subjectName} · ${semName}`;
    renderEntryTable();

    document.getElementById('entryCard').style.display = 'block';
    entryMsg.innerHTML = '';
    document.getElementById('saveMsg').innerHTML = '';
  } catch (e) {
    entryMsg.innerHTML = `<span style="color:var(--error-color)">Error: ${e.message}</span>`;
  }
}

function renderEntryTable() {
  const tableContainer = document.querySelector('#entryCard div[style*="overflow-x"]');
  if (!tableContainer) return;
  const { classWeight, examWeight } = getScoreWeights();

  if (isBreakdownMode) {
    tableContainer.innerHTML = `
      <table style="width:100%; font-size:0.85rem;">
        <thead>
          <tr>
            <th>#</th>
            <th>Code</th>
            <th>Student Name</th>
            <th>Ex 1<br><small>(10%)</small></th>
            <th>Ex 2<br><small>(10%)</small></th>
            <th>Ass 1<br><small>(10%)</small></th>
            <th>Ass 2<br><small>(10%)</small></th>
            <th>Ind Proj<br><small>(20%)</small></th>
            <th>Grp Work<br><small>(10%)</small></th>
            <th>Pract<br><small>(10%)</small></th>
            <th>Mid-Sem<br><small>(20%)</small></th>
            <th>${classWeight}% Class<br><small>(Auto)</small></th>
            <th>${examWeight}% Exam<br><small>(Max ${examWeight})</small></th>
            <th>Total<br><small>(100%)</small></th>
            <th>Grade</th>
          </tr>
        </thead>
        <tbody id="entryBody">
          ${currentStudentsData.map((s, i) => {
            const ex1 = s.ex1 || 0, ex2 = s.ex2 || 0, ass1 = s.ass1 || 0, ass2 = s.ass2 || 0;
            const ind_proj = s.ind_proj || 0, grp_work = s.grp_work || 0, pract_work = s.pract_work || 0, mid_sem = s.mid_sem || 0;
            const rawSum = ex1 + ex2 + ass1 + ass2 + ind_proj + grp_work + pract_work + mid_sem;
            const classScore = rawSum > 0 ? Math.min(classWeight, parseFloat((rawSum * (classWeight / 100)).toFixed(1))) : s.class_score;
            const total = Math.min(100, classScore + s.exam_score);
            const { grade } = calcGrade(total);

            return `
              <tr id="row-${s.student_id}" data-student-id="${s.student_id}" data-score-id="${s.score_id || ''}">
                <td>${i + 1}</td>
                <td><strong>${s.student_code}</strong></td>
                <td>${s.student_name}</td>
                <td><input type="number" class="score-input ex1-input" style="width:50px;" min="0" max="10" value="${ex1}" oninput="updateBreakdownRowTotal(${s.student_id})" /></td>
                <td><input type="number" class="score-input ex2-input" style="width:50px;" min="0" max="10" value="${ex2}" oninput="updateBreakdownRowTotal(${s.student_id})" /></td>
                <td><input type="number" class="score-input ass1-input" style="width:50px;" min="0" max="10" value="${ass1}" oninput="updateBreakdownRowTotal(${s.student_id})" /></td>
                <td><input type="number" class="score-input ass2-input" style="width:50px;" min="0" max="10" value="${ass2}" oninput="updateBreakdownRowTotal(${s.student_id})" /></td>
                <td><input type="number" class="score-input ind-proj-input" style="width:50px;" min="0" max="20" value="${ind_proj}" oninput="updateBreakdownRowTotal(${s.student_id})" /></td>
                <td><input type="number" class="score-input grp-work-input" style="width:50px;" min="0" max="10" value="${grp_work}" oninput="updateBreakdownRowTotal(${s.student_id})" /></td>
                <td><input type="number" class="score-input pract-work-input" style="width:50px;" min="0" max="10" value="${pract_work}" oninput="updateBreakdownRowTotal(${s.student_id})" /></td>
                <td><input type="number" class="score-input mid-sem-input" style="width:50px;" min="0" max="20" value="${mid_sem}" oninput="updateBreakdownRowTotal(${s.student_id})" /></td>
                <td class="total-cell" id="class-score-${s.student_id}" style="color:#22d3ee;">${classScore.toFixed(1)}</td>
                <td><input type="number" class="score-input exam-score-input" style="width:55px;" min="0" max="${examWeight}" step="0.5" value="${s.exam_score}" oninput="updateBreakdownRowTotal(${s.student_id})" /></td>
                <td class="total-cell" id="total-${s.student_id}">${total.toFixed(1)}</td>
                <td id="grade-${s.student_id}">${gradeChipHTML(grade)}</td>
              </tr>`;
          }).join('')}
        </tbody>
      </table>`;
  } else {
    tableContainer.innerHTML = `
      <table style="width:100%;">
        <thead>
          <tr>
            <th>#</th>
            <th>Code</th>
            <th>Student Name</th>
            <th>Class Score<br><small style="opacity:.6">(max ${classWeight})</small></th>
            <th>Exam Score<br><small style="opacity:.6">(max ${examWeight})</small></th>
            <th>Total</th>
            <th>Grade</th>
          </tr>
        </thead>
        <tbody id="entryBody">
          ${currentStudentsData.map((s, i) => {
            const { grade } = calcGrade(s.total_score);
            return `
              <tr id="row-${s.student_id}" data-student-id="${s.student_id}" data-score-id="${s.score_id || ''}">
                <td>${i + 1}</td>
                <td><strong>${s.student_code}</strong></td>
                <td>${s.student_name}</td>
                <td>
                  <input type="number" class="score-input class-score-input" min="0" max="${classWeight}" step="0.5"
                    value="${s.class_score}" oninput="updateRowTotal(${s.student_id})" />
                </td>
                <td>
                  <input type="number" class="score-input exam-score-input" min="0" max="${examWeight}" step="0.5"
                    value="${s.exam_score}" oninput="updateRowTotal(${s.student_id})" />
                </td>
                <td class="total-cell" id="total-${s.student_id}">${s.total_score.toFixed(1)}</td>
                <td id="grade-${s.student_id}">${gradeChipHTML(grade)}</td>
              </tr>`;
          }).join('')}
        </tbody>
      </table>`;
  }
}

function updateBreakdownRowTotal(studentId) {
  const { classWeight } = getScoreWeights();
  const row = document.getElementById(`row-${studentId}`);
  if (!row) return;
  const ex1 = parseFloat(row.querySelector('.ex1-input').value) || 0;
  const ex2 = parseFloat(row.querySelector('.ex2-input').value) || 0;
  const ass1 = parseFloat(row.querySelector('.ass1-input').value) || 0;
  const ass2 = parseFloat(row.querySelector('.ass2-input').value) || 0;
  const ind_proj = parseFloat(row.querySelector('.ind-proj-input').value) || 0;
  const grp_work = parseFloat(row.querySelector('.grp-work-input').value) || 0;
  const pract_work = parseFloat(row.querySelector('.pract-work-input').value) || 0;
  const mid_sem = parseFloat(row.querySelector('.mid-sem-input').value) || 0;

  const rawSum = ex1 + ex2 + ass1 + ass2 + ind_proj + grp_work + pract_work + mid_sem;
  const classScore = parseFloat((rawSum * (classWeight / 100)).toFixed(1));
  const examScore = parseFloat(row.querySelector('.exam-score-input').value) || 0;
  const total = Math.min(100, classScore + examScore);
  const { grade } = calcGrade(total);

  document.getElementById(`class-score-${studentId}`).textContent = classScore.toFixed(1);
  document.getElementById(`total-${studentId}`).textContent = total.toFixed(1);
  document.getElementById(`grade-${studentId}`).innerHTML = gradeChipHTML(grade);
}

function updateRowTotal(studentId) {
  const { classWeight, examWeight } = getScoreWeights();
  const row = document.getElementById(`row-${studentId}`);
  if (!row) return;
  const classScore = parseFloat(row.querySelector('.class-score-input').value) || 0;
  const examScore  = parseFloat(row.querySelector('.exam-score-input').value) || 0;
  const total      = Math.min(classScore, classWeight) + Math.min(examScore, examWeight);
  const { grade }  = calcGrade(total);
  document.getElementById(`total-${studentId}`).textContent = total.toFixed(1);
  document.getElementById(`grade-${studentId}`).innerHTML   = gradeChipHTML(grade);
}

async function saveAllScores() {
  const { classId, semesterId, subjectId } = currentEntryContext;
  const saveMsg = document.getElementById('saveMsg');

  if (!classId) {
    saveMsg.innerHTML = '<span style="opacity:.6">Load students first.</span>';
    return;
  }

  const rows = document.querySelectorAll('#entryBody tr[data-student-id]');
  if (rows.length === 0) return;

  saveMsg.innerHTML = '<span style="opacity:.6">Saving scores...</span>';

  let saved = 0, errors = 0;
  const { classWeight } = getScoreWeights();
  const promises = Array.from(rows).map(async row => {
    const studentId  = parseInt(row.dataset.studentId);
    const scoreId    = row.dataset.scoreId;

    let payload = {
      student_id:  studentId,
      subject_id:  parseInt(subjectId),
      semester_id: parseInt(semesterId),
    };

    if (isBreakdownMode) {
      const ex1 = parseFloat(row.querySelector('.ex1-input').value) || 0;
      const ex2 = parseFloat(row.querySelector('.ex2-input').value) || 0;
      const ass1 = parseFloat(row.querySelector('.ass1-input').value) || 0;
      const ass2 = parseFloat(row.querySelector('.ass2-input').value) || 0;
      const ind_proj = parseFloat(row.querySelector('.ind-proj-input').value) || 0;
      const grp_work = parseFloat(row.querySelector('.grp-work-input').value) || 0;
      const pract_work = parseFloat(row.querySelector('.pract-work-input').value) || 0;
      const mid_sem = parseFloat(row.querySelector('.mid-sem-input').value) || 0;
      const rawSum = ex1 + ex2 + ass1 + ass2 + ind_proj + grp_work + pract_work + mid_sem;
      const classScore = parseFloat((rawSum * (classWeight / 100)).toFixed(1));
      const examScore = parseFloat(row.querySelector('.exam-score-input').value) || 0;

      payload = {
        ...payload,
        ex1, ex2, ass1, ass2, ind_proj, grp_work, pract_work, mid_sem,
        class_score: classScore,
        exam_score: examScore
      };
    } else {
      const classScore = parseFloat(row.querySelector('.class-score-input').value) || 0;
      const examScore  = parseFloat(row.querySelector('.exam-score-input').value) || 0;
      payload = {
        ...payload,
        class_score: classScore,
        exam_score: examScore
      };
    }

    try {
      let res;
      if (scoreId) {
        res = await fetch(`${API_BASE}/results/${scoreId}`, {
          method: 'PUT',
          headers: getHeaders({ 'Content-Type': 'application/json' }),
          body: JSON.stringify(payload),
        });
      } else {
        res = await fetch(`${API_BASE}/results/`, {
          method: 'POST',
          headers: getHeaders({ 'Content-Type': 'application/json' }),
          body: JSON.stringify(payload),
        });
      }
      if (res.ok) {
        const data = await res.json();
        row.dataset.scoreId = data.id;
        saved++;
      } else {
        errors++;
      }
    } catch (_) {
      errors++;
    }
  });

  await Promise.all(promises);

  if (errors === 0) {
    saveMsg.innerHTML = `<span style="color:var(--success-color)">✔ All ${saved} scores saved successfully.</span>`;
  } else {
    saveMsg.innerHTML = `<span style="color:var(--error-color)">⚠ Saved ${saved}, failed ${errors}. Check console.</span>`;
  }
}

// ── PANEL 2: Results Browser ──────────────────────────────────────────────────
async function loadResultsBrowser() {
  const classId    = document.getElementById('br_class_id').value;
  const semesterId = document.getElementById('br_semester_id').value;
  const subjectId  = document.getElementById('br_subject_id').value;
  const tbody      = document.getElementById('browserBody');

  if (!classId || !semesterId) {
    tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;padding:20px;opacity:.6">Select class and semester.</td></tr>';
    return;
  }

  tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;padding:20px;opacity:.6">Loading...</td></tr>';

  try {
    let url = `${API_BASE}/results/class/${classId}?semester_id=${semesterId}`;
    if (subjectId) url += `&subject_id=${subjectId}`;

    const res = await fetch(url, { headers: getHeaders() });
    if (!res.ok) throw new Error('Failed to load results');
    const results = await res.json();

    if (results.length === 0) {
      tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;padding:20px;opacity:.6">No results found for the selected filters.</td></tr>';
      renderBrowserStats([]);
      return;
    }

    tbody.innerHTML = results.map(r => `
      <tr id="br-row-${r.id}">
        <td>${r.student_name}<br><small style="opacity:.6">${r.student_code}</small></td>
        <td>${r.subject_name}</td>
        <td class="br-class-score" contenteditable="false">${r.class_score}</td>
        <td class="br-exam-score" contenteditable="false">${r.exam_score}</td>
        <td class="total-cell">${r.total_score.toFixed(1)}</td>
        <td>${gradeChipHTML(r.grade)}</td>
        <td style="opacity:.7;">${r.remark}</td>
        <td style="white-space:nowrap;">
          <button class="btn" style="padding:4px 8px; font-size:.8rem; margin-right:4px;" onclick="startInlineEdit(${r.id}, ${r.student_id}, ${r.subject_id}, ${r.semester_id})">✏ Edit</button>
          <a class="btn" style="padding:4px 8px; font-size:.8rem;"
            href="report-card.html?student_id=${r.student_id}&semester_id=${semesterId}" target="_blank">📄 Report</a>
        </td>
      </tr>
    `).join('');

    renderBrowserStats(results);
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;padding:20px;color:var(--error-color)">Error: ${e.message}</td></tr>`;
  }
}

function renderBrowserStats(results) {
  const el = document.getElementById('browserStats');
  if (results.length === 0) { el.style.display = 'none'; return; }
  const avg = (results.reduce((s, r) => s + r.total_score, 0) / results.length).toFixed(1);
  const passes = results.filter(r => r.total_score >= 40).length;
  const fails  = results.length - passes;
  el.style.display = 'flex';
  el.innerHTML = `
    <span>📊 <strong>${results.length}</strong> scores</span>
    <span>📈 Class Avg: <strong>${avg}%</strong></span>
    <span>✅ Pass: <strong>${passes}</strong></span>
    <span>❌ Fail: <strong>${fails}</strong></span>
  `;
}

function startInlineEdit(scoreId, studentId, subjectId, semesterId) {
  const row = document.getElementById(`br-row-${scoreId}`);
  if (!row) return;

  const classCell = row.querySelector('.br-class-score');
  const examCell  = row.querySelector('.br-exam-score');
  const btn       = row.querySelector('button');

  const origClass = parseFloat(classCell.textContent);
  const origExam  = parseFloat(examCell.textContent);

  classCell.innerHTML = `<input type="number" class="score-input" min="0" max="30" step="0.5" value="${origClass}" style="width:65px;" />`;
  examCell.innerHTML  = `<input type="number" class="score-input" min="0" max="70" step="0.5" value="${origExam}" style="width:65px;" />`;

  btn.textContent = '💾 Save';
  btn.onclick = () => saveInlineEdit(scoreId, studentId, subjectId, semesterId, row, btn);
}

async function saveInlineEdit(scoreId, studentId, subjectId, semesterId, row, btn) {
  const classScore = parseFloat(row.querySelector('.br-class-score input').value) || 0;
  const examScore  = parseFloat(row.querySelector('.br-exam-score input').value) || 0;

  btn.textContent = '...';
  btn.disabled = true;

  try {
    const res = await fetch(`${API_BASE}/results/${scoreId}`, {
      method: 'PUT',
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({
        student_id:  studentId,
        subject_id:  subjectId,
        semester_id: semesterId,
        class_score: classScore,
        exam_score:  examScore,
      }),
    });
    if (!res.ok) throw new Error('Save failed');
    const data = await res.json();

    row.querySelector('.br-class-score').textContent = data.class_score;
    row.querySelector('.br-exam-score').textContent  = data.exam_score;
    const totalCell  = row.querySelector('.total-cell');
    const gradeCell  = row.cells[5];
    const remarkCell = row.cells[6];
    totalCell.textContent  = data.total_score.toFixed(1);
    gradeCell.innerHTML    = gradeChipHTML(data.grade);
    remarkCell.textContent = data.remark;

    btn.disabled = false;
    btn.textContent = '✏ Edit';
    btn.onclick = () => startInlineEdit(scoreId, studentId, subjectId, semesterId);

    // Refresh stats
    loadResultsBrowser();
  } catch (e) {
    btn.disabled = false;
    btn.textContent = '✏ Edit';
    alert('Save failed: ' + e.message);
  }
}

// ── Init ───────────────────────────────────────────────────────────────────────
window.toggleBreakdownMode = toggleBreakdownMode;
window.updateBreakdownRowTotal = updateBreakdownRowTotal;
initPage();
