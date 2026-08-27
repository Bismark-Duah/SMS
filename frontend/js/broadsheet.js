// Class Broadsheet & Remarks Controller

let currentBroadsheetData = null;

document.addEventListener("DOMContentLoaded", () => {
  initBroadsheetPage();
});

async function getAuthHeader() {
  const token = localStorage.getItem("accessToken") || sessionStorage.getItem("accessToken");
  return {
    "Content-Type": "application/json",
    "Authorization": token ? `Bearer ${token}` : ""
  };
}

async function initBroadsheetPage() {
  const headers = await getAuthHeader();
  try {
    const [classesRes, semRes] = await Promise.all([
      fetch("/api/classes/my-classes", { headers }),
      fetch("/api/academic/semesters", { headers })
    ]);

    if (classesRes.ok) {
      const classes = await classesRes.json();
      const classSelect = document.getElementById("selectClassSection");
      classSelect.innerHTML = '<option value="">Select class section...</option>';
      classes.forEach(c => {
        classSelect.innerHTML += `<option value="${c.id}">${c.name}</option>`;
      });
    }

    if (semRes.ok) {
      const sems = await semRes.json();
      const semSelect = document.getElementById("selectSemester");
      semSelect.innerHTML = '<option value="">Current Term</option>';
      sems.forEach(s => {
        const curr = s.is_current ? " (Current)" : "";
        semSelect.innerHTML += `<option value="${s.id}">${s.name}${curr}</option>`;
      });
    }
  } catch (err) {
    console.error("Initialization error:", err);
  }
}

async function loadBroadsheetData() {
  const classId = document.getElementById("selectClassSection").value;
  const semId = document.getElementById("selectSemester").value;

  if (!classId) {
    document.getElementById("broadsheetBody").innerHTML = '<tr><td colspan="8" style="text-align:center; padding:40px; opacity:0.6;">Please select a class section above to view the broadsheet.</td></tr>';
    return;
  }

  const headers = await getAuthHeader();
  let url = `/api/academic-hierarchy/broadsheet/${classId}`;
  if (semId) url += `?semester_id=${semId}`;

  try {
    const res = await fetch(url, { headers });
    if (!res.ok) {
      document.getElementById("broadsheetBody").innerHTML = `<tr><td colspan="8" style="text-align:center; padding:40px; color:#ef4444;">Failed to load broadsheet (${res.status})</td></tr>`;
      return;
    }

    currentBroadsheetData = await res.json();
    renderBroadsheet(currentBroadsheetData);
  } catch (err) {
    console.error("Failed to load broadsheet:", err);
    document.getElementById("broadsheetBody").innerHTML = '<tr><td colspan="8" style="text-align:center; padding:40px; color:#ef4444;">Network error while loading broadsheet.</td></tr>';
  }
}

function renderBroadsheet(data) {
  document.getElementById("broadsheetTitle").innerText = `${data.class_name} Broadsheet (${data.semester_name})`;

  // Render Banner Policy Info
  const mode = data.publishing_mode;
  let modeTitle = "⚙️ Report Publishing Policy Mode: ";
  let modeDesc = "";

  if (mode === "FORM_MASTER_DIRECT") {
    modeTitle += "Direct Form Master Publishing (Option 1)";
    modeDesc = "Form Masters can publish report cards directly to guardians for this class once broadsheet is complete.";
  } else if (mode === "ACADEMIC_HEAD_ONLY") {
    modeTitle += "Centralized Executive Approval (Option 2)";
    modeDesc = "Form Masters submit broadsheet. Terminal report cards must be published by the Assistant Head Academic / Headmaster.";
  } else {
    modeTitle += "Hybrid Dual Mode (Option 3)";
    modeDesc = "Both Form Masters and the Assistant Head Academic have full authority to publish report cards.";
  }

  document.getElementById("bannerTitle").innerText = modeTitle;
  document.getElementById("bannerDesc").innerText = modeDesc;

  const actionContainer = document.getElementById("bannerActionContainer");
  const isPub = data.is_published;

  let pubStatusBadge = isPub ? 
    '<span style="background:rgba(34, 197, 94, 0.2); color:#22c55e; border:1px solid #22c55e; padding:6px 14px; border-radius:20px; font-weight:700; font-size:0.85rem;">🟢 Published to Parents</span>' :
    '<span style="background:rgba(245, 158, 11, 0.2); color:#f59e0b; border:1px solid #f59e0b; padding:6px 14px; border-radius:20px; font-weight:700; font-size:0.85rem;">⏳ Not Published Yet</span>';

  actionContainer.innerHTML = `
    <div style="display:flex; align-items:center; gap:12px;">
      ${pubStatusBadge}
      <button class="btn btn-primary" style="font-weight:700;" onclick="publishClassReports()">📲 Publish & Send Reports</button>
    </div>
  `;

  // Render Table Header (Dynamic Subjects)
  const headerRow = document.getElementById("broadsheetHeaderRow");
  let headerHTML = `
    <th style="text-align:left; min-width:180px;">Student Code & Name</th>
  `;

  data.subjects.forEach(s => {
    headerHTML += `<th title="${s.name} (${s.is_core ? 'Core' : 'Elective'})">${s.code || s.name}</th>`;
  });

  headerHTML += `
    <th>Total</th>
    <th>Avg</th>
    <th>Rank</th>
    <th>WASSCE Agg</th>
    <th style="width:120px;">Attitude</th>
    <th style="width:120px;">Conduct</th>
    <th style="width:120px;">Interest</th>
    <th style="min-width:200px;">Form Teacher Remarks</th>
  `;
  headerRow.innerHTML = headerHTML;

  // Render Student Rows
  const tbody = document.getElementById("broadsheetBody");
  if (data.students.length === 0) {
    tbody.innerHTML = `<tr><td colspan="${data.subjects.length + 9}" style="text-align:center; padding:30px; opacity:0.6;">No active students found in this class section.</td></tr>`;
    return;
  }

  tbody.innerHTML = data.students.map(st => {
    let subjCells = data.subjects.map(s => {
      const scoreVal = st.subject_scores[s.name] !== undefined ? st.subject_scores[s.name] : '-';
      return `<td><b>${scoreVal}</b></td>`;
    }).join('');

    const rankClass = st.class_rank <= 3 ? "rank-top" : "rank-normal";
    const aggDisplay = st.aggregate !== undefined && st.aggregate !== null ? st.aggregate : '-';

    return `
      <tr data-student-id="${st.student_id}">
        <td style="text-align:left;">
          <div style="font-weight:700;">${st.student_name}</div>
          <div style="font-size:0.75rem; opacity:0.7;">Code: ${st.student_code}</div>
        </td>
        ${subjCells}
        <td style="color:#818cf8; font-weight:800;">${st.total_marks}</td>
        <td><b>${st.average_mark}%</b></td>
        <td><span class="rank-badge ${rankClass}">#${st.class_rank}</span></td>
        <td><span class="rank-badge" style="background:rgba(168, 85, 247, 0.15); color:#c084fc; border:1px solid rgba(168, 85, 247, 0.4);">${aggDisplay}</span></td>
        <td><input type="text" class="remark-input input-attitude" value="${st.attitude || ''}" placeholder="e.g. Good" /></td>
        <td><input type="text" class="remark-input input-conduct" value="${st.conduct || ''}" placeholder="e.g. Satisfactory" /></td>
        <td><input type="text" class="remark-input input-interest" value="${st.interest || ''}" placeholder="e.g. Reading" /></td>
        <td><input type="text" class="remark-input input-remarks" value="${st.remarks || ''}" placeholder="Enter form master remarks..." /></td>
      </tr>
    `;
  }).join('');

  renderSubjectMasteryAnalytics(data);
}

function renderSubjectMasteryAnalytics(data) {
  const section = document.getElementById("subjectMasterySection");
  const container = document.getElementById("subjectMasteryContent");
  if (!section || !container || !data || !data.students || data.students.length === 0 || !data.subjects || data.subjects.length === 0) {
    if (section) section.style.display = "none";
    return;
  }

  let html = "";
  data.subjects.forEach(s => {
    let totalScore = 0;
    let count = 0;
    let passCount = 0;

    data.students.forEach(st => {
      const val = st.subject_scores[s.name];
      if (typeof val === 'number') {
        totalScore += val;
        count++;
        if (val >= 50) passCount++;
      }
    });

    const avg = count > 0 ? (totalScore / count).toFixed(1) : 0.0;
    const passRate = count > 0 ? Math.round((passCount / count) * 100) : 0;
    const badgeColor = passRate >= 75 ? "#10b981" : (passRate >= 50 ? "#3b82f6" : "#ef4444");

    html += `
      <div style="background:rgba(255,255,255,0.03); border:1px solid var(--border-color); border-radius:8px; padding:12px; font-size:0.85rem;">
        <div style="font-weight:700; font-size:0.92rem; color:#f8fafc; margin-bottom:4px;">${s.name}</div>
        <div style="display:flex; justify-content:space-between; margin-bottom:6px; opacity:0.85;">
          <span>Class Average:</span> <strong style="color:#38bdf8;">${avg}%</strong>
        </div>
        <div style="display:flex; justify-content:space-between; opacity:0.85;">
          <span>Pass Rate (≥50%):</span> <strong style="color:${badgeColor}">${passRate}% (${passCount}/${count})</strong>
        </div>
      </div>
    `;
  });

  container.innerHTML = html;
  section.style.display = "block";
}

async function saveBroadsheetRemarks() {
  if (!currentBroadsheetData) {
    alert("Please select a class section first.");
    return;
  }

  const rows = document.querySelectorAll("#broadsheetBody tr[data-student-id]");
  const remarkItems = [];

  rows.forEach(r => {
    const studentId = parseInt(r.getAttribute("data-student-id"));
    const attitude = r.querySelector(".input-attitude").value;
    const conduct = r.querySelector(".input-conduct").value;
    const interest = r.querySelector(".input-interest").value;
    const form_teacher_remarks = r.querySelector(".input-remarks").value;

    remarkItems.push({
      student_id: studentId,
      attitude,
      conduct,
      interest,
      form_teacher_remarks
    });
  });

  const payload = {
    class_section_id: currentBroadsheetData.class_section_id,
    semester_id: currentBroadsheetData.semester_id,
    remarks: remarkItems
  };

  const headers = await getAuthHeader();
  try {
    const res = await fetch("/api/academic-hierarchy/broadsheet/remarks", {
      method: "POST",
      headers,
      body: JSON.stringify(payload)
    });

    if (res.ok) {
      alert("Form teacher remarks saved successfully!");
    } else {
      const err = await res.json();
      alert(`Error saving remarks: ${err.detail}`);
    }
  } catch (e) {
    alert("Network error while saving remarks.");
  }
}

async function publishClassReports() {
  if (!currentBroadsheetData) return;
  const ok = await (window.showConfirmDialog ? window.showConfirmDialog(
    '📢 Publish Terminal Reports',
    `Are you sure you want to publish final terminal report cards for ${currentBroadsheetData.class_name} to student and parent portals?`,
    'Publish Reports',
    'Cancel'
  ) : Promise.resolve(confirm(`Are you sure you want to publish terminal report cards for ${currentBroadsheetData.class_name} to guardians?`)));

  if (!ok) return;

  const headers = await getAuthHeader();
  try {
    const res = await fetch(`/api/academic-hierarchy/broadsheet/publish?class_section_id=${currentBroadsheetData.class_section_id}&semester_id=${currentBroadsheetData.semester_id}`, {
      method: "POST",
      headers
    });

    if (res.ok) {
      const data = await res.json();
      alert(data.message);
      await loadBroadsheetData();
    } else {
      const err = await res.json();
      alert(`Publishing Denied: ${err.detail}`);
    }
  } catch (e) {
    alert("Network error while publishing reports.");
  }
}

function exportBroadsheetCSV() {
  if (!currentBroadsheetData || !currentBroadsheetData.students || currentBroadsheetData.students.length === 0) {
    alert("Please select a class and load broadsheet data before exporting.");
    return;
  }

  const data = currentBroadsheetData;
  const subjects = data.subjects || [];
  const students = data.students || [];

  // 1. Build CSV Header
  const headers = [
    "Student ID",
    "Student Code",
    "Full Name",
    ...subjects.map(s => `"${s.name} (${s.is_core ? 'Core' : 'Elective'})"`),
    "Total Marks",
    "Average (%)",
    "Class Rank",
    "WASSCE Best 6 Aggregate",
    "Attitude",
    "Conduct",
    "Interest",
    "Form Teacher Remarks"
  ];

  const rows = [];
  rows.push(headers.join(","));

  // 2. Build Student Data Rows
  students.forEach(st => {
    const subjValues = subjects.map(s => {
      const v = st.subject_scores[s.name];
      return v !== undefined && v !== null ? v : "";
    });

    const escapeCSV = (val) => {
      if (val === null || val === undefined) return '""';
      return `"${String(val).replace(/"/g, '""')}"`;
    };

    const row = [
      st.student_id,
      escapeCSV(st.student_code),
      escapeCSV(st.student_name),
      ...subjValues,
      st.total_marks,
      st.average_mark,
      st.class_rank,
      st.aggregate !== undefined && st.aggregate !== null ? st.aggregate : "",
      escapeCSV(st.attitude || ""),
      escapeCSV(st.conduct || ""),
      escapeCSV(st.interest || ""),
      escapeCSV(st.remarks || st.form_teacher_remarks || "")
    ];

    rows.push(row.join(","));
  });

  // 3. Trigger Download
  const csvContent = "\uFEFF" + rows.join("\r\n"); // UTF-8 BOM for Excel compatibility
  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  
  const classNameClean = (data.class_name || "Class").replace(/[^a-zA-Z0-9_-]/g, "_");
  const semNameClean = (data.semester_name || "Term").replace(/[^a-zA-Z0-9_-]/g, "_");
  link.setAttribute("href", url);
    document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

// ═══════════════════════════════════════════════════════════════════════════════
// COMPARATIVE INTELLIGENCE & LEAGUE TABLES CONTROLLER
// ═══════════════════════════════════════════════════════════════════════════════

let currentViewMode = 'matrix';
let currentComparativeData = null;
let currentCompSubTab = 'class_league';

function switchBroadsheetView(mode) {
  currentViewMode = mode;
  const singleView = document.getElementById("singleBroadsheetView");
  const compView = document.getElementById("comparativeHubView");
  const tabMatrix = document.getElementById("viewTabBroadsheet");
  const tabComp = document.getElementById("viewTabComparative");
  const btnExport = document.getElementById("btnExportCSV");

  if (mode === 'comparative') {
    if (singleView) singleView.style.display = "none";
    if (compView) compView.style.display = "block";
    if (tabMatrix) tabMatrix.classList.remove("active");
    if (tabComp) tabComp.classList.add("active");
    if (btnExport) btnExport.style.display = "none";
    loadComparativeData();
  } else {
    if (singleView) singleView.style.display = "block";
    if (compView) compView.style.display = "none";
    if (tabMatrix) tabMatrix.classList.add("active");
    if (tabComp) tabComp.classList.remove("active");
    if (btnExport) btnExport.style.display = "inline-flex";
  }
}

function switchCompSubTab(tabName) {
  currentCompSubTab = tabName;
  const tabs = ['class_league', 'dept_benchmarks', 'subject_mastery', 'scholars_podium'];
  const viewMap = {
    class_league: 'compSubViewClassLeague',
    dept_benchmarks: 'compSubViewDeptBenchmark',
    subject_mastery: 'compSubViewSubjectMastery',
    scholars_podium: 'compSubViewScholars'
  };
  const btnMap = {
    class_league: 'tabBtnClassLeague',
    dept_benchmarks: 'tabBtnDeptBenchmark',
    subject_mastery: 'tabBtnSubjectMastery',
    scholars_podium: 'tabBtnScholars'
  };

  tabs.forEach(t => {
    const v = document.getElementById(viewMap[t]);
    const b = document.getElementById(btnMap[t]);
    if (v) v.style.display = (t === tabName) ? "block" : "none";
    if (b) b.classList.toggle("active", t === tabName);
  });
}

async function loadComparativeData() {
  const headers = await getAuthHeader();
  const semId = document.getElementById("selectSemester") ? document.getElementById("selectSemester").value : "";
  let url = "/api/results/comparative-rankings";
  if (semId) url += `?semester_id=${semId}`;

  try {
    const res = await fetch(url, { headers });
    if (res.ok) {
      currentComparativeData = await res.json();
      renderComparativeKpis();
      renderClassLeagueTable();
      renderDeptBenchmarks();
      renderSubjectMasteryOptions();
      renderSubjectMasteryBreakdown();
      renderSvgTrajectoryCurves();
      renderTopScholarsPodium();
    }
  } catch (err) {
    console.error("Error loading comparative rankings:", err);
  }
}

function renderComparativeKpis() {
  const ribbon = document.getElementById("compKpiRibbon");
  if (!ribbon || !currentComparativeData) return;

  const data = currentComparativeData;
  const topClass = data.class_league && data.class_league[0];
  const topDept = data.department_benchmarks && data.department_benchmarks[0];
  const topScholar = data.top_scholars && data.top_scholars[0];
  
  // Calculate average quality pass rate
  let totalPass = 0, count = 0;
  (data.class_league || []).forEach(c => {
    if (c.scores_recorded > 0) {
      totalPass += c.pass_rate_pct;
      count++;
    }
  });
  const avgPass = count > 0 ? (totalPass / count).toFixed(1) : "0.0";

  ribbon.innerHTML = `
    <div class="comparative-kpi-card">
      <div style="font-size:2rem;">🥇</div>
      <div>
        <div style="font-size:0.72rem; font-weight:700; text-transform:uppercase; color:#f59e0b;">Leading Stream</div>
        <div style="font-size:1.05rem; font-weight:800;">${topClass ? topClass.class_name : 'N/A'}</div>
        <div style="font-size:0.78rem; opacity:0.8;">Class Mean: <b>${topClass ? topClass.average_score : '0'}%</b></div>
      </div>
    </div>

    <div class="comparative-kpi-card">
      <div style="font-size:2rem;">🏛️</div>
      <div>
        <div style="font-size:0.72rem; font-weight:700; text-transform:uppercase; color:#6366f1;">Top Department</div>
        <div style="font-size:1.05rem; font-weight:800;">${topDept ? topDept.department_name : 'N/A'}</div>
        <div style="font-size:0.78rem; opacity:0.8;">Quality Pass: <b>${topDept ? topDept.quality_pass_rate_pct : '0'}%</b></div>
      </div>
    </div>

    <div class="comparative-kpi-card">
      <div style="font-size:2rem;">🌟</div>
      <div>
        <div style="font-size:0.72rem; font-weight:700; text-transform:uppercase; color:#10b981;">Top Scholar</div>
        <div style="font-size:1.05rem; font-weight:800;">${topScholar ? topScholar.student_name : 'N/A'}</div>
        <div style="font-size:0.78rem; opacity:0.8;">Average Score: <b>${topScholar ? topScholar.average_score : '0'}%</b></div>
      </div>
    </div>

    <div class="comparative-kpi-card">
      <div style="font-size:2rem;">📊</div>
      <div>
        <div style="font-size:0.72rem; font-weight:700; text-transform:uppercase; color:#0284c7;">School Quality Pass</div>
        <div style="font-size:1.05rem; font-weight:800;">${avgPass}%</div>
        <div style="font-size:0.78rem; opacity:0.8;">${data.class_league ? data.class_league.length : 0} Class Sections</div>
      </div>
    </div>
  `;
}

function renderClassLeagueTable() {
  const tbody = document.getElementById("leagueTableBody");
  if (!tbody || !currentComparativeData) return;

  const stageFilter = (document.getElementById("leagueStageFilter") ? document.getElementById("leagueStageFilter").value : "ALL");
  let classes = currentComparativeData.class_league || [];

  if (stageFilter !== "ALL") {
    classes = classes.filter(c => c.stage_name && c.stage_name.toLowerCase().includes(stageFilter.toLowerCase()));
  }

  if (classes.length === 0) {
    tbody.innerHTML = '<tr><td colspan="10" style="text-align:center; padding:30px; opacity:0.6;">No class rankings available for this filter.</td></tr>';
    return;
  }

  tbody.innerHTML = classes.map((c, idx) => {
    let rankBadgeClass = 'normal';
    let rankIcon = c.rank;
    if (c.rank === 1) { rankBadgeClass = 'gold'; rankIcon = '🥇 1'; }
    else if (c.rank === 2) { rankBadgeClass = 'silver'; rankIcon = '🥈 2'; }
    else if (c.rank === 3) { rankBadgeClass = 'bronze'; rankIcon = '🥉 3'; }

    let deltaBadge = '<span class="rank-delta-badge neutral">● 0</span>';
    if (c.rank_delta > 0) {
      deltaBadge = `<span class="rank-delta-badge up">▲ +${c.rank_delta}</span>`;
    } else if (c.rank_delta < 0) {
      deltaBadge = `<span class="rank-delta-badge down">▼ ${c.rank_delta}</span>`;
    }

    const myClassHighlight = c.is_my_class ? 'style="background: rgba(99, 102, 241, 0.08); font-weight: 700;"' : '';
    const topStu = c.top_student ? `<b>${c.top_student.name}</b> (${c.top_student.average}%)` : '<span style="opacity:0.5;">None</span>';

    return `
      <tr ${myClassHighlight}>
        <td><span class="league-rank-badge ${rankBadgeClass}">${rankIcon}</span></td>
        <td style="text-align:left;">
          <div style="font-weight:700;">${c.class_name}</div>
          <div style="font-size:0.75rem; opacity:0.75;">${c.stage_name} ${c.is_my_class ? '• <span style="color:#818cf8;">My Class</span>' : ''}</div>
        </td>
        <td>${c.form_master_name}</td>
        <td><b>${c.student_count}</b></td>
        <td>${c.scores_recorded}</td>
        <td>
          <div style="font-weight:800; color:#0284c7;">${c.average_score}%</div>
          <div style="width:100%; height:4px; background:rgba(255,255,255,0.1); border-radius:2px; margin-top:4px;">
            <div style="width:${Math.min(100, c.average_score)}%; height:100%; background:#0284c7; border-radius:2px;"></div>
          </div>
        </td>
        <td>
          <span style="display:inline-block; padding:3px 8px; border-radius:6px; font-weight:700; font-size:0.78rem; background:${c.pass_rate_pct >= 75 ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.15)'}; color:${c.pass_rate_pct >= 75 ? '#10b981' : '#ef4444'};">
            ${c.pass_rate_pct}%
          </span>
        </td>
        <td><b style="color:#f59e0b;">${c.distinctions_count}</b></td>
        <td>${deltaBadge}</td>
        <td style="text-align:left; font-size:0.82rem;">${topStu}</td>
      </tr>
    `;
  }).join("");
}

function renderDeptBenchmarks() {
  const tbody = document.getElementById("deptBenchmarkBody");
  if (!tbody || !currentComparativeData) return;

  const depts = currentComparativeData.department_benchmarks || [];
  if (depts.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; padding:30px; opacity:0.6;">No departmental benchmarks available.</td></tr>';
    return;
  }

  tbody.innerHTML = depts.map(d => {
    let rankBadgeClass = 'normal';
    if (d.rank === 1) rankBadgeClass = 'gold';
    else if (d.rank === 2) rankBadgeClass = 'silver';
    else if (d.rank === 3) rankBadgeClass = 'bronze';

    const myDeptHighlight = d.is_my_department ? 'style="background: rgba(16, 185, 129, 0.08); font-weight: 700;"' : '';

    return `
      <tr ${myDeptHighlight}>
        <td><span class="league-rank-badge ${rankBadgeClass}">${d.rank}</span></td>
        <td style="text-align:left;">
          <div style="font-weight:700;">${d.department_name}</div>
          <div style="font-size:0.75rem; opacity:0.75;">Code: ${d.department_code} ${d.is_my_department ? '• <span style="color:#10b981;">My Dept</span>' : ''}</div>
        </td>
        <td><b>${d.hod_name}</b></td>
        <td>${d.subjects_count}</td>
        <td>${d.faculty_count}</td>
        <td><b style="color:#0284c7;">${d.average_score}%</b></td>
        <td>
          <span style="display:inline-block; padding:3px 8px; border-radius:6px; font-weight:700; font-size:0.78rem; background:rgba(16,185,129,0.15); color:#10b981;">
            ${d.quality_pass_rate_pct}%
          </span>
        </td>
        <td><b style="color:#f59e0b;">${d.distinction_rate_pct}%</b></td>
      </tr>
    `;
  }).join("");
}

function renderSubjectMasteryOptions() {
  const select = document.getElementById("compSubjectSelect");
  if (!select || !currentComparativeData) return;

  const subjects = currentComparativeData.subject_mastery || [];
  select.innerHTML = '';

  if (subjects.length === 0) {
    select.innerHTML = '<option value="">No subjects tested</option>';
    return;
  }

  subjects.forEach((sub, idx) => {
    const opt = document.createElement("option");
    opt.value = sub.subject_id;
    opt.textContent = `${sub.subject_name} (School Avg: ${sub.overall_average}%)`;
    if (idx === 0) opt.selected = true;
    select.appendChild(opt);
  });
}

function renderSubjectMasteryBreakdown() {
  const container = document.getElementById("subjectMasteryRankedBars");
  const select = document.getElementById("compSubjectSelect");
  if (!container || !select || !currentComparativeData) return;

  const selectedSubId = parseInt(select.value, 10);
  const subjectObj = (currentComparativeData.subject_mastery || []).find(s => s.subject_id === selectedSubId);

  if (!subjectObj || !subjectObj.class_rankings || subjectObj.class_rankings.length === 0) {
    container.innerHTML = '<div style="text-align:center; padding:30px; opacity:0.6;">No class rankings available for this subject.</div>';
    return;
  }

  container.innerHTML = `
    <div style="display:flex; justify-content:space-between; align-items:center; background:rgba(99,102,241,0.06); padding:12px 16px; border-radius:10px; border:1px dashed rgba(99,102,241,0.2);">
      <div>
        <h4 style="margin:0; font-size:0.95rem; color:#818cf8;">📌 Subject Performance Benchmark: ${subjectObj.subject_name}</h4>
        <span style="font-size:0.78rem; opacity:0.8;">Total Students Tested: <b>${subjectObj.total_students_tested}</b></span>
      </div>
      <div style="text-align:right;">
        <span style="font-size:0.75rem; text-transform:uppercase; font-weight:700; opacity:0.75;">School-Wide Average</span>
        <div style="font-size:1.25rem; font-weight:900; color:#0284c7;">${subjectObj.overall_average}%</div>
      </div>
    </div>

    <div style="display:flex; flex-direction:column; gap:10px; margin-top:8px;">
      ${subjectObj.class_rankings.map((c, idx) => `
        <div style="background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.08); border-radius:10px; padding:12px 16px;">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
            <div style="display:flex; align-items:center; gap:8px;">
              <span style="width:24px; height:24px; border-radius:50%; background:${idx === 0 ? '#f59e0b' : 'rgba(255,255,255,0.1)'}; color:${idx === 0 ? '#fff' : 'inherit'}; display:inline-flex; align-items:center; justify-content:center; font-size:0.75rem; font-weight:800;">${idx + 1}</span>
              <span style="font-weight:700; font-size:0.9rem;">${c.class_name}</span>
              <span style="font-size:0.75rem; opacity:0.65;">(${c.students_tested} students)</span>
            </div>
            <div style="font-weight:900; font-size:1rem; color:${c.average_score >= 70 ? '#10b981' : (c.average_score >= 50 ? '#0284c7' : '#ef4444')};">
              ${c.average_score}%
            </div>
          </div>
          <div style="width:100%; height:6px; background:rgba(255,255,255,0.08); border-radius:3px; overflow:hidden;">
            <div style="width:${Math.min(100, c.average_score)}%; height:100%; background:${c.average_score >= 70 ? '#10b981' : (c.average_score >= 50 ? '#0284c7' : '#ef4444')}; border-radius:3px;"></div>
          </div>
        </div>
      `).join("")}
    </div>
  `;
}

function renderSvgTrajectoryCurves() {
  const container = document.getElementById("svgTrajectoryChart");
  if (!container || !currentComparativeData) return;

  const classes = (currentComparativeData.class_league || []).slice(0, 5); // Top 5 classes
  if (classes.length === 0) {
    container.innerHTML = '<div style="text-align:center; padding:30px; opacity:0.6;">No trajectory data available.</div>';
    return;
  }

  const semName = currentComparativeData.semester.name;
  const prevSemName = currentComparativeData.semester.previous_semester_name || "Prior Term";

  const colors = ['#6366f1', '#10b981', '#f59e0b', '#0284c7', '#ec4899'];
  let paths = '';
  let dots = '';
  let legend = '';

  classes.forEach((c, idx) => {
    const color = colors[idx % colors.length];
    const prevScore = c.previous_average !== null ? c.previous_average : (c.average_score * 0.95);
    const currScore = c.average_score;

    // SVG coordinate mapping: Width 600, Height 200, Y: 100% -> 30px, 0% -> 170px
    const y1 = 170 - (prevScore / 100 * 140);
    const y2 = 170 - (currScore / 100 * 140);

    paths += `<path d="M 120 ${y1} C 250 ${y1}, 350 ${y2}, 480 ${y2}" fill="none" stroke="${color}" stroke-width="3" />`;
    dots += `<circle cx="120" cy="${y1}" r="5" fill="${color}" /><circle cx="480" cy="${y2}" r="5" fill="${color}" />`;
    
    legend += `
      <div style="display:flex; align-items:center; gap:6px; font-size:0.78rem; font-weight:700;">
        <span style="width:10px; height:10px; border-radius:50%; background:${color};"></span>
        <span>${c.class_name} (${currScore}%)</span>
      </div>
    `;
  });

  container.innerHTML = `
    <svg width="100%" height="220" viewBox="0 0 600 220" xmlns="http://www.w3.org/2000/svg" style="background:rgba(255,255,255,0.02); border-radius:12px; border:1px solid rgba(255,255,255,0.08);">
      <!-- Grid Lines -->
      <line x1="80" y1="30" x2="520" y2="30" stroke="rgba(255,255,255,0.08)" stroke-dasharray="4" />
      <text x="40" y="34" fill="#94a3b8" font-size="11" font-weight="600">100%</text>

      <line x1="80" y1="100" x2="520" y2="100" stroke="rgba(255,255,255,0.08)" stroke-dasharray="4" />
      <text x="45" y="104" fill="#94a3b8" font-size="11" font-weight="600">50%</text>

      <line x1="80" y1="170" x2="520" y2="170" stroke="rgba(255,255,255,0.08)" />
      <text x="50" y="174" fill="#94a3b8" font-size="11" font-weight="600">0%</text>

      <!-- Trajectory Paths & Dots -->
      ${paths}
      ${dots}

      <!-- Term Labels -->
      <text x="120" y="198" fill="#94a3b8" font-size="12" font-weight="700" text-anchor="middle">📅 ${prevSemName}</text>
      <text x="480" y="198" fill="#818cf8" font-size="12" font-weight="700" text-anchor="middle">📅 ${semName} (Current)</text>
    </svg>
    <div style="display:flex; gap:16px; flex-wrap:wrap; margin-top:12px; justify-content:center;">
      ${legend}
    </div>
  `;
}

function renderTopScholarsPodium() {
  const container = document.getElementById("topScholarsPodium");
  if (!container || !currentComparativeData) return;

  const scholars = currentComparativeData.top_scholars || [];
  if (scholars.length === 0) {
    container.innerHTML = '<div style="text-align:center; padding:20px; opacity:0.6;">No scholar records logged for this term.</div>';
    return;
  }

  container.innerHTML = scholars.map((s, idx) => {
    let rankBadgeClass = 'normal';
    let icon = '🎖️';
    if (idx === 0) { rankBadgeClass = 'gold'; icon = '👑'; }
    else if (idx === 1) { rankBadgeClass = 'silver'; icon = '🥈'; }
    else if (idx === 2) { rankBadgeClass = 'bronze'; icon = '🥉'; }

    return `
      <div class="podium-card ${idx === 0 ? 'rank-1' : ''}">
        <div style="display:flex; justify-content:space-between; align-items:flex-start;">
          <div style="display:flex; align-items:center; gap:10px;">
            <div style="font-size:1.6rem;">${icon}</div>
            <div>
              <h4 style="margin:0; font-size:0.95rem; font-weight:800;">${s.student_name}</h4>
              <span style="font-size:0.74rem; opacity:0.75;">${s.student_code} • ${s.class_name}</span>
            </div>
          </div>
          <span class="league-rank-badge ${rankBadgeClass}">${idx + 1}</span>
        </div>
        <div style="display:flex; justify-content:space-between; align-items:center; margin-top:14px; padding-top:10px; border-top:1px solid rgba(255,255,255,0.08);">
          <span style="font-size:0.78rem; opacity:0.8;">Subjects Tested: <b>${s.subjects_taken}</b></span>
          <div style="font-size:1.15rem; font-weight:900; color:#10b981;">${s.average_score}%</div>
        </div>
      </div>
    `;
  }).join("");
}

function handlePrintAction() {
  if (currentViewMode === 'comparative') {
    const s = document.createElement('style');
    s.id = '_compLandscapeHint';
    s.textContent = '@page{size:A4 landscape; margin: 10mm;}';
    document.head.appendChild(s);
    window.print();
    setTimeout(() => {
      const el = document.getElementById('_compLandscapeHint');
      if (el) el.parentNode.removeChild(el);
    }, 1000);
  } else {
    const s = document.createElement('style');
    s.id = '_landscapeHint';
    s.textContent = '@page{size:A4 landscape;}';
    document.head.appendChild(s);
    window.print();
    setTimeout(() => {
      const el = document.getElementById('_landscapeHint');
      if (el) el.parentNode.removeChild(el);
    }, 1000);
  }
}


