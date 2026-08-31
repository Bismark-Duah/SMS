const API_BASE = window.API_BASE || (window.location.origin.includes('http') ? (window.location.origin + '/api') : 'http://127.0.0.1:8000/api');

const token = localStorage.getItem('accessToken');
if (!token) {
  window.location.href = 'auth.html';
}

function getHeaders(headers = {}) {
  const currentToken = localStorage.getItem('accessToken');
  const h = { ...headers };
  if (currentToken) h['Authorization'] = `Bearer ${currentToken}`;
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
    const activeRole = (sessionStorage.getItem('activeRole') || localStorage.getItem('activeRole') || sessionStorage.getItem('userRole') || localStorage.getItem('userRole') || '').toLowerCase();
    return _ADMIN_ROLES.has(activeRole);
  } catch { return false; }
}

let allTeachers = [];
let allClasses = [];
let allSemesters = [];
let allHouses = [];
let allDepartments = [];
let allAssignmentsData = [];
let allPrivilegesData = [];
let currentRoleFilter = 'all';

async function loadDropdowns() {
  const teacherSelect = document.getElementById('teacherSelect');
  const semesterSelect = document.getElementById('semesterSelect');
  const privilegeClassSelect = document.getElementById('privilegeClassSelect');
  const privilegeHouseSelect = document.getElementById('privilegeHouseSelect');
  const privilegeDeptSelect = document.getElementById('privilegeDepartmentSelect');

  try {
    const [resUsers, resClasses, resSemesters, resHouses, resDepts] = await Promise.all([
      fetch(`${API_BASE}/auth/users`, { headers: getHeaders() }),
      fetch(`${API_BASE}/classes/`, { headers: getHeaders() }),
      fetch(`${API_BASE}/academic/semesters`, { headers: getHeaders() }),
      fetch(`${API_BASE}/houses/`, { headers: getHeaders() }),
      fetch(`${API_BASE}/departments/`, { headers: getHeaders() }),
    ]);

    const users = await resUsers.json();
    allClasses = await resClasses.json();
    allSemesters = await resSemesters.json();
    allHouses = await resHouses.json();
    allDepartments = resDepts.ok ? await resDepts.json() : [];

    const isAdmin = _userIsAdmin();

    allTeachers = users.filter(u => u.roles && u.roles.some(r => {
      const rName = (typeof r === 'string' ? r : r.name || '').toLowerCase();
      return !['student', 'parent'].includes(rName);
    }));

    if (!isAdmin) {
      allTeachers = allTeachers.filter(u => {
        const roleNames = u.roles ? u.roles.map(r => (typeof r === 'string' ? r : r.name || '').toLowerCase()) : [];
        return !roleNames.includes('super_admin') && !roleNames.includes('admin');
      });

      const assignTypeSelect = document.getElementById('assignmentTypeSelect');
      if (assignTypeSelect) {
        assignTypeSelect.innerHTML = `
          <option value="teaching" selected>📘 Subject Teaching Assignment (HOD Scope)</option>
        `;
        assignTypeSelect.disabled = true;
      }
    }

    teacherSelect.innerHTML = '<option value="">Select Teacher / Staff Member...</option>' +
      allTeachers.map(t => `<option value="${t.id}">${t.full_name || t.username} (${t.email || 'Staff'})</option>`).join('');

    // Populate Multi-Class Checkboxes
    renderClassCheckboxes();

    // Populate classes (Privilege target)
    if (privilegeClassSelect) {
      privilegeClassSelect.innerHTML = '<option value="">Select Class Section...</option>' +
        allClasses.map(c => `<option value="${c.id}">${c.name}</option>`).join('');
    }

    // Populate houses (Privilege target)
    if (privilegeHouseSelect) {
      privilegeHouseSelect.innerHTML = '<option value="">Select House...</option>' +
        allHouses.map(h => `<option value="${h.id}">${h.name} (${h.gender})</option>`).join('');
    }

    // Populate departments (Privilege target for HOD)
    if (privilegeDeptSelect) {
      privilegeDeptSelect.innerHTML = '<option value="">Select Academic Department...</option>' +
        allDepartments.map(d => `<option value="${d.id}">${d.name} (${d.code})</option>`).join('');
    }

    // Populate semesters
    semesterSelect.innerHTML = '<option value="">Select Term / Semester...</option>' +
      allSemesters.map(s => `<option value="${s.id}">${s.name}</option>`).join('');

    filterTeachingAssignments();
  } catch (error) {
    console.error('Error loading dropdown data:', error);
  }
}

function renderClassCheckboxes() {
  const cbClassContainer = document.getElementById('classesCheckboxList');
  if (!cbClassContainer) return;

  if (allClasses.length === 0) {
    cbClassContainer.innerHTML = '<span style="opacity:0.6; font-style:italic; font-size:0.85rem;">No class sections available.</span>';
    return;
  }

  cbClassContainer.innerHTML = `
    <div style="display:grid; grid-template-columns:repeat(auto-fill, minmax(140px, 1fr)); gap:7px; width:100%;">
      ${allClasses.map(c => `
        <label class="assign-chip-label" onclick="handleAssignChipToggle(this, 'assign-class-cb', handleClassCheckboxChange)"
          style="display:flex; align-items:center; gap:6px; padding:8px 10px; border-radius:7px;
                 background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.1);
                 cursor:pointer; transition:all 0.15s ease; user-select:none;">
          <input type="checkbox" class="assign-class-cb" value="${c.id}" data-name="${c.name}" style="display:none;" />
          <span class="assign-chip-check" style="width:14px; height:14px; border-radius:3px; border:1.5px solid rgba(255,255,255,0.3); flex-shrink:0; display:flex; align-items:center; justify-content:center; font-size:10px; transition:all 0.15s;"></span>
          <span style="font-size:0.82rem; font-weight:500; color:#f1f5f9; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">🏫 ${c.name}</span>
        </label>
      `).join('')}
    </div>
  `;
}

// Select All / Clear All Classes handlers — syncs chip visual state
document.getElementById('selectAllClassesBtn')?.addEventListener('click', () => {
  document.querySelectorAll('.assign-chip-label').forEach(label => {
    const cb = label.querySelector('.assign-class-cb');
    if (!cb) return;
    cb.checked = true;
    applyAssignChipStyle(label, label.querySelector('.assign-chip-check'), true);
  });
  handleClassCheckboxChange();
});

document.getElementById('clearAllClassesBtn')?.addEventListener('click', () => {
  document.querySelectorAll('.assign-chip-label').forEach(label => {
    const cb = label.querySelector('.assign-class-cb');
    if (!cb) return;
    cb.checked = false;
    applyAssignChipStyle(label, label.querySelector('.assign-chip-check'), false);
  });
  handleClassCheckboxChange();
});

// Shared helper — apply/remove chip selected style
function applyAssignChipStyle(label, chipCheck, isSelected) {
  if (isSelected) {
    label.style.borderColor = 'rgba(96,165,250,0.7)';
    label.style.background = 'rgba(59,130,246,0.15)';
    if (chipCheck) { chipCheck.style.background = '#3b82f6'; chipCheck.style.borderColor = '#3b82f6'; chipCheck.textContent = '\u2713'; chipCheck.style.color = '#fff'; }
  } else {
    label.style.borderColor = 'rgba(255,255,255,0.1)';
    label.style.background = 'rgba(255,255,255,0.04)';
    if (chipCheck) { chipCheck.style.background = ''; chipCheck.style.borderColor = 'rgba(255,255,255,0.3)'; chipCheck.textContent = ''; }
  }
}

function handleAssignChipToggle(labelEl, cbClass, onChangeCallback) {
  event.preventDefault();
  const cb = labelEl.querySelector(`input.${cbClass}`);
  if (!cb) return;
  cb.checked = !cb.checked;
  applyAssignChipStyle(labelEl, labelEl.querySelector('.assign-chip-check'), cb.checked);
  if (typeof onChangeCallback === 'function') onChangeCallback();
}

let isSubjectDeptFilterActive = true;

function getTeacherDepartment(teacherId) {
  if (!teacherId || !allDepartments.length) return null;
  const t = allTeachers.find(u => u.id == teacherId);
  if (!t) return null;

  // 1. Direct department_id
  if (t.department_id) {
    const dept = allDepartments.find(d => d.id == t.department_id);
    if (dept) return dept;
  }

  // 2. Teacher is HOD of a department
  const hodDept = allDepartments.find(d => d.hod_id == teacherId);
  if (hodDept) return hodDept;

  // 3. Listed in department teachers array
  const facultyDept = allDepartments.find(d => d.teachers && d.teachers.some(dt => dt.id == teacherId));
  if (facultyDept) return facultyDept;

  return null;
}

window.toggleSubjectDeptFilter = function() {
  isSubjectDeptFilterActive = !isSubjectDeptFilterActive;
  handleClassCheckboxChange();
};

// Handle Class Checkbox Selection change to dynamically load subjects for all selected classes
async function handleClassCheckboxChange() {
  const checkedClassCbs = Array.from(document.querySelectorAll('.assign-class-cb:checked'));
  const cbListContainer = document.getElementById('subjectsCheckboxList');
  const filterIndicator = document.getElementById('deptFilterIndicator');
  const toggleBtn = document.getElementById('toggleAllSubjectsBtn');
  if (!cbListContainer) return;

  if (checkedClassCbs.length === 0) {
    cbListContainer.innerHTML = '<span style="opacity: 0.6; font-style: italic; font-size: 0.85rem;">Select at least one Class Section above to load subjects...</span>';
    if (filterIndicator) filterIndicator.style.display = 'none';
    if (toggleBtn) toggleBtn.style.display = 'none';
    return;
  }

  cbListContainer.innerHTML = '<span style="opacity:0.6; font-style:italic; font-size:0.85rem;">Loading subjects for selected class(es)...</span>';

  try {
    const classIds = checkedClassCbs.map(cb => cb.value);
    const subjectMap = new Map();

    for (const cid of classIds) {
      const res = await fetch(`${API_BASE}/classes/${cid}/subjects`, { headers: getHeaders() });
      if (res.ok) {
        const subs = await res.json();
        subs.forEach(s => {
          if (!subjectMap.has(s.id)) {
            subjectMap.set(s.id, { ...s, classNames: [checkedClassCbs.find(c => c.value == cid)?.dataset.name] });
          } else {
            subjectMap.get(s.id).classNames.push(checkedClassCbs.find(c => c.value == cid)?.dataset.name);
          }
        });
      }
    }

    let allClassSubjects = Array.from(subjectMap.values());
    const selectedTeacherId = document.getElementById('teacherSelect')?.value;
    const teacherDept = getTeacherDepartment(selectedTeacherId);

    let displaySubjects = allClassSubjects;
    let deptSubjectIds = new Set();

    if (teacherDept && teacherDept.subject_ids) {
      deptSubjectIds = new Set(teacherDept.subject_ids);
    }

    if (!_userIsAdmin()) {
      // HOD scope: restrict to HOD department subjects always
      const userSubsRes = await fetch(`${API_BASE}/subjects/`, { headers: getHeaders() });
      if (userSubsRes.ok) {
        const userSubs = await userSubsRes.json();
        const allowedSubIds = new Set(userSubs.map(s => s.id));
        displaySubjects = displaySubjects.filter(s => allowedSubIds.has(s.id));
      }
      if (filterIndicator) filterIndicator.style.display = 'none';
      if (toggleBtn) toggleBtn.style.display = 'none';
    } else if (teacherDept && deptSubjectIds.size > 0) {
      const matchingDeptSubjects = allClassSubjects.filter(s => deptSubjectIds.has(s.id));

      if (isSubjectDeptFilterActive) {
        // Active filter mode: show only teacher's department subjects for the selected class(es)
        displaySubjects = matchingDeptSubjects;

        if (filterIndicator) {
          filterIndicator.style.display = 'inline-flex';
          filterIndicator.innerHTML = `🔬 ${teacherDept.name} (${matchingDeptSubjects.length} subject${matchingDeptSubjects.length === 1 ? '' : 's'})`;
          filterIndicator.style.background = 'rgba(14,165,233,0.15)';
          filterIndicator.style.color = '#38bdf8';
        }
        if (toggleBtn) {
          toggleBtn.style.display = 'inline-flex';
          toggleBtn.textContent = `🌐 Show All Class Subjects (${allClassSubjects.length})`;
          toggleBtn.title = 'Switch to view subjects from all departments for these classes';
        }
      } else {
        // All subjects mode: show all, with department subjects marked
        displaySubjects = allClassSubjects;

        if (filterIndicator) {
          filterIndicator.style.display = 'inline-flex';
          filterIndicator.innerHTML = `🌐 All Departments (${allClassSubjects.length} subjects)`;
          filterIndicator.style.background = 'rgba(255,255,255,0.08)';
          filterIndicator.style.color = 'var(--text-secondary,#94a3b8)';
        }
        if (toggleBtn) {
          toggleBtn.style.display = 'inline-flex';
          toggleBtn.textContent = `🔬 Filter: ${teacherDept.name} (${matchingDeptSubjects.length})`;
          toggleBtn.title = `Filter back to ${teacherDept.name} subjects only`;
        }
      }
    } else {
      // Teacher has no department or admin hasn't selected a teacher yet
      if (filterIndicator) {
        if (selectedTeacherId) {
          filterIndicator.style.display = 'inline-flex';
          filterIndicator.innerHTML = `💡 General / Unassigned Dept (${allClassSubjects.length} subjects)`;
          filterIndicator.style.background = 'rgba(234,179,8,0.15)';
          filterIndicator.style.color = '#fde047';
        } else {
          filterIndicator.style.display = 'none';
        }
      }
      if (toggleBtn) toggleBtn.style.display = 'none';
    }

    if (displaySubjects.length === 0) {
      if (teacherDept && isSubjectDeptFilterActive) {
        cbListContainer.innerHTML = `
          <div style="grid-column: 1 / -1; padding: 14px; text-align: center; background: rgba(234,179,8,0.06); border: 1px dashed rgba(234,179,8,0.3); border-radius: 8px;">
            <p style="margin: 0 0 8px 0; font-size: 0.85rem; color: #fde047;">No subjects from <strong>${teacherDept.name}</strong> are assigned to the selected class section(s).</p>
            <button type="button" class="btn sm" onclick="toggleSubjectDeptFilter()" style="padding: 4px 10px; font-size: 0.8rem; background: #0284c7; color: #fff;">🌐 Show All Subjects For This Class</button>
          </div>
        `;
      } else {
        cbListContainer.innerHTML = '<span style="opacity:0.6; font-style:italic; font-size:0.85rem; color:var(--warning);">No subjects found for the selected class section(s).</span>';
      }
    } else {
      const teacherAssignedSubjectIds = selectedTeacherId ? allAssignmentsData.filter(a => a.teacher_id == selectedTeacherId).map(a => a.subject_id) : [];

      cbListContainer.innerHTML = `
        <div style="display:grid; grid-template-columns:repeat(auto-fill, minmax(175px, 1fr)); gap:7px; width:100%;">
          ${displaySubjects.map(s => {
            const isAlreadyAssigned = teacherAssignedSubjectIds.includes(s.id);
            const isDeptSubject = deptSubjectIds.has(s.id);
            const borderColor = isAlreadyAssigned 
              ? 'rgba(234,179,8,0.5)' 
              : (isDeptSubject ? 'rgba(56,189,248,0.4)' : 'rgba(255,255,255,0.1)');
            const bgColor = isAlreadyAssigned 
              ? 'rgba(234,179,8,0.08)' 
              : (isDeptSubject ? 'rgba(14,165,233,0.06)' : 'rgba(255,255,255,0.04)');

            return `
              <label class="assign-chip-label assign-subject-chip" onclick="handleAssignChipToggle(this, 'assign-subject-cb', null)"
                style="display:flex; align-items:flex-start; gap:6px; padding:8px 10px; border-radius:7px;
                       background:${bgColor}; border:1px solid ${borderColor};
                       cursor:pointer; transition:all 0.15s ease; user-select:none; position:relative;">
                <input type="checkbox" class="assign-subject-cb" value="${s.id}" data-name="${s.name}" style="display:none;" />
                <span class="assign-chip-check" style="margin-top:2px; width:14px; height:14px; border-radius:3px; border:1.5px solid rgba(255,255,255,0.3); flex-shrink:0; display:flex; align-items:center; justify-content:center; font-size:10px; transition:all 0.15s;"></span>
                <div style="flex:1; min-width:0;">
                  <div style="display:flex; align-items:center; justify-content:space-between; gap:4px;">
                    <span style="font-size:0.82rem; font-weight:600; color:#f1f5f9; line-height:1.3; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${s.name}">${s.name}</span>
                    ${isDeptSubject ? '<span style="font-size:0.65rem; background:rgba(14,165,233,0.25); color:#38bdf8; padding:1px 4px; border-radius:3px; flex-shrink:0;">Dept</span>' : ''}
                  </div>
                  <div style="font-size:0.72rem; color:#64748b; margin-top:1px;">${s.is_core ? 'Core' : 'Elective'}</div>
                  ${isAlreadyAssigned ? '<div style="margin-top:3px; font-size:0.68rem; background:rgba(234,179,8,0.25); color:#fde047; padding:1px 5px; border-radius:3px; display:inline-block;">⚠ Already Assigned</div>' : ''}
                </div>
              </label>
            `;
          }).join('')}
        </div>
      `;
    }
  } catch (error) {
    console.error('Error fetching subjects:', error);
    cbListContainer.innerHTML = '<span style="color:var(--danger); font-size:0.85rem;">Error loading subjects. Please try again.</span>';
  }
}

// Live Workload Counter for Selected Teacher
function handleTeacherSelectChange(teacherId) {
  const badgeContainer = document.getElementById('teacherWorkloadBadge');
  if (!badgeContainer) return;
  if (!teacherId) {
    badgeContainer.style.display = 'none';
    return;
  }

  const teacher = allTeachers.find(t => t.id == teacherId);
  const teacherName = teacher ? (teacher.full_name || teacher.username) : 'Teacher';

  const teacherAssignments = allAssignmentsData.filter(a => a.teacher_id == teacherId);
  const teacherPrivileges = allPrivilegesData.filter(p => p.teacher_id == teacherId);

  const uniqueClasses = new Set(teacherAssignments.map(a => a.class_section_name)).size;
  const uniqueSubjects = new Set(teacherAssignments.map(a => a.subject_name)).size;
  const privLabels = teacherPrivileges.map(p => `${p.privilege_type || p.role_title || 'Role'} (${p.target_name || 'Global'})`).join(', ');

  const teacherDept = getTeacherDepartment(teacherId);
  const deptLabel = teacherDept ? `<span style="margin-left:6px; background:rgba(14,165,233,0.18); color:#38bdf8; padding:2px 8px; border-radius:4px; font-weight:600;">🔬 ${teacherDept.name}</span>` : '';

  badgeContainer.innerHTML = `
    📊 <strong>${teacherName} Current Workload:</strong> ${deptLabel}
    <span style="margin-left:8px; background:rgba(255,255,255,0.08); padding:2px 8px; border-radius:4px;">🏫 <strong>${uniqueClasses}</strong> Class Section(s)</span>
    <span style="margin-left:6px; background:rgba(255,255,255,0.08); padding:2px 8px; border-radius:4px;">📘 <strong>${uniqueSubjects}</strong> Subject(s)</span>
    ${teacherPrivileges.length > 0 ? `<span style="margin-left:6px; background:rgba(234,179,8,0.2); color:#fde047; padding:2px 8px; border-radius:4px;">⭐ ${privLabels}</span>` : ''}
  `;
  badgeContainer.style.display = 'block';

  // Reset department filter to active when switching teacher
  isSubjectDeptFilterActive = true;
  // Re-run class checkbox change to refresh subjects list matching this teacher's department!
  const checkedClassCbs = document.querySelectorAll('.assign-class-cb:checked');
  if (checkedClassCbs.length > 0) {
    handleClassCheckboxChange();
  }
}

// Toggle field blocks based on assignment category
document.getElementById('assignmentTypeSelect').addEventListener('change', (event) => {
  const type = event.target.value;
  const teachingFields = document.getElementById('teachingFields');
  const privilegeFields = document.getElementById('privilegeFields');
  const privilegeTypeSelect = document.getElementById('privilegeTypeSelect');

  if (type === 'teaching') {
    teachingFields.style.display = 'contents';
    privilegeFields.style.display = 'none';
    privilegeTypeSelect.required = false;
  } else if (type === 'privilege') {
    teachingFields.style.display = 'none';
    privilegeFields.style.display = 'block';
    privilegeTypeSelect.required = true;
  } else { // both
    teachingFields.style.display = 'contents';
    privilegeFields.style.display = 'block';
    privilegeTypeSelect.required = true;
  }
});

document.getElementById('privilegeTypeSelect').addEventListener('change', (event) => {
  const role = event.target.value;
  const classTarget = document.getElementById('privilegeClassTarget');
  const houseTarget = document.getElementById('privilegeHouseTarget');
  const deptTarget = document.getElementById('privilegeDepartmentTarget');
  const classSelect = document.getElementById('privilegeClassSelect');
  const houseSelect = document.getElementById('privilegeHouseSelect');
  const deptSelect = document.getElementById('privilegeDepartmentSelect');

  if (classTarget) classTarget.style.display = 'none';
  if (houseTarget) houseTarget.style.display = 'none';
  if (deptTarget) deptTarget.style.display = 'none';
  if (classSelect) classSelect.required = false;
  if (houseSelect) houseSelect.required = false;
  if (deptSelect) deptSelect.required = false;

  if (role === 'form_master') {
    if (classTarget) classTarget.style.display = 'block';
    if (classSelect) classSelect.required = true;
  } else if (role === 'house_master' || role === 'assistant_house_master') {
    if (houseTarget) houseTarget.style.display = 'block';
    if (houseSelect) houseSelect.required = true;
  } else if (role === 'hod') {
    if (deptTarget) deptTarget.style.display = 'block';
    if (deptSelect) deptSelect.required = true;
  }
});

// Wire Select All and Clear All buttons for subjects checkboxes
document.getElementById('selectAllSubjectsBtn')?.addEventListener('click', () => {
  document.querySelectorAll('.assign-subject-chip').forEach(label => {
    const cb = label.querySelector('.assign-subject-cb');
    if (!cb) return;
    cb.checked = true;
    applyAssignChipStyle(label, label.querySelector('.assign-chip-check'), true);
  });
});

document.getElementById('clearAllSubjectsBtn')?.addEventListener('click', () => {
  document.querySelectorAll('.assign-subject-chip').forEach(label => {
    const cb = label.querySelector('.assign-subject-cb');
    if (!cb) return;
    cb.checked = false;
    applyAssignChipStyle(label, label.querySelector('.assign-chip-check'), false);
  });
});

async function loadAssignments() {
  try {
    const [resAsgn, resPriv] = await Promise.all([
      fetch(`${API_BASE}/assignments/`, { headers: getHeaders() }),
      fetch(`${API_BASE}/assignments/privileges`, { headers: getHeaders() })
    ]);
    allAssignmentsData = await resAsgn.json();
    if (resPriv.ok) {
      allPrivilegesData = await resPriv.json();
    }
    filterTeachingAssignments();
  } catch (error) {
    const container = document.getElementById('assignmentsList');
    if (container) container.textContent = 'Unable to load teaching assignments.';
    console.error('Error loading assignments:', error);
  }
}

function setWorkloadRoleFilter(roleKey) {
  currentRoleFilter = roleKey;
  
  // Update button styles
  const btnIds = ['filterRoleAll', 'filterRoleHod', 'filterRoleFormMaster', 'filterRoleHouseMaster', 'filterRoleUnassigned'];
  btnIds.forEach(id => {
    const btn = document.getElementById(id);
    if (btn) btn.className = 'btn sm';
  });

  const activeBtnId = roleKey === 'hod' ? 'filterRoleHod' :
                      roleKey === 'form_master' ? 'filterRoleFormMaster' :
                      roleKey === 'house_master' ? 'filterRoleHouseMaster' :
                      roleKey === 'unassigned' ? 'filterRoleUnassigned' : 'filterRoleAll';

  const activeBtn = document.getElementById(activeBtnId);
  if (activeBtn) activeBtn.className = 'btn primary sm';

  filterTeachingAssignments();
}

function filterTeachingAssignments() {
  const container = document.getElementById('assignmentsList');
  if (!container) return;

  const query = document.getElementById('filterAssignmentSearch')?.value.toLowerCase().trim() || '';

  // Construct Teacher Consolidated Profile Map
  const teacherMap = new Map();

  allTeachers.forEach(t => {
    const teacherId = t.id;
    const teacherName = t.full_name || t.username;

    // Get assignments for teacher
    const tAsgns = allAssignmentsData.filter(a => String(a.teacher_id) === String(teacherId));
    // Get privileges for teacher
    let tPrivs = allPrivilegesData.filter(p => String(p.teacher_id) === String(teacherId));

    // Comprehensive Executive & Leadership role fallbacks
    if (t.roles && Array.isArray(t.roles)) {
      const roleNames = t.roles.map(r => (typeof r === 'string' ? r : r.name || '').toLowerCase());
      
      const execRoles = [
        { key: 'hod', title: 'Head of Department (HOD)', target: 'Department Leadership' },
        { key: 'assistant_headmaster_academic', title: 'Assistant Headmaster / Mistress (Academic)', target: 'Global (School-wide)' },
        { key: 'assistant_headmaster_domestic', title: 'Assistant Headmaster / Mistress (Domestic)', target: 'Global (School-wide)' },
        { key: 'assistant_headmaster_admin', title: 'Assistant Headmaster / Mistress (Admin)', target: 'Global (School-wide)' },
        { key: 'assistant_head_academic', title: 'Assistant Headmaster / Mistress (Academic)', target: 'Global (School-wide)' },
        { key: 'assistant_head_domestic', title: 'Assistant Headmaster / Mistress (Domestic)', target: 'Global (School-wide)' },
        { key: 'assistant_head_admin', title: 'Assistant Headmaster / Mistress (Admin)', target: 'Global (School-wide)' },
        { key: 'headmaster', title: 'Headmaster / Principal', target: 'Global (School-wide)' },
        { key: 'headmistress', title: 'Headmistress / Principal', target: 'Global (School-wide)' },
        { key: 'bursar', title: 'School Accountant / Bursar', target: 'Global (School-wide)' },
        { key: 'senior_house_master', title: 'Senior House Master / Mistress', target: 'Global (School-wide)' },
        { key: 'senior_housemaster', title: 'Senior House Master / Mistress', target: 'Global (School-wide)' },
        { key: 'senior_housemistress', title: 'Senior House Master / Mistress', target: 'Global (School-wide)' },
        { key: 'form_master', title: 'Form Master / Mistress', target: 'Assigned Class Section' },
        { key: 'form_mistress', title: 'Form Master / Mistress', target: 'Assigned Class Section' },
        { key: 'house_master', title: 'House Master / Mistress', target: 'Assigned House' },
        { key: 'house_mistress', title: 'House Master / Mistress', target: 'Assigned House' },
        { key: 'assistant_house_master', title: 'Assistant House Master / Mistress', target: 'Assigned House' },
        { key: 'assistant_house_mistress', title: 'Assistant House Master / Mistress', target: 'Assigned House' }
      ];

      execRoles.forEach(er => {
        if (roleNames.includes(er.key) && !tPrivs.some(p => (p.privilege_type || '').toLowerCase().includes(er.title.toLowerCase().slice(0, 10)))) {
          tPrivs.push({
            id: `role-${er.key}-${teacherId}`,
            teacher_id: teacherId,
            teacher_name: teacherName,
            privilege_type: er.title,
            target_name: er.target
          });
        }
      });
    }

    // Direct HOD department mapping from allDepartments
    if (Array.isArray(allDepartments)) {
      const hodDepts = allDepartments.filter(d => d.hod_id && String(d.hod_id) === String(teacherId));
      hodDepts.forEach(d => {
        if (!tPrivs.some(p => (p.privilege_type || '').toLowerCase().includes('hod') && (p.target_name || '').toLowerCase().includes(d.name.toLowerCase()))) {
          tPrivs.push({
            id: `dept-hod-${d.id}`,
            teacher_id: teacherId,
            teacher_name: teacherName,
            privilege_type: "Head of Department (HOD)",
            target_id: d.id,
            target_name: `${d.name} (${d.code})`
          });
        }
      });
    }

    // Group subjects taught — carry individual assignment IDs per class chip
    const subjectMap = new Map();
    tAsgns.forEach(a => {
      const key = `${a.subject_name}|||${a.semester_name || ''}`;
      if (!subjectMap.has(key)) {
        subjectMap.set(key, {
          subject_name: a.subject_name,
          semester_name: a.semester_name,
          is_core: a.is_core,
          classes: [{ name: a.class_section_name, id: a.id }]
        });
      } else {
        const item = subjectMap.get(key);
        if (!item.classes.some(c => c.name === a.class_section_name)) {
          item.classes.push({ name: a.class_section_name, id: a.id });
        }
      }
    });

    teacherMap.set(teacherId, {
      id: teacherId,
      name: teacherName,
      email: t.email || 'Staff Member',
      assignmentsCount: tAsgns.length,
      privilegesCount: tPrivs.length,
      privileges: tPrivs,
      subjectGroups: Array.from(subjectMap.values()),
      rawAssignments: tAsgns,
      rawUser: t
    });
  });

  // Filter list
  let teacherProfiles = Array.from(teacherMap.values());

  if (!_userIsAdmin()) {
    const activeUserId = localStorage.getItem('userId') || sessionStorage.getItem('userId');
    const assignedTeacherIds = new Set(allAssignmentsData.map(a => String(a.teacher_id)));
    const hodDept = allDepartments.find(d => d.hod_id && String(d.hod_id) === String(activeUserId));
    const hodDeptTeacherIds = new Set(hodDept && hodDept.teachers ? hodDept.teachers.map(t => String(t.id)) : []);

    teacherProfiles = teacherProfiles.filter(tp => {
      const uId = String(tp.id);
      const isSystemAdmin = tp.rawUser && tp.rawUser.roles && tp.rawUser.roles.some(r => {
        const rName = (typeof r === 'string' ? r : r.name || '').toLowerCase();
        return rName === 'super_admin' || rName === 'admin';
      });
      if (isSystemAdmin && !assignedTeacherIds.has(uId)) return false;

      return assignedTeacherIds.has(uId) || hodDeptTeacherIds.has(uId) || uId === String(activeUserId);
    });
  }

  // Filter by Role Pill
  if (currentRoleFilter === 'hod') {
    teacherProfiles = teacherProfiles.filter(tp => {
      const hasPriv = tp.privileges.some(p => {
        const pType = (p.privilege_type || '').toLowerCase();
        const pTarget = (p.target_name || '').toLowerCase();
        return pType.includes('hod') || pType.includes('head of department') || pType.includes('department') || pTarget.includes('department');
      });
      const hasRole = tp.rawUser && tp.rawUser.roles && tp.rawUser.roles.some(r => {
        const rName = (typeof r === 'string' ? r : r.name || '').toLowerCase();
        return rName === 'hod' || rName.includes('department');
      });
      return hasPriv || hasRole;
    });
  } else if (currentRoleFilter === 'form_master') {
    teacherProfiles = teacherProfiles.filter(tp => {
      const hasPriv = tp.privileges.some(p => {
        const pType = (p.privilege_type || '').toLowerCase();
        return pType.includes('form master') || pType.includes('form mistress') || pType.includes('form_master') || pType.includes('tutor');
      });
      const hasRole = tp.rawUser && tp.rawUser.roles && tp.rawUser.roles.some(r => {
        const rName = (typeof r === 'string' ? r : r.name || '').toLowerCase();
        return rName.includes('form');
      });
      return hasPriv || hasRole;
    });
  } else if (currentRoleFilter === 'house_master') {
    teacherProfiles = teacherProfiles.filter(tp => {
      const hasPriv = tp.privileges.some(p => {
        const pType = (p.privilege_type || '').toLowerCase();
        return pType.includes('house');
      });
      const hasRole = tp.rawUser && tp.rawUser.roles && tp.rawUser.roles.some(r => {
        const rName = (typeof r === 'string' ? r : r.name || '').toLowerCase();
        return rName.includes('house');
      });
      return hasPriv || hasRole;
    });
  } else if (currentRoleFilter === 'unassigned') {
    teacherProfiles = teacherProfiles.filter(tp => tp.assignmentsCount === 0 && tp.privilegesCount === 0);
  }

  // Filter by Search Query
  if (query) {
    teacherProfiles = teacherProfiles.filter(tp => {
      const matchName = tp.name.toLowerCase().includes(query);
      const matchPriv = tp.privileges.some(p => (p.privilege_type || '').toLowerCase().includes(query) || (p.target_name || '').toLowerCase().includes(query));
      const matchSub = tp.subjectGroups.some(sg => sg.subject_name.toLowerCase().includes(query) || sg.classes.some(c => c.toLowerCase().includes(query)));
      return matchName || matchPriv || matchSub;
    });
  }

  if (teacherProfiles.length === 0) {
    container.innerHTML = '<p style="opacity:.6; font-style:italic; padding:16px; text-align:center;">No matching consolidated teacher workloads found.</p>';
    return;
  }

  container.innerHTML = `
    <div style="display:flex; flex-direction:column; gap:16px;">
      ${teacherProfiles.map(tp => {
        const uniqueClassesCount = new Set(tp.rawAssignments.map(a => a.class_section_name)).size;
        const uniqueSubjectsCount = tp.subjectGroups.length;

        return `
          <div class="card" style="background:rgba(255,255,255,0.02); border:1px solid var(--border-color); border-radius:10px; padding:16px; box-shadow:0 2px 10px rgba(0,0,0,0.15);">
            <!-- Header Row -->
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px; border-bottom:1px solid rgba(255,255,255,0.06); padding-bottom:10px;">
              <div>
                <h4 style="margin:0; font-size:1.05rem; color:var(--text-primary); display:flex; align-items:center; gap:8px;">
                  👤 <strong>${tp.name}</strong> 
                  <small style="opacity:0.6; font-weight:normal; font-size:0.8rem;">(${tp.email})</small>
                </h4>
                <!-- Administrative Leadership Privileges -->
                <div style="display:flex; gap:6px; flex-wrap:wrap; margin-top:6px;">
                  ${tp.privileges.length > 0 ? tp.privileges.map(p => `
                    <span style="background:rgba(234,179,8,0.18); color:#fde047; padding:2px 8px; border-radius:4px; font-size:0.8rem; border:1px solid rgba(234,179,8,0.3);">
                      ⭐ ${p.privilege_type || p.role_title} — <strong>${p.target_name || 'Global'}</strong>
                    </span>
                  `).join('') : '<span style="opacity:0.6; font-size:0.78rem; font-style:italic;">No leadership privileges</span>'}
                </div>
              </div>

              <!-- Workload Summary Stats & Quick Actions -->
              <div style="display:flex; align-items:center; gap:10px; flex-wrap:wrap;">
                <div style="font-size:0.82rem; background:rgba(255,255,255,0.04); padding:4px 10px; border-radius:6px; border:1px solid rgba(255,255,255,0.08);">
                  🏫 <strong>${uniqueClassesCount}</strong> Class(es) | 📘 <strong>${uniqueSubjectsCount}</strong> Subject(s)
                </div>
                <button class="btn sm primary" onclick="openEditTeacherWorkloadModal(${tp.id})" style="padding:4px 10px; font-size:0.8rem;">✏️ Edit Workload</button>
                <button class="btn sm danger" onclick="removeAllTeacherAssignments(${tp.id}, '${tp.name}')" style="padding:4px 10px; font-size:0.8rem;">🗑 Remove Workload</button>
              </div>
            </div>

            <!-- Subject & Class Allocations — grouped by subject, class chips per row -->
            <div style="margin-top:12px;">
              ${tp.subjectGroups.length > 0 ? `
                <div style="display:flex; flex-direction:column; gap:7px;">
                  ${tp.subjectGroups.map(sg => `
                    <div style="display:flex; align-items:center; background:rgba(255,255,255,0.02); padding:9px 13px; border-radius:7px; border:1px solid rgba(255,255,255,0.06); flex-wrap:wrap; gap:8px;">
                      <strong style="color:var(--text-primary); font-size:0.88rem; white-space:nowrap; margin-right:2px;">
                        📘 ${sg.subject_name}
                        ${sg.is_core !== undefined ? `<span style="font-size:0.68rem; margin-left:5px; padding:1px 6px; border-radius:9px; background:${sg.is_core ? 'rgba(99,102,241,0.18)' : 'rgba(234,179,8,0.15)'}; color:${sg.is_core ? '#818cf8' : '#facc15'}; font-weight:600; vertical-align:middle;">${sg.is_core ? 'CORE' : 'ELECTIVE'}</span>` : ''}
                      </strong>
                      <div style="display:flex; flex-wrap:wrap; gap:5px; align-items:center; flex:1;">
                        ${sg.classes.map(cls => `
                          <span style="display:inline-flex; align-items:center; gap:4px; background:rgba(59,130,246,0.15); color:#93c5fd; border:1px solid rgba(59,130,246,0.3); padding:3px 8px; border-radius:5px; font-size:0.78rem; font-weight:500; white-space:nowrap;">
                            🏫 ${cls.name}
                            <button onclick="deleteSingleAssignment(${cls.id}, '${sg.subject_name.replace(/\\/g, '\\\\').replace(/'/g, "\\'")}', '${cls.name.replace(/\\/g, '\\\\').replace(/'/g, "\\'")}')"
                              title="Remove ${sg.subject_name} from ${cls.name}"
                              style="background:none; border:none; cursor:pointer; color:rgba(252,165,165,0.85); font-size:0.75rem; padding:0 0 0 3px; line-height:1; display:flex; align-items:center; transition:color 0.15s;"
                              onmouseover="this.style.color='#f87171'" onmouseout="this.style.color='rgba(252,165,165,0.85)'">✕</button>
                          </span>
                        `).join('')}
                      </div>
                      <small style="opacity:0.55; font-size:0.75rem; white-space:nowrap;">(${sg.semester_name || 'General'})</small>
                    </div>
                  `).join('')}
                </div>
              ` : `
                <p style="margin:4px 0 0 0; opacity:0.6; font-style:italic; font-size:0.85rem;">No subject teaching allocations assigned yet.</p>
              `}
            </div>
          </div>
        `;
      }).join('')}
    </div>
  `;
}

async function loadPrivileges() {
  const container = document.getElementById('privilegesList');
  try {
    const res = await fetch(`${API_BASE}/assignments/privileges`, { headers: getHeaders() });
    if (!res.ok) {
      throw new Error('Failed to fetch administrative privileges');
    }
    allPrivilegesData = await res.json();
    filterTeachingAssignments();

    if (!Array.isArray(allPrivilegesData) || allPrivilegesData.length === 0) {
      container.innerHTML = '<p style="opacity:.6; font-style:italic; padding:10px;">No active administrative privileges assigned yet.</p>';
      return;
    }

    container.innerHTML = `
      <div style="overflow-x: auto;">
        <table style="width: 100%; border-collapse: collapse; margin-top: 10px; color: var(--text-primary);">
          <thead>
            <tr style="border-bottom: 2px solid var(--border-color); text-align: left;">
              <th style="padding: 10px 14px;">Staff / Supervisor</th>
              <th style="padding: 10px 14px;">Privilege / Role</th>
              <th style="padding: 10px 14px;">Assigned Target</th>
              <th style="padding: 10px 14px; text-align: center;">Action</th>
            </tr>
          </thead>
          <tbody>
            ${allPrivilegesData.map(p => `
              <tr style="border-bottom: 1px solid var(--border-color);">
                <td style="padding: 10px 14px;"><strong>${p.teacher_name}</strong></td>
                <td style="padding: 10px 14px;"><span style="background:rgba(234,179,8,0.18); color:#fde047; padding:2px 8px; border-radius:4px; font-size:0.85rem;">⭐ ${p.privilege_type || p.role_title || 'Administrative Role'}</span></td>
                <td style="padding: 10px 14px;">${p.target_name}</td>
                <td style="padding: 10px 14px; text-align: center;">
                  <button class="btn danger" onclick="deletePrivilege('${p.privilege_type}', ${p.target_id}, ${p.teacher_id})" style="padding: 4px 8px; font-size: 0.85rem;">Remove</button>
                </td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    `;
  } catch (error) {
    container.textContent = 'Unable to load administrative privileges.';
    console.error('Error loading privileges:', error);
  }
}

// Form Submission with Multi-Class + Multi-Subject Batch Assignment
const form = document.getElementById('assignmentForm');
if (form) {
  form.addEventListener('submit', async (event) => {
    event.preventDefault();

    const category = document.getElementById('assignmentTypeSelect').value;
    const teacherId = parseInt(document.getElementById('teacherSelect').value);
    const semesterId = parseInt(document.getElementById('semesterSelect').value);

    // Collect all checked Class Section IDs
    const checkedClassBoxes = Array.from(document.querySelectorAll('.assign-class-cb:checked'));
    const checkedClassSectionIds = checkedClassBoxes.map(cb => parseInt(cb.value)).filter(id => !isNaN(id));

    // Collect all checked Subject IDs
    const checkedSubjectBoxes = Array.from(document.querySelectorAll('.assign-subject-cb:checked'));
    const checkedSubjectIds = checkedSubjectBoxes.map(cb => parseInt(cb.value)).filter(id => !isNaN(id));

    if (category === 'teaching' || category === 'both') {
      if (checkedClassSectionIds.length === 0) {
        alert('Please select at least one Target Class Section.');
        return;
      }
      if (checkedSubjectIds.length === 0) {
        alert('Please check at least one subject to assign.');
        return;
      }
      if (!semesterId) {
        alert('Please select a Term / Semester.');
        return;
      }
    }

    if (category === 'teaching') {
      let successCount = 0;
      let failMessages = [];

      for (const classSecId of checkedClassSectionIds) {
        for (const subId of checkedSubjectIds) {
          const payload = {
            teacher_id: teacherId,
            subject_id: subId,
            class_section_id: classSecId,
            semester_id: semesterId
          };

          try {
            const response = await fetch(`${API_BASE}/assignments/`, {
              method: 'POST',
              headers: getHeaders({ 'Content-Type': 'application/json' }),
              body: JSON.stringify(payload)
            });
            if (response.ok) {
              successCount++;
            } else {
              const err = await response.json();
              failMessages.push(err.detail || 'Assignment failed');
            }
          } catch (error) {
            failMessages.push(error.message);
          }
        }
      }

      if (successCount > 0) {
        alert(`Successfully created ${successCount} teaching assignment(s) across selected class(es) & subject(s).`);
        resetEntireForm();
        await loadAssignments();
      } else if (failMessages.length > 0) {
        alert(`Error assigning subjects: ${failMessages.join(' | ')}`);
      }

    } else if (category === 'privilege') {
      const privilegeType = document.getElementById('privilegeTypeSelect').value;
      let targetId = null;

      if (privilegeType === 'form_master') {
        targetId = parseInt(document.getElementById('privilegeClassSelect').value);
      } else if (privilegeType === 'house_master' || privilegeType === 'assistant_house_master') {
        targetId = parseInt(document.getElementById('privilegeHouseSelect').value);
      } else if (privilegeType === 'hod') {
        targetId = parseInt(document.getElementById('privilegeDepartmentSelect').value);
      }

      const payload = {
        teacher_id: teacherId,
        privilege_type: privilegeType,
        target_id: targetId
      };

      try {
        const response = await fetch(`${API_BASE}/assignments/privilege`, {
          method: 'POST',
          headers: getHeaders({ 'Content-Type': 'application/json' }),
          body: JSON.stringify(payload)
        });

        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || 'Failed to save administrative privilege');

        alert('Administrative privilege successfully assigned.');
        resetEntireForm();
        await loadPrivileges();
        await loadAssignments();
      } catch (error) {
        alert(`Could not assign privilege: ${error.message}`);
      }
    } else { // both
      const privilegeType = document.getElementById('privilegeTypeSelect').value;
      let targetId = null;

      if (privilegeType === 'form_master') {
        targetId = parseInt(document.getElementById('privilegeClassSelect').value) || checkedClassSectionIds[0];
      } else if (privilegeType === 'house_master' || privilegeType === 'assistant_house_master') {
        targetId = parseInt(document.getElementById('privilegeHouseSelect').value);
      } else if (privilegeType === 'hod') {
        targetId = parseInt(document.getElementById('privilegeDepartmentSelect').value);
      }

      let successCount = 0;
      for (const classSecId of checkedClassSectionIds) {
        for (const subId of checkedSubjectIds) {
          const teachingPayload = {
            teacher_id: teacherId,
            subject_id: subId,
            class_section_id: classSecId,
            semester_id: semesterId
          };
          try {
            const res = await fetch(`${API_BASE}/assignments/`, {
              method: 'POST',
              headers: getHeaders({ 'Content-Type': 'application/json' }),
              body: JSON.stringify(teachingPayload)
            });
            if (res.ok) successCount++;
          } catch (_) {}
        }
      }

      const privilegePayload = {
        teacher_id: teacherId,
        privilege_type: privilegeType,
        target_id: targetId
      };

      try {
        const resPrivilege = await fetch(`${API_BASE}/assignments/privilege`, {
          method: 'POST',
          headers: getHeaders({ 'Content-Type': 'application/json' }),
          body: JSON.stringify(privilegePayload)
        });

        if (!resPrivilege.ok) {
          const err = await resPrivilege.json();
          throw new Error(`Privilege Error: ${err.detail}`);
        }

        alert(`Assigned ${successCount} teaching subject(s) and Administrative Privilege successfully.`);
        resetEntireForm();
        await Promise.all([loadAssignments(), loadPrivileges()]);
      } catch (error) {
        alert(`Could not complete assignments: ${error.message}`);
      }
    }
  });
}

function resetEntireForm() {
  const form = document.getElementById('assignmentForm');
  if (form) form.reset();
  document.querySelectorAll('.assign-class-cb').forEach(cb => cb.checked = false);
  document.querySelectorAll('.assign-subject-cb').forEach(cb => cb.checked = false);
  document.getElementById('subjectsCheckboxList').innerHTML = '<span style="opacity: 0.6; font-style: italic; font-size: 0.85rem;">Select at least one Class Section above to load subjects...</span>';
  const badgeContainer = document.getElementById('teacherWorkloadBadge');
  if (badgeContainer) badgeContainer.style.display = 'none';
}

function switchAssignmentTab(tabName) {
  const teachingPane = document.getElementById('tabTeachingPane');
  const privilegesPane = document.getElementById('tabPrivilegesPane');
  const privilegesBtn = document.getElementById('tabPrivilegesBtn');

  if (tabName === 'teaching') {
    teachingPane.style.display = 'block';
    privilegesPane.style.display = 'none';
    if (privilegesBtn) privilegesBtn.textContent = '🎗️ View Raw Privileges Table';
  } else {
    teachingPane.style.display = 'none';
    privilegesPane.style.display = 'block';
    if (privilegesBtn) privilegesBtn.textContent = '📘 View Consolidated Workload';
    loadPrivileges();
  }
}

function toggleAssignmentTab() {
  const privilegesPane = document.getElementById('tabPrivilegesPane');
  const isPrivilegesVisible = privilegesPane && privilegesPane.style.display === 'block';
  if (isPrivilegesVisible) {
    switchAssignmentTab('teaching');
  } else {
    switchAssignmentTab('privileges');
  }
}

async function removeAllTeacherAssignments(teacherId, teacherName) {
  const ok = await (window.showConfirmDialog ? window.showConfirmDialog(
    '🗑️ Remove All Teaching Assignments',
    `Are you sure you want to remove all teaching assignments for ${teacherName}?`,
    'Remove All Assignments',
    'Cancel',
    'warning'
  ) : Promise.resolve(confirm(`Are you sure you want to remove all teaching assignments for ${teacherName}?`)));

  if (!ok) return;

  const tAsgns = allAssignmentsData.filter(a => a.teacher_id == teacherId);
  let count = 0;
  for (const a of tAsgns) {
    try {
      const res = await fetch(`${API_BASE}/assignments/${a.id}`, { method: 'DELETE', headers: getHeaders() });
      if (res.ok) count++;
    } catch (_) {}
  }
  if (window.showToast) window.showToast(`Removed ${count} assignment(s) for ${teacherName}.`, 'info');
  else alert(`Removed ${count} assignment(s) for ${teacherName}.`);
  await loadAssignments();
}

async function deletePrivilege(privType, targetId, teacherId) {
  const ok = await (window.showConfirmDialog ? window.showConfirmDialog(
    '🗑️ Revoke Administrative Privilege',
    'Are you sure you want to remove this administrative privilege assignment?',
    'Revoke Privilege',
    'Cancel',
    'warning'
  ) : Promise.resolve(confirm('Are you sure you want to remove this administrative privilege?')));

  if (!ok) return;
  
  try {
    let url = `${API_BASE}/assignments/privilege/${privType}`;
    const params = [];
    if (targetId) params.push(`target_id=${targetId}`);
    if (teacherId) params.push(`teacher_id=${teacherId}`);
    if (params.length > 0) url += `?${params.join('&')}`;

    const response = await fetch(url, {
      method: 'DELETE',
      headers: getHeaders()
    });

    if (response.ok) {
      await loadPrivileges();
      await loadAssignments();
    } else {
      const err = await response.json();
      alert(`Error: ${err.detail || 'Could not remove privilege'}`);
    }
  } catch (error) {
    alert('Failed to remove privilege.');
  }
}

function printStaffWorkloadRegister() {
  const schName = localStorage.getItem('school_name') || 'School Management System';
  const schAbbr = localStorage.getItem('school_abbreviation') || 'SMS';

  // Construct Teacher Profiles
  const teacherMap = new Map();
  allTeachers.forEach(t => {
    const tAsgns = allAssignmentsData.filter(a => a.teacher_id == t.id);
    const tPrivs = allPrivilegesData.filter(p => p.teacher_id == t.id);

    if (tAsgns.length > 0 || tPrivs.length > 0) {
      const subMap = new Map();
      tAsgns.forEach(a => {
        if (!subMap.has(a.subject_name)) {
          subMap.set(a.subject_name, [a.class_section_name]);
        } else {
          subMap.get(a.subject_name).push(a.class_section_name);
        }
      });

      teacherMap.set(t.id, {
        name: t.full_name || t.username,
        email: t.email || 'N/A',
        privileges: tPrivs.map(p => `${p.privilege_type || p.role_title} (${p.target_name || 'Global'})`).join(', '),
        subjects: Array.from(subMap.entries()).map(([sName, classes]) => `${sName} [${Array.from(new Set(classes)).join(', ')}]`).join('<br>')
      });
    }
  });

  const profiles = Array.from(teacherMap.values());

  const win = window.open('', '_blank', 'width=900,height=700');
  win.document.write(`
    <!DOCTYPE html>
    <html>
      <head>
        <title>Staff Duty & Teaching Roster - ${schAbbr}</title>
        <style>
          body { font-family: 'Segoe UI', Tahoma, sans-serif; padding: 24px; color: #1e293b; }
          h2, h4 { margin: 0; }
          table { width: 100%; border-collapse: collapse; margin-top: 16px; }
          th, td { border: 1px solid #cbd5e1; padding: 8px 12px; font-size: 0.88rem; text-align: left; }
          th { background: #f1f5f9; }
          .badge { background: #fef08a; padding: 2px 6px; border-radius: 4px; font-weight: 600; font-size: 0.8rem; }
          @media print { body { padding: 0; } }
        </style>
      </head>
      <body>
        <div style="display:flex; justify-content:space-between; border-bottom:2px solid #0f172a; padding-bottom:12px; margin-bottom:16px;">
          <div>
            <h2>${schName}</h2>
            <h4>Official Staff Teaching & Leadership Workload Register</h4>
          </div>
          <div style="text-align:right; font-size:0.85rem;">
            <p style="margin:0;">Date: ${new Date().toLocaleDateString()}</p>
            <p style="margin:0;">Total Active Staff Assigned: <strong>${profiles.length}</strong></p>
          </div>
        </div>

        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Teacher / Staff Name</th>
              <th>Administrative & Leadership Role</th>
              <th>Subjects & Class Allocations</th>
            </tr>
          </thead>
          <tbody>
            ${profiles.map((p, idx) => `
              <tr>
                <td>${idx + 1}</td>
                <td><strong>${p.name}</strong><br><small style="color:#64748b;">${p.email}</small></td>
                <td>${p.privileges ? `<span class="badge">⭐ ${p.privileges}</span>` : '<em>Teaching Only</em>'}</td>
                <td>${p.subjects || '<em>Leadership Only</em>'}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
        <script>window.onload = function() { window.print(); };</script>
      </body>
    </html>
  `);
  win.document.close();
}

function openCopyWorkloadModal() {
  const modal = document.getElementById('copyWorkloadModal');
  if (!modal) return;

  const fromSel = document.getElementById('copyFromSemesterSelect');
  const toSel = document.getElementById('copyToSemesterSelect');

  fromSel.innerHTML = allSemesters.map(s => `<option value="${s.id}">${s.name}</option>`).join('');
  toSel.innerHTML = allSemesters.map(s => `<option value="${s.id}">${s.name}</option>`).join('');

  modal.style.display = 'flex';
}

function closeCopyWorkloadModal() {
  const modal = document.getElementById('copyWorkloadModal');
  if (modal) modal.style.display = 'none';
}

async function submitCopyWorkload(event) {
  event.preventDefault();
  const fromId = parseInt(document.getElementById('copyFromSemesterSelect').value);
  const toId = parseInt(document.getElementById('copyToSemesterSelect').value);

  if (fromId === toId) {
    alert('Source term and target term must be different.');
    return;
  }

  const sourceAssignments = allAssignmentsData.filter(a => a.semester_id == fromId);
  if (sourceAssignments.length === 0) {
    alert('No teaching assignments found in the selected source term.');
    return;
  }

  let createdCount = 0;
  for (const asgn of sourceAssignments) {
    try {
      const payload = {
        teacher_id: asgn.teacher_id,
        subject_id: asgn.subject_id,
        class_section_id: asgn.class_section_id,
        semester_id: toId
      };
      const res = await fetch(`${API_BASE}/assignments/`, {
        method: 'POST',
        headers: getHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(payload)
      });
      if (res.ok) createdCount++;
    } catch (_) {}
  }

  alert(`Successfully copied ${createdCount} assignment(s) to the target term.`);
  closeCopyWorkloadModal();
  await loadAssignments();
}

// ── Edit Workload Modal Functions ──────────────────────────────────────────

// ── Consolidated Edit Teacher Workload Modal Functions ──────────────────────

function openEditTeacherWorkloadModal(teacherId) {
  const teacher = allTeachers.find(t => String(t.id) === String(teacherId));
  const teacherName = teacher ? (teacher.full_name || teacher.username) : 'Staff Member';

  document.getElementById('editModalTeacherId').value = teacherId;
  document.getElementById('editModalTeacherName').textContent = `✏ Edit Workload — ${teacherName}`;
  document.getElementById('editModalTeacherSub').textContent = `Managing all subject & class section allocations for ${teacherName}`;

  // Populate semester select in modal
  const semSelect = document.getElementById('modalSemesterSelect');
  if (semSelect) {
    semSelect.innerHTML = '<option value="">Select Academic Term...</option>' +
      allSemesters.map(s => `<option value="${s.id}">${s.name}</option>`).join('');
  }

  // Populate class section checkboxes in modal — pill/chip grid style
  const modalClassCbContainer = document.getElementById('modalClassesCheckboxList');
  if (modalClassCbContainer) {
    if (allClasses.length === 0) {
      modalClassCbContainer.innerHTML = '<span style="color:#64748b; font-style:italic; font-size:0.82rem;">No class sections available.</span>';
    } else {
      modalClassCbContainer.innerHTML = `
        <div style="display:flex; justify-content:flex-end; margin-bottom:6px;">
          <button type="button" onclick="modalToggleAllCheckboxes('modal-class-cb', true)" style="background:none; border:none; color:#60a5fa; font-size:0.75rem; cursor:pointer; padding:0 4px;">Select All</button>
          <span style="color:#475569; font-size:0.75rem; padding:0 4px;">|</span>
          <button type="button" onclick="modalToggleAllCheckboxes('modal-class-cb', false)" style="background:none; border:none; color:#94a3b8; font-size:0.75rem; cursor:pointer; padding:0 4px;">Clear</button>
        </div>
        <div style="display:grid; grid-template-columns:repeat(auto-fill, minmax(130px, 1fr)); gap:6px;">
          ${allClasses.map(c => `
            <label class="modal-chip-label" onclick="handleModalChipToggle(this, 'modal-class-cb', handleModalClassCheckboxChange)" style="display:flex; align-items:center; gap:6px; padding:7px 10px; border-radius:7px; background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.1); cursor:pointer; transition:all 0.15s ease; user-select:none;">
              <input type="checkbox" class="modal-class-cb" value="${c.id}" style="display:none;" />
              <span class="chip-check" style="width:14px; height:14px; border-radius:3px; border:1.5px solid rgba(255,255,255,0.3); flex-shrink:0; display:flex; align-items:center; justify-content:center; font-size:10px; transition:all 0.15s;"></span>
              <span style="font-size:0.8rem; font-weight:500; color:#f1f5f9; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">🏫 ${c.name}</span>
            </label>
          `).join('')}
        </div>
      `;
    }
  }

  // Reset subject checkboxes list in modal
  const modalSubCbContainer = document.getElementById('modalSubjectsCheckboxList');
  if (modalSubCbContainer) {
    modalSubCbContainer.innerHTML = '<span style="opacity:0.6; font-style:italic; font-size:0.82rem;">Select class section(s) above to load subjects...</span>';
  }

  // Render Section 1: Active Allocated Workload Table
  renderModalActiveWorkload(teacherId);

  const modal = document.getElementById('editAssignmentModal');
  if (modal) modal.style.display = 'flex';
}

function renderModalActiveWorkload(teacherId) {
  const container = document.getElementById('modalActiveWorkloadContainer');
  if (!container) return;

  const tAsgns = allAssignmentsData.filter(a => String(a.teacher_id) === String(teacherId));
  if (tAsgns.length === 0) {
    container.innerHTML = '<p style="margin:4px 0; opacity:0.6; font-style:italic; font-size:0.85rem;">No subject teaching allocations assigned yet.</p>';
    return;
  }

  container.innerHTML = `
    <div style="overflow-x:auto;">
      <table style="width:100%; border-collapse:collapse; font-size:0.85rem; color:var(--text-primary);">
        <thead>
          <tr style="border-bottom:1px solid var(--border-color); text-align:left; opacity:0.8;">
            <th style="padding:8px 10px;">Subject Taught</th>
            <th style="padding:8px 10px;">Class Section</th>
            <th style="padding:8px 10px;">Academic Term</th>
            <th style="padding:8px 10px; text-align:center;">Action</th>
          </tr>
        </thead>
        <tbody>
          ${tAsgns.map(a => `
            <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
              <td style="padding:8px 10px;"><strong>📘 ${a.subject_name}</strong></td>
              <td style="padding:8px 10px;"><span style="background:rgba(59,130,246,0.15); color:var(--text-primary); padding:2px 8px; border-radius:4px; border:1px solid rgba(59,130,246,0.3);">${a.class_section_name}</span></td>
              <td style="padding:8px 10px; opacity:0.85;">${a.semester_name || 'General'}</td>
              <td style="padding:8px 10px; text-align:center;">
                <button type="button" class="btn sm danger" onclick="deleteAssignmentFromModal(${a.id}, ${teacherId})" style="padding:2px 8px; font-size:0.75rem;">🗑 Remove</button>
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}

async function deleteAssignmentFromModal(assignmentId, teacherId) {
  const ok = await (window.showConfirmDialog ? window.showConfirmDialog(
    '🗑️ Remove Allocation',
    'Are you sure you want to remove this teaching allocation?',
    'Remove Allocation',
    'Cancel',
    'warning'
  ) : Promise.resolve(confirm("Are you sure you want to remove this teaching allocation?")));

  if (!ok) return;
  try {
    const res = await fetch(`${API_BASE}/assignments/${assignmentId}`, {
      method: 'DELETE',
      headers: getHeaders()
    });
    if (res.ok) {
      await loadAssignments();
      renderModalActiveWorkload(teacherId);
    } else {
      const err = await res.json();
      alert(`Error: ${err.detail || 'Could not remove allocation'}`);
    }
  } catch (error) {
    alert("Failed to remove allocation.");
  }
}

async function handleModalClassCheckboxChange() {
  const checkedClassCbs = Array.from(document.querySelectorAll('.modal-class-cb:checked')).map(cb => cb.value);
  const container = document.getElementById('modalSubjectsCheckboxList');
  if (!container) return;

  if (checkedClassCbs.length === 0) {
    container.innerHTML = '<span style="opacity:0.6; font-style:italic; font-size:0.82rem;">Select class section(s) above to load subjects...</span>';
    return;
  }

  try {
    const subjectMap = new Map();
    for (const classId of checkedClassCbs) {
      const res = await fetch(`${API_BASE}/classes/${classId}/subjects`, { headers: getHeaders() });
      if (res.ok) {
        const subjects = await res.json();
        subjects.forEach(s => subjectMap.set(s.id, s));
      }
    }

    const uniqueSubjects = Array.from(subjectMap.values());
    if (uniqueSubjects.length === 0) {
      container.innerHTML = '<span style="opacity:0.6; font-style:italic; font-size:0.82rem;">No subjects configured for selected class section(s).</span>';
      return;
    }

    container.innerHTML = `
      <div style="display:flex; justify-content:flex-end; margin-bottom:6px;">
        <button type="button" onclick="modalToggleAllCheckboxes('modal-subject-cb', true)" style="background:none; border:none; color:#60a5fa; font-size:0.75rem; cursor:pointer; padding:0 4px;">Select All</button>
        <span style="color:#475569; font-size:0.75rem; padding:0 4px;">|</span>
        <button type="button" onclick="modalToggleAllCheckboxes('modal-subject-cb', false)" style="background:none; border:none; color:#94a3b8; font-size:0.75rem; cursor:pointer; padding:0 4px;">Clear</button>
      </div>
      <div style="display:grid; grid-template-columns:repeat(auto-fill, minmax(160px, 1fr)); gap:6px;">
        ${uniqueSubjects.map(s => `
          <label class="modal-chip-label" onclick="handleModalChipToggle(this, 'modal-subject-cb', null)" style="display:flex; align-items:flex-start; gap:6px; padding:8px 10px; border-radius:7px; background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.1); cursor:pointer; transition:all 0.15s ease; user-select:none;">
            <input type="checkbox" class="modal-subject-cb" value="${s.id}" style="display:none;" />
            <span class="chip-check" style="margin-top:2px; width:14px; height:14px; border-radius:3px; border:1.5px solid rgba(255,255,255,0.3); flex-shrink:0; display:flex; align-items:center; justify-content:center; font-size:10px; transition:all 0.15s;"></span>
            <div>
              <div style="font-size:0.8rem; font-weight:600; color:#f1f5f9; line-height:1.3;">📘 ${s.name}</div>
              <div style="font-size:0.72rem; color:#64748b; margin-top:1px;">${s.code || 'Core'}</div>
            </div>
          </label>
        `).join('')}
      </div>
    `;

  } catch (err) {
    console.error('Error loading modal class subjects:', err);
  }
}


// Toggle a single chip (label) — updates hidden checkbox + visual state
function handleModalChipToggle(labelEl, cbClass, onChangeCallback) {
  const cb = labelEl.querySelector(`input.${cbClass}`);
  if (!cb) return;

  // Prevent double-fire from native checkbox input
  event.preventDefault();
  cb.checked = !cb.checked;

  const chipCheck = labelEl.querySelector('.chip-check');
  if (cb.checked) {
    labelEl.style.borderColor = 'rgba(96,165,250,0.7)';
    labelEl.style.background = 'rgba(59,130,246,0.15)';
    if (chipCheck) {
      chipCheck.style.background = '#3b82f6';
      chipCheck.style.borderColor = '#3b82f6';
      chipCheck.textContent = '✓';
      chipCheck.style.color = '#fff';
    }
  } else {
    labelEl.style.borderColor = 'rgba(255,255,255,0.1)';
    labelEl.style.background = 'rgba(255,255,255,0.04)';
    if (chipCheck) {
      chipCheck.style.background = '';
      chipCheck.style.borderColor = 'rgba(255,255,255,0.3)';
      chipCheck.textContent = '';
    }
  }

  if (typeof onChangeCallback === 'function') onChangeCallback();
}

// Select all / clear all chips of a given class
function modalToggleAllCheckboxes(cbClass, selectAll) {
  const labels = document.querySelectorAll(`.modal-chip-label`);
  labels.forEach(label => {
    const cb = label.querySelector(`input.${cbClass}`);
    if (!cb) return;
    if (cb.checked === selectAll) return; // already in desired state
    cb.checked = selectAll;
    const chipCheck = label.querySelector('.chip-check');
    if (selectAll) {
      label.style.borderColor = 'rgba(96,165,250,0.7)';
      label.style.background = 'rgba(59,130,246,0.15)';
      if (chipCheck) {
        chipCheck.style.background = '#3b82f6';
        chipCheck.style.borderColor = '#3b82f6';
        chipCheck.textContent = '✓';
        chipCheck.style.color = '#fff';
      }
    } else {
      label.style.borderColor = 'rgba(255,255,255,0.1)';
      label.style.background = 'rgba(255,255,255,0.04)';
      if (chipCheck) {
        chipCheck.style.background = '';
        chipCheck.style.borderColor = 'rgba(255,255,255,0.3)';
        chipCheck.textContent = '';
      }
    }
  });
  // Trigger subject reload when class checkboxes change
  if (cbClass === 'modal-class-cb') handleModalClassCheckboxChange();
}

async function submitAddWorkloadInModal(event) {
  event.preventDefault();
  const teacherId = parseInt(document.getElementById('editModalTeacherId').value);
  const semesterId = parseInt(document.getElementById('modalSemesterSelect').value);
  const checkedClassIds = Array.from(document.querySelectorAll('.modal-class-cb:checked')).map(cb => parseInt(cb.value));
  const checkedSubjectIds = Array.from(document.querySelectorAll('.modal-subject-cb:checked')).map(cb => parseInt(cb.value));

  if (!teacherId) return alert("Teacher not found.");
  if (!semesterId) return alert("Select academic term.");
  if (checkedClassIds.length === 0) return alert("Select at least one Class Section.");
  if (checkedSubjectIds.length === 0) return alert("Select at least one Subject.");

  let successCount = 0;
  for (const classId of checkedClassIds) {
    for (const subId of checkedSubjectIds) {
      try {
        const payload = {
          teacher_id: teacherId,
          subject_id: subId,
          class_section_id: classId,
          semester_id: semesterId
        };
        const res = await fetch(`${API_BASE}/assignments/`, {
          method: 'POST',
          headers: getHeaders({ 'Content-Type': 'application/json' }),
          body: JSON.stringify(payload)
        });
        if (res.ok) successCount++;
      } catch (_) {}
    }
  }

  if (successCount > 0) {
    alert(`Successfully added ${successCount} teaching allocation(s).`);
    document.querySelectorAll('.modal-class-cb').forEach(cb => cb.checked = false);
    handleModalClassCheckboxChange();
    await loadAssignments();
    renderModalActiveWorkload(teacherId);
  } else {
    alert("Could not add allocations.");
  }
}

function closeEditAssignmentModal() {
  const modal = document.getElementById('editAssignmentModal');
  if (modal) modal.style.display = 'none';
}

async function deleteSingleAssignment(assignmentId, subjectName, className) {
  const ok = await (window.showConfirmDialog ? window.showConfirmDialog(
    '🗑️ Delete Assignment',
    `Are you sure you want to remove the assignment for ${subjectName} in ${className}?`,
    'Delete Assignment',
    'Cancel',
    'warning'
  ) : Promise.resolve(confirm(`Are you sure you want to remove the assignment for ${subjectName} in ${className}?`)));

  if (!ok) return;
  try {
    const res = await fetch(`${API_BASE}/assignments/${assignmentId}`, { method: 'DELETE', headers: getHeaders() });
    if (res.ok) {
      await loadAssignments();
    } else {
      const err = await res.json();
      alert(`Error: ${err.detail || 'Could not delete assignment'}`);
    }
  } catch (err) {
    alert('Failed to delete assignment.');
  }
}

window.switchAssignmentTab = switchAssignmentTab;
window.toggleAssignmentTab = toggleAssignmentTab;
window.deletePrivilege = deletePrivilege;
window.filterTeachingAssignments = filterTeachingAssignments;
window.handleClassCheckboxChange = handleClassCheckboxChange;
window.handleAssignChipToggle = handleAssignChipToggle;
window.applyAssignChipStyle = applyAssignChipStyle;
window.handleTeacherSelectChange = handleTeacherSelectChange;
window.resetEntireForm = resetEntireForm;
window.setWorkloadRoleFilter = setWorkloadRoleFilter;
window.removeAllTeacherAssignments = removeAllTeacherAssignments;
window.printStaffWorkloadRegister = printStaffWorkloadRegister;
window.openCopyWorkloadModal = openCopyWorkloadModal;
window.closeCopyWorkloadModal = closeCopyWorkloadModal;
window.submitCopyWorkload = submitCopyWorkload;
window.openEditTeacherWorkloadModal = openEditTeacherWorkloadModal;
window.deleteAssignmentFromModal = deleteAssignmentFromModal;
window.handleModalClassCheckboxChange = handleModalClassCheckboxChange;
window.handleModalChipToggle = handleModalChipToggle;
window.modalToggleAllCheckboxes = modalToggleAllCheckboxes;
window.submitAddWorkloadInModal = submitAddWorkloadInModal;
window.closeEditAssignmentModal = closeEditAssignmentModal;
window.deleteSingleAssignment = deleteSingleAssignment;

// ── 1-Click Primary Class Allocation Handlers ─────────────────────────────
const primaryFastAssignModal = document.getElementById('primaryFastAssignModal');
const btnOpenPrimaryFastAssign = document.getElementById('btnOpenPrimaryFastAssign');

function initPrimaryFastAssignButton() {
  const mode = (localStorage.getItem('school_mode') || 'COMBINED').toUpperCase();
  if (btnOpenPrimaryFastAssign) {
    if (_userIsAdmin() && (mode === 'BASIC_ONLY' || mode === 'COMBINED')) {
      btnOpenPrimaryFastAssign.style.display = 'inline-flex';
      btnOpenPrimaryFastAssign.style.alignItems = 'center';
      btnOpenPrimaryFastAssign.style.gap = '6px';
    } else {
      btnOpenPrimaryFastAssign.style.display = 'none';
    }
  }
}

async function openPrimaryFastAssignModal() {
  if (!primaryFastAssignModal) return;
  primaryFastAssignModal.style.display = 'flex';
  const msg = document.getElementById('fastAssignMsg');
  if (msg) msg.innerHTML = '';

  const teacherSel = document.getElementById('fastTeacherSelect');
  const classSel = document.getElementById('fastClassSelect');
  const semSel = document.getElementById('fastSemesterSelect');

  // Copy options from main dropdowns
  const mainTeacher = document.getElementById('teacherSelect');
  const mainSem = document.getElementById('semesterSelect');

  if (teacherSel && mainTeacher) {
    teacherSel.innerHTML = mainTeacher.innerHTML;
  }
  if (semSel && mainSem) {
    semSel.innerHTML = mainSem.innerHTML;
  }

  // Load and populate basic classes
  if (classSel) {
    try {
      const res = await fetch(`${API_BASE}/classes/`, { headers: getHeaders() });
      const classes = await res.json();
      const basicClasses = classes.filter(c => {
        const n = (c.name || '').toUpperCase();
        const st = (c.stage_name || '').toUpperCase();
        if (st.includes('SHS') || n.includes('FORM ') || n.includes('SHS')) return false;
        return true;
      });

      classSel.innerHTML = '<option value="">Select Primary / Early Childhood Class...</option>' +
        basicClasses.map(c => `<option value="${c.id}">🏫 ${c.name} (${c.stage_name || 'Basic'})</option>`).join('');
    } catch (e) {
      classSel.innerHTML = '<option value="">Error loading classes</option>';
    }
  }
}

function closePrimaryFastAssignModal() {
  if (primaryFastAssignModal) primaryFastAssignModal.style.display = 'none';
}

async function submitPrimaryFastAssign(event) {
  event.preventDefault();
  const btn = document.getElementById('btnRunFastAssign');
  const msg = document.getElementById('fastAssignMsg');
  if (btn) { btn.disabled = true; btn.textContent = '⏳ Allocating Class Subjects...'; }
  if (msg) msg.innerHTML = '';

  const teacherId = parseInt(document.getElementById('fastTeacherSelect')?.value);
  const classId = parseInt(document.getElementById('fastClassSelect')?.value);
  const semId = parseInt(document.getElementById('fastSemesterSelect')?.value);

  if (!teacherId || !classId || !semId) {
    if (msg) msg.innerHTML = '<div style="color:#f87171;">Please select a teacher, class, and semester.</div>';
    if (btn) { btn.disabled = false; btn.textContent = '⚡ Assign to All Subjects'; }
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/teacher-assignments/assign-primary-class`, {
      method: 'POST',
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({
        teacher_id: teacherId,
        class_section_id: classId,
        semester_id: semId
      })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || data.message || 'Allocation failed');

    if (msg) {
      msg.innerHTML = `
        <div style="background:rgba(16,185,129,0.15); color:#34d399; border:1px solid rgba(16,185,129,0.3); padding:10px 14px; border-radius:8px;">
          ✓ <strong>Success:</strong> ${data.message}
        </div>
      `;
    }

    if (window.showToast) window.showToast(data.message || 'Class Teacher successfully assigned!', 'success');
    await loadAssignments();
    await loadPrivileges();

    setTimeout(() => {
      closePrimaryFastAssignModal();
    }, 1800);
  } catch (err) {
    if (msg) {
      msg.innerHTML = `
        <div style="background:rgba(239,68,68,0.15); color:#f87171; border:1px solid rgba(239,68,68,0.3); padding:10px 14px; border-radius:8px;">
          ❌ <strong>Error:</strong> ${err.message}
        </div>
      `;
    }
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = '⚡ Assign to All Subjects'; }
  }
}

window.openPrimaryFastAssignModal = openPrimaryFastAssignModal;
window.closePrimaryFastAssignModal = closePrimaryFastAssignModal;
window.submitPrimaryFastAssign = submitPrimaryFastAssign;

async function initAssignmentsPage() {
  await loadDropdowns();
  await loadAssignments();
  await loadPrivileges();
  filterTeachingAssignments();
  initPrimaryFastAssignButton();

  if (!_userIsAdmin()) {
    // Hide Copy to Next Term button for non-admins (HODs)
    const copyBtn = document.getElementById('openCopyModalBtn') || document.querySelector('button[onclick*="openCopyWorkloadModal"]');
    if (copyBtn) copyBtn.style.display = 'none';

    // Lock Category selector to Subject Teaching Assignment for HOD persona
    const catSelect = document.getElementById('assignmentCategorySelect') || document.getElementById('privilegeTypeSelect');
    if (catSelect) {
      Array.from(catSelect.options).forEach(opt => {
        if (opt.value && opt.value !== 'subject' && opt.value !== 'SUBJECT_TEACHING') {
          opt.disabled = true;
          opt.hidden = true;
        }
      });
      catSelect.value = catSelect.querySelector('option[value="subject"], option[value="SUBJECT_TEACHING"]')?.value || catSelect.value;
    }
  }
}

initAssignmentsPage();

const filterInput = document.getElementById('filterAssignmentSearch');
if (filterInput) {
  filterInput.value = '';
}


