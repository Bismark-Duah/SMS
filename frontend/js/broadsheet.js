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
  link.setAttribute("download", `${classNameClean}_Broadsheet_${semNameClean}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

