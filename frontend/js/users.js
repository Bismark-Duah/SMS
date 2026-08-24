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

const ROLE_DISPLAY_NAMES = {
  super_admin: 'Super Admin',
  admin: 'School Admin / Headmaster',
  assistant_headmaster_academic: 'Assistant Headmaster/Mistress (Academic)',
  assistant_headmaster_domestic: 'Assistant Headmaster/Mistress (Domestic)',
  assistant_headmaster_admin: 'Assistant Headmaster/Mistress (Administration)',
  hod: 'HOD (Head of Department)',
  form_master: 'Form Master',
  form_mistress: 'Form Mistress',
  senior_house_master: 'Senior House Master',
  senior_house_mistress: 'Senior House Mistress',
  house_master: 'House Master',
  assistant_house_master: 'Assistant House Master',
  house_mistress: 'House Mistress',
  assistant_house_mistress: 'Assistant House Mistress',
  bursar: 'School Accountant / Bursar',
  storekeeper: 'Storekeeper (Asset & Books)',
  security_officer: 'Security Officer (Gate Exeats)',
  teacher: 'Teacher',
  student: 'Student',
  parent: 'Parent'
};

function formatRoleTitle(name) {
  if (ROLE_DISPLAY_NAMES[name]) return ROLE_DISPLAY_NAMES[name];
  return name.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
}

async function loadRoles() {
  const container = document.getElementById('rolesContainer');
  if (!container) return;

  try {
    const res = await fetch(`${API_BASE}/auth/roles`, { headers: getHeaders() });
    if (!res.ok) throw new Error('Failed to fetch roles');
    const roles = await res.json();

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
      'senior_house_master', 'senior_house_mistress',
      'house_master', 'assistant_house_master',
      'house_mistress', 'assistant_house_mistress',
      'assistant_headmaster_domestic', 'assistant_head_domestic',
      'security_officer'
    ];

    const filteredRoles = roles.filter(r => {
      const rName = r.name.toLowerCase();
      if (!isBoarding && BOARDING_ROLES.includes(rName)) return false;
      if (isBasicOnly && rName === 'hod') return false;
      return true;
    });

    container.innerHTML = `<div style="display:grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 8px;">
      ${filteredRoles.map(r => {
        const title = formatRoleTitle(r.name);
        const isDefaultChecked = r.name === 'teacher' ? 'checked' : '';
        return `
          <label style="display:flex; align-items:center; gap:6px; font-size:0.85rem; background:rgba(255,255,255,0.04); padding:6px 10px; border-radius:4px; cursor:pointer;">
            <input type="checkbox" name="user_role" value="${r.name}" ${isDefaultChecked} />
            <span>${title}</span>
          </label>
        `;
      }).join('')}
    </div>`;

    // Mutual exclusion: selecting Assistant Head unchecks generic Admin to enforce Principle of Least Privilege
    const roleInputs = container.querySelectorAll('input[name="user_role"]');
    roleInputs.forEach(input => {
      input.addEventListener('change', (e) => {
        const val = e.target.value;
        const isChecked = e.target.checked;
        const assistHeadRoles = [
          'assistant_headmaster_academic', 'assistant_headmaster_domestic', 'assistant_headmaster_admin',
          'assistant_head_academic', 'assistant_head_domestic', 'assistant_head_admin'
        ];
        if (isChecked) {
          if (assistHeadRoles.includes(val)) {
            roleInputs.forEach(other => {
              if (other.value === 'admin') other.checked = false;
            });
          } else if (val === 'admin') {
            roleInputs.forEach(other => {
              if (assistHeadRoles.includes(other.value)) other.checked = false;
            });
          }
        }
      });
    });
  } catch (err) {
    console.error('Error loading roles:', err);
    container.innerHTML = '<span style="color:var(--danger, #ef4444);">Failed to load roles.</span>';
  }
}

let selectedSchoolScope = localStorage.getItem('school_id') || 'system_only';

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

async function loadData() {
  const userList = document.getElementById('userList');
  const studentSelect = document.getElementById('link_student_id');
  const parentSelect = document.getElementById('link_parent_id');

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

    if (!users || !users.length) {
      userList.innerHTML = '<div style="padding:16px; text-align:center; opacity:0.7;">No users found in current scope.</div>';
      return;
    }

    // Render User List
    const currentUserId = parseInt(localStorage.getItem('userId') || sessionStorage.getItem('userId') || '0', 10);

    userList.innerHTML = `<ul>${users.map(u => {
      const isParent = u.roles.some(r => r.name === 'parent');
      let childrenInfo = '';
      if (isParent) {
        const linked = students.filter(s => String(s.parent_id) === String(u.id));
        childrenInfo = linked.length 
          ? ` <span style="font-size:.75rem; color:#10b981; font-weight:600;">👨‍👩‍👧 (${linked.length} linked: ${linked.map(c=>c.full_name).join(', ')})</span>`
          : ` <span style="font-size:.75rem; opacity:.7;">(No children linked)</span>`;
      }
      
      const roleBadges = u.roles.length 
        ? u.roles.map(r => formatRoleTitle(r.name)).join(', ')
        : 'No Role';

      const genderBadge = u.gender ? `<span style="font-size:0.75rem; opacity:0.7; margin-left:6px;">(${u.gender})</span>` : '';

      const isUserAdminOrExec = u.roles.some(r => {
        const rName = (r.name || '').toLowerCase();
        return rName === 'admin' || rName === 'super_admin' || rName.includes('assistant_head');
      });

      const canImpersonate = (u.id !== currentUserId) && !isUserAdminOrExec && (selectedSchoolScope !== 'system_only');

      const impersonateBtn = canImpersonate ? `
        <button type="button" onclick="impersonateUser(${u.id}, '${u.username}')" style="background:#0284c7; color:#fff; border:none; padding:3px 9px; border-radius:4px; font-size:0.75rem; font-weight:600; cursor:pointer; margin-left:8px;" title="View portal as ${u.username}">
          👤 View As
        </button>
      ` : '';

      return `<li style="margin-bottom:8px; padding:8px 12px; background:rgba(255,255,255,0.02); border-radius:6px; border:1px solid rgba(255,255,255,0.05); display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:6px;">
        <div>
          <strong>${u.username}</strong> ${genderBadge}
          <span style="display:inline-block; margin-left:8px; font-size:0.8rem; color:var(--primary-color, #6366f1); font-weight:500;">
            (${roleBadges})
          </span>
          ${childrenInfo}
        </div>
        <div>
          ${impersonateBtn}
        </div>
      </li>`;
    }).join('')}</ul>`;

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
  }
}

// User Creation Form
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
      username: document.getElementById('username').value,
      email: document.getElementById('email').value,
      password: document.getElementById('password').value,
      roles: checkedRoles
    };

    const res = await fetch(`${API_BASE}/auth/users`, {
      method: 'POST',
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload)
    });

    if (res.ok) {
      alert('User created successfully!');
      userForm.reset();
      loadRoles();
      loadData();
    } else {
      const err = await res.json();
      alert(`Error: ${err.detail}`);
    }
  });
}

// Modal Handlers for Custom Role
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

// Initial Load
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
