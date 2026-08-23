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

function getRoles() {
  if (!token) return [];
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(atob(base64).split('').map(c => 
      '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2)
    ).join(''));
    return JSON.parse(jsonPayload).roles || [];
  } catch (e) {
    return [];
  }
}

const roles = getRoles();
const isAdmin = roles.includes('admin');

// Switch tabs view
function switchTab(tabId) {
  document.querySelectorAll('.tab-panel').forEach(p => p.style.display = 'none');
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));

  if (tabId === 'terminal') {
    document.getElementById('panelTerminal').style.display = 'block';
    document.getElementById('tabTerminalBtn').classList.add('active');
  } else if (tabId === 'academic') {
    document.getElementById('panelAcademic').style.display = 'block';
    document.getElementById('tabAcademicBtn').classList.add('active');
  } else if (tabId === 'financial') {
    document.getElementById('panelFinancial').style.display = 'block';
    document.getElementById('tabFinancialBtn').classList.add('active');
  }
}

// Populate all selects
async function initPage() {
  const studentSelect = document.getElementById('student_id');
  const semesterSelect = document.getElementById('semester_id');
  const acadClassSelect = document.getElementById('acad_class_id');
  const acadSemesterSelect = document.getElementById('acad_semester_id');
  const finClassSelect = document.getElementById('fin_class_id');

  try {
    // 1. Fetch Students
    const resStudents = await fetch(`${API_BASE}/students/`, { headers: getHeaders() });
    const students = await resStudents.json();
    studentSelect.innerHTML = '<option value="">Select Student...</option>' + 
      students.map(s => `<option value="${s.id}">${s.full_name} (${s.student_code})</option>`).join('');

    // 2. Fetch Semesters
    const resSemesters = await fetch(`${API_BASE}/academic/semesters`, { headers: getHeaders() });
    const semesters = await resSemesters.json();
    const mode = localStorage.getItem('school_mode') || 'COMBINED';
    const isBasic = (mode === 'BASIC_ONLY');

    const semestersHtml = semesters.map(s => {
      const displayName = isBasic ? s.name.replace(/Semester/i, 'Term') : s.name;
      return `<option value="${s.id}">${displayName} (${s.academic_year?.label || ''})</option>`;
    }).join('');

    const periodLabel = isBasic ? 'Select Term...' : 'Select Semester...';
    semesterSelect.innerHTML = `<option value="">${periodLabel}</option>` + semestersHtml;
    acadSemesterSelect.innerHTML = `<option value="">${periodLabel}</option>` + semestersHtml;

    // 3. Fetch Classes
    const resClasses = await fetch(`${API_BASE}/classes/my-classes`, { headers: getHeaders() });
    const classes = await resClasses.json();
    const classesHtml = classes.map(c => `<option value="${c.id}">${c.name}</option>`).join('');
    acadClassSelect.innerHTML = '<option value="">Select Class...</option>' + classesHtml;
    finClassSelect.innerHTML = '<option value="">All Classes</option>' + classesHtml;

    // Show config card if Admin
    if (isAdmin) {
      document.getElementById('configCard').style.display = 'block';
      loadReportConfig();
    } else {
      document.getElementById('tabFinancialBtn').style.display = 'none';
    }

  } catch (error) {
    console.error('Error populating dropdowns:', error);
  }
}

// Load configurations
async function loadReportConfig() {
  try {
    const res = await fetch(`${API_BASE}/settings/`, { headers: getHeaders() });
    if (res.ok) {
      const config = await res.json();
      if (config.school_name) document.getElementById('cfg_school_name').value = config.school_name;
      if (config.report_motto) document.getElementById('cfg_report_motto').value = config.report_motto;
      if (config.report_title) document.getElementById('cfg_report_title').value = config.report_title;
      if (config.report_headmaster) document.getElementById('cfg_report_headmaster').value = config.report_headmaster;
    }
  } catch (e) {
    console.error('Failed to load settings:', e);
  }
}

// Save configurations
async function saveReportConfig() {
  const payload = {
    school_name: document.getElementById('cfg_school_name').value,
    report_motto: document.getElementById('cfg_report_motto').value,
    report_title: document.getElementById('cfg_report_title').value,
    report_headmaster: document.getElementById('cfg_report_headmaster').value
  };

  const configMsg = document.getElementById('configMsg');
  configMsg.innerHTML = '<span style="color:var(--text-secondary);">Saving settings...</span>';

  try {
    const res = await fetch(`${API_BASE}/settings/`, {
      method: 'PUT',
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      configMsg.innerHTML = '<span style="color:var(--success-color);">✔ Settings saved successfully!</span>';
    } else {
      const err = await res.json();
      configMsg.innerHTML = `<span style="color:var(--error-color);">❌ Save failed: ${err.detail || 'Unknown error'}</span>`;
    }
  } catch (e) {
    configMsg.innerHTML = `<span style="color:var(--error-color);">❌ Connection error: ${e.message}</span>`;
  }
}

// Single student report handler
const reportForm = document.getElementById('reportForm');
if (reportForm) {
  reportForm.addEventListener('submit', (event) => {
    event.preventDefault();
    const studentId  = document.getElementById('student_id').value;
    const semesterId = document.getElementById('semester_id').value;
    const msgEl      = document.getElementById('reportMsg');

    if (!studentId || !semesterId) {
      msgEl.innerHTML = '<span style="color:var(--error-color)">Select a student and semester.</span>';
      return;
    }
    msgEl.innerHTML = `
      <div style="display:flex; gap:10px; margin-top:8px; flex-wrap:wrap;">
        <a class="btn primary" href="report-card.html?student_id=${studentId}&semester_id=${semesterId}" target="_blank">👁 View Report Card</a>
        <button class="btn" onclick="window.open('${API_BASE}/reports/terminal-report/${studentId}?semester_id=${semesterId}&token=${token}', '_blank')">
          📥 Download PDF
        </button>
      </div>
    `;
  });
}

// Load Academic Performance summary
async function loadAcademicSummary() {
  const classId = document.getElementById('acad_class_id').value;
  const semesterId = document.getElementById('acad_semester_id').value;
  const gradeTier = document.getElementById('acad_grade_tier').value;
  const attendanceRate = document.getElementById('acad_attendance_rate').value;

  if (!classId || !semesterId) {
    return alert('Please select Class and Semester.');
  }

  const tbody = document.getElementById('academicSummaryBody');
  tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding:20px; color:var(--text-secondary);">Loading summary data...</td></tr>';

  try {
    let url = `${API_BASE}/reports/class-summary/${classId}?semester_id=${semesterId}`;
    if (gradeTier) url += `&grade_tier=${gradeTier}`;
    if (attendanceRate) url += `&attendance_rate=${attendanceRate}`;

    const res = await fetch(url, { headers: getHeaders() });
    if (!res.ok) throw new Error(await res.text());

    const data = await res.json();
    if (data.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding:20px; color:var(--text-secondary);">No matching records found.</td></tr>';
      return;
    }

    tbody.innerHTML = data.map(row => `
      <tr>
        <td><strong>${row.student_code}</strong></td>
        <td>${row.full_name}</td>
        <td>${row.average_score}%</td>
        <td><span class="chip ${row.fails_count > 0 ? 'danger' : 'success'}">${row.fails_count} fails</span></td>
        <td>${row.attendance_rate}%</td>
        <td><span class="chip ${row.grade_tier === 'Fail' ? 'danger' : row.grade_tier === 'Pass' ? 'warning' : 'success'}">Tier ${row.grade_tier}</span></td>
        <td style="white-space:nowrap;">
          <a class="btn" style="padding:4px 8px; font-size:0.8rem; margin-right:4px;"
            href="report-card.html?student_id=${row.student_id}&semester_id=${semesterId}" target="_blank">👁 View</a>
          <button class="btn" style="padding:4px 8px; font-size:0.8rem;"
            onclick="window.open('${API_BASE}/reports/terminal-report/${row.student_id}?semester_id=${semesterId}&token=${token}', '_blank')">📥 PDF</button>
        </td>
      </tr>
    `).join('');

  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:20px; color:var(--error-color);">Error loading data: ${e.message}</td></tr>`;
  }
}

// Export Academic Summary CSV
function exportAcademicCSV() {
  const classId = document.getElementById('acad_class_id').value;
  const semesterId = document.getElementById('acad_semester_id').value;
  const gradeTier = document.getElementById('acad_grade_tier').value;
  const attendanceRate = document.getElementById('acad_attendance_rate').value;

  if (!classId || !semesterId) {
    return alert('Please select Class and Semester first.');
  }

  let url = `${API_BASE}/reports/class-summary/${classId}/export?semester_id=${semesterId}`;
  if (gradeTier) url += `&grade_tier=${gradeTier}`;
  if (attendanceRate) url += `&attendance_rate=${attendanceRate}`;

  window.open(url, '_blank');
}

// Load Financial Summary
async function loadFinancialSummary() {
  const classId = document.getElementById('fin_class_id').value;
  const minBalance = document.getElementById('fin_min_balance').value;
  const overdueOnly = document.getElementById('fin_overdue_only').checked;

  const tbody = document.getElementById('financialSummaryBody');
  tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding:20px; color:var(--text-secondary);">Loading financial data...</td></tr>';

  try {
    let url = `${API_BASE}/reports/financial-summary?overdue_only=${overdueOnly}`;
    if (classId) url += `&class_id=${classId}`;
    if (minBalance) url += `&min_balance=${minBalance}`;

    const res = await fetch(url, { headers: getHeaders() });
    if (!res.ok) throw new Error(await res.text());

    const data = await res.json();
    if (data.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding:20px; color:var(--text-secondary);">No matching fee balances found.</td></tr>';
      return;
    }

    tbody.innerHTML = data.map(row => `
      <tr>
        <td><strong>${row.student_code}</strong></td>
        <td>${row.full_name}</td>
        <td>${row.class_name}</td>
        <td>GHS ${row.total_billed.toFixed(2)}</td>
        <td>GHS ${row.total_paid.toFixed(2)}</td>
        <td><strong style="color: ${row.outstanding_balance > 0 ? 'var(--error-color)' : 'var(--success-color)'}">GHS ${row.outstanding_balance.toFixed(2)}</strong></td>
        <td><span class="chip ${row.overdue_count > 0 ? 'danger' : 'success'}">${row.overdue_count} overdue</span></td>
      </tr>
    `).join('');

  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:20px; color:var(--error-color);">Error loading data: ${e.message}</td></tr>`;
  }
}

// Export Financial Summary CSV
function exportFinancialCSV() {
  const classId = document.getElementById('fin_class_id').value;
  const minBalance = document.getElementById('fin_min_balance').value;
  const overdueOnly = document.getElementById('fin_overdue_only').checked;

  let url = `${API_BASE}/reports/financial-summary/export?overdue_only=${overdueOnly}`;
  if (classId) url += `&class_id=${classId}`;
  if (minBalance) url += `&min_balance=${minBalance}`;

  window.open(url, '_blank');
}

// Initialize on page load
initPage();
