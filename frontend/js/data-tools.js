var API_BASE = window.API_BASE || (window.location.origin.includes('http') ? (window.location.origin + '/api') : 'http://127.0.0.1:8000/api');

var token = localStorage.getItem('accessToken');
if (!token && !window.location.pathname.includes('auth.html')) {
  window.location.href = 'auth.html';
}

function getHeaders(headers = {}) {
  const h = { ...headers };
  const t = localStorage.getItem('accessToken');
  if (t) h['Authorization'] = `Bearer ${t}`;
  return h;
}

window.triggerBlobDownload = function(blobOrContent, filename, mimeType = 'text/csv;charset=utf-8;') {
  try {
    const blob = (blobOrContent instanceof Blob) ? blobOrContent : new Blob([blobOrContent], { type: mimeType });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.style.display = 'none';
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => {
      if (document.body.contains(a)) document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    }, 250);
  } catch (err) {
    console.error('Download error:', err);
    alert('Download failed: ' + (err.message || err));
  }
};

// ── CSSPS CSV Template & Import ──────────────────────────────────────────────
window.downloadCSSPSCSVTemplate = function() {
  const headers = [
    'bece_index_number',
    'enrolment_code',
    'first_name',
    'middle_name',
    'last_name',
    'gender',
    'date_of_birth',
    'bece_raw_score',
    'bece_aggregate',
    'jhs_attended',
    'program_name',
    'residential_status',
    'guardian_name',
    'primary_phone',
    'alternative_phone',
    'address'
  ];

  const csvContent = headers.join(',') + '\n';
  window.triggerBlobDownload(csvContent, 'CSSPS_Official_Placement_Template.csv');
};

window.triggerCSSPSCSVUpload = function() {
  const input = document.getElementById('csspsCsvFileInput');
  if (input) input.click();
};

// ── Basic School Students CSV Template & Direct Instant Enrollment ─────────
window.downloadBasicStudentsTemplate = function() {
  const headers = [
    'full_name',
    'student_code',
    'class_name',
    'gender',
    'date_of_birth',
    'guardian_name',
    'phone',
    'alternative_phone',
    'address',
    'blood_group',
    'allergies'
  ];

  const csvContent = headers.join(',') + '\n';
  window.triggerBlobDownload(csvContent, 'Basic_School_Students_Enrollment_Template.csv');
};

window.triggerBasicStudentsCSVUpload = function() {
  const input = document.getElementById('basicStudentsCsvFileInput');
  if (input) input.click();
};

window.handleBasicStudentsCSVSelected = function(event) {
  handleContinuingStudentsCSVSelected(event);
};

// ── Continuing Students CSV Template & Direct Instant Enrollment ───────────
window.downloadContinuingStudentsTemplate = function() {
  const headers = [
    'full_name',
    'student_code',
    'form',
    'class_name',
    'program_name',
    'gender',
    'residential_status',
    'house_name',
    'dormitory_name',
    'guardian_name',
    'phone',
    'address'
  ];

  const csvContent = headers.join(',') + '\n';
  window.triggerBlobDownload(csvContent, 'Continuing_Students_Direct_Enrollment_Template.csv');
};

window.triggerContinuingStudentsCSVUpload = function() {
  const input = document.getElementById('continuingStudentsCsvFileInput');
  if (input) input.click();
};

window.handleContinuingStudentsCSVSelected = async function(event) {
  const file = event.target.files && event.target.files[0];
  if (!file) return;

  const formData = new FormData();
  formData.append('file', file);

  if (window.showToast) window.showToast('Enrolling continuing students into active classes...', 'info');

  try {
    const res = await fetch(`${API_BASE}/students/import-csv`, {
      method: 'POST',
      headers: getHeaders(),
      body: formData
    });

    let data;
    try {
      data = await res.json();
    } catch (parseErr) {
      const textErr = await res.text().catch(() => '');
      throw new Error(`Server returned ${res.status}: ${textErr || res.statusText}`);
    }

    if (res.ok && data.status !== 'error') {
      if (window.showCSSPSImportResultsModal) {
        window.showCSSPSImportResultsModal({
          imported: data.imported,
          skipped: data.skipped || 0,
          errors: data.errors || []
        });
      } else {
        let msg = `✔ Successfully enrolled ${data.imported} continuing students!`;
        if (data.skipped > 0) msg += ` (${data.skipped} skipped/already existing)`;
        if (window.showToast) window.showToast(msg, data.imported > 0 ? 'success' : 'warning');
      }

      if (window.loadStudents) window.loadStudents();
    } else {
      let errMsg = 'Continuing student import failed';
      if (data.errors && data.errors.length > 0) {
        errMsg = data.errors.slice(0, 5).join('\n');
      } else if (data.detail) {
        errMsg = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
      }
      if (window.showToast) window.showToast(`Import Notice:\n${errMsg}`, 'error');
      else alert(`Import Notice:\n${errMsg}`);
    }
  } catch (error) {
    if (window.showToast) window.showToast("Import error: " + error.message, 'error');
    else alert("Import error: " + error.message);
  } finally {
    event.target.value = '';
  }
};

window.showCSSPSImportResultsModal = function(data) {
  const existing = document.getElementById('cssps-import-result-modal');
  if (existing) existing.remove();

  const isSuccess = data.imported > 0 && (!data.skipped || data.skipped === 0);
  const isPartial = data.imported > 0 && data.skipped > 0;
  const isFailed = data.imported === 0;

  const headerColor = isSuccess ? '#10b981' : (isPartial ? '#f59e0b' : '#ef4444');
  const headerIcon = isSuccess ? '🎉' : (isPartial ? '⚠️' : '❌');
  const title = isSuccess 
    ? 'CSSPS Placement Import Successful' 
    : (isPartial ? 'Partial Placement Import Completed' : 'CSSPS Placement Import Report');

  const modal = document.createElement('div');
  modal.id = 'cssps-import-result-modal';
  modal.style.cssText = 'position:fixed; inset:0; z-index:999999; background:rgba(0,0,0,0.75); backdrop-filter:blur(4px); display:flex; align-items:center; justify-content:center; padding:16px;';

  let errorListHtml = '';
  if (data.errors && data.errors.length > 0) {
    const errorItems = data.errors.slice(0, 50).map(e => `<li style="margin-bottom:4px; font-family:monospace; font-size:0.82rem; color:#fca5a5;">${e}</li>`).join('');
    const moreText = data.errors.length > 50 ? `<p style="font-size:0.8rem; color:#94a3b8; margin-top:6px;">...and ${data.errors.length - 50} more issues.</p>` : '';
    errorListHtml = `
      <div style="margin-top:14px; text-align:left;">
        <label style="font-size:0.82rem; font-weight:700; color:#e2e8f0; text-transform:uppercase; letter-spacing:0.5px;">Detailed Row Log (${data.errors.length})</label>
        <div style="max-height:160px; overflow-y:auto; background:rgba(0,0,0,0.35); border:1px solid rgba(239,68,68,0.3); border-radius:8px; padding:10px 14px; margin-top:6px;">
          <ul style="margin:0; padding-left:18px;">${errorItems}</ul>
          ${moreText}
        </div>
      </div>
    `;
  }

  modal.innerHTML = `
    <div style="background:var(--surface-card, #1e293b); color:var(--text-main, #f8fafc); border-radius:14px; max-width:540px; width:100%; box-shadow:0 25px 50px -12px rgba(0,0,0,0.5); border:1px solid rgba(255,255,255,0.1); overflow:hidden;">
      <div style="background:${headerColor}; padding:14px 20px; color:#ffffff; display:flex; align-items:center; justify-content:space-between;">
        <div style="display:flex; align-items:center; gap:10px;">
          <span style="font-size:1.3rem;">${headerIcon}</span>
          <h3 style="margin:0; font-size:1.05rem; font-weight:700;">${title}</h3>
        </div>
        <button onclick="document.getElementById('cssps-import-result-modal').remove()" style="background:none; border:none; color:#ffffff; font-size:1.4rem; cursor:pointer; line-height:1;">&times;</button>
      </div>
      <div style="padding:20px;">
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:14px;">
          <div style="background:rgba(16,185,129,0.1); border:1px solid rgba(16,185,129,0.25); border-radius:10px; padding:12px; text-align:center;">
            <div style="font-size:0.75rem; font-weight:600; color:#34d399; text-transform:uppercase;">Successfully Imported</div>
            <div style="font-size:1.8rem; font-weight:800; color:#10b981;">${data.imported || 0}</div>
          </div>
          <div style="background:rgba(239,68,68,0.1); border:1px solid rgba(239,68,68,0.25); border-radius:10px; padding:12px; text-align:center;">
            <div style="font-size:0.75rem; font-weight:600; color:#f87171; text-transform:uppercase;">Skipped / Existing</div>
            <div style="font-size:1.8rem; font-weight:800; color:#ef4444;">${data.skipped || 0}</div>
          </div>
        </div>
        ${errorListHtml}
        <div style="margin-top:18px; display:flex; justify-content:flex-end; gap:10px;">
          ${isFailed ? `<button onclick="downloadCSSPSCSVTemplate(); document.getElementById('cssps-import-result-modal').remove();" class="btn" style="background:#6366f1; color:#fff; border:none; padding:8px 16px; border-radius:8px; font-weight:600; font-size:0.85rem; cursor:pointer;">📥 Download Template</button>` : ''}
          <button onclick="document.getElementById('cssps-import-result-modal').remove()" class="btn" style="background:var(--primary, #3b82f6); color:#fff; border:none; padding:8px 18px; border-radius:8px; font-weight:600; font-size:0.85rem; cursor:pointer;">Got It</button>
        </div>
      </div>
    </div>
  `;

  document.body.appendChild(modal);
};

window.handleCSSPSCSVFileSelected = async function(event) {
  const file = event.target.files && event.target.files[0];
  if (!file) return;

  const formData = new FormData();
  formData.append('file', file);

  if (window.showToast) window.showToast('Uploading and parsing CSSPS placement sheet...', 'info');

  try {
    const res = await fetch(`${API_BASE}/cssps/import-csv`, {
      method: 'POST',
      headers: getHeaders(),
      body: formData
    });

    let data;
    try {
      data = await res.json();
    } catch (parseErr) {
      const textErr = await res.text().catch(() => '');
      throw new Error(`Server returned ${res.status}: ${textErr || res.statusText}`);
    }

    if (res.ok && data.status !== 'error') {
      if (window.showCSSPSImportResultsModal) {
        window.showCSSPSImportResultsModal(data);
      } else {
        let msg = `✔ Successfully imported ${data.imported} CSSPS candidates!`;
        if (data.skipped > 0) msg += ` (${data.skipped} skipped/already enrolled)`;
        if (window.showToast) window.showToast(msg, data.imported > 0 ? 'success' : 'warning');
      }

      if (window.loadStudents) window.loadStudents();
    } else {
      let errMsg = 'CSSPS import failed';
      if (data.errors && data.errors.length > 0) {
        errMsg = data.errors.slice(0, 5).join('\n');
      } else if (data.detail) {
        errMsg = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
      }
      if (window.showToast) window.showToast(`Import Notice:\n${errMsg}`, 'error');
      else alert(`Import Notice:\n${errMsg}`);
    }
  } catch (error) {
    if (window.showToast) window.showToast("Import error: " + error.message, 'error');
    else alert("Import error: " + error.message);
  } finally {
    event.target.value = '';
  }
};

// ── CSV Imports ─────────────────────────────────────────────────────────────
window.importStudentCSV = async function() {
  const fileInput = document.getElementById('studentCsvFile');
  if (!fileInput.files || fileInput.files.length === 0) {
    alert("Please select a student CSV file first.");
    return;
  }

  const formData = new FormData();
  formData.append('file', fileInput.files[0]);

  const resultEl = document.getElementById('importStudentResult');
  if (resultEl) resultEl.innerHTML = '<span style="opacity:.7">Uploading and processing...</span>';

  try {
    const res = await fetch(`${API_BASE}/students/import-csv`, {
      method: 'POST',
      headers: getHeaders(),
      body: formData
    });
    const data = await res.json();
    if (res.ok) {
      if (resultEl) resultEl.innerHTML = `<span style="color:var(--success-color)">✔ Successfully imported ${data.imported} students.</span>`;
      if (data.errors && data.errors.length > 0 && resultEl) {
        resultEl.innerHTML += `<br><span style="color:var(--warning-color)">Errors: ${data.errors.join(', ')}</span>`;
      }
    } else {
      if (resultEl) resultEl.innerHTML = `<span style="color:var(--danger-color)">Error: ${data.detail || 'Import failed'}</span>`;
    }
  } catch (error) {
    if (resultEl) resultEl.innerHTML = '<span style="color:var(--danger-color)">Network error during import.</span>';
  }
};

// ── User / Staff CSV & Excel Template & Import ─────────────────────────────
window.downloadUserExcelTemplate = async function() {
  const btn = event ? event.target.closest('button') : null;
  const originalHtml = btn ? btn.innerHTML : '';
  if (btn) btn.innerHTML = '<span>⏳</span> Generating Excel...';

  try {
    const res = await fetch(`${API_BASE}/auth/staff-template-xlsx`, {
      headers: getHeaders()
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      alert(`Failed to generate Excel template: ${err.detail || res.statusText}`);
      return;
    }
    const blob = await res.blob();
    let filename = 'Staff_Onboarding_Template_Dropdowns.xlsx';
    const disp = res.headers.get('content-disposition');
    if (disp && disp.includes('filename=')) {
      filename = disp.split('filename=')[1].replace(/["']/g, '').trim();
    }
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.style.display = 'none';
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => {
      if (document.body.contains(a)) document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    }, 250);
  } catch (error) {
    console.error("Error downloading excel template:", error);
    alert("Network error downloading Excel template. Falling back to plain CSV template.");
    window.downloadUserCSVTemplate();
  } finally {
    if (btn) btn.innerHTML = originalHtml;
  }
};

window.downloadUserCSVTemplate = function() {
  const headers = ['full_name', 'gender', 'phone', 'email', 'roles', 'department', 'subject', 'form_class', 'house_assigned', 'password'];
  const csvContent = headers.join(',') + '\n';
  window.triggerBlobDownload(csvContent, 'Official_Staff_Institutional_Provisioning_Template.csv');
};

window.downloadGeneratedCredentialsCSV = function() {
  if (!window._lastGeneratedCredentials || window._lastGeneratedCredentials.length === 0) {
    alert("No credentials to export.");
    return;
  }
  const rows = ['full_name,username,roles,temporary_password'];
  for (const c of window._lastGeneratedCredentials) {
    const fn = (c.full_name || '').replace(/"/g, '""');
    const un = (c.username || '').replace(/"/g, '""');
    const rl = (c.roles || '').replace(/"/g, '""');
    const pw = (c.temporary_password || '').replace(/"/g, '""');
    rows.push(`"${fn}","${un}","${rl}","${pw}"`);
  }
  window.triggerBlobDownload(rows.join('\n'), `Staff_Temporary_Credentials_${new Date().toISOString().slice(0, 10)}.csv`);
};

window.importUserCSV = async function() {
  const fileInput = document.getElementById('userCsvFile');
  if (!fileInput.files || fileInput.files.length === 0) {
    alert("Please select an Excel (.xlsx) or CSV (.csv) file first.");
    return;
  }

  const formData = new FormData();
  formData.append('file', fileInput.files[0]);

  const resultEl = document.getElementById('importUserResult');
  if (resultEl) resultEl.innerHTML = '<span style="opacity:.7">⏳ Uploading and provisioning user accounts...</span>';

  try {
    const res = await fetch(`${API_BASE}/auth/import-users-csv`, {
      method: 'POST',
      headers: getHeaders(),
      body: formData
    });
    const data = await res.json();
    if (res.ok) {
      let html = `<div style="padding:12px 16px; border-radius:8px; background:rgba(16,185,129,0.12); border:1px solid rgba(16,185,129,0.3); color:#34d399; font-weight:600; margin-bottom:12px;">
        ✔ Successfully provisioned ${data.imported} user account${data.imported === 1 ? '' : 's'}.
      </div>`;

      if (data.temporary_credentials && data.temporary_credentials.length > 0) {
        window._lastGeneratedCredentials = data.temporary_credentials;
        html += `
          <div style="margin-top:12px; padding:14px; background:rgba(15,23,42,0.85); border:1px solid rgba(255,255,255,0.15); border-radius:8px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px; flex-wrap:wrap; gap:8px;">
              <strong style="color:#f1f5f9; font-size:0.9rem;">🔐 Auto-Generated Temporary Passwords (${data.temporary_credentials.length})</strong>
              <button class="btn sm" onclick="downloadGeneratedCredentialsCSV()" style="font-size:0.8rem; padding:4px 10px; background:#3b82f6; color:#fff; border:none; border-radius:6px; cursor:pointer;">💾 Download Credentials (CSV)</button>
            </div>
            <p style="font-size:0.82rem; color:#94a3b8; margin:0 0 10px 0;">Please copy or download these credentials now to distribute to staff. Users will be prompted to set a new private password upon first login.</p>
            <div style="max-height:260px; overflow-y:auto; border:1px solid rgba(255,255,255,0.1); border-radius:6px;">
              <table style="width:100%; border-collapse:collapse; font-size:0.82rem; text-align:left;">
                <thead>
                  <tr style="background:rgba(255,255,255,0.06); color:#cbd5e1;">
                    <th style="padding:8px 12px; border-bottom:1px solid rgba(255,255,255,0.1);">Full Name</th>
                    <th style="padding:8px 12px; border-bottom:1px solid rgba(255,255,255,0.1);">Username</th>
                    <th style="padding:8px 12px; border-bottom:1px solid rgba(255,255,255,0.1);">Roles Assigned</th>
                    <th style="padding:8px 12px; border-bottom:1px solid rgba(255,255,255,0.1);">Temporary Password</th>
                  </tr>
                </thead>
                <tbody>
                  ${data.temporary_credentials.map(c => `
                    <tr style="border-bottom:1px solid rgba(255,255,255,0.04);">
                      <td style="padding:8px 12px; font-weight:600; color:#f8fafc;">${c.full_name || c.username}</td>
                      <td style="padding:8px 12px; color:#a5b4fc; font-family:monospace;">${c.username}</td>
                      <td style="padding:8px 12px; color:#cbd5e1; font-size:0.78rem;">${c.roles || 'Teacher'}</td>
                      <td style="padding:8px 12px; font-family:monospace; color:#38bdf8; font-weight:600;">${c.temporary_password}</td>
                    </tr>
                  `).join('')}
                </tbody>
              </table>
            </div>
          </div>
        `;
      }

      if (data.errors && data.errors.length > 0) {
        html += `
          <div style="margin-top:12px; padding:12px; background:rgba(239,68,68,0.1); border:1px solid rgba(239,68,68,0.3); border-radius:8px; color:#f87171; font-size:0.85rem;">
            <strong>⚠️ Warnings / Skipped Rows (${data.errors.length}):</strong>
            <ul style="margin:6px 0 0 16px; padding:0;">
              ${data.errors.map(err => `<li>${err}</li>`).join('')}
            </ul>
          </div>
        `;
      }

      if (resultEl) resultEl.innerHTML = html;
      fileInput.value = '';
    } else {
      if (resultEl) resultEl.innerHTML = `<span style="color:var(--danger-color)">Error: ${data.detail || 'Import failed'}</span>`;
    }
  } catch (error) {
    if (resultEl) resultEl.innerHTML = '<span style="color:var(--danger-color)">Network error during import.</span>';
  }
};


// ── Student Data Export Wizard ──────────────────────────────────────────────
window.openStudentExportWizard = async function() {
  const existing = document.getElementById('student-export-wizard-modal');
  if (existing) existing.remove();

  const modal = document.createElement('div');
  modal.id = 'student-export-wizard-modal';
  modal.style.cssText = 'position:fixed; inset:0; z-index:999999; background:rgba(0,0,0,0.8); backdrop-filter:blur(5px); display:flex; align-items:center; justify-content:center; padding:16px;';

  modal.innerHTML = `
    <div style="background:var(--surface-card, #1e293b); color:var(--text-main, #f8fafc); border-radius:16px; max-width:680px; width:100%; max-height:92vh; display:flex; flex-direction:column; box-shadow:0 25px 50px -12px rgba(0,0,0,0.6); border:1px solid rgba(255,255,255,0.12); overflow:hidden;">
      <!-- Header -->
      <div style="background:linear-gradient(135deg, #4f46e5 0%, #06b6d4 100%); padding:16px 22px; color:#ffffff; display:flex; align-items:center; justify-content:space-between;">
        <div style="display:flex; align-items:center; gap:10px;">
          <span style="font-size:1.4rem;">🎓</span>
          <div>
            <h3 style="margin:0; font-size:1.1rem; font-weight:700;">Student Data Export Wizard</h3>
            <p style="margin:2px 0 0; font-size:0.78rem; opacity:0.9;">Export scoped student cohorts in styled Excel (.xlsx) or universal CSV format.</p>
          </div>
        </div>
        <button onclick="document.getElementById('student-export-wizard-modal').remove()" style="background:none; border:none; color:#ffffff; font-size:1.5rem; cursor:pointer; line-height:1;">&times;</button>
      </div>

      <!-- Scrollable Body -->
      <div style="padding:20px; overflow-y:auto; flex:1;">
        <!-- Step 1: Filters -->
        <div style="margin-bottom:18px;">
          <label style="font-size:0.8rem; font-weight:700; color:#818cf8; text-transform:uppercase; letter-spacing:0.5px; display:block; margin-bottom:8px;">
            1. Filter Cohort (Optional)
          </label>
          <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(180px, 1fr)); gap:10px;">
            <div>
              <label style="font-size:0.75rem; color:#94a3b8; display:block; margin-bottom:4px;">Form / Year</label>
              <select id="ew_form" onchange="window.updateExportWizardCount()" style="width:100%; padding:8px 10px; background:rgba(0,0,0,0.3); border:1px solid rgba(255,255,255,0.15); border-radius:6px; color:#f8fafc; font-size:0.84rem;">
                <option value="">All Forms</option>
                <option value="1">Form 1</option>
                <option value="2">Form 2</option>
                <option value="3">Form 3</option>
              </select>
            </div>
            <div>
              <label style="font-size:0.75rem; color:#94a3b8; display:block; margin-bottom:4px;">Class Section</label>
              <select id="ew_class_id" onchange="window.updateExportWizardCount()" style="width:100%; padding:8px 10px; background:rgba(0,0,0,0.3); border:1px solid rgba(255,255,255,0.15); border-radius:6px; color:#f8fafc; font-size:0.84rem;">
                <option value="">All Classes</option>
              </select>
            </div>
            <div>
              <label style="font-size:0.75rem; color:#94a3b8; display:block; margin-bottom:4px;">Program / Track</label>
              <select id="ew_program_id" onchange="window.updateExportWizardCount()" style="width:100%; padding:8px 10px; background:rgba(0,0,0,0.3); border:1px solid rgba(255,255,255,0.15); border-radius:6px; color:#f8fafc; font-size:0.84rem;">
                <option value="">All Programs</option>
              </select>
            </div>
            <div>
              <label style="font-size:0.75rem; color:#94a3b8; display:block; margin-bottom:4px;">Residential Status</label>
              <select id="ew_residential_status" onchange="window.updateExportWizardCount()" style="width:100%; padding:8px 10px; background:rgba(0,0,0,0.3); border:1px solid rgba(255,255,255,0.15); border-radius:6px; color:#f8fafc; font-size:0.84rem;">
                <option value="">All (Boarding & Day)</option>
                <option value="Boarding">Boarding Only</option>
                <option value="Day">Day Only</option>
              </select>
            </div>
            <div>
              <label style="font-size:0.75rem; color:#94a3b8; display:block; margin-bottom:4px;">Boarding House</label>
              <select id="ew_house_id" onchange="window.updateExportWizardCount()" style="width:100%; padding:8px 10px; background:rgba(0,0,0,0.3); border:1px solid rgba(255,255,255,0.15); border-radius:6px; color:#f8fafc; font-size:0.84rem;">
                <option value="">All Houses</option>
              </select>
            </div>
            <div>
              <label style="font-size:0.75rem; color:#94a3b8; display:block; margin-bottom:4px;">Gender</label>
              <select id="ew_gender" onchange="window.updateExportWizardCount()" style="width:100%; padding:8px 10px; background:rgba(0,0,0,0.3); border:1px solid rgba(255,255,255,0.15); border-radius:6px; color:#f8fafc; font-size:0.84rem;">
                <option value="">All Genders</option>
                <option value="Male">Male</option>
                <option value="Female">Female</option>
              </select>
            </div>
          </div>
        </div>

        <!-- Step 2: Presets -->
        <div style="margin-bottom:18px;">
          <label style="font-size:0.8rem; font-weight:700; color:#818cf8; text-transform:uppercase; letter-spacing:0.5px; display:block; margin-bottom:8px;">
            2. Choose Column Preset
          </label>
          <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(260px, 1fr)); gap:10px;">
            <label class="ew-preset-card" style="display:flex; align-items:flex-start; gap:10px; padding:10px 12px; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.12); border-radius:8px; cursor:pointer;">
              <input type="radio" name="ew_preset" value="academic" checked style="margin-top:3px;" />
              <div>
                <strong style="font-size:0.88rem; color:#f1f5f9;">🎓 Academic Class Roster</strong>
                <p style="margin:2px 0 0; font-size:0.75rem; color:#94a3b8;">Code, Name, Gender, Form, Class, Program, Subject / Electives</p>
              </div>
            </label>
            <label class="ew-preset-card" style="display:flex; align-items:flex-start; gap:10px; padding:10px 12px; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.12); border-radius:8px; cursor:pointer;">
              <input type="radio" name="ew_preset" value="boarding" style="margin-top:3px;" />
              <div>
                <strong style="font-size:0.88rem; color:#f1f5f9;">🏠 Boarding & House Directory</strong>
                <p style="margin:2px 0 0; font-size:0.75rem; color:#94a3b8;">Name, Class, Residential Status, House, Dormitory, Emergency Tel</p>
              </div>
            </label>
            <label class="ew-preset-card" style="display:flex; align-items:flex-start; gap:10px; padding:10px 12px; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.12); border-radius:8px; cursor:pointer;">
              <input type="radio" name="ew_preset" value="cssps" style="margin-top:3px;" />
              <div>
                <strong style="font-size:0.88rem; color:#f1f5f9;">📋 CSSPS & WAEC Audit</strong>
                <p style="margin:2px 0 0; font-size:0.75rem; color:#94a3b8;">Code, BECE Index, Name, Gender, DOB, JHS Attended, Scores</p>
              </div>
            </label>
            <label class="ew-preset-card" style="display:flex; align-items:flex-start; gap:10px; padding:10px 12px; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.12); border-radius:8px; cursor:pointer;">
              <input type="radio" name="ew_preset" value="guardian" style="margin-top:3px;" />
              <div>
                <strong style="font-size:0.88rem; color:#f1f5f9;">📞 Guardian & Emergency Desk</strong>
                <p style="margin:2px 0 0; font-size:0.75rem; color:#94a3b8;">Name, Class, Guardian Name, Primary Phone, Address</p>
              </div>
            </label>
            <label class="ew-preset-card" style="display:flex; align-items:flex-start; gap:10px; padding:10px 12px; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.12); border-radius:8px; cursor:pointer;">
              <input type="radio" name="ew_preset" value="health" style="margin-top:3px;" />
              <div>
                <strong style="font-size:0.88rem; color:#f1f5f9;">🏥 Health & Medical Profile</strong>
                <p style="margin:2px 0 0; font-size:0.75rem; color:#94a3b8;">Name, Class, House, Blood Group, Allergies, Chronic Conditions</p>
              </div>
            </label>
            <label class="ew-preset-card" style="display:flex; align-items:flex-start; gap:10px; padding:10px 12px; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.12); border-radius:8px; cursor:pointer;">
              <input type="radio" name="ew_preset" value="master" style="margin-top:3px;" />
              <div>
                <strong style="font-size:0.88rem; color:#f1f5f9;">📦 Master Institutional Archive</strong>
                <p style="margin:2px 0 0; font-size:0.75rem; color:#94a3b8;">All 20+ academic, pastoral, and bio fields combined</p>
              </div>
            </label>
          </div>
        </div>

        <!-- Step 3: Format & Status -->
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px; background:rgba(255,255,255,0.02); padding:12px 14px; border-radius:8px; border:1px solid rgba(255,255,255,0.08);">
          <div>
            <label style="font-size:0.78rem; font-weight:700; color:#94a3b8; display:block; margin-bottom:6px;">Export Format</label>
            <div style="display:flex; gap:14px;">
              <label style="display:flex; align-items:center; gap:6px; cursor:pointer; font-size:0.85rem; font-weight:600; color:#34d399;">
                <input type="radio" name="ew_format" value="xlsx" checked /> 📊 Excel Workbook (.xlsx)
              </label>
              <label style="display:flex; align-items:center; gap:6px; cursor:pointer; font-size:0.85rem; font-weight:600; color:#60a5fa;">
                <input type="radio" name="ew_format" value="csv" /> 📄 Universal CSV (.csv)
              </label>
            </div>
          </div>
          <div id="ew_counter_pill" style="font-size:0.84rem; font-weight:700; color:#34d399; background:rgba(16,185,129,0.15); border:1px solid rgba(16,185,129,0.3); padding:6px 14px; border-radius:999px;">
            🟢 Calculating...
          </div>
        </div>
      </div>

      <!-- Footer -->
      <div style="padding:14px 20px; background:rgba(0,0,0,0.25); border-top:1px solid rgba(255,255,255,0.08); display:flex; justify-content:flex-end; gap:10px;">
        <button type="button" class="btn" onclick="document.getElementById('student-export-wizard-modal').remove()" style="padding:8px 16px;">Cancel</button>
        <button type="button" id="ew_download_btn" class="btn primary" onclick="window.triggerStudentExportDownload()" style="display:inline-flex; align-items:center; gap:8px; padding:9px 20px; font-weight:700; background:linear-gradient(135deg, #10b981 0%, #059669 100%); border:none; border-radius:8px; cursor:pointer; color:#ffffff;">
          <span>🚀</span> Download Student Export
        </button>
      </div>
    </div>
  `;

  document.body.appendChild(modal);

  // Populate dynamic dropdowns and initial count
  await window.loadExportWizardLookups();
  await window.updateExportWizardCount();
};

window.loadExportWizardLookups = async function() {
  try {
    const [clsRes, progRes, houseRes] = await Promise.all([
      fetch(`${API_BASE}/classes/`, { headers: getHeaders() }).catch(() => null),
      fetch(`${API_BASE}/programs/`, { headers: getHeaders() }).catch(() => null),
      fetch(`${API_BASE}/houses/`, { headers: getHeaders() }).catch(() => null)
    ]);

    if (clsRes && clsRes.ok) {
      const classes = await clsRes.json();
      const sel = document.getElementById('ew_class_id');
      if (sel && Array.isArray(classes)) {
        classes.forEach(c => {
          const opt = document.createElement('option');
          opt.value = c.id;
          opt.textContent = c.name;
          sel.appendChild(opt);
        });
      }
    }

    if (progRes && progRes.ok) {
      const programs = await progRes.json();
      const sel = document.getElementById('ew_program_id');
      if (sel && Array.isArray(programs)) {
        programs.forEach(p => {
          const opt = document.createElement('option');
          opt.value = p.id;
          opt.textContent = p.name;
          sel.appendChild(opt);
        });
      }
    }

    if (houseRes && houseRes.ok) {
      const houses = await houseRes.json();
      const sel = document.getElementById('ew_house_id');
      if (sel && Array.isArray(houses)) {
        houses.forEach(h => {
          const opt = document.createElement('option');
          opt.value = h.id;
          opt.textContent = h.name;
          sel.appendChild(opt);
        });
      }
    }
  } catch (e) {
    console.warn("Error loading export wizard lookups:", e);
  }
};

window.updateExportWizardCount = async function() {
  const pill = document.getElementById('ew_counter_pill');
  if (!pill) return;
  pill.textContent = '⏳ Calculating...';

  const params = new URLSearchParams();
  const form = document.getElementById('ew_form')?.value;
  const classId = document.getElementById('ew_class_id')?.value;
  const programId = document.getElementById('ew_program_id')?.value;
  const resStatus = document.getElementById('ew_residential_status')?.value;
  const houseId = document.getElementById('ew_house_id')?.value;
  const gender = document.getElementById('ew_gender')?.value;

  if (form) params.append('form', form);
  if (classId) params.append('class_id', classId);
  if (programId) params.append('program_id', programId);
  if (resStatus) params.append('residential_status', resStatus);
  if (houseId) params.append('house_id', houseId);
  if (gender) params.append('gender', gender);

  try {
    const res = await fetch(`${API_BASE}/students/export-wizard-count?${params.toString()}`, {
      headers: getHeaders()
    });
    if (res.ok) {
      const data = await res.json();
      const count = data.count || 0;
      pill.textContent = `🟢 ${count} Student${count === 1 ? '' : 's'} Selected`;
    } else {
      pill.textContent = '⚪ Scope Active';
    }
  } catch (e) {
    pill.textContent = '⚪ Ready';
  }
};

window.triggerStudentExportDownload = async function() {
  const btn = document.getElementById('ew_download_btn');
  const originalHtml = btn ? btn.innerHTML : '';
  if (btn) {
    btn.innerHTML = '<span>⏳</span> Generating Export...';
    btn.disabled = true;
  }

  try {
    const params = new URLSearchParams();
    const presetRadio = document.querySelector('input[name="ew_preset"]:checked');
    const formatRadio = document.querySelector('input[name="ew_format"]:checked');
    const preset = presetRadio ? presetRadio.value : 'academic';
    const format = formatRadio ? formatRadio.value : 'xlsx';

    params.append('preset', preset);
    params.append('file_format', format);

    const form = document.getElementById('ew_form')?.value;
    const classId = document.getElementById('ew_class_id')?.value;
    const programId = document.getElementById('ew_program_id')?.value;
    const resStatus = document.getElementById('ew_residential_status')?.value;
    const houseId = document.getElementById('ew_house_id')?.value;
    const gender = document.getElementById('ew_gender')?.value;

    if (form) params.append('form', form);
    if (classId) params.append('class_id', classId);
    if (programId) params.append('program_id', programId);
    if (resStatus) params.append('residential_status', resStatus);
    if (houseId) params.append('house_id', houseId);
    if (gender) params.append('gender', gender);

    const res = await fetch(`${API_BASE}/students/export-wizard?${params.toString()}`, {
      headers: getHeaders()
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      alert(`Export failed: ${err.detail || res.statusText}`);
      return;
    }

    const blob = await res.blob();
    let filename = `Student_Export_${new Date().toISOString().slice(0, 10)}.${format}`;
    const disp = res.headers.get('content-disposition');
    if (disp && disp.includes('filename=')) {
      filename = disp.split('filename=')[1].replace(/["']/g, '').trim();
    }

    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.style.display = 'none';
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => {
      if (document.body.contains(a)) document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    }, 250);

    const modal = document.getElementById('student-export-wizard-modal');
    if (modal) modal.remove();

    if (window.showToast) {
      window.showToast(`✔ Export successfully downloaded: ${filename}`, 'success');
    }
  } catch (error) {
    console.error("Export error:", error);
    alert("Network error during student export: " + error.message);
  } finally {
    if (btn) {
      btn.innerHTML = originalHtml;
      btn.disabled = false;
    }
  }
};

// Aliased so all existing buttons launch the wizard
window.exportStudentsCSV = window.openStudentExportWizard;


// ── Database Backups ────────────────────────────────────────────────────────
window.loadBackups = async function() {
  const body = document.getElementById('backupListBody');
  if (!body) return;

  try {
    const res = await fetch(`${API_BASE}/backup/list`, { headers: getHeaders() });
    if (res.ok) {
      const backups = await res.json();
      if (backups.length === 0) {
        body.innerHTML = `<tr><td colspan="4" style="text-align:center; opacity:0.6; padding:12px;">No backups found.</td></tr>`;
        return;
      }

      body.innerHTML = backups.map(b => {
        const sizeKB = (b.size_bytes / 1024).toFixed(1);
        const dateStr = new Date(b.created_at).toLocaleString();
        return `
          <tr>
            <td><strong>${b.filename}</strong></td>
            <td>${sizeKB} KB</td>
            <td>${dateStr}</td>
            <td style="display:flex; gap:6px;">
              <button class="btn secondary" onclick="downloadBackup('${b.filename}')" style="padding: 2px 8px; font-size: 0.8rem; font-weight:700;">⬇️ Download</button>
              <button class="btn danger" onclick="deleteBackup('${b.filename}')" style="padding: 2px 6px; font-size: 0.8rem;">Delete</button>
            </td>
          </tr>
        `;
      }).join('');
    } else {
      body.innerHTML = `<tr><td colspan="4" style="text-align:center; color:var(--danger-color); padding:12px;">Failed to load backups list.</td></tr>`;
    }
  } catch (e) {
    body.innerHTML = `<tr><td colspan="4" style="text-align:center; color:var(--danger-color); padding:12px;">Network error loading backups.</td></tr>`;
  }
};

window.runBackup = async function() {
  const msg = document.getElementById('backupMsg');
  if (!msg) return;
  msg.innerHTML = '<span style="opacity:0.7">Creating SQLite hot backup...</span>';

  try {
    const res = await fetch(`${API_BASE}/backup/run`, {
      method: 'POST',
      headers: getHeaders()
    });
    const data = await res.json();
    if (res.ok) {
      msg.innerHTML = `<span style="color:var(--success-color)">✔ Database backup generated: ${data.filename} (${(data.size_bytes/1024).toFixed(1)} KB)</span>`;
      loadBackups();
    } else {
      msg.innerHTML = `<span style="color:var(--danger-color)">Error: ${data.detail || 'Backup failed'}</span>`;
    }
  } catch (e) {
    msg.innerHTML = `<span style="color:var(--danger-color)">Network error during backup.</span>`;
  }
};

window.deleteBackup = async function(filename) {
  const ok = await (window.showConfirmDialog ? window.showConfirmDialog(
    '🗑️ Delete Database Backup',
    `Are you sure you want to permanently delete the backup file "${filename}"?`,
    'Delete Backup',
    'Cancel',
    'warning'
  ) : Promise.resolve(confirm(`Are you sure you want to permanently delete the backup "${filename}"?`)));

  if (!ok) return;

  try {
    const res = await fetch(`${API_BASE}/backup/${filename}`, {
      method: 'DELETE',
      headers: getHeaders()
    });
    if (res.ok) {
      loadBackups();
    } else {
      const data = await res.json();
      alert("Failed to delete backup: " + (data.detail || "Unknown error"));
    }
  } catch (e) {
    alert("Network error deleting backup: " + e.message);
  }
};

window.downloadBackup = function(filename) {
  window.open(`${API_BASE}/backup/download/${filename}`, '_blank');
};

window.exportFullSystemZip = function() {
  const msg = document.getElementById('backupMsg');
  if (msg) msg.innerHTML = '<span style="color:#0284c7; font-weight:700;">📦 Compiling full system backup package (.zip)... Download will start automatically.</span>';
  window.open(`${API_BASE}/backup/export-full-zip`, '_blank');
};

window.saveToCustomPath = async function() {
  const inputEl = document.getElementById('customBackupPathInput');
  const msg = document.getElementById('backupMsg');
  const targetPath = inputEl ? inputEl.value.trim() : '';

  if (!targetPath) {
    alert("Please enter a valid target folder path (e.g., D:\\SchoolBackups).");
    return;
  }

  if (msg) msg.innerHTML = '<span style="opacity:0.7">Copying backup snapshot to custom location...</span>';

  try {
    const res = await fetch(`${API_BASE}/backup/copy-to-path`, {
      method: 'POST',
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ target_path: targetPath })
    });
    const data = await res.json();
    if (res.ok) {
      if (msg) msg.innerHTML = `<span style="color:var(--success-color); font-weight:700;">✔ ${data.message} (${data.size_kb} KB)</span>`;
    } else {
      if (msg) msg.innerHTML = `<span style="color:var(--danger-color)">Error: ${data.detail || 'Failed to save to custom path.'}</span>`;
    }
  } catch (e) {
    if (msg) msg.innerHTML = `<span style="color:var(--danger-color)">Network error saving backup: ${e.message}</span>`;
  }
};

// ── Enterprise Cloud Auto-Sync Desk Logic ──────────────────────────────────
window.loadSyncStatus = async function() {
  const pendingEl = document.getElementById('syncPendingCount');
  const totalEl = document.getElementById('syncTotalCount');
  const lastTimeEl = document.getElementById('syncLastTime');
  const tbody = document.getElementById('syncOutboxListBody');
  const pill = document.getElementById('cloudSyncStatusPill');

  try {
    const res = await fetch(`${API_BASE}/sync/status`, { headers: getHeaders() });
    if (res.ok) {
      const data = await res.json();
      if (pendingEl) pendingEl.textContent = data.pending_count || 0;
      if (totalEl) totalEl.textContent = data.total_synced_count || 0;
      if (lastTimeEl) {
        lastTimeEl.textContent = data.last_synced_at 
          ? new Date(data.last_synced_at).toLocaleString() 
          : 'Never';
      }

      if (pill) {
        if (!navigator.onLine) {
          pill.innerHTML = '🟡 Offline Mode (Local)';
          pill.style.background = 'rgba(245, 158, 11, 0.15)';
          pill.style.color = '#f59e0b';
          pill.style.borderColor = 'rgba(245, 158, 11, 0.3)';
        } else if (data.pending_count > 0) {
          pill.innerHTML = `🔄 Pending Sync (${data.pending_count})`;
          pill.style.background = 'rgba(234, 88, 12, 0.15)';
          pill.style.color = '#ea580c';
          pill.style.borderColor = 'rgba(234, 88, 12, 0.3)';
        } else {
          pill.innerHTML = '🟢 Cloud Connected & Synced';
          pill.style.background = 'rgba(16, 185, 129, 0.15)';
          pill.style.color = '#34d399';
          pill.style.borderColor = 'rgba(16, 185, 129, 0.3)';
        }
      }

      if (tbody) {
        const activities = data.recent_activity || [];
        if (activities.length === 0) {
          tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; opacity:0.6; padding:10px;">No sync events recorded yet.</td></tr>`;
        } else {
          tbody.innerHTML = activities.map(a => {
            const timeStr = a.created_at ? new Date(a.created_at).toLocaleTimeString() : '-';
            const statusBadge = a.is_synced 
              ? `<span style="color:#34d399; font-weight:700;">✔ Synced</span>`
              : `<span style="color:#f59e0b; font-weight:700;">⏳ Pending</span>`;
            return `
              <tr>
                <td><strong>${a.entity.toUpperCase()}</strong></td>
                <td><code style="background:rgba(255,255,255,0.06); padding:2px 4px; border-radius:4px;">${a.action}</code></td>
                <td>#${a.entity_id}</td>
                <td>${timeStr}</td>
                <td>${statusBadge}</td>
              </tr>
            `;
          }).join('');
        }
      }
    }
  } catch (err) {
    if (tbody) tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; opacity:0.6; padding:10px;">Offline local mode active.</td></tr>`;
  }
};

window.triggerManualSyncPush = async function() {
  const msg = document.getElementById('syncStatusMsg');
  if (msg) msg.innerHTML = '<span style="color:#818cf8; font-weight:700;">🔄 Bundling delta changes and pushing to cloud...</span>';

  try {
    const res = await fetch(`${API_BASE}/sync/push`, {
      method: 'POST',
      headers: getHeaders()
    });
    const data = await res.json();
    if (res.ok) {
      if (msg) msg.innerHTML = `<span style="color:var(--success-color); font-weight:700;">✔ ${data.message}</span>`;
      if (window.showToast) window.showToast(`✔ Cloud Sync: ${data.message}`, 'success');
      window.loadSyncStatus();
    } else {
      if (msg) msg.innerHTML = `<span style="color:var(--warning-color); font-weight:700;">Notice: ${data.detail || 'Sync failed.'}</span>`;
    }
  } catch (e) {
    if (msg) msg.innerHTML = `<span style="color:var(--danger-color)">Network error during sync dispatch.</span>`;
  }
};

window.pullCloudSnapshot = async function() {
  const ok = await (window.showConfirmDialog ? window.showConfirmDialog(
    '📥 Pull Cloud Snapshot',
    'This will download a complete cloud backup snapshot of all student records and settings for this school. Proceed?',
    'Pull Snapshot',
    'Cancel',
    'info'
  ) : Promise.resolve(confirm('Download fresh cloud snapshot package?')));

  if (!ok) return;

  const msg = document.getElementById('syncStatusMsg');
  if (msg) msg.innerHTML = '<span style="color:#0284c7; font-weight:700;">📥 Fetching school snapshot from central cloud...</span>';

  try {
    const res = await fetch(`${API_BASE}/sync/pull-snapshot`, {
      method: 'POST',
      headers: getHeaders()
    });
    const data = await res.json();
    if (res.ok && data.snapshot) {
      window.triggerBlobDownload(JSON.stringify(data.snapshot, null, 2), `School_Snapshot_${data.school_id}_${new Date().toISOString().slice(0, 10)}.json`, 'application/json');
      if (msg) msg.innerHTML = `<span style="color:var(--success-color); font-weight:700;">✔ Cloud snapshot successfully exported (${data.snapshot.students_count || 0} students, ${data.snapshot.scores_count || 0} scores).</span>`;
    } else {
      if (msg) msg.innerHTML = `<span style="color:var(--danger-color)">Failed to pull snapshot: ${data.detail || 'Error'}</span>`;
    }
  } catch (e) {
    if (msg) msg.innerHTML = `<span style="color:var(--danger-color)">Network error pulling snapshot: ${e.message}</span>`;
  }
};

window.addEventListener('sms:sync-updated', () => {
  if (window.loadSyncStatus) window.loadSyncStatus();
});

document.addEventListener('DOMContentLoaded', () => {
  if (window.loadBackups) window.loadBackups();
  if (window.loadSyncStatus) window.loadSyncStatus();
});
