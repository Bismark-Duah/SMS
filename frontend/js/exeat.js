// Exeat Management JavaScript Module

let allStudents = [];
let allHouses = [];
let exeatRecords = [];

document.addEventListener("DOMContentLoaded", () => {
  initExeatPage();
});

async function getAuthHeader() {
  const token = localStorage.getItem("accessToken") || sessionStorage.getItem("accessToken");
  return {
    "Content-Type": "application/json",
    "Authorization": token ? `Bearer ${token}` : ""
  };
}

window.openGatekeeperView = function() {
  const code = prompt("🚪 GATEKEEPER VERIFICATION:\nEnter Student Code or Index Number (e.g. SHS-10029381):");
  if (!code) return;
  const cleanCode = code.trim().toLowerCase();
  
  const record = exeatRecords.find(r => 
    (r.student_code && r.student_code.toLowerCase() === cleanCode) ||
    (r.student_name && r.student_name.toLowerCase().includes(cleanCode))
  );

  if (record && (record.status === 'Approved' || record.status === 'Active' || record.status === 'Signed Out')) {
    alert(`🟢 GATE PASS APPROVED & VALID!\n\n👤 Student: ${record.student_name} (${record.student_code})\n📚 Class: ${record.class_name || 'N/A'}\n📋 Type: ${record.exeat_type}\n📍 Destination: ${record.destination}\n🟢 Status: ${record.status.toUpperCase()}\n\n✅ Security Officer: Clear for departure/entry.`);
  } else if (record) {
    alert(`🔴 GATE PASS DENIED!\n\n👤 Student: ${record.student_name} (${record.student_code})\n🔴 Status: ${record.status.toUpperCase()}\n\n❌ Reason: Exeat is NOT in approved state.`);
  } else {
    alert(`🔴 GATE PASS DENIED!\n\nNo active exeat record found for '${code}'.\n❌ Reason: Student has no authorized exeat slip.`);
  }
};

async function initExeatPage() {
  try {
    await Promise.all([
      loadJurisdictionAndStats(),
      loadHousesFilter(),
      loadStudentsForModal(),
      loadExeatRecords()
    ]);
    setDefaultDateTimes();
  } catch (err) {
    console.error("Initialization error:", err);
  }
}

function setDefaultDateTimes() {
  const now = new Date();
  const tomorrow = new Date(now);
  tomorrow.setDate(tomorrow.getDate() + 1);
  tomorrow.setHours(17, 0, 0, 0); // 5:00 PM tomorrow

  const formatLocalISO = (d) => {
    const tzOffset = d.getTimezoneOffset() * 60000;
    return new Date(d.getTime() - tzOffset).toISOString().slice(0, 16);
  };

  const depInput = document.getElementById("formExpectedDeparture");
  const retInput = document.getElementById("formExpectedReturn");
  if (depInput && !depInput.value) depInput.value = formatLocalISO(now);
  if (retInput && !retInput.value) retInput.value = formatLocalISO(tomorrow);
}

async function loadJurisdictionAndStats() {
  const headers = await getAuthHeader();
  
  // Load Stats
  try {
    const res = await fetch("/api/exeat/stats", { headers });
    if (res.ok) {
      const stats = await res.json();
      document.getElementById("statCurrentlyAway").innerText = stats.currently_away;
      document.getElementById("statPending").innerText = stats.pending_approvals;
      document.getElementById("statOverdue").innerText = stats.overdue_returns;
      document.getElementById("statTotalTerm").innerText = stats.total_this_term;
    }
  } catch (e) {
    console.error("Failed to load stats:", e);
  }

  // Load Current User info to display jurisdiction banner
  try {
    const userRes = await fetch("/api/auth/me", { headers });
    if (userRes.ok) {
      const user = await userRes.json();
      const roleNames = (user.roles || []).map(r => r.name.toLowerCase());
      const username = user.username;

      let title = `Logged in as: ${username}`;
      let desc = "You can manage exeat requests according to your boarding permissions.";

      if (roleNames.includes("admin") || roleNames.includes("assistant_head_domestic")) {
        title = "🛡️ Executive Domestic Oversight (All Boarding Houses)";
        desc = "Full administrative privilege over Boys and Girls houses across the entire school.";
      } else if (roleNames.includes("senior_house_master") || username.toLowerCase().includes("senior house master")) {
        title = "🚹 Senior House Master (All Boys Houses)";
        desc = "Executive jurisdiction over all male students and boys' boarding houses.";
      } else if (roleNames.includes("senior_house_mistress") || username.toLowerCase().includes("senior house mistress")) {
        title = "🚺 Senior House Mistress (All Girls Houses)";
        desc = "Executive jurisdiction over all female students and girls' boarding houses.";
      } else {
        title = `👤 House Master / Residential Staff (${username})`;
        desc = "Authorized to issue and approve exeats for students residing in your assigned house.";
      }

      document.getElementById("jurisdictionRoleLabel").innerText = title;
      document.getElementById("jurisdictionDescription").innerText = desc;
    }
  } catch (e) {
    console.warn("Could not load user profile info:", e);
  }
}

async function loadHousesFilter() {
  const headers = await getAuthHeader();
  try {
    const res = await fetch("/api/houses/", { headers });
    if (res.ok) {
      allHouses = await res.json();
      const houseSelect = document.getElementById("filterHouse");
      if (houseSelect) {
        houseSelect.innerHTML = '<option value="">All Houses</option>';
        allHouses.forEach(h => {
          houseSelect.innerHTML += `<option value="${h.id}">${h.name} (${h.gender})</option>`;
        });
      }
    }
  } catch (e) {
    console.error("Failed to load houses filter:", e);
  }
}

async function loadStudentsForModal() {
  const headers = await getAuthHeader();
  try {
    const res = await fetch("/api/students/", { headers });
    if (res.ok) {
      allStudents = await res.json();
      const studentSelect = document.getElementById("formStudentId");
      if (studentSelect) {
        studentSelect.innerHTML = '<option value="">Select student...</option>';
        allStudents.forEach(s => {
          const houseInfo = s.house ? ` [${s.house.name}]` : "";
          studentSelect.innerHTML += `<option value="${s.id}" data-phone="${s.phone || ''}">${s.full_name} (${s.student_code})${houseInfo}</option>`;
        });
      }
    }
  } catch (e) {
    console.error("Failed to load students:", e);
  }
}

function autoFillParentContact() {
  const select = document.getElementById("formStudentId");
  const phoneInput = document.getElementById("formParentContact");
  if (select && phoneInput) {
    const selectedOption = select.options[select.selectedIndex];
    const phone = selectedOption.getAttribute("data-phone");
    if (phone) phoneInput.value = phone;
  }
}

async function loadExeatRecords() {
  const headers = await getAuthHeader();
  const search = document.getElementById("searchInput")?.value || "";
  const status = document.getElementById("filterStatus")?.value || "";
  const type = document.getElementById("filterType")?.value || "";
  const houseId = document.getElementById("filterHouse")?.value || "";

  let url = `/api/exeat/?search=${encodeURIComponent(search)}&status=${encodeURIComponent(status)}&exeat_type=${encodeURIComponent(type)}`;
  if (houseId) url += `&house_id=${houseId}`;

  const tbody = document.getElementById("exeatTableBody");
  try {
    const res = await fetch(url, { headers });
    if (!res.ok) {
      if (res.status === 401) {
        // Session expired — redirect to login
        window.location.href = `/assets/auth.html?next=${encodeURIComponent(window.location.href)}`;
        return;
      }
      let errDetail = "";
      try { const errJson = await res.json(); errDetail = errJson.detail || ""; } catch (_) {}
      tbody.innerHTML = `
        <tr><td colspan="7" style="text-align:center; padding:30px;">
          <div style="color:#ef4444; font-weight:600; margin-bottom:10px;">
            ⚠️ Failed to load exeats (${res.status})${errDetail ? `: ${errDetail}` : ""}
          </div>
          <button class="btn btn-sm btn-primary" onclick="loadExeatRecords()" style="margin-top:4px;">🔄 Retry</button>
        </td></tr>`;
      return;
    }

    exeatRecords = await res.json();
    if (exeatRecords.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding:30px; opacity:0.6;">No exeat records found matching criteria.</td></tr>';
      return;
    }

    tbody.innerHTML = exeatRecords.map(ex => {
      const depDate = new Date(ex.expected_departure).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
      const retDate = new Date(ex.expected_return).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
      const houseStr = ex.house_name ? `${ex.house_name}` + (ex.dormitory_name ? ` (${ex.dormitory_name})` : '') : 'N/A';

      const statusBadge = getStatusBadge(ex.status);

      let actionButtons = `<button class="btn btn-sm" onclick="openExeatSlip(${ex.id})">🖨️ Slip</button> `;

      if (ex.status === "Pending") {
        actionButtons += `<button class="btn btn-sm btn-primary" onclick="approveExeat(${ex.id})">Approve</button> `;
        actionButtons += `<button class="btn btn-sm" style="background:#ef4444; color:white;" onclick="rejectExeat(${ex.id})">Reject</button>`;
      } else if (ex.status === "Approved") {
        actionButtons += `<button class="btn btn-sm" style="background:#3b82f6; color:white;" onclick="gateSignOut(${ex.id})">🚪 Sign Out</button>`;
      } else if (ex.status === "Departed" || ex.status === "Overdue") {
        actionButtons += `<button class="btn btn-sm" style="background:#22c55e; color:white;" onclick="gateSignIn(${ex.id})">🟢 Sign In</button>`;
      }

      return `
        <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
          <td style="padding:12px 10px;">
            <div style="font-weight:700;">${ex.student_name}</div>
            <div style="font-size:0.78rem; opacity:0.7;">Code: ${ex.student_code} | Class: ${ex.class_name || 'N/A'}</div>
          </td>
          <td style="padding:12px 10px;">${houseStr}</td>
          <td style="padding:12px 10px;">
            <div style="font-weight:600;">${ex.exeat_type} Exeat</div>
            <div style="font-size:0.78rem; opacity:0.8; color:#94a3b8;">📍 ${ex.destination}</div>
          </td>
          <td style="padding:12px 10px;">${depDate}</td>
          <td style="padding:12px 10px;">${retDate}</td>
          <td style="padding:12px 10px;">${statusBadge}</td>
          <td style="padding:12px 10px; text-align:right;">${actionButtons}</td>
        </tr>
      `;
    }).join('');

  } catch (err) {
    console.error("Error rendering exeat records:", err);
    tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding:30px; color:#ef4444;">Error loading data.</td></tr>';
  }
}

function getStatusBadge(status) {
  const s = (status || "").toLowerCase();
  if (s === "pending") return '<span class="badge-status status-pending">⏳ Pending</span>';
  if (s === "approved") return '<span class="badge-status status-approved">🟢 Approved</span>';
  if (s === "rejected") return '<span class="badge-status status-rejected">❌ Rejected</span>';
  if (s === "departed") return '<span class="badge-status status-departed">🚶‍♂️ Departed</span>';
  if (s === "returned") return '<span class="badge-status status-returned">🟩 Returned</span>';
  if (s === "overdue") return '<span class="badge-status status-overdue">🚨 OVERDUE</span>';
  return `<span class="badge-status">${status}</span>`;
}

function switchTab(tab) {
  document.getElementById("tabBtnLog").classList.toggle("active", tab === 'log');
  document.getElementById("tabBtnGate").classList.toggle("active", tab === 'gate');

  document.getElementById("tabContentLog").style.display = (tab === 'log') ? 'block' : 'none';
  document.getElementById("tabContentGate").style.display = (tab === 'gate') ? 'block' : 'none';
}

function openNewExeatModal() {
  document.getElementById("newExeatForm").reset();
  setDefaultDateTimes();
  document.getElementById("newExeatModal").classList.add("show");
}

function closeModal(modalId) {
  document.getElementById(modalId).classList.remove("show");
}

async function submitNewExeat(e) {
  e.preventDefault();
  const headers = await getAuthHeader();

  const payload = {
    student_id: parseInt(document.getElementById("formStudentId").value),
    exeat_type: document.getElementById("formExeatType").value,
    destination: document.getElementById("formDestination").value,
    reason: document.getElementById("formReason").value,
    expected_departure: new Date(document.getElementById("formExpectedDeparture").value).toISOString(),
    expected_return: new Date(document.getElementById("formExpectedReturn").value).toISOString(),
    parent_contact: document.getElementById("formParentContact").value || null,
    parent_approved: true,
    approval_notes: document.getElementById("formApprovalNotes").value || null
  };

  try {
    const res = await fetch("/api/exeat/", {
      method: "POST",
      headers,
      body: JSON.stringify(payload)
    });

    if (res.ok) {
      alert("Exeat pass created and recorded successfully!");
      closeModal("newExeatModal");
      await loadJurisdictionAndStats();
      await loadExeatRecords();
    } else {
      const errData = await res.json();
      alert(`Error: ${errData.detail || "Could not create exeat"}`);
    }
  } catch (err) {
    alert("Network or server error while submitting exeat.");
    console.error(err);
  }
}

async function approveExeat(exeatId) {
  if (!confirm("Approve this exeat pass?")) return;
  const headers = await getAuthHeader();
  try {
    const res = await fetch(`/api/exeat/${exeatId}/approve`, { method: "PUT", headers });
    if (res.ok) {
      if (window.showToast) window.showToast("✅ Exeat permission approved successfully!", "success");
      await loadJurisdictionAndStats();
      await loadExeatRecords();
    } else {
      const errData = await res.json();
      await (window.showAlertDialog ? window.showAlertDialog("Approval Failed", errData.detail || "Could not approve exeat.", "error") : alert(`Approval Failed: ${errData.detail}`));
    }
  } catch (e) {
    if (window.showToast) window.showToast("Error approving exeat.", "danger");
  }
}

async function rejectExeat(exeatId) {
  const reason = await (window.showPromptDialog ? window.showPromptDialog("Reject Exeat Application", "Please enter the reason for rejecting this exeat request:", "", "Enter reason for rejection...") : Promise.resolve(prompt("Enter reason for rejecting this exeat:")));
  if (reason === null) return;

  const headers = await getAuthHeader();
  try {
    const res = await fetch(`/api/exeat/${exeatId}/reject?notes=${encodeURIComponent(reason)}`, { method: "PUT", headers });
    if (res.ok) {
      if (window.showToast) window.showToast("Exeat request marked as Rejected.", "warning");
      await loadJurisdictionAndStats();
      await loadExeatRecords();
    } else {
      const errData = await res.json();
      await (window.showAlertDialog ? window.showAlertDialog("Rejection Failed", errData.detail || "Could not reject exeat.", "error") : alert(`Rejection Failed: ${errData.detail}`));
    }
  } catch (e) {
    if (window.showToast) window.showToast("Error rejecting exeat.", "danger");
  }
}

async function gateSignOut(exeatId) {
  const confirmed = await (window.showConfirmDialog ? window.showConfirmDialog(
    "🚪 Gate Departure Sign-Out",
    "Confirm student departure at security gate? This will log official departure time and trigger automated guardian notification.",
    "Confirm Departure",
    "Cancel"
  ) : Promise.resolve(confirm("Confirm Student Sign-Out (Departing campus at gate)?")));

  if (!confirmed) return;
  const headers = await getAuthHeader();
  try {
    const res = await fetch(`/api/exeat/${exeatId}/sign-out`, { method: "PUT", headers });
    if (res.ok) {
      if (window.showToast) window.showToast("✅ Student departure logged & guardian notified!", "success");
      await loadJurisdictionAndStats();
      await loadExeatRecords();
      if (document.getElementById("tabContentGate").style.display !== "none") {
        searchGateStudent();
      }
    } else {
      const errData = await res.json();
      await (window.showAlertDialog ? window.showAlertDialog("Gate Sign-Out Failed", errData.detail || "Could not process sign out.", "error") : alert(`Gate Sign-Out Failed: ${errData.detail}`));
    }
  } catch (e) {
    if (window.showToast) window.showToast("Error during gate sign-out.", "danger");
  }
}

async function gateSignIn(exeatId) {
  const confirmed = await (window.showConfirmDialog ? window.showConfirmDialog(
    "✅ Campus Arrival Sign-In",
    "Confirm student safe arrival back on campus? This will log official arrival time and mark the exeat pass completed.",
    "Confirm Safe Return",
    "Cancel"
  ) : Promise.resolve(confirm("Confirm Student Sign-In (Returned to campus at gate)?")));

  if (!confirmed) return;
  const headers = await getAuthHeader();
  try {
    const res = await fetch(`/api/exeat/${exeatId}/sign-in`, { method: "PUT", headers });
    if (res.ok) {
      if (window.showToast) window.showToast("✅ Student safely signed back onto campus!", "success");
      await loadJurisdictionAndStats();
      await loadExeatRecords();
      if (document.getElementById("tabContentGate").style.display !== "none") {
        searchGateStudent();
      }
    } else {
      const errData = await res.json();
      alert(`Gate Sign-In Failed: ${errData.detail}`);
    }
  } catch (e) {
    alert("Error during gate sign-in.");
  }
}

let currentSlipData = null;

async function openExeatSlip(exeatId) {
  const headers = await getAuthHeader();
  try {
    const res = await fetch(`/api/exeat/${exeatId}/slip`, { headers });
    if (res.ok) {
      const ex = await res.json();
      currentSlipData = ex;

      document.getElementById("slipStudentName").innerText = ex.student_name;
      document.getElementById("slipStudentCode").innerText = ex.student_code;
      document.getElementById("slipClass").innerText = ex.class_name || "N/A";
      document.getElementById("slipHouseDorm").innerText = (ex.house_name || "N/A") + (ex.dormitory_name ? ` / ${ex.dormitory_name}` : '');
      document.getElementById("slipType").innerText = `${ex.exeat_type} Exeat`;
      document.getElementById("slipDestination").innerText = ex.destination;

      const depDate = new Date(ex.expected_departure).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' });
      const retDate = new Date(ex.expected_return).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' });

      document.getElementById("slipDeparture").innerText = depDate;
      document.getElementById("slipReturn").innerText = retDate;
      document.getElementById("slipReason").innerText = ex.reason;

      document.getElementById("slipApprovedBy").innerText = ex.approved_by_name || "Self / System";
      document.getElementById("slipApprovedRole").innerText = ex.approved_by_role || "House Master";
      document.getElementById("slipParentContact").innerText = ex.parent_contact || "N/A";

      document.getElementById("slipModal").classList.add("show");
    } else {
      alert("Could not load slip details.");
    }
  } catch (e) {
    alert("Error opening exeat slip.");
  }
}

function dispatchSlipWhatsApp() {
  if (!currentSlipData) return;
  const ex = currentSlipData;
  const rawPhone = ex.parent_contact || '';
  const cleanPhone = rawPhone.replace(/[^0-9]/g, '');
  if (!cleanPhone) {
    alert('No guardian phone contact recorded on this exeat slip.');
    return;
  }
  const formattedPhone = cleanPhone.startsWith('0') && cleanPhone.length === 10 ? ('233' + cleanPhone.slice(1)) : cleanPhone;
  const depDate = new Date(ex.expected_departure).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' });
  const retDate = new Date(ex.expected_return).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' });

  const msg = 
    `🏡 *OFFICIAL PERMISSION PASS / EXEAT NOTICE*\n\n` +
    `👤 *Student:* ${ex.student_name} (${ex.student_code})\n` +
    `📚 *Class:* ${ex.class_name || 'N/A'}\n` +
    `🏠 *House:* ${ex.house_name || 'N/A'}\n` +
    `📋 *Category:* ${ex.exeat_type} Exeat\n` +
    `📍 *Destination:* ${ex.destination}\n` +
    `🕒 *Departure:* ${depDate}\n` +
    `📅 *Due Return:* ${retDate}\n` +
    `📝 *Reason:* ${ex.reason}\n` +
    `🟢 *Status:* ${ex.status.toUpperCase()}\n` +
    `✍️ *Authorized By:* ${ex.approved_by_name || 'House Master'}\n\n` +
    `📌 _Official Clearance Slip issued by School Management System_`;

  const waUrl = `https://wa.me/${formattedPhone}?text=${encodeURIComponent(msg)}`;
  window.open(waUrl, '_blank');
}

function dispatchSlipSms() {
  if (!currentSlipData) return;
  const ex = currentSlipData;
  const rawPhone = ex.parent_contact || '';
  const cleanPhone = rawPhone.replace(/[^0-9+]/g, '');
  if (!cleanPhone) {
    alert('No guardian phone contact recorded on this exeat slip.');
    return;
  }
  const retDate = new Date(ex.expected_return).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' });
  const msg = `EXEAT PASS: ${ex.student_name} (${ex.class_name || ''}) granted ${ex.exeat_type} exeat to ${ex.destination}. Due return: ${retDate}. Status: ${ex.status}.`;
  window.location.href = `sms:${cleanPhone}?body=${encodeURIComponent(msg)}`;
}

function printExeatSlipDoc() {
  const printContents = document.getElementById("printableSlipArea").innerHTML;
  const originalContents = document.body.innerHTML;

  document.body.innerHTML = `<div style="padding:20px;">${printContents}</div>`;
  window.print();
  document.body.innerHTML = originalContents;
  location.reload();
}

async function reportSecurityIncident(studentId, studentName) {
  const reason = await (window.showPromptDialog ? window.showPromptDialog(
    "🚨 Report Security Incident",
    `Enter details for security incident involving ${studentName} to be sent to Assistant Head (Domestic):`,
    "Unauthorized gate departure attempt without valid exeat slip.",
    "Describe gate / curfew violation..."
  ) : Promise.resolve(prompt(`🚨 REPORT SECURITY INCIDENT to Assistant Head (Domestic):\nEnter details for ${studentName}:`, "Unauthorized gate departure attempt without valid exeat slip.")));

  if (!reason) return;

  const headers = await getAuthHeader();
  try {
    const res = await fetch("/api/exeat/security-incident", {
      method: "POST",
      headers,
      body: JSON.stringify({
        student_id: studentId,
        incident_type: "Curfew / Gate Violation",
        description: reason
      })
    });
    if (res.ok) {
      if (window.showToast) window.showToast("🚨 Security incident alert logged and sent to Assistant Head (Domestic).", "warning");
      else alert("🚨 Security incident alert logged and sent to Assistant Head (Domestic).");
    } else {
      if (window.showToast) window.showToast("Failed to record security incident.", "danger");
      else alert("Failed to record security incident.");
    }
  } catch (err) {
    if (window.showToast) window.showToast("Error logging security incident.", "danger");
    else alert("Error logging security incident.");
  }
}

async function searchGateStudent() {
  const input = document.getElementById("gateSearchInput")?.value.trim();
  const container = document.getElementById("gateResultContainer");

  if (!input) {
    container.innerHTML = '<p style="text-align:center; padding:30px; opacity:0.6;">Please type a student code or name.</p>';
    return;
  }

  const headers = await getAuthHeader();
  try {
    const res = await fetch(`/api/exeat/?search=${encodeURIComponent(input)}`, { headers });
    if (!res.ok) {
      container.innerHTML = '<p style="text-align:center; padding:30px; color:#ef4444;">Search failed.</p>';
      return;
    }

    const records = await res.json();
    if (records.length === 0) {
      container.innerHTML = `
        <div style="background:rgba(239,68,68,0.1); border:1px solid rgba(239,68,68,0.3); padding:20px; border-radius:12px; text-align:center;">
          <h4 style="color:#ef4444; margin:0 0 6px 0;">❌ No Active Exeat Found</h4>
          <p style="margin:0 0 12px 0; font-size:0.9rem;">No approved exeat record matches '${input}'. Student cannot be signed out without house master clearance.</p>
        </div>
      `;
      return;
    }

    container.innerHTML = records.map(ex => {
      const statusBadge = getStatusBadge(ex.status);
      let gateAction = "";

      if (ex.status === "Approved") {
        gateAction = `<button class="btn" style="background:#3b82f6; color:white; font-size:1.1rem; padding:12px 24px;" onclick="gateSignOut(${ex.id})">🚪 SIGN OUT STUDENT</button>`;
      } else if (ex.status === "Departed" || ex.status === "Overdue") {
        gateAction = `
          <div style="display:flex; gap:8px; flex-wrap:wrap; justify-content:flex-end;">
            <button class="btn" style="background:#22c55e; color:white; font-size:1.1rem; padding:12px 24px;" onclick="gateSignIn(${ex.id})">🟩 SIGN IN STUDENT</button>
            <button class="btn" style="background:#ef4444; color:white; font-weight:700; padding:12px 16px;" onclick="reportSecurityIncident(${ex.student_id}, '${ex.student_name}')">🚨 Alert Domestic Head</button>
          </div>
        `;
      } else {
        gateAction = `
          <div style="display:flex; gap:8px; align-items:center;">
            <span style="opacity:0.7; font-style:italic;">Status: ${ex.status}</span>
            <button class="btn" style="background:#ef4444; color:white; font-size:0.85rem; padding:6px 12px;" onclick="reportSecurityIncident(${ex.student_id}, '${ex.student_name}')">🚨 Report Incident</button>
          </div>
        `;
      }

      return `
        <div class="card" style="border-left: 5px solid var(--primary); margin-bottom:16px;">
          <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:16px;">
            <div>
              <h3 style="margin:0 0 4px 0; border:none; font-size:1.2rem;">${ex.student_name} (${ex.student_code})</h3>
              <div style="font-size:0.88rem; opacity:0.8;">
                <span>Class: ${ex.class_name || 'N/A'}</span> | 
                <span>House: ${ex.house_name || 'N/A'}</span> | 
                <span>Type: <b>${ex.exeat_type} Exeat</b></span>
              </div>
              <div style="font-size:0.85rem; margin-top:6px; color:#94a3b8;">
                📍 Destination: <b>${ex.destination}</b> | Approved By: <b>${ex.approved_by_name || 'System'} (${ex.approved_by_role || 'Staff'})</b>
              </div>
            </div>
            <div>
              <div style="margin-bottom:8px; text-align:right;">${statusBadge}</div>
              ${gateAction}
            </div>
          </div>
        </div>
      `;
    }).join('');

  } catch (e) {
    container.innerHTML = '<p style="text-align:center; padding:30px; color:#ef4444;">Error searching gate records.</p>';
  }
}

window.reportSecurityIncident = reportSecurityIncident;
window.searchGateStudent = searchGateStudent;

