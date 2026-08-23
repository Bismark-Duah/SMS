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

  const sampleRow = [
    '100000000026',
    'CSSPS-2026-X89',
    'Kwame',
    'Kofi',
    'Mensah',
    'Male',
    '2009-04-12',
    '430',
    '8',
    'Achimota Junior High',
    'General Science',
    'Boarding',
    'Mr. Ebenezer Mensah',
    '0244123456',
    '0200000000',
    '"House 12, West Legon, Accra"'
  ];

  const csvContent = [headers.join(','), sampleRow.join(',')].join('\n');
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.setAttribute('href', url);
  a.setAttribute('download', `CSSPS_Official_Placement_Template.csv`);
  a.click();
};

window.triggerCSSPSCSVUpload = function() {
  const input = document.getElementById('csspsCsvFileInput');
  if (input) input.click();
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

    const data = await res.json();
    if (res.ok) {
      let msg = `✔ Successfully imported ${data.imported} CSSPS candidates!`;
      if (data.skipped > 0) msg += ` (${data.skipped} skipped/already enrolled)`;
      if (window.showToast) window.showToast(msg, 'success');
      else alert(msg);

      if (window.loadStudents) window.loadStudents();
    } else {
      const err = data.detail || 'CSSPS import failed';
      if (window.showToast) window.showToast(`Error: ${err}`, 'error');
      else alert(`Error: ${err}`);
    }
  } catch (error) {
    alert("Network error importing CSSPS CSV: " + error.message);
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

window.importUserCSV = async function() {
  const fileInput = document.getElementById('userCsvFile');
  if (!fileInput.files || fileInput.files.length === 0) {
    alert("Please select a user CSV file first.");
    return;
  }

  const formData = new FormData();
  formData.append('file', fileInput.files[0]);

  const resultEl = document.getElementById('importUserResult');
  if (resultEl) resultEl.innerHTML = '<span style="opacity:.7">Uploading and processing...</span>';

  try {
    const res = await fetch(`${API_BASE}/auth/import-users-csv`, {
      method: 'POST',
      headers: getHeaders(),
      body: formData
    });
    const data = await res.json();
    if (res.ok) {
      if (resultEl) resultEl.innerHTML = `<span style="color:var(--success-color)">✔ Successfully imported ${data.imported} users.</span>`;
    } else {
      if (resultEl) resultEl.innerHTML = `<span style="color:var(--danger-color)">Error: ${data.detail || 'Import failed'}</span>`;
    }
  } catch (error) {
    if (resultEl) resultEl.innerHTML = '<span style="color:var(--danger-color)">Network error during import.</span>';
  }
};

// ── Export ──────────────────────────────────────────────────────────────────
window.exportStudentsCSV = async function() {
  try {
    const res = await fetch(`${API_BASE}/students/`, { headers: getHeaders() });
    const students = await res.json();
    if (!students || students.length === 0) {
      alert("No student data available to export.");
      return;
    }

    const headers = ['id', 'student_code', 'full_name', 'gender', 'date_of_birth', 'guardian_name', 'phone', 'address', 'class_section_id', 'program_name', 'bece_index_number'];
    const csvRows = [headers.join(',')];

    for (const s of students) {
      const values = [
        s.id,
        `"${s.student_code || ''}"`,
        `"${s.full_name || ''}"`,
        `"${s.gender || ''}"`,
        `"${s.date_of_birth || ''}"`,
        `"${s.guardian_name || ''}"`,
        `"${s.phone || ''}"`,
        `"${s.address || ''}"`,
        s.class_section_id || '',
        `"${s.program_name || ''}"`,
        `"${s.bece_index_number || ''}"`
      ];
      csvRows.push(values.join(','));
    }

    const blob = new Blob([csvRows.join('\n')], { type: 'text/csv;charset=utf-8;' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.setAttribute('href', url);
    a.setAttribute('download', `Students_Export_${new Date().toISOString().slice(0, 10)}.csv`);
    a.click();
  } catch (e) {
    alert("Export failed: " + e.message);
  }
};

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
  if (!confirm(`Are you sure you want to permanently delete the backup "${filename}"?`)) {
    return;
  }

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

document.addEventListener('DOMContentLoaded', () => {
  if (window.loadBackups) window.loadBackups();
});
