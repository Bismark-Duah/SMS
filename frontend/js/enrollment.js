/* ================================================================
   enrollment.js — Candidate Voucher Authentication & Admissions Engine
   ================================================================ */

const API_BASE = window.API_BASE || (window.location.origin.includes('http') ? (window.location.origin + '/api') : 'http://127.0.0.1:8000/api');

let currentVerifiedStudent = null;

document.addEventListener('DOMContentLoaded', () => {
  // Check if student_id parameter passed in URL
  const urlParams = new URLSearchParams(window.location.search);
  const studentId = urlParams.get('student_id');
  if (studentId) {
    loadProspectusPackage(studentId);
  }
});


// ── 1. Handle Candidate Voucher Login ─────────────────────────────────────────

async function handleVoucherLogin(event) {
  event.preventDefault();
  const statusEl = document.getElementById('voucher-login-status');
  statusEl.style.color = '#38bdf8';
  statusEl.textContent = 'Verifying Voucher & CSSPS Placement...';

  const bece_index_number = document.getElementById('gate_bece_index').value.trim();
  const serial_code = document.getElementById('gate_serial').value.trim();
  const pin_code = document.getElementById('gate_pin').value.trim();

  try {
    const res = await fetch(`${API_BASE}/vouchers/verify`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ bece_index_number, serial_code, pin_code })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Verification failed');

    currentVerifiedStudent = data;

    statusEl.style.color = '#4ade80';
    statusEl.textContent = '✔ Verified! Unlocking Admission Form...';

    // Show Step 2 Form
    document.getElementById('step-gateway').style.display = 'none';
    document.getElementById('step-form').style.display = 'block';

    document.getElementById('cand-name-display').textContent = data.full_name;
    document.getElementById('cand-bece-display').textContent = data.bece_index_number;
    document.getElementById('cand-status-badge').textContent = `STATUS: ${data.enrollment_status}`;

    // Pre-populate program electives if available
    updateElectiveComboOptions(data.program_name);

  } catch (err) {
    statusEl.style.color = '#f87171';
    statusEl.textContent = `❌ ${err.message}`;
  }
}


function updateElectiveComboOptions(programName) {
  const comboSelect = document.getElementById('adm_elective_combo');
  if (!comboSelect) return;

  const prog = (programName || '').toLowerCase();

  if (prog.includes('home') || prog.includes('econ')) {
    comboSelect.innerHTML = `
      <option value="">-- Choose Home Economics Elective Combination --</option>
      <option value="Option A (Mgmt in Living + Food & Nut + Clothing & Textiles + GKA)">Option A: Mgmt in Living + Food & Nut + Clothing & Textiles + GKA → (Form 1 Home Econ 1)</option>
      <option value="Option B (Mgmt in Living + Food & Nut + Biology + Economics)">Option B: Mgmt in Living + Food & Nut + Biology + Economics → (Form 1 Home Econ 2)</option>
      <option value="Option C (Mgmt in Living + Clothing & Textiles + Economics + French)">Option C: Mgmt in Living + Clothing & Textiles + Economics + French → (Form 1 Home Econ 3)</option>
      <option value="Option D (Mgmt in Living + Food & Nut + GKA + French)">Option D: Mgmt in Living + Food & Nut + GKA + French → (Form 1 Home Econ 4)</option>
    `;
  } else if (prog.includes('sci') || prog.includes('stem')) {
    comboSelect.innerHTML = `
      <option value="">-- Choose General Science / STEM Elective Combination --</option>
      <option value="Option A (Physics + Chemistry + Elective Maths + Biology)">Option A: Physics + Chemistry + Elective Maths + Biology → (Form 1 Science 1)</option>
      <option value="Option B (Physics + Chemistry + Elective Maths + Geography)">Option B: Physics + Chemistry + Elective Maths + Geography → (Form 1 Science 2)</option>
      <option value="Option C (Physics + Chemistry + Elective Maths + Information Tech)">Option C: Physics + Chemistry + Elective Maths + Information Tech → (Form 1 Science 3)</option>
    `;
  } else if (prog.includes('art')) {
    comboSelect.innerHTML = `
      <option value="">-- Choose General Arts / Visual Arts Combination --</option>
      <option value="Option A (Literature + Economics + Geography + Elective Maths)">Option A: Literature + Economics + Geography + Elective Maths → (Form 1 Arts 1)</option>
      <option value="Option B (Government + History + Religious Studies + Twi)">Option B: Government + History + Religious Studies + Twi → (Form 1 Arts 2)</option>
      <option value="Option C (Graphic Design + Picture Making + Sculpture + GKA)">Option C: Graphic Design + Picture Making + Sculpture + GKA → (Form 1 Visual Arts 1)</option>
    `;
  } else if (prog.includes('bus')) {
    comboSelect.innerHTML = `
      <option value="">-- Choose Business Elective Combination --</option>
      <option value="Option A (Financial Accounting + Cost Accounting + Business Mgmt + Elective Maths)">Option A: Financial Accounting + Cost Accounting + Business Mgmt + Elective Maths → (Form 1 Business 1)</option>
      <option value="Option B (Financial Accounting + Business Mgmt + Economics + Typewriting)">Option B: Financial Accounting + Business Mgmt + Economics + Typewriting → (Form 1 Business 2)</option>
    `;
  }
}


// ── 2. Handle Admission Form Submission ───────────────────────────────────────

async function handleFormSubmission(event) {
  event.preventDefault();
  if (!currentVerifiedStudent) return;

  const statusEl = document.getElementById('form-submit-status');
  statusEl.style.color = '#38bdf8';
  statusEl.textContent = 'Submitting Admission Form & Routing Class/House...';

  const payload = {
    student_id: currentVerifiedStudent.student_id,
    serial_code: currentVerifiedStudent.serial_code,
    elective_combination: document.getElementById('adm_elective_combo').value,
    guardian_name: document.getElementById('adm_guardian_name').value.trim(),
    primary_phone: document.getElementById('adm_primary_phone').value.trim(),
    alternative_phone: document.getElementById('adm_alt_phone').value.trim(),
    residential_address: document.getElementById('adm_address').value.trim(),
    blood_group: document.getElementById('adm_blood_group').value,
    allergies: document.getElementById('adm_allergies').value.trim(),
    medical_conditions: document.getElementById('adm_conditions').value.trim(),
  };

  try {
    const res = await fetch(`${API_BASE}/cssps/complete-form`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Form submission failed');

    statusEl.style.color = '#4ade80';
    statusEl.textContent = '✔ Submitted! Generating Prospectus Package...';

    // Load Prospectus Package Step 3
    loadProspectusPackage(currentVerifiedStudent.student_id);

  } catch (err) {
    statusEl.style.color = '#f87171';
    statusEl.textContent = `❌ ${err.message}`;
  }
}


// ── 3. Load Dynamic GES Prospectus & Admission Letter Package ────────────────

async function loadProspectusPackage(studentId) {
  try {
    const res = await fetch(`${API_BASE}/cssps/prospectus-package/${studentId}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Failed to load prospectus');

    const s = data.student_info;
    const p = data.prospectus;

    document.getElementById('step-gateway').style.display = 'none';
    document.getElementById('step-form').style.display = 'none';
    document.getElementById('step-package').style.display = 'block';

    // Populate Printable Letterhead
    document.getElementById('letter-school-name').textContent = s.school_name || 'GHANA SENIOR HIGH SCHOOL';
    document.getElementById('letter-school-body').textContent = s.school_name || 'this institution';
    document.getElementById('letter-student-name').textContent = s.full_name;
    document.getElementById('letter-bece-index').textContent = s.bece_index_number;
    document.getElementById('letter-student-code').textContent = s.student_code;
    document.getElementById('letter-program').textContent = s.program_name;
    document.getElementById('letter-class').textContent = s.class_name;
    document.getElementById('letter-house').textContent = `${s.house_name} (${s.dormitory_name})`;
    document.getElementById('letter-residential').textContent = s.residential_status;
    document.getElementById('letter-year').textContent = s.academic_year;
    document.getElementById('letter-year-body').textContent = s.academic_year;
    document.getElementById('letter-qr-code').textContent = s.qr_verification_code;

    // Populate Prospectus Checklists
    renderList('prospectus-academic', p.academic_supplies);
    renderList('prospectus-boarding', p.boarding_supplies);
    renderList('prospectus-gender', p.clothing_and_grooming);
    renderList('prospectus-program', p.program_practical_tools);

    // Populate Code of Conduct & Honor Declaration
    const c = data.code_of_conduct || {};
    const rulesEl = document.getElementById('prospectus-conduct-rules');
    const pledgeEl = document.getElementById('prospectus-honor-pledge');
    if (rulesEl) rulesEl.textContent = c.rules_text || 'All students must comply with school attendance, dress code, and examination ethics regulations.';
    if (pledgeEl) pledgeEl.textContent = c.honor_pledge || 'I solemnly pledge to abide by the School Code of Conduct.';

    // Hide boarding section if Day Student
    if (s.residential_status.toLowerCase() === 'day') {
      const bSec = document.getElementById('section-boarding');
      if (bSec) bSec.style.display = 'none';
    }

  } catch (err) {
    alert(`Prospectus Error: ${err.message}`);
  }
}

function renderList(elementId, items) {
  const el = document.getElementById(elementId);
  if (!el) return;
  if (!items || items.length === 0) {
    el.innerHTML = '<li><em>No special items required.</em></li>';
    return;
  }
  el.innerHTML = items.map(item => `<li>✔ ${item}</li>`).join('');
}


// ── 4. Batch Generate Vouchers Helper (Admin Tool) ───────────────────────────

async function handleGenerateBatchVouchers() {
  const token = localStorage.getItem('accessToken');
  if (!token) {
    alert('Admin authentication required to generate vouchers. Please login as Admin or Academic Head.');
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/vouchers/generate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + token
      },
      body: JSON.stringify({ count: 50, prefix: 'JAK-2026' })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Batch generation failed');

    alert(`✔ Success: ${data.message}\nSample Voucher: Serial=${data.vouchers[0].serial_code}, PIN=${data.vouchers[0].pin_code}`);
  } catch (err) {
    alert(`Batch Generation Error: ${err.message}`);
  }
}
