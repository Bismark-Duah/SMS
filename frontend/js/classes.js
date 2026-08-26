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
let allStagesData = [];
let allProgramsData = [];

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

function filterClasses(query) {
  const q = (query || '').trim().toLowerCase();
  if (!q) {
    renderClassList(allClassesData);
    return;
  }
  const filtered = allClassesData.filter(c => 
    (c.name && c.name.toLowerCase().includes(q)) ||
    (c.stage_name && c.stage_name.toLowerCase().includes(q)) ||
    (c.program_name && c.program_name.toLowerCase().includes(q)) ||
    (c.form_master_name && c.form_master_name.toLowerCase().includes(q))
  );
  renderClassList(filtered);
}

function renderClassList(data) {
  const isAdmin = _userIsAdmin();

  if (!Array.isArray(data) || data.length === 0) {
    if (allClassesData.length === 0) {
      // ── Smart Onboarding Empty State (When 0 classes exist) ────────────────
      container.innerHTML = `
        <div style="text-align:center; padding:36px 16px; background:rgba(255,255,255,0.02); border:2px dashed var(--border-color); border-radius:12px;">
          <span style="font-size:2.8rem; display:block; margin-bottom:10px;">🏫</span>
          <h4 style="margin:0 0 6px; font-size:1.15rem; color:var(--text-primary);">No Classes Configured Yet</h4>
          <p style="margin:0 0 20px; font-size:0.88rem; color:var(--text-secondary); max-width:480px; margin-inline:auto;">
            Get your school structure running instantly using standard national presets or capacity-driven auto-generation.
          </p>
          <div style="display:flex; justify-content:center; gap:12px; flex-wrap:wrap;">
            ${isAdmin ? `
            <button type="button" onclick="loadDefaultPresets()" class="btn" style="font-size:0.85rem; padding:9px 16px;">⚡ Load Standard GES Stages & Classes</button>
            <button type="button" onclick="openSmartGenModal()" class="btn primary" style="font-size:0.85rem; padding:9px 18px; background:linear-gradient(135deg, #6366f1, #06b6d4); border:none; box-shadow:0 4px 12px rgba(99,102,241,0.35);">⚡ Auto-Generate from Enrolled Students</button>
            ` : '<p style="opacity:0.7;">No classes are currently assigned.</p>'}
          </div>
        </div>`;
    } else {
      container.innerHTML = '<p style="opacity:0.7; padding:12px 0;">No classes match your search query.</p>';
    }
    return;
  }

  container.innerHTML = `<ul style="list-style:none; padding:0; margin:0;">${data.map((item) => `
    <li style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; border-bottom: 1px solid var(--border-color); padding: 8px 4px;">
      <span>
        <strong>${item.name}</strong> 
        <small style="opacity:.65; margin-left:8px; background:rgba(255,255,255,0.06); padding:2px 6px; border-radius:4px;">${item.stage_name || 'N/A'}</small>
        ${item.program_name ? `<small style="opacity:.8; margin-left:6px; color:#818cf8; font-weight:600;">• ${item.program_name}</small>` : ''}
        <small style="opacity:.7; margin-left:8px; color:#22d3ee;">👤 Form Master: ${item.form_master_name || 'Unassigned'}</small>
      </span>
      <div style="display:flex; gap:6px; align-items:center;">
        ${isAdmin ? `<button type="button" class="btn primary sm" style="padding:4px 10px; font-size:0.82rem;" onclick="editClass(${item.id})">✏️ Edit</button>` : ''}
        <button type="button" class="btn sm" style="padding:4px 10px; font-size:0.82rem;" onclick="openSubjectsModal(${item.id}, '${item.name.replace(/'/g, "\\'")}', ${item.program_id || 'null'})">📚 Subjects</button>
        ${isAdmin ? `<button type="button" data-delete="${item.id}" data-name="${item.name}" class="btn danger sm" style="padding:4px 10px; font-size:0.82rem;">🗑️ Delete</button>` : ''}
      </div>
    </li>
  `).join('')}</ul>`;
}

async function loadClasses() {
  try {
    const response = await fetch(`${API_BASE}/classes/`, { headers: getHeaders() });
    const data = await response.json();

    if (!Array.isArray(data)) {
      container.innerHTML = '<p style="opacity:0.7;">Unable to load classes.</p>';
      allClassesData = [];
      return;
    }

    allClassesData = data;
    const searchInput = document.getElementById('classSearchInput');
    filterClasses(searchInput ? searchInput.value : '');
  } catch (error) {
    container.textContent = 'Unable to load classes.';
  }
}

async function loadStages() {
  const select = document.getElementById('classLevel');
  const batchSelect = document.getElementById('batchStageSelect');
  try {
    const response = await fetch(`${API_BASE}/classes/stages`, { headers: getHeaders() });
    const stages = await response.json();
    allStagesData = Array.isArray(stages) ? stages : [];
    
    const opts = '<option value="">Select Stage...</option>' + 
      allStagesData.map(s => `<option value="${s.id}" data-type="${s.school_type}">${s.name} (${s.school_type})</option>`).join('');
    
    if (select) select.innerHTML = opts;
    if (batchSelect) {
      batchSelect.innerHTML = opts;
      batchSelect.addEventListener('change', updateBatchPreview);
    }
  } catch (error) {
    console.error('Error loading stages:', error);
  }
}

async function loadPrograms() {
  const select = document.getElementById('classProgram');
  const batchSelect = document.getElementById('batchProgramSelect');
  const progLabel = document.getElementById('classProgramLabel');
  const batchProgGroup = document.getElementById('batchProgramGroup');
  const schoolMode = (localStorage.getItem('school_mode') || 'COMBINED').toUpperCase();

  if (schoolMode === 'BASIC_ONLY') {
    if (progLabel) progLabel.style.display = 'none';
    if (batchProgGroup) batchProgGroup.style.display = 'none';
    return;
  }

  try {
    const response = await fetch(`${API_BASE}/programs/`, { headers: getHeaders() });
    const programs = await response.json();
    allProgramsData = Array.isArray(programs) ? programs : [];
    
    const opts = '<option value="">Select Program (None)...</option>' + 
      allProgramsData.map(p => `<option value="${p.id}">${p.name}</option>`).join('');
    
    if (select) select.innerHTML = opts;
    if (batchSelect) {
      batchSelect.innerHTML = opts;
      batchSelect.addEventListener('change', updateBatchPreview);
    }
  } catch (error) {
    console.error('Error loading programs:', error);
  }
}

async function loadDefaultPresets() {
  if (!confirm("Load standard national stages and core classes (KG 1-2, Primary 1-6, JHS 1-3, SHS Form 1-3) based on your school mode?")) return;
  try {
    const res = await fetch(`${API_BASE}/classes/presets`, {
      method: 'POST',
      headers: getHeaders()
    });
    const data = await res.json();
    alert(data.message || "Presets loaded successfully!");
    await loadStages();
    await loadPrograms();
    await loadClasses();
  } catch (err) {
    alert("Error loading presets: " + err.message);
  }
}
window.loadDefaultPresets = loadDefaultPresets;

// ── Smart Generator Modal Handlers ───────────────────────────────────────────
function openSmartGenModal() {
  const modal = document.getElementById('smartGenModal');
  if (modal) {
    modal.style.display = 'flex';
    switchGenTab('auto');
    updateBatchPreview();
  }
}
function closeSmartGenModal() {
  const modal = document.getElementById('smartGenModal');
  if (modal) modal.style.display = 'none';
}
function switchGenTab(tab) {
  const autoTab = document.getElementById('tabContentAuto');
  const batchTab = document.getElementById('tabContentBatch');
  const autoBtn = document.getElementById('tabAutoGenBtn');
  const batchBtn = document.getElementById('tabBatchArmsBtn');

  if (tab === 'auto') {
    if (autoTab) autoTab.style.display = 'block';
    if (batchTab) batchTab.style.display = 'none';
    if (autoBtn) { autoBtn.className = 'btn primary'; }
    if (batchBtn) { batchBtn.className = 'btn'; }
  } else {
    if (autoTab) autoTab.style.display = 'none';
    if (batchTab) batchTab.style.display = 'block';
    if (autoBtn) { autoBtn.className = 'btn'; }
    if (batchBtn) { batchBtn.className = 'btn primary'; }
    updateBatchPreview();
  }
}

let currentSmartPreviewData = null;

async function previewSmartAllocation() {
  const cap = parseInt(document.getElementById('genTargetCapacity').value) || 45;
  const style = document.getElementById('genNamingStyle').value;
  const previewArea = document.getElementById('smartPreviewArea');
  const tableContainer = document.getElementById('smartPreviewTableContainer');
  const execBtn = document.getElementById('executeSmartGenBtn');

  try {
    const res = await fetch(`${API_BASE}/classes/smart-preview?target_capacity=${cap}&naming_style=${style}`, {
      headers: getHeaders()
    });
    const data = await res.json();
    currentSmartPreviewData = data;

    if (!data.proposals || data.proposals.length === 0) {
      tableContainer.innerHTML = '<p style="padding:12px; margin:0; opacity:0.7;">No enrolled students found to allocate.</p>';
      previewArea.style.display = 'block';
      if (execBtn) execBtn.disabled = true;
      return;
    }

    let rowsHtml = data.proposals.map(p => `
      <tr style="border-bottom:1px solid var(--border-color);">
        <td style="padding:8px 10px; font-weight:600;">${p.stage_name}</td>
        <td style="padding:8px 10px; color:#818cf8;">${p.program_name || 'Core Curriculum'}</td>
        <td style="padding:8px 10px; font-size:0.8rem; opacity:0.8;">${p.elective_combination || 'Standard'}</td>
        <td style="padding:8px 10px; text-align:center;"><span style="background:rgba(99,102,241,0.15); padding:2px 8px; border-radius:10px; font-weight:700;">${p.student_count}</span></td>
        <td style="padding:8px 10px; text-align:center;"><span style="color:#22c55e; font-weight:700;">${p.needed_arms}</span></td>
        <td style="padding:8px 10px; font-size:0.82rem; color:#06b6d4;">${p.proposed_classes.join(', ')}</td>
      </tr>
    `).join('');

    tableContainer.innerHTML = `
      <table style="width:100%; border-collapse:collapse; font-size:0.85rem;">
        <thead>
          <tr style="background:rgba(255,255,255,0.04); text-align:left; border-bottom:1px solid var(--border-color);">
            <th style="padding:8px 10px;">Stage</th>
            <th style="padding:8px 10px;">Program</th>
            <th style="padding:8px 10px;">Track / Combo</th>
            <th style="padding:8px 10px; text-align:center;">Students</th>
            <th style="padding:8px 10px; text-align:center;">Arms</th>
            <th style="padding:8px 10px;">Proposed Classes</th>
          </tr>
        </thead>
        <tbody>${rowsHtml}</tbody>
      </table>`;

    previewArea.style.display = 'block';
    if (execBtn) execBtn.disabled = false;
  } catch (err) {
    alert('Error previewing allocation: ' + err.message);
  }
}

async function executeSmartGeneration() {
  const cap = parseInt(document.getElementById('genTargetCapacity').value) || 45;
  const style = document.getElementById('genNamingStyle').value;
  const assign = document.getElementById('genAssignStudentsCb').checked;
  const execBtn = document.getElementById('executeSmartGenBtn');

  if (execBtn) { execBtn.disabled = true; execBtn.textContent = 'Generating...'; }

  try {
    const res = await fetch(`${API_BASE}/classes/smart-generate`, {
      method: 'POST',
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({
        target_capacity: cap,
        naming_style: style,
        assign_students: assign
      })
    });
    const data = await res.json();
    alert(data.message || 'Classes generated successfully!');
    closeSmartGenModal();
    loadClasses();
  } catch (err) {
    alert('Error generating classes: ' + err.message);
  } finally {
    if (execBtn) { execBtn.disabled = false; execBtn.textContent = '⚡ Generate Classes'; }
  }
}

function updateBatchPreview() {
  const stageSelect = document.getElementById('batchStageSelect');
  const progSelect = document.getElementById('batchProgramSelect');
  const countInput = document.getElementById('batchArmsCount');
  const styleSelect = document.getElementById('batchNamingStyle');
  const baseInput = document.getElementById('batchBaseName');
  const previewDiv = document.getElementById('batchLivePreview');

  if (!stageSelect || !previewDiv) return;

  const stageId = stageSelect.value;
  if (!stageId) {
    previewDiv.textContent = 'Select a stage to see preview...';
    return;
  }

  const stageOpt = stageSelect.options[stageSelect.selectedIndex];
  const stageName = stageOpt ? stageOpt.textContent.split(' (')[0].trim() : 'Form 1';
  const stageType = stageOpt ? stageOpt.getAttribute('data-type') : 'SHS';

  const progOpt = progSelect && progSelect.selectedIndex >= 0 ? progSelect.options[progSelect.selectedIndex] : null;
  const progName = (progOpt && progOpt.value) ? progOpt.textContent.replace('General ', '').replace('Technical', 'Tech').trim() : '';

  const count = Math.min(20, Math.max(1, parseInt(countInput ? countInput.value : 1) || 1));
  const style = styleSelect ? styleSelect.value : 'NUMBERS';
  const customBase = baseInput ? baseInput.value.trim() : '';

  const names = [];
  for (let i = 1; i <= count; i++) {
    const suffix = style === 'LETTERS' ? chrAlpha(i) : String(i);
    let name = '';
    if (stageType === 'SHS' && (progName || customBase)) {
      const base = customBase || progName;
      name = `${stageName} ${base} ${suffix}`;
    } else if (stageType === 'Basic') {
      const base = customBase || stageName;
      name = style === 'LETTERS' ? `${base}${suffix}` : `${base} ${suffix}`;
    } else {
      const base = customBase || (progName || stageName);
      name = `${stageName} ${base} ${suffix}`;
    }
    names.push(name);
  }

  previewDiv.textContent = names.join('  •  ');
}

function chrAlpha(num) {
  return String.fromCharCode(64 + num);
}

async function submitBatchArms(e) {
  e.preventDefault();
  const stageId = parseInt(document.getElementById('batchStageSelect').value);
  const progVal = document.getElementById('batchProgramSelect').value;
  const count = parseInt(document.getElementById('batchArmsCount').value) || 1;
  const style = document.getElementById('batchNamingStyle').value;
  const base = document.getElementById('batchBaseName').value.trim() || null;

  try {
    const res = await fetch(`${API_BASE}/classes/batch-create-arms`, {
      method: 'POST',
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({
        stage_id: stageId,
        program_id: progVal ? parseInt(progVal) : null,
        number_of_arms: count,
        naming_style: style,
        base_name: base
      })
    });
    const data = await res.json();
    alert(data.message || 'Batch arms provisioned successfully!');
    closeSmartGenModal();
    loadClasses();
  } catch (err) {
    alert('Error provisioning batch arms: ' + err.message);
  }
}

window.openSmartGenModal = openSmartGenModal;
window.closeSmartGenModal = closeSmartGenModal;
window.switchGenTab = switchGenTab;
window.previewSmartAllocation = previewSmartAllocation;
window.executeSmartGeneration = executeSmartGeneration;
window.updateBatchPreview = updateBatchPreview;
window.submitBatchArms = submitBatchArms;
window.filterClasses = filterClasses;

const openSmartGenBtn = document.getElementById('openSmartGenBtn');
if (openSmartGenBtn) {
  if (!_userIsAdmin()) {
    openSmartGenBtn.style.display = 'none';
  } else {
    openSmartGenBtn.addEventListener('click', openSmartGenModal);
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
  const deleteBtn = event.target.closest('[data-delete]');
  if (deleteBtn) {
    const deleteId = deleteBtn.getAttribute('data-delete');
    const className = deleteBtn.getAttribute('data-name') || 'this class section';

    if (!confirm(`Are you sure you want to delete "${className}"?\n\nNote: If students are currently enrolled in this class, deletion will be prevented to protect student records.`)) return;

    try {
      const resp = await fetch(`${API_BASE}/classes/${deleteId}`, { method: 'DELETE', headers: getHeaders() });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        alert(err.detail || 'Could not delete class section.');
        return;
      }
      loadClasses();
    } catch (e) {
      alert('Network error while deleting class.');
    }
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
      
      if (classRawSubjectsList.length === 0 && programSubjectsList.length > 0) {
        classRawSubjectsList = [...programSubjectsList];
      }
      toggle.checked = true;
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
  
  const checkboxes = subjectsForm.querySelectorAll('input[name="subjectIds"]:checked');
  const payload = Array.from(checkboxes).map(cb => parseInt(cb.value));

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
