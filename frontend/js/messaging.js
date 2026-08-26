const API_BASE = window.API_BASE || (window.location.origin.includes('http') ? (window.location.origin + '/api') : 'http://127.0.0.1:8000/api');

const token = localStorage.getItem('accessToken') || localStorage.getItem('token');
if (!token) {
  window.location.href = 'auth.html';
}

function getHeaders(extra = {}) {
  return { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json', ...extra };
}

// State
let recipients = [];
let selectedStudentIds = new Set();
let activeChannel = 'WHATSAPP'; // 'WHATSAPP' | 'SMS'
let currentPreviewData = null;

document.addEventListener('DOMContentLoaded', async () => {
  setupUserHeader();
  await loadDropdowns();
  await loadRecipients();
});

function setupUserHeader() {
  const nameEl = document.getElementById('userDisplayName');
  if (nameEl) {
    const userStr = localStorage.getItem('user');
    if (userStr) {
      try {
        const u = JSON.parse(userStr);
        nameEl.textContent = u.username || 'User';
      } catch (e) {}
    }
  }
  const logoutBtn = document.getElementById('logoutBtn');
  if (logoutBtn) {
    logoutBtn.addEventListener('click', () => {
      localStorage.clear();
      window.location.href = 'auth.html';
    });
  }
}

async function loadDropdowns() {
  try {
    const [resClasses, resHouses, resPrograms] = await Promise.all([
      fetch(`${API_BASE}/classes/`, { headers: getHeaders() }),
      fetch(`${API_BASE}/houses/`, { headers: getHeaders() }),
      fetch(`${API_BASE}/programs/`, { headers: getHeaders() }),
    ]);

    if (resClasses.ok) {
      const classes = await resClasses.json();
      const sel = document.getElementById('filterClassSelect');
      sel.innerHTML = '<option value="">All Assigned Classes...</option>' +
        classes.map(c => `<option value="${c.id}">${c.name}</option>`).join('');
    }

    if (resHouses.ok) {
      const houses = await resHouses.json();
      const sel = document.getElementById('filterHouseSelect');
      sel.innerHTML = '<option value="">All Assigned Houses...</option>' +
        houses.map(h => `<option value="${h.id}">${h.name} (${h.gender})</option>`).join('');
    }

    if (resPrograms.ok) {
      const progs = await resPrograms.json();
      const sel = document.getElementById('filterProgramSelect');
      sel.innerHTML = '<option value="">All Programs...</option>' +
        progs.map(p => `<option value="${p.id}">${p.name}</option>`).join('');
    }
  } catch (err) {
    console.error('Error loading filter dropdowns:', err);
  }
}

async function loadRecipients() {
  const classId = document.getElementById('filterClassSelect').value;
  const houseId = document.getElementById('filterHouseSelect').value;
  const programId = document.getElementById('filterProgramSelect').value;
  const groupByParent = document.getElementById('chkGroupParent').checked;

  const tbody = document.getElementById('recipientTableBody');
  tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; padding: 24px; opacity: 0.6;">Loading recipients...</td></tr>';

  let url = `${API_BASE}/messaging/recipients?`;
  if (classId) url += `class_id=${classId}&`;
  if (houseId) url += `house_id=${houseId}&`;
  if (programId) url += `program_id=${programId}&`;
  if (groupByParent) url += `group_by_parent=true&`;

  try {
    const res = await fetch(url, { headers: getHeaders() });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    recipients = await res.json();

    document.getElementById('recipientCount').textContent = recipients.length;
    selectedStudentIds.clear();
    recipients.forEach(r => selectedStudentIds.add(r.id));
    updateSelectedCount();

    renderRecipients();
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; padding: 24px; color: var(--error-color);">Failed to load recipients: ${err.message}</td></tr>`;
  }
}

function renderRecipients() {
  const tbody = document.getElementById('recipientTableBody');
  if (!recipients.length) {
    tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; padding: 24px; opacity: 0.6;">No students or guardians found for selected filters.</td></tr>';
    return;
  }

  tbody.innerHTML = recipients.map(r => {
    const isChecked = selectedStudentIds.has(r.id);
    const hasPhone = r.has_phone;
    const phoneDisplay = hasPhone
      ? `<strong>${r.phone}</strong>`
      : `<span class="chip warning" style="font-size: 0.72rem; color: #f59e0b;">⚠️ Missing Contact</span>`;

    return `
      <tr class="recipient-row ${!hasPhone ? 'warning-no-phone' : ''}">
        <td style="padding: 10px;">
          <input type="checkbox" value="${r.id}" ${isChecked ? 'checked' : ''} onchange="toggleRecipientSelect(${r.id}, this.checked)" />
        </td>
        <td style="padding: 10px;">
          <div><strong>${escapeHtml(r.full_name)}</strong></div>
          <div style="font-size: 0.78rem; opacity: 0.75;">Code: ${r.student_code}</div>
        </td>
        <td style="padding: 10px;">
          <div>${escapeHtml(r.class_name)}</div>
          <div style="font-size: 0.78rem; opacity: 0.75;">${escapeHtml(r.house_name)}</div>
        </td>
        <td style="padding: 10px;">
          <div>${escapeHtml(r.guardian_name)}</div>
          <div>${phoneDisplay}</div>
        </td>
        <td style="padding: 10px; text-align: right;">
          <button class="btn primary" style="padding: 4px 8px; font-size: 0.8rem;" onclick="openSinglePreview(${r.id})">👁️ Preview & Send</button>
        </td>
      </tr>
    `;
  }).join('');
}

function toggleRecipientSelect(studentId, isChecked) {
  if (isChecked) selectedStudentIds.add(studentId);
  else selectedStudentIds.delete(studentId);
  updateSelectedCount();
}

function toggleSelectAll(selectAll) {
  selectedStudentIds.clear();
  if (selectAll) {
    recipients.forEach(r => selectedStudentIds.add(r.id));
  }
  document.getElementById('chkSelectAllHeader').checked = selectAll;
  updateSelectedCount();
  renderRecipients();
}

function onHeaderCheckChange(chk) {
  toggleSelectAll(chk.checked);
}

function updateSelectedCount() {
  document.getElementById('selectedCount').textContent = selectedStudentIds.size;
}

function setChannel(channel) {
  activeChannel = channel;
  document.getElementById('btnChannelWA').classList.toggle('active', channel === 'WHATSAPP');
  document.getElementById('btnChannelSMS').classList.toggle('active', channel === 'SMS');
}

function onMsgTypeChange() {
  const type = document.getElementById('msgTypeSelect').value;
  const templateBox = document.getElementById('announcementTemplateBox');
  templateBox.style.display = (type === 'ANNOUNCEMENT') ? 'block' : 'none';
}

function insertTag(tag) {
  const txt = document.getElementById('customTemplateText');
  txt.value += ' ' + tag;
}

// ── Preview & Send Single ─────────────────────────────────────────────────────

function switchPreviewMode(mode) {
  const tableContainer = document.getElementById('richTableViewContainer');
  const textContainer = document.getElementById('rawTextViewContainer');
  const btnTable = document.getElementById('btnViewRichTable');
  const btnText = document.getElementById('btnViewRawText');

  if (mode === 'table') {
    tableContainer.style.display = 'block';
    textContainer.style.display = 'none';
    btnTable.classList.add('active');
    btnText.classList.remove('active');
  } else {
    tableContainer.style.display = 'none';
    textContainer.style.display = 'block';
    btnTable.classList.remove('active');
    btnText.classList.add('active');
  }
}

function copyWhatsAppTextToClipboard() {
  const txt = document.getElementById('previewTextContent').textContent;
  if (!txt) return;
  navigator.clipboard.writeText(txt).then(() => {
    alert('📋 Formatted message copied to clipboard!');
  }).catch(err => {
    alert('Failed to copy: ' + err.message);
  });
}

function getGradeBadgeColor(grade) {
  const g = (grade || '').toUpperCase();
  if (['A1', 'B2'].includes(g)) return 'background:#059669; color:#ffffff;';
  if (['B3', 'C4', 'C5', 'C6'].includes(g)) return 'background:#2563eb; color:#ffffff;';
  if (['D7', 'E8'].includes(g)) return 'background:#d97706; color:#ffffff;';
  if (['F9'].includes(g)) return 'background:#dc2626; color:#ffffff;';
  return 'background:#64748b; color:#ffffff;';
}

function renderRichTableView(data, msgType) {
  const renderArea = document.getElementById('richTableRenderArea');
  if (!data) {
    renderArea.innerHTML = `<div style="text-align:center; padding:20px; opacity:0.6;">No preview data available.</div>`;
    return;
  }

  const rc = data.report_card_data || {};
  const sch = rc.school || { name: 'J.A. KUFFOUR STEM TECHNICAL', motto: 'Knowledge is Power', title: 'TERMINAL REPORT CARD' };
  const st = rc.student || { name: data.full_name, code: data.student_code, class_name: data.class_name, house_dorm: 'Day Student', guardian_name: data.guardian_name, phone: data.phone, gender: 'N/A' };
  const acad = rc.academic || { year: '2025/2026', term: 'Term 1', vacation_date: '-', reopening_date: '-' };
  const sum = rc.summary || { total_marks: 0, average_mark: data.avg_score || 0.0, overall_grade: data.overall_grade || 'N/A', class_position: data.position || 'N/A', attendance_present: 0, attendance_total: 0 };
  const ev = rc.evaluations || { attitude: '-', conduct: 'Good', interest: '-', form_teacher_remarks: 'Hardworking student.', headmaster_remarks: '-', promoted_to: '-' };
  const fin = rc.finances || { fee_balance: 0.0 };
  const scores = rc.scores || [];

  let scoresRowsHtml = '';
  if (scores.length === 0) {
    scoresRowsHtml = `<tr><td colspan="7" style="text-align:center; padding:16px; opacity:0.6;">No score records found for this term.</td></tr>`;
  } else {
    scores.forEach(s => {
      const badgeStyle = getGradeBadgeColor(s.grade);
      scoresRowsHtml += `
        <tr>
          <td style="padding:8px 10px; font-weight:600;">${escapeHtml(s.subject)}</td>
          <td style="text-align:center; padding:8px;">${s.class_score ?? '-'}</td>
          <td style="text-align:center; padding:8px;">${s.exam_score ?? '-'}</td>
          <td style="text-align:center; padding:8px; font-weight:700; color:#2563eb;">${s.total_score ?? '-'}</td>
          <td style="text-align:center; padding:8px;"><span style="padding:3px 8px; border-radius:12px; font-size:0.75rem; font-weight:700; ${badgeStyle}">${escapeHtml(s.grade)}</span></td>
          <td style="text-align:center; padding:8px; font-size:0.82rem;">${escapeHtml(s.remark || '-')}</td>
          <td style="text-align:center; padding:8px; font-size:0.82rem; font-weight:600;">${escapeHtml(s.position || '-')}</td>
        </tr>
      `;
    });
  }

  renderArea.innerHTML = `
    <div style="background:var(--card-bg, #0f172a); border:1px solid var(--border-color); border-radius:10px; padding:18px; color:var(--text-color);">
      <!-- School Branding Header -->
      <div style="text-align:center; border-bottom:2px solid #2563eb; padding-bottom:12px; margin-bottom:16px;">
        <span style="display:inline-block; background:#2563eb; color:white; font-size:0.7rem; font-weight:800; padding:2px 8px; border-radius:4px; text-transform:uppercase; letter-spacing:1px; margin-bottom:6px;">Official Report Document</span>
        <h2 style="margin:4px 0 2px 0; font-size:1.25rem; font-weight:800; color:#f8fafc;">${escapeHtml(sch.name)}</h2>
        <p style="margin:0; font-size:0.8rem; opacity:0.7; font-style:italic;">${escapeHtml(sch.motto || 'Knowledge is Power')}</p>
        <h4 style="margin:8px 0 0 0; font-size:0.95rem; text-transform:uppercase; letter-spacing:1px; color:#38bdf8;">${escapeHtml(sch.title || 'TERMINAL REPORT CARD')}</h4>
        <div style="font-size:0.8rem; font-weight:600; opacity:0.85; margin-top:2px;">Academic Year: ${escapeHtml(acad.year)} | ${escapeHtml(acad.term)}</div>
      </div>

      <!-- Student Bio Matrix Table (Columns & Rows) -->
      <table style="width:100%; border-collapse:collapse; margin-bottom:16px; font-size:0.85rem; background:rgba(255,255,255,0.03); border-radius:6px; border:1px solid var(--border-color);">
        <tr>
          <td style="padding:6px 10px; border:1px solid var(--border-color); width:50%;"><strong>Student Name:</strong> ${escapeHtml(st.name)}</td>
          <td style="padding:6px 10px; border:1px solid var(--border-color); width:50%;"><strong>Student ID:</strong> ${escapeHtml(st.code)}</td>
        </tr>
        <tr>
          <td style="padding:6px 10px; border:1px solid var(--border-color);"><strong>Class Section:</strong> ${escapeHtml(st.class_name)}</td>
          <td style="padding:6px 10px; border:1px solid var(--border-color);"><strong>House / Dorm:</strong> ${escapeHtml(st.house_dorm || 'Day Student')}</td>
        </tr>
        <tr>
          <td style="padding:6px 10px; border:1px solid var(--border-color);"><strong>Guardian Contact:</strong> ${escapeHtml(st.guardian_name)}</td>
          <td style="padding:6px 10px; border:1px solid var(--border-color);"><strong>Phone:</strong> ${escapeHtml(st.phone || 'N/A')}</td>
        </tr>
      </table>

      <!-- Academic Subject Scores Table -->
      <h4 style="margin:0 0 8px 0; font-size:0.9rem; border-left:3px solid #2563eb; padding-left:8px;">📊 ACADEMIC SUBJECT SCORES</h4>
      <div style="overflow-x:auto; margin-bottom:16px;">
        <table style="width:100%; border-collapse:collapse; font-size:0.82rem; border:1px solid var(--border-color);">
          <thead>
            <tr style="background:rgba(37,99,235,0.15); border-bottom:1px solid var(--border-color);">
              <th style="padding:8px 10px; text-align:left;">Subject</th>
              <th style="padding:8px; text-align:center;">Class (30%)</th>
              <th style="padding:8px; text-align:center;">Exam (70%)</th>
              <th style="padding:8px; text-align:center;">Total (100%)</th>
              <th style="padding:8px; text-align:center;">Grade</th>
              <th style="padding:8px; text-align:center;">Remark</th>
              <th style="padding:8px; text-align:center;">Pos</th>
            </tr>
          </thead>
          <tbody style="divide-y divide-slate-700;">
            ${scoresRowsHtml}
          </tbody>
        </table>
      </div>

      <!-- Performance Summary Cards Matrix -->
      <h4 style="margin:0 0 8px 0; font-size:0.9rem; border-left:3px solid #10b981; padding-left:8px;">🏆 OVERALL PERFORMANCE SUMMARY</h4>
      <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(130px, 1fr)); gap:10px; margin-bottom:16px;">
        <div style="background:rgba(255,255,255,0.04); padding:10px; border-radius:6px; text-align:center; border:1px solid var(--border-color);">
          <div style="font-size:1.1rem; font-weight:800; color:#38bdf8;">${sum.average_mark}%</div>
          <div style="font-size:0.72rem; opacity:0.7; font-weight:600;">Average Score</div>
        </div>
        <div style="background:rgba(255,255,255,0.04); padding:10px; border-radius:6px; text-align:center; border:1px solid var(--border-color);">
          <div style="font-size:1.1rem; font-weight:800; color:#10b981;">${escapeHtml(sum.overall_grade)}</div>
          <div style="font-size:0.72rem; opacity:0.7; font-weight:600;">Overall Grade</div>
        </div>
        <div style="background:rgba(255,255,255,0.04); padding:10px; border-radius:6px; text-align:center; border:1px solid var(--border-color);">
          <div style="font-size:1.1rem; font-weight:800; color:#f59e0b;">${escapeHtml(sum.class_position)}</div>
          <div style="font-size:0.72rem; opacity:0.7; font-weight:600;">Class Position</div>
        </div>
        <div style="background:rgba(255,255,255,0.04); padding:10px; border-radius:6px; text-align:center; border:1px solid var(--border-color);">
          <div style="font-size:1.1rem; font-weight:800; color:#a855f7;">GH₵ ${(fin.fee_balance || 0).toFixed(2)}</div>
          <div style="font-size:0.72rem; opacity:0.7; font-weight:600;">Fee Balance Due</div>
        </div>
      </div>

      <!-- Conduct & Remarks Box -->
      <div style="background:rgba(255,255,255,0.03); padding:12px 14px; border-radius:6px; font-size:0.82rem; border:1px solid var(--border-color);">
        <div style="margin-bottom:4px;"><strong>Conduct:</strong> ${escapeHtml(ev.conduct || 'Good')}</div>
        <div style="margin-bottom:4px;"><strong>Teacher Remarks:</strong> ${escapeHtml(ev.form_teacher_remarks || 'Hardworking student.')}</div>
        <div><strong>Headmaster Comments:</strong> ${escapeHtml(ev.headmaster_remarks || '-')}</div>
      </div>
    </div>
  `;
}

async function openSinglePreview(studentId) {
  const msgType = document.getElementById('msgTypeSelect').value;

  try {
    const res = await fetch(`${API_BASE}/messaging/report-payload`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({ student_id: studentId, msg_type: msgType })
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    currentPreviewData = data;

    let payloadText = (activeChannel === 'WHATSAPP') ? data.whatsapp_payload : data.sms_payload;

    if (msgType === 'ANNOUNCEMENT') {
      const template = document.getElementById('customTemplateText').value || 'Notice: {student_name} report update.';
      payloadText = template
        .replace(/{student_name}/g, data.full_name)
        .replace(/{guardian_name}/g, data.guardian_name)
        .replace(/{class_name}/g, data.class_name)
        .replace(/{school_name}/g, 'School');
    }

    document.getElementById('previewModalTitle').textContent = `Preview Report - ${data.full_name}`;
    document.getElementById('previewMetaInfo').innerHTML = `
      Guardian: <strong>${escapeHtml(data.guardian_name)}</strong> (${data.phone || 'No phone'}) · Class: <strong>${escapeHtml(data.class_name)}</strong>
    `;
    document.getElementById('previewTextContent').textContent = payloadText;

    const charCount = payloadText.length;
    const smsSegments = Math.ceil(charCount / 160) || 1;
    document.getElementById('charCountLabel').textContent = `${charCount} chars · ${smsSegments} SMS segment(s)`;
    document.getElementById('gradeHighlightLabel').textContent = `Grade / Status: ${data.overall_grade}`;

    // Render Rich Table View
    renderRichTableView(data, msgType);
    switchPreviewMode('table');

    document.getElementById('previewModal').style.display = 'flex';
  } catch (err) {
    alert(`Error generating preview payload: ${err.message}`);
  }
}

function closePreviewModal() {
  document.getElementById('previewModal').style.display = 'none';
  currentPreviewData = null;
}

async function executeSendCurrent() {
  if (!currentPreviewData) return;

  const data = currentPreviewData;
  const payloadText = document.getElementById('previewTextContent').textContent;
  const msgType = document.getElementById('msgTypeSelect').value;
  const cleanPhone = (data.phone || '').replace(/[^0-9+]/g, '');

  if (!cleanPhone) {
    alert('Warning: Guardian has no valid phone number recorded. Message logged to outbox as QUEUED.');
  }

  // 1. Dispatch via Client Intent Link
  if (cleanPhone) {
    if (activeChannel === 'WHATSAPP') {
      const encodedMsg = encodeURIComponent(payloadText);
      const waUrl = `https://wa.me/${cleanPhone.replace('+', '')}?text=${encodedMsg}`;
      window.open(waUrl, '_blank');
    } else {
      const encodedMsg = encodeURIComponent(payloadText);
      const smsUrl = `sms:${cleanPhone}?body=${encodedMsg}`;
      window.location.href = smsUrl;
    }
  }

  // 2. Log Message to Backend SQLite Database
  try {
    await fetch(`${API_BASE}/messaging/send-log`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({
        student_id: data.student_id,
        recipient_name: data.guardian_name,
        recipient_phone: data.phone,
        channel: activeChannel,
        message_type: msgType,
        message_body: payloadText,
        overall_grade: data.overall_grade,
        status: cleanPhone ? 'SENT' : 'QUEUED'
      })
    });
  } catch (e) {
    console.error('Failed to log message to outbox:', e);
  }

  closePreviewModal();
  alert(`Message dispatched via ${activeChannel} and recorded in local Outbox!`);
}

// ── Bulk Send & CSV Export ───────────────────────────────────────────────────

async function openBulkPreviewModal() {
  if (selectedStudentIds.size === 0) {
    alert('Please select at least one student recipient.');
    return;
  }

  const selectedList = recipients.filter(r => selectedStudentIds.has(r.id));
  const missingCount = selectedList.filter(r => !r.has_phone).length;

  if (missingCount > 0) {
    if (!confirm(`Warning: ${missingCount} of the ${selectedList.length} selected recipients have no phone number. They will be logged as QUEUED. Proceed?`)) {
      return;
    }
  }

  const firstId = Array.from(selectedStudentIds)[0];
  await openSinglePreview(firstId);
}

async function exportBulkCSV() {
  if (selectedStudentIds.size === 0) {
    alert('Please select at least one recipient to export CSV.');
    return;
  }

  const msgType = document.getElementById('msgTypeSelect').value;
  const selectedList = recipients.filter(r => selectedStudentIds.has(r.id));

  let csvRows = [
    ["Student Code", "Student Name", "Class Name", "Guardian Name", "Guardian Phone", "Channel", "Message Body"].join(",")
  ];

  const batchLogs = [];

  for (const r of selectedList) {
    let body = `Notice for ${r.full_name} (${r.class_name}).`;
    try {
      const res = await fetch(`${API_BASE}/messaging/report-payload`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify({ student_id: r.id, msg_type: msgType })
      });
      if (res.ok) {
        const data = await res.json();
        body = (activeChannel === 'WHATSAPP') ? data.whatsapp_payload : data.sms_payload;
      }
    } catch (e) {}

    const cleanPhone = (r.phone || "").replace(/[^0-9+]/g, "");
    csvRows.push([
      `"${r.student_code}"`,
      `"${escapeCsv(r.full_name)}"`,
      `"${escapeCsv(r.class_name)}"`,
      `"${escapeCsv(r.guardian_name)}"`,
      `"${cleanPhone}"`,
      `"${activeChannel}"`,
      `"${escapeCsv(body)}"`
    ].join(","));

    batchLogs.push({
      student_id: r.id,
      recipient_name: r.guardian_name,
      recipient_phone: r.phone,
      channel: activeChannel,
      message_type: msgType,
      message_body: body,
      overall_grade: "BULK_EXPORT",
      status: cleanPhone ? "SENT" : "QUEUED"
    });
  }

  // Download CSV
  const csvContent = "data:text/csv;charset=utf-8," + encodeURIComponent(csvRows.join("\n"));
  const link = document.createElement("a");
  link.setAttribute("href", csvContent);
  link.setAttribute("download", `bulk_sms_export_${new Date().toISOString().slice(0,10)}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);

  // Log to outbox in batch
  try {
    await fetch(`${API_BASE}/messaging/batch-log`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify(batchLogs)
    });
  } catch (e) {
    console.error("Batch log failed:", e);
  }

  alert(`Successfully exported CSV for ${selectedList.length} recipients and logged records to Outbox!`);
}

// ── Outbox & Tab Navigation ───────────────────────────────────────────────────

function switchMainTab(tab) {
  document.getElementById('panelDispatch').style.display = (tab === 'dispatch') ? 'grid' : 'none';
  document.getElementById('panelOutbox').style.display = (tab === 'outbox') ? 'block' : 'none';
  const gwPanel = document.getElementById('panelGateway');
  if (gwPanel) gwPanel.style.display = (tab === 'gateway') ? 'block' : 'none';

  document.getElementById('tabDispatchBtn').classList.toggle('primary', tab === 'dispatch');
  document.getElementById('tabDispatchBtn').classList.toggle('secondary', tab !== 'dispatch');
  document.getElementById('tabOutboxBtn').classList.toggle('primary', tab === 'outbox');
  document.getElementById('tabOutboxBtn').classList.toggle('secondary', tab !== 'outbox');
  const gwBtn = document.getElementById('tabGatewayBtn');
  if (gwBtn) {
    gwBtn.classList.toggle('primary', tab === 'gateway');
    gwBtn.classList.toggle('secondary', tab !== 'gateway');
  }

  if (tab === 'outbox') {
    loadOutboxLogs();
  } else if (tab === 'gateway') {
    loadGatewaySettings();
  }
}

async function loadOutboxLogs() {
  const tbody = document.getElementById('outboxTableBody');
  tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; padding: 24px; opacity: 0.6;">Loading outbox history...</td></tr>';

  try {
    const res = await fetch(`${API_BASE}/messaging/logs`, { headers: getHeaders() });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const logs = await res.json();

    if (!logs.length) {
      tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; padding: 24px; opacity: 0.6;">No message history recorded yet.</td></tr>';
      return;
    }

    tbody.innerHTML = logs.map(l => {
      let statusChipClass = 'warning';
      if (l.status === 'SENT') statusChipClass = 'success';
      else if (l.status === 'FAILED' || l.status === 'FAILED_NO_PHONE') statusChipClass = 'error';

      let channelChipClass = 'primary';
      if (l.channel === 'WHATSAPP') channelChipClass = 'success';
      else if (l.channel === 'EMAIL') channelChipClass = 'info';

      return `
        <tr>
          <td style="padding: 10px; font-size: 0.82rem; opacity: 0.85;">${l.created_at}</td>
          <td style="padding: 10px;">${escapeHtml(l.sender_name)}</td>
          <td style="padding: 10px;"><strong>${escapeHtml(l.student_name)}</strong><br/><span style="font-size:0.75rem; opacity:0.75;">${escapeHtml(l.recipient_name)}</span></td>
          <td style="padding: 10px; font-size: 0.85rem;">${escapeHtml(l.recipient_phone)}</td>
          <td style="padding: 10px;"><span class="chip ${channelChipClass}">${l.channel}</span></td>
          <td style="padding: 10px; font-size: 0.82rem;">${escapeHtml(l.message_type)}</td>
          <td style="padding: 10px; font-size: 0.82rem;"><strong>${escapeHtml(l.overall_grade)}</strong></td>
          <td style="padding: 10px;"><span class="chip ${statusChipClass}">${l.status}</span></td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; padding: 24px; color: var(--error-color);">Failed to load outbox: ${err.message}</td></tr>`;
  }
}

// ── Gateway Settings & Live Testing ───────────────────────────────────────────

function onSmsProviderChange() {
  const prov = document.getElementById('gwSmsProvider').value;
  const clientGroup = document.getElementById('gwSmsClientIdGroup');
  if (clientGroup) {
    clientGroup.style.display = (prov === 'HUBTEL' || prov === 'TWILIO') ? 'block' : 'none';
  }
}

async function loadGatewaySettings() {
  try {
    const res = await fetch(`${API_BASE}/messaging/gateway-settings`, { headers: getHeaders() });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const cfg = await res.json();

    document.getElementById('gwSmsProvider').value = cfg.sms_provider || 'NONE';
    document.getElementById('gwSmsSenderId').value = cfg.sms_sender_id || 'EduManage';
    document.getElementById('gwSmsApiKey').value = cfg.sms_api_key || '';
    if (document.getElementById('gwSmsClientId')) {
      document.getElementById('gwSmsClientId').value = cfg.sms_client_id || '';
    }

    document.getElementById('gwWaProvider').value = cfg.whatsapp_provider || 'NONE';
    document.getElementById('gwWaSenderNumber').value = cfg.whatsapp_sender_number || '';
    document.getElementById('gwWaAccountSid').value = cfg.whatsapp_account_sid || '';
    document.getElementById('gwWaApiKey').value = cfg.whatsapp_api_key || '';

    document.getElementById('gwAutoGateOut').checked = !!cfg.auto_notify_exeat_gateout;
    document.getElementById('gwAutoGateIn').checked = !!cfg.auto_notify_exeat_gatein;
    document.getElementById('gwAutoFeePayment').checked = !!cfg.auto_notify_fee_payment;
    document.getElementById('gwAutoAbsence').checked = !!cfg.auto_notify_absence;

    onSmsProviderChange();
  } catch (err) {
    console.error('Failed to load gateway settings:', err);
  }
}

async function saveGatewaySettings() {
  const payload = {
    sms_provider: document.getElementById('gwSmsProvider').value,
    sms_sender_id: document.getElementById('gwSmsSenderId').value,
    sms_api_key: document.getElementById('gwSmsApiKey').value,
    sms_client_id: document.getElementById('gwSmsClientId') ? document.getElementById('gwSmsClientId').value : '',

    whatsapp_provider: document.getElementById('gwWaProvider').value,
    whatsapp_sender_number: document.getElementById('gwWaSenderNumber').value,
    whatsapp_account_sid: document.getElementById('gwWaAccountSid').value,
    whatsapp_api_key: document.getElementById('gwWaApiKey').value,

    auto_notify_exeat_gateout: document.getElementById('gwAutoGateOut').checked,
    auto_notify_exeat_gatein: document.getElementById('gwAutoGateIn').checked,
    auto_notify_fee_payment: document.getElementById('gwAutoFeePayment').checked,
    auto_notify_absence: document.getElementById('gwAutoAbsence').checked
  };

  try {
    const res = await fetch(`${API_BASE}/messaging/gateway-settings`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    alert('✅ Gateway and automated event triggers saved successfully!');
    await loadGatewaySettings();
  } catch (err) {
    alert(`Failed to save gateway settings: ${err.message}`);
  }
}

function openTestGatewayModal() {
  document.getElementById('testResultArea').style.display = 'none';
  document.getElementById('testGatewayModal').style.display = 'flex';
}

function closeTestGatewayModal() {
  document.getElementById('testGatewayModal').style.display = 'none';
}

async function runTestDelivery() {
  const channel = document.getElementById('testChannelSelect').value;
  const recipient = document.getElementById('testRecipientInput').value.trim();
  const message = document.getElementById('testMessageInput').value.trim();
  const resultArea = document.getElementById('testResultArea');

  if (!recipient) {
    alert('Please enter a recipient phone number or email address.');
    return;
  }

  resultArea.style.display = 'block';
  resultArea.innerHTML = '<span style="opacity:0.7;">⏳ Dispatching test message through gateway...</span>';

  try {
    const res = await fetch(`${API_BASE}/messaging/test-gateway`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({ channel, recipient, message })
    });
    const data = await res.json();

    if (data.success) {
      resultArea.innerHTML = `
        <div style="background: rgba(16, 185, 129, 0.15); border: 1px solid #10b981; color: #34d399; padding: 10px; border-radius: 6px;">
          <strong>✅ Delivery Successful / Handled</strong><br/>
          Provider: <code>${data.provider || channel}</code> &bull; Status: <code>${data.status || 'OK'}</code>
          ${data.intent_url ? `<br/><a href="${data.intent_url}" target="_blank" style="color: #38bdf8; text-decoration: underline; font-size: 0.8rem; margin-top: 4px; display: inline-block;">Open Intent Link ↗</a>` : ''}
        </div>
      `;
    } else {
      resultArea.innerHTML = `
        <div style="background: rgba(239, 68, 68, 0.15); border: 1px solid #ef4444; color: #f87171; padding: 10px; border-radius: 6px;">
          <strong>⚠️ Test Dispatch Notice</strong><br/>
          Status: <code>${data.status || 'FAILED'}</code><br/>
          ${data.message || data.error || 'Check provider API key and internet connectivity.'}
        </div>
      `;
    }
  } catch (err) {
    resultArea.innerHTML = `
      <div style="background: rgba(239, 68, 68, 0.15); border: 1px solid #ef4444; color: #f87171; padding: 10px; border-radius: 6px;">
        <strong>❌ Connection Error:</strong> ${err.message}
      </div>
    `;
  }
}

async function triggerAutoLinkGuardians() {
  try {
    const res = await fetch(`${API_BASE}/students/auto-link-guardians`, {
      method: 'POST',
      headers: getHeaders()
    });
    const data = await res.json();
    alert(data.message || 'Auto-linking completed!');
    await loadRecipients();
  } catch (err) {
    alert(`Auto-link failed: ${err.message}`);
  }
}

function escapeHtml(str) {
  return str ? String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;") : '';
}

function escapeCsv(str) {
  return str ? String(str).replace(/"/g, '""').replace(/\n/g, ' ') : '';
}
