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
    let url = `${API_BASE}/subjects/`;
    if (mode === 'SHS_ONLY') {
      url += '?exclude_basic=true';
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

    if (query) {
      data = data.filter(item => 
        (item.name && item.name.toLowerCase().includes(query)) ||
        (item.code && item.code.toLowerCase().includes(query))
      );
    }

    if (data.length === 0) {
      container.innerHTML = '<p style="opacity:0.7;">No subjects match your search.</p>';
      return;
    }

    const isAdmin = _userIsAdmin();

    container.innerHTML = `<ul>${data.map((item) => {
      const level = item.school_level || 'SHS';
      const levelColor = level === 'Basic' ? '#0d6efd' : level === 'STEM' ? '#6f42c1' : '#198754';
      return `
      <li style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; border-bottom: 1px solid var(--border-color, #eee); padding-bottom: 6px;">
        <div>
          <strong>${item.name}</strong> ${item.code ? `<span style="opacity:0.8; font-size:0.85rem;">(${item.code})</span>` : ''}
          <span style="font-size:0.75rem; background-color:${levelColor}; color:#fff; padding:2px 6px; border-radius:10px; margin-left:6px;">${level}</span>
          <span style="font-size:0.8rem; opacity:0.8; margin-left:4px;">• ${item.is_core ? 'Core' : 'Elective'}</span>
        </div>
        ${isAdmin ? `
        <div>
          <button type="button" data-edit="${item.id}" data-name="${item.name}" data-code="${item.code ?? ''}" data-iscore="${item.is_core}" data-level="${level}" class="btn" style="padding:4px 8px; font-size:0.85rem;">Edit</button>
          <button type="button" data-delete="${item.id}" class="btn danger" style="padding:4px 8px; font-size:0.85rem;">Delete</button>
        </div>` : ''}
      </li>`;
    }).join('')}</ul>`;
  } catch (error) {
    container.textContent = 'Unable to load subjects.';
  }
}

function editSubject(id, name, code, isCore, schoolLevel) {
  document.getElementById('subjectId').value = id;
  document.getElementById('subjectName').value = name;
  document.getElementById('subjectCode').value = code;
  document.getElementById('subjectIsCore').value = String(isCore);
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
}

if (form) {
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const id = document.getElementById('subjectId').value;
    const levelSelect = document.getElementById('subjectSchoolLevel');
    const payload = {
      name: document.getElementById('subjectName').value,
      code: document.getElementById('subjectCode').value.trim() || null,
      is_core: document.getElementById('subjectIsCore').value === 'true',
      school_level: levelSelect ? levelSelect.value : 'SHS',
    };

    const response = await fetch(`${API_BASE}/subjects/${id ? id : ''}`, {
      method: id ? 'PUT' : 'POST',
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      alert('Could not save subject.');
      return;
    }

    resetForm();
    loadSubjects();
  });
}

container.addEventListener('click', async (event) => {
  const deleteId = event.target.getAttribute('data-delete');
  const editId = event.target.getAttribute('data-edit');

  if (deleteId) {
    if (!confirm('Delete this subject?')) return;
    await fetch(`${API_BASE}/subjects/${deleteId}`, { method: 'DELETE', headers: getHeaders() });
    loadSubjects();
  }

  if (editId) {
    const name = event.target.getAttribute('data-name');
    const code = event.target.getAttribute('data-code');
    const isCore = event.target.getAttribute('data-iscore') === 'true';
    const level = event.target.getAttribute('data-level') || 'SHS';
    editSubject(editId, name, code, isCore, level);
  }
});

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
