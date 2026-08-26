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

let currentCurriculumData = null;

document.addEventListener('DOMContentLoaded', () => {
  loadPrograms();
});

async function loadPrograms() {
  try {
    const response = await fetch(`${API_BASE}/programs/`, { headers: getHeaders() });
    const data = await response.json();

    if (!Array.isArray(data) || data.length === 0) {
      container.innerHTML = '<p style="opacity:.6">No academic programs registered yet. Add your first program below.</p>';
      return;
    }

    // Load curriculum overview counts for each program
    const listHtml = await Promise.all(data.map(async (item) => {
      let coreCount = 0;
      let pkgCount = 0;
      try {
        const curRes = await fetch(`${API_BASE}/programs/${item.id}/curriculum`, { headers: getHeaders() });
        if (curRes.ok) {
          const curData = await curRes.json();
          coreCount = curData.core_subjects ? curData.core_subjects.length : 0;
          pkgCount = curData.elective_combinations ? curData.elective_combinations.length : 0;
        }
      } catch (_) {}

      return `
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px; border-bottom: 1px solid var(--border-color); padding-bottom: 10px;">
          <div>
            <div style="display:flex; align-items:center; gap:8px;">
              <strong style="font-size:0.95rem; color:#f8fafc;">${item.name}</strong>
              ${item.code ? `<span style="font-size:0.75rem; background:rgba(99,102,241,0.15); color:#818cf8; padding:2px 6px; border-radius:4px; font-family:monospace;">${item.code}</span>` : ''}
            </div>
            <div style="font-size:0.8rem; color:#94a3b8; margin-top:4px; display:flex; gap:12px;">
              <span>📘 Cores: <strong style="color:#60a5fa;">${coreCount}</strong></span>
              <span>📦 Elective Packages: <strong style="color:#facc15;">${pkgCount}</strong></span>
            </div>
          </div>
          <div style="display:flex; gap:6px;">
            <button type="button" class="btn" style="padding:5px 12px; font-size:0.82rem; background:rgba(99,102,241,0.2); color:#a5b4fc; border:1px solid rgba(99,102,241,0.4);" onclick="openCurriculumModal(${item.id}, '${item.name.replace(/'/g, "\\'")}', '${item.code || ''}')">
              ⚙ Curriculum & Packages
            </button>
            <button type="button" data-delete="${item.id}" class="btn danger" style="padding:5px 10px; font-size:0.82rem;">Delete</button>
          </div>
        </div>
      `;
    }));

    container.innerHTML = listHtml.join('');
  } catch (error) {
    container.textContent = 'Unable to load programs.';
  }
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const id = document.getElementById('programId').value;
  const payload = {
    name: document.getElementById('programName').value.trim(),
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
    if (!confirm('Delete this program? This will also remove its associated combinations.')) return;
    await fetch(`${API_BASE}/programs/${deleteId}`, { method: 'DELETE', headers: getHeaders() });
    loadPrograms();
  }
});

document.getElementById('cancelProgramBtn').addEventListener('click', () => form.reset());


// ── Curriculum & Elective Packages Modal Logic ─────────────────────────────────

const curriculumModal = document.getElementById('curriculumModal');
const modalCurriculumTitle = document.getElementById('modalCurriculumTitle');
const modalCurriculumSubtitle = document.getElementById('modalCurriculumSubtitle');
const curriculumProgramId = document.getElementById('curriculumProgramId');

function switchCurriculumTab(tab) {
  const tabCore = document.getElementById('tabContentCore');
  const tabPkg = document.getElementById('tabContentPackages');
  const btnCore = document.getElementById('tabBtnCore');
  const btnPkg = document.getElementById('tabBtnPackages');

  if (tab === 'core') {
    tabCore.style.display = 'block';
    tabPkg.style.display = 'none';
    btnCore.className = 'curriculum-tab-btn active';
    btnPkg.className = 'curriculum-tab-btn';
  } else {
    tabCore.style.display = 'none';
    tabPkg.style.display = 'block';
    btnCore.className = 'curriculum-tab-btn';
    btnPkg.className = 'curriculum-tab-btn active';
  }
}
window.switchCurriculumTab = switchCurriculumTab;

async function openCurriculumModal(programId, programName, programCode) {
  curriculumProgramId.value = programId;
  modalCurriculumTitle.textContent = `🎓 ${programName}`;
  modalCurriculumSubtitle.textContent = `Configure custom mandatory core subjects and approved elective packages for this track.`;
  curriculumModal.style.display = 'flex';
  switchCurriculumTab('core');

  await loadCurriculumData(programId);
}
window.openCurriculumModal = openCurriculumModal;

function closeCurriculumModal() {
  curriculumModal.style.display = 'none';
  loadPrograms();
}
window.closeCurriculumModal = closeCurriculumModal;

async function loadCurriculumData(programId) {
  const coreContainer = document.getElementById('coreSubjectsContainer');
  const pkgContainer = document.getElementById('packagesListContainer');
  const electivesList = document.getElementById('packageElectivesCheckboxList');
  const sectionSelect = document.getElementById('pkg_class_section_id');

  coreContainer.innerHTML = '<p style="opacity:.6">Loading curriculum...</p>';
  pkgContainer.innerHTML = '<p style="opacity:.6">Loading packages...</p>';

  try {
    const res = await fetch(`${API_BASE}/programs/${programId}/curriculum`, { headers: getHeaders() });
    if (!res.ok) throw new Error('Failed to load curriculum data');

    currentCurriculumData = await res.json();

    // 1. Render Track Core Subjects
    const configuredCoreIds = new Set((currentCurriculumData.core_subjects || []).map(s => s.id));
    const allSubjects = currentCurriculumData.all_subjects || [];

    const isBasicOrKGSubject = (s) => {
      const lvl = (s.school_level || '').toUpperCase();
      const code = (s.code || '').toUpperCase();
      const name = (s.name || '').toLowerCase();
      if (lvl === 'BASIC' || lvl === 'KG' || lvl === 'PRIMARY' || lvl === 'JHS') return true;
      if (code.endsWith('-BAS') || code.endsWith('-KG') || code.endsWith('-JHS') || code.endsWith('-PRIM')) return true;
      if (name.includes('(basic)') || name.includes('(kg)')) return true;
      const kgKeywords = ['sensory', 'rhymes', 'early numeracy', 'creative play', 'language and literacy', 'our world our people', 'physical development'];
      if (kgKeywords.some(k => name.includes(k)) && !name.includes('(shs)')) return true;
      return false;
    };

    // Filter to purely SHS and STEM subjects
    const shsSubjects = allSubjects.filter(s => !isBasicOrKGSubject(s));

    // Core candidates for SHS
    const coreCandidates = shsSubjects.filter(s => s.is_core || s.category === 'Core' || ['english language', 'core mathematics', 'social studies', 'general science', 'integrated science', 'peh'].some(k => s.name.toLowerCase().includes(k)));

    if (coreCandidates.length === 0) {
      coreContainer.innerHTML = '<p style="opacity:.6">No core subjects registered in the system yet. Please add subjects first.</p>';
    } else {
      coreContainer.innerHTML = `
        <div style="display:grid; grid-template-columns:repeat(auto-fill, minmax(220px, 1fr)); gap:8px;">
          ${coreCandidates.map(sub => {
            const isChecked = configuredCoreIds.has(sub.id);
            return `
              <label style="display:flex; align-items:center; gap:8px; padding:10px; border-radius:8px; background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.08); cursor:pointer;">
                <input type="checkbox" name="trackCoreSubjectIds" value="${sub.id}" ${isChecked ? 'checked' : ''} onchange="updateCoreSubjectsCountBadge()" />
                <div>
                  <div style="font-weight:600; font-size:0.85rem; color:#f1f5f9;">${sub.name}</div>
                  <div style="font-size:0.72rem; color:#818cf8; font-family:monospace;">${sub.code || 'CORE'}</div>
                </div>
              </label>
            `;
          }).join('')}
        </div>
      `;
    }
    updateCoreSubjectsCountBadge();

    // 2. Render Packages List
    renderPackagesList(currentCurriculumData.elective_combinations || []);

    // 3. Populate Stream Picker in New Package Form
    const availableSections = currentCurriculumData.available_sections || [];
    sectionSelect.innerHTML = `
      <option value="">-- Select Target Form 1 Class Stream --</option>
      ${availableSections.map(sec => `<option value="${sec.id}">${sec.name}</option>`).join('')}
    `;

    // 4. Populate Electives Checkbox in New Package Form (True SHS Electives)
    const electiveCandidates = shsSubjects.filter(s => {
      const n = s.name.toLowerCase();
      if (['core mathematics', 'social studies (shs)', 'english language (shs)'].includes(n)) return false;
      return true;
    });

    if (electiveCandidates.length === 0) {
      electivesList.innerHTML = '<p style="opacity:.6">No elective subjects available. Add subjects in Subjects page.</p>';
    } else {
      electivesList.innerHTML = `
        <div style="display:grid; grid-template-columns:repeat(auto-fill, minmax(200px, 1fr)); gap:6px;">
          ${electiveCandidates.map(sub => `
            <label style="display:flex; align-items:center; gap:6px; padding:6px 8px; border-radius:6px; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.06); cursor:pointer; font-size:0.8rem;">
              <input type="checkbox" name="pkgSubjectIds" value="${sub.id}" />
              <span>${sub.name}</span>
            </label>
          `).join('')}
        </div>
      `;
    }

  } catch (err) {
    coreContainer.textContent = `❌ ${err.message}`;
    pkgContainer.textContent = `❌ ${err.message}`;
  }
}

function updateCoreSubjectsCountBadge() {
  const checked = document.querySelectorAll('input[name="trackCoreSubjectIds"]:checked');
  const badge = document.getElementById('coreSubjectsCountBadge');
  if (badge) {
    badge.textContent = `✔ ${checked.length} Core Subject${checked.length === 1 ? '' : 's'} Selected for this Track`;
  }
}
window.updateCoreSubjectsCountBadge = updateCoreSubjectsCountBadge;

async function saveTrackCoreSubjects() {
  const programId = curriculumProgramId.value;
  const checked = Array.from(document.querySelectorAll('input[name="trackCoreSubjectIds"]:checked')).map(el => parseInt(el.value));

  try {
    const res = await fetch(`${API_BASE}/programs/${programId}/core-subjects`, {
      method: 'POST',
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ subject_ids: checked })
    });

    if (!res.ok) throw new Error('Failed to save track core subjects');
    alert('✔ Core subjects saved for this program track!');
    loadCurriculumData(programId);
  } catch (err) {
    alert(`❌ ${err.message}`);
  }
}
window.saveTrackCoreSubjects = saveTrackCoreSubjects;

function renderPackagesList(packages) {
  const container = document.getElementById('packagesListContainer');
  if (!packages || packages.length === 0) {
    container.innerHTML = '<p style="opacity:.6; font-size:0.85rem;">No elective packages configured yet. Click <strong>+ Add New Package</strong> to create Option A, Option B, etc.</p>';
    return;
  }

  container.innerHTML = packages.map(pkg => `
    <div class="package-card">
      <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:8px;">
        <div>
          <div style="display:flex; align-items:center; gap:8px;">
            <strong style="color:#f8fafc; font-size:0.95rem;">${pkg.name}</strong>
            ${pkg.code ? `<span style="font-size:0.72rem; background:rgba(234,179,8,0.15); color:#facc15; padding:2px 6px; border-radius:4px; font-family:monospace;">${pkg.code}</span>` : ''}
          </div>
          <div style="font-size:0.8rem; color:#94a3b8; margin-top:3px;">
            Target Stream: <strong style="color:#60a5fa;">${pkg.class_section_name || 'Unassigned'}</strong> | Quota: <strong>${pkg.capacity || 'Unlimited'}</strong>
          </div>
        </div>
        <div style="display:flex; gap:6px;">
          <button type="button" class="btn danger" style="padding:3px 8px; font-size:0.75rem;" onclick="deleteElectivePackage(${pkg.id})">Delete</button>
        </div>
      </div>
      <div>
        <span style="font-size:0.75rem; color:#94a3b8; margin-right:4px;">Subjects (${pkg.subjects.length}):</span>
        ${pkg.subjects.map(s => `<span class="subject-pill">${s.name}</span>`).join('')}
      </div>
    </div>
  `).join('');
}

function toggleAddPackageForm(show) {
  const formContainer = document.getElementById('addPackageFormContainer');
  if (formContainer) {
    formContainer.style.display = show ? 'block' : 'none';
  }
}
window.toggleAddPackageForm = toggleAddPackageForm;

async function handleCreatePackage(event) {
  event.preventDefault();
  const programId = curriculumProgramId.value;
  const name = document.getElementById('pkg_name').value.trim();
  const code = document.getElementById('pkg_code').value.trim();
  const class_section_id = document.getElementById('pkg_class_section_id').value ? parseInt(document.getElementById('pkg_class_section_id').value) : null;
  const capacity = parseInt(document.getElementById('pkg_capacity').value) || 50;
  const checkedSubjects = Array.from(document.querySelectorAll('input[name="pkgSubjectIds"]:checked')).map(el => parseInt(el.value));

  if (checkedSubjects.length === 0) {
    alert('Please select at least 1 elective subject for this package.');
    return;
  }

  const payload = {
    name,
    code: code || null,
    class_section_id,
    capacity,
    is_active: true,
    subject_ids: checkedSubjects
  };

  try {
    const res = await fetch(`${API_BASE}/programs/${programId}/elective-combinations`, {
      method: 'POST',
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload)
    });

    if (!res.ok) throw new Error('Failed to create elective package');

    document.getElementById('newPackageForm').reset();
    toggleAddPackageForm(false);
    loadCurriculumData(programId);
  } catch (err) {
    alert(`❌ ${err.message}`);
  }
}
window.handleCreatePackage = handleCreatePackage;

async function deleteElectivePackage(packageId) {
  if (!confirm('Are you sure you want to delete this elective package?')) return;
  try {
    const res = await fetch(`${API_BASE}/programs/elective-combinations/${packageId}`, {
      method: 'DELETE',
      headers: getHeaders()
    });
    if (!res.ok) throw new Error('Failed to delete package');
    loadCurriculumData(curriculumProgramId.value);
  } catch (err) {
    alert(`❌ ${err.message}`);
  }
}
window.deleteElectivePackage = deleteElectivePackage;
