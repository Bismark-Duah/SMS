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
      const blob = new Blob([JSON.stringify(data.snapshot, null, 2)], { type: 'application/json' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `School_Snapshot_${data.school_id}_${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
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
