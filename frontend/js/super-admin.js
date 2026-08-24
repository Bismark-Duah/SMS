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

const modal = document.getElementById('newSchoolModal');
const form = document.getElementById('newSchoolForm');

function openNewSchoolModal() {
  modal.classList.add('active');
}

function closeNewSchoolModal() {
  modal.classList.remove('active');
  form.reset();
}

function toggleRegisterPasswordVisibility() {
  const input = document.getElementById('adminPassword');
  const btn = document.getElementById('toggleAdminPassBtn');
  if (!input) return;
  if (input.type === 'password') {
    input.type = 'text';
    if (btn) btn.textContent = '🙈';
  } else {
    input.type = 'password';
    if (btn) btn.textContent = '👁️';
  }
}

async function loadSuperAdminDashboard() {
  try {
    const res = await fetch(`${API_BASE}/super-admin/dashboard`, { headers: getHeaders() });
    if (!res.ok) {
      if (res.status === 403) {
        alert('Super-Admin privileges required.');
        window.location.href = 'dashboard.html';
        return;
      }
      throw new Error('Failed to load Super-Admin dashboard');
    }

    const data = await res.json();

    // Populate KPIs
    document.getElementById('kpiTotalSchools').textContent = data.total_schools || 0;
    document.getElementById('kpiTotalStudents').textContent = data.total_students || 0;
    document.getElementById('kpiTotalUsers').textContent = data.total_users || 0;
    document.getElementById('kpiTotalFees').textContent = `GH₵ ${data.total_fees_collected ? data.total_fees_collected.toLocaleString('en-US', { minimumFractionDigits: 2 }) : '0.00'}`;

    const diag = data.diagnostics || {};
    document.getElementById('kpiDbSize').textContent = `${diag.db_size_mb || 0} MB`;
    document.getElementById('kpiBackupStatus').textContent = `Backups: ${diag.backups_count || 0} | Last: ${diag.last_backup_time || 'None'}`;

    // Mode Distribution
    const dist = data.mode_distribution || {};
    document.getElementById('modeDistributionLabel').innerHTML = `
      <span class="badge-mode badge-shs">SHS Only: ${dist.SHS_ONLY || 0}</span>
      <span class="badge-mode badge-basic">Basic Only: ${dist.BASIC_ONLY || 0}</span>
      <span class="badge-mode badge-combined">Combined: ${dist.COMBINED || 0}</span>
    `;

    // Render Schools Table
    const tbody = document.getElementById('schoolsTableBody');
    if (!data.schools || data.schools.length === 0) {
      tbody.innerHTML = '<tr><td colspan="8" style="padding:16px; text-align:center; opacity:0.7;">No registered schools found. Click "+ Register New School" to add one.</td></tr>';
      return;
    }

    const sortedSchools = [...data.schools].sort((a, b) => a.id - b.id);
    tbody.innerHTML = sortedSchools.map(s => {
      const statusClass = s.status === 'ACTIVE' ? 'status-active' : 'status-suspended';
      const boardingVal = s.boarding_type || 'BOARDING_AND_DAY';
      const boardingLabel = boardingVal === 'DAY_ONLY' ? 'Day Only' : 'Boarding & Day';
      const boardingClass = boardingVal === 'DAY_ONLY' ? 'badge-day' : 'badge-boarding';

      // Profile Preview — shows what features the current config enables
      const profileSummary = window.FeatureGate
        ? window.FeatureGate.getProfileSummary(s.school_mode, boardingVal)
        : [];
      const previewHtml = profileSummary.map(f =>
        `<span class="feat-${f.enabled ? 'on' : 'off'}">${f.enabled ? '+' : '-'}${f.label}</span>`
      ).join(' &nbsp; ');

      return `
        <tr style="border-bottom: 1px solid var(--border-color, #334155);">
          <td style="padding:10px; font-weight:600;">#${s.id}</td>
          <td style="padding:10px;">
            <strong>${s.name}</strong>
          </td>
          <td style="padding:10px;"><code style="background:rgba(255,255,255,0.08); padding:2px 6px; border-radius:4px;">${s.code}</code></td>
          <td style="padding:10px;">
            <select onchange="changeSchoolMode(${s.id}, this.value, this.closest('tr').querySelector('.boarding-select').value)"
                    style="padding:2px 6px; font-size:0.8rem; border-radius:4px; background:#1e293b; color:#fff; border:1px solid #6366f1;">
              <option value="SHS_ONLY"   ${s.school_mode === 'SHS_ONLY'   ? 'selected' : ''}>SHS Only</option>
              <option value="BASIC_ONLY" ${s.school_mode === 'BASIC_ONLY' ? 'selected' : ''}>Basic Only</option>
              <option value="COMBINED"   ${s.school_mode === 'COMBINED'   ? 'selected' : ''}>Combined</option>
            </select>
          </td>
          <td style="padding:10px;">
            <select class="boarding-select"
                    onchange="changeSchoolBoarding(${s.id}, this.value)"
                    style="padding:2px 6px; font-size:0.8rem; border-radius:4px; background:#1e293b; color:#fff; border:1px solid #0891b2;">
              <option value="BOARDING_AND_DAY" ${boardingVal === 'BOARDING_AND_DAY' ? 'selected' : ''}>Boarding & Day</option>
              <option value="DAY_ONLY"         ${boardingVal === 'DAY_ONLY'         ? 'selected' : ''}>Day Only</option>
            </select>
          </td>
          <td style="padding:10px;">
            <div class="profile-preview">${previewHtml || '<span style="opacity:0.5;">—</span>'}</div>
          </td>
          <td style="padding:10px;">${s.student_count}</td>
          <td style="padding:10px;">${s.user_count}</td>
          <td style="padding:10px;"><span class="${statusClass}">${s.status}</span></td>
          <td style="padding:10px; text-align:right;">
            <button class="btn" style="padding:4px 10px; font-size:0.8rem; background:#0284c7; border-color:#0369a1; color:#fff; margin-right:4px;" onclick="downloadSchoolBackup(${s.id}, '${s.code}')">📥 Backup</button>
            <button class="btn primary" style="padding:4px 10px; font-size:0.8rem;" onclick="enterSchoolView(${s.id}, '${escapeJsQuotes(s.name)}', '${s.school_mode}', '${escapeJsQuotes(s.code || '')}')">👁 Enter View</button>
            <button class="btn ${s.status === 'ACTIVE' ? 'danger' : ''}" style="padding:4px 10px; font-size:0.8rem; margin-left:4px;" onclick="toggleSchoolStatus(${s.id}, '${s.status}')">${s.status === 'ACTIVE' ? 'Suspend' : 'Activate'}</button>
            ${s.id !== 1
              ? `<button class="btn danger" style="padding:4px 10px; font-size:0.8rem; margin-left:4px; background:#dc2626; border-color:#b91c1c;" onclick="deleteSchool(${s.id}, '${escapeJsQuotes(s.name)}')">🗑 Delete</button>`
              : `<button class="btn" disabled title="Default school cannot be deleted" style="padding:4px 10px; font-size:0.8rem; margin-left:4px; background:#374151; border-color:#4b5563; color:#6b7280; cursor:not-allowed; opacity:0.55;">🗑 Delete</button>`
            }
          </td>
        </tr>
      `;
    }).join('');


  } catch (error) {
    console.error('Super-Admin dashboard error:', error);
  }
}

function escapeJsQuotes(str) {
  return str.replace(/'/g, "\\'");
}

async function deleteSchool(schoolId, schoolName) {
  if (schoolId === 1) {
    alert("Primary default school template (ID 1) cannot be deleted.");
    return;
  }
  if (!confirm(`CAUTION: Are you sure you want to PERMANENTLY delete '${schoolName}'?\n\nAn automatic pre-deletion JSON backup will be created before deletion.`)) return;

  try {
    const res = await fetch(`${API_BASE}/super-admin/schools/${schoolId}`, {
      method: 'DELETE',
      headers: getHeaders()
    });
    const data = await res.json();
    if (res.ok) {
      alert(`✔ ${data.message}\nPre-deletion backup saved to: ${data.backup_saved_to}`);
      loadSuperAdminDashboard();
    } else {
      alert(data.detail || 'Could not delete school.');
    }
  } catch (err) {
    alert('Failed to delete school.');
  }
}

function enterSchoolView(schoolId, schoolName, schoolMode, schoolCode) {
  localStorage.setItem('school_id', String(schoolId));
  localStorage.setItem('school_name', schoolName);
  localStorage.setItem('school_mode', schoolMode);
  if (schoolCode) {
    localStorage.setItem('school_abbreviation', schoolCode);
  }
  localStorage.setItem('is_super_admin_viewing', 'true');
  window.location.href = 'dashboard.html';
}

async function toggleSchoolStatus(schoolId, currentStatus) {
  const newStatus = currentStatus === 'ACTIVE' ? 'SUSPENDED' : 'ACTIVE';
  if (!confirm(`Are you sure you want to change school status to ${newStatus}?`)) return;

  try {
    const res = await fetch(`${API_BASE}/super-admin/schools/${schoolId}/status`, {
      method: 'PUT',
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ status: newStatus })
    });
    if (res.ok) {
      loadSuperAdminDashboard();
    } else {
      alert('Could not update school status.');
    }
  } catch (err) {
    alert('Failed to update status.');
  }
}

async function changeSchoolMode(schoolId, newMode, currentBoarding) {
  const profileName = window.FeatureGate
    ? window.FeatureGate.getProfileName(newMode, currentBoarding || 'BOARDING_AND_DAY')
    : newMode;
  if (!confirm(`Change school mode to: ${profileName}?\n\nThis will immediately affect what features are available to this school's administrators and staff.`)) return;

  try {
    const res = await fetch(`${API_BASE}/super-admin/schools/${schoolId}/mode`, {
      method: 'PUT',
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ school_mode: newMode })
    });

    if (res.ok) {
      loadSuperAdminDashboard();
    } else {
      alert('Could not update school mode.');
      loadSuperAdminDashboard(); // Reset dropdown to actual value
    }
  } catch (err) {
    alert('Failed to update mode.');
    loadSuperAdminDashboard();
  }
}

async function changeSchoolBoarding(schoolId, newBoarding) {
  const profileName = window.FeatureGate
    ? window.FeatureGate.getProfileName('COMBINED', newBoarding)
    : newBoarding;
  if (!confirm(`Change boarding status to: ${newBoarding === 'DAY_ONLY' ? 'Day Only' : 'Boarding & Day'}?\n\nThis affects Exeat Management, Houses & Dormitories, boarding staff roles, and boarding fee categories.`)) {
    loadSuperAdminDashboard(); // Reset dropdown
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/super-admin/schools/${schoolId}/boarding`, {
      method: 'PUT',
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ boarding_status: newBoarding })
    });

    if (res.ok) {
      loadSuperAdminDashboard();
    } else {
      const err = await res.json().catch(() => ({}));
      alert(err.detail || 'Could not update boarding status.');
      loadSuperAdminDashboard();
    }
  } catch (err) {
    alert('Failed to update boarding status.');
    loadSuperAdminDashboard();
  }
}


async function downloadSchoolBackup(schoolId, schoolCode) {
  try {
    const res = await fetch(`${API_BASE}/super-admin/schools/${schoolId}/backup`, {
      headers: getHeaders()
    });

    if (!res.ok) {
      alert('Could not download backup.');
      return;
    }

    const data = await res.json();
    const jsonStr = JSON.stringify(data, null, 2);
    const blob = new Blob([jsonStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `backup_${schoolCode}_${new Date().toISOString().split('T')[0]}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  } catch (err) {
    alert('Failed to download backup data.');
  }
}

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const payload = {
    name: document.getElementById('schoolName').value.trim(),
    code: document.getElementById('schoolCode').value.trim().toUpperCase(),
    school_mode: document.getElementById('schoolMode').value,
    boarding_type: document.getElementById('schoolBoarding').value,
    address: document.getElementById('schoolAddress').value.trim() || null,
    phone: document.getElementById('schoolPhone').value.trim() || null,
    email: document.getElementById('schoolEmail').value.trim() || null,
    admin_username: document.getElementById('adminUsername').value.trim(),
    admin_email: document.getElementById('adminEmail').value.trim(),
    admin_password: document.getElementById('adminPassword').value
  };

  try {
    const res = await fetch(`${API_BASE}/super-admin/schools`, {
      method: 'POST',
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    if (!res.ok) {
      alert(data.detail || 'Could not register school.');
      return;
    }

    alert(`✔ School '${data.school.name}' onboarded successfully!`);
    closeNewSchoolModal();
    loadSuperAdminDashboard();
  } catch (err) {
    alert('Failed to onboard new school.');
  }
});

loadSuperAdminDashboard();
