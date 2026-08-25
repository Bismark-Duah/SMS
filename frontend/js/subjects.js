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

const _ADMIN_ROLES = new Set([
  'admin', 'super_admin', 'headmaster', 'headmistress',
  'assistant_headmaster_academic', 'assistant_head_academic',
  'assistant_headmaster_admin', 'assistant_head_admin',
  'assistant_headmaster_domestic', 'assistant_head_domestic',
]);
function _userIsAdmin() {
  try {
    const activeRole = (localStorage.getItem('activeRole') || localStorage.getItem('userRole') || '').toLowerCase();
    return _ADMIN_ROLES.has(activeRole);
  } catch { return false; }
}

const form = document.getElementById('subjectForm');
const container = document.getElementById('subjectList');
const searchInput = document.getElementById('subjectSearchInput');
const statusFilter = document.getElementById('subjectStatusFilter');
const archiveModal = document.getElementById('archivePromptModal');
const archiveMsg = document.getElementById('archivePromptMsg');
const confirmArchiveBtn = document.getElementById('confirmArchiveBtn');
const closeArchiveModalBtn = document.getElementById('closeArchiveModalBtn');

let pendingArchiveSubjectId = null;

function applySchoolModeUI() {
  const mode = (localStorage.getItem('school_mode') || 'COMBINED').toUpperCase();
  const formLevelSelect = document.getElementById('subjectSchoolLevel');
  if (formLevelSelect) {
    if (mode === 'SHS_ONLY') {
      const formBasicOpt = formLevelSelect.querySelector('option[value="Basic"]');
      if (formBasicOpt) formBasicOpt.remove();
      if (formLevelSelect.value === 'Basic') formLevelSelect.value = 'SHS';
    } else if (mode === 'BASIC_ONLY') {
      const formShsOpt = formLevelSelect.querySelector('option[value="SHS"]');
      const formStemOpt = formLevelSelect.querySelector('option[value="STEM"]');
      if (formShsOpt) formShsOpt.remove();
      if (formStemOpt) formStemOpt.remove();
      formLevelSelect.value = 'Basic';
    }
  }
}

async function loadSubjects() {
  applySchoolModeUI();
  
  if (searchInput) {
    if (!searchInput.dataset.userTyped && document.activeElement !== searchInput) {
      searchInput.value = '';
    }
    if (!searchInput.dataset.initialized) {
      searchInput.setAttribute('autocomplete', 'new-password');
      searchInput.addEventListener('input', () => {
        searchInput.dataset.userTyped = 'true';
      });
      searchInput.dataset.initialized = 'true';
    }
  }

  try {
    const mode = (localStorage.getItem('school_mode') || 'COMBINED').toUpperCase();
    const query = searchInput ? searchInput.value.trim().toLowerCase() : '';
    const statusVal = statusFilter ? statusFilter.value : 'active';

    let url = `${API_BASE}/subjects/?include_inactive=true`;
    if (mode === 'SHS_ONLY') {
      url += '&exclude_basic=true';
    }

    const response = await fetch(url, { headers: getHeaders() });
    let data = await response.json();

    if (!Array.isArray(data)) {
      container.innerHTML = '<p style="opacity:0.7;">Unable to parse subjects.</p>';
      return;
    }

    if (mode === 'SHS_ONLY') {
      data = data.filter(item => (item.school_level || 'SHS') !== 'Basic');
    } else if (mode === 'BASIC_ONLY') {
      data = data.filter(item => (item.school_level || 'Basic') === 'Basic');
    }

    // Status filtering
    if (statusVal === 'active') {
      data = data.filter(item => item.is_active !== false);
    } else if (statusVal === 'archived') {
      data = data.filter(item => item.is_active === false);
    }

    if (query) {
      data = data.filter(item => 
        (item.name && item.name.toLowerCase().includes(query)) ||
        (item.code && item.code.toLowerCase().includes(query))
      );
    }

    if (data.length === 0) {
      container.innerHTML = '<p style="opacity:0.7; padding:12px 0;">No subjects found for this selection.</p>';
      return;
    }

    const isAdmin = _userIsAdmin();

    container.innerHTML = `<ul style="list-style:none; padding:0; margin:0;">${data.map((item) => {
      const level = item.school_level || 'SHS';
      const levelColor = level === 'Basic' ? '#0d6efd' : level === 'STEM' ? '#6f42c1' : '#198754';
      const isActive = item.is_active !== false;
      const opacityStyle = isActive ? '1' : '0.65';
      const statusBadge = isActive 
        ? '<span style="font-size:0.72rem; background:rgba(34,197,94,0.15); color:#22c55e; border:1px solid rgba(34,197,94,0.3); padding:2px 6px; border-radius:10px; font-weight:600; margin-left:6px;">🟢 Active</span>'
        : '<span style="font-size:0.72rem; background:rgba(148,163,184,0.15); color:var(--text-secondary); border:1px solid rgba(148,163,184,0.3); padding:2px 6px; border-radius:10px; font-weight:600; margin-left:6px;">⚪ Archived</span>';

      return `
      <li style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; border-bottom: 1px solid var(--border-color, #eee); padding: 8px 4px; opacity:${opacityStyle}; transition:all 0.2s;">
        <div>
          <strong style="${!isActive ? 'text-decoration:line-through; opacity:0.8;' : ''}">${item.name}</strong> 
          ${item.code ? `<span style="opacity:0.8; font-size:0.85rem;">(${item.code})</span>` : ''}
          <span style="font-size:0.75rem; background-color:${levelColor}; color:#fff; padding:2px 6px; border-radius:10px; margin-left:6px;">${level}</span>
          <span style="font-size:0.8rem; opacity:0.8; margin-left:4px;">• ${item.is_core ? 'Core' : 'Elective'}</span>
          ${statusBadge}
        </div>
        ${isAdmin ? `
        <div style="display:flex; gap:6px; align-items:center;">
          <button type="button" data-edit="${item.id}" data-name="${item.name}" data-code="${item.code ?? ''}" data-iscore="${item.is_core}" data-isactive="${isActive}" data-level="${level}" class="btn" style="padding:4px 8px; font-size:0.82rem;">✏️ Edit</button>
          <button type="button" data-toggle="${item.id}" data-name="${item.name}" data-isactive="${isActive}" class="btn" style="padding:4px 8px; font-size:0.82rem; background:${isActive ? 'rgba(234,179,8,0.15)' : 'rgba(34,197,94,0.15)'}; border:1px solid ${isActive ? 'rgba(234,179,8,0.4)' : 'rgba(34,197,94,0.4)'};">${isActive ? '📦 Archive' : '🔄 Reactivate'}</button>
          <button type="button" data-delete="${item.id}" data-name="${item.name}" class="btn danger" style="padding:4px 8px; font-size:0.82rem;">🗑️ Delete</button>
        </div>` : ''}
      </li>`;
    }).join('')}</ul>`;
  } catch (error) {
    container.textContent = 'Unable to load subjects.';
  }
}

function editSubject(id, name, code, isCore, schoolLevel, isActive = true) {
  document.getElementById('subjectId').value = id;
  document.getElementById('subjectName').value = name;
  document.getElementById('subjectCode').value = code;
  document.getElementById('subjectIsCore').value = String(isCore);
  const activeSelect = document.getElementById('subjectIsActive');
  if (activeSelect) activeSelect.value = String(isActive);

  const levelSelect = document.getElementById('subjectSchoolLevel');
  if (levelSelect && schoolLevel) {
    levelSelect.value = schoolLevel;
  }
  document.getElementById('subjectName').focus();
}

function resetForm() {
  if (form) form.reset();
  const subId = document.getElementById('subjectId');
  if (subId) subId.value = '';
  const activeSelect = document.getElementById('subjectIsActive');
  if (activeSelect) activeSelect.value = 'true';
}

if (form) {
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const id = document.getElementById('subjectId').value;
    const levelSelect = document.getElementById('subjectSchoolLevel');
    const activeSelect = document.getElementById('subjectIsActive');
    const payload = {
      name: document.getElementById('subjectName').value.trim(),
      code: document.getElementById('subjectCode').value.trim() || null,
      is_core: document.getElementById('subjectIsCore').value === 'true',
      is_active: activeSelect ? activeSelect.value === 'true' : true,
      school_level: levelSelect ? levelSelect.value : 'SHS',
    };

    const response = await fetch(`${API_BASE}/subjects/${id ? id : ''}`, {
      method: id ? 'PUT' : 'POST',
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      alert(err.detail || 'Could not save subject.');
      return;
    }

    resetForm();
    loadSubjects();
  });
}

container.addEventListener('click', async (event) => {
  const deleteBtn = event.target.closest('[data-delete]');
  const editBtn = event.target.closest('[data-edit]');
  const toggleBtn = event.target.closest('[data-toggle]');

  // 1. DELETE ACTION WITH PROTECTIVE INTERCEPT
  if (deleteBtn) {
    const deleteId = deleteBtn.getAttribute('data-delete');
    const subjectName = deleteBtn.getAttribute('data-name') || 'this subject';

    if (!confirm(`Are you sure you want to permanently delete "${subjectName}"?\n\nNote: If historical grades or records exist, permanent deletion will be prevented to protect student transcripts.`)) return;

    try {
      const resp = await fetch(`${API_BASE}/subjects/${deleteId}`, {
        method: 'DELETE',
        headers: getHeaders()
      });

      const resData = await resp.json().catch(() => ({}));

      if (!resp.ok) {
        // Dependency protection triggered (HTTP 400)
        pendingArchiveSubjectId = deleteId;
        if (archiveModal && archiveMsg) {
          archiveMsg.textContent = resData.detail || `Cannot delete "${subjectName}" because historical records are attached.`;
          archiveModal.style.display = 'flex';
        } else {
          alert(resData.detail || 'Cannot delete subject because dependent records exist.');
        }
        return;
      }

      loadSubjects();
    } catch (e) {
      alert('Network error while deleting subject.');
    }
  }

  // 2. EDIT ACTION
  if (editBtn) {
    const editId = editBtn.getAttribute('data-edit');
    const name = editBtn.getAttribute('data-name');
    const code = editBtn.getAttribute('data-code');
    const isCore = editBtn.getAttribute('data-iscore') === 'true';
    const isActive = editBtn.getAttribute('data-isactive') === 'true';
    const level = editBtn.getAttribute('data-level') || 'SHS';
    editSubject(editId, name, code, isCore, level, isActive);
  }

  // 3. ARCHIVE / REACTIVATE TOGGLE
  if (toggleBtn) {
    const toggleId = toggleBtn.getAttribute('data-toggle');
    const subjectName = toggleBtn.getAttribute('data-name') || 'Subject';
    const isCurrentlyActive = toggleBtn.getAttribute('data-isactive') === 'true';
    const actionName = isCurrentlyActive ? 'Archive / Discontinue' : 'Reactivate';

    if (!confirm(`Do you want to ${actionName} "${subjectName}"?`)) return;

    try {
      const resp = await fetch(`${API_BASE}/subjects/${toggleId}/toggle-status`, {
        method: 'POST',
        headers: getHeaders()
      });
      if (resp.ok) {
        loadSubjects();
      } else {
        const err = await resp.json().catch(() => ({}));
        alert(err.detail || 'Could not update subject status.');
      }
    } catch (e) {
      alert('Network error updating status.');
    }
  }
});

// Modal Action Handlers
if (closeArchiveModalBtn) {
  closeArchiveModalBtn.addEventListener('click', () => {
    if (archiveModal) archiveModal.style.display = 'none';
    pendingArchiveSubjectId = null;
  });
}

if (confirmArchiveBtn) {
  confirmArchiveBtn.addEventListener('click', async () => {
    if (!pendingArchiveSubjectId) return;
    try {
      const resp = await fetch(`${API_BASE}/subjects/${pendingArchiveSubjectId}/toggle-status`, {
        method: 'POST',
        headers: getHeaders()
      });
      if (resp.ok) {
        if (archiveModal) archiveModal.style.display = 'none';
        pendingArchiveSubjectId = null;
        loadSubjects();
      } else {
        const err = await resp.json().catch(() => ({}));
        alert(err.detail || 'Could not archive subject.');
      }
    } catch (e) {
      alert('Network error archiving subject.');
    }
  });
}

const cancelBtn = document.getElementById('cancelSubjectBtn');
if (cancelBtn) cancelBtn.addEventListener('click', resetForm);

if (!_userIsAdmin()) {
  const formCard = form && form.closest('.card, section, .form-card');
  if (formCard) formCard.style.display = 'none';
  else if (form) form.style.display = 'none';

  const notice = document.createElement('div');
  notice.style = 'margin-bottom:14px; padding:10px 16px; background:rgba(99,102,241,.1); border:1px solid rgba(99,102,241,.3); border-radius:8px; font-size:.88rem; color:var(--text-secondary);';
  notice.textContent = 'ℹ️ You are viewing subjects assigned to your department. Subject creation and editing is restricted to Administrators.';
  if (container && container.parentElement) {
    container.parentElement.insertBefore(notice, container);
  }
}

loadSubjects();
