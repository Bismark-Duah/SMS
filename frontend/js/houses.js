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

async function triggerAutoAllocation() {
  if (!confirm('Are you sure you want to auto-allocate all unassigned students into Houses and Boarding Dormitories?')) {
    return;
  }
  try {
    const res = await fetch(`${API_BASE}/houses/auto-allocate`, {
      method: 'POST',
      headers: getHeaders()
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Allocation failed');
    }
    const data = await res.json();
    alert(data.message || 'Auto-allocation completed successfully!');
    if (typeof loadHouses === 'function') loadHouses();
  } catch (e) {
    alert(`Error: ${e.message}`);
  }
}

const houseForm = document.getElementById('houseForm');
const housesList = document.getElementById('housesList');
const seniorSelect = document.getElementById('houseSenior');
const houseMasterSelect = document.getElementById('houseMaster');
const houseAssistantSelect = document.getElementById('houseAssistant');
const houseSeniorGirlsSelect = document.getElementById('houseSeniorGirls');
const houseMasterGirlsSelect = document.getElementById('houseMasterGirls');
const houseAssistantGirlsSelect = document.getElementById('houseAssistantGirls');
const houseGenderSelect = document.getElementById('houseGender');
const cancelHouseBtn = document.getElementById('cancelHouseBtn');
const houseMsg = document.getElementById('houseMsg');

// Boys/Girls supervisor form containers
const boysContainer = document.getElementById('boysSupervisorsContainer');
const girlsContainer = document.getElementById('girlsSupervisorsContainer');

function updateSupervisorFieldsVisibility() {
  const val = houseGenderSelect.value;
  if (val === 'Boys') {
    boysContainer.style.display = 'block';
    girlsContainer.style.display = 'none';
  } else if (val === 'Girls') {
    boysContainer.style.display = 'none';
    girlsContainer.style.display = 'block';
  } else if (val === 'Both') {
    boysContainer.style.display = 'block';
    girlsContainer.style.display = 'block';
  }
}

houseGenderSelect.addEventListener('change', updateSupervisorFieldsVisibility);

// Dormitory modal elements
const dormsModal = document.getElementById('dormsModal');
const modalHouseName = document.getElementById('modalHouseName');
const modalDormsList = document.getElementById('modalDormsList');
const dormForm = document.getElementById('dormForm');
const cancelDormBtn = document.getElementById('cancelDormBtn');
const closeDormsModalBtn = document.getElementById('closeDormsModalBtn');
const dormMsg = document.getElementById('dormMsg');

let allTeachers = [];
let allHouses = [];

async function initPage() {
  try {
    // Fetch all users (teachers / staff)
    const userRes = await fetch(`${API_BASE}/auth/users`, { headers: getHeaders() });
    if (userRes.ok) {
      const users = await userRes.json();
      // Filter users who can act as supervisor (all staff members)
      allTeachers = users.filter(u => u.roles && u.roles.some(r => 
        !['student', 'parent'].includes(r.name.toLowerCase())
      ));
    }

    renderSupervisorsDropdowns();
    updateSupervisorFieldsVisibility();
    await loadHouses();
  } catch (error) {
    console.error('Error initializing page:', error);
  }
}

// Renders lists for House Supervisors
function renderSupervisorsDropdowns() {
  const optionsHtml = allTeachers.map(t => `<option value="${t.id}">${t.username} (${t.gender || 'Unknown gender'})</option>`).join('');
  
  seniorSelect.innerHTML = '<option value="">Select Senior in charge...</option>' + optionsHtml;
  if (houseMasterSelect) houseMasterSelect.innerHTML = '<option value="">Select House Master...</option>' + optionsHtml;
  if (houseAssistantSelect) houseAssistantSelect.innerHTML = '<option value="">Select Assistant...</option>' + optionsHtml;

  if (houseSeniorGirlsSelect) houseSeniorGirlsSelect.innerHTML = '<option value="">Select Senior in charge...</option>' + optionsHtml;
  if (houseMasterGirlsSelect) houseMasterGirlsSelect.innerHTML = '<option value="">Select House Mistress...</option>' + optionsHtml;
  if (houseAssistantGirlsSelect) houseAssistantGirlsSelect.innerHTML = '<option value="">Select Assistant...</option>' + optionsHtml;
}

// Loads boarding houses
async function loadHouses() {
  try {
    const res = await fetch(`${API_BASE}/houses/`, { headers: getHeaders() });
    if (!res.ok) throw new Error('Failed to load houses');
    allHouses = await res.json();

    renderHousesList();
    renderReportingStructure();
  } catch (error) {
    console.error(error);
    housesList.innerHTML = '<p style="color:var(--danger); text-align:center;">Failed to load boarding houses.</p>';
  }
}

function renderHousesList() {
  if (allHouses.length === 0) {
    housesList.innerHTML = '<p style="opacity:.6; text-align:center; padding:20px;">No boarding houses created yet.</p>';
    return;
  }

  housesList.innerHTML = allHouses.map(house => {
    let supervisorInfo = '';
    
    if (house.gender === 'Both') {
      const boysSenior = house.senior_in_charge_name ? `<strong>${house.senior_in_charge_name}</strong>` : '<span style="opacity:.5;">None</span>';
      const boysMaster = house.house_master_name ? `<strong>${house.house_master_name}</strong>` : '<span style="opacity:.5;">None</span>';
      const boysAssistant = house.assistant_house_master_name ? `<strong>${house.assistant_house_master_name}</strong>` : '<span style="opacity:.5;">None</span>';

      const girlsSenior = house.senior_in_charge_girls_name ? `<strong>${house.senior_in_charge_girls_name}</strong>` : '<span style="opacity:.5;">None</span>';
      const girlsMaster = house.house_master_girls_name ? `<strong>${house.house_master_girls_name}</strong>` : '<span style="opacity:.5;">None</span>';
      const girlsAssistant = house.assistant_house_master_girls_name ? `<strong>${house.assistant_house_master_girls_name}</strong>` : '<span style="opacity:.5;">None</span>';

      supervisorInfo = `
        <div style="display:grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top:8px; font-size:0.82rem; opacity:.9; line-height:1.4; background: rgba(255,255,255,0.02); padding: 8px; border-radius: var(--radius-md); border: 1px solid rgba(255,255,255,0.05);">
          <div>
            <span style="color:#818cf8; font-weight:600; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.5px;">🚹 Boys' Wing:</span><br>
            Senior: ${boysSenior}<br>
            Master: ${boysMaster}<br>
            Asst: ${boysAssistant}
          </div>
          <div>
            <span style="color:#f472b6; font-weight:600; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.5px;">🚺 Girls' Wing:</span><br>
            Senior: ${girlsSenior}<br>
            Mistress: ${girlsMaster}<br>
            Asst: ${girlsAssistant}
          </div>
        </div>
      `;
    } else {
      const seniorLabel = house.senior_in_charge_name 
        ? `<strong>${house.senior_in_charge_name}</strong>` 
        : '<span style="opacity:.5;">None Assigned</span>';
      const houseMasterLabel = house.house_master_name 
        ? `<strong>${house.house_master_name}</strong>` 
        : '<span style="opacity:.5;">None Assigned</span>';
      const assistantLabel = house.assistant_house_master_name 
        ? `<strong>${house.assistant_house_master_name}</strong>` 
        : '<span style="opacity:.5;">None Assigned</span>';
      
      const roleLabel = house.gender === 'Girls' ? 'Mistress' : 'Master';

      supervisorInfo = `
        <p style="margin:4px 0 0 0; font-size:0.85rem; opacity:.75; line-height:1.4;">
          Senior supervisor: ${seniorLabel}<br>
          House ${roleLabel}: ${houseMasterLabel} | Assistant: ${assistantLabel}
        </p>
      `;
    }

    const dormsLabel = house.dormitories.length > 0 
      ? house.dormitories.map(d => d.name).join(', ') 
      : '<span style="opacity:.5; font-style:italic;">No dormitories created</span>';

    // Style badge color based on gender
    let badgeBg = 'rgba(16,185,129,0.15)';
    let badgeColor = '#10b981';
    if (house.gender === 'Boys') {
      badgeBg = 'rgba(99,102,241,0.15)';
      badgeColor = '#818cf8';
    } else if (house.gender === 'Girls') {
      badgeBg = 'rgba(244,114,182,0.15)';
      badgeColor = '#f472b6';
    }

    const totalHouseCap = house.dormitories.reduce((acc, d) => acc + (d.capacity || 30), 0);

    return `
      <div style="border-bottom: 1px solid var(--border-color); padding: 16px 0; display:flex; flex-direction:column; gap:8px;">
        <div style="display:flex; justify-content:space-between; align-items:flex-start;">
          <div style="flex: 1;">
            <h4 style="margin:0; font-size:1.05rem; color:#fff;">
              ${house.name} 
              <span style="font-size:0.72rem; padding:2px 8px; border-radius:10px; margin-left:6px; font-weight:600; 
                background:${badgeBg}; color:${badgeColor};">
                ${house.gender}
              </span>
            </h4>
            ${supervisorInfo}
            <div style="margin-top: 6px; font-size:0.85rem; opacity:.85;">
              Enrolled Boarders: <strong>${house.boarder_count !== undefined ? house.boarder_count : house.student_count}</strong> | Day Members: <strong>${house.day_count || 0}</strong> | Total Bed Capacity: <strong>${totalHouseCap} Beds</strong>
            </div>
          </div>
          <div style="display:flex; gap:6px;">
            <button class="btn" style="padding:4px 8px; font-size:0.8rem; border-color:var(--secondary); color:#22d3ee;" onclick="openDormsModal(${house.id}, '${house.name.replace(/'/g, "\\'")}', '${house.gender}')">🏫 Dorms</button>
            <button class="btn" style="padding:4px 8px; font-size:0.8rem;" onclick="editHouse(${house.id}, '${house.name.replace(/'/g, "\\'")}', '${house.gender}', ${house.senior_in_charge_id || 'null'}, ${house.house_master_id || 'null'}, ${house.assistant_house_master_id || 'null'}, ${house.senior_in_charge_girls_id || 'null'}, ${house.house_master_girls_id || 'null'}, ${house.assistant_house_master_girls_id || 'null'})">Edit</button>
            <button class="btn danger" style="padding:4px 8px; font-size:0.8rem;" onclick="deleteHouse(${house.id})">Delete</button>
          </div>
        </div>
        <div style="font-size:0.82rem; opacity:.8; margin-top: 4px;">
          <strong style="color:var(--text-secondary);">Dormitories:</strong> ${dormsLabel}
        </div>
      </div>
    `;
  }).join('');
}

// Renders the Reporting Structure Widget dynamically
function renderReportingStructure() {
  // Boys Residential Wing
  const seniorsBoys = [];
  const boysStaff = [];

  // Girls Residential Wing
  const seniorsGirls = [];
  const girlsStaff = [];

  allHouses.forEach(h => {
    if (h.gender === 'Boys') {
      if (h.senior_in_charge_name) seniorsBoys.push(h.senior_in_charge_name);
      if (h.house_master_name) boysStaff.push(`<strong>${h.house_master_name}</strong> (${h.name} Master)`);
      if (h.assistant_house_master_name) boysStaff.push(`<strong>${h.assistant_house_master_name}</strong> (${h.name} Assistant)`);
    } else if (h.gender === 'Girls') {
      if (h.senior_in_charge_name) seniorsGirls.push(h.senior_in_charge_name);
      if (h.house_master_name) girlsStaff.push(`<strong>${h.house_master_name}</strong> (${h.name} Mistress)`);
      if (h.assistant_house_master_name) girlsStaff.push(`<strong>${h.assistant_house_master_name}</strong> (${h.name} Assistant)`);
    } else if (h.gender === 'Both') {
      if (h.senior_in_charge_name) seniorsBoys.push(h.senior_in_charge_name);
      if (h.house_master_name) boysStaff.push(`<strong>${h.house_master_name}</strong> (${h.name} Master)`);
      if (h.assistant_house_master_name) boysStaff.push(`<strong>${h.assistant_house_master_name}</strong> (${h.name} Assistant)`);

      if (h.senior_in_charge_girls_name) seniorsGirls.push(h.senior_in_charge_girls_name);
      if (h.house_master_girls_name) girlsStaff.push(`<strong>${h.house_master_girls_name}</strong> (${h.name} Mistress)`);
      if (h.assistant_house_master_girls_name) girlsStaff.push(`<strong>${h.assistant_house_master_girls_name}</strong> (${h.name} Assistant)`);
    }
  });

  const uniqueSeniorsBoys = [...new Set(seniorsBoys)];
  document.getElementById('reportSeniorHousemaster').innerHTML = uniqueSeniorsBoys.length > 0 
    ? uniqueSeniorsBoys.join(', ') 
    : '<span style="opacity:.5; font-style:italic;">No Senior Housemaster assigned</span>';

  const maleListEl = document.getElementById('reportHousemastersList');
  if (boysStaff.length > 0) {
    maleListEl.innerHTML = boysStaff.map(staff => `
      <li style="margin-bottom:4px;">
        ${staff} reports to ${uniqueSeniorsBoys.length > 0 ? uniqueSeniorsBoys.join('/') : 'Senior Housemaster'}
      </li>
    `).join('');
  } else {
    maleListEl.innerHTML = '<li style="opacity:0.5;">No active housemasters/assistants in boys houses.</li>';
  }

  const uniqueSeniorsGirls = [...new Set(seniorsGirls)];
  document.getElementById('reportSeniorHousemistress').innerHTML = uniqueSeniorsGirls.length > 0 
    ? uniqueSeniorsGirls.join(', ') 
    : '<span style="opacity:.5; font-style:italic;">No Senior Housemistress assigned</span>';

  const femaleListEl = document.getElementById('reportHousemistressesList');
  if (girlsStaff.length > 0) {
    femaleListEl.innerHTML = girlsStaff.map(staff => `
      <li style="margin-bottom:4px;">
        ${staff} reports to ${uniqueSeniorsGirls.length > 0 ? uniqueSeniorsGirls.join('/') : 'Senior Housemistress'}
      </li>
    `).join('');
  } else {
    femaleListEl.innerHTML = '<li style="opacity:0.5;">No active housemistresses/assistants in girls houses.</li>';
  }
}

// Edit House handler
function editHouse(id, name, gender, seniorId, masterId, assistantId, seniorGirlsId, masterGirlsId, assistantGirlsId) {
  document.getElementById('houseId').value = id;
  document.getElementById('houseName').value = name;
  houseGenderSelect.value = gender;
  updateSupervisorFieldsVisibility();
  
  // Set Boys/Default values
  seniorSelect.value = seniorId || '';
  houseMasterSelect.value = masterId || '';
  houseAssistantSelect.value = assistantId || '';

  // Set Girls values
  houseSeniorGirlsSelect.value = seniorGirlsId || '';
  houseMasterGirlsSelect.value = masterGirlsId || '';
  houseAssistantGirlsSelect.value = assistantGirlsId || '';

  houseMsg.innerHTML = '<div style="color:var(--warning); font-size:0.85rem;">Editing house... Submit form to save.</div>';
}

// Delete House handler
async function deleteHouse(id) {
  if (!confirm('Are you sure you want to delete this house? This will clear assignments for all dormitories and students inside it.')) return;
  try {
    const res = await fetch(`${API_BASE}/houses/${id}`, {
      method: 'DELETE',
      headers: getHeaders()
    });
    if (res.ok) {
      loadHouses();
      houseForm.reset();
      document.getElementById('houseId').value = '';
      updateSupervisorFieldsVisibility();
    } else {
      const err = await res.json();
      alert(`Error: ${err.detail}`);
    }
  } catch (error) {
    alert('Failed to connect to backend.');
  }
}

// House Form submission
houseForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const id = document.getElementById('houseId').value;
  const gender = houseGenderSelect.value;
  
  const payload = {
    name: document.getElementById('houseName').value.trim(),
    gender: gender,
    senior_in_charge_id: (gender === 'Boys' || gender === 'Both') && seniorSelect.value ? parseInt(seniorSelect.value) : null,
    house_master_id: (gender === 'Boys' || gender === 'Both') && houseMasterSelect.value ? parseInt(houseMasterSelect.value) : null,
    assistant_house_master_id: (gender === 'Boys' || gender === 'Both') && houseAssistantSelect.value ? parseInt(houseAssistantSelect.value) : null,
    
    senior_in_charge_girls_id: (gender === 'Girls' || gender === 'Both') && houseSeniorGirlsSelect.value ? parseInt(houseSeniorGirlsSelect.value) : null,
    house_master_girls_id: (gender === 'Girls' || gender === 'Both') && houseMasterGirlsSelect.value ? parseInt(houseMasterGirlsSelect.value) : null,
    assistant_house_master_girls_id: (gender === 'Girls' || gender === 'Both') && houseAssistantGirlsSelect.value ? parseInt(houseAssistantGirlsSelect.value) : null
  };

  try {
    const url = id ? `${API_BASE}/houses/${id}` : `${API_BASE}/houses/`;
    const method = id ? 'PUT' : 'POST';

    const res = await fetch(url, {
      method: method,
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Could not save house');
    }

    houseForm.reset();
    document.getElementById('houseId').value = '';
    updateSupervisorFieldsVisibility();
    houseMsg.innerHTML = '<div style="color:var(--success); font-size:0.85rem;">House saved successfully!</div>';
    setTimeout(() => { houseMsg.innerHTML = ''; }, 3000);
    loadHouses();
  } catch (error) {
    houseMsg.innerHTML = `<div style="color:var(--danger); font-size:0.85rem;">Error: ${error.message}</div>`;
  }
});

cancelHouseBtn.addEventListener('click', () => {
  houseForm.reset();
  document.getElementById('houseId').value = '';
  updateSupervisorFieldsVisibility();
  houseMsg.innerHTML = '';
});

// --- Dormitory Modal Handling ---

let activeHouseGender = 'Boys';

function openDormsModal(houseId, houseName, gender) {
  document.getElementById('dormHouseId').value = houseId;
  document.getElementById('dormId').value = '';
  dormForm.reset();
  activeHouseGender = gender;
  modalHouseName.textContent = `House: ${houseName} (${gender})`;
  dormMsg.innerHTML = '';

  dormsModal.style.display = 'flex';
  loadDormitoriesList(houseId);
}

function loadDormitoriesList(houseId) {
  const house = allHouses.find(h => h.id === houseId);
  if (!house || house.dormitories.length === 0) {
    modalDormsList.innerHTML = '<p style="opacity:.6; font-size:.85rem; text-align:center; padding:10px;">No dormitories in this house yet.</p>';
    return;
  }

  modalDormsList.innerHTML = house.dormitories.map(d => {
    const cap = d.capacity || 30;
    const occ = d.occupied_count || 0;
    const pct = Math.min(100, Math.round((occ / cap) * 100));
    
    let statusColor = '#10b981'; // Green
    let statusBg = 'rgba(16,185,129,0.2)';
    if (pct >= 100) {
      statusColor = '#ef4444'; // Red (Full)
      statusBg = 'rgba(239,68,68,0.2)';
    } else if (pct >= 80) {
      statusColor = '#f59e0b'; // Amber (Nearly Full)
      statusBg = 'rgba(245,158,11,0.2)';
    }

    return `
    <div style="display:flex; flex-direction:column; gap:6px; background:rgba(255,255,255,0.03); padding:10px 14px; border-radius:8px; border:1px solid rgba(255,255,255,0.08);">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <div>
          <strong style="color:#fff; font-size:0.92rem;">${d.name}</strong>
          <span style="font-size:0.75rem; padding:2px 8px; border-radius:10px; margin-left:8px; font-weight:600; background:${statusBg}; color:${statusColor};">
            ${occ} / ${cap} Beds (${pct}%) ${pct >= 100 ? '🔒 FULL' : ''}
          </span>
        </div>
        <div style="display:flex; gap:6px;">
          <button type="button" class="btn sm" style="padding:2px 8px; font-size:0.75rem;" onclick="editDormitory(${d.id}, '${d.name.replace(/'/g, "\\'")}', ${cap})">Edit</button>
          <button type="button" class="btn danger sm" style="padding:2px 8px; font-size:0.75rem;" onclick="deleteDormitory(${d.id})">Delete</button>
        </div>
      </div>
      <div style="width:100%; background:rgba(255,255,255,0.1); height:6px; border-radius:3px; overflow:hidden;">
        <div style="width:${pct}%; background:${statusColor}; height:100%; transition:width 0.3s ease;"></div>
      </div>
    </div>
  `;
  }).join('');
}

function editDormitory(id, name, capacity) {
  document.getElementById('dormId').value = id;
  document.getElementById('dormName').value = name;
  document.getElementById('dormCapacity').value = capacity || 30;
  dormMsg.innerHTML = '<div style="color:var(--warning); font-size:0.85rem;">Editing dormitory... Submit form to update.</div>';
}

async function deleteDormitory(dormId) {
  if (!confirm('Are you sure you want to delete this dormitory? Students in this dormitory will be unassigned.')) return;
  const houseId = parseInt(document.getElementById('dormHouseId').value);
  try {
    const res = await fetch(`${API_BASE}/houses/dormitories/${dormId}`, {
      method: 'DELETE',
      headers: getHeaders()
    });
    if (res.ok) {
      dormForm.reset();
      document.getElementById('dormId').value = '';
      document.getElementById('dormCapacity').value = '30';
      dormMsg.innerHTML = '<div style="color:var(--success); font-size:0.85rem;">Dormitory deleted.</div>';
      await loadHouses();
      loadDormitoriesList(houseId);
    } else {
      const err = await res.json();
      alert(`Error: ${err.detail}`);
    }
  } catch (error) {
    alert('Failed to connect to backend.');
  }
}

dormForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const houseId = parseInt(document.getElementById('dormHouseId').value);
  const dormId = document.getElementById('dormId').value;
  const capVal = document.getElementById('dormCapacity').value;

  const payload = {
    name: document.getElementById('dormName').value.trim(),
    capacity: capVal ? parseInt(capVal) : 30,
    house_id: houseId
  };

  try {
    const url = dormId ? `${API_BASE}/houses/dormitories/${dormId}` : `${API_BASE}/houses/${houseId}/dormitories`;
    const method = dormId ? 'PUT' : 'POST';

    const res = await fetch(url, {
      method: method,
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Could not save dormitory');
    }

    dormForm.reset();
    document.getElementById('dormId').value = '';
    document.getElementById('dormCapacity').value = '30';
    dormMsg.innerHTML = '<div style="color:var(--success); font-size:0.85rem;">Dormitory saved successfully!</div>';
    await loadHouses();
    loadDormitoriesList(houseId);
  } catch (error) {
    dormMsg.innerHTML = `<div style="color:var(--danger); font-size:0.85rem;">Error: ${error.message}</div>`;
  }
});

cancelDormBtn.addEventListener('click', () => {
  dormForm.reset();
  document.getElementById('dormId').value = '';
  document.getElementById('dormCapacity').value = '30';
  dormMsg.innerHTML = '';
});

closeDormsModalBtn.addEventListener('click', () => {
  dormsModal.style.display = 'none';
});

// Bind to window
window.editHouse = editHouse;
window.deleteHouse = deleteHouse;
window.openDormsModal = openDormsModal;
window.editDormitory = editDormitory;
window.deleteDormitory = deleteDormitory;

initPage();
