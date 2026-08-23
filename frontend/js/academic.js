const API_BASE = window.API_BASE || (window.location.origin.includes('http') ? (window.location.origin + '/api') : 'http://127.0.0.1:8000/api');

const token = localStorage.getItem('accessToken');
if (!token) window.location.href = 'auth.html';

function getHeaders(extra = {}) {
  return { 'Authorization': `Bearer ${token}`, ...extra };
}

function showMsg(id, html) {
  const el = document.getElementById(id);
  if (el) el.innerHTML = html;
}

function populateTermDropdowns() {
  const mode = localStorage.getItem('school_mode') || 'COMBINED';
  let options = [];
  if (mode === 'BASIC_ONLY') {
    options = [
      { val: 'Term 1', label: 'Term 1 (First Term)' },
      { val: 'Term 2', label: 'Term 2 (Second Term)' },
      { val: 'Term 3', label: 'Term 3 (Third Term)' }
    ];
  } else if (mode === 'SHS_ONLY') {
    options = [
      { val: 'Semester 1', label: 'Semester 1' },
      { val: 'Semester 2', label: 'Semester 2' }
    ];
  } else {
    options = [
      { val: 'Term 1', label: 'Term 1 (First Term)' },
      { val: 'Term 2', label: 'Term 2 (Second Term)' },
      { val: 'Term 3', label: 'Term 3 (Third Term)' },
      { val: 'Semester 1', label: 'Semester 1' },
      { val: 'Semester 2', label: 'Semester 2' }
    ];
  }
  const optsHtml = '<option value="">Select Term / Semester...</option>' +
    options.map(o => `<option value="${o.val}">${o.label}</option>`).join('');

  const semSel = document.getElementById('semesterName');
  const editSemSel = document.getElementById('editSemesterName');
  if (semSel) semSel.innerHTML = optsHtml;
  if (editSemSel) editSemSel.innerHTML = optsHtml;
}

window.autoGenerateTerms = async function() {
  const yearSelect = document.getElementById('academic_year_id');
  const yearId = parseInt(yearSelect?.value);
  if (!yearId) {
    alert("Please select an Academic Year first from the dropdown.");
    return;
  }
  const mode = localStorage.getItem('school_mode') || 'COMBINED';
  const termList = (mode === 'BASIC_ONLY') ? ['Term 1', 'Term 2', 'Term 3']
    : (mode === 'SHS_ONLY') ? ['Semester 1', 'Semester 2']
    : ['Term 1', 'Term 2', 'Term 3'];

  let count = 0;
  for (const name of termList) {
    try {
      const res = await fetch(`${API_BASE}/academic/semesters`, {
        method: 'POST',
        headers: getHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ name, academic_year_id: yearId, is_current: false }),
      });
      if (res.ok) count++;
    } catch (_) {}
  }
  showMsg('semesterMsg', `<span style="color:var(--success-color)">✔ Auto-generated ${count} terms/semesters.</span>`);
  loadYearsList();
};

// ── Load & Render Years List ────────────────────────────────────────────────
async function loadYearsList() {
  populateTermDropdowns();
  const container = document.getElementById('yearsList');
  const yearSelect = document.getElementById('academic_year_id');

  try {
    const res = await fetch(`${API_BASE}/academic/years`, { headers: getHeaders() });
    const years = await res.json();

    if (!years.length) {
      container.innerHTML = '<p style="opacity:.6; text-align:center; padding:20px;">No academic years defined yet.</p>';
      yearSelect.innerHTML = '<option value="">No years available</option>';
      return;
    }

    // Update the semester form dropdown
    yearSelect.innerHTML = '<option value="">Select Year...</option>' +
      years.map(y => `<option value="${y.id}">${y.label}</option>`).join('');

    // Render the years list with nested semesters
    container.innerHTML = years.map(year => `
      <div style="border:1px solid var(--border-color); border-radius:10px; padding:14px; margin-bottom:12px; background:var(--bg-card);">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
          <div style="display:flex; align-items:center; gap:10px;">
            <strong style="font-size:1rem;">${year.label}</strong>
            ${year.is_current ? '<span class="chip success">Current</span>' : ''}
          </div>
          <div style="display:flex; gap:8px; flex-wrap:wrap;">
            <button class="btn" style="font-size:.8rem; padding:4px 10px;" onclick="openEditYearModal(${year.id}, '${year.label}', ${year.is_current})">✏ Edit</button>
            ${!year.is_current ? `
              <button class="btn" style="font-size:.8rem; padding:4px 10px;" onclick="setCurrentYear(${year.id})">⭐ Set Current</button>
            ` : ''}
            <button class="btn" style="font-size:.8rem; padding:4px 10px; color:var(--error-color); border-color:var(--error-color);"
              onclick="deleteYear(${year.id}, '${year.label}')">🗑 Delete</button>
          </div>
        </div>

        ${year.semesters && year.semesters.length ? `
          <div style="margin-top:12px; padding-left:12px; border-left:2px solid var(--border-color);">
            ${year.semesters.map(sem => `
              <div style="display:flex; justify-content:space-between; align-items:center; padding:6px 0; flex-wrap:wrap; gap:6px;">
                <span style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
                  📅 <strong>${sem.name}</strong>
                  ${sem.start_date && sem.end_date ? `<span style="font-size:0.8rem; opacity:0.6; margin-left:6px;">(${sem.start_date} to ${sem.end_date})</span>` : ''}
                  ${sem.is_current ? '<span class="chip success" style="font-size:.7rem; margin-left:6px;">Current</span>' : ''}
                </span>
                <div style="display:flex; gap:6px;">
                  <button class="btn" style="font-size:.75rem; padding:3px 8px;" onclick="openEditSemesterModal(${sem.id}, '${sem.name}', '${sem.start_date || ''}', '${sem.end_date || ''}', ${sem.is_current})">✏ Edit</button>
                  ${!sem.is_current ? `
                    <button class="btn" style="font-size:.75rem; padding:3px 8px;" onclick="setCurrentSemester(${sem.id})">⭐ Set Current</button>
                  ` : ''}
                  <button class="btn" style="font-size:.75rem; padding:3px 8px; color:var(--error-color); border-color:var(--error-color);"
                    onclick="deleteSemester(${sem.id}, '${sem.name}')">🗑</button>
                </div>
              </div>
            `).join('')}
          </div>
        ` : '<p style="margin-top:8px; opacity:.5; font-size:.85rem;">No semesters yet.</p>'}
      </div>
    `).join('');
  } catch (e) {
    container.innerHTML = `<p style="color:var(--error-color);">Failed to load years: ${e.message}</p>`;
  }
}

// ── Deprecated loadYears — kept for backward compatibility ─────────────────
async function loadYears() {
  await loadYearsList();
}

// ── Set Current Year ────────────────────────────────────────────────────────
async function setCurrentYear(yearId) {
  try {
    const res = await fetch(`${API_BASE}/academic/years/${yearId}/set-current`, {
      method: 'PATCH',
      headers: getHeaders(),
    });
    if (!res.ok) throw new Error('Failed');
    const data = await res.json();
    showMsg('academicMsg', `<span style="color:var(--success-color)">✔ ${data.message}</span>`);
    loadYearsList();
  } catch (e) {
    showMsg('academicMsg', `<span style="color:var(--error-color)">Failed: ${e.message}</span>`);
  }
}

// ── Delete Year ─────────────────────────────────────────────────────────────
async function deleteYear(yearId, label) {
  if (!confirm(`Delete academic year "${label}" and all its semesters? This cannot be undone.`)) return;
  try {
    const res = await fetch(`${API_BASE}/academic/years/${yearId}`, {
      method: 'DELETE',
      headers: getHeaders(),
    });
    if (!res.ok) throw new Error('Failed');
    showMsg('academicMsg', `<span style="color:var(--success-color)">✔ "${label}" deleted.</span>`);
    loadYearsList();
  } catch (e) {
    showMsg('academicMsg', `<span style="color:var(--error-color)">Failed: ${e.message}</span>`);
  }
}

// ── Set Current Semester ────────────────────────────────────────────────────
async function setCurrentSemester(semesterId) {
  try {
    const res = await fetch(`${API_BASE}/academic/semesters/${semesterId}/set-current`, {
      method: 'PATCH',
      headers: getHeaders(),
    });
    if (!res.ok) throw new Error('Failed');
    const data = await res.json();
    showMsg('academicMsg', `<span style="color:var(--success-color)">✔ ${data.message}</span>`);
    loadYearsList();
  } catch (e) {
    showMsg('academicMsg', `<span style="color:var(--error-color)">Failed: ${e.message}</span>`);
  }
}

// ── Delete Semester ─────────────────────────────────────────────────────────
async function deleteSemester(semesterId, name) {
  if (!confirm(`Delete semester "${name}"?`)) return;
  try {
    const res = await fetch(`${API_BASE}/academic/semesters/${semesterId}`, {
      method: 'DELETE',
      headers: getHeaders(),
    });
    if (!res.ok) throw new Error('Failed');
    showMsg('academicMsg', `<span style="color:var(--success-color)">✔ "${name}" deleted.</span>`);
    loadYearsList();
  } catch (e) {
    showMsg('academicMsg', `<span style="color:var(--error-color)">Failed: ${e.message}</span>`);
  }
}

// ── Add Academic Year Form ──────────────────────────────────────────────────
const yearForm = document.getElementById('yearForm');
if (yearForm) {
  yearForm.addEventListener('submit', async (e) => {
    const startDateVal = document.getElementById('yearStartDate')?.value;
    const endDateVal = document.getElementById('yearEndDate')?.value;
    const payload = {
      label: document.getElementById('yearLabel').value,
      is_current: false,
      start_date: startDateVal || null,
      end_date: endDateVal || null
    };
    try {
      const res = await fetch(`${API_BASE}/academic/years`, {
        method: 'POST',
        headers: getHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Failed to create');
      }
      showMsg('yearMsg', '<span style="color:var(--success-color)">✔ Academic year created.</span>');
      yearForm.reset();
      loadYearsList();
    } catch (e) {
      showMsg('yearMsg', `<span style="color:var(--error-color)">❌ ${e.message}</span>`);
    }
  });
}

// ── Add Semester Form ───────────────────────────────────────────────────────
const semesterForm = document.getElementById('semesterForm');
if (semesterForm) {
  semesterForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const yearId = parseInt(document.getElementById('academic_year_id').value);
    if (!yearId) { showMsg('semesterMsg', '<span style="color:var(--error-color)">Select an academic year first.</span>'); return; }

    const startDateVal = document.getElementById('semesterStartDate').value;
    const endDateVal = document.getElementById('semesterEndDate').value;

    const payload = {
      name: document.getElementById('semesterName').value,
      academic_year_id: yearId,
      is_current: false,
      start_date: startDateVal ? `${startDateVal}T00:00:00` : null,
      end_date: endDateVal ? `${endDateVal}T00:00:00` : null,
    };
    try {
      const res = await fetch(`${API_BASE}/academic/semesters`, {
        method: 'POST',
        headers: getHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error('Failed to create semester');
      showMsg('semesterMsg', '<span style="color:var(--success-color)">✔ Semester created.</span>');
      semesterForm.reset();
      loadYearsList();
    } catch (e) {
      showMsg('semesterMsg', `<span style="color:var(--error-color)">❌ ${e.message}</span>`);
    }
  });
}

// ── Promote Button ──────────────────────────────────────────────────────────
const promoteBtn = document.getElementById('promoteBtn');
if (promoteBtn) {
  promoteBtn.addEventListener('click', async () => {
    if (!confirm('This will promote ALL active students to the next form. Proceed?')) return;
    try {
      const res = await fetch(`${API_BASE}/academic/promote`, {
        method: 'POST',
        headers: getHeaders(),
      });
      if (res.ok) {
        const data = await res.json();
        showMsg('promoteMsg', `<span style="color:var(--success-color)">✔ Promotion complete — Promoted: ${data.promoted}, Graduated: ${data.graduated}</span>`);
      } else {
        showMsg('promoteMsg', '<span style="color:var(--error-color)">❌ Promotion failed.</span>');
      }
    } catch (e) {
      showMsg('promoteMsg', `<span style="color:var(--error-color)">❌ ${e.message}</span>`);
    }
  });
}

// ── Edit Academic Year Modal Controls ────────────────────────────────────────
window.openEditYearModal = function(id, label, isCurrent) {
  document.getElementById('editYearId').value = id;
  document.getElementById('editYearLabel').value = label;
  document.getElementById('editYearIsCurrent').checked = isCurrent;
  document.getElementById('editYearMsg').innerHTML = '';
  document.getElementById('editYearModal').classList.add('open');
};

window.closeEditYearModal = function() {
  document.getElementById('editYearModal').classList.remove('open');
};

window.saveEditYear = async function(event) {
  event.preventDefault();
  const id = document.getElementById('editYearId').value;
  const label = document.getElementById('editYearLabel').value;
  const isCurrent = document.getElementById('editYearIsCurrent').checked;

  const payload = { label, is_current: isCurrent };
  try {
    const res = await fetch(`${API_BASE}/academic/years/${id}`, {
      method: 'PUT',
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to update academic year');
    }

    showMsg('editYearMsg', '<span style="color:var(--success-color)">✔ Saved successfully.</span>');
    setTimeout(() => {
      closeEditYearModal();
      loadYearsList();
    }, 500);
  } catch (e) {
    showMsg('editYearMsg', `<span style="color:var(--error-color)">❌ ${e.message}</span>`);
  }
};

// ── Edit Semester Modal Controls ─────────────────────────────────────────────
window.openEditSemesterModal = function(id, name, startDate, endDate, isCurrent) {
  document.getElementById('editSemesterId').value = id;
  document.getElementById('editSemesterName').value = name;
  document.getElementById('editSemesterStartDate').value = startDate || '';
  document.getElementById('editSemesterEndDate').value = endDate || '';
  document.getElementById('editSemesterIsCurrent').checked = isCurrent;
  document.getElementById('editSemesterMsg').innerHTML = '';
  document.getElementById('editSemesterModal').classList.add('open');
};

window.closeEditSemesterModal = function() {
  document.getElementById('editSemesterModal').classList.remove('open');
};

window.saveEditSemester = async function(event) {
  event.preventDefault();
  const id = document.getElementById('editSemesterId').value;
  const name = document.getElementById('editSemesterName').value;
  const startDateVal = document.getElementById('editSemesterStartDate').value;
  const endDateVal = document.getElementById('editSemesterEndDate').value;
  const isCurrent = document.getElementById('editSemesterIsCurrent').checked;

  const payload = {
    name: name,
    is_current: isCurrent,
    start_date: startDateVal ? `${startDateVal}T00:00:00` : null,
    end_date: endDateVal ? `${endDateVal}T00:00:00` : null,
  };

  try {
    const res = await fetch(`${API_BASE}/academic/semesters/${id}`, {
      method: 'PUT',
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to update semester');
    }

    showMsg('editSemesterMsg', '<span style="color:var(--success-color)">✔ Saved successfully.</span>');
    setTimeout(() => {
      closeEditSemesterModal();
      loadYearsList();
    }, 500);
  } catch (e) {
    showMsg('editSemesterMsg', `<span style="color:var(--error-color)">❌ ${e.message}</span>`);
  }
};

// ── Init ────────────────────────────────────────────────────────────────────
loadYearsList();
