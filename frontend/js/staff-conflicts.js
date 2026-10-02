/**
 * staff-conflicts.js — Staffing Conflicts & Smart Workload Distribution Engine.
 * 
 * Flow:
 * 1. Upload/Audit detects teacher overload (> max weekly periods)
 * 2. Opens the "Staffing Conflicts" review modal showing each overloaded subject
 * 3. Provides a "Smart Distribute" button per subject that proposes a balanced split among qualified teachers
 * 4. Admin reviews/adjusts the proposed split
 * 5. On confirmation ("Approve & Save All Proposed Distributions"), saves the assignments to the database
 */

if (typeof window.escapeHtml !== 'function') {
  window.escapeHtml = function(str) {
    if (str === null || str === undefined) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  };
}

if (typeof window.getHeaders !== 'function') {
  window.getHeaders = function(headers = {}) {
    const token = sessionStorage.getItem('accessToken') || localStorage.getItem('accessToken');
    const h = { ...headers };
    if (token) h['Authorization'] = `Bearer ${token}`;
    const schId = sessionStorage.getItem('selectedSchoolId') || sessionStorage.getItem('school_id') || localStorage.getItem('school_id');
    if (schId && schId !== 'all' && schId !== 'system_only') {
      h['X-School-Id'] = String(parseInt(schId));
    }
    return h;
  };
}

window.staffingConflictsState = {
  semesterId: null,
  conflicts: [],
  proposals: {}, // subjectId -> proposal object
};

window.openStaffingConflictsModal = async function(preloadedConflicts, semesterId) {
  const modal = document.getElementById('staffingConflictsModal');
  if (!modal) return;

  modal.classList.add('active');
  modal.style.display = 'flex';

  if (semesterId) {
    window.staffingConflictsState.semesterId = semesterId;
  } else {
    const semSelect = document.getElementById('semesterSelect') || document.getElementById('modalSemesterSelect');
    window.staffingConflictsState.semesterId = semSelect ? (parseInt(semSelect.value) || null) : null;
  }

  if (preloadedConflicts && Array.isArray(preloadedConflicts)) {
    window.staffingConflictsState.conflicts = preloadedConflicts;
    renderStaffingConflictsUI();
  } else {
    await fetchAndRenderStaffingConflicts();
  }
};

window.closeStaffingConflictsModal = function() {
  const modal = document.getElementById('staffingConflictsModal');
  if (modal) {
    modal.classList.remove('active');
    modal.style.display = 'none';
  }
};

window.fetchAndRenderStaffingConflicts = async function() {
  const banner = document.getElementById('conflictsSummaryBanner');
  const container = document.getElementById('conflictsListContainer');
  if (banner) banner.innerHTML = '⏳ Auditing academic staff workloads and timetable scheduling capacity...';
  if (container) container.innerHTML = '';

  try {
    const semId = window.staffingConflictsState.semesterId;
    const url = `${API_BASE}/assignments/audit-staffing-conflicts${semId ? `?semester_id=${semId}` : ''}`;
    const res = await fetch(url, { headers: getHeaders() });
    if (!res.ok) throw new Error('Failed to load staffing conflict audit');
    const data = await res.json();

    window.staffingConflictsState.conflicts = data.conflicts || [];
    if (data.semester_id) window.staffingConflictsState.semesterId = data.semester_id;

    updateConflictsHeaderBadge(window.staffingConflictsState.conflicts.length);
    renderStaffingConflictsUI();
  } catch (err) {
    if (banner) {
      banner.innerHTML = `<span style="color:#f87171;">⚠️ Error checking staffing conflicts: ${err.message}</span>`;
    }
  }
};

function updateConflictsHeaderBadge(count) {
  const btn = document.getElementById('btnOpenStaffingConflicts');
  const countEl = document.getElementById('conflictsHeaderCount');
  if (countEl) countEl.textContent = count;
  if (btn) {
    btn.style.display = count > 0 ? 'inline-flex' : 'none';
  }
}

function renderStaffingConflictsUI() {
  const banner = document.getElementById('conflictsSummaryBanner');
  const container = document.getElementById('conflictsListContainer');
  const approveBtn = document.getElementById('btnApproveAllProposed');
  const conflicts = window.staffingConflictsState.conflicts || [];

  updateConflictsHeaderBadge(conflicts.length);

  if (conflicts.length === 0) {
    if (banner) {
      banner.style.background = 'rgba(16,185,129,0.12)';
      banner.style.borderColor = 'rgba(16,185,129,0.3)';
      banner.style.color = '#34d399';
      banner.innerHTML = '✔ <strong>All Staff Workloads Optimal:</strong> No capacity overflows or timetable conflicts detected. All teachers are within their designated weekly period limits.';
    }
    if (container) container.innerHTML = '<div style="text-align:center; padding:30px; color:#94a3b8;">No staffing conflicts found.</div>';
    if (approveBtn) approveBtn.style.display = 'none';
    return;
  }

  if (banner) {
    banner.style.background = 'rgba(239,68,68,0.12)';
    banner.style.borderColor = 'rgba(239,68,68,0.3)';
    banner.style.color = '#fca5a5';
    banner.innerHTML = `
      <strong>⚠️ ${conflicts.length} Overload / Scheduling Conflict${conflicts.length === 1 ? '' : 's'} Detected:</strong>
      Certain teachers have been allocated more classes/periods than physically possible or allowed by Ghana Education Service guidelines.
      Use <strong>"Smart Distribute"</strong> on each subject below to balance the workload fairly among available qualified teachers.
    `;
  }

  let html = '';
  conflicts.forEach(c => {
    const subjId = c.subject_id;
    const hasProposal = Boolean(window.staffingConflictsState.proposals[subjId]);
    const prop = window.staffingConflictsState.proposals[subjId];

    html += `
      <div class="card" style="border:1px solid rgba(239,68,68,0.3); background:rgba(30,41,59,0.7); border-radius:10px; padding:18px;">
        <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:12px; margin-bottom:12px; border-bottom:1px solid rgba(255,255,255,0.08); padding-bottom:12px;">
          <div>
            <div style="display:flex; align-items:center; gap:8px;">
              <span style="font-size:1.1rem; font-weight:700; color:#f8fafc;">${escapeHtml(c.subject_name)}</span>
              <span style="font-size:0.75rem; font-weight:700; background:rgba(239,68,68,0.2); color:#f87171; border:1px solid rgba(239,68,68,0.4); padding:2px 8px; border-radius:12px;">
                ${c.assigned_classes.length} Classes (${c.subject_periods} Periods/Wk)
              </span>
            </div>
            <div style="font-size:0.84rem; color:#94a3b8; margin-top:4px;">
              Assigned to: <strong style="color:#f1f5f9;">${escapeHtml(c.overloaded_teacher_name)}</strong>
              &nbsp;|&nbsp; Current Total Load: <strong style="color:#f87171;">${c.current_teacher_load}</strong> / ${c.max_cap} max periods
              &nbsp;(<span style="color:#ef4444; font-weight:700;">+${c.overload_periods} periods over capacity</span>)
            </div>
          </div>
          <div>
            <button class="btn primary" onclick="runSmartDistribute(${subjId})" style="display:inline-flex; align-items:center; gap:6px; background:linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%); border:none; padding:8px 14px; font-weight:700; font-size:0.84rem; border-radius:8px;">
              <span>⚡</span> Smart Distribute
            </button>
          </div>
        </div>

        <!-- Class Allocation Breakdown -->
        <div style="margin-bottom:12px;">
          <div style="font-size:0.78rem; text-transform:uppercase; letter-spacing:0.04em; color:#94a3b8; font-weight:700; margin-bottom:6px;">Current Classes Assigned:</div>
          <div style="display:flex; flex-wrap:wrap; gap:6px;">
            ${c.assigned_classes.map(cls => `
              <span style="font-size:0.78rem; font-weight:600; padding:3px 8px; background:rgba(255,255,255,0.06); border:1px solid rgba(255,255,255,0.12); border-radius:6px; color:#cbd5e1;">
                ${escapeHtml(cls.class_section_name)} (${cls.weekly_periods}p)
              </span>
            `).join('')}
          </div>
        </div>

        <!-- Qualified Available Teachers -->
        <div style="font-size:0.8rem; color:#94a3b8; margin-bottom:12px;">
          Qualified Staff on Register for ${escapeHtml(c.subject_name)}:
          <span style="color:#cbd5e1; font-weight:600;">
            ${c.qualified_teachers.length > 0 ? c.qualified_teachers.map(t => `${t.teacher_name} (Load: ${t.current_periods}/${t.max_cap}p)`).join(', ') : 'None other registered. (Add or qualify more teachers)'}
          </span>
        </div>

        <!-- Proposed Distribution Container -->
        <div id="proposal-box-${subjId}">
          ${hasProposal ? renderProposalDetailsHtml(subjId, prop) : ''}
        </div>
      </div>
    `;
  });

  if (container) container.innerHTML = html;
  checkIfAnyProposalsReady();
}

window.runSmartDistribute = async function(subjectId) {
  const box = document.getElementById(`proposal-box-${subjectId}`);
  if (box) box.innerHTML = '<div style="padding:10px; font-size:0.84rem; color:#38bdf8;">⏳ Calculating fair class split among qualified teachers...</div>';

  const semId = window.staffingConflictsState.semesterId;
  try {
    const res = await fetch(`${API_BASE}/assignments/smart-distribute-subject?subject_id=${subjectId}&semester_id=${semId}`, {
      headers: getHeaders()
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Smart distribution calculation failed');

    window.staffingConflictsState.proposals[subjectId] = data;
    if (box) box.innerHTML = renderProposalDetailsHtml(subjectId, data);
    checkIfAnyProposalsReady();
  } catch (err) {
    if (box) {
      box.innerHTML = `<div style="padding:10px; font-size:0.84rem; color:#f87171; background:rgba(239,68,68,0.1); border-radius:6px;">⚠️ ${err.message}</div>`;
    }
  }
};

function renderProposalDetailsHtml(subjectId, proposalData) {
  const teachers = proposalData.proposal || [];
  return `
    <div style="margin-top:14px; background:rgba(15,23,42,0.85); border:1px solid rgba(59,130,246,0.3); border-radius:8px; padding:14px;">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px; flex-wrap:wrap; gap:8px;">
        <strong style="color:#60a5fa; font-size:0.86rem; display:flex; align-items:center; gap:6px;">
          <span>📋</span> Proposed Smart Distribution (${proposalData.total_classes} Classes split across ${proposalData.teachers_count} Teachers)
        </strong>
        <span style="font-size:0.75rem; color:#94a3b8; font-style:italic;">Admin can inspect before saving</span>
      </div>

      <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(260px, 1fr)); gap:12px;">
        ${teachers.map((t, tIdx) => `
          <div style="background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.08); border-radius:8px; padding:12px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
              <strong style="color:#f8fafc; font-size:0.85rem;">${escapeHtml(t.teacher_name)}</strong>
              <span style="font-size:0.75rem; font-weight:700; padding:2px 6px; border-radius:4px; ${t.projected_total_periods > t.max_cap ? 'background:#ef4444; color:#fff;' : 'background:rgba(16,185,129,0.2); color:#34d399;'}">
                ${t.projected_total_periods}/${t.max_cap} Periods
              </span>
            </div>
            <div style="font-size:0.78rem; color:#94a3b8; margin-bottom:6px;">
              Allocated (${t.classes_count} Classes &bull; ${t.subject_periods}p):
            </div>
            <div style="display:flex; flex-wrap:wrap; gap:4px;">
              ${t.assigned_classes.map(c => `
                <span style="font-size:0.74rem; font-weight:600; padding:2px 6px; border-radius:4px; background:rgba(59,130,246,0.15); border:1px solid rgba(59,130,246,0.3); color:#93c5fd;">
                  ${escapeHtml(c.class_section_name)}
                </span>
              `).join('')}
            </div>
          </div>
        `).join('')}
      </div>
    </div>
  `;
}

function checkIfAnyProposalsReady() {
  const approveBtn = document.getElementById('btnApproveAllProposed');
  if (!approveBtn) return;
  const propCount = Object.keys(window.staffingConflictsState.proposals).length;
  approveBtn.style.display = propCount > 0 ? 'inline-flex' : 'none';
  approveBtn.textContent = `✔ Approve & Save ${propCount} Proposed Distribution${propCount === 1 ? '' : 's'}`;
}

window.commitApprovedDistributions = async function() {
  const proposals = window.staffingConflictsState.proposals;
  const subjectIds = Object.keys(proposals).map(id => parseInt(id));
  const semId = window.staffingConflictsState.semesterId;

  if (subjectIds.length === 0) {
    alert("Please click 'Smart Distribute' on at least one subject first.");
    return;
  }

  const items = [];
  for (const sId of subjectIds) {
    const prop = proposals[sId];
    if (prop && prop.proposal) {
      for (const t of prop.proposal) {
        for (const c of t.assigned_classes) {
          items.push({
            teacher_id: t.teacher_id,
            subject_id: sId,
            class_section_id: c.class_section_id
          });
        }
      }
    }
  }

  const ok = confirm(`Commit and save ${items.length} balanced class allocations across ${subjectIds.length} subject(s)? This will replace previous allocations for these subjects.`);
  if (!ok) return;

  const btn = document.getElementById('btnApproveAllProposed');
  if (btn) {
    btn.disabled = true;
    btn.textContent = '⏳ Saving allocations...';
  }

  try {
    const payload = {
      semester_id: semId,
      assignments: items,
      replace_subject_ids: subjectIds
    };

    const res = await fetch(`${API_BASE}/assignments/batch-confirm-assignments`, {
      method: 'POST',
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Failed to commit assignments');

    alert(`Success: ${data.message}`);
    window.staffingConflictsState.proposals = {};

    // Refresh assignments page data if available
    if (typeof loadAssignments === 'function') await loadAssignments();
    if (typeof loadPrivileges === 'function') await loadPrivileges();

    // Re-check conflicts
    await fetchAndRenderStaffingConflicts();

    // If on timetable page with autoGenModal open and conflicts resolved, automatically resume generator
    const autoGenModal = document.getElementById('autoGenModal');
    if (autoGenModal && autoGenModal.classList.contains('open') && typeof window.runAutoGenerator === 'function') {
      const remainingConflicts = window.staffingConflictsState.conflicts || [];
      if (remainingConflicts.length === 0) {
        closeStaffingConflictsModal();
        if (window.showToast) window.showToast('All conflicts resolved! Resuming timetable generation...', 'success');
        setTimeout(() => {
          window.runAutoGenerator();
        }, 600);
      }
    }
  } catch (err) {
    alert(`Could not save distributions: ${err.message}`);
  } finally {
    if (btn) {
      btn.disabled = false;
      checkIfAnyProposalsReady();
    }
  }
};
