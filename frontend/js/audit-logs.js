/**
 * audit-logs.js — Institutional Forensic Audit Trail Controller
 * Strictly multi-tenant scoped activity and security event monitoring.
 */

let currentPage = 1;
const pageSize = 15;
let totalPages = 1;

document.addEventListener('DOMContentLoaded', () => {
  // Ensure user is authorized
  const token = localStorage.getItem('token');
  if (!token) {
    window.location.href = 'index.html';
    return;
  }

  // Bind filter buttons
  document.getElementById('applyFiltersBtn')?.addEventListener('click', () => {
    currentPage = 1;
    loadAuditLogs();
  });

  document.getElementById('resetFiltersBtn')?.addEventListener('click', () => {
    document.getElementById('filterAction').value = '';
    document.getElementById('filterEntityType').value = '';
    document.getElementById('filterUsername').value = '';
    document.getElementById('filterStartDate').value = '';
    document.getElementById('filterEndDate').value = '';
    document.getElementById('filterSearch').value = '';
    currentPage = 1;
    loadAuditLogs();
  });

  // Bind pagination
  document.getElementById('prevPageBtn')?.addEventListener('click', () => {
    if (currentPage > 1) {
      currentPage--;
      loadAuditLogs();
    }
  });

  document.getElementById('nextPageBtn')?.addEventListener('click', () => {
    if (currentPage < totalPages) {
      currentPage++;
      loadAuditLogs();
    }
  });

  // Bind export
  document.getElementById('exportCsvBtn')?.addEventListener('click', exportAuditLogsCsv);

  // Bind modal close
  document.getElementById('closeModalBtn')?.addEventListener('click', closeDetailsModal);
  document.getElementById('detailsModal')?.addEventListener('click', (e) => {
    if (e.target.id === 'detailsModal') closeDetailsModal();
  });

  // Initial load
  loadAuditLogs();
});

function getFilterParams() {
  const params = new URLSearchParams();
  params.set('page', currentPage);
  params.set('limit', pageSize);

  const action = document.getElementById('filterAction')?.value;
  if (action) params.set('action', action);

  const entityType = document.getElementById('filterEntityType')?.value;
  if (entityType) params.set('entity_type', entityType);

  const username = document.getElementById('filterUsername')?.value?.trim();
  if (username) params.set('actor_username', username);

  const startDate = document.getElementById('filterStartDate')?.value;
  if (startDate) params.set('start_date', startDate);

  const endDate = document.getElementById('filterEndDate')?.value;
  if (endDate) params.set('end_date', endDate);

  const search = document.getElementById('filterSearch')?.value?.trim();
  if (search) params.set('search', search);

  return params;
}

async function loadAuditLogs() {
  const tbody = document.getElementById('auditTableBody');
  if (!tbody) return;

  tbody.innerHTML = `
    <tr>
      <td colspan="6" style="text-align:center; padding:32px; color:var(--text-secondary,#94a3b8);">
        Loading audit entries...
      </td>
    </tr>
  `;

  try {
    const params = getFilterParams();
    const res = await fetch(`/api/audit/logs?${params.toString()}`, {
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      }
    });

    if (res.status === 401) {
      window.location.href = 'index.html';
      return;
    }

    if (res.status === 403) {
      tbody.innerHTML = `
        <tr>
          <td colspan="6" style="text-align:center; padding:32px; color:#ef4444; font-weight:600;">
            ⚠️ Access Denied: Administrative or leadership role required to view institutional audit trails.
          </td>
        </tr>
      `;
      return;
    }

    if (!res.ok) {
      throw new Error(`HTTP Error ${res.status}`);
    }

    const data = await res.json();
    totalPages = data.total_pages || 1;

    renderAuditTable(data.logs || []);
    updatePaginationControls(data.total || 0);

  } catch (err) {
    console.error('Failed to load audit logs:', err);
    tbody.innerHTML = `
      <tr>
        <td colspan="6" style="text-align:center; padding:32px; color:#ef4444;">
          Failed to load audit records: ${err.message}
        </td>
      </tr>
    `;
  }
}

function renderAuditTable(logs) {
  const tbody = document.getElementById('auditTableBody');
  if (!tbody) return;

  if (!logs || logs.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="6" style="text-align:center; padding:40px; color:var(--text-secondary,#94a3b8);">
          No audit entries found matching the active filters.
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = logs.map(log => {
    const badgeClass = getActionBadgeClass(log.action);
    const ts = log.created_at ? new Date(log.created_at).toLocaleString() : 'N/A';
    const actor = escapeHtml(log.actor_username || 'system');
    const role = escapeHtml(log.actor_role || 'user');
    const action = escapeHtml(log.action || 'ACTION');
    const entity = log.entity_type ? `${escapeHtml(log.entity_type)} #${escapeHtml(String(log.entity_id || ''))}` : '—';
    const device = `${escapeHtml(log.device_category || 'Desktop')} • ${escapeHtml(log.browser_name || 'Browser')}<br/><code style="font-size:0.75rem; color:var(--text-secondary,#94a3b8);">${escapeHtml(log.ip_address || '127.0.0.1')}</code>`;
    
    // Format details
    const detailsShort = log.details ? (log.details.length > 70 ? `${escapeHtml(log.details.slice(0, 68))}...` : escapeHtml(log.details)) : '—';
    const hasFullDetails = log.details && log.details.length > 70;

    return `
      <tr style="border-bottom: 1px solid var(--border-color, rgba(255,255,255,.05));">
        <td style="font-size:0.8rem; font-family:monospace; color:var(--text-secondary,#94a3b8);">${ts}</td>
        <td>
          <div style="font-weight:600; font-size:0.875rem;">${actor}</div>
          <div style="font-size:0.75rem; color:var(--text-secondary,#94a3b8);">${role}</div>
        </td>
        <td>
          <span class="badge-action ${badgeClass}">${action}</span>
        </td>
        <td style="font-size:0.85rem;">${entity}</td>
        <td style="font-size:0.8rem;">${device}</td>
        <td style="font-size:0.85rem;">
          <span>${detailsShort}</span>
          ${hasFullDetails ? `<button class="btn link-btn" style="padding:0 4px; font-size:0.75rem; color:#818cf8;" onclick="viewFullDetails(${log.id}, '${escapeForJs(log.details)}')">Inspect</button>` : ''}
        </td>
      </tr>
    `;
  }).join('');
}

function getActionBadgeClass(action) {
  if (!action) return 'info';
  const a = action.toUpperCase();
  if (a.includes('SUCCESS') || a.includes('CREATE') || a.includes('PAYMENT')) return 'success';
  if (a.includes('FAIL') || a.includes('DELETE') || a.includes('PURGE')) return 'danger';
  if (a.includes('UPDATE') || a.includes('RESET') || a.includes('CHANGE')) return 'warning';
  return 'info';
}

function updatePaginationControls(totalCount) {
  const infoEl = document.getElementById('paginationInfo');
  const prevBtn = document.getElementById('prevPageBtn');
  const nextBtn = document.getElementById('nextPageBtn');

  if (infoEl) {
    infoEl.textContent = `Showing page ${currentPage} of ${totalPages} (${totalCount} total events)`;
  }
  if (prevBtn) prevBtn.disabled = currentPage <= 1;
  if (nextBtn) nextBtn.disabled = currentPage >= totalPages;
}

window.viewFullDetails = function(logId, detailsText) {
  const modal = document.getElementById('detailsModal');
  const body = document.getElementById('modalBody');
  if (!modal || !body) return;

  try {
    const parsed = JSON.parse(detailsText);
    body.innerHTML = `<pre style="background:rgba(0,0,0,.3); padding:12px; border-radius:8px; overflow-x:auto; font-size:0.8rem;">${JSON.stringify(parsed, null, 2)}</pre>`;
  } catch (e) {
    body.innerHTML = `<div style="padding:12px; background:rgba(0,0,0,.2); border-radius:8px;">${escapeHtml(detailsText)}</div>`;
  }

  modal.style.display = 'flex';
};

function closeDetailsModal() {
  const modal = document.getElementById('detailsModal');
  if (modal) modal.style.display = 'none';
}

async function exportAuditLogsCsv() {
  try {
    const params = getFilterParams();
    params.delete('page');
    params.set('limit', '5000');

    const res = await fetch(`/api/audit/export?${params.toString()}`, {
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      }
    });

    if (!res.ok) {
      alert(`Export failed: HTTP ${res.status}`);
      return;
    }

    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `audit_logs_${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
  } catch (err) {
    alert(`Export failed: ${err.message}`);
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function escapeForJs(str) {
  if (!str) return '';
  return String(str).replace(/'/g, "\\'").replace(/"/g, '&quot;').replace(/\n/g, ' ');
}
