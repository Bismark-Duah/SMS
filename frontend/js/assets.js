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

let allStudents = [];
let allUniformItems = [];

document.addEventListener('DOMContentLoaded', () => {
  initAssetsPage();
});

async function initAssetsPage() {
  await Promise.all([
    loadStudentsList(),
    loadAssets(),
    loadTextbooks(),
    loadUniformItems(),
    loadDisbursements()
  ]);
}

function switchStoreTab(tab) {
  const paneAssets = document.getElementById('paneAssets');
  const paneTextbooks = document.getElementById('paneTextbooks');
  const paneUniforms = document.getElementById('paneUniforms');

  const btnAssets = document.getElementById('tabBtnAssets');
  const btnTextbooks = document.getElementById('tabBtnTextbooks');
  const btnUniforms = document.getElementById('tabBtnUniforms');

  [paneAssets, paneTextbooks, paneUniforms].forEach(p => p.style.display = 'none');
  [btnAssets, btnTextbooks, btnUniforms].forEach(b => b.className = 'btn sm');

  if (tab === 'assets') {
    paneAssets.style.display = 'block';
    btnAssets.className = 'btn primary sm';
  } else if (tab === 'textbooks') {
    paneTextbooks.style.display = 'block';
    btnTextbooks.className = 'btn primary sm';
  } else if (tab === 'uniforms') {
    paneUniforms.style.display = 'block';
    btnUniforms.className = 'btn primary sm';
  }
}

async function loadStudentsList() {
  try {
    const res = await fetch(`${API_BASE}/students/`, { headers: getHeaders() });
    if (res.ok) {
      allStudents = await res.json();
      const optionsHtml = '<option value="">Select Student...</option>' +
        allStudents.map(s => `<option value="${s.id}">${s.full_name} (${s.student_code})</option>`).join('');
      
      const tbSel = document.getElementById('textbookStudentSelect');
      const uniSel = document.getElementById('disburseStudentSelect');
      if (tbSel) tbSel.innerHTML = optionsHtml;
      if (uniSel) uniSel.innerHTML = optionsHtml;
    }
  } catch (err) {
    console.error('Error loading students list:', err);
  }
}

// ── 1. Assets Management ───────────────────────────────────────────────────

async function loadAssets() {
  const container = document.getElementById('assetsTableContainer');
  const category = document.getElementById('assetCategoryFilter')?.value || '';
  
  try {
    const url = category ? `${API_BASE}/assets/?category=${encodeURIComponent(category)}` : `${API_BASE}/assets/`;
    const res = await fetch(url, { headers: getHeaders() });
    if (!res.ok) throw new Error('Failed to fetch assets');
    
    const assets = await res.json();
    if (assets.length === 0) {
      container.innerHTML = '<p style="opacity:.6; font-style:italic;">No assets registered yet.</p>';
      return;
    }

    container.innerHTML = `
      <table style="width:100%; border-collapse:collapse; color:var(--text-primary);">
        <thead>
          <tr style="border-bottom:2px solid var(--border-color); text-align:left;">
            <th style="padding:8px;">Asset Name</th>
            <th style="padding:8px;">Category</th>
            <th style="padding:8px;">Tag / Serial</th>
            <th style="padding:8px;">Qty</th>
            <th style="padding:8px;">Cost (GHS)</th>
            <th style="padding:8px;">Location</th>
            <th style="padding:8px;">Status</th>
            <th style="padding:8px; text-align:center;">Action</th>
          </tr>
        </thead>
        <tbody>
          ${assets.map(a => `
            <tr style="border-bottom:1px solid var(--border-color);">
              <td style="padding:8px;"><strong>${a.name}</strong></td>
              <td style="padding:8px;"><span style="background:rgba(59,130,246,0.15); padding:2px 6px; border-radius:4px; font-size:0.8rem;">${a.category}</span></td>
              <td style="padding:8px;">${a.serial_number || '—'}</td>
              <td style="padding:8px;"><strong>${a.quantity}</strong></td>
              <td style="padding:8px;">GHS ${a.unit_cost ? a.unit_cost.toFixed(2) : '0.00'}</td>
              <td style="padding:8px;">${a.location || '—'}</td>
              <td style="padding:8px;"><span style="background:rgba(34,197,94,0.15); color:#4ade80; padding:2px 6px; border-radius:4px; font-size:0.8rem;">${a.status}</span></td>
              <td style="padding:8px; text-align:center;">
                <button class="btn danger sm" onclick="deleteAsset(${a.id})" style="padding:2px 6px; font-size:0.75rem;">🗑 Delete</button>
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    `;
  } catch (err) {
    container.innerHTML = '<p style="color:var(--danger);">Error loading assets.</p>';
  }
}

document.getElementById('assetForm')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const payload = {
    name: document.getElementById('assetName').value.trim(),
    category: document.getElementById('assetCategory').value,
    serial_number: document.getElementById('assetSerial').value.trim() || null,
    quantity: parseInt(document.getElementById('assetQuantity').value) || 1,
    unit_cost: parseFloat(document.getElementById('assetCost').value) || 0.0,
    location: document.getElementById('assetLocation').value.trim() || null,
    status: 'Good'
  };

  try {
    const res = await fetch(`${API_BASE}/assets/`, {
      method: 'POST',
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Could not register asset');
    }
    alert('Asset successfully registered.');
    document.getElementById('assetForm').reset();
    await loadAssets();
  } catch (err) {
    alert(`Error: ${err.message}`);
  }
});

async function deleteAsset(id) {
  if (!confirm('Are you sure you want to delete this asset record?')) return;
  try {
    const res = await fetch(`${API_BASE}/assets/${id}`, { method: 'DELETE', headers: getHeaders() });
    if (res.ok) await loadAssets();
  } catch (err) {
    alert('Failed to delete asset');
  }
}

// ── 2. Textbook Allocations ────────────────────────────────────────────────

async function loadTextbooks() {
  const container = document.getElementById('textbooksTableContainer');
  try {
    const res = await fetch(`${API_BASE}/assets/textbooks`, { headers: getHeaders() });
    if (!res.ok) throw new Error('Failed to fetch textbook allocations');
    
    const allocations = await res.json();
    if (allocations.length === 0) {
      container.innerHTML = '<p style="opacity:.6; font-style:italic;">No active textbook barcode allocations recorded.</p>';
      return;
    }

    container.innerHTML = `
      <table style="width:100%; border-collapse:collapse; color:var(--text-primary);">
        <thead>
          <tr style="border-bottom:2px solid var(--border-color); text-align:left;">
            <th style="padding:8px;">Barcode ID</th>
            <th style="padding:8px;">Book Title</th>
            <th style="padding:8px;">Assigned Student</th>
            <th style="padding:8px;">Issued Date</th>
            <th style="padding:8px;">Status</th>
            <th style="padding:8px; text-align:center;">Action</th>
          </tr>
        </thead>
        <tbody>
          ${allocations.map(a => `
            <tr style="border-bottom:1px solid var(--border-color);">
              <td style="padding:8px;"><strong style="font-family:monospace; color:#38bdf8;">${a.barcode_id}</strong></td>
              <td style="padding:8px;"><strong>${a.book_title}</strong></td>
              <td style="padding:8px;">${a.student_name} (${a.student_code})</td>
              <td style="padding:8px;">${a.issued_date ? a.issued_date.slice(0, 10) : '—'}</td>
              <td style="padding:8px;">
                <span style="background:${a.status==='Issued'?'rgba(234,179,8,0.2)':'rgba(34,197,94,0.2)'}; color:${a.status==='Issued'?'#fde047':'#4ade80'}; padding:2px 8px; border-radius:4px; font-size:0.8rem;">
                  ${a.status}
                </span>
              </td>
              <td style="padding:8px; text-align:center;">
                <div style="display:flex; gap:4px; justify-content:center;">
                  <button class="btn sm" onclick="printTextbookSlip('${a.barcode_id}', '${a.book_title.replace(/'/g, "\\'")}', '${a.student_name.replace(/'/g, "\\'")}', '${a.student_code}', '${a.issued_date ? a.issued_date.slice(0, 10) : ''}')" style="padding:2px 6px; font-size:0.75rem;">🖨️ Print Slip</button>
                  ${a.status === 'Issued' ? `<button class="btn sm" onclick="returnTextbook(${a.id})" style="padding:2px 6px; font-size:0.75rem; background:#10b981; color:white;">📥 Return</button>` : ''}
                </div>
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    `;
  } catch (err) {
    container.innerHTML = '<p style="color:var(--danger);">Error loading textbook allocations.</p>';
  }
}

document.getElementById('textbookForm')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const payload = {
    student_id: parseInt(document.getElementById('textbookStudentSelect').value),
    book_title: document.getElementById('textbookTitle').value.trim(),
    barcode_id: document.getElementById('textbookBarcode').value.trim(),
    expected_return_date: document.getElementById('textbookReturnDate').value || null
  };

  try {
    const res = await fetch(`${API_BASE}/assets/textbooks/issue`, {
      method: 'POST',
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Could not issue textbook');
    }
    alert('Textbook successfully issued to student.');
    document.getElementById('textbookForm').reset();
    await loadTextbooks();
  } catch (err) {
    alert(`Error: ${err.message}`);
  }
});

async function returnTextbook(id) {
  if (!confirm('Mark this textbook as returned to school store?')) return;
  try {
    const res = await fetch(`${API_BASE}/assets/textbooks/${id}/return?status=Returned`, {
      method: 'PATCH',
      headers: getHeaders()
    });
    if (res.ok) await loadTextbooks();
  } catch (err) {
    alert('Failed to process textbook return.');
  }
}

// ── 3. Uniform Inventory & Disbursement ────────────────────────────────────

async function loadUniformItems() {
  try {
    const res = await fetch(`${API_BASE}/assets/uniforms`, { headers: getHeaders() });
    if (res.ok) {
      allUniformItems = await res.json();
      const selectEl = document.getElementById('disburseItemSelect');
      if (selectEl) {
        selectEl.innerHTML = '<option value="">Select Stock Item...</option>' +
          allUniformItems.map(u => `<option value="${u.id}">${u.item_name} [Size: ${u.size || 'Std'}] (Stock: ${u.quantity_in_stock})</option>`).join('');
      }
    }
  } catch (err) {
    console.error('Error loading uniform items:', err);
  }
}

document.getElementById('uniformStockForm')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const payload = {
    item_name: document.getElementById('uniformItemName').value.trim(),
    size: document.getElementById('uniformSize').value,
    quantity_in_stock: parseInt(document.getElementById('uniformQty').value) || 0,
    unit_price: 0.0
  };

  try {
    const res = await fetch(`${API_BASE}/assets/uniforms`, {
      method: 'POST',
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error('Could not add uniform item');
    alert('Uniform stock item added.');
    document.getElementById('uniformStockForm').reset();
    await loadUniformItems();
  } catch (err) {
    alert(`Error: ${err.message}`);
  }
});

document.getElementById('uniformDisburseForm')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const payload = {
    student_id: parseInt(document.getElementById('disburseStudentSelect').value),
    item_id: parseInt(document.getElementById('disburseItemSelect').value),
    quantity: parseInt(document.getElementById('disburseQty').value) || 1
  };

  try {
    const res = await fetch(`${API_BASE}/assets/uniforms/disburse`, {
      method: 'POST',
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Disbursement failed');
    }
    alert('Uniform disbursed to student successfully.');
    document.getElementById('uniformDisburseForm').reset();
    await Promise.all([loadUniformItems(), loadDisbursements()]);
  } catch (err) {
    alert(`Error: ${err.message}`);
  }
});

async function loadDisbursements() {
  const container = document.getElementById('uniformsTableContainer');
  try {
    const res = await fetch(`${API_BASE}/assets/uniforms/disbursements`, { headers: getHeaders() });
    if (!res.ok) throw new Error('Failed to fetch uniform disbursements');
    
    const logs = await res.json();
    if (logs.length === 0) {
      container.innerHTML = '<p style="opacity:.6; font-style:italic;">No uniform disbursements logged yet.</p>';
      return;
    }

    container.innerHTML = `
      <table style="width:100%; border-collapse:collapse; color:var(--text-primary);">
        <thead>
          <tr style="border-bottom:2px solid var(--border-color); text-align:left;">
            <th style="padding:8px;">Student</th>
            <th style="padding:8px;">Item Name</th>
            <th style="padding:8px;">Size</th>
            <th style="padding:8px;">Qty</th>
            <th style="padding:8px;">Disbursed Date</th>
            <th style="padding:8px; text-align:center;">Action</th>
          </tr>
        </thead>
        <tbody>
          ${logs.map(l => `
            <tr style="border-bottom:1px solid var(--border-color);">
              <td style="padding:8px;"><strong>${l.student_name}</strong> (${l.student_code})</td>
              <td style="padding:8px;">${l.item_name}</td>
              <td style="padding:8px;"><span style="background:rgba(255,255,255,0.06); padding:2px 6px; border-radius:4px; font-size:0.8rem;">${l.size || 'Std'}</span></td>
              <td style="padding:8px;"><strong>${l.quantity}</strong></td>
              <td style="padding:8px;">${l.disbursed_date ? l.disbursed_date.slice(0, 10) : '—'}</td>
              <td style="padding:8px; text-align:center;">
                <button class="btn sm" onclick="printUniformReceipt('${l.student_name.replace(/'/g, "\\'")}', '${l.student_code}', '${l.item_name.replace(/'/g, "\\'")}', '${l.size || 'Std'}', ${l.quantity}, '${l.disbursed_date ? l.disbursed_date.slice(0, 10) : ''}')" style="padding:2px 6px; font-size:0.75rem;">🖨️ Print Receipt</button>
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    `;
  } catch (err) {
    container.innerHTML = '<p style="color:var(--danger);">Error loading disbursement log.</p>';
  }
}

function printTextbookSlip(barcode, title, studentName, studentCode, issuedDate) {
  const printArea = document.getElementById('storePrintableArea');
  const now = new Date().toLocaleDateString();

  printArea.innerHTML = `
    <div style="padding:40px; border:2px solid #0f172a; font-family:sans-serif; text-align:center; color:#0f172a; background:white; max-width:650px; margin:0 auto; border-radius:8px;">
      <h2 style="margin:0 0 4px 0; text-transform:uppercase;">STOREKEEPER TEXTBOOK ALLOCATION SLIP</h2>
      <p style="margin:0 0 20px 0; color:#475569; font-size:0.9rem;">OFFICIAL TEXTBOOK ISSUE VOUCHER</p>
      
      <div style="border:2px dashed #38bdf8; padding:16px; margin:20px 0; background:#f0f9ff;">
        <span style="font-size:0.8rem; font-weight:bold; color:#0369a1;">UNIQUE BARCODE / BOOK ID</span><br/>
        <strong style="font-size:1.6rem; font-family:monospace; color:#0284c7;">${barcode}</strong>
      </div>

      <table style="width:100%; border-collapse:collapse; margin:20px 0; font-size:0.95rem; text-align:left;">
        <tr style="border-bottom:1px solid #e2e8f0;"><td style="padding:8px; font-weight:bold;">Book Title:</td><td style="padding:8px;">${title}</td></tr>
        <tr style="border-bottom:1px solid #e2e8f0;"><td style="padding:8px; font-weight:bold;">Issued To Student:</td><td style="padding:8px;">${studentName} (${studentCode})</td></tr>
        <tr style="border-bottom:1px solid #e2e8f0;"><td style="padding:8px; font-weight:bold;">Date Issued:</td><td style="padding:8px;">${issuedDate}</td></tr>
        <tr style="border-bottom:1px solid #e2e8f0;"><td style="padding:8px; font-weight:bold;">Return Condition:</td><td style="padding:8px;">Must be returned clean and undamaged at end of term.</td></tr>
      </table>

      <div style="display:flex; justify-content:space-between; margin-top:50px; font-size:0.85rem;">
        <div>________________________<br/><b>Student Signature</b></div>
        <div>________________________<br/><b>Storekeeper Sign-off</b></div>
      </div>
      <p style="margin-top:24px; font-size:0.75rem; color:#94a3b8;">Printed Date: ${now}</p>
    </div>
  `;

  printArea.style.display = 'block';
  window.print();
  printArea.style.display = 'none';
}

function printUniformReceipt(studentName, studentCode, itemName, size, qty, disbursedDate) {
  const printArea = document.getElementById('storePrintableArea');
  const now = new Date().toLocaleDateString();

  printArea.innerHTML = `
    <div style="padding:40px; border:2px solid #0f172a; font-family:sans-serif; text-align:center; color:#0f172a; background:white; max-width:650px; margin:0 auto; border-radius:8px;">
      <h2 style="margin:0 0 4px 0; text-transform:uppercase;">UNIFORM & GEAR DISBURSEMENT VOUCHER</h2>
      <p style="margin:0 0 20px 0; color:#475569; font-size:0.9rem;">OFFICIAL STORE DISBURSEMENT RECEIPT</p>

      <table style="width:100%; border-collapse:collapse; margin:20px 0; font-size:0.95rem; text-align:left;">
        <tr style="border-bottom:1px solid #e2e8f0;"><td style="padding:8px; font-weight:bold;">Student Name:</td><td style="padding:8px;">${studentName} (${studentCode})</td></tr>
        <tr style="border-bottom:1px solid #e2e8f0;"><td style="padding:8px; font-weight:bold;">Item Issued:</td><td style="padding:8px;">${itemName}</td></tr>
        <tr style="border-bottom:1px solid #e2e8f0;"><td style="padding:8px; font-weight:bold;">Size / Quantity:</td><td style="padding:8px;">Size: ${size || 'Std'} | Quantity: ${qty}</td></tr>
        <tr style="border-bottom:1px solid #e2e8f0;"><td style="padding:8px; font-weight:bold;">Disbursement Date:</td><td style="padding:8px;">${disbursedDate}</td></tr>
      </table>

      <div style="display:flex; justify-content:space-between; margin-top:50px; font-size:0.85rem;">
        <div>________________________<br/><b>Student Receiver Signature</b></div>
        <div>________________________<br/><b>Storekeeper Sign-off</b></div>
      </div>
      <p style="margin-top:24px; font-size:0.75rem; color:#94a3b8;">Printed Date: ${now}</p>
    </div>
  `;

  printArea.style.display = 'block';
  window.print();
  printArea.style.display = 'none';
}

window.switchStoreTab = switchStoreTab;
window.loadAssets = loadAssets;
window.deleteAsset = deleteAsset;
window.returnTextbook = returnTextbook;
window.printTextbookSlip = printTextbookSlip;
window.printUniformReceipt = printUniformReceipt;

