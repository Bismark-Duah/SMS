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

const ROLE_METADATA = {
  // Leadership & Administration
  headmaster: { title: 'Headmaster', icon: '👨‍🏫', category: 'executive' },
  headmistress: { title: 'Headmistress', icon: '👩‍🏫', category: 'executive' },
  assistant_headmaster_academic: { title: 'Assistant Head (Academic)', icon: '📘', category: 'executive' },
  assistant_head_academic: { title: 'Assistant Head (Academic)', icon: '📘', category: 'executive' },
  assistant_headmaster_admin: { title: 'Assistant Head (Administration)', icon: '🏢', category: 'executive' },
  assistant_head_admin: { title: 'Assistant Head (Administration)', icon: '🏢', category: 'executive' },
  assistant_headmaster_domestic: { title: 'Assistant Head (Domestic / Boarding)', icon: '🏡', category: 'executive' },
  assistant_head_domestic: { title: 'Assistant Head (Domestic / Boarding)', icon: '🏡', category: 'executive' },
  
  // Teaching & Academics
  teacher: { title: 'Teacher', icon: '📚', category: 'academic' },
  hod: { title: 'Head of Department (HOD)', icon: '🔬', category: 'academic' },
  form_master: { title: 'Form Master', icon: '🎓', category: 'academic' },
  form_mistress: { title: 'Form Mistress', icon: '🎓', category: 'academic' },
  
  // Boarding & Pastoral Care
  senior_house_master: { title: 'Senior Housemaster', icon: '🏠', category: 'boarding' },
  senior_housemaster: { title: 'Senior Housemaster', icon: '🏠', category: 'boarding' },
  senior_house_mistress: { title: 'Senior Housemistress', icon: '🏠', category: 'boarding' },
  senior_housemistress: { title: 'Senior Housemistress', icon: '🏠', category: 'boarding' },
  house_master: { title: 'Housemaster', icon: '🛌', category: 'boarding' },
  housemaster: { title: 'Housemaster', icon: '🛌', category: 'boarding' },
  house_mistress: { title: 'Housemistress', icon: '🛌', category: 'boarding' },
  housemistress: { title: 'Housemistress', icon: '🛌', category: 'boarding' },
  assistant_house_master: { title: 'Assistant Housemaster', icon: '🚪', category: 'boarding' },
  assistant_house_mistress: { title: 'Assistant Housemistress', icon: '🚪', category: 'boarding' },
  
  // Operations & Finance
  bursar: { title: 'School Accountant / Bursar', icon: '💰', category: 'operations' },
  storekeeper: { title: 'Storekeeper (Asset & Books)', icon: '📦', category: 'operations' },
  security_officer: { title: 'Security Officer (Gate & Exeats)', icon: '🛡️', category: 'operations' },
  
  // Stakeholder Portals
  parent: { title: 'Parent / Guardian', icon: '👨‍👩‍👧', category: 'portal' },
  student: { title: 'Student', icon: '🎒', category: 'portal' }
};

function getRoleInfo(name) {
  const clean = (name || '').toLowerCase();
  if (ROLE_METADATA[clean]) return ROLE_METADATA[clean];
  const title = clean.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
  return { title, icon: '🏷️', category: 'custom' };
}

function formatRoleTitle(name) {
  return getRoleInfo(name).title;
}

let allRawRoles = [];
let allUsersData = [];
let allStudentsData = [];
let selectedSchoolScope = localStorage.getItem('school_id') || 'system_only';

// ── Load & Categorize Available Roles ──────────────────────────────────────────

async function loadRoles() {
  const container = document.getElementById('rolesContainer');
  if (!container) return;

  try {
    const res = await fetch(`${API_BASE}/auth/roles`, { headers: getHeaders() });
    if (!res.ok) throw new Error('Failed to fetch roles');
    const roles = await res.json();
    allRawRoles = roles || [];

    if (!roles || !roles.length) {
      container.innerHTML = '<span style="opacity:.6;">No roles found.</span>';
      return;
    }

    const F = (window.SchoolFeatures && window.SchoolFeatures.version)
      ? window.SchoolFeatures
      : (window.FeatureGate ? window.FeatureGate.getFeatures() : null);

    const isBoarding = F ? F.showBoardingRoles : ((localStorage.getItem('boarding_status') || 'BOARDING_AND_DAY').toUpperCase() === 'BOARDING_AND_DAY');
    const isBasicOnly = F ? F.isBasicOnly : (localStorage.getItem('school_mode') === 'BASIC_ONLY');

    const BOARDING_ROLES = [
      'senior_house_master', 'senior_housemaster', 'senior_house_mistress', 'senior_housemistress',
      'house_master', 'housemaster', 'assistant_house_master',
      'house_mistress', 'housemistress', 'assistant_house_mistress',
      'assistant_headmaster_domestic', 'assistant_head_domestic',
      'security_officer'
    ];

    // Filter out super_admin and admin (security & architecture rule)
    const allowedRoles = roles.filter(r => {
      const rName = r.name.toLowerCase();
      if (rName === 'super_admin' || rName === 'admin') return false;
      if (!isBoarding && BOARDING_ROLES.includes(rName)) return false;
      if (isBasicOnly && rName === 'hod') return false;
      return true;
    });

    const groups = {
      executive: { title: '🏛️ School Executive & Leadership', roles: [] },
      academic: { title: '👨‍🏫 Teaching Faculty & Academics', roles: [] },
      boarding: { title: '🏡 Boarding & Pastoral Care', roles: [] },
      operations: { title: '💼 Finance, Assets & Operations', roles: [] },
      portal: { title: '👥 Stakeholder Portals', roles: [] },
      custom: { title: '🌟 Custom Privileges', roles: [] }
    };

    allowedRoles.forEach(r => {
      const info = getRoleInfo(r.name);
      const cat = groups[info.category] ? info.category : 'custom';
      groups[cat].roles.push({ ...r, info });
    });

    let html = '';
    Object.values(groups).forEach(grp => {
      if (!grp.roles.length) return;
      html += `
        <div class="role-group-section">
          <div class="role-group-title">${grp.title}</div>
          <div class="role-tile-grid">
            ${grp.roles.map(r => {
              const isDefaultChecked = r.name === 'teacher' ? 'checked' : '';
              return `
                <label class="role-tile-card">
                  <input type="checkbox" name="user_role" value="${r.name}" ${isDefaultChecked} />
                  <div>
                    <span style="font-size:1.05rem; margin-right:4px;">${r.info.icon}</span>
                    <span class="role-tile-title">${r.info.title}</span>
                  </div>
                </label>
              `;
            }).join('')}
          </div>
        </div>
      `;
    });

    container.innerHTML = html;

  } catch (err) {
    console.error('Error loading roles:', err);
    container.innerHTML = '<span style="color:var(--danger, #ef4444);">Failed to load roles.</span>';
  }
}

// ── Super-Admin Tenant Filter ──────────────────────────────────────────────────

async function initSuperAdminTenantFilter() {
  const isSuperAdmin = (localStorage.getItem('is_super_admin') === 'true' || localStorage.getItem('userRole') === 'super_admin');
  const filterContainer = document.getElementById('superAdminTenantFilter');
  const tenantSelect = document.getElementById('tenantSelect');

  if (!isSuperAdmin || !filterContainer || !tenantSelect) return;

  filterContainer.style.display = 'flex';

  try {
    const res = await fetch(`${API_BASE}/super-admin/schools`, { headers: getHeaders() });
    if (res.ok) {
      const schools = await res.json();
      let optionsHtml = `
        <option value="system_only" ${selectedSchoolScope === 'system_only' ? 'selected' : ''}>👑 System & Super-Admins Only</option>
        <option value="all" ${selectedSchoolScope === 'all' ? 'selected' : ''}>🌐 All Accounts (Global System View)</option>
      `;
      (schools || []).forEach(s => {
        optionsHtml += `<option value="${s.id}" ${String(selectedSchoolScope) === String(s.id) ? 'selected' : ''}>🏫 ${s.name} (${s.code})</option>`;
      });
      tenantSelect.innerHTML = optionsHtml;
    }
  } catch (e) {}
}

window.onTenantFilterChange = function(val) {
  selectedSchoolScope = val;
  if (val === 'system_only' || val === 'all') {
    localStorage.removeItem('school_id');
  } else {
    localStorage.setItem('school_id', val);
  }
  loadData();
};

// ── Load & Render User Directory ──────────────────────────────────────────────

async function loadData() {
  const userList = document.getElementById('userList');
  const studentSelect = document.getElementById('link_student_id');
  const parentSelect = document.getElementById('link_parent_id');
  const countBadge = document.getElementById('userCountBadge');

  try {
    const reqHeaders = getHeaders();
    if (selectedSchoolScope === 'system_only') {
      delete reqHeaders['X-School-Id'];
    }

    const [resUsers, resStudents] = await Promise.all([
      fetch(`${API_BASE}/auth/users`, { headers: reqHeaders }),
      fetch(`${API_BASE}/students/`, { headers: reqHeaders }),
    ]);

    let users = await resUsers.json();
    let students = await resStudents.json();

    if (!Array.isArray(users)) users = [];
    if (!Array.isArray(students)) students = [];

    const isSuperAdminSession = (localStorage.getItem('is_super_admin') === 'true' || localStorage.getItem('userRole') === 'super_admin');
    if (isSuperAdminSession && selectedSchoolScope === 'system_only') {
      users = users.filter(u => u.roles.some(r => r.name === 'super_admin') || u.school_id === null);
    } else if (!isSuperAdminSession) {
      users = users.filter(u => !u.roles.some(r => r.name === 'super_admin'));
    }

    allUsersData = users;
    allStudentsData = students;

    renderUserTable(users);

    // Populate Student Select
    if (studentSelect) {
      studentSelect.innerHTML = '<option value="">Select Student...</option>' + 
        students.map(s => `<option value="${s.id}">${s.full_name} (${s.student_code})</option>`).join('');
    }

    // Populate Parent Select (Filter by 'parent' role)
    if (parentSelect) {
      const parents = users.filter(u => u.roles.some(r => r.name === 'parent'));
      parentSelect.innerHTML = '<option value="">Select Parent...</option>' + 
        parents.map(p => `<option value="${p.id}">${p.username}</option>`).join('');
    }

  } catch (error) {
    console.error('Error loading data:', error);
    if (userList) userList.innerHTML = '<div style="padding:16px; color:var(--danger,#ef4444);">Failed to load user directory.</div>';
  }
}

function renderUserTable(users) {
  const userList = document.getElementById('userList');
  const countBadge = document.getElementById('userCountBadge');
  if (!userList) return;

  if (countBadge) {
    countBadge.textContent = `Showing ${users.length} registered user account${users.length === 1 ? '' : 's'}`;
  }

  if (!users || !users.length) {
    userList.innerHTML = '<div style="padding:24px; text-align:center; opacity:0.7; font-size:0.9rem;">No matching users found in current scope.</div>';
    return;
  }

  const currentUserId = parseInt(localStorage.getItem('userId') || sessionStorage.getItem('userId') || '0', 10);
  const isSuperAdminSession = (localStorage.getItem('is_super_admin') === 'true' || localStorage.getItem('userRole') === 'super_admin');

  let tableHtml = `
    <table class="user-directory-table">
      <thead>
        <tr>
          <th>User / Staff Name</th>
          <th>Contact & Email</th>
          <th>Assigned Roles & Privileges</th>
          <th>Status</th>
          <th style="text-align:right;">Actions</th>
        </tr>
      </thead>
      <tbody>
  `;

  users.forEach(u => {
    const isParent = u.roles.some(r => r.name === 'parent');
    let childrenInfo = '';
    if (isParent) {
      const linked = allStudentsData.filter(s => String(s.parent_id) === String(u.id));
      childrenInfo = linked.length 
        ? `<div style="font-size:0.75rem; color:#10b981; font-weight:600; margin-top:3px;">👨‍👩‍👧 Linked: ${linked.map(c=>c.full_name).join(', ')}</div>`
        : `<div style="font-size:0.72rem; color:var(--text-secondary); margin-top:2px;">(No students linked)</div>`;
    }

    const initial = (u.username || 'U').charAt(0).toUpperCase();
    const genderBadge = u.gender ? `<span style="font-size:0.72rem; opacity:0.75; margin-left:4px;">(${u.gender})</span>` : '';

    const rolePills = u.roles.length 
      ? u.roles.map(r => {
          const info = getRoleInfo(r.name);
          const isExec = info.category === 'executive' || r.name === 'admin';
          const bg = isExec ? 'rgba(239, 68, 68, 0.15)' : 'rgba(99, 102, 241, 0.15)';
          const border = isExec ? 'rgba(239, 68, 68, 0.4)' : 'rgba(99, 102, 241, 0.4)';
          const color = isExec ? '#fca5a5' : '#a5b4fc';
          return `<span style="display:inline-flex; align-items:center; gap:4px; font-size:0.75rem; font-weight:600; padding:2px 8px; border-radius:12px; background:${bg}; border:1px solid ${border}; color:${color}; margin:2px 4px 2px 0;">
            <span>${info.icon}</span> ${info.title}
          </span>`;
        }).join('')
      : '<span style="font-size:0.75rem; color:var(--text-secondary);">No Role Assigned</span>';

    const isUserAdminOrExec = u.roles.some(r => {
      const rName = (r.name || '').toLowerCase();
      return rName === 'admin' || rName === 'super_admin' || rName.includes('assistant_head');
    });

    const canImpersonate = (u.id !== currentUserId) && !isUserAdminOrExec && (selectedSchoolScope !== 'system_only');
    const canDelete = (u.id !== currentUserId);

    const impersonateBtn = canImpersonate ? `
      <button type="button" onclick="impersonateUser(${u.id}, '${escapeHtml(u.username)}')" 
              style="background:rgba(14, 165, 233, 0.2); border:1px solid rgba(14, 165, 233, 0.4); color:#38bdf8; padding:4px 9px; border-radius:5px; font-size:0.75rem; font-weight:600; cursor:pointer;" 
              title="Preview portal as ${u.username}">
        👤 View As
      </button>
    ` : '';

    const editBtn = `
      <button type="button" onclick="openEditRolesModal(${u.id})" 
              style="background:rgba(99, 102, 241, 0.2); border:1px solid rgba(99, 102, 241, 0.4); color:#a5b4fc; padding:4px 9px; border-radius:5px; font-size:0.75rem; font-weight:600; cursor:pointer;" 
              title="Edit Assigned Roles">
        ✏️ Roles
      </button>
    `;

    const resetBtn = `
      <button type="button" onclick="openResetPasswordModal(${u.id}, '${escapeHtml(u.username)}')" 
              style="background:rgba(234, 179, 8, 0.2); border:1px solid rgba(234, 179, 8, 0.4); color:#fde047; padding:4px 9px; border-radius:5px; font-size:0.75rem; font-weight:600; cursor:pointer;" 
              title="Reset Password">
        🔑 Reset
      </button>
    `;

    const deleteBtn = canDelete ? `
      <button type="button" onclick="deleteUser(${u.id}, '${escapeHtml(u.username)}')" 
              style="background:rgba(239, 68, 68, 0.15); border:1px solid rgba(239, 68, 68, 0.35); color:#fca5a5; padding:4px 8px; border-radius:5px; font-size:0.75rem; font-weight:600; cursor:pointer;" 
              title="Delete Account">
        🗑️
      </button>
    ` : '';

    tableHtml += `
      <tr>
        <td>
          <div style="display:flex; align-items:center; gap:10px;">
            <div class="user-avatar-badge">${initial}</div>
            <div>
              <div style="font-weight:700; color:#f8fafc; font-size:0.9rem;">${escapeHtml(u.username)} ${genderBadge}</div>
              ${childrenInfo}
            </div>
          </div>
        </td>
        <td>
          <div style="font-size:0.83rem; color:var(--text-secondary);">${u.email ? escapeHtml(u.email) : '<em>No email</em>'}</div>
        </td>
        <td>
          <div style="display:flex; flex-wrap:wrap; align-items:center;">${rolePills}</div>
        </td>
        <td>
          <span style="display:inline-flex; align-items:center; gap:4px; font-size:0.75rem; font-weight:700; color:${u.is_active !== false ? '#10b981' : '#ef4444'};">
            ● ${u.is_active !== false ? 'Active' : 'Inactive'}
          </span>
        </td>
        <td style="text-align:right;">
          <div style="display:inline-flex; gap:5px; align-items:center; justify-content:flex-end;">
            ${editBtn}
            ${resetBtn}
            ${impersonateBtn}
            ${deleteBtn}
          </div>
        </td>
      </tr>
    `;
  });

  tableHtml += `</tbody></table>`;
  userList.innerHTML = tableHtml;
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str).replace(/[&<>"']/g, function(m) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[m];
  });
}

// ── Live Filter & Search ───────────────────────────────────────────────────────

window.filterUserDirectory = function() {
  const searchInput = document.getElementById('userSearchInput');
  const roleSelect = document.getElementById('userRoleFilter');
  const query = (searchInput ? searchInput.value : '').toLowerCase().trim();
  const selectedRole = roleSelect ? roleSelect.value : 'ALL';

  const filtered = allUsersData.filter(u => {
    // Keyword match
    const usernameMatch = (u.username || '').toLowerCase().includes(query);
    const emailMatch = (u.email || '').toLowerCase().includes(query);
    const roleMatchText = u.roles.some(r => formatRoleTitle(r.name).toLowerCase().includes(query));

    const matchesQuery = !query || usernameMatch || emailMatch || roleMatchText;

    // Role filter match
    let matchesRole = true;
    if (selectedRole !== 'ALL') {
      matchesRole = u.roles.some(r => r.name.toLowerCase().includes(selectedRole.toLowerCase()));
    }

    return matchesQuery && matchesRole;
  });

  renderUserTable(filtered);
};

// ── User Creation Form ─────────────────────────────────────────────────────────

const userForm = document.getElementById('userForm');
if (userForm) {
  userForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const checkedRoles = Array.from(document.querySelectorAll('input[name="user_role"]:checked')).map(cb => cb.value);

    if (!checkedRoles.length) {
      alert('Please select at least one role/privilege for this user.');
      return;
    }

    const payload = {
      username: document.getElementById('username').value.trim(),
      email: document.getElementById('email').value.trim() || null,
      password: document.getElementById('password').value,
      gender: document.getElementById('userGender') ? document.getElementById('userGender').value : 'Male',
      roles: checkedRoles
    };

    try {
      const res = await fetch(`${API_BASE}/auth/users`, {
        method: 'POST',
        headers: getHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(payload)
      });

      if (res.ok) {
        alert('User account created successfully!');
        userForm.reset();
        await loadRoles();
        await loadData();
      } else {
        const err = await res.json();
        alert(`Error: ${err.detail || 'Could not create user'}`);
      }
    } catch (err) {
      alert(`Network error: ${err.message}`);
    }
  });
}

// ── Edit Roles Modal Handlers ──────────────────────────────────────────────────

window.openEditRolesModal = function(userId) {
  const user = allUsersData.find(u => u.id === userId);
  if (!user) return;

  const modal = document.getElementById('editRolesModal');
  const title = document.getElementById('editUserModalTitle');
  const subtitle = document.getElementById('editUserSubtitle');
  const idInput = document.getElementById('editUserId');
  const container = document.getElementById('editRolesContainer');

  if (!modal || !container) return;

  idInput.value = user.id;
  if (title) title.textContent = `✏️ Edit Roles: ${user.username}`;
  if (subtitle) subtitle.textContent = `Configure assigned permissions for ${user.username} (${user.email || 'No email'})`;

  const userRoleNames = new Set(user.roles.map(r => r.name.toLowerCase()));

  // Render role checkboxes inside modal
  const allowedRoles = allRawRoles.filter(r => {
    const rName = r.name.toLowerCase();
    return rName !== 'super_admin' && rName !== 'admin';
  });

  container.innerHTML = `
    <div class="role-tile-grid">
      ${allowedRoles.map(r => {
        const info = getRoleInfo(r.name);
        const isChecked = userRoleNames.has(r.name.toLowerCase()) ? 'checked' : '';
        return `
          <label class="role-tile-card">
            <input type="checkbox" name="edit_user_role" value="${r.name}" ${isChecked} />
            <div>
              <span style="font-size:1.05rem; margin-right:4px;">${info.icon}</span>
              <span class="role-tile-title">${info.title}</span>
            </div>
          </label>
        `;
      }).join('')}
    </div>
  `;

  modal.style.display = 'flex';
};

window.closeEditRolesModal = function() {
  const modal = document.getElementById('editRolesModal');
  if (modal) modal.style.display = 'none';
};

window.saveUserRoles = async function() {
  const userId = document.getElementById('editUserId').value;
  const checkedRoles = Array.from(document.querySelectorAll('input[name="edit_user_role"]:checked')).map(cb => cb.value);

  if (!checkedRoles.length) {
    alert('Please select at least one role.');
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/auth/users/${userId}/roles`, {
      method: 'PUT',
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ roles: checkedRoles })
    });

    if (res.ok) {
      alert('User roles updated successfully!');
      closeEditRolesModal();
      await loadData();
    } else {
      const err = await res.json();
      alert(`Error: ${err.detail || 'Failed to update roles'}`);
    }
  } catch (e) {
    alert(`Error: ${e.message}`);
  }
};

// ── Reset Password Modal Handlers ──────────────────────────────────────────────

window.openResetPasswordModal = function(userId, username) {
  const modal = document.getElementById('resetPasswordModal');
  const idInput = document.getElementById('resetUserId');
  const subtitle = document.getElementById('resetUserSubtitle');
  const passInput = document.getElementById('newResetPassword');

  if (!modal) return;
  idInput.value = userId;
  if (subtitle) subtitle.textContent = `Set a new password for account "${username}"`;
  if (passInput) passInput.value = '';

  modal.style.display = 'flex';
};

window.closeResetPasswordModal = function() {
  const modal = document.getElementById('resetPasswordModal');
  if (modal) modal.style.display = 'none';
};

window.saveNewPassword = async function() {
  const userId = document.getElementById('resetUserId').value;
  const passInput = document.getElementById('newResetPassword');
  const newPassword = passInput ? passInput.value.trim() : '';

  if (!newPassword || newPassword.length < 6) {
    alert('Password must be at least 6 characters long.');
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/auth/users/${userId}/reset-password`, {
      method: 'PATCH',
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ new_password: newPassword })
    });

    if (res.ok) {
      alert('Password reset successfully!');
      closeResetPasswordModal();
    } else {
      const err = await res.json();
      alert(`Error: ${err.detail || 'Could not reset password'}`);
    }
  } catch (e) {
    alert(`Error: ${e.message}`);
  }
};

// ── Delete User Handler ────────────────────────────────────────────────────────

window.deleteUser = async function(userId, username) {
  if (!confirm(`Are you sure you want to delete user account "${username}"? This action cannot be undone.`)) {
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/auth/users/${userId}`, {
      method: 'DELETE',
      headers: getHeaders()
    });

    if (res.ok) {
      alert(`User "${username}" deleted successfully!`);
      await loadData();
    } else {
      const err = await res.json();
      alert(`Error: ${err.detail || 'Could not delete user'}`);
    }
  } catch (e) {
    alert(`Error: ${e.message}`);
  }
};

// ── Parent-Student Linking Form ────────────────────────────────────────────────

const linkForm = document.getElementById('linkForm');
if (linkForm) {
  linkForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const parentId = document.getElementById('link_parent_id').value;
    const studentId = document.getElementById('link_student_id').value;

    if (!parentId || !studentId) {
      alert('Please select both a parent and a student.');
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/students/${studentId}`, {
        method: 'PUT',
        headers: getHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ parent_id: parseInt(parentId, 10) })
      });

      if (res.ok) {
        alert('Parent and student linked successfully!');
        await loadData();
      } else {
        const err = await res.json();
        alert(`Error: ${err.detail || 'Could not link accounts'}`);
      }
    } catch (e) {
      alert(`Error: ${e.message}`);
    }
  });
}

// ── Modal Handlers for Custom Role ─────────────────────────────────────────────

window.openAddRoleModal = function() {
  const modal = document.getElementById('addRoleModal');
  if (modal) modal.style.display = 'flex';
};

window.closeAddRoleModal = function() {
  const modal = document.getElementById('addRoleModal');
  if (modal) modal.style.display = 'none';
};

window.handleCreateRole = async function(event) {
  event.preventDefault();
  const nameInput = document.getElementById('newRoleName');
  const roleName = nameInput.value.trim();
  if (!roleName) return;

  try {
    const res = await fetch(`${API_BASE}/auth/roles`, {
      method: 'POST',
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ name: roleName })
    });

    if (res.ok) {
      alert(`Role '${roleName}' created successfully!`);
      closeAddRoleModal();
      nameInput.value = '';
      await loadRoles();
    } else {
      const err = await res.json();
      alert(`Error creating role: ${err.detail}`);
    }
  } catch (error) {
    alert(`Error: ${error.message}`);
  }
};

// ── Impersonation ──────────────────────────────────────────────────────────────

async function impersonateUser(userId, username) {
  if (!confirm(`Are you sure you want to view the portal as "${username}" without entering their password?`)) return;

  try {
    const response = await fetch(`${API_BASE}/auth/impersonate/${userId}`, {
      method: 'POST',
      headers: getHeaders()
    });

    if (!response.ok) {
      const err = await response.json();
      throw new Error(err.detail || 'Could not switch user session');
    }

    const data = await response.json();

    const adminBackup = {
      accessToken: localStorage.getItem('accessToken') || sessionStorage.getItem('accessToken'),
      userId: localStorage.getItem('userId') || sessionStorage.getItem('userId'),
      username: localStorage.getItem('username') || sessionStorage.getItem('username'),
      userRole: localStorage.getItem('userRole') || sessionStorage.getItem('userRole'),
      activeRole: localStorage.getItem('activeRole') || sessionStorage.getItem('activeRole'),
      userRoles: localStorage.getItem('userRoles') || sessionStorage.getItem('userRoles')
    };

    sessionStorage.setItem('_admin_backup_session', JSON.stringify(adminBackup));
    localStorage.setItem('_admin_backup_session', JSON.stringify(adminBackup));

    sessionStorage.setItem('accessToken', data.access_token);
    sessionStorage.setItem('userId', String(data.user_id));
    sessionStorage.setItem('username', data.username);
    sessionStorage.setItem('userRole', data.role);
    sessionStorage.setItem('activeRole', data.role);
    sessionStorage.setItem('userRoles', JSON.stringify(data.roles));
    sessionStorage.setItem('is_impersonating', 'true');
    sessionStorage.setItem('impersonator_username', data.impersonator_username);

    localStorage.setItem('accessToken', data.access_token);
    localStorage.setItem('userId', String(data.user_id));
    localStorage.setItem('username', data.username);
    localStorage.setItem('userRole', data.role);
    localStorage.setItem('activeRole', data.role);
    localStorage.setItem('userRoles', JSON.stringify(data.roles));
    localStorage.setItem('is_impersonating', 'true');
    localStorage.setItem('impersonator_username', data.impersonator_username);

    window.location.href = 'dashboard.html';
  } catch (error) {
    alert('Error: ' + error.message);
  }
}

window.impersonateUser = impersonateUser;

initSuperAdminTenantFilter();
loadRoles();
loadData();

