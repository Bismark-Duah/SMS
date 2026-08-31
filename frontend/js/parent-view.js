/* ============================================================
   Parent Portal – parent-view.js
   Phase D: Enhanced Student/Parent Portal
   ============================================================ */

const API_BASE = window.API_BASE || (window.location.origin.includes('http') ? (window.location.origin + '/api') : 'http://127.0.0.1:8000/api');

// ── Auth guard ────────────────────────────────────────────────
const token = localStorage.getItem('accessToken');
if (!token) {
  window.location.href = 'auth.html';
}

function getHeaders(extra = {}) {
  return { 'Authorization': `Bearer ${token}`, ...extra };
}
function jsonHeaders() {
  return getHeaders({ 'Content-Type': 'application/json' });
}

// ── State ─────────────────────────────────────────────────────
let currentChildId = null;
let allChildren    = [];
let resultsChart   = null;  // Chart.js instance

// ── Helpers ───────────────────────────────────────────────────
function fmt(num) {
  return Number(num).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
function fmtDate(str) {
  if (!str) return '—';
  return new Date(str).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

// ── Tab switching ─────────────────────────────────────────────
function switchTab(name) {
  document.querySelectorAll('.tab-btn').forEach((btn, i) => {
    btn.classList.toggle('active', btn.textContent.toLowerCase().includes(name));
  });
  document.querySelectorAll('.tab-panel').forEach(p => {
    p.classList.toggle('active', p.id === `tab-${name}`);
  });
}

// ── Load portal (child list) ──────────────────────────────────
async function loadPortal() {
  const userId = localStorage.getItem('userId');
  const role   = localStorage.getItem('userRole');

  // Update hero
  const parentName = localStorage.getItem('fullName') || localStorage.getItem('username') || 'Parent';
  document.getElementById('heroName').textContent = `Welcome, ${parentName}`;

  const childSelect = document.getElementById('child_id');
  try {
    const res = await fetch(`${API_BASE}/students/`, { headers: getHeaders() });
    if (!res.ok) throw new Error('Failed to load students');
    const allStudents = await res.json();

    // Admins & teachers can see all students; parents see their own children
    if (role === 'parent') {
      allChildren = allStudents.filter(s => String(s.parent_id) === String(userId));
    } else {
      allChildren = allStudents;
    }

    if (allChildren.length === 0) {
      childSelect.innerHTML = '<option value="">No children linked to this account.</option>';
      return;
    }

    childSelect.innerHTML = allChildren.map(c =>
      `<option value="${c.id}">${c.full_name}</option>`
    ).join('');

    document.getElementById('viewBtn').disabled = false;
    // Auto-load first child
    loadChildDashboard();
  } catch (err) {
    console.error('Error loading children:', err);
    childSelect.innerHTML = '<option value="">Error loading children</option>';
  }
}

// ── On child dropdown change ──────────────────────────────────
function onChildChange() {
  document.getElementById('viewBtn').disabled = false;
}

window.downloadSelectedChildReportCard = function() {
  if (!currentChildId) return;
  window.open(`report-card.html?student_id=${currentChildId}`, '_blank');
};

window.downloadSelectedChildAdmissionPackage = async function() {
  if (!currentChildId) {
    alert('Please select a child first.');
    return;
  }

  const btn1 = document.getElementById('downloadProspectusBtn');
  const btn2 = document.getElementById('btnCardDownloadProspectus');
  const orig1 = btn1 ? btn1.innerHTML : '';
  const orig2 = btn2 ? btn2.innerHTML : '';

  if (btn1) { btn1.innerHTML = '⏳ Generating PDF...'; btn1.disabled = true; }
  if (btn2) { btn2.innerHTML = '⏳ Generating Package...'; btn2.disabled = true; }

  try {
    const res = await fetch(`${API_BASE}/students/${currentChildId}/admission-package-pdf`, {
      headers: getHeaders()
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to download admission package.');
    }
    const blob = await res.blob();
    const blobUrl = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = blobUrl;
    a.download = `Admission_Package_Child_${currentChildId}.pdf`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(blobUrl);
    document.body.removeChild(a);
  } catch (err) {
    alert(`Download Error: ${err.message}`);
  } finally {
    if (btn1) { btn1.innerHTML = orig1; btn1.disabled = false; }
    if (btn2) { btn2.innerHTML = orig2; btn2.disabled = false; }
  }
};

// ── Main dashboard loader ─────────────────────────────────────
async function loadChildDashboard() {
  const childId = document.getElementById('child_id').value;
  if (!childId) return;
  currentChildId = childId;

  // Show dashboard container & action buttons
  document.getElementById('childDashboard').style.display = 'block';
  const downloadBtn = document.getElementById('downloadReportCardBtn');
  if (downloadBtn) downloadBtn.style.display = 'inline-flex';
  const downloadProsBtn = document.getElementById('downloadProspectusBtn');
  if (downloadProsBtn) downloadProsBtn.style.display = 'inline-flex';

  // Update hero subtitle
  const child = allChildren.find(c => String(c.id) === String(childId));
  if (child) {
    const classInfo = child.class_name ? ` · Class: ${child.class_name}` : '';
    document.getElementById('heroSub').textContent =
      `Viewing records for ${child.full_name}${classInfo} · ${child.student_code || ''}`;
  }

  // Feature gating for Basic mode / Day Only
  const F = (window.SchoolFeatures && window.SchoolFeatures.version)
    ? window.SchoolFeatures
    : (window.FeatureGate ? window.FeatureGate.getFeatures() : null);

  const isBasicOnly = F ? F.isBasicOnly : (localStorage.getItem('school_mode') === 'BASIC_ONLY');
  const isBoarding = F ? F.isBoarding : (localStorage.getItem('boarding_status') !== 'DAY_ONLY');

  const exeatTabBtn = document.querySelector('.tab-btn[onclick*="exeat"]');
  if (exeatTabBtn) {
    exeatTabBtn.style.display = (!isBasicOnly && isBoarding) ? 'inline-block' : 'none';
  }

  // Reset KPIs
  ['kpiAttendance', 'kpiBalance', 'kpiAvgScore', 'kpiDiscipline'].forEach(id => {
    document.getElementById(id).textContent = '…';
  });

  // Load all sections in parallel
  const tasks = [
    loadAttendanceHeatmap(childId),
    loadFees(childId),
    loadResults(childId),
    loadDiscipline(childId),
    loadNotifications(childId),
    loadSemesters()
  ];
  if (!isBasicOnly && isBoarding) {
    tasks.push(loadExeat(childId));
  }
  await Promise.all(tasks);
}

// ── ATTENDANCE HEATMAP ────────────────────────────────────────
async function loadAttendanceHeatmap(childId) {
  try {
    const res  = await fetch(`${API_BASE}/attendance/student/${childId}`, { headers: getHeaders() });
    const data = await res.json();

    // Build a map: date string → status
    const dayMap = {};
    data.forEach(r => { dayMap[r.date] = r.status; });

    const totalDays    = data.length;
    const presentDays  = data.filter(r => r.status === 'Present').length;
    const percentage   = totalDays ? Math.round((presentDays / totalDays) * 100) : 0;

    // Update KPI
    document.getElementById('kpiAttendance').textContent = `${percentage}%`;
    document.getElementById('kpiAttendanceSub').textContent =
      `${presentDays} / ${totalDays} days present`;
    const kpiCard = document.getElementById('kpiAttendance').closest('.stat-card');
    kpiCard.className = `stat-card ${percentage >= 80 ? 'success' : percentage >= 60 ? 'warning' : 'danger'}`;

    document.getElementById('attendanceBadge').textContent =
      `${percentage}% · ${presentDays}/${totalDays} days`;

    // No records
    if (totalDays === 0) {
      document.getElementById('attendanceEmptyMsg').style.display = 'block';
      return;
    }
    document.getElementById('attendanceEmptyMsg').style.display = 'none';

    // Build calendar heatmap
    // Find date range (first to last record date)
    const sortedDates = Object.keys(dayMap).sort();
    const firstDate = new Date(sortedDates[0]);
    const lastDate  = new Date(sortedDates[sortedDates.length - 1]);

    // Start from the Sunday of the week containing firstDate
    const start = new Date(firstDate);
    start.setDate(start.getDate() - start.getDay());

    const grid = document.getElementById('heatmapGrid');
    // Remove previous cells (keep the 7 day-header divs)
    const headers = Array.from(grid.querySelectorAll('.heatmap-day-header'));
    grid.innerHTML = '';
    headers.forEach(h => grid.appendChild(h));

    const cur = new Date(start);
    while (cur <= lastDate) {
      const dateStr = cur.toISOString().slice(0, 10);
      const status  = dayMap[dateStr];
      const day     = cur.getDay(); // 0=Sun

      const cell = document.createElement('div');
      const dayNum = cur.getDate();

      if (status) {
        cell.className = `heatmap-cell ${status.toLowerCase()}`;
        cell.textContent = dayNum;
        cell.title = `${dateStr} — ${status}`;
      } else {
        // Weekend or no-school day
        const isWeekend = (day === 0 || day === 6);
        cell.className = isWeekend ? 'heatmap-cell empty' : 'heatmap-cell filler';
        cell.textContent = dayNum;
        cell.style.opacity = '0.4';
        cell.title = dateStr;
      }
      grid.appendChild(cell);
      cur.setDate(cur.getDate() + 1);
    }

  } catch (err) {
    console.error('Attendance heatmap error:', err);
    document.getElementById('attendanceBadge').textContent = 'Error';
  }
}

// ── FEE BALANCE ───────────────────────────────────────────────
let currentChildFees = [];
let currentChildBalance = 0;

async function loadFees(childId) {
  try {
    const res  = await fetch(`${API_BASE}/fees/student/${childId}/summary`, { headers: getHeaders() });
    const data = await res.json();
    currentChildFees = data.fees || [];

    // KPI card
    const balance = data.total_balance || 0;
    currentChildBalance = balance;
    document.getElementById('kpiBalance').textContent = `GHS ${fmt(balance)}`;
    document.getElementById('kpiBalanceSub').textContent =
      `of GHS ${fmt(data.total_billed)} billed`;
    const balCard = document.getElementById('kpiBalanceCard');
    balCard.className = `stat-card ${balance <= 0 ? 'success' : balance < data.total_billed / 2 ? 'warning' : 'danger'}`;

    document.getElementById('feesBadge').textContent =
      `Balance: GHS ${fmt(balance)}`;

    // Show or hide "Pay Outstanding Balance" button
    const btnPayAll = document.getElementById('btnPayAllFees');
    if (btnPayAll) {
      btnPayAll.style.display = balance > 0 ? 'inline-block' : 'none';
    }

    // Summary pills
    document.getElementById('feeSummaryBar').innerHTML = `
      <div class="fee-pill billed">
        <span>GHS ${fmt(data.total_billed)}</span>Total Billed
      </div>
      <div class="fee-pill paid">
        <span>GHS ${fmt(data.total_paid)}</span>Total Paid
      </div>
      <div class="fee-pill balance">
        <span>GHS ${fmt(data.total_balance)}</span>Outstanding
      </div>
    `;

    // Table rows
    const tbody = document.getElementById('feesTableBody');
    if (!data.fees || data.fees.length === 0) {
      tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;padding:24px;color:var(--text-muted);">No fee records found.</td></tr>';
      return;
    }
    tbody.innerHTML = data.fees.map(f => {
      let actionHtml = '';
      if (f.balance > 0) {
        const safeType = (f.fee_type || 'Fee').replace(/'/g, "\\'");
        actionHtml += `<button class="fee-btn-action fee-btn-pay" onclick="openPayFeeModal(${f.id}, ${f.balance}, '${safeType}')">💳 Pay</button> `;
      }
      if (f.latest_payment_id) {
        actionHtml += `<button class="fee-btn-action fee-btn-receipt" onclick="downloadPaymentReceipt(${f.latest_payment_id})">📄 Receipt</button>`;
      }
      if (!actionHtml) {
        actionHtml = `<span style="color:var(--text-muted);font-size:0.75rem;">—</span>`;
      }

      return `
      <tr>
        <td><strong>${f.fee_type}</strong></td>
        <td>${f.description || '—'}</td>
        <td>GHS ${fmt(f.amount)}</td>
        <td>GHS ${fmt(f.amount_paid)}</td>
        <td style="font-weight:700; color:${f.balance > 0 ? '#e74c3c' : '#27ae60'};">
          GHS ${fmt(f.balance)}
        </td>
        <td><span class="fee-row-status ${f.status}">${f.status}</span></td>
        <td>${f.due_date ? fmtDate(f.due_date) : '—'}</td>
        <td>${actionHtml}</td>
      </tr>
    `;
    }).join('');

  } catch (err) {
    console.error('Fees error:', err);
    document.getElementById('feesBadge').textContent = 'Error';
  }
}

// ── RESULTS / PERFORMANCE ─────────────────────────────────────
async function loadResults(childId) {
  try {
    const [resResults, resSubjects] = await Promise.all([
      fetch(`${API_BASE}/results/`, { headers: getHeaders() }),
      fetch(`${API_BASE}/subjects/`, { headers: getHeaders() }),
    ]);
    const allResults = await resResults.json();
    const subjects   = await resSubjects.json();

    const subjectMap = {};
    subjects.forEach(s => { subjectMap[s.id] = s.name; });

    const childResults = allResults.filter(r => String(r.student_id) === String(childId));

    const resultsBadge = document.getElementById('resultsBadge');
    const chartEmpty   = document.getElementById('resultsChartEmpty');
    const tbody        = document.getElementById('resultsTableBody');

    if (childResults.length === 0) {
      document.getElementById('kpiAvgScore').textContent = '—';
      resultsBadge.textContent = 'No results';
      chartEmpty.style.display = 'block';
      tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;padding:24px;color:var(--text-muted);">No results recorded yet.</td></tr>';
      return;
    }

    const avgScore = childResults.reduce((s, r) => s + (r.total_score || 0), 0) / childResults.length;
    document.getElementById('kpiAvgScore').textContent = `${Math.round(avgScore)}%`;
    resultsBadge.textContent = `${childResults.length} subjects · Avg ${Math.round(avgScore)}%`;

    // Chart
    const labels = childResults.map(r => subjectMap[r.subject_id] || `Subj ${r.subject_id}`);
    const scores = childResults.map(r => r.total_score || 0);
    const colors = scores.map(s =>
      s >= 70 ? 'rgba(39,174,96,0.85)' : s >= 50 ? 'rgba(230,126,34,0.85)' : 'rgba(231,76,60,0.85)'
    );

    if (resultsChart) {
      resultsChart.destroy();
      resultsChart = null;
    }
    chartEmpty.style.display = 'none';

    // Use the existing createBarChart helper if available, otherwise fall back to simple Chart.js
    if (typeof Chart !== 'undefined') {
      const ctx = document.getElementById('resultsChart').getContext('2d');
      resultsChart = new Chart(ctx, {
        type: 'bar',
        data: {
          labels,
          datasets: [{
            label: 'Score (%)',
            data: scores,
            backgroundColor: colors,
            borderRadius: 6,
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            y: {
              beginAtZero: true, max: 100,
              grid: { color: 'rgba(128,128,128,0.1)' }
            },
            x: { grid: { display: false } }
          }
        }
      });
    } else if (typeof createBarChart === 'function') {
      createBarChart('resultsChart', labels, scores);
    }

    // Table
    tbody.innerHTML = childResults.map(r => {
      const sba = r.class_score !== undefined && r.class_score !== null ? r.class_score : '—';
      const exam = r.exam_score !== undefined && r.exam_score !== null ? r.exam_score : '—';
      const total = r.total_score !== undefined && r.total_score !== null ? r.total_score : '—';
      const grade = r.grade || '—';
      const term = r.term || '—';
      const sName = subjectMap[r.subject_id] || `Subject ${r.subject_id}`;
      return `
        <tr>
          <td><strong>${sName}</strong></td>
          <td>${sba}</td>
          <td>${exam}</td>
          <td style="font-weight:700; color:#38bdf8;">${total}</td>
          <td><span style="font-weight:700; background:rgba(99,102,241,0.15); color:#818cf8; padding:2px 8px; border-radius:6px;">${grade}</span></td>
          <td>${term}</td>
        </tr>
      `;
    }).join('');

  } catch (err) {
    console.error('Results error:', err);
    document.getElementById('resultsBadge').textContent = 'Error';
  }
}

// ── DISCIPLINE RECORDS ────────────────────────────────────────
async function loadDiscipline(childId) {
  try {
    const res  = await fetch(`${API_BASE}/discipline/student/${childId}`, { headers: getHeaders() });
    const data = await res.json();

    const feed  = document.getElementById('disciplineFeed');
    const badge = document.getElementById('disciplineBadge');

    // KPI – count incidents (not commendations)
    const incidents = data.filter(d => d.incident_type !== 'Commendation');
    const commend   = data.filter(d => d.incident_type === 'Commendation');

    document.getElementById('kpiDiscipline').textContent = incidents.length;
    document.getElementById('kpiDisciplineSub').textContent =
      `${commend.length} commendation${commend.length !== 1 ? 's' : ''}`;
    const discCard = document.getElementById('kpiDisciplineCard');
    discCard.className = `stat-card ${incidents.length === 0 ? 'success' : incidents.length <= 2 ? 'warning' : 'danger'}`;

    badge.textContent = `${data.length} record${data.length !== 1 ? 's' : ''}`;

    if (data.length === 0) {
      feed.innerHTML = `<p style="text-align:center;padding:32px;color:var(--text-muted);">🎉 No discipline records for this student.</p>`;
      return;
    }

    const typeIcon = { Warning: '⚠️', Detention: '🔒', Suspension: '🚫', Expulsion: '❌', Commendation: '🏆' };

    feed.innerHTML = data.map(d => `
      <div class="disc-item ${d.incident_type}">
        <span style="font-size:1.4rem;">${typeIcon[d.incident_type] || '📝'}</span>
        <div style="flex:1;">
          <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:4px;">
            <span class="disc-badge ${d.incident_type}">${d.incident_type}</span>
            <span style="font-size:.75rem;color:var(--text-muted);">${fmtDate(d.date_of_incident)}</span>
            ${d.parent_notified ? '<span style="font-size:.72rem;color:#27ae60;">✔ Parent notified</span>' : ''}
          </div>
          <div class="disc-desc">${d.description || '—'}</div>
          ${d.action_taken ? `<div class="disc-meta">Action: ${d.action_taken}</div>` : ''}
        </div>
      </div>
    `).join('');

  } catch (err) {
    console.error('Discipline error:', err);
    document.getElementById('disciplineBadge').textContent = 'Error';
  }
}

// ── NOTIFICATIONS ─────────────────────────────────────────────
async function loadNotifications(childId) {
  try {
    const res   = await fetch(`${API_BASE}/notifications/student/${childId}`, { headers: getHeaders() });
    const data  = await res.json();

    const feed  = document.getElementById('notifFeed');
    const badge = document.getElementById('notifBadge');
    const unread = data.filter(n => !n.is_read).length;

    badge.textContent = `${data.length} total · ${unread} unread`;

    if (data.length === 0) {
      feed.innerHTML = '<p style="text-align:center;padding:32px;color:var(--text-muted);">No notifications.</p>';
      return;
    }

    const typeIcon = {
      'Attendance': '📅',
      'Fee': '💰',
      'Discipline': '⚖️',
      'Result': '📊',
      'General': '📢',
    };

    feed.innerHTML = data.map(n => `
      <div class="notif-item ${n.is_read ? 'read' : ''}" id="notif-${n.id}">
        <span class="notif-icon">${typeIcon[n.type] || '🔔'}</span>
        <div style="flex:1;">
          <div class="notif-msg">${n.message}</div>
          <div class="notif-time">${fmtDate(n.created_at)}</div>
        </div>
        ${!n.is_read
          ? `<button class="btn" style="padding:4px 12px;font-size:.78rem;" onclick="markRead(${n.id}, '${childId}')">Mark Read</button>`
          : '<span style="font-size:.75rem;color:var(--text-muted);">Read</span>'
        }
      </div>
    `).join('');

  } catch (err) {
    console.error('Notifications error:', err);
    document.getElementById('notifBadge').textContent = 'Error';
  }
}

// ── Mark notification as read ─────────────────────────────────
async function markRead(notifId, childId) {
  try {
    await fetch(`${API_BASE}/notifications/${notifId}/read`, {
      method: 'POST', headers: getHeaders()
    });
    // Optimistically mark as read in DOM
    const el = document.getElementById(`notif-${notifId}`);
    if (el) el.classList.add('read');
    // Reload notifications tab to refresh badge
    await loadNotifications(childId || currentChildId);
  } catch (err) {
    console.error('markRead error:', err);
  }
}

// ── EXEAT & LEAVE PASSES ─────────────────────────────────────────
async function loadExeat(childId) {
  try {
    const res = await fetch(`${API_BASE}/exeat/?student_id=${childId}`, { headers: getHeaders() });
    const badge = document.getElementById('exeatBadge');
    const tbody = document.getElementById('exeatTableBody');
    if (!res.ok) {
      badge.textContent = 'Error';
      return;
    }
    const records = await res.json();

    badge.textContent = `${records.length} passes`;

    if (records.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:24px;color:var(--text-muted);">No exeat/leave passes recorded for this student.</td></tr>';
      return;
    }

    tbody.innerHTML = records.map(r => {
      let stColor = "#3b82f6";
      if (r.status === "Approved") stColor = "#22c55e";
      else if (r.status === "Departed") stColor = "#a855f7";
      else if (r.status === "Returned") stColor = "#10b981";
      else if (r.status === "Overdue") stColor = "#ef4444";
      else if (r.status === "Rejected") stColor = "#6b7280";

      return `
        <tr>
          <td><b>${r.exeat_type}</b></td>
          <td>${r.reason}</td>
          <td>${r.destination}</td>
          <td>${r.expected_departure ? r.expected_departure.replace('T', ' ').substring(0, 16) : '-'}</td>
          <td>${r.expected_return ? r.expected_return.replace('T', ' ').substring(0, 16) : '-'}</td>
          <td><span style="background:rgba(255,255,255,0.05); color:${stColor}; border:1px solid ${stColor}; padding:3px 10px; border-radius:12px; font-weight:700; font-size:0.75rem;">${r.status}</span></td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    console.error('Exeat error:', err);
    document.getElementById('exeatBadge').textContent = 'Error';
  }
}

async function loadSemesters() {
  const select = document.getElementById('reportSemesterSelect');
  if (!select) return;
  try {
    const res = await fetch(`${API_BASE}/academic/semesters`, { headers: getHeaders() });
    if (!res.ok) return;
    const sems = await res.json();
    select.innerHTML = sems.map(s => `
      <option value="${s.id}" ${s.is_current ? 'selected' : ''}>${s.name} ${s.is_current ? '(Current Term)' : ''}</option>
    `).join('');
  } catch (err) {
    console.error('Semesters load error:', err);
  }
}

function viewInteractiveReportCard() {
  if (!currentChildId) return alert("Please select a child first.");
  const semId = document.getElementById('reportSemesterSelect')?.value || 1;
  window.location.href = `report-card.html?student_id=${currentChildId}&semester_id=${semId}`;
}

// ── ONLINE FEE PAYMENT & RECEIPTS ─────────────────────────────
function selectMoMoNetwork(netName) {
  document.getElementById('payModalNetwork').value = netName;
  document.querySelectorAll('.momo-btn').forEach(btn => {
    btn.classList.toggle('active', btn.textContent.includes(netName));
  });
}

function openPayFeeModal(feeId, defaultAmount, feeType) {
  if (!currentChildId) {
    alert("Please select a child first.");
    return;
  }
  const child = allChildren.find(c => String(c.id) === String(currentChildId));
  const childName = child ? child.full_name : "Student";

  document.getElementById('payModalFeeId').value = feeId || '';
  document.getElementById('payModalStudentName').textContent = `${childName} (${child?.student_code || ''})`;
  document.getElementById('payModalFeeType').textContent = feeType ? `${feeType} Fee Bill` : "All Outstanding Fees";

  const amt = defaultAmount !== undefined ? defaultAmount : (currentChildBalance || 10.0);
  document.getElementById('payModalAmount').value = Number(amt).toFixed(2);
  document.getElementById('payModalAmount').max = Number(amt).toFixed(2);
  document.getElementById('payModalBalanceHint').textContent = `Max outstanding balance: GHS ${fmt(amt)}`;

  // Default phone number from child record if available
  const phoneInput = document.getElementById('payModalPhone');
  if (phoneInput && !phoneInput.value && child?.phone) {
    phoneInput.value = child.phone;
  }

  const statusBox = document.getElementById('payModalStatusBox');
  if (statusBox) statusBox.style.display = 'none';

  const modal = document.getElementById('modalPayFee');
  if (modal) modal.classList.add('open');
}

function closePayFeeModal() {
  const modal = document.getElementById('modalPayFee');
  if (modal) modal.classList.remove('open');
}

async function processOnlineFeePayment(event) {
  event.preventDefault();
  const feeIdVal = document.getElementById('payModalFeeId').value;
  const amount = parseFloat(document.getElementById('payModalAmount').value);
  const phone = document.getElementById('payModalPhone').value.trim();
  const network = document.getElementById('payModalNetwork').value;

  if (isNaN(amount) || amount < 1.0) {
    alert("Payment amount must be at least GHS 1.00");
    return;
  }

  // If feeId is not specified, resolve first unpaid fee for the child
  let feeId = feeIdVal ? parseInt(feeIdVal) : null;
  if (!feeId && currentChildFees.length > 0) {
    const unpaid = currentChildFees.find(f => f.balance > 0);
    if (unpaid) feeId = unpaid.id;
  }

  if (!feeId) {
    alert("No outstanding fee bill found to apply payment towards.");
    return;
  }

  const submitBtn = document.getElementById('btnSubmitPayment');
  const statusBox = document.getElementById('payModalStatusBox');
  submitBtn.disabled = true;
  submitBtn.textContent = '⏳ Processing Gateway Request…';

  statusBox.style.display = 'block';
  statusBox.style.background = 'rgba(56, 189, 248, 0.15)';
  statusBox.style.color = '#38bdf8';
  statusBox.style.border = '1px solid #0284c7';
  statusBox.innerHTML = `📡 Connecting to <strong>${network}</strong> gateway... Please check your phone for the authorization prompt.`;

  try {
    const res = await fetch(`${API_BASE}/fees/paystack/initialize`, {
      method: 'POST',
      headers: jsonHeaders(),
      body: JSON.stringify({
        fee_id: feeId,
        amount_paid: amount,
        mobile_number: phone,
        network: network
      })
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || 'Payment initialization failed.');
    }

    if (data.status === 'offline_fallback') {
      statusBox.style.background = 'rgba(234, 179, 8, 0.15)';
      statusBox.style.color = '#eab308';
      statusBox.style.border = '1px solid #ca8a04';
      statusBox.innerHTML = `⚠️ <strong>Offline Mode / Unconfigured Gateway</strong>: ${data.message}`;
      submitBtn.disabled = false;
      submitBtn.textContent = '🚀 Authorize MoMo Payment';
      return;
    }

    if (data.authorization_url && !data.authorization_url.startsWith('/paystack-callback')) {
      // Open Paystack popup/window
      statusBox.innerHTML = `✅ Payment initiated! Redirecting to Paystack secure checkout…`;
      window.open(data.authorization_url, '_blank');
    }

    // Begin automatic verification poll
    const ref = data.reference;
    statusBox.innerHTML = `⏳ <strong>Waiting for ${network} PIN approval on ${phone}…</strong><br/><small>Ref: ${ref}</small>`;

    let attempts = 0;
    const pollInterval = setInterval(async () => {
      attempts++;
      try {
        const vRes = await fetch(`${API_BASE}/fees/paystack/verify/${ref}`, { headers: getHeaders() });
        const vData = await vRes.json();
        if (vRes.ok && vData.status === 'success') {
          clearInterval(pollInterval);
          statusBox.style.background = 'rgba(34, 197, 94, 0.15)';
          statusBox.style.color = '#22c55e';
          statusBox.style.border = '1px solid #16a34a';
          statusBox.innerHTML = `
            🎉 <strong>Payment Successful!</strong> GHS ${fmt(amount)} received.<br/>
            An official SMS receipt has been sent to your phone.
            <div style="margin-top:10px;">
              <button type="button" class="fee-btn-action fee-btn-receipt" onclick="downloadPaymentReceipt(${vData.payment_id})">📥 Download Official PDF Receipt</button>
            </div>
          `;
          submitBtn.textContent = '✅ Payment Complete';
          // Reload child fees
          if (currentChildId) loadFees(currentChildId);
        } else if (attempts >= 15) {
          clearInterval(pollInterval);
          submitBtn.disabled = false;
          submitBtn.textContent = '🚀 Authorize MoMo Payment';
          statusBox.innerHTML = `⚠️ Transaction pending or timed out. If you authorized the MoMo prompt, it will reflect momentarily.`;
        }
      } catch (err) {
        if (attempts >= 15) clearInterval(pollInterval);
      }
    }, 3000);

  } catch (err) {
    submitBtn.disabled = false;
    submitBtn.textContent = '🚀 Authorize MoMo Payment';
    statusBox.style.background = 'rgba(239, 68, 68, 0.15)';
    statusBox.style.color = '#ef4444';
    statusBox.style.border = '1px solid #dc2626';
    statusBox.innerHTML = `❌ <strong>Error</strong>: ${err.message}`;
  }
}

async function downloadPaymentReceipt(paymentId) {
  if (!paymentId) return alert("Receipt ID not found.");
  try {
    const res = await fetch(`${API_BASE}/fees/receipt/${paymentId}/pdf`, {
      headers: getHeaders()
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Server returned ${res.status}`);
    }
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `Official_Fee_Receipt_${paymentId}.pdf`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
  } catch (err) {
    alert(`Could not download payment receipt: ${err.message}`);
  }
}

// ── Bootstrap ─────────────────────────────────────────────────
loadPortal();
