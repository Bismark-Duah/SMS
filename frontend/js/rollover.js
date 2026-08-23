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

let activeYearsData = [];
let activeSemestersData = [];

document.addEventListener('DOMContentLoaded', () => {
  loadRolloverStatus();
});

async function loadRolloverStatus() {
  try {
    const res = await fetch(`${API_BASE}/rollover/status`, { headers: getHeaders() });
    if (res.ok) {
      const data = await res.json();
      
      document.getElementById('currentYearText').textContent = data.current_year_label;
      document.getElementById('currentSemText').textContent = data.current_semester_name;
      document.getElementById('enrolledCount').textContent = data.active_students_count;
      document.getElementById('unpaidCount').textContent = data.unpaid_fees_count;
      document.getElementById('unpaidAmountText').textContent = `GHc ${data.total_unpaid_amount.toFixed(2)}`;

      activeYearsData = data.years;
      activeSemestersData = data.semesters;

      // Populate Target Year select
      const yrSelect = document.getElementById('targetYearSelect');
      yrSelect.innerHTML = '<option value="">Select Target Year...</option>' + 
        data.years.map(y => `<option value="${y.id}" ${y.is_current ? 'disabled style="opacity:0.5"' : ''}>${y.label} ${y.is_current ? '(Current)' : ''}</option>`).join('');

      // Add target year change listener to filter target terms
      yrSelect.onchange = (e) => {
        const yearId = parseInt(e.target.value);
        const termSelect = document.getElementById('targetSemSelect');
        if (!yearId) {
          termSelect.innerHTML = '<option value="">Select Term...</option>';
          return;
        }

        const filteredSems = activeSemestersData.filter(s => s.academic_year_id === yearId);
        termSelect.innerHTML = '<option value="">Select Target Term...</option>' + 
          filteredSems.map(s => `<option value="${s.id}">${s.name}</option>`).join('');
      };

    } else {
      console.error("Failed to load rollover status.");
    }
  } catch (error) {
    console.error("Error loading rollover status:", error);
  }
}

window.nextStep = function(stepNum) {
  // Hide all steps
  document.querySelectorAll('.wizard-step').forEach(el => el.classList.remove('active'));
  
  // Show target step
  document.getElementById(`step-${stepNum}`).classList.add('active');

  // Update step nodes
  for (let i = 1; i <= 4; i++) {
    const node = document.getElementById(`node-${i}`);
    if (i < stepNum) {
      node.classList.add('completed');
      node.classList.remove('active');
    } else if (i === stepNum) {
      node.classList.add('active');
      node.classList.remove('completed');
    } else {
      node.classList.remove('active', 'completed');
    }
  }
};

window.prevStep = function(stepNum) {
  window.nextStep(stepNum);
};

window.executeRollover = async function() {
  const targetYearId = parseInt(document.getElementById('targetYearSelect').value);
  const targetSemId = parseInt(document.getElementById('targetSemSelect').value);
  const carryOverFees = document.getElementById('carryOverCheckbox').checked;
  const archiveReports = document.getElementById('archiveReportsCheckbox').checked;

  if (!targetYearId || !targetSemId) {
    alert("Please select both target academic year and term.");
    return;
  }

  const confirmMsg = "CRITICAL ACTION REQUIRED!\n\nExecuting term rollover is irreversible. It locks active grades, carries over balances, and updates the active school term.\n\nAre you absolutely sure you want to proceed?";
  if (!confirm(confirmMsg)) {
    return;
  }

  const msgEl = document.getElementById('rolloverMsg');
  msgEl.innerHTML = '<span style="opacity:0.7">Executing rollover actions. Please do not close this page...</span>';

  try {
    const payload = {
      target_year_id: targetYearId,
      target_semester_id: targetSemId,
      carry_over_fees: carryOverFees,
      archive_reports: archiveReports
    };

    const res = await fetch(`${API_BASE}/rollover/execute`, {
      method: 'POST',
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    if (res.ok) {
      msgEl.innerHTML = `<span style="color:var(--success-color)">✔ Rollover Completed Successfully!<br>Active Term advanced. ${data.fees_carried_over} fee balances carried over.</span>`;
      // Clear targets
      document.getElementById('targetYearSelect').value = '';
      document.getElementById('targetSemSelect').value = '';
      // Reload status
      loadRolloverStatus();
      
      // Auto redirect back to settings after 3 seconds
      setTimeout(() => {
        window.location.href = 'settings.html';
      }, 3000);
    } else {
      msgEl.innerHTML = `<span style="color:var(--danger-color)">Rollover Failed: ${data.detail || 'Execution error'}</span>`;
    }
  } catch (e) {
    msgEl.innerHTML = `<span style="color:var(--danger-color)">Network error executing rollover.</span>`;
  }
};
