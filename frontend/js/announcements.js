// ── Config & Auth ────────────────────────────────────────────────
const API_BASE = window.API_BASE || (window.location.origin.includes('http') ? (window.location.origin + '/api') : 'http://127.0.0.1:8000/api');
const token = localStorage.getItem('accessToken');
if (!token) window.location.href = 'auth.html';

function getHeaders(extra = {}) {
  return { 'Authorization': `Bearer ${token}`, ...extra };
}

// ── State ────────────────────────────────────────────────────────
let allNotifications = [];
let allStudents = [];
let selectedType = 'General';
let targetMode = 'all';   // 'all' | 'select'
const PAGE_SIZE = 30;
let displayCount = PAGE_SIZE;

// ── Init ─────────────────────────────────────────────────────────
async function init() {
  await Promise.all([loadNotifications(), loadStudents()]);
  setupTypeChips();
}

// ── Type Chip Selection ──────────────────────────────────────────
function setupTypeChips() {
  document.querySelectorAll('.type-chip').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.type-chip').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      selectedType = btn.dataset.type;
    });
  });
}

// ── Target Toggle ────────────────────────────────────────────────
window.setTarget = function(mode) {
  targetMode = mode;
  document.getElementById('targetAll').classList.toggle('active', mode === 'all');
  document.getElementById('targetSelect').classList.toggle('active', mode === 'select');
  document.getElementById('studentPicker').classList.toggle('visible', mode === 'select');
};

// ── Load Students for Picker ─────────────────────────────────────
async function loadStudents() {
  try {
    const res = await fetch(`${API_BASE}/students/`, { headers: getHeaders() });
    if (!res.ok) return;
    allStudents = await res.json();
    renderPicker(allStudents);
  } catch (e) {
    console.error('Error loading students:', e);
  }
}

function renderPicker(students) {
  const list = document.getElementById('pickerList');
  if (!students.length) {
    list.innerHTML = '<p style="color:var(--text-secondary);font-size:0.82rem;text-align:center;padding:10px;">No students found.</p>';
    return;
  }
  list.innerHTML = students.map(s => `
    <div class="picker-item">
      <input type="checkbox" id="pick_${s.id}" value="${s.id}" />
      <label for="pick_${s.id}">${escapeHtml(s.full_name)} <span style="color:var(--text-secondary);font-size:0.75rem;">(${s.student_code})</span></label>
    </div>
  `).join('');
}

// Picker search filter
document.addEventListener('DOMContentLoaded', () => {
  const search = document.getElementById('pickerSearch');
  if (search) {
    search.addEventListener('input', () => {
      const q = search.value.toLowerCase();
      const filtered = allStudents.filter(s =>
        s.full_name.toLowerCase().includes(q) || s.student_code.toLowerCase().includes(q)
      );
      renderPicker(filtered);
    });
  }
  init();
});

// ── Load Notifications ───────────────────────────────────────────
async function loadNotifications() {
  try {
    const res = await fetch(`${API_BASE}/notifications/`, { headers: getHeaders() });
    if (!res.ok) {
      document.getElementById('notifList').innerHTML =
        '<div class="empty-state"><p>Failed to load notifications. Are you an admin?</p></div>';
      return;
    }
    allNotifications = await res.json();
    displayCount = PAGE_SIZE;
    updateStats();
    applyFilter();
  } catch (e) {
    console.error('Error loading notifications:', e);
    document.getElementById('notifList').innerHTML =
      '<div class="empty-state"><p>Network error loading notifications.</p></div>';
  }
}

// ── Stats ────────────────────────────────────────────────────────
function updateStats() {
  const total = allNotifications.length;
  const unread = allNotifications.filter(n => !n.is_read).length;
  const uniqueStudents = new Set(allNotifications.map(n => n.student_id)).size;
  document.getElementById('statTotal').textContent = total.toLocaleString();
  document.getElementById('statUnread').textContent = unread.toLocaleString();
  document.getElementById('statStudents').textContent = uniqueStudents.toLocaleString();
}

// ── Filter & Render ──────────────────────────────────────────────
window.applyFilter = function() {
  const typeF = document.getElementById('filterType').value;
  const readF = document.getElementById('filterRead').value;
  const searchF = document.getElementById('filterSearch').value.toLowerCase();

  let filtered = allNotifications.filter(n => {
    if (typeF && n.type !== typeF) return false;
    if (readF === 'unread' && n.is_read) return false;
    if (readF === 'read' && !n.is_read) return false;
    if (searchF && !n.message.toLowerCase().includes(searchF)) return false;
    return true;
  });

  renderFeed(filtered);
};

function renderFeed(notifications) {
  const list = document.getElementById('notifList');
  const loadMoreBtn = document.getElementById('loadMoreBtn');
  const visible = notifications.slice(0, displayCount);

  if (!notifications.length) {
    list.innerHTML = `
      <div class="empty-state">
        <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" fill="currentColor" viewBox="0 0 16 16">
          <path d="M8 16a2 2 0 0 0 2-2H6a2 2 0 0 0 2 2zm.995-14.901a1 1 0 1 0-1.99 0A5.002 5.002 0 0 0 3 6c0 1.098-.5 6-2 7h14c-1.5-1-2-5.902-2-7 0-2.42-1.72-4.44-4.005-4.901z"/>
        </svg>
        <p>No notifications match your filters.</p>
      </div>`;
    loadMoreBtn.style.display = 'none';
    return;
  }

  list.innerHTML = visible.map(n => renderCard(n)).join('');
  loadMoreBtn.style.display = notifications.length > displayCount ? 'block' : 'none';
}

window.loadMore = function() {
  displayCount += PAGE_SIZE;
  applyFilter();
};

function renderCard(n) {
  const type = n.type || 'General';
  const typeClass = `type-${type.toLowerCase()}`;
  const iconMap = {
    General: '📢', Attendance: '📋', Result: '📊', Promotion: '🎓', Alert: '🚨'
  };
  const icon = iconMap[type] || '📢';
  const timeAgo = formatTime(n.created_at);
  const unreadClass = n.is_read ? '' : 'unread';

  return `
    <div class="notif-card ${unreadClass}" id="notif_${n.id}">
      <div class="notif-icon icon-${type.toLowerCase()}">${icon}</div>
      <div class="notif-body">
        <div class="notif-meta">
          <span class="notif-type ${typeClass}">${type}</span>
          <span class="notif-time">${timeAgo}</span>
        </div>
        <div class="notif-msg">${escapeHtml(n.message)}</div>
        <div class="notif-student">Student ID: <span>#${n.student_id}</span></div>
        <div class="notif-actions">
          ${!n.is_read ? `<button class="btn-sm" onclick="markRead(${n.id})">Mark read</button>` : ''}
          <button class="btn-sm danger" onclick="deleteNotif(${n.id})">Delete</button>
        </div>
      </div>
    </div>`;
}

// ── Actions ──────────────────────────────────────────────────────
window.markRead = async function(id) {
  try {
    const res = await fetch(`${API_BASE}/notifications/${id}/read`, {
      method: 'POST',
      headers: getHeaders()
    });
    if (res.ok) {
      const n = allNotifications.find(x => x.id === id);
      if (n) n.is_read = true;
      updateStats();
      applyFilter();
    }
  } catch (e) { console.error(e); }
};

window.deleteNotif = async function(id) {
  if (!confirm('Delete this notification? This cannot be undone.')) return;
  try {
    const res = await fetch(`${API_BASE}/notifications/${id}`, {
      method: 'DELETE',
      headers: getHeaders()
    });
    if (res.ok || res.status === 204) {
      allNotifications = allNotifications.filter(n => n.id !== id);
      updateStats();
      applyFilter();
    }
  } catch (e) { console.error(e); }
};

// ── Send Announcement ────────────────────────────────────────────
window.sendAnnouncement = async function() {
  const msg = document.getElementById('msgBody').value.trim();
  if (!msg) {
    showStatus('Please write a message first.', 'warning');
    return;
  }

  let studentIds = null;
  if (targetMode === 'select') {
    const checked = document.querySelectorAll('#pickerList input[type="checkbox"]:checked');
    studentIds = Array.from(checked).map(cb => parseInt(cb.value));
    if (!studentIds.length) {
      showStatus('Please select at least one student.', 'warning');
      return;
    }
  }

  const payload = {
    message: msg,
    type: selectedType,
    student_ids: studentIds
  };

  const btn = document.getElementById('sendBtn');
  btn.disabled = true;
  btn.textContent = 'Sending...';

  try {
    const res = await fetch(`${API_BASE}/notifications/broadcast`, {
      method: 'POST',
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload)
    });

    if (res.ok || res.status === 201) {
      const data = await res.json();
      showStatus(`✅ ${data.message}`, 'success');
      document.getElementById('msgBody').value = '';
      // Reload feed
      await loadNotifications();
    } else {
      const err = await res.json();
      showStatus(`❌ ${err.detail || 'Failed to send.'}`, 'danger');
    }
  } catch (e) {
    console.error(e);
    showStatus('❌ Network error. Please try again.', 'danger');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Send Announcement';
  }
};

function showStatus(msg, type = 'info') {
  const el = document.getElementById('sendStatus');
  const colors = { success: 'var(--success)', danger: 'var(--danger)', warning: 'var(--warning)', info: 'var(--text-secondary)' };
  el.style.color = colors[type] || 'var(--text-secondary)';
  el.textContent = msg;
  setTimeout(() => { el.textContent = ''; }, 5000);
}

// ── Utilities ────────────────────────────────────────────────────
function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#039;');
}

function formatTime(isoStr) {
  if (!isoStr) return '';
  const d = new Date(isoStr);
  const now = new Date();
  const diff = Math.floor((now - d) / 1000);
  if (diff < 60) return 'Just now';
  if (diff < 3600) return `${Math.floor(diff/60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff/3600)}h ago`;
  if (diff < 604800) return `${Math.floor(diff/86400)}d ago`;
  return d.toLocaleDateString();
}
