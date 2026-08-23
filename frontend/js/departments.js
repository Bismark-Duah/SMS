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

const form = document.getElementById('deptForm');
const container = document.getElementById('deptList');
const hodSelect = document.getElementById('deptHod');
const subjectsCheckboxList = document.getElementById('subjectsCheckboxList');
const cancelBtn = document.getElementById('cancelDeptBtn');
const deptMsg = document.getElementById('deptMsg');

let allSubjects = [];
let allTeachers = [];

async function loadInitialData() {
  const mode = localStorage.getItem('school_mode') || 'COMBINED';
  if (mode === 'BASIC_ONLY') {
    if (container) {
      container.innerHTML = '<div style="padding:24px; text-align:center; color:var(--text-muted);">ℹ️ Academic Departments are disabled in Basic School mode.</div>';
    }
    if (form) {
      form.style.display = 'none';
    }
    return;
  }
  try {
    const mode = (localStorage.getItem('school_mode') || 'COMBINED').toUpperCase();
    const url = mode === 'SHS_ONLY' ? `${API_BASE}/subjects/?exclude_basic=true` : `${API_BASE}/subjects/`;
    
    const subRes = await fetch(url, { headers: getHeaders() });
    if (subRes.ok) {
      let subjects = await subRes.json();
      if (mode === 'SHS_ONLY') {
        subjects = subjects.filter(s => (s.school_level || 'SHS') !== 'Basic');
      }
      allSubjects = subjects;
    }

    // Load users (teachers / staff)
    const userRes = await fetch(`${API_BASE}/auth/users`, { headers: getHeaders() });
    if (userRes.ok) {
      const users = await userRes.json();
      allTeachers = users.filter(u => u.roles && u.roles.some(r => !['student', 'parent'].includes(r.name.toLowerCase())));
    }

    renderHodDropdown();
    renderSubjectsCheckboxList();
    loadDepartments();
  } catch (error) {
    console.error('Error loading initial department data:', error);
  }
}

function renderHodDropdown() {
  hodSelect.innerHTML = '<option value="">Select HOD...</option>' + 
    allTeachers.map(t => `<option value="${t.id}">${t.username} (${t.email})</option>`).join('');
}

function renderSubjectsCheckboxList() {
  if (allSubjects.length === 0) {
    subjectsCheckboxList.innerHTML = '<p style="opacity:.6; font-size:.85rem;">No subjects available. Add subjects first.</p>';
    return;
  }

  const coreSubjects = allSubjects.filter(s => s.is_core);
  const electiveSubjects = allSubjects.filter(s => !s.is_core);

  const renderItem = (sub) => {
    const level = sub.school_level || 'SHS';
    const badgeBg    = level === 'Basic' ? 'rgba(13,110,253,0.2)' : level === 'STEM' ? 'rgba(111,66,193,0.2)' : 'rgba(25,135,84,0.2)';
    const badgeColor = level === 'Basic' ? '#6ea8fe'              : level === 'STEM' ? '#c59fec'              : '#75b798';
    return `
      <label onclick="deptSubjectChipToggle(this)"
        style="display:flex; align-items:flex-start; gap:7px; padding:8px 10px; border-radius:8px;
               background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.1);
               cursor:pointer; transition:all 0.15s ease; user-select:none;">
        <input type="checkbox" name="subjectIds" value="${sub.id}" style="display:none;" />
        <span style="margin-top:2px; width:14px; height:14px; border-radius:3px; border:1.5px solid rgba(255,255,255,0.3);
                     flex-shrink:0; display:flex; align-items:center; justify-content:center; font-size:10px; transition:all 0.15s;"></span>
        <div style="flex:1; min-width:0;">
          <div style="font-size:0.82rem; font-weight:600; color:#f1f5f9; line-height:1.3;">${sub.name}</div>
          <div style="margin-top:2px; display:flex; gap:4px; flex-wrap:wrap;">
            ${sub.code ? `<span style="font-size:0.7rem; opacity:0.7;">(${sub.code})</span>` : ''}
            <span style="font-size:0.68rem; padding:1px 5px; border-radius:4px; background:${badgeBg}; color:${badgeColor}; font-weight:600;">${level} • ${sub.is_core ? 'Core' : 'Elec'}</span>
          </div>
        </div>
      </label>
    `;
  };

  let html = '';
  if (coreSubjects.length > 0) {
    html += `<div style="font-size:0.78rem; font-weight:700; text-transform:uppercase; letter-spacing:0.5px; color:#818cf8; margin:4px 0 8px 0;">📘 Core Subjects</div>`;
    html += `<div style="display:grid; grid-template-columns:repeat(auto-fill, minmax(170px, 1fr)); gap:6px; margin-bottom:14px;">`;
    html += coreSubjects.map(renderItem).join('');
    html += `</div>`;
  }
  if (electiveSubjects.length > 0) {
    html += `<div style="font-size:0.78rem; font-weight:700; text-transform:uppercase; letter-spacing:0.5px; color:#facc15; margin:4px 0 8px 0;">📙 Elective Subjects</div>`;
    html += `<div style="display:grid; grid-template-columns:repeat(auto-fill, minmax(170px, 1fr)); gap:6px;">`;
    html += electiveSubjects.map(renderItem).join('');
    html += `</div>`;
  }
  subjectsCheckboxList.innerHTML = html;
}

function deptSubjectChipToggle(labelEl) {
  event.preventDefault();
  const cb = labelEl.querySelector('input[name="subjectIds"]');
  if (!cb) return;
  cb.checked = !cb.checked;
  const span = labelEl.querySelector('span');
  if (cb.checked) {
    labelEl.style.borderColor = 'rgba(96,165,250,0.7)';
    labelEl.style.background  = 'rgba(59,130,246,0.15)';
    if (span) { span.style.background = '#3b82f6'; span.style.borderColor = '#3b82f6'; span.textContent = '\u2713'; span.style.color = '#fff'; }
  } else {
    labelEl.style.borderColor = 'rgba(255,255,255,0.1)';
    labelEl.style.background  = 'rgba(255,255,255,0.04)';
    if (span) { span.style.background = ''; span.style.borderColor = 'rgba(255,255,255,0.3)'; span.textContent = ''; }
  }
}

const _ADMIN_ROLES = new Set([
  'admin', 'super_admin', 'headmaster', 'headmistress',
  'assistant_headmaster_academic', 'assistant_head_academic',
  'assistant_headmaster_admin', 'assistant_head_admin',
  'assistant_headmaster_domestic', 'assistant_head_domestic',
]);
function _userIsAdmin() {
  try {
    const activeRole = (sessionStorage.getItem('activeRole') || localStorage.getItem('activeRole') || sessionStorage.getItem('userRole') || localStorage.getItem('userRole') || '').toLowerCase();
    return _ADMIN_ROLES.has(activeRole);
  } catch { return false; }
}

async function loadDepartments() {
  try {
    const response = await fetch(`${API_BASE}/departments/`, { headers: getHeaders() });
    const data = await response.json();

    if (!Array.isArray(data) || data.length === 0) {
      container.innerHTML = '<p style="opacity:.6; text-align:center; padding:20px;">No departments created yet.</p>';
      return;
    }

    const isAdmin = _userIsAdmin();

    container.innerHTML = data.map(item => {
      let subjectsHtml = '';
      if (item.subject_names && item.subject_names.length > 0) {
        subjectsHtml = `
          <div style="display:flex; flex-wrap:wrap; gap:5px; margin-top:6px;">
            ${item.subject_names.map(sName => {
              const isCore = sName.toLowerCase().includes('core') || sName.toLowerCase().includes('english') || sName.toLowerCase().includes('social');
              const bg = isCore ? 'rgba(59,130,246,0.18)' : 'rgba(234,179,8,0.18)';
              const color = isCore ? '#93c5fd' : '#fef08a';
              const border = isCore ? '1px solid rgba(59,130,246,0.3)' : '1px solid rgba(234,179,8,0.3)';
              return `<span style="font-size:0.75rem; padding:2px 8px; border-radius:12px; background:${bg}; color:${color}; border:${border}; font-weight:500;">${sName}</span>`;
            }).join('')}
          </div>
        `;
      } else {
        subjectsHtml = '<span style="opacity:.5; font-style:italic;">No subjects associated</span>';
      }
      
      const teacherCount = item.teacher_count || (item.teachers ? item.teachers.length : 0);

      return `
        <div style="border-bottom: 1px solid var(--border-color, rgba(255,255,255,0.1)); padding: 16px 0; display:flex; flex-direction:column; gap:10px;">
          <div style="display:flex; justify-content:space-between; align-items:flex-start;">
            <div>
              <h4 style="margin:0; font-size:1.1rem; color:#fff;">${item.name} (${item.code})</h4>
              <p style="margin:4px 0 0 0; font-size:0.85rem; opacity:.8;">HOD: <strong style="color:#60a5fa;">${item.hod_name || 'Not assigned'}</strong></p>
              <div style="margin-top:6px; display:flex; gap:8px; align-items:center;">
                <span style="font-size:0.72rem; padding:2px 7px; border-radius:10px; background:rgba(99,102,241,0.18); color:#a5b4fc; border:1px solid rgba(99,102,241,0.3); font-weight:600;">📊 ${item.subject_names ? item.subject_names.length : 0} Subjects</span>
                <span style="font-size:0.72rem; padding:2px 7px; border-radius:10px; background:rgba(16,185,129,0.18); color:#6ee7b7; border:1px solid rgba(16,185,129,0.3); font-weight:600;">👨‍🏫 ${teacherCount} Teachers</span>
              </div>
            </div>
            ${isAdmin ? `
            <div style="display:flex; gap:6px;">
              <button class="btn" style="padding:4px 8px; font-size:0.8rem;" onclick="editDepartment(${item.id}, '${item.name.replace(/'/g, "\\'")}', '${item.code.replace(/'/g, "\\'")}', ${item.hod_id || 'null'}, [${item.subject_ids.join(',')}])">Edit</button>
              <button class="btn danger" style="padding:4px 8px; font-size:0.8rem;" onclick="deleteDepartment(${item.id})">Delete</button>
            </div>` : ''}
          </div>
          <div style="font-size: 0.82rem; opacity:.85; line-height:1.4;">
            <div style="font-weight:600; color:var(--text-secondary); margin-bottom:4px;">Departmental Subjects:</div>
            ${subjectsHtml}
          </div>
        </div>
      `;
    }).join('');

    // If HOD persona, replace the right column form card with Department Teachers Workload Register panel
    if (!isAdmin) {
      const rightCard = form ? form.closest('.card') : null;
      if (rightCard) {
        const hodDept = data[0];
        const teachersList = hodDept && hodDept.teachers && hodDept.teachers.length > 0
          ? `<div style="display:flex; flex-direction:column; gap:10px;">
              ${hodDept.teachers.map(t => {
                const wlStatus = t.workload_status || 'UNASSIGNED';
                let wlColor = '#94a3b8';
                let wlBg = 'rgba(148,163,184,0.15)';
                let wlBorder = 'rgba(148,163,184,0.3)';
                if (wlStatus === 'BALANCED') {
                  wlColor = '#34d399'; wlBg = 'rgba(16,185,129,0.15)'; wlBorder = 'rgba(16,185,129,0.3)';
                } else if (wlStatus === 'HEAVY') {
                  wlColor = '#f87171'; wlBg = 'rgba(239,68,68,0.15)'; wlBorder = 'rgba(239,68,68,0.3)';
                } else if (wlStatus === 'LIGHT') {
                  wlColor = '#60a5fa'; wlBg = 'rgba(59,130,246,0.15)'; wlBorder = 'rgba(59,130,246,0.3)';
                }

                const subsPill = t.assigned_subjects && t.assigned_subjects.length > 0
                  ? t.assigned_subjects.map(s => `<span style="font-size:0.68rem; background:rgba(99,102,241,0.2); color:#a5b4fc; padding:1px 5px; border-radius:4px;">${s}</span>`).join(' ')
                  : '<span style="font-size:0.68rem; opacity:0.5; font-style:italic;">No subjects</span>';

                const classesPill = t.assigned_classes && t.assigned_classes.length > 0
                  ? `<div style="font-size:0.72rem; color:#cbd5e1; margin-top:3px;">🏫 ${t.assigned_classes.join(', ')}</div>`
                  : '';

                return `
                  <div style="padding:10px; border-radius:8px; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.08); display:flex; flex-direction:column; gap:4px;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                      <div>
                        <strong style="color:#f8fafc; font-size:0.9rem;">${t.full_name || t.username}</strong>
                        <div style="font-size:0.73rem; color:#94a3b8;">${t.email || 'Teacher Staff'}</div>
                      </div>
                      <span style="font-size:0.68rem; font-weight:700; background:${wlBg}; color:${wlColor}; border:1px solid ${wlBorder}; padding:2px 7px; border-radius:10px; text-transform:uppercase;">
                        ${wlStatus} (${t.class_count || 0} Classes)
                      </span>
                    </div>
                    <div style="display:flex; flex-wrap:wrap; gap:4px; margin-top:2px;">
                      ${subsPill}
                    </div>
                    ${classesPill}
                  </div>
                `;
              }).join('')}
            </div>`
          : '<p style="opacity:0.6; font-style:italic; font-size:0.85rem;">No staff assigned to this department yet.</p>';

        rightCard.innerHTML = `
          <h3 style="margin-top:0;">📊 Department Workload Register</h3>
          <p style="font-size:0.82rem; opacity:0.7; margin-top:-4px; margin-bottom:12px;">Staff teaching assignments & workload status for <strong>${hodDept ? hodDept.name : 'your department'}</strong>:</p>
          ${teachersList}
          <div style="margin-top:16px;">
            <a href="assignments.html" class="btn primary" style="display:block; text-align:center; padding:10px; font-weight:600; border-radius:8px;">👨‍🏫 Manage Subject Workload</a>
          </div>
        `;
      }
    }
  } catch (error) {
    console.error(error);
    container.innerHTML = '<p style="color:var(--danger); text-align:center;">Failed to load departments.</p>';
  }
}

function editDepartment(id, name, code, hodId, subjectIds) {
  document.getElementById('deptId').value = id;
  document.getElementById('deptName').value = name;
  document.getElementById('deptCode').value = code;
  hodSelect.value = hodId || '';

  // Sync chip visual state + hidden checkbox for associated subjects
  const labels = subjectsCheckboxList.querySelectorAll('label');
  labels.forEach(label => {
    const cb = label.querySelector('input[name="subjectIds"]');
    if (!cb) return;
    const isSelected = subjectIds.includes(parseInt(cb.value));
    cb.checked = isSelected;
    const span = label.querySelector('span');
    if (isSelected) {
      label.style.borderColor = 'rgba(96,165,250,0.7)';
      label.style.background  = 'rgba(59,130,246,0.15)';
      if (span) { span.style.background = '#3b82f6'; span.style.borderColor = '#3b82f6'; span.textContent = '\u2713'; span.style.color = '#fff'; }
    } else {
      label.style.borderColor = 'rgba(255,255,255,0.1)';
      label.style.background  = 'rgba(255,255,255,0.04)';
      if (span) { span.style.background = ''; span.style.borderColor = 'rgba(255,255,255,0.3)'; span.textContent = ''; }
    }
  });

  deptMsg.innerHTML = '<div style="color:var(--warning); font-size:0.85rem;">Editing department... Submit form to save.</div>';
}

async function deleteDepartment(id) {
  if (!confirm('Are you sure you want to delete this department?')) return;
  try {
    const res = await fetch(`${API_BASE}/departments/${id}`, {
      method: 'DELETE',
      headers: getHeaders()
    });
    if (res.ok) {
      loadDepartments();
      form.reset();
    } else {
      const err = await res.json();
      alert(`Error deleting department: ${err.detail || 'unknown error'}`);
    }
  } catch (error) {
    alert('Failed to connect to server.');
  }
}

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const id = document.getElementById('deptId').value;
  const checkboxes = subjectsCheckboxList.querySelectorAll('input[name="subjectIds"]:checked');
  const subjectIds = Array.from(checkboxes).map(cb => parseInt(cb.value));

  const payload = {
    name: document.getElementById('deptName').value.trim(),
    code: document.getElementById('deptCode').value.trim(),
    hod_id: hodSelect.value ? parseInt(hodSelect.value) : null,
    subject_ids: subjectIds
  };

  try {
    const url = id ? `${API_BASE}/departments/${id}` : `${API_BASE}/departments/`;
    const method = id ? 'PUT' : 'POST';

    const response = await fetch(url, {
      method: method,
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      const err = await response.json();
      throw new Error(err.detail || 'Could not save department');
    }

    form.reset();
    document.getElementById('deptId').value = '';
    deptMsg.innerHTML = '<div style="color:var(--success); font-size:0.85rem;">Department saved successfully!</div>';
    setTimeout(() => { deptMsg.innerHTML = ''; }, 3000);
    loadDepartments();
  } catch (error) {
    deptMsg.innerHTML = `<div style="color:var(--danger); font-size:0.85rem;">Error: ${error.message}</div>`;
  }
});

const DEPARTMENT_PRESETS = {
  science: [
    "General Science (Core)", "Science", "Biology", "Chemistry", "Physics",
    "Biomedical Science", "Engineering Science", "Aviation & Aerospace Eng",
    "Agriculture (Elective)", "General Agriculture", "Crop Husbandry and Horticulture",
    "Animal Husbandry", "Fisheries", "Forestry", "Horticulture", "STEM Group C Lab Practical"
  ],
  math: [
    "Core Mathematics", "Mathematics", "Early Numeracy", "Additional Mathematics"
  ],
  language: [
    "English Language (SHS)", "English Language", "Rhymes, Phonics & Language",
    "Language and Literacy", "Literature in English", "French (Elective)",
    "French", "Ghanaian Language", "Arabic", "Music", "Twi (Asante / Akuapem)", "Twi (Asante)",
    "Twi (Akuapem)", "Fante", "Ewe", "Ga", "Dagbani", "Nzema", "Dagaare",
    "Dangme", "Kasem", "Gonja"
  ],
  social: [
    "Social Studies (SHS)", "Social Studies", "Our World Our People", "History of Ghana",
    "History (SHS)", "Government", "Geography", "Economics",
    "Religious and Moral Education", "Christian Religious Studies", "Islamic Religious Studies"
  ],
  ict: [
    "Computing", "Robotics and Coding (Form 2)", "Computer Science (Elective)",
    "ICT (Elective)", "Robotics Engineering", "Artificial Intelligence & Data Science",
    "Cybersecurity & Network Security"
  ],
  business: [
    "Business Management", "Financial Accounting", "Cost Accounting",
    "Clerical Office Duties", "Typewriting & Keyboarding"
  ],
  home_econ: [
    "Food and Nutrition", "Clothing and Textiles", "Management in Living",
    "Sensory & Motor Skills", "Physical Development", "Catering & Hospitality",
    "Garment Making & Fashion", "Cosmetology & Beauty Therapy",
    "Physical and Health Education", "PEH (Core)"
  ],
  technical: [
    "Applied Electricity", "Electronics", "Auto Mechanics", "Auto Electricals",
    "Refrigeration & Air Conditioning", "Mechanical Engineering Craft Practice",
    "Plumbing & Pipe Fitting", "Welding & Fabrication", "Building Construction",
    "Woodwork", "Metalwork", "Technical Drawing", "Career Technology",
    "Design & Communication Tech", "Design and Communication Technology",
    "Manufacturing Engineering", "Engineering Science", "Renewable Energy Technology"
  ],
  art: [
    "General Knowledge in Art", "Art and Design Foundation", "Art and Design Studio",
    "Graphic Design", "Picture Making", "Ceramics", "Sculpture", "Textiles",
    "Leatherwork", "Jewellery", "Basketry", "Creative Play & Drawing",
    "Creative Arts and Design", "Design & Communication Tech"
  ]
};

function loadPresetSubjects() {
  const deptNameInput = document.getElementById('deptName');
  const deptName = (deptNameInput ? deptNameInput.value : '').toLowerCase().trim();
  
  if (!deptName) {
    alert('Please enter a Department Name first (e.g. "Science Department", "Business Department", "Visual Arts", "Languages", "Mathematics", "Technical", "ICT", or "Home Economics").');
    return;
  }

  let matchedCategory = null;
  if (deptName.includes('science') || deptName.includes('sci')) matchedCategory = 'science';
  else if (deptName.includes('math')) matchedCategory = 'math';
  else if (deptName.includes('lang') || deptName.includes('english')) matchedCategory = 'language';
  else if (deptName.includes('social') || deptName.includes('humanities') || deptName.includes('arts department') === false && deptName.includes('arts')) matchedCategory = 'social';
  else if (deptName.includes('ict') || deptName.includes('comput')) matchedCategory = 'ict';
  else if (deptName.includes('bus') || deptName.includes('commercial')) matchedCategory = 'business';
  else if (deptName.includes('home') || deptName.includes('econ') || deptName.includes('hec')) matchedCategory = 'home_econ';
  else if (deptName.includes('tech') || deptName.includes('applied') || deptName.includes('craft')) matchedCategory = 'technical';
  else if (deptName.includes('art') || deptName.includes('visual') || deptName.includes('design')) matchedCategory = 'art';

  if (!matchedCategory) {
    alert('Could not auto-determine preset from department name. Try using names like "Science", "Business", "Visual Arts", "Languages", "Mathematics", "Technical", "ICT", or "Home Economics".');
    return;
  }

  const presetSubjectNames = new Set(DEPARTMENT_PRESETS[matchedCategory] || []);
  let count = 0;

  document.querySelectorAll('#subjectsCheckboxList label').forEach(labelEl => {
    const cb = labelEl.querySelector('input[name="subjectIds"]');
    const nameEl = labelEl.querySelector('div > div');
    if (!cb || !nameEl) return;
    const sName = nameEl.textContent.trim();
    
    if (presetSubjectNames.has(sName)) {
      if (!cb.checked) {
        cb.checked = true;
        labelEl.style.borderColor = 'rgba(96,165,250,0.7)';
        labelEl.style.background  = 'rgba(59,130,246,0.15)';
        const span = labelEl.querySelector('span');
        if (span) { span.style.background = '#3b82f6'; span.style.borderColor = '#3b82f6'; span.textContent = '\u2713'; span.style.color = '#fff'; }
      }
      count++;
    } else {
      if (cb.checked) {
        cb.checked = false;
        labelEl.style.borderColor = 'rgba(255,255,255,0.1)';
        labelEl.style.background  = 'rgba(255,255,255,0.04)';
        const span = labelEl.querySelector('span');
        if (span) { span.style.background = ''; span.style.borderColor = 'rgba(255,255,255,0.3)'; span.textContent = ''; }
      }
    }
  });

  if (deptMsg) {
    deptMsg.innerHTML = `<div style="color:#4ade80; font-weight:600; font-size:0.85rem;">⚡ Auto-selected ${count} standard preset subjects for ${deptNameInput.value}!</div>`;
    setTimeout(() => { if (deptMsg) deptMsg.innerHTML = ''; }, 4000);
  }
}

const loadPresetSubjectsBtn = document.getElementById('loadPresetSubjectsBtn');
if (loadPresetSubjectsBtn) {
  loadPresetSubjectsBtn.addEventListener('click', loadPresetSubjects);
}

// Bind to window to allow button onclick triggers
window.editDepartment = editDepartment;
window.deleteDepartment = deleteDepartment;
window.loadPresetSubjects = loadPresetSubjects;

loadInitialData();
