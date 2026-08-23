const API_BASE = window.API_BASE || (window.location.origin.includes('http') ? (window.location.origin + '/api') : 'http://127.0.0.1:8000/api');

const token = localStorage.getItem('accessToken');
if (!token) {
  window.location.href = 'auth.html';
}

// ── Role Helpers ──────────────────────────────────────────────────────────────
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

function getHeaders(headers = {}) {
  const token = localStorage.getItem('accessToken');
  const h = { ...headers };
  if (token) h['Authorization'] = `Bearer ${token}`;
  const schoolId = localStorage.getItem('school_id');
  if (schoolId) h['X-School-Id'] = schoolId;
  return h;
}

const form = document.getElementById('classForm');
const container = document.getElementById('classList');

async function loadStages() {
  const select = document.getElementById('classLevel'); // Reusing existing ID
  try {
    const response = await fetch(`${API_BASE}/classes/stages`, { headers: getHeaders() });
    const stages = await response.json();
    select.innerHTML = '<option value="">Select Stage...</option>' + 
      stages.map(s => `<option value="${s.id}">${s.name}</option>`).join('');
  } catch (error) {
    console.error('Error loading stages:', error);
  }
}

async function loadPrograms() {
  const select = document.getElementById('classProgram');
  const schoolMode = (localStorage.getItem('school_mode') || 'COMBINED').toUpperCase();
  if (select && select.parentElement && schoolMode === 'BASIC_ONLY') {
    select.parentElement.style.display = 'none';
    return;
  }
  try {
    const response = await fetch(`${API_BASE}/programs/`, { headers: getHeaders() });
    const programs = await response.json();
    select.innerHTML = '<option value="">Select Program (None)...</option>' + 
      programs.map(p => `<option value="${p.id}">${p.name}</option>`).join('');
  } catch (error) {
    console.error('Error loading programs:', error);
  }
}

let allClassesData = [];

function resetClassForm() {
  form.reset();
  document.getElementById('classId').value = '';
  const formTitle = document.getElementById('formTitle');
  const saveBtn = document.getElementById('saveClassBtn');
  const formCard = document.getElementById('classFormCard');

  if (formTitle) formTitle.textContent = 'Add Class';
  if (saveBtn) saveBtn.textContent = 'Save Class';
  if (formCard) formCard.style.border = '';
}

function editClass(id) {
  let item = allClassesData.find(c => String(c.id) === String(id));
  
  const applyEditData = (data) => {
    document.getElementById('classId').value = data.id;
    document.getElementById('className').value = data.name;
    document.getElementById('classLevel').value = data.stage_id || '';
    document.getElementById('classProgram').value = data.program_id || '';
    document.getElementById('classFormMaster').value = data.form_master_id || '';

    const formTitle = document.getElementById('formTitle');
    const saveBtn = document.getElementById('saveClassBtn');
    const formCard = document.getElementById('classFormCard');

    if (formTitle) formTitle.textContent = `Edit Class: ${data.name}`;
    if (saveBtn) saveBtn.textContent = `Update ${data.name}`;
    if (formCard) formCard.style.border = '2px solid var(--primary-color, #6366f1)';

    if (formCard) formCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
  };

  if (item) {
    applyEditData(item);
  } else {
    fetch(`${API_BASE}/classes/${id}`, { headers: getHeaders() })
      .then(res => res.json())
      .then(data => applyEditData(data))
      .catch(err => {
        console.error('Error fetching class details:', err);
        alert('Could not find class details for editing.');
      });
  }
}

async function loadClasses() {
  try {
    const response = await fetch(`${API_BASE}/classes/`, { headers: getHeaders() });
    const data = await response.json();

    if (!Array.isArray(data) || data.length === 0) {
      container.innerHTML = 'No classes assigned to you yet.';
      allClassesData = [];
      return;
    }

    allClassesData = data;
    const isAdmin = _userIsAdmin();

    container.innerHTML = `<ul>${data.map((item) => `
      <li style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; border-bottom: 1px solid var(--border-color); padding-bottom: 8px;">
        <span>
          <strong>${item.name}</strong> 
          <small style="opacity:.6; margin-left:8px;">Stage: ${item.stage_name || 'N/A'}</small>
          ${item.program_name ? `<small style="opacity:.6; margin-left:8px;">Program: ${item.program_name}</small>` : ''}
          <small style="opacity:.6; margin-left:8px; color:#22d3ee;">Form Master: ${item.form_master_name || 'None'}</small>
        </span>
        <div>
          ${isAdmin ? `<button type="button" class="btn primary sm" style="padding:4px 10px; font-size:0.85rem; margin-right:4px;" onclick="editClass(${item.id})">✏️ Edit</button>` : ''}
          <button type="button" class="btn sm" style="padding:4px 10px; font-size:0.85rem; margin-right:4px;" onclick="openSubjectsModal(${item.id}, '${item.name.replace(/'/g, "\\'")}', ${item.program_id || 'null'})">📚 Subjects</button>
          ${isAdmin ? `<button type="button" data-delete="${item.id}" class="btn danger sm" style="padding:4px 10px; font-size:0.85rem;">Delete</button>` : ''}
        </div>
      </li>
    `).join('')}</ul>`;
  } catch (error) {
    container.textContent = 'Unable to load classes.';
  }
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const id = document.getElementById('classId').value;
  const programSelectVal = document.getElementById('classProgram').value;
  const formMasterSelectVal = document.getElementById('classFormMaster').value;
  const payload = {
    name: document.getElementById('className').value,
    stage_id: parseInt(document.getElementById('classLevel').value),
    program_id: programSelectVal ? parseInt(programSelectVal) : null,
    form_master_id: formMasterSelectVal ? parseInt(formMasterSelectVal) : null,
  };

  const response = await fetch(`${API_BASE}/classes/${id ? id : ''}`, {
    method: id ? 'PUT' : 'POST',
    headers: getHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    alert('Could not save class.');
    return;
  }

  resetClassForm();
  loadClasses();
});

container.addEventListener('click', async (event) => {
  const deleteId = event.target.getAttribute('data-delete');

  if (deleteId) {
    if (!confirm('Delete this class?')) return;
    await fetch(`${API_BASE}/classes/${deleteId}`, { method: 'DELETE', headers: getHeaders() });
    loadClasses();
  }
});

document.getElementById('cancelClassBtn').addEventListener('click', resetClassForm);

async function loadTeachers() {
  const select = document.getElementById('classFormMaster');
  try {
    const response = await fetch(`${API_BASE}/auth/users`, { headers: getHeaders() });
    const users = await response.json();
    const teachers = users.filter(u => u.roles && u.roles.some(r => !['student', 'parent'].includes(r.name.toLowerCase())));
    select.innerHTML = '<option value="">Select Form Master/Mistress...</option>' + 
      teachers.map(t => `<option value="${t.id}">${t.username} (${t.gender || 'Staff'})</option>`).join('');
  } catch (error) {
    console.error('Error loading teachers:', error);
  }
}

loadStages();
loadPrograms();
if (_userIsAdmin()) {
  loadTeachers();
} else {
  // Hide create/edit form for non-admins — read-only view
  const formCard = form && form.closest('.card, section, .form-card');
  if (formCard) formCard.style.display = 'none';
  else if (form) form.style.display = 'none';

  // Show a read-only notice above the list
  const notice = document.createElement('div');
  notice.style = 'margin-bottom:14px; padding:10px 16px; background:rgba(99,102,241,.1); border:1px solid rgba(99,102,241,.3); border-radius:8px; font-size:.88rem; color:var(--text-secondary);';
  notice.textContent = 'ℹ️ You are viewing only the class sections assigned to you. Class creation and editing is restricted to Administrators.';
  container.parentElement.insertBefore(notice, container);
}
loadClasses();
window.editClass = editClass;

// --- Manage Subjects Modal Logic ---
const subjectsModal = document.getElementById('subjectsModal');
const modalClassName = document.getElementById('modalClassName');
const modalClassId = document.getElementById('modalClassId');
const subjectsCheckboxList = document.getElementById('subjectsCheckboxList');
const subjectsForm = document.getElementById('subjectsForm');
const closeSubjectsModalBtn = document.getElementById('closeSubjectsModalBtn');

let currentClassProgramId = null;
let allSubjectsList = [];
let programSubjectsList = [];
let classRawSubjectsList = [];

async function openSubjectsModal(classId, className, programId) {
  modalClassId.value = classId;
  modalClassName.textContent = `Class Section: ${className}`;
  subjectsCheckboxList.innerHTML = '<p style="opacity:.6">Loading subjects...</p>';
  subjectsModal.style.display = 'flex';
  
  currentClassProgramId = programId;
  const toggleContainer = document.getElementById('overrideToggleContainer');
  const toggle = document.getElementById('showAllSubjectsToggle');
  
  if (currentClassProgramId) {
    toggleContainer.style.display = 'block';
  } else {
    toggleContainer.style.display = 'none';
    toggle.checked = true; // No program, so manual override is forced
  }

  try {
    const isShsMode = (localStorage.getItem('school_mode') || '').toUpperCase() === 'SHS_ONLY';
    const subUrl = (isShsMode || currentClassProgramId) ? `${API_BASE}/subjects/?exclude_basic=true` : `${API_BASE}/subjects/`;
    const promises = [
      fetch(subUrl, { headers: getHeaders() })
    ];
    if (currentClassProgramId) {
      promises.push(fetch(`${API_BASE}/programs/${currentClassProgramId}/subjects`, { headers: getHeaders() }));
      promises.push(fetch(`${API_BASE}/classes/${classId}/subjects?raw=true`, { headers: getHeaders() }));
    } else {
      promises.push(fetch(`${API_BASE}/classes/${classId}/subjects`, { headers: getHeaders() }));
    }

    const responses = await Promise.all(promises);
    for (const r of responses) {
      if (!r.ok) throw new Error('Failed to fetch subjects info');
    }

    allSubjectsList = await responses[0].json();
    
    if (currentClassProgramId) {
      programSubjectsList = await responses[1].json();
      classRawSubjectsList = await responses[2].json();
      
      // Override is active if class has its own raw subjects saved
      const isOverridden = classRawSubjectsList.length > 0;
      toggle.checked = isOverridden;
    } else {
      programSubjectsList = [];
      classRawSubjectsList = await responses[1].json();
      toggle.checked = true;
    }

    renderSubjectCheckboxes();
  } catch (error) {
    console.error('Error opening subjects modal:', error);
    subjectsCheckboxList.innerHTML = '<p style="color:var(--error-color)">Error loading subjects.</p>';
  }
}

function renderSubjectCheckboxes() {
  const toggle = document.getElementById('showAllSubjectsToggle');
  const isManual = toggle.checked;
  
  if (allSubjectsList.length === 0) {
    subjectsCheckboxList.innerHTML = '<p style="opacity:.6">No subjects available in the system. Add subjects first.</p>';
    return;
  }

  const activeSet = new Set(
    (currentClassProgramId && !isManual)
      ? programSubjectsList.map(s => s.id)
      : classRawSubjectsList.map(s => s.id)
  );

  const isDisabledMode = !!(currentClassProgramId && !isManual);
  const coreSubjects = allSubjectsList.filter(s => s.is_core);
  const electiveSubjects = allSubjectsList.filter(s => !s.is_core);

  const renderItem = (sub) => {
    const isChecked = activeSet.has(sub.id);
    const chipBg   = isChecked  ? 'rgba(59,130,246,0.15)'    : 'rgba(255,255,255,0.04)';
    const chipBdr  = isChecked  ? 'rgba(96,165,250,0.7)'     : 'rgba(255,255,255,0.1)';
    const checkBg  = isChecked  ? '#3b82f6'                  : 'transparent';
    const checkBdr = isChecked  ? '#3b82f6'                  : 'rgba(255,255,255,0.3)';
    const checkTxt = isChecked  ? '✓'                        : '';
    const disabledStyle = isDisabledMode ? 'opacity:0.5; cursor:not-allowed; pointer-events:none;' : 'cursor:pointer;';
    const onclickAttr  = isDisabledMode ? '' : `onclick="classSubjectChipToggle(this)"`;

    return `
      <label ${onclickAttr}
        style="display:flex; align-items:flex-start; gap:8px; padding:9px 11px; border-radius:8px;
               background:${chipBg}; border:1px solid ${chipBdr};
               transition:all 0.15s ease; user-select:none; ${disabledStyle}">
        <input type="checkbox" name="subjectIds" value="${sub.id}" ${isChecked ? 'checked' : ''} ${isDisabledMode ? 'disabled' : ''} style="display:none;" />
        <span style="margin-top:2px; width:15px; height:15px; border-radius:3px; border:1.5px solid ${checkBdr};
                     flex-shrink:0; display:flex; align-items:center; justify-content:center;
                     font-size:10px; background:${checkBg}; color:#fff; transition:all 0.15s;">${checkTxt}</span>
        <div style="flex:1; min-width:0;">
          <div style="font-size:0.85rem; font-weight:600; color:#f1f5f9; line-height:1.3;">${sub.name}</div>
          <div style="margin-top:2px;">
            <span style="font-size:0.7rem; padding:1px 7px; border-radius:10px;
                         background:${sub.is_core ? 'rgba(99,102,241,0.2)' : 'rgba(234,179,8,0.2)'};
                         color:${sub.is_core ? '#818cf8' : '#facc15'}; font-weight:600;">
              ${sub.code || (sub.is_core ? 'CORE' : 'ELECTIVE')}
            </span>
          </div>
        </div>
      </label>
    `;
  };

  let html = '';
  if (coreSubjects.length > 0) {
    html += `<div style="font-size:0.78rem; font-weight:700; text-transform:uppercase; letter-spacing:0.5px; color:#818cf8; margin:4px 0 8px 0;">📘 Core Subjects</div>`;
    html += `<div style="display:grid; grid-template-columns:repeat(auto-fill, minmax(175px, 1fr)); gap:6px; margin-bottom:16px;">`;
    html += coreSubjects.map(renderItem).join('');
    html += `</div>`;
  }

  if (electiveSubjects.length > 0) {
    html += `<div style="font-size:0.78rem; font-weight:700; text-transform:uppercase; letter-spacing:0.5px; color:#facc15; margin:4px 0 8px 0;">📙 Elective Subjects</div>`;
    html += `<div style="display:grid; grid-template-columns:repeat(auto-fill, minmax(175px, 1fr)); gap:6px;">`;
    html += electiveSubjects.map(renderItem).join('');
    html += `</div>`;
  }

  subjectsCheckboxList.innerHTML = html;
}

function classSubjectChipToggle(labelEl) {
  event.preventDefault();
  const cb = labelEl.querySelector('input[name="subjectIds"]');
  if (!cb || cb.disabled) return;
  cb.checked = !cb.checked;
  const span = labelEl.querySelector('span');
  if (cb.checked) {
    labelEl.style.borderColor = 'rgba(96,165,250,0.7)';
    labelEl.style.background  = 'rgba(59,130,246,0.15)';
    if (span) { span.style.background = '#3b82f6'; span.style.borderColor = '#3b82f6'; span.textContent = '✓'; }
  } else {
    labelEl.style.borderColor = 'rgba(255,255,255,0.1)';
    labelEl.style.background  = 'rgba(255,255,255,0.04)';
    if (span) { span.style.background = 'transparent'; span.style.borderColor = 'rgba(255,255,255,0.3)'; span.textContent = ''; }
  }
}

// Add event listener to the toggle
document.getElementById('showAllSubjectsToggle').addEventListener('change', (e) => {
  if (e.target.checked && classRawSubjectsList.length === 0) {
    // Copy program subjects to start with a default selection
    classRawSubjectsList = [...programSubjectsList];
  }
  renderSubjectCheckboxes();
});

closeSubjectsModalBtn.addEventListener('click', () => {
  subjectsModal.style.display = 'none';
});

subjectsForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const classId = modalClassId.value;
  const toggle = document.getElementById('showAllSubjectsToggle');
  
  let payload = [];
  if (!currentClassProgramId || toggle.checked) {
    const checkboxes = subjectsForm.querySelectorAll('input[name="subjectIds"]:checked');
    payload = Array.from(checkboxes).map(cb => parseInt(cb.value));
  } else {
    // If not manual override, we send [] to clear class-specific subjects so it inherits program subjects
    payload = [];
  }

  try {
    const response = await fetch(`${API_BASE}/classes/${classId}/subjects`, {
      method: 'POST',
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      throw new Error('Failed to save subject associations');
    }

    alert('Subjects updated successfully!');
    subjectsModal.style.display = 'none';
  } catch (error) {
    alert(`Could not save subjects: ${error.message}`);
  }
});

window.openSubjectsModal = openSubjectsModal;
window.classSubjectChipToggle = classSubjectChipToggle;

const loadPresetsBtn = document.getElementById('loadPresetsBtn');
if (loadPresetsBtn) {
  if (!_userIsAdmin()) {
    loadPresetsBtn.style.display = 'none';
  } else {
    loadPresetsBtn.addEventListener('click', async () => {
      if (!confirm("Load standard preset stages and classes (Creche, Nursery, KG, Primary, JHS, SHS)?")) return;
      try {
        const res = await fetch(`${API_BASE}/classes/presets`, {
          method: 'POST',
          headers: getHeaders()
        });
        const data = await res.json();
        alert(data.message || "Presets loaded successfully!");
        await loadStages();
        await loadClasses();
      } catch (err) {
        alert("Error loading presets: " + err.message);
      }
    });
  }
}
