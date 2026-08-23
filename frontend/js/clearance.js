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

let allClearanceRecords = [];

document.addEventListener('DOMContentLoaded', () => {
  loadClearanceList();
});

async function loadClearanceList() {
  const tbody = document.getElementById('clearanceTableBody');
  try {
    const res = await fetch(`${API_BASE}/clearance/final-year-students`, { headers: getHeaders() });
    if (!res.ok) throw new Error('Failed to load clearance list');
    
    allClearanceRecords = await res.json();
    renderTable(allClearanceRecords);
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; padding:30px; color:var(--danger);">Error loading final year clearance matrix.</td></tr>`;
  }
}

function renderTable(records) {
  const tbody = document.getElementById('clearanceTableBody');
  if (records.length === 0) {
    tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; padding:30px; opacity:0.6;">No final year students found.</td></tr>`;
    return;
  }

  tbody.innerHTML = records.map(r => {
    const storeBadge = r.storekeeper_cleared ? `<span class="badge-clearance badge-ok">✓ Cleared</span>` : `<span class="badge-clearance badge-hold">⚠ Hold</span>`;
    const bursarBadge = r.bursar_cleared ? `<span class="badge-clearance badge-ok">✓ Cleared</span>` : `<span class="badge-clearance badge-hold">⚠ Hold</span>`;
    const houseBadge = r.housemaster_cleared ? `<span class="badge-clearance badge-ok">✓ Cleared</span>` : `<span class="badge-clearance badge-hold">⚠ Hold</span>`;
    const headBadge = r.headmaster_cleared ? `<span class="badge-clearance badge-ok">✓ Cleared</span>` : `<span class="badge-clearance badge-pending">Pending</span>`;
    
    const isFullyCleared = r.status === 'Fully Cleared';
    const overallBadge = isFullyCleared ? `<span class="badge-clearance badge-ok">🎓 FULLY CLEARED</span>` : `<span class="badge-clearance badge-pending">PENDING</span>`;

    return `
      <tr style="border-bottom:1px solid var(--border-color);">
        <td style="padding:10px;"><strong>${r.full_name}</strong><br/><small style="opacity:0.7;">${r.student_code}</small></td>
        <td style="padding:10px;">${r.class_name}</td>
        <td style="padding:10px;">${r.house_name}</td>
        <td style="padding:10px; text-align:center;">${storeBadge}</td>
        <td style="padding:10px; text-align:center;">${bursarBadge}</td>
        <td style="padding:10px; text-align:center;">${houseBadge}</td>
        <td style="padding:10px; text-align:center;">${headBadge}</td>
        <td style="padding:10px; text-align:center;">${overallBadge}</td>
        <td style="padding:10px; text-align:right;">
          <button class="btn sm primary" onclick="openClearanceModal(${r.student_id})" style="padding:4px 10px; font-size:0.8rem;">📋 Sign-off / Inspect</button>
        </td>
      </tr>
    `;
  }).join('');
}

function filterTable() {
  const query = document.getElementById('clearanceSearchInput').value.toLowerCase().trim();
  const statusFilter = document.getElementById('clearanceFilterStatus').value;

  const filtered = allClearanceRecords.filter(r => {
    const matchesSearch = !query || r.full_name.toLowerCase().includes(query) || r.student_code.toLowerCase().includes(query) || r.class_name.toLowerCase().includes(query);
    const matchesStatus = !statusFilter || r.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  renderTable(filtered);
}

async function openClearanceModal(studentId) {
  const modal = document.getElementById('clearanceModal');
  const titleEl = document.getElementById('modalStudentTitle');
  const container = document.getElementById('modalContentContainer');

  modal.style.display = 'flex';
  container.innerHTML = '<p style="opacity:0.6; padding:20px; text-align:center;">Fetching student live clearance metrics...</p>';

  try {
    const res = await fetch(`${API_BASE}/clearance/status/${studentId}`, { headers: getHeaders() });
    if (!res.ok) throw new Error('Could not fetch student clearance status');
    
    const data = await res.json();
    titleEl.innerText = `🎓 Graduation Clearance: ${data.full_name} (${data.student_code})`;

    const m = data.live_metrics;
    const r = data.record;

    const unreturnedHtml = m.unreturned_books.length > 0
      ? `<ul style="margin:4px 0 0 15px; color:#f87171; font-size:0.85rem;">${m.unreturned_books.map(b => `<li>${b.title} [Barcode: ${b.barcode}]</li>`).join('')}</ul>`
      : `<span style="color:#4ade80; font-size:0.85rem;">All issued textbooks returned.</span>`;

    const feeHtml = m.outstanding_balance > 0
      ? `<span style="color:#f87171; font-weight:bold; font-size:0.9rem;">Outstanding Balance: GHS ${m.outstanding_balance.toFixed(2)}</span>`
      : `<span style="color:#4ade80; font-weight:bold; font-size:0.9rem;">Zero Arrears (Paid in Full)</span>`;

    container.innerHTML = `
      <div style="display:flex; flex-direction:column; gap:16px; margin-top:12px;">
        <!-- Live Audit Box -->
        <div style="background:rgba(255,255,255,0.03); border:1px solid var(--border-color); padding:14px; border-radius:8px;">
          <h4 style="margin:0 0 10px 0; color:#818cf8;">🔍 Live Audit Checks</h4>
          
          <div style="display:flex; flex-direction:column; gap:10px; font-size:0.9rem;">
            <div>
              <strong>1. Storekeeper Inventory:</strong> ${unreturnedHtml}
            </div>
            <div>
              <strong>2. Bursar Fee Account:</strong> ${feeHtml}
            </div>
            <div>
              <strong>3. Housemaster & Discipline:</strong> ${m.open_discipline_issues > 0 ? `<span style="color:#f87171;">${m.open_discipline_issues} open discipline issue(s)</span>` : `<span style="color:#4ade80;">Discipline record clear.</span>`}
            </div>
          </div>
        </div>

        <!-- Departmental Sign-off Buttons -->
        <div style="background:rgba(255,255,255,0.03); border:1px solid var(--border-color); padding:14px; border-radius:8px;">
          <h4 style="margin:0 0 10px 0;">✍️ Departmental Sign-offs</h4>
          
          <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px;">
            <button class="btn sm" style="background:${r.storekeeper_cleared?'#059669':'#d97706'}; color:white;" onclick="signOffDept(${studentId}, 'storekeeper')">
              ${r.storekeeper_cleared ? '✓ Storekeeper Signed' : 'Sign-off Storekeeper'}
            </button>

            <button class="btn sm" style="background:${r.bursar_cleared?'#059669':'#d97706'}; color:white;" onclick="signOffDept(${studentId}, 'bursar')">
              ${r.bursar_cleared ? '✓ Bursar Signed' : 'Sign-off Bursar'}
            </button>

            <button class="btn sm" style="background:${r.housemaster_cleared?'#059669':'#d97706'}; color:white;" onclick="signOffDept(${studentId}, 'housemaster')">
              ${r.housemaster_cleared ? '✓ Housemaster Signed' : 'Sign-off Housemaster'}
            </button>

            <button class="btn sm" style="background:${r.headmaster_cleared?'#059669':'#d97706'}; color:white;" onclick="signOffDept(${studentId}, 'headmaster')">
              ${r.headmaster_cleared ? '✓ Headmaster Signed' : 'Sign-off Headmaster'}
            </button>
          </div>
        </div>

        ${r.status === 'Fully Cleared' ? `
          <div style="text-align:center; margin-top:10px;">
            <button class="btn primary" onclick="printClearanceCertificate('${data.full_name}', '${data.student_code}', '${data.class_name}', '${data.house_name}')">
              📜 Print Official Clearance Certificate
            </button>
          </div>
        ` : ''}
      </div>
    `;

  } catch (err) {
    container.innerHTML = '<p style="color:var(--danger);">Error loading student clearance audit.</p>';
  }
}

async function signOffDept(studentId, department) {
  const notes = prompt(`Enter optional sign-off remarks for ${department.toUpperCase()}:`, "Cleared for graduation");
  if (notes === null) return;

  try {
    const res = await fetch(`${API_BASE}/clearance/sign-off`, {
      method: 'POST',
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ student_id: studentId, department, notes })
    });
    if (!res.ok) throw new Error('Sign-off failed');

    alert(`${department.toUpperCase()} clearance sign-off recorded!`);
    await openClearanceModal(studentId);
    await loadClearanceList();
  } catch (err) {
    alert('Error recording sign-off.');
  }
}

function closeClearanceModal() {
  document.getElementById('clearanceModal').style.display = 'none';
}

function printClearanceCertificate(name, code, className, houseName) {
  const printArea = document.getElementById('printableCertificateArea');
  const now = new Date().toLocaleDateString();

  printArea.innerHTML = `
    <div style="padding:40px; border:8px double #1e293b; font-family:serif; text-align:center; color:#0f172a; background:white; max-width:800px; margin:0 auto;">
      <h1 style="font-size:2rem; margin:0 0 6px 0; text-transform:uppercase;">Official SHS Completion Clearance Certificate</h1>
      <h3 style="font-size:1.1rem; color:#475569; margin:0 0 20px 0;">SENIOR HIGH SCHOOL GRADUATION CLEARANCE</h3>
      
      <p style="font-size:1rem; line-height:1.8; margin:30px 0;">
        This is to certify that student <strong>${name}</strong> (Index/Code: <strong>${code}</strong>) 
        of Class <strong>${className}</strong> and House <strong>${houseName}</strong> 
        has successfully completed all departmental clearance requirements.
      </p>

      <table style="width:100%; border-collapse:collapse; margin:40px 0; font-family:sans-serif; text-align:left;">
        <tr style="border-bottom:1px solid #cbd5e1;"><td style="padding:10px;"><b>Storekeeper Clearance:</b></td><td style="padding:10px; color:#15803d;">✓ CLEARED (All Textbooks & Assets Accounted)</td></tr>
        <tr style="border-bottom:1px solid #cbd5e1;"><td style="padding:10px;"><b>Bursar Clearance:</b></td><td style="padding:10px; color:#15803d;">✓ CLEARED (Zero Fee Arrears)</td></tr>
        <tr style="border-bottom:1px solid #cbd5e1;"><td style="padding:10px;"><b>House Master Clearance:</b></td><td style="padding:10px; color:#15803d;">✓ CLEARED (Dorm Property & Discipline Clear)</td></tr>
        <tr style="border-bottom:1px solid #cbd5e1;"><td style="padding:10px;"><b>Headmaster Sign-off:</b></td><td style="padding:10px; color:#15803d;">✓ APPROVED FOR WASSCE & TRANSCRIPT RELEASE</td></tr>
      </table>

      <div style="display:flex; justify-content:space-between; margin-top:60px; font-family:sans-serif; font-size:0.9rem;">
        <div>________________________<br/><b>Bursar / Accountant</b></div>
        <div>________________________<br/><b>Senior Housemaster</b></div>
        <div>________________________<br/><b>Headmaster / Principal</b></div>
      </div>
      <p style="margin-top:30px; font-size:0.8rem; color:#64748b;">Date Issued: ${now}</p>
    </div>
  `;

  printArea.style.display = 'block';
  window.print();
  printArea.style.display = 'none';
}

window.loadClearanceList = loadClearanceList;
window.filterTable = filterTable;
window.openClearanceModal = openClearanceModal;
window.closeClearanceModal = closeClearanceModal;
window.signOffDept = signOffDept;
window.printClearanceCertificate = printClearanceCertificate;
