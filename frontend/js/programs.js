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

const form = document.getElementById('programForm');
const container = document.getElementById('programList');

async function loadPrograms() {
  try {
    const response = await fetch(`${API_BASE}/programs/`, { headers: getHeaders() });
    const data = await response.json();

    if (!Array.isArray(data) || data.length === 0) {
      container.innerHTML = 'No programs available yet.';
      return;
    }

    container.innerHTML = `<ul>${data.map((item) => `
      <li style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; border-bottom: 1px solid var(--border-color); padding-bottom: 8px;">
        <span><strong>${item.name}</strong></span>
        <div>
          <button type="button" class="btn" style="padding:4px 8px; font-size:0.85rem; margin-right:4px;" onclick="openSubjectsModal(${item.id}, '${item.name.replace(/'/g, "\\'")}')">📚 Subjects</button>
          <button type="button" data-delete="${item.id}" class="btn danger" style="padding:4px 8px; font-size:0.85rem;">Delete</button>
        </div>
      </li>
    `).join('')}</ul>`;
  } catch (error) {
    container.textContent = 'Unable to load programs.';
  }
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const id = document.getElementById('programId').value;
  const payload = {
    name: document.getElementById('programName').value,
  };

  const response = await fetch(`${API_BASE}/programs/${id ? id : ''}`, {
    method: id ? 'PUT' : 'POST',
    headers: getHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    alert('Could not save program.');
    return;
  }

  form.reset();
  loadPrograms();
});

container.addEventListener('click', async (event) => {
  const deleteId = event.target.getAttribute('data-delete');

  if (deleteId) {
    if (!confirm('Delete this program?')) return;
    await fetch(`${API_BASE}/programs/${deleteId}`, { method: 'DELETE', headers: getHeaders() });
    loadPrograms();
  }
});

document.getElementById('cancelProgramBtn').addEventListener('click', () => form.reset());

// --- Manage Program Subjects Modal Logic ---
const subjectsModal = document.getElementById('subjectsModal');
const modalProgramName = document.getElementById('modalProgramName');
const modalProgramId = document.getElementById('modalProgramId');
const subjectsCheckboxList = document.getElementById('subjectsCheckboxList');
const subjectsForm = document.getElementById('subjectsForm');
const closeSubjectsModalBtn = document.getElementById('closeSubjectsModalBtn');

async function openSubjectsModal(programId, programName) {
  modalProgramId.value = programId;
  modalProgramName.textContent = `Program: ${programName}`;
  subjectsCheckboxList.innerHTML = '<p style="opacity:.6">Loading subjects...</p>';
  subjectsModal.style.display = 'flex';

  try {
    const [resAll, resCurrent] = await Promise.all([
      fetch(`${API_BASE}/subjects/?exclude_basic=true`, { headers: getHeaders() }),
      fetch(`${API_BASE}/programs/${programId}/subjects`, { headers: getHeaders() })
    ]);

    if (!resAll.ok || !resCurrent.ok) {
      throw new Error('Failed to fetch subjects');
    }

    const allSubjects = await resAll.json();
    const currentSubjects = await resCurrent.json();
    const currentIds = new Set(currentSubjects.map(s => s.id));

    if (allSubjects.length === 0) {
      subjectsCheckboxList.innerHTML = '<p style="opacity:.6">No SHS/STEM subjects available in the system. Add SHS subjects first.</p>';
      return;
    }

    const shsStemSubjects = allSubjects.filter(s => (s.school_level || 'SHS') !== 'Basic');
    const coreSubjects = shsStemSubjects.filter(s => s.is_core);
    const electiveSubjects = shsStemSubjects.filter(s => !s.is_core);

    const renderSubjectItem = (sub) => {
      const isChecked = currentIds.has(sub.id);
      const chipBg  = isChecked ? 'rgba(59,130,246,0.15)' : 'rgba(255,255,255,0.04)';
      const chipBdr = isChecked ? 'rgba(96,165,250,0.7)'  : 'rgba(255,255,255,0.1)';
      const checkBg = isChecked ? '#3b82f6'               : 'transparent';
      const checkBdr= isChecked ? '#3b82f6'               : 'rgba(255,255,255,0.3)';
      const checkTxt= isChecked ? '✓'                     : '';
      return `
        <label onclick="programSubjectChipToggle(this)"
          style="display:flex; align-items:flex-start; gap:8px; padding:9px 11px; border-radius:8px;
                 background:${chipBg}; border:1px solid ${chipBdr};
                 cursor:pointer; transition:all 0.15s ease; user-select:none;">
          <input type="checkbox" name="subjectIds" value="${sub.id}" ${isChecked ? 'checked' : ''} style="display:none;" />
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
        </label>`;
    };

    let html = '';
    if (coreSubjects.length > 0) {
      html += `<div style="font-size:0.78rem; font-weight:700; text-transform:uppercase; letter-spacing:0.5px; color:#818cf8; margin:4px 0 8px 0;">📘 Core Subjects</div>`;
      html += `<div style="display:grid; grid-template-columns:repeat(auto-fill, minmax(175px, 1fr)); gap:6px; margin-bottom:16px;">`;
      html += coreSubjects.map(renderSubjectItem).join('');
      html += `</div>`;
    }
    if (electiveSubjects.length > 0) {
      html += `<div style="font-size:0.78rem; font-weight:700; text-transform:uppercase; letter-spacing:0.5px; color:#facc15; margin:4px 0 8px 0;">📙 Elective Subjects</div>`;
      html += `<div style="display:grid; grid-template-columns:repeat(auto-fill, minmax(175px, 1fr)); gap:6px;">`;
      html += electiveSubjects.map(renderSubjectItem).join('');
      html += `</div>`;
    }
    subjectsCheckboxList.innerHTML = html;
  } catch (error) {
    console.error('Error opening subjects modal:', error);
    subjectsCheckboxList.innerHTML = '<p style="color:var(--error-color)">Error loading subjects.</p>';
  }
}

closeSubjectsModalBtn.addEventListener('click', () => {
  subjectsModal.style.display = 'none';
});

function programSubjectChipToggle(labelEl) {
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
    if (span) { span.style.background = 'transparent'; span.style.borderColor = 'rgba(255,255,255,0.3)'; span.textContent = ''; }
  }
}

subjectsForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const programId = modalProgramId.value;
  const checkboxes = subjectsForm.querySelectorAll('input[name="subjectIds"]:checked');
  const payload = Array.from(checkboxes).map(cb => parseInt(cb.value));

  try {
    const response = await fetch(`${API_BASE}/programs/${programId}/subjects`, {
      method: 'POST',
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      throw new Error('Failed to save subject associations');
    }

    alert('Program subjects updated successfully!');
    subjectsModal.style.display = 'none';
  } catch (error) {
    alert(`Could not save subjects: ${error.message}`);
  }
});

window.openSubjectsModal = openSubjectsModal;

loadPrograms();
