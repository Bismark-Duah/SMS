/* ================================================================
   enrollment.js — Candidate Public Voucher Authentication & Admissions Engine
   ================================================================ */

const API_BASE = window.API_BASE || (window.location.origin.includes('http') ? (window.location.origin + '/api') : 'http://127.0.0.1:8000/api');

let currentVerifiedStudent = null;
let currentLoadedStudentId = null;
let currentActiveSchoolId = null;
let currentPlacementRecord = null;
let currentVoucherPrice = 0.10;
let currentRecipientNumber = "0508929456";
let currentRecipientName = "Duah Bismark";

document.addEventListener('DOMContentLoaded', () => {
  initPortal();
});

async function initPortal() {
  await loadPublicSchoolBranding();

  // Check if student_id parameter passed in URL
  const urlParams = new URLSearchParams(window.location.search);
  const studentId = urlParams.get('student_id');
  if (studentId) {
    loadProspectusPackage(studentId);
  }
}

// ── 0. Public School Branding & Pricing Loader ─────────────────────────────────
async function loadPublicSchoolBranding() {
  const schoolNameEl = document.getElementById('portalSchoolName');
  const logoContainer = document.getElementById('portalLogoContainer');

  const urlParams = new URLSearchParams(window.location.search);
  const urlSchoolId = urlParams.get('school_id');
  const localSchoolId = localStorage.getItem('school_id');

  currentActiveSchoolId = urlSchoolId || localSchoolId;

  let name = localStorage.getItem('school_name') || 'J.A. KUFFOUR STEM TECHNICAL SCHOOL';
  let logo = localStorage.getItem('school_logo');

  try {
    const headers = {};
    if (currentActiveSchoolId) headers['X-School-Id'] = String(currentActiveSchoolId);

    const queryParams = new URLSearchParams({ mode: 'SHS_ONLY' });
    if (currentActiveSchoolId) queryParams.set('school_id', currentActiveSchoolId);

    const res = await fetch(`${API_BASE}/settings/public-branding?${queryParams.toString()}`, { headers });
    if (res.ok) {
      const data = await res.json();
      if (data.school_id) currentActiveSchoolId = data.school_id;
      if (data.school_name) name = data.school_name;
      if (data.school_logo) logo = data.school_logo;
      if (typeof data.voucher_price === 'number') currentVoucherPrice = data.voucher_price;
      if (data.momo_recipient_number) currentRecipientNumber = data.momo_recipient_number;
      if (data.momo_recipient_name) currentRecipientName = data.momo_recipient_name;
    }
  } catch (_) {}

  if (schoolNameEl) schoolNameEl.textContent = name;
  if (logoContainer && logo) {
    logoContainer.innerHTML = `<img src="${logo}" alt="${name} Logo" style="width:100%; height:100%; object-fit:contain;" />`;
  }

  // Format voucher price text
  const priceFormatted = currentVoucherPrice < 1.0 
    ? `GHS ${currentVoucherPrice.toFixed(2)} (${Math.round(currentVoucherPrice * 100)} Pesewas)`
    : `GHS ${currentVoucherPrice.toFixed(2)}`;

  document.querySelectorAll('.voucher-price-display').forEach(el => {
    el.textContent = priceFormatted;
  });

  const modalPrice = document.getElementById('modalVoucherFeeDisplay');
  if (modalPrice) modalPrice.textContent = `GHS ${currentVoucherPrice.toFixed(2)}`;

  const modalRec = document.getElementById('modalRecipientDisplay');
  if (modalRec) modalRec.textContent = `Recipient: ${currentRecipientName} (${currentRecipientNumber})`;

  document.querySelectorAll('.active-school-name-text').forEach(el => {
    el.textContent = name;
  });
}


// ── Tab Switching ─────────────────────────────────────────────────────────────
function switchPortalTab(tab) {
  const tabNew = document.getElementById('tabContentNew');
  const tabRet = document.getElementById('tabContentRetrieve');
  const btnNew = document.getElementById('tabNewAdmBtn');
  const btnRet = document.getElementById('tabRetrieveBtn');

  if (tab === 'new') {
    if (tabNew) tabNew.style.display = 'block';
    if (tabRet) tabRet.style.display = 'none';
    if (btnNew) btnNew.className = 'tab-btn active';
    if (btnRet) btnRet.className = 'tab-btn';
  } else {
    if (tabNew) tabNew.style.display = 'none';
    if (tabRet) tabRet.style.display = 'block';
    if (btnNew) btnNew.className = 'tab-btn';
    if (btnRet) btnRet.className = 'tab-btn active';
  }
}
window.switchPortalTab = switchPortalTab;


// ── STEP 1: Handle Candidate Placement & Eligibility Check ────────────────────

async function handleCheckPlacement(event) {
  if (event) event.preventDefault();

  const indexInput = document.getElementById('check_bece_index');
  const yearSelect = document.getElementById('check_bece_year');
  const btn = document.getElementById('btnCheckPlacement');
  const spinner = document.getElementById('placement-check-spinner');
  const resultContainer = document.getElementById('placement-check-result');
  const verifiedCard = document.getElementById('placement-verified-card');
  const unverifiedCard = document.getElementById('placement-unverified-card');

  const rawIndex = (indexInput ? indexInput.value : '').trim();
  const rawYear = (yearSelect ? yearSelect.value : '').trim();

  if (!rawIndex) return;

  if (btn) btn.disabled = true;
  if (spinner) spinner.style.display = 'inline-block';
  if (resultContainer) resultContainer.style.display = 'block';
  if (verifiedCard) verifiedCard.style.display = 'none';
  if (unverifiedCard) unverifiedCard.style.display = 'none';

  try {
    const queryParams = new URLSearchParams({
      index_number: rawIndex,
      year: rawYear
    });
    if (currentActiveSchoolId) {
      queryParams.set('school_id', currentActiveSchoolId);
    }

    const res = await fetch(`${API_BASE}/cssps/check-placement?${queryParams.toString()}`);
    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.detail || 'Could not verify placement. Please check the index number.');
    }

    if (data.is_placed) {
      currentPlacementRecord = data;

      // Update school branding if specific
      if (data.school_name) {
        const nameEl = document.getElementById('portalSchoolName');
        if (nameEl) nameEl.textContent = data.school_name;
      }
      if (data.school_logo) {
        const logoEl = document.getElementById('portalLogoContainer');
        if (logoEl) logoEl.innerHTML = `<img src="${data.school_logo}" alt="${data.school_name || 'School'} Logo" style="width:100%; height:100%; object-fit:contain;" />`;
      }

      // Populate Verified Placement Card
      const nameEl = document.getElementById('pv-cand-name');
      const idxEl = document.getElementById('pv-cand-index');
      const progEl = document.getElementById('pv-cand-program');
      const resEl = document.getElementById('pv-cand-residential');

      if (nameEl) nameEl.textContent = data.full_name || 'Candidate';
      if (idxEl) idxEl.textContent = data.bece_index_number || rawIndex;
      if (progEl) progEl.textContent = data.program_name || 'Assigned Program';
      if (resEl) resEl.textContent = data.residential_status || 'Day / Boarding';

      if (verifiedCard) verifiedCard.style.display = 'block';
      if (unverifiedCard) unverifiedCard.style.display = 'none';

    } else {
      currentPlacementRecord = null;
      const notFoundIdxEl = document.getElementById('pnv-searched-index');
      if (notFoundIdxEl) notFoundIdxEl.textContent = data.searched_index || rawIndex;

      document.querySelectorAll('.active-school-name-text').forEach(el => {
        el.textContent = document.getElementById('portalSchoolName')?.textContent || 'this institution';
      });

      if (unverifiedCard) unverifiedCard.style.display = 'block';
      if (verifiedCard) verifiedCard.style.display = 'none';
    }

  } catch (err) {
    alert(`Placement Verification Notice: ${err.message}`);
  } finally {
    if (btn) btn.disabled = false;
    if (spinner) spinner.style.display = 'none';
  }
}
window.handleCheckPlacement = handleCheckPlacement;

function proceedToVoucherStep() {
  if (!currentPlacementRecord) return;

  const step1 = document.getElementById('step-placement-check');
  const step2 = document.getElementById('step-gateway');

  if (step1) step1.style.display = 'none';
  if (step2) step2.style.display = 'block';

  // Populate Gate Candidate Badge
  const nameEl = document.getElementById('gate-cand-name');
  const indexEl = document.getElementById('gate-cand-index');
  const gateBece = document.getElementById('gate_bece_index');

  if (nameEl) nameEl.textContent = currentPlacementRecord.full_name;
  if (indexEl) indexEl.textContent = currentPlacementRecord.bece_index_number;
  if (gateBece) {
    gateBece.value = currentPlacementRecord.bece_index_number;
  }

  // Pre-fill Buy Voucher modal index
  const buyIndex = document.getElementById('buy_bece_index');
  if (buyIndex) {
    buyIndex.value = currentPlacementRecord.bece_index_number;
  }

  // Pre-fill Serial if previously assigned
  const gateSerial = document.getElementById('gate_serial');
  const gatePin = document.getElementById('gate_pin');
  if (gateSerial && !gateSerial.value) {
    setTimeout(() => {
      if (gateSerial) gateSerial.focus();
    }, 100);
  }

  step2.scrollIntoView({ behavior: 'smooth' });
}
window.proceedToVoucherStep = proceedToVoucherStep;

function backToPlacementStep() {
  const step1 = document.getElementById('step-placement-check');
  const step2 = document.getElementById('step-gateway');

  if (step2) step2.style.display = 'none';
  if (step1) step1.style.display = 'block';
  step1.scrollIntoView({ behavior: 'smooth' });
}
window.backToPlacementStep = backToPlacementStep;

function resetPlacementCheck() {
  currentPlacementRecord = null;
  const resultContainer = document.getElementById('placement-check-result');
  const verifiedCard = document.getElementById('placement-verified-card');
  const unverifiedCard = document.getElementById('placement-unverified-card');
  const indexInput = document.getElementById('check_bece_index');

  if (resultContainer) resultContainer.style.display = 'none';
  if (verifiedCard) verifiedCard.style.display = 'none';
  if (unverifiedCard) unverifiedCard.style.display = 'none';
  if (indexInput) {
    indexInput.value = '';
    indexInput.focus();
  }
}
window.resetPlacementCheck = resetPlacementCheck;

function focusPlacementInput() {
  const indexInput = document.getElementById('check_bece_index');
  if (indexInput) {
    indexInput.focus();
    indexInput.select();
  }
}
window.focusPlacementInput = focusPlacementInput;


// ── STEP 2: Handle Candidate Voucher Login ─────────────────────────────────────

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

    // Dynamically update branding if candidate belongs to a specific institution
    if (data.school_name) {
      const nameEl = document.getElementById('portalSchoolName');
      if (nameEl) nameEl.textContent = data.school_name;
    }
    if (data.school_logo) {
      const logoEl = document.getElementById('portalLogoContainer');
      if (logoEl) logoEl.innerHTML = `<img src="${data.school_logo}" alt="${data.school_name || 'School'} Logo" style="width:100%; height:100%; object-fit:contain;" />`;
    }

    statusEl.style.color = '#4ade80';
    statusEl.textContent = '✔ Verified! Unlocking Admission Form...';

    // Show Step 2 Form
    document.getElementById('step-gateway').style.display = 'none';
    document.getElementById('step-form').style.display = 'block';

    document.getElementById('cand-name-display').textContent = data.full_name;
    document.getElementById('cand-bece-display').textContent = data.bece_index_number;
    document.getElementById('cand-status-badge').textContent = `STATUS: ${data.enrollment_status}`;

    // Pre-populate program electives if available
    await updateElectiveComboOptions(data.program_name, data.program_id);

  } catch (err) {
    statusEl.style.color = '#f87171';
    statusEl.textContent = `❌ ${err.message}`;
  }
}


async function updateElectiveComboOptions(programName, programId) {
  const comboSelect = document.getElementById('adm_elective_combo');
  if (!comboSelect) return;

  comboSelect.innerHTML = '<option value="">-- Loading available elective packages... --</option>';

  // 1. Try fetching school-configured dynamic combinations from API
  if (programId) {
    try {
      const res = await fetch(`${API_BASE}/cssps/program-options/${programId}`);
      if (res.ok) {
        const data = await res.json();
        if (data.combinations && data.combinations.length > 0) {
          comboSelect.innerHTML = `
            <option value="">-- Choose Approved Elective Package --</option>
            ${data.combinations.map(c => {
              const subjList = (c.subjects && c.subjects.length > 0) ? ` (${c.subjects.map(s => s.name).join(' + ')})` : '';
              const streamInfo = c.class_section_name ? ` → (${c.class_section_name})` : '';
              return `<option value="${c.name}" data-combo-id="${c.id}">${c.name}${subjList}${streamInfo}</option>`;
            }).join('')}
          `;
          return;
        }
      }
    } catch (_) {}
  }

  // 2. Graceful fallback to standard GES defaults if custom packages not configured
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
  } else {
    comboSelect.innerHTML = `
      <option value="">-- Standard Curriculum Track --</option>
      <option value="Option A (Standard General Curriculum)">Option A: Standard Core & Elective Package → (Form 1 Stream 1)</option>
      <option value="Option B (Alternative Stream)">Option B: Alternative Stream → (Form 1 Stream 2)</option>
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

  const comboSelect = document.getElementById('adm_elective_combo');
  const selectedOption = comboSelect.options[comboSelect.selectedIndex];
  const comboId = selectedOption ? selectedOption.getAttribute('data-combo-id') : null;

  const payload = {
    student_id: currentVerifiedStudent.student_id,
    serial_code: currentVerifiedStudent.serial_code,
    elective_combination: comboSelect.value,
    elective_combination_id: comboId ? parseInt(comboId) : null,
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


// ── 3. Handle Re-Printing / Document Retrieval ────────────────────────────────

async function handleRetrieveAdmission(event) {
  event.preventDefault();
  const statusEl = document.getElementById('retrieve-status');
  statusEl.style.color = '#38bdf8';
  statusEl.textContent = 'Looking up admission records...';

  const bece_index_number = document.getElementById('ret_bece_index').value.trim();
  const pin_code = document.getElementById('ret_pin').value.trim();

  try {
    const res = await fetch(`${API_BASE}/vouchers/retrieve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ bece_index_number, pin_code })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Lookup failed');

    statusEl.style.color = '#4ade80';
    statusEl.textContent = '✔ Record found! Loading documents...';

    loadProspectusPackage(data.student_id);

  } catch (err) {
    statusEl.style.color = '#f87171';
    statusEl.textContent = `❌ ${err.message}`;
  }
}
window.handleRetrieveAdmission = handleRetrieveAdmission;


// ── 4. Load Dynamic GES Prospectus & Admission Letter Package ────────────────

async function loadProspectusPackage(studentId) {
  try {
    currentLoadedStudentId = studentId;
    const res = await fetch(`${API_BASE}/cssps/prospectus-package/${studentId}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Failed to load prospectus');

    const s = data.student_info;
    const p = data.prospectus;

    document.getElementById('step-gateway').style.display = 'none';
    const formEl = document.getElementById('step-form');
    if (formEl) formEl.style.display = 'none';
    const retEl = document.getElementById('tabContentRetrieve');
    if (retEl) retEl.style.display = 'none';
    document.getElementById('step-package').style.display = 'block';

    // Populate Printable Letterhead
    const schoolName = s.school_name || 'J.A. KUFFOUR STEM TECHNICAL SCHOOL';
    document.getElementById('letter-school-name').textContent = schoolName;
    document.getElementById('letter-school-body').textContent = schoolName;
    document.getElementById('letter-student-name').textContent = s.full_name;
    document.getElementById('letter-bece-index').textContent = s.bece_index_number;
    document.getElementById('letter-student-code').textContent = s.student_code;
    document.getElementById('letter-program').textContent = s.program_name;
    document.getElementById('letter-class').textContent = s.class_name;
    document.getElementById('letter-house').textContent = `${s.house_name} (${s.dormitory_name})`;
    document.getElementById('letter-residential').textContent = s.residential_status;
    document.getElementById('letter-year').textContent = s.academic_year;
    document.getElementById('letter-year-body').textContent = s.academic_year;
    const qrEl = document.getElementById('letter-qr-code');
    if (qrEl) qrEl.textContent = s.qr_verification_code || `VERIFIED-${s.student_code || s.bece_index_number}`;

    // Populate Medical Certificate Info
    document.querySelectorAll('.med-cand-name').forEach(el => el.textContent = s.full_name);
    document.querySelectorAll('.med-cand-bece').forEach(el => el.textContent = s.bece_index_number);
    document.querySelectorAll('.med-cand-blood').forEach(el => el.textContent = s.blood_group || 'Pending Clinical Test');

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
    if ((s.residential_status || '').toLowerCase() === 'day') {
      const bSec = document.getElementById('section-boarding');
      if (bSec) bSec.style.display = 'none';
    }

  } catch (err) {
    alert(`Prospectus Error: ${err.message}`);
  }
}

async function downloadAdmissionPackagePDF(studentId = null) {
  const targetId = studentId || currentLoadedStudentId || (currentVerifiedStudent ? currentVerifiedStudent.student_id : null);
  if (!targetId) {
    alert('No active student placement record found to generate PDF.');
    return;
  }

  const btn = document.getElementById('downloadPdfBtn');
  const originalText = btn ? btn.innerHTML : '';
  if (btn) {
    btn.innerHTML = '⏳ Generating PDF Package...';
    btn.disabled = true;
  }

  try {
    const res = await fetch(`${API_BASE}/cssps/admission-package-pdf/${targetId}`);
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || 'Failed to download admission package PDF.');
    }
    const blob = await res.blob();
    const blobUrl = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = blobUrl;
    a.download = `Official_Admission_Package_${targetId}.pdf`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(blobUrl);
    document.body.removeChild(a);
  } catch (err) {
    alert(`PDF Download Error: ${err.message}`);
  } finally {
    if (btn) {
      btn.innerHTML = originalText;
      btn.disabled = false;
    }
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


// ── 5. Instant MoMo Voucher Purchase Modal Controls ─────────────────────────

function openBuyVoucherModal() {
  const modal = document.getElementById('modalBuyVoucher');
  if (modal) {
    modal.style.display = 'flex';
    const beceInput = document.getElementById('buy_bece_index');
    const phoneInput = document.getElementById('buy_parent_phone');
    if (beceInput) {
      if (currentPlacementRecord && currentPlacementRecord.bece_index_number) {
        beceInput.value = currentPlacementRecord.bece_index_number;
        if (phoneInput) setTimeout(() => phoneInput.focus(), 150);
      } else {
        setTimeout(() => beceInput.focus(), 150);
      }
    }
  }
}
window.openBuyVoucherModal = openBuyVoucherModal;

let momoPollingTimer = null;
let momoCountdownInterval = null;
let activeOrderRef = null;
let activeParentPhone = null;
let activeBeceIndex = null;
let activeMomoNet = null;
let activeAmount = null;

function resetVoucherModal() {
  if (otpVerificationTimer) clearInterval(otpVerificationTimer);
  if (momoPollingTimer) clearInterval(momoPollingTimer);
  if (momoCountdownInterval) clearInterval(momoCountdownInterval);
  const form = document.getElementById('buy-voucher-form');
  const authScreen = document.getElementById('momo-auth-screen');
  const btn = document.getElementById('btnPayVoucher');
  const otpBtn = document.getElementById('btnSubmitMomoOtp');
  const otpInput = document.getElementById('momo_otp_input');
  const otpStatus = document.getElementById('momo-otp-status');

  if (form) form.style.display = 'block';
  if (authScreen) authScreen.style.display = 'none';
  if (btn) btn.disabled = false;
  if (otpBtn) {
    otpBtn.disabled = false;
    otpBtn.textContent = '⚡ Verify Code & Get Voucher';
  }
  if (otpInput) otpInput.value = '';
  if (otpStatus) otpStatus.textContent = '';
}
window.resetVoucherModal = resetVoucherModal;

function closeBuyVoucherModal() {
  resetVoucherModal();
  const modal = document.getElementById('modalBuyVoucher');
  if (modal) modal.style.display = 'none';
}
window.closeBuyVoucherModal = closeBuyVoucherModal;

function showMomoAuthScreen(orderRef, phone, amount, beceIndex, momoNet, displayText) {
  if (otpVerificationTimer) clearInterval(otpVerificationTimer);
  if (momoPollingTimer) clearInterval(momoPollingTimer);
  if (momoCountdownInterval) clearInterval(momoCountdownInterval);

  activeOrderRef = orderRef;
  activeParentPhone = phone;
  activeBeceIndex = beceIndex;
  activeMomoNet = momoNet;
  activeAmount = amount;

  const form = document.getElementById('buy-voucher-form');
  const authScreen = document.getElementById('momo-auth-screen');

  if (form) form.style.display = 'none';
  if (authScreen) authScreen.style.display = 'block';

  const phEl = document.getElementById('momoAuthPhone');
  const amtEl = document.getElementById('momoAuthAmount');
  const otpStatus = document.getElementById('momo-otp-status');
  const otpInput = document.getElementById('momo_otp_input');
  const countdownEl = document.getElementById('momoCountdown');

  if (phEl) phEl.textContent = `${phone} (${momoNet || 'MoMo'})`;
  if (amtEl) amtEl.textContent = `GHS ${parseFloat(amount || currentVoucherPrice).toFixed(2)}`;
  if (otpStatus) {
    otpStatus.style.color = '#38bdf8';
    otpStatus.textContent = displayText || 'Enter code received via SMS, or approve prompt on phone.';
  }
  if (otpInput) {
    otpInput.value = '';
    setTimeout(() => otpInput.focus(), 150);
  }

  // 1. Live USSD Countdown in background
  let remaining = 60;
  momoCountdownInterval = setInterval(() => {
    remaining--;
    if (countdownEl) countdownEl.textContent = `Waiting for network confirmation... (${remaining}s)`;
    if (remaining <= 0) {
      clearInterval(momoCountdownInterval);
      if (countdownEl) countdownEl.textContent = 'Still waiting for network? Click "I\'ve Approved on Phone" below.';
    }
  }, 1000);

  // 2. Background Auto-Poll for instant USSD / Webhook fulfillment
  momoPollingTimer = setInterval(async () => {
    try {
      const res = await fetch(`${API_BASE}/vouchers/verify-status`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          applicant_phone: phone,
          order_reference: orderRef
        })
      });
      if (res.ok) {
        const vData = await res.json();
        if ((vData.status === 'CONFIRMED' || vData.status === 'DELIVERED') && vData.serial_code && vData.pin_code) {
          clearInterval(momoPollingTimer);
          if (momoCountdownInterval) clearInterval(momoCountdownInterval);
          if (otpVerificationTimer) clearInterval(otpVerificationTimer);
          localStorage.removeItem('pending_voucher_order');
          onVoucherFulfilled(beceIndex, vData.serial_code, vData.pin_code, phone);
        }
      }
    } catch (_) {}
  }, 2500);
}
window.showMomoAuthScreen = showMomoAuthScreen;
window.showMomoOtpScreen = showMomoAuthScreen;

let otpVerificationTimer = null;

function startOtpVerificationPolling(orderRef, phone, beceIndex) {
  if (otpVerificationTimer) clearInterval(otpVerificationTimer);
  if (momoPollingTimer) clearInterval(momoPollingTimer);

  const otpStatus = document.getElementById('momo-otp-status');
  const otpBtn = document.getElementById('btnSubmitMomoOtp');

  let attempts = 0;
  const maxAttempts = 20; // 30 seconds total (every 1.5s)

  otpVerificationTimer = setInterval(async () => {
    attempts++;
    if (otpStatus) {
      otpStatus.style.color = '#38bdf8';
      otpStatus.textContent = `✔ Code submitted. Verifying debit with network (${attempts}/${maxAttempts})...`;
    }

    try {
      const res = await fetch(`${API_BASE}/vouchers/verify-status`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          applicant_phone: phone,
          order_reference: orderRef
        })
      });

      if (res.ok) {
        const vData = await res.json();
        if ((vData.status === 'CONFIRMED' || vData.status === 'DELIVERED') && vData.serial_code && vData.pin_code) {
          clearInterval(otpVerificationTimer);
          if (momoPollingTimer) clearInterval(momoPollingTimer);
          localStorage.removeItem('pending_voucher_order');
          if (otpStatus) {
            otpStatus.style.color = '#4ade80';
            otpStatus.textContent = '✔ Payment confirmed! Unlocking admission voucher...';
          }
          onVoucherFulfilled(beceIndex, vData.serial_code, vData.pin_code, phone);
          return;
        }
      }
    } catch (_) {}

    if (attempts >= maxAttempts) {
      clearInterval(otpVerificationTimer);
      if (otpStatus) {
        otpStatus.style.color = '#fbbf24';
        otpStatus.textContent = 'Network confirmation is taking a moment. Please check your SMS or click Verify again.';
      }
      if (otpBtn) {
        otpBtn.disabled = false;
        otpBtn.textContent = '⚡ Verify Code & Get Voucher';
      }
    }
  }, 1500);
}
window.startOtpVerificationPolling = startOtpVerificationPolling;

async function submitMomoOtp(event) {
  if (event) event.preventDefault();
  const otpInput = document.getElementById('momo_otp_input');
  const otpStatus = document.getElementById('momo-otp-status');
  const otpBtn = document.getElementById('btnSubmitMomoOtp');

  const code = (otpInput ? otpInput.value : '').trim();
  if (!code || code.length < 4) {
    if (otpStatus) {
      otpStatus.style.color = '#f87171';
      otpStatus.textContent = 'Please enter the full 6-digit authorization code.';
    }
    return;
  }

  if (otpBtn) {
    otpBtn.disabled = true;
    otpBtn.textContent = '⏳ Verifying Code...';
  }
  if (otpStatus) {
    otpStatus.style.color = '#38bdf8';
    otpStatus.textContent = 'Submitting authorization code to Paystack & issuing voucher...';
  }

  try {
    const res = await fetch(`${API_BASE}/vouchers/submit-otp`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        order_reference: activeOrderRef,
        otp: code,
        bece_index_number: activeBeceIndex
      })
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || data.message || 'Invalid authorization code. Please try again.');
    }

    if (data.serial_code && data.pin_code) {
      if (otpVerificationTimer) clearInterval(otpVerificationTimer);
      if (momoPollingTimer) clearInterval(momoPollingTimer);
      localStorage.removeItem('pending_voucher_order');
      if (otpStatus) {
        otpStatus.style.color = '#4ade80';
        otpStatus.textContent = '✔ Code verified! Unlocking admission voucher...';
      }
      onVoucherFulfilled(activeBeceIndex, data.serial_code, data.pin_code, activeParentPhone);
    } else if (data.status === 'processing' || data.status === 'pending') {
      if (otpStatus) {
        otpStatus.style.color = '#38bdf8';
        otpStatus.textContent = '✔ Code accepted. Waiting for network debit confirmation...';
      }
      startOtpVerificationPolling(activeOrderRef, activeParentPhone, activeBeceIndex);
    } else {
      throw new Error(data.message || 'Payment could not be verified.');
    }
  } catch (err) {
    if (otpStatus) {
      otpStatus.style.color = '#f87171';
      otpStatus.textContent = `❌ ${err.message}`;
    }
    if (otpBtn) {
      otpBtn.disabled = false;
      otpBtn.textContent = '⚡ Verify Code & Get Voucher';
    }
  }
}
window.submitMomoOtp = submitMomoOtp;

async function handleBuyVoucher(event) {
  event.preventDefault();
  const statusEl = document.getElementById('buy-voucher-status');
  const btn = document.getElementById('btnPayVoucher');

  const beceIndex = document.getElementById('buy_bece_index').value.trim();
  const parentPhone = document.getElementById('buy_parent_phone').value.trim();
  const momoNet = document.getElementById('buy_momo_network').value;
  const schoolId = currentActiveSchoolId ? parseInt(currentActiveSchoolId) : 2;

  statusEl.style.color = '#38bdf8';
  statusEl.textContent = `Dispatching MoMo prompt of GHS ${currentVoucherPrice.toFixed(2)} to ${parentPhone}...`;
  btn.disabled = true;

  try {
    // 1. Initiate purchase via direct checkout
    let data;
    try {
      const res = await fetch(`${API_BASE}/vouchers/checkout/initiate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          school_id: schoolId,
          applicant_name: `Candidate ${beceIndex}`,
          applicant_phone: parentPhone,
          bece_index_number: beceIndex,
          momo_network: momoNet,
          gateway: 'PAYSTACK'
        })
      });
      if (res.ok) data = await res.json();
    } catch (_) {}

    // Fallback to direct purchase endpoint if needed
    if (!data) {
      const fbRes = await fetch(`${API_BASE}/vouchers/purchase-online`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          school_id: schoolId,
          bece_index_number: beceIndex,
          parent_phone: parentPhone,
          momo_network: momoNet,
          amount: currentVoucherPrice
        })
      });
      data = await fbRes.json();
    }

    if (data.serial_code && data.pin_code) {
      // Instant fulfillment
      onVoucherFulfilled(beceIndex, data.serial_code, data.pin_code, parentPhone);
    } else if (data.order_reference) {
      activeOrderRef = data.order_reference;
      activeParentPhone = parentPhone;
      activeBeceIndex = beceIndex;
      activeMomoNet = momoNet;
      activeAmount = data.amount || currentVoucherPrice;

      localStorage.setItem('pending_voucher_order', JSON.stringify({
        order_ref: data.order_reference,
        phone: parentPhone,
        bece: beceIndex,
        network: momoNet,
        timestamp: Date.now()
      }));

      // Directly show unified authorization & OTP screen
      showMomoAuthScreen(data.order_reference, parentPhone, data.amount || currentVoucherPrice, beceIndex, momoNet, data.display_text);
    } else {
      throw new Error(data.detail || 'Could not initiate Mobile Money transaction.');
    }
  } catch (err) {
    statusEl.style.color = '#f87171';
    statusEl.textContent = `❌ ${err.message}`;
    btn.disabled = false;
  }
}
window.handleBuyVoucher = handleBuyVoucher;

async function checkVoucherStatusManually() {
  if (!activeOrderRef || !activeParentPhone) return;
  const otpStatus = document.getElementById('momo-otp-status');

  if (otpStatus) {
    otpStatus.style.color = '#38bdf8';
    otpStatus.textContent = 'Verifying Mobile Money transaction status with Paystack...';
  }

  try {
    const res = await fetch(`${API_BASE}/vouchers/verify-status`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        applicant_phone: activeParentPhone,
        order_reference: activeOrderRef
      })
    });
    if (res.ok) {
      const vData = await res.json();
      if (vData.serial_code && vData.pin_code) {
        if (momoPollingTimer) clearInterval(momoPollingTimer);
        if (momoCountdownInterval) clearInterval(momoCountdownInterval);
        if (otpVerificationTimer) clearInterval(otpVerificationTimer);
        localStorage.removeItem('pending_voucher_order');
        onVoucherFulfilled(activeBeceIndex, vData.serial_code, vData.pin_code, activeParentPhone);
        return;
      }
    }
    if (otpStatus) {
      otpStatus.style.color = '#fbbf24';
      otpStatus.textContent = 'Payment not yet confirmed by network. Please enter the OTP or check your phone.';
    }
  } catch (e) {
    if (otpStatus) otpStatus.textContent = 'Network check failed. Retrying...';
  }
}
window.checkVoucherStatusManually = checkVoucherStatusManually;

function onVoucherFulfilled(beceIndex, serial, pin, phone) {
  const form = document.getElementById('buy-voucher-form');
  const authScreen = document.getElementById('momo-auth-screen');

  if (form) form.style.display = 'block';
  if (authScreen) authScreen.style.display = 'none';

  const statusEl = document.getElementById('buy-voucher-status');
  if (statusEl) {
    statusEl.style.color = '#4ade80';
    statusEl.innerHTML = `✔ <strong>Payment Approved!</strong> Serial: <code>${serial}</code> | PIN: <code>${pin}</code> (Receipt sent to ${phone})`;
  }

  const gateBece = document.getElementById('gate_bece_index');
  const gateSerial = document.getElementById('gate_serial');
  const gatePin = document.getElementById('gate_pin');
  if (gateBece && beceIndex) gateBece.value = beceIndex;
  if (gateSerial) gateSerial.value = serial;
  if (gatePin) gatePin.value = pin;

  const loginStatus = document.getElementById('voucher-login-status');
  if (loginStatus) {
    loginStatus.style.color = '#4ade80';
    loginStatus.textContent = '✔ Credentials verified and auto-filled! Entering admission docket...';
  }

  setTimeout(() => {
    closeBuyVoucherModal();
    const btn = document.getElementById('btnPayVoucher');
    if (btn) btn.disabled = false;
    if (statusEl) statusEl.textContent = '';
    
    // Auto-trigger verification and login into form
    const loginForm = document.getElementById('voucher-login-form');
    if (loginForm) {
      handleVoucherLogin(new Event('submit'));
    }
  }, 1800);
}


// ── 6. Batch Generate Vouchers Helper (Admin Tool) ───────────────────────────

async function handleGenerateBatchVouchers() {
  const token = localStorage.getItem('accessToken');
  if (!token) {
    alert('Admin authentication required to generate vouchers. Please login as Admin or Academic Head.');
    window.location.href = 'auth.html';
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

window.handleVoucherLogin = handleVoucherLogin;
window.handleFormSubmission = handleFormSubmission;
window.handleGenerateBatchVouchers = handleGenerateBatchVouchers;

// Auto-recover pending background MoMo order on page load
window.addEventListener('DOMContentLoaded', async () => {
  const pending = localStorage.getItem('pending_voucher_order');
  if (pending) {
    try {
      const order = JSON.parse(pending);
      if (Date.now() - order.timestamp < 3600000) {
        const res = await fetch(`${API_BASE}/vouchers/verify-status`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            applicant_phone: order.phone,
            order_reference: order.order_ref
          })
        });
        if (res.ok) {
          const vData = await res.json();
          if (vData.serial_code && vData.pin_code) {
            localStorage.removeItem('pending_voucher_order');
            onVoucherFulfilled(order.bece, vData.serial_code, vData.pin_code, order.phone);
          }
        }
      }
    } catch (_) {}
  }
});

