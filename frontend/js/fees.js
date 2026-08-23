// ── Config & Auth ────────────────────────────────────────────────────────────
const API_BASE = window.API_BASE || (window.location.origin.includes('http') ? (window.location.origin + '/api') : 'http://127.0.0.1:8000/api');
const token = localStorage.getItem('accessToken');
if (!token) window.location.href = 'auth.html';

function H(extra = {}) {
  return { 'Authorization': `Bearer ${token}`, ...extra };
}
function J(extra = {}) {
  return H({ 'Content-Type': 'application/json', ...extra });
}

// ── State ────────────────────────────────────────────────────────────────────
let allFees = [];
let allStudents = [];
let allClasses = [];
let currentFeeId = null;

// ── Init ─────────────────────────────────────────────────────────────────────
async function init() {
  // Set today as default payment date
  document.getElementById('payDate').value = todayISO();
  const mode = localStorage.getItem('school_mode') || 'COMBINED';
  if (mode === 'BASIC_ONLY') {
    const sTermEl = document.getElementById('sTerm');
    const bTermEl = document.getElementById('bTerm');
    if (sTermEl) sTermEl.placeholder = 'e.g. First Term';
    if (bTermEl) bTermEl.placeholder = 'e.g. First Term';
  }
  await Promise.all([loadStudents(), loadClasses()]);
  await Promise.all([loadSummary(), loadFees()]);
}

// ── Data loaders ─────────────────────────────────────────────────────────────
async function loadStudents() {
  const res = await fetch(`${API_BASE}/students/`, { headers: H() });
  if (!res.ok) return;
  allStudents = await res.json();

  const opts = '<option value="">Select student...</option>' +
    allStudents.map(s => `<option value="${s.id}">${escHtml(s.full_name)} (${s.student_code})</option>`).join('');
  document.getElementById('sStudentId').innerHTML = opts;
}

async function loadClasses() {
  const res = await fetch(`${API_BASE}/classes/`, { headers: H() });
  if (!res.ok) return;
  allClasses = await res.json();

  const opts = '<option value="">All Classes</option>' +
    allClasses.map(c => `<option value="${c.id}">${escHtml(c.name)}</option>`).join('');
  document.getElementById('filterClass').innerHTML = opts;

  const bOpts = '<option value="">Select class...</option>' +
    allClasses.map(c => `<option value="${c.id}">${escHtml(c.name)}</option>`).join('');
  document.getElementById('bClassId').innerHTML = bOpts;
}

async function loadSummary() {
  try {
    const res = await fetch(`${API_BASE}/fees/summary`, { headers: H() });
    if (!res.ok) return;
    const d = await res.json();
    document.getElementById('sTotalBilled').textContent  = `GHS ${fmt(d.total_billed)}`;
    document.getElementById('sTotalPaid').textContent    = `GHS ${fmt(d.total_paid)}`;
    document.getElementById('sTotalBalance').textContent = `GHS ${fmt(d.total_balance)}`;
    document.getElementById('sOverdue').textContent      = d.count_overdue;
    document.getElementById('sPaid').textContent         = d.count_paid;
    document.getElementById('sPending').textContent      = d.count_pending;
  } catch (e) { console.error(e); }
}

async function loadFees() {
  document.getElementById('feesBody').innerHTML = '<tr><td colspan="9" class="empty-state">Loading fees...</td></tr>';
  try {
    const res = await fetch(`${API_BASE}/fees/`, { headers: H() });
    if (!res.ok) {
      document.getElementById('feesBody').innerHTML = '<tr><td colspan="9" class="empty-state">Failed to load fees.</td></tr>';
      return;
    }
    allFees = await res.json();
    applyFilter();
  } catch (e) {
    document.getElementById('feesBody').innerHTML = '<tr><td colspan="9" class="empty-state">Network error loading fees.</td></tr>';
  }
}

// ── Filter & Render Table ─────────────────────────────────────────────────────
window.applyFilter = function() {
  const statusF  = document.getElementById('filterStatus').value;
  const typeF    = document.getElementById('filterType').value;
  const classF   = document.getElementById('filterClass').value;
  const searchF  = document.getElementById('filterSearch').value.toLowerCase();

  let filtered = allFees.filter(f => {
    if (statusF && f.status !== statusF) return false;
    if (typeF && f.fee_type !== typeF) return false;
    if (classF) {
      const s = allStudents.find(st => st.id === f.student_id);
      if (!s || String(s.class_section_id) !== classF) return false;
    }
    if (searchF) {
      const name = (f.student_name || '').toLowerCase();
      const code = (f.student_code || '').toLowerCase();
      if (!name.includes(searchF) && !code.includes(searchF)) return false;
    }
    return true;
  });

  window.currentFilteredFees = filtered;
  renderTable(filtered);
  document.getElementById('tableCount').textContent =
    `Showing ${filtered.length} of ${allFees.length} records`;
};

window.exportFeesCSV = function() {
  const list = window.currentFilteredFees || allFees;
  if (!list || list.length === 0) {
    if (window.showToast) window.showToast('No fee records to export.', 'warning');
    return;
  }

  const headers = ["Student Code", "Student Name", "Class", "Fee Type", "Academic Year", "Term", "Amount Billed (GHS)", "Amount Paid (GHS)", "Balance (GHS)", "Due Date", "Status"];

  const rows = list.map(f => [
    `"${(f.student_code || '').replace(/"/g, '""')}"`,
    `"${(f.student_name || '').replace(/"/g, '""')}"`,
    `"${(f.class_name || '').replace(/"/g, '""')}"`,
    `"${(f.fee_type || '').replace(/"/g, '""')}"`,
    `"${(f.academic_year || '').replace(/"/g, '""')}"`,
    `"${(f.term || '').replace(/"/g, '""')}"`,
    `"${f.amount || 0}"`,
    `"${f.amount_paid || 0}"`,
    `"${f.balance || 0}"`,
    `"${f.due_date ? f.due_date.slice(0,10) : ''}"`,
    `"${f.status || ''}"`
  ]);

  const csvContent = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);

  const link = document.createElement('a');
  link.setAttribute('href', url);
  const dateStr = new Date().toISOString().slice(0, 10);
  link.setAttribute('download', `Fee_Statements_Export_${dateStr}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);

  if (window.showToast) window.showToast('📊 Fee Statements exported to CSV!', 'success');
};


function renderTable(fees) {
  const tbody = document.getElementById('feesBody');
  if (!fees.length) {
    tbody.innerHTML = '<tr><td colspan="9" class="empty-state">No fees match your filters.</td></tr>';
    return;
  }

  tbody.innerHTML = fees.map(f => {
    const pct = f.amount > 0 ? Math.min(100, (f.amount_paid / f.amount) * 100) : 0;
    const statusBadge = `<span class="badge badge-${f.status.toLowerCase()}">${f.status}</span>`;
    const due = f.due_date ? new Date(f.due_date).toLocaleDateString() : '—';
    return `
      <tr>
        <td>
          <div style="font-weight:500;">${escHtml(f.student_name || '—')}</div>
          <div style="font-size:0.75rem;color:var(--text-secondary);">${escHtml(f.student_code || '')}</div>
        </td>
        <td style="color:var(--text-secondary);">${escHtml(f.class_name || '—')}</td>
        <td>${escHtml(f.fee_type)}</td>
        <td style="font-weight:600;">GHS ${fmt(f.amount)}</td>
        <td style="color:var(--success);">GHS ${fmt(f.amount_paid)}</td>
        <td style="color:${f.balance > 0 ? 'var(--warning)' : 'var(--success)'};">GHS ${fmt(f.balance)}</td>
        <td style="color:var(--text-secondary);">${due}</td>
        <td>${statusBadge}</td>
        <td>
          ${f.status !== 'Paid' && f.status !== 'Waived'
            ? `<button class="tbl-btn pay" onclick="openPayModal(${f.id})">Pay</button>`
            : ''}
          <button class="tbl-btn del" onclick="deleteFee(${f.id})">Del</button>
        </td>
      </tr>`;
  }).join('');
}

// ── Compose Panel Toggle ──────────────────────────────────────────────────────
window.switchCompose = function(mode) {
  document.getElementById('tabSingle').classList.toggle('active', mode === 'single');
  document.getElementById('tabBulk').classList.toggle('active', mode === 'bulk');
  document.getElementById('formSingle').style.display = mode === 'single' ? 'block' : 'none';
  document.getElementById('formBulk').style.display   = mode === 'bulk'   ? 'block' : 'none';
};

// ── Create Single Fee ─────────────────────────────────────────────────────────
window.createSingleFee = async function() {
  const studentId = document.getElementById('sStudentId').value;
  const feeType   = document.getElementById('sFeeType').value;
  const amount    = parseFloat(document.getElementById('sAmount').value);
  const acYear    = document.getElementById('sAcYear').value.trim();
  const term      = document.getElementById('sTerm').value.trim();
  const dueDate   = document.getElementById('sDueDate').value;
  const desc      = document.getElementById('sDesc').value.trim();

  if (!studentId || !amount || amount <= 0) {
    showStatus('singleStatus', '⚠️ Please select a student and enter a valid amount.', 'warning');
    return;
  }

  const payload = {
    student_id: parseInt(studentId), fee_type: feeType, amount,
    academic_year: acYear || null, term: term || null,
    due_date: dueDate ? new Date(dueDate).toISOString() : null,
    description: desc || null
  };

  try {
    const res = await fetch(`${API_BASE}/fees/`, { method: 'POST', headers: J(), body: JSON.stringify(payload) });
    if (res.ok || res.status === 201) {
      showStatus('singleStatus', '✅ Fee assigned successfully!', 'success');
      document.getElementById('sAmount').value = '';
      document.getElementById('sDesc').value = '';
      await Promise.all([loadSummary(), loadFees()]);
    } else {
      const err = await res.json();
      showStatus('singleStatus', `❌ ${err.detail || 'Failed to assign fee.'}`, 'danger');
    }
  } catch (e) {
    showStatus('singleStatus', '❌ Network error.', 'danger');
  }
};

// ── Create Bulk Fee ───────────────────────────────────────────────────────────
window.createBulkFee = async function() {
  const classId = document.getElementById('bClassId').value;
  const feeType = document.getElementById('bFeeType').value;
  const amount  = parseFloat(document.getElementById('bAmount').value);
  const acYear  = document.getElementById('bAcYear').value.trim();
  const term    = document.getElementById('bTerm').value.trim();
  const dueDate = document.getElementById('bDueDate').value;
  const desc    = document.getElementById('bDesc').value.trim();

  if (!classId || !amount || amount <= 0) {
    showStatus('bulkStatus', '⚠️ Please select a class and enter a valid amount.', 'warning');
    return;
  }

  const className = allClasses.find(c => String(c.id) === classId)?.name || '';
  if (!confirm(`Assign ${feeType} fee of GHS ${amount.toLocaleString('en-GH', {minimumFractionDigits:2})} to all active students in ${className}?`)) return;

  const payload = {
    class_section_id: parseInt(classId), fee_type: feeType, amount,
    academic_year: acYear || null, term: term || null,
    due_date: dueDate ? new Date(dueDate).toISOString() : null,
    description: desc || null
  };

  try {
    const res = await fetch(`${API_BASE}/fees/bulk`, { method: 'POST', headers: J(), body: JSON.stringify(payload) });
    if (res.ok || res.status === 201) {
      const data = await res.json();
      showStatus('bulkStatus', `✅ Fee assigned to ${data.count} student(s)!`, 'success');
      document.getElementById('bAmount').value = '';
      document.getElementById('bDesc').value = '';
      await Promise.all([loadSummary(), loadFees()]);
    } else {
      const err = await res.json();
      showStatus('bulkStatus', `❌ ${err.detail || 'Failed.'}`, 'danger');
    }
  } catch (e) {
    showStatus('bulkStatus', '❌ Network error.', 'danger');
  }
};

// ── Payment Modal ─────────────────────────────────────────────────────────────
window.openPayModal = function(feeId) {
  currentFeeId = feeId;
  const fee = allFees.find(f => f.id === feeId);
  if (!fee) return;

  const balance = fee.balance;
  document.getElementById('payFeeInfo').innerHTML = `
    <div style="font-weight:600;margin-bottom:6px;">${escHtml(fee.student_name)} — ${escHtml(fee.fee_type)}</div>
    <div style="color:var(--text-secondary);">${fee.academic_year || ''} ${fee.term || ''}</div>
    <div class="progress-bar-wrap" style="margin-top:10px;">
      <div class="progress-bar" style="width:${fee.amount > 0 ? Math.min(100,(fee.amount_paid/fee.amount)*100) : 0}%;"></div>
    </div>
    <div style="display:flex;justify-content:space-between;font-size:0.8rem;margin-top:4px;">
      <span>Paid: <strong style="color:var(--success);">GHS ${fmt(fee.amount_paid)}</strong></span>
      <span>Balance: <strong style="color:var(--warning);">GHS ${fmt(balance)}</strong></span>
      <span>Total: <strong>GHS ${fmt(fee.amount)}</strong></span>
    </div>`;

  document.getElementById('payAmount').value = balance.toFixed(2);
  document.getElementById('payAmount').max   = balance;
  document.getElementById('payRef').value    = '';
  document.getElementById('payNotes').value  = '';
  document.getElementById('payStatus').textContent = '';

  // Payment history
  if (fee.payments && fee.payments.length > 0) {
    document.getElementById('payHistorySection').style.display = 'block';
    document.getElementById('payHistoryList').innerHTML = fee.payments.map(p => `
      <div class="payment-item">
        <div>
          <div class="p-amount">GHS ${fmt(p.amount_paid)}</div>
          <div class="p-meta">${p.payment_method} ${p.reference_no ? '· Ref: ' + p.reference_no : ''}</div>
        </div>
        <div class="p-meta">${new Date(p.payment_date).toLocaleDateString()}</div>
      </div>`).join('');
  } else {
    document.getElementById('payHistorySection').style.display = 'none';
  }

  document.getElementById('payModal').classList.add('open');
};

window.closePayModal = function() {
  document.getElementById('payModal').classList.remove('open');
  currentFeeId = null;
};

// Close modal on backdrop click
document.getElementById('payModal').addEventListener('click', (e) => {
  if (e.target === e.currentTarget) closePayModal();
});

window.submitPayment = async function() {
  if (!currentFeeId) return;
  const amount     = parseFloat(document.getElementById('payAmount').value);
  const method     = document.getElementById('payMethod').value;
  const date       = document.getElementById('payDate').value;
  const reference  = document.getElementById('payRef').value.trim();
  const notes      = document.getElementById('payNotes').value.trim();

  if (!amount || amount <= 0) {
    showStatus('payStatus', '⚠️ Enter a valid payment amount.', 'warning');
    return;
  }

  const payload = {
    amount_paid: amount,
    payment_method: method,
    payment_date: date ? new Date(date).toISOString() : null,
    reference_no: reference || null,
    notes: notes || null
  };

  try {
    const res = await fetch(`${API_BASE}/fees/${currentFeeId}/payments`, {
      method: 'POST', headers: J(), body: JSON.stringify(payload)
    });
    if (res.ok || res.status === 201) {
      showStatus('payStatus', '✅ Payment recorded!', 'success');
      setTimeout(() => { closePayModal(); }, 900);
      await Promise.all([loadSummary(), loadFees()]);
    } else {
      const err = await res.json();
      showStatus('payStatus', `❌ Payment failed: ${err.detail || 'Unknown error'}`, 'error');
    }
  } catch (e) {
    showStatus('payStatus', '❌ Network error processing payment.', 'error');
  }
};

window.payOnlineWithPaystack = async function() {
  if (!currentFeeId) return;
  const amount = parseFloat(document.getElementById('payAmount').value);
  const method = document.getElementById('payMethod').value;

  if (!amount || amount <= 0) {
    showStatus('payStatus', '⚠️ Enter a valid payment amount.', 'warning');
    return;
  }

  showStatus('payStatus', '⌛ Connecting to Paystack MoMo Gateway...', 'info');

  const payload = {
    fee_id: currentFeeId,
    amount_paid: amount,
    network: method
  };

  try {
    const res = await fetch(`${API_BASE}/fees/paystack/initialize`, {
      method: 'POST',
      headers: J(),
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (res.ok) {
      if (data.status === 'success' && data.authorization_url) {
        showStatus('payStatus', '✅ Opening Paystack Gateway... Redirecting...', 'success');
        window.open(data.authorization_url, '_blank');
      } else {
        const fallbackMsg = `ℹ️ ${data.message || 'Paystack is unconfigured or server is offline.'}`;
        showStatus('payStatus', fallbackMsg, 'warning');
      }
    } else {
      showStatus('payStatus', `❌ Paystack Error: ${data.detail || 'Initialization failed'}`, 'error');
    }
  } catch (e) {
    showStatus('payStatus', `ℹ️ Server is operating in 100% Offline Mode. Click 'Submit Offline Payment' to record locally.`, 'warning');
  }
};

// ── Delete Fee ────────────────────────────────────────────────────────────────
window.deleteFee = async function(feeId) {
  const fee = allFees.find(f => f.id === feeId);
  if (!fee) return;
  if (!confirm(`Delete ${fee.fee_type} fee of GHS ${fmt(fee.amount)} for ${fee.student_name}? This cannot be undone.`)) return;

  try {
    const res = await fetch(`${API_BASE}/fees/${feeId}`, { method: 'DELETE', headers: H() });
    if (res.ok || res.status === 204) {
      allFees = allFees.filter(f => f.id !== feeId);
      applyFilter();
      await loadSummary();
    }
  } catch (e) { console.error(e); }
};

// ── Utilities ─────────────────────────────────────────────────────────────────
function fmt(val) {
  if (val == null) return '0.00';
  return Number(val).toLocaleString('en-GH', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function todayISO() {
  return new Date().toISOString().split('T')[0];
}

function escHtml(str) {
  if (!str) return '';
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function showStatus(elId, msg, type = 'info') {
  const el = document.getElementById(elId);
  if (!el) return;
  const colors = { success: 'var(--success)', danger: 'var(--danger)', warning: 'var(--warning)', info: 'var(--text-secondary)' };
  el.style.color = colors[type] || 'var(--text-secondary)';
  el.textContent = msg;
  setTimeout(() => { el.textContent = ''; }, 5000);
}

// ── Bootstrap ─────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', init);

window.broadcastFeeReminders = async function() {
  const debtors = allInvoices.filter(i => (i.balance || 0) > 0);
  if (debtors.length === 0) {
    alert('✔ No students currently have outstanding fee balances!');
    return;
  }

  if (!confirm(`Are you sure you want to send automated Fee Reminder notices to the guardians of ${debtors.length} debtor student(s)?`)) return;

  let successCount = 0;
  for (const inv of debtors) {
    const messagePayload = {
      recipient: inv.student_name || `Student #${inv.student_id}`,
      phone: inv.guardian_phone || '+233 24 000 0000',
      message: `Dear Guardian, outstanding fee balance for ${inv.student_name} (${inv.student_code}) is GH₵ ${inv.balance.toFixed(2)}. Kindly settle before end of term. Thank you.`,
      channel: 'SMS',
      status: 'SENT'
    };
    try {
      await fetch(`${API_BASE}/messaging/send`, {
        method: 'POST',
        headers: getHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(messagePayload)
      });
      successCount++;
    } catch (_) {}
  }

  alert(`✔ Successfully broadcast fee reminders to ${successCount} guardian phone number(s)!`);
};
