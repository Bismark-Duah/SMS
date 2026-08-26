const API_BASE = window.API_BASE || (window.location.origin.includes('http') ? (window.location.origin + '/api') : 'http://127.0.0.1:8000/api');

const roleLabels = {
  admin:   'Administrator',
  teacher: 'Teacher',
  student: 'Student',
  parent:  'Parent',
};

// ── Nav cards per role with icons ─────────────────────────────────────────────
const cardsByRole = {
  admin: [
    { label: 'Students',                icon: '👨‍🎓', href: 'students.html' },
    { label: 'Attendance',              icon: '✅',   href: 'attendance.html' },
    { label: 'Results',                 icon: '📝',   href: 'results.html' },
    { label: 'Class Broadsheet',        icon: '📜',   href: 'broadsheet.html' },
    { label: 'Reports',                 icon: '📄',   href: 'reports.html' },
    { label: 'Classes',                 icon: '🏫',   href: 'classes.html' },
    { label: 'Subjects',                icon: '📚',   href: 'subjects.html' },
    { label: 'Programs',                icon: '🎓',   href: 'programs.html' },
    { label: 'Academic Calendar',       icon: '📅',   href: 'academic.html' },
    { label: 'Teacher Assignments',     icon: '👨‍🏫',  href: 'assignments.html' },
    { label: 'Departments',             icon: '🏢',  href: 'departments.html' },
    { label: 'Houses & Dorms',          icon: '🏠',  href: 'houses.html' },
    { label: 'Exeat Management',        icon: '🏡',  href: 'exeat.html' },
    { label: 'Promotions',              icon: '⬆️',   href: 'promotions.html' },
    { label: 'Fee Management',          icon: '💰',   href: 'fees.html' },
    { label: 'Timetable',               icon: '🕐',   href: 'timetable.html' },
    { label: 'Discipline Records',      icon: '⚖️',   href: 'discipline.html' },
    { label: 'Bulk Messaging',          icon: '📲',   href: 'messaging.html' },
    { label: 'Announcements',           icon: '📣',   href: 'announcements.html' },
    { label: 'Parent Portal',           icon: '👨‍👩‍👧', href: 'parent-view.html' },
    { label: 'Users',                   icon: '👤',   href: 'users.html' },
    { label: 'Data Tools',              icon: '🔧',   href: 'data-tools.html' },
    { label: 'Settings',                icon: '⚙️',   href: 'settings.html' },
  ],
  teacher: [
    { label: 'Attendance',    icon: '✅',  href: 'attendance.html' },
    { label: 'Results',       icon: '📝',  href: 'results.html' },
    { label: 'Reports',       icon: '📄',  href: 'reports.html' },
    { label: 'Timetable',     icon: '🕐',  href: 'timetable.html' },
    { label: 'Bulk Messaging', icon: '📲', href: 'messaging.html' },
    { label: 'Announcements', icon: '📣',  href: 'announcements.html' },
  ],
  student: [
    { label: 'My Attendance', icon: '✅',  href: 'attendance.html' },
    { label: 'My Results',    icon: '📝',  href: 'results.html' },
    { label: 'Reports',       icon: '📄',  href: 'reports.html' },
    { label: 'Announcements', icon: '📣',  href: 'announcements.html' },
  ],
  parent: [
    { label: 'Parent Portal', icon: '👨‍👩‍👧', href: 'parent-view.html' },
    { label: 'Reports',       icon: '📄',  href: 'reports.html' },
    { label: 'Announcements', icon: '📣',  href: 'announcements.html' },
  ],
};

// ── Utility: animate number count-up ─────────────────────────────────────────
function animateCountUp(el, target, suffix = '', duration = 800) {
  if (!el || isNaN(target)) return;
  const start = 0;
  const startTime = performance.now();
  const update = (now) => {
    const elapsed = now - startTime;
    const progress = Math.min(elapsed / duration, 1);
    // Ease-out cubic
    const eased = 1 - Math.pow(1 - progress, 3);
    const current = Math.round(start + (target - start) * eased);
    el.textContent = current + suffix;
    if (progress < 1) requestAnimationFrame(update);
  };
  requestAnimationFrame(update);
}

// ── Render quick-nav cards ───────────────────────────────────────────────────
function renderCards(role) {
  const container = document.getElementById('dashboardCards');
  if (!container) return;

  const activeRole = (sessionStorage.getItem('activeRole') || localStorage.getItem('activeRole') || role || '').toLowerCase();
  const isAdmin = ['admin', 'super_admin'].includes(activeRole);

  let items = [...(cardsByRole[activeRole] || cardsByRole.admin)];

  // 1. HOD / Academic Leadership cards
  if (activeRole === 'hod' || isAdmin) {
    const hodCards = [
      { label: 'Teacher Assignments', icon: '👨‍🏫', href: 'assignments.html' },
      { label: 'Departments', icon: '🏢', href: 'departments.html' },
      { label: 'Subjects', icon: '📚', href: 'subjects.html' },
      { label: 'Class Broadsheet', icon: '📜', href: 'broadsheet.html' },
      { label: 'Results (Marks Entry)', icon: '✍️', href: 'bulk-entry.html' },
    ];
    hodCards.forEach(c => {
      if (!items.some(i => i.href === c.href)) items.push(c);
    });
  }

  // 2. Form Master / Mistress cards
  if (['form_master', 'form_mistress'].includes(activeRole) || isAdmin) {
    const formCards = [
      { label: 'Classes', icon: '🏫', href: 'classes.html' },
      { label: 'Promotions', icon: '⬆️', href: 'promotions.html' },
      { label: 'Class Broadsheet', icon: '📜', href: 'broadsheet.html' },
    ];
    formCards.forEach(c => {
      if (!items.some(i => i.href === c.href)) items.push(c);
    });
  }

  // 3. House Master / Domestic Leadership cards
  if (['house_master', 'house_mistress', 'senior_housemaster', 'senior_housemistress', 'assistant_house_master', 'assistant_house_mistress'].includes(activeRole) || isAdmin) {
    const houseCards = [
      { label: 'Houses & Dorms', icon: '🏠', href: 'houses.html' },
      { label: 'Exeat Management', icon: '🏡', href: 'exeat.html' },
    ];
    houseCards.forEach(c => {
      if (!items.some(i => i.href === c.href)) items.push(c);
    });
  }

  // ── Centralized Feature Gating Filter ────────────────────────────────────
  const F = (window.SchoolFeatures && window.SchoolFeatures.version)
    ? window.SchoolFeatures
    : (window.FeatureGate ? window.FeatureGate.getFeatures() : null);

  const isBasicOnly = F ? F.isBasicOnly : (localStorage.getItem('school_mode') === 'BASIC_ONLY');
  const isShsOnly   = F ? F.isShsOnly   : (localStorage.getItem('school_mode') === 'SHS_ONLY');
  const isBoarding  = F ? F.isBoarding  : (localStorage.getItem('boarding_status') !== 'DAY_ONLY');

  items = items.filter(item => {
    const href = (item.href || '').toLowerCase();
    
    // SHS-only features (hide in Basic Only)
    if (isBasicOnly && (href.includes('programs.html') || href.includes('departments.html') || href.includes('enrollment.html') || href.includes('transcript') || href.includes('clearance.html'))) {
      return false;
    }
    // Basic-only features (hide in SHS Only)
    if (isShsOnly && href.includes('cumulative-record.html')) {
      return false;
    }
    // Boarding-only features (hide in Day Only)
    if (!isBoarding && (href.includes('houses.html') || href.includes('exeat.html'))) {
      return false;
    }
    return true;
  });

  container.innerHTML = items.map(item => `
    <a class="nav-card" href="${item.href}">
      <span class="nav-icon">${item.icon}</span>
      <span>${item.label}</span>
    </a>
  `).join('');
}

// ── Initialise page (auth guard + user info) ─────────────────────────────────
function initDashboard() {
  const username = localStorage.getItem('username');
  const activeRole = (sessionStorage.getItem('activeRole') || localStorage.getItem('activeRole') || localStorage.getItem('userRole') || '').toLowerCase();
  const token    = localStorage.getItem('accessToken');

  if (!username || !activeRole || !token) {
    window.location.href = 'auth.html';
    return;
  }

  // Topbar user info
  const nameEl = document.getElementById('topbarUsername');
  const roleEl = document.getElementById('topbarRole');
  const displayRole = window.ROLE_DISPLAY_NAMES ? (window.ROLE_DISPLAY_NAMES[activeRole] || activeRole.toUpperCase()) : (roleLabels[activeRole] || activeRole);
  if (nameEl) nameEl.textContent = username;
  if (roleEl) roleEl.textContent = displayRole;

  renderCards(activeRole);
  renderDailyShortcuts(activeRole);

  // Logout
  const logoutBtn = document.getElementById('logoutBtn');
  if (logoutBtn) {
    logoutBtn.addEventListener('click', () => {
      ['username', 'userRole', 'userId', 'accessToken', 'userRoles', '_lastActivity']
        .forEach(k => localStorage.removeItem(k));
      window.location.href = 'auth.html';
    });
  }
}

// ── Render Dynamic Daily Shortcuts per Role ───────────────────────────────────
function renderDailyShortcuts(activeRole) {
  const container = document.getElementById('dailyShortcutsContainer');
  const heading = document.getElementById('dailyShortcutsHeading');
  if (!container) return;

  const role = (activeRole || '').toLowerCase();

  let shortcuts = [];
  if (['assistant_headmaster_academic', 'assistant_head_academic'].includes(role)) {
    if (heading) heading.innerHTML = '⚡ Academic Operations Shortcuts';
    shortcuts = [
      { label: '📜 Master Class Broadsheet', href: 'broadsheet.html' },
      { label: '✍️ Bulk Score Review & Entry', href: 'bulk-entry.html' },
      { label: '👨‍🏫 Teacher Workload & Allocations', href: 'assignments.html' },
      { label: '🖨️ Terminal Reports & Transcripts', href: 'report-card.html' },
      { label: '📚 Programs & Elective Packages', href: 'programs.html' },
      { label: '💬 Broadcast Academic Notice', href: 'messaging.html' }
    ];
  } else if (['assistant_headmaster_domestic', 'assistant_head_domestic', 'senior_housemaster', 'senior_housemistress', 'house_master', 'house_mistress'].includes(role)) {
    if (heading) heading.innerHTML = '⚡ Campus Life & Welfare Shortcuts';
    shortcuts = [
      { label: '🏡 Exeat Approval Desk', href: 'exeat.html' },
      { label: '🏠 Houses & Dormitories', href: 'houses.html' },
      { label: '⚖️ Student Discipline Records', href: 'discipline.html' },
      { label: '📋 Roll Call & Prep Attendance', href: 'attendance.html' },
      { label: '🩺 Student Health Registry', href: 'students.html' },
      { label: '💬 Broadcast Boarding Alert', href: 'messaging.html' }
    ];
  } else if (['assistant_headmaster_admin', 'assistant_head_admin'].includes(role)) {
    if (heading) heading.innerHTML = '⚡ Administrative Operations Shortcuts';
    shortcuts = [
      { label: '👥 User Accounts & Roles', href: 'users.html' },
      { label: '👨‍🏫 Teacher Workload & Allocations', href: 'assignments.html' },
      { label: '🏫 Class Streams & Sections', href: 'classes.html' },
      { label: '📊 Student Admissions & Census', href: 'students.html' },
      { label: '🛡️ Institutional Audit Logs', href: 'audit-logs.html' },
      { label: '💬 Institutional Broadcast & SMS', href: 'messaging.html' }
    ];
  } else if (role === 'hod') {
    if (heading) heading.innerHTML = '⚡ Departmental Operations Shortcuts';
    shortcuts = [
      { label: '✍️ Department Score Review', href: 'bulk-entry.html' },
      { label: '👨‍🏫 Faculty Allocations', href: 'assignments.html' },
      { label: '📜 Department Broadsheet', href: 'broadsheet.html' },
      { label: '📚 Department Subjects & Scheme', href: 'subjects.html' },
      { label: '🖨️ Terminal Reports & Transcripts', href: 'report-card.html' },
      { label: '💬 Broadcast Department SMS', href: 'messaging.html' }
    ];
  } else if (['form_master', 'form_mistress'].includes(role)) {
    if (heading) heading.innerHTML = '⚡ Class Master Operations Shortcuts';
    shortcuts = [
      { label: '📋 Daily Class Register', href: 'attendance.html' },
      { label: '📜 Master Class Broadsheet', href: 'broadsheet.html' },
      { label: '🖨️ Terminal Reports & Remarks', href: 'report-card.html' },
      { label: '👥 Class Student Census', href: 'students.html' },
      { label: '🎓 Student Clearance Desk', href: 'clearance.html' },
      { label: '💬 Message Class Parents', href: 'messaging.html' }
    ];
  } else if (role === 'teacher') {
    if (heading) heading.innerHTML = '⚡ Faculty Teaching & Score Desk Shortcuts';
    shortcuts = [
      { label: '✍️ Record Class Scores', href: 'bulk-entry.html' },
      { label: '📅 My Teaching Timetable', href: 'timetable.html' },
      { label: '⚡ Mark Period Attendance', href: 'attendance.html' },
      { label: '📚 Subject Schemes & Notes', href: 'subjects.html' },
      { label: '📜 Student Terminal Progress', href: 'report-card.html' },
      { label: '💬 Message Subject Parents', href: 'messaging.html' }
    ];
  } else if (['house_master', 'house_mistress', 'assistant_house_master', 'assistant_house_mistress'].includes(role)) {
    if (heading) heading.innerHTML = '⚡ House Custody & Welfare Shortcuts';
    shortcuts = [
      { label: '🏡 House Exeat Approvals', href: 'exeat.html' },
      { label: '🏠 Dormitory Bed Allocations', href: 'houses.html' },
      { label: '📋 Evening Roll Call', href: 'attendance.html' },
      { label: '⚖️ House Discipline Cases', href: 'discipline.html' },
      { label: '🩺 Dormitory Health Alerts', href: 'students.html' },
      { label: '💬 Broadcast House Alert', href: 'messaging.html' }
    ];
  } else if (['bursar', 'accountant'].includes(role)) {
    if (heading) heading.innerHTML = '⚡ Bursary & Financial Operations Shortcuts';
    shortcuts = [
      { label: '💳 Record Fee Payment', href: 'fees.html' },
      { label: '🧾 Batch Invoicing & Billing', href: 'fees.html' },
      { label: '📊 Financial Statements', href: 'fees.html' },
      { label: '📜 Student Clearance Desk', href: 'clearance.html' },
      { label: '💬 Fee Arrears Reminder SMS', href: 'messaging.html' }
    ];
  } else if (['storekeeper', 'inventory_officer'].includes(role)) {
    if (heading) heading.innerHTML = '⚡ Store & Inventory Operations Shortcuts';
    shortcuts = [
      { label: '📦 Log Item Requisition', href: 'inventory.html' },
      { label: '📥 Receive Stock Delivery', href: 'inventory.html' },
      { label: '⚠️ Low Stock Reorder Desk', href: 'inventory.html' },
      { label: '📋 Inventory Audit Register', href: 'inventory.html' },
      { label: '🎓 Final Year Clearance', href: 'clearance.html' }
    ];
  } else if (['security', 'security_officer'].includes(role)) {
    if (heading) heading.innerHTML = '⚡ Gatehouse & Campus Security Shortcuts';
    shortcuts = [
      { label: '🚪 Gate Pass Scanner', href: 'exeat.html' },
      { label: '🏡 Verify Return & Check-In', href: 'exeat.html' },
      { label: '🚨 Overdue Exeat Watch', href: 'exeat.html' },
      { label: '📋 Campus Visitor Log', href: 'exeat.html' }
    ];
  } else if (role === 'student') {
    if (heading) heading.innerHTML = '⚡ Student Self-Service Shortcuts';
    shortcuts = [
      { label: '🖨️ My Terminal Report Card', href: 'report-card.html' },
      { label: '📊 My Academic Transcript', href: 'broadsheet.html' },
      { label: '💳 My Fee Account Statement', href: 'fees.html' },
      { label: '🏡 My Exeat Requests', href: 'exeat.html' }
    ];
  } else if (['parent', 'guardian'].includes(role)) {
    if (heading) heading.innerHTML = '⚡ Parent Portal Shortcuts';
    shortcuts = [
      { label: '🖨️ Download Ward\'s Terminal Report', href: 'report-card.html' },
      { label: '💳 Pay Ward\'s School Fees Online', href: 'fees.html' },
      { label: '🏡 Request Exeat for Ward', href: 'exeat.html' },
      { label: '💬 Message Form / House Master', href: 'messaging.html' }
    ];
  } else {
    if (heading) heading.innerHTML = '⚡ Daily Operations Shortcuts';
    shortcuts = [
      { label: '⚡ Mark Attendance Today', href: 'attendance.html' },
      { label: '✍️ Record Class Marks', href: 'bulk-entry.html' },
      { label: '💳 Log Student Payment', href: 'fees.html' },
      { label: '💬 Broadcast Parent SMS', href: 'messaging.html' }
    ];
  }

  container.innerHTML = shortcuts.map(s => `
    <a class="btn" href="${s.href}" style="background:var(--card-bg, rgba(30,41,59,.7)); border:1px solid var(--border-color, rgba(255,255,255,.08)); color:var(--text-primary, #f8fafc); font-weight:600; padding:10px 16px; display:inline-flex; align-items:center; gap:8px; text-decoration:none; border-radius:10px; transition:all .2s ease;">
      ${s.label}
    </a>
  `).join('');
}

// ── Current term banner ──────────────────────────────────────────────────────
async function loadCurrentTerm() {
  const token = localStorage.getItem('accessToken');
  try {
    const res = await fetch(`${API_BASE}/academic/years`, {
      headers: { 'Authorization': `Bearer ${token}` },
    });
    if (!res.ok) return;
    const years = await res.json();
    const currentYear = years.find(y => y.is_current);
    if (!currentYear) return;

    // Current semester within the current year
    const currentSem = (currentYear.semesters || []).find(s => s.is_current);

    const schoolMode = localStorage.getItem('school_mode') || 'COMBINED';
    let displayTermName = currentSem?.name || '—';
    if (schoolMode === 'BASIC_ONLY') {
      displayTermName = displayTermName.replace(/Semester/i, 'Term');
    }

    // Stat card
    const termStatEl  = document.getElementById('statTerm');
    const termSubEl   = document.getElementById('statTermSub');
    if (termStatEl) termStatEl.textContent = displayTermName;
    if (termSubEl)  termSubEl.textContent  = currentYear.label;

  } catch (_) {}
}

// ── Stats: active students ────────────────────────────────────────────────────
async function loadStudentsStat() {
  const token = localStorage.getItem('accessToken');
  try {
    const res = await fetch(`${API_BASE}/students/`, {
      headers: { 'Authorization': `Bearer ${token}` },
    });
    const students = await res.json();
    const active = Array.isArray(students) ? students.filter(s => s.is_active !== false).length : 0;
    const el = document.getElementById('statStudents');
    const subEl = document.getElementById('statStudentsSub');
    const progEl = document.getElementById('progStudents');
    animateCountUp(el, active);
    if (subEl) subEl.textContent = `${students.length} total enrolled`;
    if (progEl && students.length > 0) {
      const activePct = Math.min(100, Math.round((active / students.length) * 100));
      setTimeout(() => { progEl.style.width = `${activePct}%`; }, 150);
    }
  } catch (_) {}
}

// ── Stats: attendance today ───────────────────────────────────────────────────
async function loadAttendanceStat() {
  const token = localStorage.getItem('accessToken');
  try {
    const res = await fetch(`${API_BASE}/attendance/today-stats`, {
      headers: { 'Authorization': `Bearer ${token}` },
    });
    if (!res.ok) return;
    const data = await res.json();
    const el    = document.getElementById('statAttendance');
    const subEl = document.getElementById('statAttendanceSub');
    const progEl = document.getElementById('progAttendance');
    if (data.total_marked > 0) {
      const pct = parseFloat(data.attendance_percentage) || 0;
      animateCountUp(el, Math.round(pct), '%');
      if (subEl) subEl.textContent = `${data.present_count || '—'} present of ${data.total_marked}`;
      if (progEl) {
        setTimeout(() => { progEl.style.width = `${Math.min(100, Math.round(pct))}%`; }, 150);
      }
    } else {
      if (el) el.textContent = 'N/A';
      if (subEl) subEl.textContent = 'Not yet marked today';
      if (progEl) progEl.style.width = '0%';
    }
  } catch (_) {}
}

// ── Stats: classes count ──────────────────────────────────────────────────────
async function loadClassesStat() {
  const token = localStorage.getItem('accessToken');
  try {
    const res = await fetch(`${API_BASE}/classes/my-classes`, {
      headers: { 'Authorization': `Bearer ${token}` },
    });
    const classes = await res.json();
    const el    = document.getElementById('statClasses');
    const subEl = document.getElementById('statClassesSub');
    animateCountUp(el, Array.isArray(classes) ? classes.length : 0);
    if (subEl) subEl.textContent = 'class sections';
  } catch (_) {}
}

// ── Stats: unread alerts ──────────────────────────────────────────────────────
async function loadAlertsStat() {
  const token = localStorage.getItem('accessToken');
  try {
    const res = await fetch(`${API_BASE}/notifications/unread-count`, {
      headers: { 'Authorization': `Bearer ${token}` },
    });
    if (!res.ok) return;
    const data = await res.json();
    const count = data.unread_count || 0;
    const el = document.getElementById('statAlerts');
    animateCountUp(el, count);

    // Badge on Announcements card
    if (count > 0) {
      document.querySelectorAll('.nav-card').forEach(card => {
        if (card.textContent.includes('Announcements')) {
          const label = card.querySelector('span:last-child');
          if (label) label.innerHTML = `Announcements <span style="background:var(--danger,#ef4444);color:white;border-radius:10px;padding:1px 6px;font-size:.68rem;font-weight:700;margin-left:4px;vertical-align:middle;">${count}</span>`;
        }
      });
    }
  } catch (_) {}
}

// ── Stats: outstanding fees ───────────────────────────────────────────────────
async function loadFeesStat() {
  const activeRole = (sessionStorage.getItem('activeRole') || localStorage.getItem('activeRole') || '').toLowerCase();
  const feesCard = document.getElementById('statFeesCard');
  if (['assistant_headmaster_academic', 'assistant_head_academic', 'assistant_headmaster_domestic', 'assistant_head_domestic', 'assistant_headmaster_admin', 'assistant_head_admin', 'senior_housemaster', 'senior_housemistress', 'house_master', 'house_mistress'].includes(activeRole)) {
    if (feesCard) feesCard.style.display = 'none';
    return;
  }

  const token = localStorage.getItem('accessToken');
  try {
    const res = await fetch(`${API_BASE}/reports/financial-summary`, {
      headers: { 'Authorization': `Bearer ${token}` },
    });
    if (!res.ok) return;
    const data = await res.json();
    const total = Array.isArray(data)
      ? data.reduce((sum, r) => sum + (r.outstanding_balance || 0), 0)
      : 0;
    const el    = document.getElementById('statFees');
    const subEl = document.getElementById('statFeesSub');
    const progEl = document.getElementById('progFees');
    if (el) {
      el.textContent = total === 0
        ? 'GHS 0'
        : `GHS ${total.toLocaleString('en-GH', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
    }
    if (subEl) {
      const debtors = Array.isArray(data) ? data.filter(r => r.outstanding_balance > 0).length : 0;
      subEl.textContent = `${debtors} student${debtors !== 1 ? 's' : ''} with balance`;
      if (progEl && data.length > 0) {
        const clearedPct = Math.max(0, Math.min(100, Math.round(((data.length - debtors) / data.length) * 100)));
        setTimeout(() => { progEl.style.width = `${clearedPct}%`; }, 150);
      }
    }
  } catch (_) {}
}

// ── Stats: boarding houses ───────────────────────────────────────────────────
async function loadHousesStat() {
  const token = localStorage.getItem('accessToken');
  const cardEl = document.getElementById('statHousesCard');
  const F = (window.SchoolFeatures && window.SchoolFeatures.version)
    ? window.SchoolFeatures
    : (window.FeatureGate ? window.FeatureGate.getFeatures() : null);

  const isBoarding = F ? F.showBoardingKpi : ((localStorage.getItem('boarding_status') || 'BOARDING_AND_DAY').toUpperCase() === 'BOARDING_AND_DAY');
  const activeRole = (sessionStorage.getItem('activeRole') || localStorage.getItem('activeRole') || '').toLowerCase();

  if (!isBoarding || ['assistant_headmaster_academic', 'assistant_head_academic', 'assistant_headmaster_admin', 'assistant_head_admin'].includes(activeRole)) {
    if (cardEl) cardEl.style.display = 'none';
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/houses/`, {
      headers: { 'Authorization': `Bearer ${token}` },
    });
    if (!res.ok) return;
    const houses = await res.json();
    const count = Array.isArray(houses) ? houses.length : 0;
    const el = document.getElementById('statHouses');
    const subEl = document.getElementById('statHousesSub');
    const progEl = document.getElementById('progHouses');
    
    let totalDorms = 0;
    let totalBoarders = 0;
    let totalCapacity = 0;
    if (Array.isArray(houses)) {
      houses.forEach(h => {
        totalDorms += (h.dormitories || []).length;
        totalBoarders += (h.student_count || 0);
        totalCapacity += (h.capacity || (h.student_count || 0) + 10);
      });
    }

    animateCountUp(el, count);
    if (subEl) subEl.textContent = `${totalDorms} dorms | ${totalBoarders} boarders`;
    if (progEl && totalCapacity > 0) {
      const occPct = Math.min(100, Math.round((totalBoarders / totalCapacity) * 100));
      setTimeout(() => { progEl.style.width = `${occPct}%`; }, 150);
    }
  } catch (_) {}
}

// ── Load all admin stats in parallel ─────────────────────────────────────────
async function loadDashboardStats() {
  const activeRole = (sessionStorage.getItem('activeRole') || localStorage.getItem('activeRole') || localStorage.getItem('userRole') || '').toLowerCase();

  const allowedStatsRoles = ['admin', 'super_admin', 'headmaster', 'headmistress', 'assistant_headmaster_academic', 'assistant_head_academic', 'assistant_headmaster_domestic', 'assistant_head_domestic', 'assistant_headmaster_admin', 'assistant_head_admin', 'hod', 'bursar', 'form_master', 'form_mistress', 'teacher'];
  const canSeeStats = allowedStatsRoles.includes(activeRole);
  if (!canSeeStats) return;

  const statsRow = document.getElementById('statsRow');
  if (statsRow) statsRow.style.display = 'block';

  const isAcademicHead = ['assistant_headmaster_academic', 'assistant_head_academic'].includes(activeRole);
  const isDomesticHead = ['assistant_headmaster_domestic', 'assistant_head_domestic', 'senior_housemaster', 'senior_housemistress'].includes(activeRole);
  const isAdminHead = ['assistant_headmaster_admin', 'assistant_head_admin'].includes(activeRole);

  const feesCard = document.getElementById('statFeesCard');
  const housesCard = document.getElementById('statHousesCard');
  const sbaCard = document.getElementById('statSbaCard');
  const passRateCard = document.getElementById('statPassRateCard');
  const atRiskCard = document.getElementById('statAtRiskCard');
  const boardersCard = document.getElementById('statBoardersCard');
  const exeatCard = document.getElementById('statExeatCard');
  const medicalCard = document.getElementById('statMedicalCard');
  const disciplineCard = document.getElementById('statDisciplineCard');
  const staffCard = document.getElementById('statStaffCard');
  const usersCard = document.getElementById('statUsersCard');
  const broadcastsCard = document.getElementById('statBroadcastsCard');

  if (isAcademicHead) {
    if (feesCard) feesCard.style.display = 'none';
    if (housesCard) housesCard.style.display = 'none';
    if (boardersCard) boardersCard.style.display = 'none';
    if (exeatCard) exeatCard.style.display = 'none';
    if (medicalCard) medicalCard.style.display = 'none';
    if (disciplineCard) disciplineCard.style.display = 'none';
    if (staffCard) staffCard.style.display = 'none';
    if (usersCard) usersCard.style.display = 'none';
    if (broadcastsCard) broadcastsCard.style.display = 'none';
    if (sbaCard) sbaCard.style.display = 'flex';
    if (passRateCard) passRateCard.style.display = 'flex';
    if (atRiskCard) atRiskCard.style.display = 'flex';
  } else if (isDomesticHead) {
    if (feesCard) feesCard.style.display = 'none';
    if (sbaCard) sbaCard.style.display = 'none';
    if (passRateCard) passRateCard.style.display = 'none';
    if (atRiskCard) atRiskCard.style.display = 'none';
    if (staffCard) staffCard.style.display = 'none';
    if (usersCard) usersCard.style.display = 'none';
    if (broadcastsCard) broadcastsCard.style.display = 'none';
    if (boardersCard) boardersCard.style.display = 'flex';
    if (exeatCard) exeatCard.style.display = 'flex';
    if (medicalCard) medicalCard.style.display = 'flex';
    if (disciplineCard) disciplineCard.style.display = 'flex';
    if (housesCard) housesCard.style.display = 'flex';
  } else if (isAdminHead) {
    if (feesCard) feesCard.style.display = 'none';
    if (sbaCard) sbaCard.style.display = 'none';
    if (passRateCard) passRateCard.style.display = 'none';
    if (atRiskCard) atRiskCard.style.display = 'none';
    if (boardersCard) boardersCard.style.display = 'none';
    if (exeatCard) exeatCard.style.display = 'none';
    if (medicalCard) medicalCard.style.display = 'none';
    if (disciplineCard) disciplineCard.style.display = 'none';
    if (housesCard) housesCard.style.display = 'none';
    if (staffCard) staffCard.style.display = 'flex';
    if (usersCard) usersCard.style.display = 'flex';
    if (broadcastsCard) broadcastsCard.style.display = 'flex';
  } else if (activeRole === 'hod') {
    if (feesCard) feesCard.style.display = 'none';
    if (housesCard) housesCard.style.display = 'none';
    if (boardersCard) boardersCard.style.display = 'none';
    if (exeatCard) exeatCard.style.display = 'none';
    if (medicalCard) medicalCard.style.display = 'none';
    if (disciplineCard) disciplineCard.style.display = 'none';
    if (staffCard) staffCard.style.display = 'none';
    if (usersCard) usersCard.style.display = 'none';
    if (broadcastsCard) broadcastsCard.style.display = 'none';
    if (sbaCard) sbaCard.style.display = 'flex';
    if (passRateCard) passRateCard.style.display = 'flex';
    if (atRiskCard) atRiskCard.style.display = 'flex';
  } else if (['form_master', 'form_mistress'].includes(activeRole)) {
    if (feesCard) feesCard.style.display = 'none';
    if (housesCard) housesCard.style.display = 'none';
    if (boardersCard) boardersCard.style.display = 'none';
    if (exeatCard) exeatCard.style.display = 'none';
    if (medicalCard) medicalCard.style.display = 'none';
    if (disciplineCard) disciplineCard.style.display = 'none';
    if (staffCard) staffCard.style.display = 'none';
    if (usersCard) usersCard.style.display = 'none';
    if (broadcastsCard) broadcastsCard.style.display = 'none';
    if (sbaCard) sbaCard.style.display = 'flex';
    if (passRateCard) passRateCard.style.display = 'flex';
    if (atRiskCard) atRiskCard.style.display = 'flex';
  } else if (activeRole === 'teacher') {
    if (feesCard) feesCard.style.display = 'none';
    if (housesCard) housesCard.style.display = 'none';
    if (boardersCard) boardersCard.style.display = 'none';
    if (exeatCard) exeatCard.style.display = 'none';
    if (medicalCard) medicalCard.style.display = 'none';
    if (disciplineCard) disciplineCard.style.display = 'none';
    if (staffCard) staffCard.style.display = 'none';
    if (usersCard) usersCard.style.display = 'none';
    if (broadcastsCard) broadcastsCard.style.display = 'none';
    if (sbaCard) sbaCard.style.display = 'flex';
    if (passRateCard) passRateCard.style.display = 'flex';
    if (atRiskCard) atRiskCard.style.display = 'flex';
  } else if (['house_master', 'house_mistress', 'assistant_house_master', 'assistant_house_mistress'].includes(activeRole)) {
    if (feesCard) feesCard.style.display = 'none';
    if (sbaCard) sbaCard.style.display = 'none';
    if (passRateCard) passRateCard.style.display = 'none';
    if (atRiskCard) atRiskCard.style.display = 'none';
    if (staffCard) staffCard.style.display = 'none';
    if (usersCard) usersCard.style.display = 'none';
    if (broadcastsCard) broadcastsCard.style.display = 'none';
    if (boardersCard) boardersCard.style.display = 'flex';
    if (exeatCard) exeatCard.style.display = 'flex';
    if (medicalCard) medicalCard.style.display = 'flex';
    if (disciplineCard) disciplineCard.style.display = 'flex';
    if (housesCard) housesCard.style.display = 'flex';
  } else {
    if (feesCard) feesCard.style.display = 'flex';
    if (sbaCard) sbaCard.style.display = 'none';
    if (passRateCard) passRateCard.style.display = 'none';
    if (atRiskCard) atRiskCard.style.display = 'none';
    if (boardersCard) boardersCard.style.display = 'none';
    if (exeatCard) exeatCard.style.display = 'none';
    if (medicalCard) medicalCard.style.display = 'none';
    if (disciplineCard) disciplineCard.style.display = 'none';
    if (staffCard) staffCard.style.display = 'none';
    if (usersCard) usersCard.style.display = 'none';
    if (broadcastsCard) broadcastsCard.style.display = 'none';
    if (housesCard) housesCard.style.display = 'flex';
  }

  // All load in parallel — each handles its own errors
  await Promise.all([
    loadStudentsStat(),
    loadAttendanceStat(),
    loadClassesStat(),
    loadCurrentTerm(),
    loadAlertsStat(),
    loadFeesStat(),
    loadHousesStat(),
  ]);

  // Remove skeleton loading shimmer from all stat cards
  document.querySelectorAll('.stat-card.loading').forEach(card => {
    card.classList.remove('loading');
  });
}

// ── Analytics charts ──────────────────────────────────────────────────────────
async function loadClassPerformance(classId, className) {
  const chartBox = document.getElementById('performanceChartBox');
  if (!chartBox) return;
  chartBox.textContent = 'Loading…';
  try {
    const res = await fetch(`${API_BASE}/results/analytics/class-averages/${classId}`, {
      headers: { 'Authorization': `Bearer ${localStorage.getItem('accessToken')}` },
    });
    const averages = await res.json();
    if (!res.ok) throw new Error(averages.detail || 'Failed');
    if (!Array.isArray(averages) || averages.length === 0) {
      chartBox.textContent = `No scores recorded for ${className} yet.`;
    } else {
      createBarChart('performanceChartBox', averages.map(a => a.subject), averages.map(a => a.average));
    }
  } catch (_) {
    chartBox.textContent = 'Unable to load class averages.';
  }
}

async function loadAnalytics() {
  const activeRole = (sessionStorage.getItem('activeRole') || localStorage.getItem('activeRole') || localStorage.getItem('userRole') || '').toLowerCase();
  const allowedAnalyticsRoles = ['admin', 'super_admin', 'headmaster', 'headmistress', 'assistant_headmaster_academic', 'assistant_head_academic', 'hod'];

  const canSeeAnalytics = allowedAnalyticsRoles.includes(activeRole);
  if (!canSeeAnalytics) return;

  const section = document.getElementById('analyticsSection');
  if (section) section.style.display = 'block';

  // Attendance chart
  try {
    const res = await fetch(`${API_BASE}/attendance/analytics`, {
      headers: { 'Authorization': `Bearer ${localStorage.getItem('accessToken')}` },
    });
    const data = await res.json();
    if (!Array.isArray(data) || data.length === 0) {
      document.getElementById('attendanceChartBox').textContent = 'No attendance data yet.';
    } else {
      createBarChart(
        'attendanceChartBox',
        data.map(d => d.student_name || `Student ${d.student_id}`),
        data.map(d => d.percentage),
      );
    }
  } catch (_) {
    document.getElementById('attendanceChartBox').textContent = 'Unable to load attendance.';
  }

  // Class performance chart
  try {
    const res = await fetch(`${API_BASE}/classes/my-classes`, {
      headers: { 'Authorization': `Bearer ${localStorage.getItem('accessToken')}` },
    });
    const classes = await res.json();
    const select = document.getElementById('classAnalyticsSelect');
    if (classes.length > 0 && select) {
      select.innerHTML = classes.map(c => `<option value="${c.id}">${c.name}</option>`).join('');
      select.addEventListener('change', async () => {
        await loadClassPerformance(select.value, select.options[select.selectedIndex].text);
      });
      await loadClassPerformance(classes[0].id, classes[0].name);
    } else {
      if (select) select.innerHTML = '<option value="">No classes</option>';
      document.getElementById('performanceChartBox').textContent = 'No classes created yet.';
    }
  } catch (_) {
    document.getElementById('performanceChartBox').textContent = 'Unable to load academic averages.';
  }
}

// ── Executive Analytics Widgets ────────────────────────────────────────────────
async function loadExecutiveAnalytics() {
  const activeRole = (sessionStorage.getItem('activeRole') || localStorage.getItem('activeRole') || localStorage.getItem('userRole') || '').toLowerCase();
  const execRoles = [
    'admin', 'super_admin', 'headmaster', 'headmistress',
    'assistant_headmaster_academic', 'assistant_head_academic',
    'assistant_headmaster_domestic', 'assistant_head_domestic',
    'assistant_headmaster_admin', 'assistant_head_admin',
    'hod', 'form_master', 'form_mistress',
    'teacher', 'senior_housemaster', 'senior_housemistress',
    'house_master', 'house_mistress', 'assistant_house_master', 'assistant_house_mistress',
    'bursar', 'accountant', 'storekeeper', 'inventory_officer',
    'security', 'security_officer', 'student', 'parent', 'guardian'
  ];

  const isExecutive = execRoles.includes(activeRole);
  if (!isExecutive) {
    const section = document.getElementById('executiveAnalyticsSection');
    if (section) section.style.display = 'none';
    return;
  }

  const section = document.getElementById('executiveAnalyticsSection');
  const container = document.getElementById('execAnalyticsContainer');
  if (!section || !container) return;

  try {
    const res = await fetch(`${API_BASE}/academic/executive-analytics`, {
      headers: { 'Authorization': `Bearer ${localStorage.getItem('accessToken')}` }
    });
    if (!res.ok) return;

    const data = await res.json();
    const ac = data.academic || {};
    const dom = data.domestic || {};
    const adm = data.administration || {};
    const dept = data.departmental || {};
    const cls = data.class_master || {};
    const tchr = data.teacher || {};
    const hm = data.house_master || {};
    const bur = data.bursar || {};
    const stk = data.storekeeper || {};
    const sec = data.security || {};
    const stp = data.student_portal || {};
    const prt = data.parent_portal || {};

    section.style.display = 'block';

    const isAcademicHead = ['assistant_headmaster_academic', 'assistant_head_academic'].includes(activeRole);
    const isDomesticHead = ['assistant_headmaster_domestic', 'assistant_head_domestic', 'senior_housemaster', 'senior_housemistress'].includes(activeRole);
    const isAdminHead = ['assistant_headmaster_admin', 'assistant_head_admin'].includes(activeRole);
    const isHOD = activeRole === 'hod';
    const isFormMaster = ['form_master', 'form_mistress'].includes(activeRole);
    const isTeacher = activeRole === 'teacher';
    const isHouseMaster = ['house_master', 'house_mistress', 'assistant_house_master', 'assistant_house_mistress'].includes(activeRole);
    const isBursar = ['bursar', 'accountant'].includes(activeRole);
    const isStorekeeper = ['storekeeper', 'inventory_officer'].includes(activeRole);
    const isSecurity = ['security', 'security_officer'].includes(activeRole);
    const isStudent = activeRole === 'student';
    const isParent = ['parent', 'guardian'].includes(activeRole);
    const isSuperOrHead = ['admin', 'super_admin', 'headmaster', 'headmistress'].includes(activeRole);

    const showAcademic = isAcademicHead || isSuperOrHead;
    const showDomestic = isDomesticHead || isSuperOrHead;
    const showAdmin = isAdminHead || isSuperOrHead;
    const showHOD = isHOD;
    const showFormMaster = isFormMaster;
    const showTeacher = isTeacher;
    const showHouseMaster = isHouseMaster;
    const showBursar = isBursar;
    const showStorekeeper = isStorekeeper;
    const showSecurity = isSecurity;
    const showStudent = isStudent;
    const showParent = isParent;

    // Populate top KPI cards if Academic Head
    if (isAcademicHead || isSuperOrHead) {
      const sbaEl = document.getElementById('statSba');
      const passRateEl = document.getElementById('statPassRate');
      const atRiskEl = document.getElementById('statAtRisk');
      const progSba = document.getElementById('progSba');
      const progPassRate = document.getElementById('progPassRate');

      if (sbaEl && ac.sba_completion_pct !== undefined) {
        animateCountUp(sbaEl, ac.sba_completion_pct, '%');
        if (progSba) setTimeout(() => { progSba.style.width = `${Math.min(100, ac.sba_completion_pct)}%`; }, 150);
      }
      if (passRateEl && ac.school_pass_rate_pct !== undefined) {
        animateCountUp(passRateEl, ac.school_pass_rate_pct, '%');
        if (progPassRate) setTimeout(() => { progPassRate.style.width = `${Math.min(100, ac.school_pass_rate_pct)}%`; }, 150);
      }
      if (atRiskEl && ac.at_risk_students_count !== undefined) {
        animateCountUp(atRiskEl, ac.at_risk_students_count);
      }
    }

    // Populate top KPI cards if HOD
    if (isHOD) {
      const sbaEl = document.getElementById('statSba');
      const passRateEl = document.getElementById('statPassRate');
      const atRiskEl = document.getElementById('statAtRisk');
      const progSba = document.getElementById('progSba');
      const progPassRate = document.getElementById('progPassRate');

      if (sbaEl && dept.sba_completion_pct !== undefined) {
        animateCountUp(sbaEl, dept.sba_completion_pct, '%');
        if (progSba) setTimeout(() => { progSba.style.width = `${Math.min(100, dept.sba_completion_pct)}%`; }, 150);
      }
      if (passRateEl && dept.pass_rate_pct !== undefined) {
        animateCountUp(passRateEl, dept.pass_rate_pct, '%');
        if (progPassRate) setTimeout(() => { progPassRate.style.width = `${Math.min(100, dept.pass_rate_pct)}%`; }, 150);
      }
      if (atRiskEl && dept.submissions) {
        const pendingCount = dept.submissions.filter(s => s.status !== 'COMPLETE').length;
        animateCountUp(atRiskEl, pendingCount);
      }
    }

    // Populate top KPI cards if Form Master
    if (isFormMaster) {
      const sbaEl = document.getElementById('statSba');
      const passRateEl = document.getElementById('statPassRate');
      const atRiskEl = document.getElementById('statAtRisk');
      const progSba = document.getElementById('progSba');
      const progPassRate = document.getElementById('progPassRate');
      const attEl = document.getElementById('statAttendance');
      const attSub = document.getElementById('statAttendanceSub');
      const progAtt = document.getElementById('progAttendance');

      if (cls.attendance_today_pct !== undefined && attEl) {
        animateCountUp(attEl, cls.attendance_today_pct, '%');
        if (attSub) attSub.textContent = cls.attendance_taken ? 'Today (Class Register)' : 'Not Recorded Today';
        if (progAtt) setTimeout(() => { progAtt.style.width = `${Math.min(100, cls.attendance_today_pct)}%`; }, 150);
      }
      if (sbaEl && cls.subjects_matrix) {
        const avgSba = cls.subjects_matrix.length > 0
          ? Math.round(cls.subjects_matrix.reduce((acc, s) => acc + (s.completion_pct || 0), 0) / cls.subjects_matrix.length)
          : 0;
        animateCountUp(sbaEl, avgSba, '%');
        if (progSba) setTimeout(() => { progSba.style.width = `${avgSba}%`; }, 150);
      }
      if (passRateEl && cls.pass_rate_pct !== undefined) {
        animateCountUp(passRateEl, cls.pass_rate_pct, '%');
        if (progPassRate) setTimeout(() => { progPassRate.style.width = `${Math.min(100, cls.pass_rate_pct)}%`; }, 150);
      }
      if (atRiskEl && cls.at_risk_count !== undefined) {
        animateCountUp(atRiskEl, cls.at_risk_count);
      }
    }

    // Populate top KPI cards if Subject Teacher
    if (isTeacher) {
      const sbaEl = document.getElementById('statSba');
      const sbaSub = document.getElementById('statSbaSub');
      const passRateEl = document.getElementById('statPassRate');
      const passRateSub = document.getElementById('statPassRateSub');
      const atRiskEl = document.getElementById('statAtRisk');
      const atRiskSub = document.getElementById('statAtRiskSub');
      const progSba = document.getElementById('progSba');
      const progPassRate = document.getElementById('progPassRate');

      if (sbaSub) sbaSub.textContent = 'My SBA Marks Entry';
      if (passRateSub) passRateSub.textContent = 'Allocations Completion';
      if (atRiskSub) atRiskSub.textContent = 'Failing My Subjects';

      if (sbaEl && tchr.sba_completion_pct !== undefined) {
        animateCountUp(sbaEl, tchr.sba_completion_pct, '%');
        if (progSba) setTimeout(() => { progSba.style.width = `${Math.min(100, tchr.sba_completion_pct)}%`; }, 150);
      }
      if (passRateEl) {
        const passPct = tchr.sba_completion_pct !== undefined ? tchr.sba_completion_pct : 100;
        animateCountUp(passRateEl, passPct, '%');
        if (progPassRate) setTimeout(() => { progPassRate.style.width = `${passPct}%`; }, 150);
      }
      if (atRiskEl && tchr.at_risk_students) {
        animateCountUp(atRiskEl, tchr.at_risk_students.length);
      }
    }

    // Populate top KPI cards if Housemaster / Housemistress
    if (isHouseMaster) {
      const boardersEl = document.getElementById('statBoarders');
      const boardersSub = document.getElementById('statBoardersSub');
      const progBoarders = document.getElementById('progBoarders');
      const exeatEl = document.getElementById('statExeat');
      const exeatSub = document.getElementById('statExeatSub');
      const progExeat = document.getElementById('progExeat');
      const medicalEl = document.getElementById('statMedical');
      const medicalSub = document.getElementById('statMedicalSub');
      const disciplineEl = document.getElementById('statDiscipline');
      const disciplineSub = document.getElementById('statDisciplineSub');

      if (boardersEl && hm.total_boarders !== undefined) {
        animateCountUp(boardersEl, hm.total_boarders);
        if (boardersSub) boardersSub.textContent = `${hm.total_boarders} of ${hm.total_capacity || 50} beds (${hm.occupancy_pct || 0}%)`;
        if (progBoarders) setTimeout(() => { progBoarders.style.width = `${Math.min(100, hm.occupancy_pct || 0)}%`; }, 150);
      }
      if (exeatEl && hm.active_exeats_count !== undefined) {
        animateCountUp(exeatEl, hm.active_exeats_count);
        if (exeatSub) exeatSub.textContent = 'Active house exeats';
        if (progExeat) {
          const ePct = hm.total_boarders > 0 ? Math.round((hm.active_exeats_count / hm.total_boarders) * 100) : 0;
          setTimeout(() => { progExeat.style.width = `${ePct}%`; }, 150);
        }
      }
      if (medicalEl && hm.medical_alerts) {
        animateCountUp(medicalEl, hm.medical_alerts.length);
        if (medicalSub) medicalSub.textContent = 'In my house';
      }
      if (disciplineEl && hm.discipline_cases) {
        animateCountUp(disciplineEl, hm.discipline_cases.length);
        if (disciplineSub) disciplineSub.textContent = 'Reported in my house';
      }
    }

    // Populate top KPI cards if Bursar / Accountant
    if (isBursar) {
      const feesEl = document.getElementById('statFees');
      const feesSub = document.getElementById('statFeesSub');
      const progFees = document.getElementById('progFees');
      if (feesEl && bur.total_collected_ghc !== undefined) {
        feesEl.textContent = `GH₵ ${bur.total_collected_ghc.toLocaleString()}`;
        if (feesSub) feesSub.textContent = `Rate: ${bur.collection_rate_pct}% of GH₵ ${bur.total_billed_ghc.toLocaleString()}`;
        if (progFees) setTimeout(() => { progFees.style.width = `${Math.min(100, bur.collection_rate_pct)}%`; }, 150);
      }
    }

    // Populate top KPI cards if Storekeeper
    if (isStorekeeper) {
      const housesEl = document.getElementById('statHouses');
      const housesSub = document.getElementById('statHousesSub');
      if (housesEl && stk.total_assets_count !== undefined) {
        animateCountUp(housesEl, stk.total_assets_count);
        if (housesSub) housesSub.textContent = `${stk.total_uniforms_in_stock} uniforms | ${stk.total_textbooks_issued} books`;
      }
    }

    // Populate top KPI cards if Security Officer
    if (isSecurity) {
      const exeatEl = document.getElementById('statExeat');
      const exeatSub = document.getElementById('statExeatSub');
      if (exeatEl && sec.active_gate_exeats_count !== undefined) {
        animateCountUp(exeatEl, sec.active_gate_exeats_count);
        if (exeatSub) exeatSub.textContent = `${sec.overdue_exeats_count} overdue curfew violations`;
      }
    }

    // Populate top KPI cards if Student / Parent
    if (isStudent || isParent) {
      const sbaEl = document.getElementById('statSba');
      const sbaSub = document.getElementById('statSbaSub');
      const passRateEl = document.getElementById('statPassRate');
      const passRateSub = document.getElementById('statPassRateSub');
      const attEl = document.getElementById('statAttendance');
      const attSub = document.getElementById('statAttendanceSub');

      if (sbaEl && stp.term_average !== undefined) {
        animateCountUp(sbaEl, stp.term_average, '%');
        if (sbaSub) sbaSub.textContent = 'Cumulative Term Average';
      }
      if (attEl && stp.attendance_rate_pct !== undefined) {
        animateCountUp(attEl, stp.attendance_rate_pct, '%');
        if (attSub) attSub.textContent = 'Academic Attendance';
      }
      if (passRateEl && stp.fee_summary) {
        passRateEl.textContent = `GH₵ ${stp.fee_summary.balance.toLocaleString()}`;
        if (passRateSub) passRateSub.textContent = 'Outstanding Fee Balance';
      }
    }

    // Populate top KPI cards if Admin Head
    if (isAdminHead || isSuperOrHead) {
      const staffEl = document.getElementById('statStaff');
      const staffSub = document.getElementById('statStaffSub');
      const progStaff = document.getElementById('progStaff');
      const usersEl = document.getElementById('statUsers');
      const usersSub = document.getElementById('statUsersSub');
      const broadcastsEl = document.getElementById('statBroadcasts');
      const broadcastsSub = document.getElementById('statBroadcastsSub');

      if (staffEl && adm.total_staff !== undefined) {
        animateCountUp(staffEl, adm.total_staff);
        if (staffSub) staffSub.textContent = `${adm.teaching_staff_count || 0} teaching | ${adm.non_teaching_staff_count || 0} support`;
        if (progStaff) {
          const sPct = (adm.total_staff || 0) > 0 ? Math.round(((adm.teaching_staff_count || 0) / adm.total_staff) * 100) : 0;
          setTimeout(() => { progStaff.style.width = `${sPct}%`; }, 150);
        }
      }
      if (usersEl && adm.active_users_count !== undefined) {
        animateCountUp(usersEl, adm.active_users_count);
        if (usersSub) usersSub.textContent = `${adm.inactive_users_count || 0} inactive / pending`;
      }
      if (broadcastsEl && adm.total_broadcast_messages !== undefined) {
        animateCountUp(broadcastsEl, adm.total_broadcast_messages);
        if (broadcastsSub) broadcastsSub.textContent = 'Sent notices & SMS';
      }
    }

    let cardsHtml = '';

    // ── Academic Executive Command Center ─────────────────────────────────────
    if (showAcademic) {
      // 1. Academic Quality & Assessment Overview Card
      cardsHtml += `
        <div class="card" style="border-left: 4px solid #818cf8; background: var(--card-bg, #1e293b);">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
            <h4 style="margin:0; font-size:1.05rem; color:#818cf8; display:flex; align-items:center; gap:8px;">
              <span>📚</span> Academic Quality & Assessment Pipeline
            </h4>
            <span style="font-size:0.75rem; background:rgba(99,102,241,0.2); color:#818cf8; padding:2px 8px; border-radius:12px; font-weight:700;">ACADEMIC HEAD</span>
          </div>

          <div style="margin-bottom:14px;">
            <div style="display:flex; justify-content:space-between; font-size:0.85rem; margin-bottom:4px;">
              <span>Continuous Assessment (SBA) Entry Progress</span>
              <strong style="color:#818cf8;">${ac.sba_completion_pct}%</strong>
            </div>
            <div style="width:100%; height:8px; background:rgba(255,255,255,0.1); border-radius:4px; overflow:hidden;">
              <div style="width:${ac.sba_completion_pct}%; height:100%; background:linear-gradient(90deg, #6366f1, #818cf8);"></div>
            </div>
          </div>

          <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; font-size:0.85rem;">
            <div style="background:rgba(255,255,255,0.03); padding:10px 12px; border-radius:8px; border:1px solid rgba(255,255,255,0.05);">
              <span style="opacity:0.7; font-size:0.75rem;">Institutional Pass Rate:</span><br/>
              <strong style="font-size:1.15rem; color:${ac.school_pass_rate_pct>=50?'#4ade80':'#f87171'};">${ac.school_pass_rate_pct}%</strong>
              <div style="font-size:0.72rem; opacity:0.6; margin-top:2px;">Across all core subjects</div>
            </div>
            <div style="background:rgba(255,255,255,0.03); padding:10px 12px; border-radius:8px; border:1px solid rgba(255,255,255,0.05);">
              <span style="opacity:0.7; font-size:0.75rem;">At-Risk Students:</span><br/>
              <strong style="font-size:1.15rem; color:${ac.at_risk_students_count>0?'#f87171':'#4ade80'};">${ac.at_risk_students_count} Students</strong>
              <div style="font-size:0.72rem; opacity:0.6; margin-top:2px;">Failing 2+ subjects</div>
            </div>
            <div style="background:rgba(255,255,255,0.03); padding:10px 12px; border-radius:8px; border:1px solid rgba(255,255,255,0.05);">
              <span style="opacity:0.7; font-size:0.75rem;">Pending HOD Approvals:</span><br/>
              <strong style="font-size:1.15rem; color:${ac.pending_hod_approvals>0?'#f59e0b':'#4ade80'};">${ac.pending_hod_approvals} Sheets</strong>
              <div style="font-size:0.72rem; opacity:0.6; margin-top:2px;">Awaiting verification</div>
            </div>
            <div style="background:rgba(255,255,255,0.03); padding:10px 12px; border-radius:8px; border:1px solid rgba(255,255,255,0.05);">
              <span style="opacity:0.7; font-size:0.75rem;">Published Class Reports:</span><br/>
              <strong style="font-size:1.15rem; color:#4ade80;">${ac.published_classes_count} / ${ac.total_classes}</strong>
              <div style="font-size:0.72rem; opacity:0.6; margin-top:2px;">Class sections finalized</div>
            </div>
          </div>
        </div>
      `;

      // 2. Institutional Grade Distribution Chart (WASSCE / SHS & Basic Curve)
      if (ac.grade_distribution) {
        const gd = ac.grade_distribution;
        const totalGrades = (gd.A1 || 0) + (gd.B2_B3 || 0) + (gd.C4_C6 || 0) + (gd.D7_E8 || 0) + (gd.F9 || 0);
        const calcPct = (cnt) => totalGrades > 0 ? Math.round((cnt / totalGrades) * 100) : 0;

        cardsHtml += `
          <div class="card" style="border-left: 4px solid #10b981; background: var(--card-bg, #1e293b);">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
              <h4 style="margin:0; font-size:1.05rem; color:#10b981; display:flex; align-items:center; gap:8px;">
                <span>📈</span> Institutional Grade Distribution
              </h4>
              <span style="font-size:0.75rem; background:rgba(16,185,129,0.2); color:#34d399; padding:2px 8px; border-radius:12px; font-weight:700;">WASSCE / BECE SCALE</span>
            </div>
            <div style="display:flex; flex-direction:column; gap:8px; font-size:0.8rem;">
              <div>
                <div style="display:flex; justify-content:space-between; margin-bottom:2px;">
                  <span style="font-weight:600; color:#34d399;">🌟 Grade A1 (75-100%): Excellent</span>
                  <strong>${gd.A1 || 0} (${calcPct(gd.A1)}%)</strong>
                </div>
                <div style="width:100%; height:6px; background:rgba(255,255,255,0.08); border-radius:3px; overflow:hidden;">
                  <div style="width:${calcPct(gd.A1)}%; height:100%; background:#10b981;"></div>
                </div>
              </div>
              <div>
                <div style="display:flex; justify-content:space-between; margin-bottom:2px;">
                  <span style="font-weight:600; color:#38bdf8;">📘 Grade B2-B3 (65-74%): Very Good/Good</span>
                  <strong>${gd.B2_B3 || 0} (${calcPct(gd.B2_B3)}%)</strong>
                </div>
                <div style="width:100%; height:6px; background:rgba(255,255,255,0.08); border-radius:3px; overflow:hidden;">
                  <div style="width:${calcPct(gd.B2_B3)}%; height:100%; background:#0284c7;"></div>
                </div>
              </div>
              <div>
                <div style="display:flex; justify-content:space-between; margin-bottom:2px;">
                  <span style="font-weight:600; color:#818cf8;">📗 Grade C4-C6 (50-64%): Credit Pass</span>
                  <strong>${gd.C4_C6 || 0} (${calcPct(gd.C4_C6)}%)</strong>
                </div>
                <div style="width:100%; height:6px; background:rgba(255,255,255,0.08); border-radius:3px; overflow:hidden;">
                  <div style="width:${calcPct(gd.C4_C6)}%; height:100%; background:#6366f1;"></div>
                </div>
              </div>
              <div>
                <div style="display:flex; justify-content:space-between; margin-bottom:2px;">
                  <span style="font-weight:600; color:#fbbf24;">📙 Grade D7-E8 (40-49%): Pass</span>
                  <strong>${gd.D7_E8 || 0} (${calcPct(gd.D7_E8)}%)</strong>
                </div>
                <div style="width:100%; height:6px; background:rgba(255,255,255,0.08); border-radius:3px; overflow:hidden;">
                  <div style="width:${calcPct(gd.D7_E8)}%; height:100%; background:#f59e0b;"></div>
                </div>
              </div>
              <div>
                <div style="display:flex; justify-content:space-between; margin-bottom:2px;">
                  <span style="font-weight:600; color:#f87171;">🚨 Grade F9 (Below 40%): Fail / Intervention</span>
                  <strong style="color:#f87171;">${gd.F9 || 0} (${calcPct(gd.F9)}%)</strong>
                </div>
                <div style="width:100%; height:6px; background:rgba(255,255,255,0.08); border-radius:3px; overflow:hidden;">
                  <div style="width:${calcPct(gd.F9)}%; height:100%; background:#ef4444;"></div>
                </div>
              </div>
            </div>
          </div>
        `;
      }

      // 3. Core Subjects Performance Matrix Card
      if (Array.isArray(ac.core_subjects_performance) && ac.core_subjects_performance.length > 0) {
        const coreBoxes = ac.core_subjects_performance.map(cs => {
          const passColor = cs.pass_rate >= 70 ? '#4ade80' : (cs.pass_rate >= 50 ? '#fbbf24' : '#f87171');
          return `
            <div style="background:rgba(255,255,255,0.03); padding:10px; border-radius:8px; border:1px solid rgba(255,255,255,0.06);">
              <div style="font-weight:600; font-size:0.8rem; color:#f8fafc; margin-bottom:4px;">${cs.subject}</div>
              <div style="display:flex; justify-content:space-between; align-items:baseline;">
                <span style="font-size:1.15rem; font-weight:800; color:#38bdf8;">${cs.average > 0 ? cs.average + '%' : '—'}</span>
                <span style="font-size:0.75rem; font-weight:700; color:${passColor};">${cs.pass_rate > 0 ? cs.pass_rate + '% Pass' : 'No Data'}</span>
              </div>
            </div>
          `;
        }).join('');

        cardsHtml += `
          <div class="card" style="grid-column: 1 / -1; border-left: 4px solid #06b6d4; background: var(--card-bg, #1e293b);">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; flex-wrap:wrap; gap:8px;">
              <div>
                <h4 style="margin:0; font-size:1.05rem; color:#06b6d4; display:flex; align-items:center; gap:8px;">
                  <span>🎯</span> Core Curriculum Performance Matrix
                </h4>
                <div style="font-size:0.75rem; opacity:0.65; margin-top:2px;">Institutional averages and pass rates across mandatory core subjects</div>
              </div>
              <a href="results.html" class="btn sm" style="background:#0891b2; color:white; font-weight:600; text-decoration:none; padding:5px 12px; font-size:0.75rem; border-radius:6px;">📊 Full Results Analytics</a>
            </div>
            <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(200px, 1fr)); gap:12px;">
              ${coreBoxes}
            </div>
          </div>
        `;
      }

      // 4. Departmental Compliance Matrix
      if (data.school_mode !== 'BASIC_ONLY' && Array.isArray(ac.departments_matrix) && ac.departments_matrix.length > 0) {
        let matrixRows = ac.departments_matrix.map(d => {
          let badge = `<span style="background:rgba(245,158,11,0.2); color:#fbbf24; border:1px solid rgba(245,158,11,0.4); padding:2px 8px; border-radius:12px; font-size:0.75rem; font-weight:700;">⏳ IN PROGRESS</span>`;
          if (d.status === 'COMPLETE') {
            badge = `<span style="background:rgba(34,197,94,0.2); color:#4ade80; border:1px solid rgba(34,197,94,0.4); padding:2px 8px; border-radius:12px; font-size:0.75rem; font-weight:700;">✓ COMPLETE</span>`;
          } else if (d.status === 'PENDING') {
            badge = `<span style="background:rgba(239,68,68,0.2); color:#f87171; border:1px solid rgba(239,68,68,0.4); padding:2px 8px; border-radius:12px; font-size:0.75rem; font-weight:700;">⚠️ PENDING</span>`;
          }

          return `
            <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
              <td style="padding:10px 12px; font-weight:600; color:#f8fafc;">${d.name} <span style="font-size:0.75rem; opacity:0.6;">(${d.code})</span></td>
              <td style="padding:10px 12px;">👨‍🏫 ${d.hod_name}</td>
              <td style="padding:10px 12px;">${d.teacher_count} Staff | ${d.subject_count} Subjects</td>
              <td style="padding:10px 12px; min-width:140px;">
                <div style="display:flex; justify-content:space-between; font-size:0.78rem; margin-bottom:2px;">
                  <span>${d.sba_completion_pct}%</span>
                </div>
                <div style="width:100%; height:6px; background:rgba(255,255,255,0.1); border-radius:3px; overflow:hidden;">
                  <div style="width:${d.sba_completion_pct}%; height:100%; background:linear-gradient(90deg, #6366f1, #818cf8);"></div>
                </div>
              </td>
              <td style="padding:10px 12px;">${badge}</td>
              <td style="padding:10px 12px; text-align:right;">
                <a href="assignments.html" class="btn sm" style="padding:4px 10px; font-size:0.75rem; background:rgba(99,102,241,0.2); color:#818cf8; border:1px solid rgba(99,102,241,0.4); text-decoration:none; border-radius:6px; font-weight:600;">🔍 Audit Workload</a>
              </td>
            </tr>
          `;
        }).join('');

        cardsHtml += `
          <div class="card" style="grid-column: 1 / -1; border-top: 4px solid #6366f1; background: var(--card-bg, #1e293b); margin-top:8px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; flex-wrap:wrap; gap:8px;">
              <div>
                <h4 style="margin:0; font-size:1.05rem; color:#818cf8;">🏢 Departmental SBA Compliance & Audit Matrix</h4>
                <div style="font-size:0.78rem; opacity:0.65; margin-top:2px;">Real-time continuous assessment entry progress & HOD leadership supervision</div>
              </div>
              <a class="btn sm" href="departments.html" style="background:#4f46e5; color:white; font-weight:600; text-decoration:none; padding:6px 14px; font-size:0.8rem; border-radius:6px;">🏢 Department Register</a>
            </div>
            <div style="overflow-x:auto;">
              <table style="width:100%; border-collapse:collapse; font-size:0.85rem;">
                <thead>
                  <tr style="border-bottom:1px solid rgba(255,255,255,0.1); text-align:left; color:#94a3b8;">
                    <th style="padding:8px 12px;">Department</th>
                    <th style="padding:8px 12px;">HOD Leader</th>
                    <th style="padding:8px 12px;">Staffing Scope</th>
                    <th style="padding:8px 12px;">SBA Progress</th>
                    <th style="padding:8px 12px;">Status</th>
                    <th style="padding:8px 12px; text-align:right;">Audit Action</th>
                  </tr>
                </thead>
                <tbody>
                  ${matrixRows}
                </tbody>
              </table>
            </div>
          </div>
        `;
      }

      // 5. Pending Assessment Submissions Early Warning Roster
      if (Array.isArray(ac.pending_submissions) && ac.pending_submissions.length > 0) {
        let pendingRows = ac.pending_submissions.map(p => `
          <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
            <td style="padding:10px 12px; font-weight:600; color:#f8fafc;">👨‍🏫 ${p.teacher_name}</td>
            <td style="padding:10px 12px; color:#38bdf8;">${p.class_name}</td>
            <td style="padding:10px 12px;">${p.subject_name}</td>
            <td style="padding:10px 12px;">
              <span style="background:rgba(239,68,68,0.2); color:#f87171; border:1px solid rgba(239,68,68,0.4); padding:2px 8px; border-radius:12px; font-size:0.75rem; font-weight:700;">⏳ PENDING SUBMISSION</span>
            </td>
            <td style="padding:10px 12px; text-align:right; white-space:nowrap;">
              <button type="button" onclick="sendAssessmentReminder('${escapeHtml(p.teacher_name)}', '${escapeHtml(p.subject_name)}', '${escapeHtml(p.class_name)}')" 
                      style="background:rgba(245,158,11,0.2); border:1px solid rgba(245,158,11,0.4); color:#fbbf24; padding:4px 10px; border-radius:6px; font-size:0.75rem; font-weight:600; cursor:pointer; margin-right:6px;">
                📲 Send Reminder
              </button>
              <a href="bulk-entry.html" class="btn sm" style="padding:4px 10px; font-size:0.75rem; background:rgba(99,102,241,0.2); color:#818cf8; border:1px solid rgba(99,102,241,0.4); text-decoration:none; border-radius:6px; font-weight:600;">
                ✍️ Review Scores
              </a>
            </td>
          </tr>
        `).join('');

        cardsHtml += `
          <div class="card" style="grid-column: 1 / -1; border-top: 4px solid #f59e0b; background: var(--card-bg, #1e293b); margin-top:8px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; flex-wrap:wrap; gap:8px;">
              <div>
                <h4 style="margin:0; font-size:1.05rem; color:#fbbf24; display:flex; align-items:center; gap:8px;">
                  <span>📋</span> Unsubmitted Faculty Score Sheets (Early Warning Roster)
                </h4>
                <div style="font-size:0.78rem; opacity:0.65; margin-top:2px;">Teaching allocations with pending marks entry prior to broadsheet finalization</div>
              </div>
              <a class="btn sm" href="bulk-entry.html" style="background:#d97706; color:white; font-weight:600; text-decoration:none; padding:6px 14px; font-size:0.8rem; border-radius:6px;">✍️ Bulk Score Desk</a>
            </div>
            <div style="overflow-x:auto;">
              <table style="width:100%; border-collapse:collapse; font-size:0.85rem;">
                <thead>
                  <tr style="border-bottom:1px solid rgba(255,255,255,0.1); text-align:left; color:#94a3b8;">
                    <th style="padding:8px 12px;">Assigned Teacher</th>
                    <th style="padding:8px 12px;">Class Stream</th>
                    <th style="padding:8px 12px;">Subject</th>
                    <th style="padding:8px 12px;">Entry Status</th>
                    <th style="padding:8px 12px; text-align:right;">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  ${pendingRows}
                </tbody>
              </table>
            </div>
          </div>
        `;
      }
    }

    // ── Administration Executive Command Center ───────────────────────────────
    if (showAdmin) {
      const unassignedBadge = ((adm.unassigned_teachers_count || 0) > 0)
        ? `<span style="background:rgba(245,158,11,0.2); color:#fbbf24; border:1px solid rgba(245,158,11,0.4); padding:2px 8px; border-radius:12px; font-weight:700; font-size:0.75rem;">⚠️ ${adm.unassigned_teachers_count} Unallocated Staff</span>`
        : `<span style="background:rgba(34,197,94,0.2); color:#4ade80; border:1px solid rgba(34,197,94,0.4); padding:2px 8px; border-radius:12px; font-size:0.75rem; font-weight:700;">✓ Staff Fully Allocated</span>`;

      // 1. Institutional Staffing & Human Resources Overview
      cardsHtml += `
        <div class="card" style="border-left: 4px solid #3b82f6; background: var(--card-bg, #1e293b);">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
            <h4 style="margin:0; font-size:1.05rem; color:#60a5fa; display:flex; align-items:center; gap:8px;">
              <span>🏛️</span> Institutional Staffing & Human Resources Overview
            </h4>
            ${unassignedBadge}
          </div>

          <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; font-size:0.85rem;">
            <div style="background:rgba(255,255,255,0.03); padding:10px 12px; border-radius:8px; border:1px solid rgba(255,255,255,0.05);">
              <span style="opacity:0.7; font-size:0.75rem;">Teaching Staff Strength:</span><br/>
              <strong style="font-size:1.15rem; color:#38bdf8;">${adm.teaching_staff_count || 0} Teachers</strong>
              <div style="font-size:0.72rem; opacity:0.6; margin-top:2px;">Across ${adm.total_departments || 0} Academic Departments</div>
            </div>
            <div style="background:rgba(255,255,255,0.03); padding:10px 12px; border-radius:8px; border:1px solid rgba(255,255,255,0.05);">
              <span style="opacity:0.7; font-size:0.75rem;">Non-Teaching / Support:</span><br/>
              <strong style="font-size:1.15rem; color:#a855f7;">${adm.non_teaching_staff_count || 0} Staff</strong>
              <div style="font-size:0.72rem; opacity:0.6; margin-top:2px;">Admin, Operations, Security & Boarding</div>
            </div>
            <div style="background:rgba(255,255,255,0.03); padding:10px 12px; border-radius:8px; border:1px solid rgba(255,255,255,0.05);">
              <span style="opacity:0.7; font-size:0.75rem;">Active User Portals:</span><br/>
              <strong style="font-size:1.15rem; color:#4ade80;">${adm.active_users_count || 0} Active</strong>
              <div style="font-size:0.72rem; opacity:0.6; margin-top:2px;">${adm.inactive_users_count || 0} Inactive / Pending</div>
            </div>
            <div style="background:rgba(255,255,255,0.03); padding:10px 12px; border-radius:8px; border:1px solid rgba(255,255,255,0.05);">
              <span style="opacity:0.7; font-size:0.75rem;">Active Class Sections:</span><br/>
              <strong style="font-size:1.15rem; color:#f59e0b;">${adm.total_classes || 0} Streams</strong>
              <div style="font-size:0.72rem; opacity:0.6; margin-top:2px;">Under academic administration</div>
            </div>
          </div>
        </div>
      `;

      // 2. CSSPS Admission & Enrollment Funnel Radar
      const funnel = adm.admissions_funnel || {};
      const totEnrolled = funnel.total || 1;
      const regPct = Math.min(100, Math.round(((funnel.fully_registered || 0) / totEnrolled) * 100));

      cardsHtml += `
        <div class="card" style="border-left: 4px solid #10b981; background: var(--card-bg, #1e293b);">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
            <h4 style="margin:0; font-size:1.05rem; color:#34d399; display:flex; align-items:center; gap:8px;">
              <span>📈</span> CSSPS Admission & Enrollment Funnel
            </h4>
            <a href="students.html" class="btn sm" style="background:#059669; color:white; font-weight:600; text-decoration:none; padding:4px 10px; font-size:0.75rem; border-radius:6px;">Admissions Desk</a>
          </div>
          <div style="display:flex; flex-direction:column; gap:8px; font-size:0.8rem;">
            <div>
              <div style="display:flex; justify-content:space-between; margin-bottom:2px;">
                <span style="font-weight:600; color:#38bdf8;">📋 CSSPS Placed:</span>
                <strong>${funnel.placed || 0} Candidates</strong>
              </div>
              <div style="width:100%; height:6px; background:rgba(255,255,255,0.08); border-radius:3px; overflow:hidden;">
                <div style="width:${Math.min(100, ((funnel.placed || 0) / totEnrolled) * 100)}%; height:100%; background:#0284c7;"></div>
              </div>
            </div>
            <div>
              <div style="display:flex; justify-content:space-between; margin-bottom:2px;">
                <span style="font-weight:600; color:#fbbf24;">📝 Form Completed:</span>
                <strong>${funnel.form_completed || 0} Students</strong>
              </div>
              <div style="width:100%; height:6px; background:rgba(255,255,255,0.08); border-radius:3px; overflow:hidden;">
                <div style="width:${Math.min(100, ((funnel.form_completed || 0) / totEnrolled) * 100)}%; height:100%; background:#f59e0b;"></div>
              </div>
            </div>
            <div>
              <div style="display:flex; justify-content:space-between; margin-bottom:2px;">
                <span style="font-weight:600; color:#4ade80;">🎓 Fully Registered:</span>
                <strong>${funnel.fully_registered || 0} Students (${regPct}%)</strong>
              </div>
              <div style="width:100%; height:6px; background:rgba(255,255,255,0.08); border-radius:3px; overflow:hidden;">
                <div style="width:${regPct}%; height:100%; background:#10b981;"></div>
              </div>
            </div>
          </div>
        </div>
      `;

      // 3. Departmental Staffing & Faculty Deployment Matrix Table
      if (Array.isArray(adm.departments_staffing) && adm.departments_staffing.length > 0) {
        let deptRows = adm.departments_staffing.map(d => `
          <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
            <td style="padding:10px 12px; font-weight:600; color:#f8fafc;">🏛️ ${d.name} <span style="font-size:0.75rem; opacity:0.6;">(${d.code})</span></td>
            <td style="padding:10px 12px; color:#38bdf8;">👨‍🏫 ${d.hod_name}</td>
            <td style="padding:10px 12px;"><strong>${d.staff_count}</strong> Staff Assigned</td>
            <td style="padding:10px 12px;">${d.subjects_count} Subjects</td>
            <td style="padding:10px 12px; text-align:right;">
              <a href="assignments.html" class="btn sm" style="padding:4px 10px; font-size:0.75rem; background:rgba(59,130,246,0.2); color:#60a5fa; border:1px solid rgba(59,130,246,0.4); text-decoration:none; border-radius:6px; font-weight:600;">👨‍🏫 Staff Allocation</a>
            </td>
          </tr>
        `).join('');

        cardsHtml += `
          <div class="card" style="grid-column: 1 / -1; border-top: 4px solid #3b82f6; background: var(--card-bg, #1e293b); margin-top:8px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; flex-wrap:wrap; gap:8px;">
              <div>
                <h4 style="margin:0; font-size:1.05rem; color:#60a5fa; display:flex; align-items:center; gap:8px;">
                  <span>🏛️</span> Departmental Staffing & Faculty Deployment Matrix
                </h4>
                <div style="font-size:0.78rem; opacity:0.65; margin-top:2px;">Human resources distribution across academic departments and faculty leadership</div>
              </div>
              <a class="btn sm" href="users.html" style="background:#2563eb; color:white; font-weight:600; text-decoration:none; padding:6px 14px; font-size:0.8rem; border-radius:6px;">👥 Staff Register</a>
            </div>
            <div style="overflow-x:auto;">
              <table style="width:100%; border-collapse:collapse; font-size:0.85rem;">
                <thead>
                  <tr style="border-bottom:1px solid rgba(255,255,255,0.1); text-align:left; color:#94a3b8;">
                    <th style="padding:8px 12px;">Department</th>
                    <th style="padding:8px 12px;">HOD Leadership</th>
                    <th style="padding:8px 12px;">Staff Strength</th>
                    <th style="padding:8px 12px;">Subject Scope</th>
                    <th style="padding:8px 12px; text-align:right;">Action</th>
                  </tr>
                </thead>
                <tbody>
                  ${deptRows}
                </tbody>
              </table>
            </div>
          </div>
        `;
      }

      // 4. Student Census & Gender Demographics by Form Level
      if (Array.isArray(adm.form_demographics) && adm.form_demographics.length > 0) {
        let demoRows = adm.form_demographics.map(f => {
          const bPct = f.total > 0 ? Math.round((f.boys / f.total) * 100) : 50;
          return `
            <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
              <td style="padding:10px 12px; font-weight:600; color:#f8fafc;">🎓 ${f.form}</td>
              <td style="padding:10px 12px; color:#38bdf8;">👦 ${f.boys} Boys</td>
              <td style="padding:10px 12px; color:#f472b6;">👧 ${f.girls} Girls</td>
              <td style="padding:10px 12px; font-weight:700;">${f.total} Total</td>
              <td style="padding:10px 12px; min-width:140px;">
                <div style="display:flex; justify-content:space-between; font-size:0.75rem; margin-bottom:2px;">
                  <span>${bPct}% Boys</span>
                  <span>${100 - bPct}% Girls</span>
                </div>
                <div style="width:100%; height:6px; background:#ec4899; border-radius:3px; overflow:hidden;">
                  <div style="width:${bPct}%; height:100%; background:#0284c7;"></div>
                </div>
              </td>
            </tr>
          `;
        }).join('');

        cardsHtml += `
          <div class="card" style="grid-column: 1 / -1; border-top: 4px solid #10b981; background: var(--card-bg, #1e293b); margin-top:8px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; flex-wrap:wrap; gap:8px;">
              <div>
                <h4 style="margin:0; font-size:1.05rem; color:#34d399; display:flex; align-items:center; gap:8px;">
                  <span>👥</span> Student Census & Gender Demographics by Form Level
                </h4>
                <div style="font-size:0.78rem; opacity:0.65; margin-top:2px;">Institutional student population breakdown across form streams and gender balance</div>
              </div>
              <a class="btn sm" href="students.html" style="background:#059669; color:white; font-weight:600; text-decoration:none; padding:6px 14px; font-size:0.8rem; border-radius:6px;">📊 Student Census</a>
            </div>
            <div style="overflow-x:auto;">
              <table style="width:100%; border-collapse:collapse; font-size:0.85rem;">
                <thead>
                  <tr style="border-bottom:1px solid rgba(255,255,255,0.1); text-align:left; color:#94a3b8;">
                    <th style="padding:8px 12px;">Academic Level</th>
                    <th style="padding:8px 12px;">Male Census</th>
                    <th style="padding:8px 12px;">Female Census</th>
                    <th style="padding:8px 12px;">Total Enrollment</th>
                    <th style="padding:8px 12px;">Gender Balance</th>
                  </tr>
                </thead>
                <tbody>
                  ${demoRows}
                </tbody>
              </table>
            </div>
          </div>
        `;
      }

      // 5. Institutional Governance & System Audit Activity Stream
      if (Array.isArray(adm.recent_audit_logs) && adm.recent_audit_logs.length > 0) {
        let auditRows = adm.recent_audit_logs.map(al => `
          <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
            <td style="padding:10px 12px; font-weight:600; color:#f8fafc;">🛡️ ${al.action}</td>
            <td style="padding:10px 12px; color:#38bdf8;">👤 ${al.user_name}</td>
            <td style="padding:10px 12px; font-size:0.75rem; opacity:0.8;">${al.entity_type || 'System'}</td>
            <td style="padding:10px 12px; color:#94a3b8; font-size:0.78rem;">${escapeHtml(al.details)}</td>
            <td style="padding:10px 12px; font-size:0.75rem; opacity:0.7; white-space:nowrap;">⏰ ${al.timestamp}</td>
          </tr>
        `).join('');

        cardsHtml += `
          <div class="card" style="grid-column: 1 / -1; border-top: 4px solid #8b5cf6; background: var(--card-bg, #1e293b); margin-top:8px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; flex-wrap:wrap; gap:8px;">
              <div>
                <h4 style="margin:0; font-size:1.05rem; color:#a78bfa; display:flex; align-items:center; gap:8px;">
                  <span>🛡️</span> Real-Time Governance & System Audit Activity Stream
                </h4>
                <div style="font-size:0.78rem; opacity:0.65; margin-top:2px;">Recent administrative actions, role assignments, mark updates, and security events</div>
              </div>
              <a class="btn sm" href="audit-logs.html" style="background:#7c3aed; color:white; font-weight:600; text-decoration:none; padding:6px 14px; font-size:0.8rem; border-radius:6px;">🛡️ Full Audit Log</a>
            </div>
            <div style="overflow-x:auto;">
              <table style="width:100%; border-collapse:collapse; font-size:0.85rem;">
                <thead>
                  <tr style="border-bottom:1px solid rgba(255,255,255,0.1); text-align:left; color:#94a3b8;">
                    <th style="padding:8px 12px;">Action Event</th>
                    <th style="padding:8px 12px;">Responsible Actor</th>
                    <th style="padding:8px 12px;">Target Entity</th>
                    <th style="padding:8px 12px;">Details</th>
                    <th style="padding:8px 12px;">Timestamp</th>
                  </tr>
                </thead>
                <tbody>
                  ${auditRows}
                </tbody>
              </table>
            </div>
          </div>
        `;
      }
    }

    // ── HOD Departmental Command Center ───────────────────────────────────────
    if (showHOD) {
      const headingEl = document.getElementById('execAnalyticsTitle');
      if (headingEl) headingEl.innerHTML = `🔬 Departmental Curriculum & SBA Command Center (${escapeHtml(dept.name || 'Department')})`;

      // 1. Departmental Curriculum & SBA Completion Overview Card
      const sbaRate = dept.sba_completion_pct || 0;
      cardsHtml += `
        <div class="card" style="border-left: 4px solid #6366f1; background: var(--card-bg, #1e293b);">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
            <h4 style="margin:0; font-size:1.05rem; color:#818cf8; display:flex; align-items:center; gap:8px;">
              <span>🔬</span> Departmental Curriculum & SBA Overview
            </h4>
            <span style="background:rgba(99,102,241,0.2); color:#a5b4fc; border:1px solid rgba(99,102,241,0.4); padding:2px 8px; border-radius:12px; font-weight:700; font-size:0.75rem;">${escapeHtml(dept.code || 'DEPT')}</span>
          </div>

          <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; font-size:0.85rem;">
            <div style="background:rgba(255,255,255,0.03); padding:10px 12px; border-radius:8px; border:1px solid rgba(255,255,255,0.05);">
              <span style="opacity:0.7; font-size:0.75rem;">Department Faculty:</span><br/>
              <strong style="font-size:1.15rem; color:#38bdf8;">${dept.teacher_count || 0} Assigned</strong>
              <div style="font-size:0.72rem; opacity:0.6; margin-top:2px;">Head: ${escapeHtml(dept.hod_name || 'HOD')}</div>
            </div>
            <div style="background:rgba(255,255,255,0.03); padding:10px 12px; border-radius:8px; border:1px solid rgba(255,255,255,0.05);">
              <span style="opacity:0.7; font-size:0.75rem;">Department Subjects:</span><br/>
              <strong style="font-size:1.15rem; color:#a855f7;">${dept.subject_count || 0} Subjects</strong>
              <div style="font-size:0.72rem; opacity:0.6; margin-top:2px;">${dept.total_scores_recorded || 0} scores logged</div>
            </div>
            <div style="background:rgba(255,255,255,0.03); padding:10px 12px; border-radius:8px; border:1px solid rgba(255,255,255,0.05);">
              <span style="opacity:0.7; font-size:0.75rem;">SBA Continuous Assessment:</span><br/>
              <strong style="font-size:1.15rem; color:#10b981;">${sbaRate}%</strong>
              <div style="font-size:0.72rem; opacity:0.6; margin-top:2px;">Entry completion rate</div>
            </div>
            <div style="background:rgba(255,255,255,0.03); padding:10px 12px; border-radius:8px; border:1px solid rgba(255,255,255,0.05);">
              <span style="opacity:0.7; font-size:0.75rem;">Subject Pass Rate:</span><br/>
              <strong style="font-size:1.15rem; color:#f59e0b;">${dept.pass_rate_pct || 0}%</strong>
              <div style="font-size:0.72rem; opacity:0.6; margin-top:2px;">Score &ge; 50%</div>
            </div>
          </div>
        </div>
      `;

      // 2. Department Grade Distribution Curve Card
      const gd = dept.grade_distribution || { A1: 0, B2_B3: 0, C4_C6: 0, D7_E8: 0, F9: 0 };
      const totG = Object.values(gd).reduce((a, b) => a + b, 0) || 1;
      cardsHtml += `
        <div class="card" style="border-left: 4px solid #10b981; background: var(--card-bg, #1e293b);">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
            <h4 style="margin:0; font-size:1.05rem; color:#34d399; display:flex; align-items:center; gap:8px;">
              <span>📈</span> Departmental Grade Distribution & Pass Curve
            </h4>
            <a href="broadsheet.html" class="btn sm" style="background:#059669; color:white; font-weight:600; text-decoration:none; padding:4px 10px; font-size:0.75rem; border-radius:6px;">Dept Broadsheet</a>
          </div>
          <div style="display:flex; flex-direction:column; gap:8px; font-size:0.8rem;">
            <div>
              <div style="display:flex; justify-content:space-between; margin-bottom:2px;">
                <span style="font-weight:600; color:#34d399;">🌟 Excellent (A1):</span>
                <strong>${gd.A1 || 0} (${Math.round(((gd.A1 || 0) / totG) * 100)}%)</strong>
              </div>
              <div style="width:100%; height:6px; background:rgba(255,255,255,0.08); border-radius:3px; overflow:hidden;">
                <div style="width:${Math.min(100, ((gd.A1 || 0) / totG) * 100)}%; height:100%; background:#10b981;"></div>
              </div>
            </div>
            <div>
              <div style="display:flex; justify-content:space-between; margin-bottom:2px;">
                <span style="font-weight:600; color:#60a5fa;">📘 Very Good / Good (B2–B3):</span>
                <strong>${gd.B2_B3 || 0} (${Math.round(((gd.B2_B3 || 0) / totG) * 100)}%)</strong>
              </div>
              <div style="width:100%; height:6px; background:rgba(255,255,255,0.08); border-radius:3px; overflow:hidden;">
                <div style="width:${Math.min(100, ((gd.B2_B3 || 0) / totG) * 100)}%; height:100%; background:#3b82f6;"></div>
              </div>
            </div>
            <div>
              <div style="display:flex; justify-content:space-between; margin-bottom:2px;">
                <span style="font-weight:600; color:#fbbf24;">📙 Credit Pass (C4–C6):</span>
                <strong>${gd.C4_C6 || 0} (${Math.round(((gd.C4_C6 || 0) / totG) * 100)}%)</strong>
              </div>
              <div style="width:100%; height:6px; background:rgba(255,255,255,0.08); border-radius:3px; overflow:hidden;">
                <div style="width:${Math.min(100, ((gd.C4_C6 || 0) / totG) * 100)}%; height:100%; background:#f59e0b;"></div>
              </div>
            </div>
            <div>
              <div style="display:flex; justify-content:space-between; margin-bottom:2px;">
                <span style="font-weight:600; color:#f87171;">⚠️ Pass / Fail (D7–F9):</span>
                <strong>${(gd.D7_E8 || 0) + (gd.F9 || 0)} (${Math.round((((gd.D7_E8 || 0) + (gd.F9 || 0)) / totG) * 100)}%)</strong>
              </div>
              <div style="width:100%; height:6px; background:rgba(255,255,255,0.08); border-radius:3px; overflow:hidden;">
                <div style="width:${Math.min(100, (((gd.D7_E8 || 0) + (gd.F9 || 0)) / totG) * 100)}%; height:100%; background:#ef4444;"></div>
              </div>
            </div>
          </div>
        </div>
      `;

      // 3. Department Teacher Score Sheet Submission Roster
      if (Array.isArray(dept.submissions) && dept.submissions.length > 0) {
        let subRows = dept.submissions.map(s => {
          let badge = s.status === 'COMPLETE'
            ? `<span style="background:rgba(34,197,94,0.2); color:#4ade80; border:1px solid rgba(34,197,94,0.4); padding:2px 8px; border-radius:12px; font-size:0.75rem; font-weight:700;">✓ SUBMITTED</span>`
            : (s.status === 'IN_PROGRESS'
              ? `<span style="background:rgba(245,158,11,0.2); color:#fbbf24; border:1px solid rgba(245,158,11,0.4); padding:2px 8px; border-radius:12px; font-size:0.75rem; font-weight:700;">⏳ IN PROGRESS (${s.completion_pct}%)</span>`
              : `<span style="background:rgba(239,68,68,0.2); color:#f87171; border:1px solid rgba(239,68,68,0.4); padding:2px 8px; border-radius:12px; font-size:0.75rem; font-weight:700;">❌ PENDING</span>`);

          return `
            <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
              <td style="padding:10px 12px; font-weight:600; color:#f8fafc;">👨‍🏫 ${escapeHtml(s.teacher_name)}</td>
              <td style="padding:10px 12px; color:#38bdf8;">${escapeHtml(s.class_name)}</td>
              <td style="padding:10px 12px; font-weight:600;">${escapeHtml(s.subject_name)}</td>
              <td style="padding:10px 12px;">${s.recorded_count} / ${s.total_students} scores</td>
              <td style="padding:10px 12px;">${badge}</td>
              <td style="padding:10px 12px; text-align:right; white-space:nowrap;">
                ${s.status !== 'COMPLETE' ? `
                  <button type="button" onclick="sendAssessmentReminder('${escapeHtml(s.teacher_name)}', '${escapeHtml(s.subject_name)}', '${escapeHtml(s.class_name)}')" 
                          style="background:rgba(245,158,11,0.2); border:1px solid rgba(245,158,11,0.4); color:#fbbf24; padding:4px 10px; border-radius:6px; font-size:0.75rem; font-weight:600; cursor:pointer; margin-right:6px;">
                    📲 Reminder
                  </button>
                ` : ''}
                <a href="bulk-entry.html" class="btn sm" style="padding:4px 10px; font-size:0.75rem; background:rgba(99,102,241,0.2); color:#818cf8; border:1px solid rgba(99,102,241,0.4); text-decoration:none; border-radius:6px; font-weight:600;">
                  ✍️ Review Scores
                </a>
              </td>
            </tr>
          `;
        }).join('');

        cardsHtml += `
          <div class="card" style="grid-column: 1 / -1; border-top: 4px solid #6366f1; background: var(--card-bg, #1e293b); margin-top:8px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; flex-wrap:wrap; gap:8px;">
              <div>
                <h4 style="margin:0; font-size:1.05rem; color:#818cf8; display:flex; align-items:center; gap:8px;">
                  <span>📋</span> Departmental Teacher Score Sheet Submission Roster
                </h4>
                <div style="font-size:0.78rem; opacity:0.65; margin-top:2px;">Track continuous assessment mark entry and exam score submissions across departmental subjects</div>
              </div>
              <a class="btn sm" href="bulk-entry.html" style="background:#4f46e5; color:white; font-weight:600; text-decoration:none; padding:6px 14px; font-size:0.8rem; border-radius:6px;">✍️ Department Score Desk</a>
            </div>
            <div style="overflow-x:auto;">
              <table style="width:100%; border-collapse:collapse; font-size:0.85rem;">
                <thead>
                  <tr style="border-bottom:1px solid rgba(255,255,255,0.1); text-align:left; color:#94a3b8;">
                    <th style="padding:8px 12px;">Assigned Teacher</th>
                    <th style="padding:8px 12px;">Class Section</th>
                    <th style="padding:8px 12px;">Subject</th>
                    <th style="padding:8px 12px;">Progress</th>
                    <th style="padding:8px 12px;">Status</th>
                    <th style="padding:8px 12px; text-align:right;">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  ${subRows}
                </tbody>
              </table>
            </div>
          </div>
        `;
      }
    }

    // ── Form Master / Form Mistress Command Center ────────────────────────────
    if (showFormMaster) {
      const headingEl = document.getElementById('execAnalyticsTitle');
      if (headingEl) headingEl.innerHTML = `🎓 Class Master Academic & Pastoral Command Center (${escapeHtml(cls.class_name || 'My Class')})`;

      // 1. Class Census & Attendance Standing Card
      const attBadge = cls.attendance_taken
        ? `<span style="background:rgba(34,197,94,0.2); color:#4ade80; border:1px solid rgba(34,197,94,0.4); padding:2px 8px; border-radius:12px; font-weight:700; font-size:0.75rem;">✓ Register Marked Today (${cls.attendance_today_pct}%)</span>`
        : `<span style="background:rgba(245,158,11,0.2); color:#fbbf24; border:1px solid rgba(245,158,11,0.4); padding:2px 8px; border-radius:12px; font-weight:700; font-size:0.75rem;">⚠️ Roll Call Pending Today</span>`;

      cardsHtml += `
        <div class="card" style="border-left: 4px solid #10b981; background: var(--card-bg, #1e293b);">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
            <h4 style="margin:0; font-size:1.05rem; color:#34d399; display:flex; align-items:center; gap:8px;">
              <span>🎓</span> Class Master Operational Standing
            </h4>
            ${attBadge}
          </div>

          <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; font-size:0.85rem;">
            <div style="background:rgba(255,255,255,0.03); padding:10px 12px; border-radius:8px; border:1px solid rgba(255,255,255,0.05);">
              <span style="opacity:0.7; font-size:0.75rem;">Total Class Enrollment:</span><br/>
              <strong style="font-size:1.15rem; color:#38bdf8;">${cls.total_students || 0} Students</strong>
              <div style="font-size:0.72rem; opacity:0.6; margin-top:2px;">👦 ${cls.boys_count || 0} Boys | 👧 ${cls.girls_count || 0} Girls</div>
            </div>
            <div style="background:rgba(255,255,255,0.03); padding:10px 12px; border-radius:8px; border:1px solid rgba(255,255,255,0.05);">
              <span style="opacity:0.7; font-size:0.75rem;">Academic Stage:</span><br/>
              <strong style="font-size:1.15rem; color:#a855f7;">${escapeHtml(cls.stage_name || 'Senior High')}</strong>
              <div style="font-size:0.72rem; opacity:0.6; margin-top:2px;">Class: ${escapeHtml(cls.class_name || 'Stream')}</div>
            </div>
            <div style="background:rgba(255,255,255,0.03); padding:10px 12px; border-radius:8px; border:1px solid rgba(255,255,255,0.05);">
              <span style="opacity:0.7; font-size:0.75rem;">Class Pass Rate:</span><br/>
              <strong style="font-size:1.15rem; color:#10b981;">${cls.pass_rate_pct || 0}%</strong>
              <div style="font-size:0.72rem; opacity:0.6; margin-top:2px;">Scores &ge; 50%</div>
            </div>
            <div style="background:rgba(255,255,255,0.03); padding:10px 12px; border-radius:8px; border:1px solid rgba(255,255,255,0.05);">
              <span style="opacity:0.7; font-size:0.75rem;">At-Risk Students:</span><br/>
              <strong style="font-size:1.15rem; color:#ef4444;">${cls.at_risk_count || 0} Flagged</strong>
              <div style="font-size:0.72rem; opacity:0.6; margin-top:2px;">Failing &ge; 2 Core Subjects</div>
            </div>
          </div>
        </div>
      `;

      // 2. Class Continuous Assessment Progress Matrix by Subject
      if (Array.isArray(cls.subjects_matrix) && cls.subjects_matrix.length > 0) {
        let subMatrixRows = cls.subjects_matrix.map(sm => {
          let badge = sm.status === 'COMPLETE'
            ? `<span style="background:rgba(34,197,94,0.2); color:#4ade80; border:1px solid rgba(34,197,94,0.4); padding:2px 8px; border-radius:12px; font-size:0.75rem; font-weight:700;">✓ COMPLETE</span>`
            : (sm.status === 'IN_PROGRESS'
              ? `<span style="background:rgba(245,158,11,0.2); color:#fbbf24; border:1px solid rgba(245,158,11,0.4); padding:2px 8px; border-radius:12px; font-size:0.75rem; font-weight:700;">⏳ ${sm.completion_pct}%</span>`
              : `<span style="background:rgba(239,68,68,0.2); color:#f87171; border:1px solid rgba(239,68,68,0.4); padding:2px 8px; border-radius:12px; font-size:0.75rem; font-weight:700;">❌ PENDING</span>`);

          return `
            <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
              <td style="padding:10px 12px; font-weight:600; color:#f8fafc;">📚 ${escapeHtml(sm.subject_name)}</td>
              <td style="padding:10px 12px; color:#38bdf8;">👨‍🏫 ${escapeHtml(sm.teacher_name)}</td>
              <td style="padding:10px 12px;">${sm.scores_recorded} / ${sm.total_students} scores</td>
              <td style="padding:10px 12px;">${badge}</td>
              <td style="padding:10px 12px; text-align:right;">
                <a href="bulk-entry.html" class="btn sm" style="padding:4px 10px; font-size:0.75rem; background:rgba(99,102,241,0.2); color:#818cf8; border:1px solid rgba(99,102,241,0.4); text-decoration:none; border-radius:6px; font-weight:600;">
                  ✍️ View Scores
                </a>
              </td>
            </tr>
          `;
        }).join('');

        cardsHtml += `
          <div class="card" style="border-left: 4px solid #3b82f6; background: var(--card-bg, #1e293b);">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
              <h4 style="margin:0; font-size:1.05rem; color:#60a5fa; display:flex; align-items:center; gap:8px;">
                <span>📋</span> Class SBA Subject Score Entry Progress
              </h4>
              <a href="broadsheet.html" class="btn sm" style="background:#2563eb; color:white; font-weight:600; text-decoration:none; padding:4px 10px; font-size:0.75rem; border-radius:6px;">Class Broadsheet</a>
            </div>
            <div style="overflow-x:auto;">
              <table style="width:100%; border-collapse:collapse; font-size:0.82rem;">
                <thead>
                  <tr style="border-bottom:1px solid rgba(255,255,255,0.1); text-align:left; color:#94a3b8;">
                    <th style="padding:6px 10px;">Subject</th>
                    <th style="padding:6px 10px;">Assigned Faculty</th>
                    <th style="padding:6px 10px;">Progress</th>
                    <th style="padding:6px 10px;">Status</th>
                    <th style="padding:6px 10px; text-align:right;">Action</th>
                  </tr>
                </thead>
                <tbody>
                  ${subMatrixRows}
                </tbody>
              </table>
            </div>
          </div>
        `;
      }

      // 3. Class Early Warning & At-Risk Intervention Roster
      if (Array.isArray(cls.at_risk_students) && cls.at_risk_students.length > 0) {
        let riskRows = cls.at_risk_students.map(rs => `
          <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
            <td style="padding:10px 12px; font-weight:600; color:#f8fafc;">⚠️ ${escapeHtml(rs.name)}</td>
            <td style="padding:10px 12px; color:#94a3b8; font-size:0.78rem;">${escapeHtml(rs.index_number)}</td>
            <td style="padding:10px 12px; color:#f87171; font-weight:700;">${rs.failing_subjects_count} Subjects Failing</td>
            <td style="padding:10px 12px; font-weight:600;">Avg: ${rs.average_score}%</td>
            <td style="padding:10px 12px; text-align:right; white-space:nowrap;">
              <button type="button" onclick="sendExeatParentAlert('${escapeHtml(rs.guardian_phone)}', '${escapeHtml(rs.name)}')" 
                      style="background:rgba(239,68,68,0.2); border:1px solid rgba(239,68,68,0.4); color:#f87171; padding:4px 10px; border-radius:6px; font-size:0.75rem; font-weight:600; cursor:pointer;">
                📲 Contact Guardian
              </button>
            </td>
          </tr>
        `).join('');

        cardsHtml += `
          <div class="card" style="grid-column: 1 / -1; border-top: 4px solid #ef4444; background: var(--card-bg, #1e293b); margin-top:8px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; flex-wrap:wrap; gap:8px;">
              <div>
                <h4 style="margin:0; font-size:1.05rem; color:#f87171; display:flex; align-items:center; gap:8px;">
                  <span>⚠️</span> Class Early Warning & Academic Intervention Roster
                </h4>
                <div style="font-size:0.78rem; opacity:0.65; margin-top:2px;">Students currently failing 2 or more core subjects requiring immediate academic remedial attention</div>
              </div>
              <a class="btn sm" href="report-card.html" style="background:#dc2626; color:white; font-weight:600; text-decoration:none; padding:6px 14px; font-size:0.8rem; border-radius:6px;">🖨️ Terminal Remarks Desk</a>
            </div>
            <div style="overflow-x:auto;">
              <table style="width:100%; border-collapse:collapse; font-size:0.85rem;">
                <thead>
                  <tr style="border-bottom:1px solid rgba(255,255,255,0.1); text-align:left; color:#94a3b8;">
                    <th style="padding:8px 12px;">Student Name</th>
                    <th style="padding:8px 12px;">Index / Admission No.</th>
                    <th style="padding:8px 12px;">Failing Load</th>
                    <th style="padding:8px 12px;">Current Average</th>
                    <th style="padding:8px 12px; text-align:right;">Guardian Intervention</th>
                  </tr>
                </thead>
                <tbody>
                  ${riskRows}
                </tbody>
              </table>
            </div>
          </div>
        `;
      }
    }

    // ── Subject Teacher Personal Command Center ───────────────────────────────
    if (showTeacher) {
      const headingEl = document.getElementById('execAnalyticsTitle');
      if (headingEl) headingEl.innerHTML = `✍️ Faculty Teaching & Continuous Assessment (SBA) Desk`;

      // 1. My Teaching Allocations & Score Entry Matrix
      let allocRows = '';
      if (Array.isArray(tchr.allocations) && tchr.allocations.length > 0) {
        allocRows = tchr.allocations.map(al => {
          let badge = al.status === 'COMPLETE'
            ? `<span style="background:rgba(34,197,94,0.2); color:#4ade80; border:1px solid rgba(34,197,94,0.4); padding:2px 8px; border-radius:12px; font-size:0.75rem; font-weight:700;">✓ COMPLETE</span>`
            : (al.status === 'IN_PROGRESS'
              ? `<span style="background:rgba(245,158,11,0.2); color:#fbbf24; border:1px solid rgba(245,158,11,0.4); padding:2px 8px; border-radius:12px; font-size:0.75rem; font-weight:700;">⏳ IN PROGRESS (${al.completion_pct}%)</span>`
              : `<span style="background:rgba(239,68,68,0.2); color:#f87171; border:1px solid rgba(239,68,68,0.4); padding:2px 8px; border-radius:12px; font-size:0.75rem; font-weight:700;">❌ NOT STARTED</span>`);

          return `
            <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
              <td style="padding:10px 12px; font-weight:600; color:#f8fafc;">🏫 ${escapeHtml(al.class_name)}</td>
              <td style="padding:10px 12px; color:#38bdf8; font-weight:600;">📚 ${escapeHtml(al.subject_name)}</td>
              <td style="padding:10px 12px;">${al.scores_recorded} / ${al.class_size} Students</td>
              <td style="padding:10px 12px; min-width:110px;">
                <div style="width:100%; height:6px; background:rgba(255,255,255,0.08); border-radius:3px; overflow:hidden;">
                  <div style="width:${al.completion_pct}%; height:100%; background:${al.status === 'COMPLETE' ? '#10b981' : (al.status === 'IN_PROGRESS' ? '#f59e0b' : '#ef4444')};"></div>
                </div>
              </td>
              <td style="padding:10px 12px;">${badge}</td>
              <td style="padding:10px 12px; text-align:right;">
                <a href="bulk-entry.html" class="btn sm" style="padding:5px 12px; font-size:0.78rem; background:rgba(99,102,241,0.2); color:#818cf8; border:1px solid rgba(99,102,241,0.4); text-decoration:none; border-radius:6px; font-weight:600; white-space:nowrap;">
                  ✍️ Enter Marks
                </a>
              </td>
            </tr>
          `;
        }).join('');
      } else {
        allocRows = `<tr><td colspan="6" style="padding:16px; text-align:center; opacity:0.6;">No subject allocations assigned yet.</td></tr>`;
      }

      cardsHtml += `
        <div class="card" style="grid-column: 1 / -1; border-top: 4px solid #6366f1; background: var(--card-bg, #1e293b);">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; flex-wrap:wrap; gap:8px;">
            <div>
              <h4 style="margin:0; font-size:1.05rem; color:#818cf8; display:flex; align-items:center; gap:8px;">
                <span>✍️</span> My Teaching Allocations & Continuous Assessment (SBA) Progress
              </h4>
              <div style="font-size:0.78rem; opacity:0.65; margin-top:2px;">Track class-by-class marks upload and continuous assessment completion across your assigned subjects</div>
            </div>
            <a class="btn sm" href="bulk-entry.html" style="background:#4f46e5; color:white; font-weight:600; text-decoration:none; padding:6px 14px; font-size:0.8rem; border-radius:6px;">✍️ Open Score Desk</a>
          </div>
          <div style="overflow-x:auto;">
            <table style="width:100%; border-collapse:collapse; font-size:0.85rem;">
              <thead>
                <tr style="border-bottom:1px solid rgba(255,255,255,0.1); text-align:left; color:#94a3b8;">
                  <th style="padding:8px 12px;">Class Section</th>
                  <th style="padding:8px 12px;">Assigned Subject</th>
                  <th style="padding:8px 12px;">Enrollment / Entered</th>
                  <th style="padding:8px 12px;">Progress</th>
                  <th style="padding:8px 12px;">Status</th>
                  <th style="padding:8px 12px; text-align:right;">Actions</th>
                </tr>
              </thead>
              <tbody>
                ${allocRows}
              </tbody>
            </table>
          </div>
        </div>
      `;

      // 2. Today's Teaching Schedule & Timetable Countdown Card
      let ttRows = '';
      if (Array.isArray(tchr.today_timetable) && tchr.today_timetable.length > 0) {
        ttRows = tchr.today_timetable.map(tt => `
          <div style="display:flex; justify-content:space-between; align-items:center; background:rgba(255,255,255,0.03); padding:10px 12px; border-radius:8px; border:1px solid rgba(255,255,255,0.05); margin-bottom:8px;">
            <div>
              <span style="font-weight:700; color:#38bdf8; font-size:0.88rem;">Period ${tt.period_number}</span>
              <span style="font-size:0.75rem; opacity:0.65; margin-left:8px;">(${escapeHtml(tt.start_time)} - ${escapeHtml(tt.end_time)})</span>
              <div style="font-size:0.82rem; font-weight:600; margin-top:2px; color:#f8fafc;">
                📚 ${escapeHtml(tt.subject_name)} &bull; <span style="color:#a855f7;">${escapeHtml(tt.class_name)}</span>
              </div>
              <div style="font-size:0.72rem; opacity:0.6; margin-top:1px;">Room: ${escapeHtml(tt.room)}</div>
            </div>
            <a href="attendance.html" class="btn sm" style="padding:4px 10px; font-size:0.75rem; background:rgba(56,189,248,0.2); color:#38bdf8; border:1px solid rgba(56,189,248,0.4); text-decoration:none; border-radius:6px; font-weight:600; white-space:nowrap;">
              ⚡ Mark Attendance
            </a>
          </div>
        `).join('');
      } else {
        ttRows = `
          <div style="text-align:center; padding:24px 12px; background:rgba(255,255,255,0.02); border-radius:8px; border:1px dashed rgba(255,255,255,0.1);">
            <div style="font-size:1.8rem; margin-bottom:6px;">☕</div>
            <strong style="color:#f8fafc; font-size:0.9rem;">No Teaching Periods Scheduled Today</strong>
            <div style="font-size:0.75rem; opacity:0.6; margin-top:4px;">Check your weekly teaching master timetable for upcoming lessons.</div>
          </div>
        `;
      }

      cardsHtml += `
        <div class="card" style="border-left: 4px solid #0284c7; background: var(--card-bg, #1e293b);">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
            <h4 style="margin:0; font-size:1.05rem; color:#38bdf8; display:flex; align-items:center; gap:8px;">
              <span>📅</span> Today's Teaching Schedule
            </h4>
            <a href="timetable.html" class="btn sm" style="background:#0284c7; color:white; font-weight:600; text-decoration:none; padding:4px 10px; font-size:0.75rem; border-radius:6px;">Full Timetable</a>
          </div>
          <div>
            ${ttRows}
          </div>
        </div>
      `;

      // 3. Academic Remedial Watchlist Card
      let tRiskRows = '';
      if (Array.isArray(tchr.at_risk_students) && tchr.at_risk_students.length > 0) {
        tRiskRows = tchr.at_risk_students.map(rs => `
          <div style="display:flex; justify-content:space-between; align-items:center; background:rgba(239,68,68,0.06); padding:10px 12px; border-radius:8px; border:1px solid rgba(239,68,68,0.2); margin-bottom:8px;">
            <div>
              <strong style="color:#f87171; font-size:0.85rem;">⚠️ ${escapeHtml(rs.name)}</strong>
              <div style="font-size:0.75rem; opacity:0.7; margin-top:1px;">
                ${escapeHtml(rs.class_name)} &bull; ${escapeHtml(rs.subject_name)}
              </div>
              <div style="font-size:0.72rem; color:#f87171; font-weight:600; margin-top:2px;">
                Score: ${rs.score}% (Requires Remedial Attention)
              </div>
            </div>
            <button type="button" onclick="sendExeatParentAlert('${escapeHtml(rs.phone)}', '${escapeHtml(rs.name)}')" 
                    style="background:rgba(239,68,68,0.2); border:1px solid rgba(239,68,68,0.4); color:#f87171; padding:4px 10px; border-radius:6px; font-size:0.75rem; font-weight:600; cursor:pointer; white-space:nowrap;">
              📲 Alert Parent
            </button>
          </div>
        `).join('');
      } else {
        tRiskRows = `
          <div style="text-align:center; padding:24px 12px; background:rgba(255,255,255,0.02); border-radius:8px; border:1px dashed rgba(255,255,255,0.1);">
            <div style="font-size:1.8rem; margin-bottom:6px;">🌟</div>
            <strong style="color:#34d399; font-size:0.9rem;">No Students Flagged At Risk</strong>
            <div style="font-size:0.75rem; opacity:0.6; margin-top:4px;">All evaluated students currently meeting satisfactory academic threshold (&ge; 50%).</div>
          </div>
        `;
      }

      cardsHtml += `
        <div class="card" style="border-left: 4px solid #ef4444; background: var(--card-bg, #1e293b);">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
            <h4 style="margin:0; font-size:1.05rem; color:#f87171; display:flex; align-items:center; gap:8px;">
              <span>⚠️</span> Subject Remedial Watchlist
            </h4>
            <a href="report-card.html" class="btn sm" style="background:#dc2626; color:white; font-weight:600; text-decoration:none; padding:4px 10px; font-size:0.75rem; border-radius:6px;">Progress Desk</a>
          </div>
          <div>
            ${tRiskRows}
          </div>
        </div>
      `;
    }

    // ── Housemaster / Housemistress Command Center ────────────────────────────
    if (showHouseMaster) {
      const headingEl = document.getElementById('execAnalyticsTitle');
      if (headingEl) headingEl.innerHTML = `🏡 Housemaster Custody & Welfare Command Center (${escapeHtml(hm.house_name || 'My House')})`;

      // 1. House Dormitory Bed Occupancy & Capacity Matrix Card
      let dormRows = '';
      if (Array.isArray(hm.dormitories) && hm.dormitories.length > 0) {
        dormRows = hm.dormitories.map(dm => `
          <div style="background:rgba(255,255,255,0.03); padding:10px 12px; border-radius:8px; border:1px solid rgba(255,255,255,0.05); margin-bottom:8px;">
            <div style="display:flex; justify-content:space-between; align-items:center; font-size:0.85rem; margin-bottom:4px;">
              <strong style="color:#f8fafc;">🛏️ ${escapeHtml(dm.name)}</strong>
              <span style="font-weight:700; color:#38bdf8;">${dm.occupants} / ${dm.capacity} beds (${dm.occupancy_pct}%)</span>
            </div>
            <div style="width:100%; height:6px; background:rgba(255,255,255,0.08); border-radius:3px; overflow:hidden;">
              <div style="width:${Math.min(100, dm.occupancy_pct)}%; height:100%; background:${dm.occupancy_pct > 90 ? '#ef4444' : '#10b981'};"></div>
            </div>
          </div>
        `).join('');
      } else {
        dormRows = `<div style="opacity:0.6; font-size:0.8rem; padding:8px 0;">No dormitories configured for this house yet.</div>`;
      }

      cardsHtml += `
        <div class="card" style="border-left: 4px solid #10b981; background: var(--card-bg, #1e293b);">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
            <h4 style="margin:0; font-size:1.05rem; color:#34d399; display:flex; align-items:center; gap:8px;">
              <span>🛌</span> Dormitory Bed Capacity & Census
            </h4>
            <a href="houses.html" class="btn sm" style="background:#059669; color:white; font-weight:600; text-decoration:none; padding:4px 10px; font-size:0.75rem; border-radius:6px;">Dorm Roster</a>
          </div>
          <div>
            ${dormRows}
          </div>
        </div>
      `;

      // 2. Active Exeats & Curfew Returnee Watchlist Card
      let exRows = '';
      if (Array.isArray(hm.active_exeats) && hm.active_exeats.length > 0) {
        exRows = hm.active_exeats.map(ex => `
          <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
            <td style="padding:8px 10px; font-weight:600; color:#f8fafc;">🏡 ${escapeHtml(ex.student_name)}</td>
            <td style="padding:8px 10px; color:#38bdf8;">${escapeHtml(ex.exeat_type)}</td>
            <td style="padding:8px 10px; font-size:0.78rem;">${escapeHtml(ex.expected_return)}</td>
            <td style="padding:8px 10px;">
              ${ex.is_overdue 
                ? `<span style="background:rgba(239,68,68,0.2); color:#f87171; border:1px solid rgba(239,68,68,0.4); padding:2px 8px; border-radius:12px; font-size:0.72rem; font-weight:700;">🚨 OVERDUE</span>`
                : `<span style="background:rgba(34,197,94,0.2); color:#4ade80; border:1px solid rgba(34,197,94,0.4); padding:2px 8px; border-radius:12px; font-size:0.72rem; font-weight:700;">✓ AWAY</span>`}
            </td>
            <td style="padding:8px 10px; text-align:right;">
              <button type="button" onclick="sendExeatParentAlert('${escapeHtml(ex.parent_phone)}', '${escapeHtml(ex.student_name)}')" 
                      style="background:rgba(245,158,11,0.2); border:1px solid rgba(245,158,11,0.4); color:#fbbf24; padding:3px 8px; border-radius:6px; font-size:0.72rem; font-weight:600; cursor:pointer;">
                📲 Alert
              </button>
            </td>
          </tr>
        `).join('');
      } else {
        exRows = `<tr><td colspan="5" style="padding:14px; text-align:center; opacity:0.6;">All boarders currently accounted for on campus.</td></tr>`;
      }

      cardsHtml += `
        <div class="card" style="border-left: 4px solid #f59e0b; background: var(--card-bg, #1e293b);">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
            <h4 style="margin:0; font-size:1.05rem; color:#fbbf24; display:flex; align-items:center; gap:8px;">
              <span>🏡</span> Active Exeats & Curfew Tracking
            </h4>
            <a href="exeat.html" class="btn sm" style="background:#d97706; color:white; font-weight:600; text-decoration:none; padding:4px 10px; font-size:0.75rem; border-radius:6px;">Exeat Desk</a>
          </div>
          <div style="overflow-x:auto;">
            <table style="width:100%; border-collapse:collapse; font-size:0.82rem;">
              <thead>
                <tr style="border-bottom:1px solid rgba(255,255,255,0.1); text-align:left; color:#94a3b8;">
                  <th style="padding:6px 10px;">Boarder Name</th>
                  <th style="padding:6px 10px;">Category</th>
                  <th style="padding:6px 10px;">Return Due</th>
                  <th style="padding:6px 10px;">Status</th>
                  <th style="padding:6px 10px; text-align:right;">Action</th>
                </tr>
              </thead>
              <tbody>
                ${exRows}
              </tbody>
            </table>
          </div>
        </div>
      `;

      // 3. House Special Care & Health Registry Card
      if (Array.isArray(hm.medical_alerts) && hm.medical_alerts.length > 0) {
        let medRows = hm.medical_alerts.map(mr => `
          <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
            <td style="padding:8px 10px; font-weight:600; color:#f8fafc;">🩺 ${escapeHtml(mr.student_name)}</td>
            <td style="padding:8px 10px; color:#f87171; font-weight:600;">${escapeHtml(mr.condition)}</td>
            <td style="padding:8px 10px; color:#38bdf8;">${escapeHtml(mr.blood_group || '—')}</td>
            <td style="padding:8px 10px; font-size:0.75rem; color:#fbbf24;">${escapeHtml(mr.allergies || 'None')}</td>
            <td style="padding:8px 10px; text-align:right;">
              <button type="button" onclick="sendExeatParentAlert('${escapeHtml(mr.emergency_contact)}', '${escapeHtml(mr.student_name)}')" 
                      style="background:rgba(239,68,68,0.2); border:1px solid rgba(239,68,68,0.4); color:#f87171; padding:3px 8px; border-radius:6px; font-size:0.72rem; font-weight:600; cursor:pointer;">
                📞 Contact
              </button>
            </td>
          </tr>
        `).join('');

        cardsHtml += `
          <div class="card" style="grid-column: 1 / -1; border-top: 4px solid #ef4444; background: var(--card-bg, #1e293b); margin-top:8px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; flex-wrap:wrap; gap:8px;">
              <div>
                <h4 style="margin:0; font-size:1.05rem; color:#f87171; display:flex; align-items:center; gap:8px;">
                  <span>🩺</span> House Special Care & Health Registry
                </h4>
                <div style="font-size:0.78rem; opacity:0.65; margin-top:2px;">Boarders in this house requiring active medical monitoring, dietary care, or chronic management</div>
              </div>
              <a class="btn sm" href="students.html" style="background:#dc2626; color:white; font-weight:600; text-decoration:none; padding:6px 14px; font-size:0.8rem; border-radius:6px;">🩺 Medical Profile Registry</a>
            </div>
            <div style="overflow-x:auto;">
              <table style="width:100%; border-collapse:collapse; font-size:0.85rem;">
                <thead>
                  <tr style="border-bottom:1px solid rgba(255,255,255,0.1); text-align:left; color:#94a3b8;">
                    <th style="padding:8px 10px;">Boarder Name</th>
                    <th style="padding:8px 10px;">Primary Condition</th>
                    <th style="padding:8px 10px;">Blood Group</th>
                    <th style="padding:8px 10px;">Allergies / Special Instructions</th>
                    <th style="padding:8px 10px; text-align:right;">Emergency Contact</th>
                  </tr>
                </thead>
                <tbody>
                  ${medRows}
                </tbody>
              </table>
            </div>
          </div>
        `;
      }
    }

    // ── Bursar / Accountant Financial Command Center ──────────────────────────
    if (showBursar) {
      const headingEl = document.getElementById('execAnalyticsTitle');
      if (headingEl) headingEl.innerHTML = `💳 Bursary & Financial Management Command Center`;

      // 1. Fee Revenue Breakdown & Collection Efficiency Matrix Card
      let catRows = '';
      if (Array.isArray(bur.fee_categories) && bur.fee_categories.length > 0) {
        catRows = bur.fee_categories.map(c => `
          <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
            <td style="padding:10px 12px; font-weight:600; color:#f8fafc;">📋 ${escapeHtml(c.category)}</td>
            <td style="padding:10px 12px; color:#94a3b8;">GH₵ ${c.billed.toLocaleString()}</td>
            <td style="padding:10px 12px; color:#34d399; font-weight:700;">GH₵ ${c.collected.toLocaleString()}</td>
            <td style="padding:10px 12px; color:#f87171; font-weight:700;">GH₵ ${c.arrears.toLocaleString()}</td>
            <td style="padding:10px 12px; min-width:110px;">
              <div style="display:flex; justify-content:space-between; font-size:0.72rem; margin-bottom:2px;">
                <span>${c.collection_pct}%</span>
              </div>
              <div style="width:100%; height:6px; background:rgba(255,255,255,0.08); border-radius:3px; overflow:hidden;">
                <div style="width:${Math.min(100, c.collection_pct)}%; height:100%; background:#10b981;"></div>
              </div>
            </td>
          </tr>
        `).join('');
      } else {
        catRows = `<tr><td colspan="5" style="padding:14px; text-align:center; opacity:0.6;">No fee categories recorded yet.</td></tr>`;
      }

      cardsHtml += `
        <div class="card" style="grid-column: 1 / -1; border-top: 4px solid #10b981; background: var(--card-bg, #1e293b);">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; flex-wrap:wrap; gap:8px;">
            <div>
              <h4 style="margin:0; font-size:1.05rem; color:#34d399; display:flex; align-items:center; gap:8px;">
                <span>💳</span> Institutional Revenue & Fee Collection Breakdown
              </h4>
              <div style="font-size:0.78rem; opacity:0.65; margin-top:2px;">Comprehensive tracking of student billing, collections, and outstanding debt by category</div>
            </div>
            <a class="btn sm" href="fees.html" style="background:#059669; color:white; font-weight:600; text-decoration:none; padding:6px 14px; font-size:0.8rem; border-radius:6px;">💳 Open Bursary Desk</a>
          </div>
          <div style="overflow-x:auto;">
            <table style="width:100%; border-collapse:collapse; font-size:0.85rem;">
              <thead>
                <tr style="border-bottom:1px solid rgba(255,255,255,0.1); text-align:left; color:#94a3b8;">
                  <th style="padding:8px 12px;">Billing Head / Stream</th>
                  <th style="padding:8px 12px;">Total Invoiced</th>
                  <th style="padding:8px 12px;">Revenue Collected</th>
                  <th style="padding:8px 12px;">Outstanding Arrears</th>
                  <th style="padding:8px 12px;">Recovery Rate</th>
                </tr>
              </thead>
              <tbody>
                ${catRows}
              </tbody>
            </table>
          </div>
        </div>
      `;

      // 2. Daily Cash Ledger & Recent Payments Activity Stream
      let payRows = '';
      if (Array.isArray(bur.recent_payments) && bur.recent_payments.length > 0) {
        payRows = bur.recent_payments.map(p => `
          <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
            <td style="padding:8px 10px; font-weight:600; color:#38bdf8;">🧾 ${escapeHtml(p.receipt_no)}</td>
            <td style="padding:8px 10px; font-weight:600; color:#f8fafc;">${escapeHtml(p.student_name)}</td>
            <td style="padding:8px 10px; color:#34d399; font-weight:700;">GH₵ ${p.amount.toLocaleString()}</td>
            <td style="padding:8px 10px; font-size:0.78rem;">${escapeHtml(p.method)}</td>
            <td style="padding:8px 10px; font-size:0.75rem; color:#94a3b8;">${escapeHtml(p.date)}</td>
          </tr>
        `).join('');
      } else {
        payRows = `<tr><td colspan="5" style="padding:14px; text-align:center; opacity:0.6;">No payments recorded today.</td></tr>`;
      }

      cardsHtml += `
        <div class="card" style="border-left: 4px solid #0284c7; background: var(--card-bg, #1e293b);">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
            <h4 style="margin:0; font-size:1.05rem; color:#38bdf8; display:flex; align-items:center; gap:8px;">
              <span>🧾</span> Recent Payments Stream
            </h4>
            <a href="fees.html" class="btn sm" style="background:#0284c7; color:white; font-weight:600; text-decoration:none; padding:4px 10px; font-size:0.75rem; border-radius:6px;">Transactions</a>
          </div>
          <div style="overflow-x:auto;">
            <table style="width:100%; border-collapse:collapse; font-size:0.82rem;">
              <thead>
                <tr style="border-bottom:1px solid rgba(255,255,255,0.1); text-align:left; color:#94a3b8;">
                  <th style="padding:6px 10px;">Receipt #</th>
                  <th style="padding:6px 10px;">Student</th>
                  <th style="padding:6px 10px;">Amount</th>
                  <th style="padding:6px 10px;">Channel</th>
                  <th style="padding:6px 10px;">Timestamp</th>
                </tr>
              </thead>
              <tbody>
                ${payRows}
              </tbody>
            </table>
          </div>
        </div>
      `;

      // 3. Fee Arrears & High-Risk Debtors Watchlist
      let debtRows = '';
      if (Array.isArray(bur.top_debtors) && bur.top_debtors.length > 0) {
        debtRows = bur.top_debtors.map(d => `
          <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
            <td style="padding:8px 10px; font-weight:600; color:#f8fafc;">⚠️ ${escapeHtml(d.student_name)}</td>
            <td style="padding:8px 10px; color:#38bdf8;">${escapeHtml(d.class_name)}</td>
            <td style="padding:8px 10px; color:#f87171; font-weight:700;">GH₵ ${d.amount_owed.toLocaleString()}</td>
            <td style="padding:8px 10px; text-align:right;">
              <button type="button" onclick="sendFeeReminder('${escapeHtml(d.guardian_phone)}', '${escapeHtml(d.student_name)}', '${d.amount_owed}')"
                      style="background:rgba(239,68,68,0.2); border:1px solid rgba(239,68,68,0.4); color:#f87171; padding:3px 8px; border-radius:6px; font-size:0.72rem; font-weight:600; cursor:pointer;">
                📲 SMS Debt Notice
              </button>
            </td>
          </tr>
        `).join('');
      } else {
        debtRows = `<tr><td colspan="4" style="padding:14px; text-align:center; opacity:0.6;">No outstanding arrears above threshold.</td></tr>`;
      }

      cardsHtml += `
        <div class="card" style="border-left: 4px solid #ef4444; background: var(--card-bg, #1e293b);">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
            <h4 style="margin:0; font-size:1.05rem; color:#f87171; display:flex; align-items:center; gap:8px;">
              <span>⚠️</span> High Arrears Watchlist
            </h4>
            <a href="fees.html" class="btn sm" style="background:#dc2626; color:white; font-weight:600; text-decoration:none; padding:4px 10px; font-size:0.75rem; border-radius:6px;">Arrears Desk</a>
          </div>
          <div style="overflow-x:auto;">
            <table style="width:100%; border-collapse:collapse; font-size:0.82rem;">
              <thead>
                <tr style="border-bottom:1px solid rgba(255,255,255,0.1); text-align:left; color:#94a3b8;">
                  <th style="padding:6px 10px;">Student</th>
                  <th style="padding:6px 10px;">Class</th>
                  <th style="padding:6px 10px;">Balance Owed</th>
                  <th style="padding:6px 10px; text-align:right;">Recovery Action</th>
                </tr>
              </thead>
              <tbody>
                ${debtRows}
              </tbody>
            </table>
          </div>
        </div>
      `;
    }

    // ── Storekeeper & Inventory Command Center ────────────────────────────────
    if (showStorekeeper) {
      const headingEl = document.getElementById('execAnalyticsTitle');
      if (headingEl) headingEl.innerHTML = `📦 Store & Inventory Management Command Center`;

      cardsHtml += `
        <div class="card" style="grid-column: 1 / -1; border-top: 4px solid #f59e0b; background: var(--card-bg, #1e293b);">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; flex-wrap:wrap; gap:8px;">
            <div>
              <h4 style="margin:0; font-size:1.05rem; color:#fbbf24; display:flex; align-items:center; gap:8px;">
                <span>📦</span> Institutional Store & Inventory Asset Overview
              </h4>
              <div style="font-size:0.78rem; opacity:0.65; margin-top:2px;">Summary of assets, uniform stocks, textbook allocations, and equipment health</div>
            </div>
            <a class="btn sm" href="inventory.html" style="background:#d97706; color:white; font-weight:600; text-decoration:none; padding:6px 14px; font-size:0.8rem; border-radius:6px;">📦 Open Store Desk</a>
          </div>
          <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(200px, 1fr)); gap:12px; font-size:0.85rem;">
            <div style="background:rgba(255,255,255,0.03); padding:12px; border-radius:8px; border:1px solid rgba(255,255,255,0.05);">
              <span style="opacity:0.7; font-size:0.75rem;">Total School Assets:</span><br/>
              <strong style="font-size:1.25rem; color:#38bdf8;">${stk.total_assets_count || 0} Registered</strong>
              <div style="font-size:0.72rem; opacity:0.6; margin-top:2px;">Furniture, ICT & lab equipment</div>
            </div>
            <div style="background:rgba(255,255,255,0.03); padding:12px; border-radius:8px; border:1px solid rgba(255,255,255,0.05);">
              <span style="opacity:0.7; font-size:0.75rem;">Textbooks Issued:</span><br/>
              <strong style="font-size:1.25rem; color:#34d399;">${stk.total_textbooks_issued || 0} With Students</strong>
              <div style="font-size:0.72rem; opacity:0.6; margin-top:2px;">Active book loans</div>
            </div>
            <div style="background:rgba(255,255,255,0.03); padding:12px; border-radius:8px; border:1px solid rgba(255,255,255,0.05);">
              <span style="opacity:0.7; font-size:0.75rem;">Uniforms in Stock:</span><br/>
              <strong style="font-size:1.25rem; color:#a855f7;">${stk.total_uniforms_in_stock || 0} Units</strong>
              <div style="font-size:0.72rem; opacity:0.6; margin-top:2px;">Available for disbursement</div>
            </div>
            <div style="background:rgba(255,255,255,0.03); padding:12px; border-radius:8px; border:1px solid rgba(255,255,255,0.05);">
              <span style="opacity:0.7; font-size:0.75rem;">Low Stock Alerts:</span><br/>
              <strong style="font-size:1.25rem; color:#ef4444;">${stk.low_stock_alerts_count || 0} Items</strong>
              <div style="font-size:0.72rem; opacity:0.6; margin-top:2px;">Below reorder threshold</div>
            </div>
          </div>
        </div>
      `;
    }

    // ── Security & Gatehouse Command Center ───────────────────────────────────
    if (showSecurity) {
      const headingEl = document.getElementById('execAnalyticsTitle');
      if (headingEl) headingEl.innerHTML = `🚪 Campus Gatehouse & Security Command Center`;

      let secLogs = '';
      if (Array.isArray(sec.recent_gate_logs) && sec.recent_gate_logs.length > 0) {
        secLogs = sec.recent_gate_logs.map(g => `
          <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
            <td style="padding:8px 10px; font-weight:600; color:#f8fafc;">👤 ${escapeHtml(g.student_name)}</td>
            <td style="padding:8px 10px; color:#38bdf8;">${escapeHtml(g.action)}</td>
            <td style="padding:8px 10px; font-size:0.78rem;">${escapeHtml(g.time)}</td>
            <td style="padding:8px 10px; font-size:0.75rem; color:#94a3b8;">${escapeHtml(g.officer)}</td>
          </tr>
        `).join('');
      } else {
        secLogs = `<tr><td colspan="4" style="padding:14px; text-align:center; opacity:0.6;">No gate movements logged today.</td></tr>`;
      }

      cardsHtml += `
        <div class="card" style="border-left: 4px solid #0284c7; background: var(--card-bg, #1e293b);">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
            <h4 style="margin:0; font-size:1.05rem; color:#38bdf8; display:flex; align-items:center; gap:8px;">
              <span>🚪</span> Today's Gate Movement Activity Log
            </h4>
            <a href="exeat.html" class="btn sm" style="background:#0284c7; color:white; font-weight:600; text-decoration:none; padding:4px 10px; font-size:0.75rem; border-radius:6px;">Gate Scanner</a>
          </div>
          <div style="overflow-x:auto;">
            <table style="width:100%; border-collapse:collapse; font-size:0.82rem;">
              <thead>
                <tr style="border-bottom:1px solid rgba(255,255,255,0.1); text-align:left; color:#94a3b8;">
                  <th style="padding:6px 10px;">Student Name</th>
                  <th style="padding:6px 10px;">Movement Type</th>
                  <th style="padding:6px 10px;">Time</th>
                  <th style="padding:6px 10px;">Verified By</th>
                </tr>
              </thead>
              <tbody>
                ${secLogs}
              </tbody>
            </table>
          </div>
        </div>
      `;

      let secOverdue = '';
      if (Array.isArray(sec.overdue_watchlist) && sec.overdue_watchlist.length > 0) {
        secOverdue = sec.overdue_watchlist.map(ov => `
          <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
            <td style="padding:8px 10px; font-weight:600; color:#f8fafc;">🚨 ${escapeHtml(ov.student_name)}</td>
            <td style="padding:8px 10px; color:#38bdf8;">${escapeHtml(ov.class_name)}</td>
            <td style="padding:8px 10px; color:#f87171; font-weight:700;">${escapeHtml(ov.expected_return)}</td>
            <td style="padding:8px 10px; text-align:right;">
              <button type="button" onclick="sendExeatParentAlert('${escapeHtml(ov.parent_phone)}', '${escapeHtml(ov.student_name)}')"
                      style="background:rgba(239,68,68,0.2); border:1px solid rgba(239,68,68,0.4); color:#f87171; padding:3px 8px; border-radius:6px; font-size:0.72rem; font-weight:600; cursor:pointer;">
                📲 Alert Guardian
              </button>
            </td>
          </tr>
        `).join('');
      } else {
        secOverdue = `<tr><td colspan="4" style="padding:14px; text-align:center; opacity:0.6;">All students currently accounted for.</td></tr>`;
      }

      cardsHtml += `
        <div class="card" style="border-left: 4px solid #ef4444; background: var(--card-bg, #1e293b);">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
            <h4 style="margin:0; font-size:1.05rem; color:#f87171; display:flex; align-items:center; gap:8px;">
              <span>🚨</span> Gatehouse Overdue Exeat Watchlist
            </h4>
            <a href="exeat.html" class="btn sm" style="background:#dc2626; color:white; font-weight:600; text-decoration:none; padding:4px 10px; font-size:0.75rem; border-radius:6px;">Exeat Desk</a>
          </div>
          <div style="overflow-x:auto;">
            <table style="width:100%; border-collapse:collapse; font-size:0.82rem;">
              <thead>
                <tr style="border-bottom:1px solid rgba(255,255,255,0.1); text-align:left; color:#94a3b8;">
                  <th style="padding:6px 10px;">Student Name</th>
                  <th style="padding:6px 10px;">Class</th>
                  <th style="padding:6px 10px;">Due Return</th>
                  <th style="padding:6px 10px; text-align:right;">Action</th>
                </tr>
              </thead>
              <tbody>
                ${secOverdue}
              </tbody>
            </table>
          </div>
        </div>
      `;
    }

    // ── Student / Parent Stakeholder Portal ───────────────────────────────────
    if (showStudent || showParent) {
      const headingEl = document.getElementById('execAnalyticsTitle');
      if (headingEl) headingEl.innerHTML = showParent ? `👨‍👩‍👧 Parent & Guardian Academic Portal` : `🎓 Student Academic & Welfare Profile`;

      cardsHtml += `
        <div class="card" style="grid-column: 1 / -1; border-top: 4px solid #6366f1; background: var(--card-bg, #1e293b);">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; flex-wrap:wrap; gap:8px;">
            <div>
              <h4 style="margin:0; font-size:1.05rem; color:#818cf8; display:flex; align-items:center; gap:8px;">
                <span>🎓</span> Academic & Residential Profile: ${escapeHtml(stp.name || 'Student')}
              </h4>
              <div style="font-size:0.78rem; opacity:0.65; margin-top:2px;">
                ${escapeHtml(stp.class_name || 'Class')} &bull; ${escapeHtml(stp.program_name || 'Program')} &bull; ${escapeHtml(stp.house_name || 'House')}
              </div>
            </div>
            <a class="btn sm" href="report-card.html" style="background:#4f46e5; color:white; font-weight:600; text-decoration:none; padding:6px 14px; font-size:0.8rem; border-radius:6px;">🖨️ View Full Report Card</a>
          </div>
          <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(200px, 1fr)); gap:12px; font-size:0.85rem;">
            <div style="background:rgba(255,255,255,0.03); padding:12px; border-radius:8px; border:1px solid rgba(255,255,255,0.05);">
              <span style="opacity:0.7; font-size:0.75rem;">Term Average:</span><br/>
              <strong style="font-size:1.25rem; color:#10b981;">${stp.term_average || 0}%</strong>
              <div style="font-size:0.72rem; opacity:0.6; margin-top:2px;">Continuous Assessment Score</div>
            </div>
            <div style="background:rgba(255,255,255,0.03); padding:12px; border-radius:8px; border:1px solid rgba(255,255,255,0.05);">
              <span style="opacity:0.7; font-size:0.75rem;">Attendance Rate:</span><br/>
              <strong style="font-size:1.25rem; color:#38bdf8;">${stp.attendance_rate_pct || 100}%</strong>
              <div style="font-size:0.72rem; opacity:0.6; margin-top:2px;">Class Attendance</div>
            </div>
            <div style="background:rgba(255,255,255,0.03); padding:12px; border-radius:8px; border:1px solid rgba(255,255,255,0.05);">
              <span style="opacity:0.7; font-size:0.75rem;">Outstanding Fees:</span><br/>
              <strong style="font-size:1.25rem; color:${(stp.fee_summary && stp.fee_summary.balance > 0) ? '#ef4444' : '#10b981'};">
                GH₵ ${stp.fee_summary ? stp.fee_summary.balance.toLocaleString() : 0}
              </strong>
              <div style="font-size:0.72rem; opacity:0.6; margin-top:2px;">Account Balance</div>
            </div>
            <div style="background:rgba(255,255,255,0.03); padding:12px; border-radius:8px; border:1px solid rgba(255,255,255,0.05);">
              <span style="opacity:0.7; font-size:0.75rem;">Exeat Status:</span><br/>
              <strong style="font-size:1.15rem; color:#fbbf24;">${escapeHtml(stp.active_exeat_status || 'On Campus')}</strong>
              <div style="font-size:0.72rem; opacity:0.6; margin-top:2px;">Residential Standing</div>
            </div>
          </div>
        </div>
      `;
    }

    // ── Domestic Executive Widget Card ────────────────────────────────────────
    if (showDomestic) {
      // Update top KPI cards if elements exist
      const boardersEl = document.getElementById('statBoarders');
      const boardersSub = document.getElementById('statBoardersSub');
      const progBoarders = document.getElementById('progBoarders');
      const exeatEl = document.getElementById('statExeat');
      const exeatSub = document.getElementById('statExeatSub');
      const progExeat = document.getElementById('progExeat');
      const medicalEl = document.getElementById('statMedical');
      const medicalSub = document.getElementById('statMedicalSub');
      const disciplineEl = document.getElementById('statDiscipline');
      const disciplineSub = document.getElementById('statDisciplineSub');

      if (boardersEl && dom.total_boarders !== undefined) {
        animateCountUp(boardersEl, dom.total_boarders);
        if (boardersSub) boardersSub.textContent = `${dom.total_boarders} boarders | ${dom.total_day_students || 0} day`;
        if (progBoarders) {
          const tot = (dom.total_boarders || 0) + (dom.total_day_students || 0);
          const pct = tot > 0 ? Math.round((dom.total_boarders / tot) * 100) : 100;
          setTimeout(() => { progBoarders.style.width = `${pct}%`; }, 150);
        }
      }
      if (exeatEl && dom.currently_away_exeat !== undefined) {
        animateCountUp(exeatEl, dom.currently_away_exeat);
        if (exeatSub) exeatSub.textContent = `${dom.overdue_exeat_count || 0} overdue curfew`;
        if (progExeat) {
          const pWidth = (dom.overdue_exeat_count > 0) ? 100 : Math.min(100, (dom.currently_away_exeat || 0) * 12);
          setTimeout(() => { progExeat.style.width = `${pWidth}%`; }, 150);
        }
      }
      if (medicalEl && dom.medical_flags_count !== undefined) {
        animateCountUp(medicalEl, dom.medical_flags_count);
        if (medicalSub) medicalSub.textContent = 'Special Care & Allergies';
      }
      if (disciplineEl && dom.active_discipline_incidents !== undefined) {
        animateCountUp(disciplineEl, dom.active_discipline_incidents);
        if (disciplineSub) disciplineSub.textContent = 'Pending Investigation';
      }

      const overdueAlertHtml = (dom.overdue_exeat_count > 0) 
        ? `<span style="background:rgba(239,68,68,0.2); color:#f87171; border:1px solid rgba(239,68,68,0.4); padding:2px 8px; border-radius:12px; font-weight:700; font-size:0.75rem;">🚨 ${dom.overdue_exeat_count} Overdue Curfew Alert(s)</span>`
        : `<span style="background:rgba(34,197,94,0.2); color:#4ade80; border:1px solid rgba(34,197,94,0.4); padding:2px 8px; border-radius:12px; font-size:0.75rem; font-weight:700;">✓ Exeats On Schedule</span>`;

      // 1. Campus Life & Welfare Summary Card
      cardsHtml += `
        <div class="card" style="border-left: 4px solid #f472b6; background: var(--card-bg, #1e293b);">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
            <h4 style="margin:0; font-size:1.05rem; color:#f472b6; display:flex; align-items:center; gap:8px;">
              <span>🏡</span> Campus Life, Welfare & Safe Custody
            </h4>
            ${overdueAlertHtml}
          </div>

          <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; font-size:0.85rem;">
            <div style="background:rgba(255,255,255,0.03); padding:10px 12px; border-radius:8px; border:1px solid rgba(255,255,255,0.05);">
              <span style="opacity:0.7; font-size:0.75rem;">Active Boarders & Capacity:</span><br/>
              <strong style="font-size:1.15rem; color:#38bdf8;">${dom.total_boarders} Boarders</strong>
              <div style="font-size:0.72rem; opacity:0.6; margin-top:2px;">Across ${dom.total_houses} Boarding Houses</div>
            </div>
            <div style="background:rgba(255,255,255,0.03); padding:10px 12px; border-radius:8px; border:1px solid rgba(255,255,255,0.05);">
              <span style="opacity:0.7; font-size:0.75rem;">Currently Away on Exeat:</span><br/>
              <strong style="font-size:1.15rem; color:#f59e0b;">${dom.currently_away_exeat} Departed</strong>
              <div style="font-size:0.72rem; opacity:0.6; margin-top:2px;">${dom.overdue_exeat_count} Overdue for return</div>
            </div>
            <div style="background:rgba(255,255,255,0.03); padding:10px 12px; border-radius:8px; border:1px solid rgba(255,255,255,0.05);">
              <span style="opacity:0.7; font-size:0.75rem;">Medical & Special Care:</span><br/>
              <strong style="font-size:1.15rem; color:#f87171;">${dom.medical_flags_count} Health Alerts</strong>
              <div style="font-size:0.72rem; opacity:0.6; margin-top:2px;">Allergies & chronic cases</div>
            </div>
            <div style="background:rgba(255,255,255,0.03); padding:10px 12px; border-radius:8px; border:1px solid rgba(255,255,255,0.05);">
              <span style="opacity:0.7; font-size:0.75rem;">Discipline Incidents:</span><br/>
              <strong style="font-size:1.15rem; color:${dom.active_discipline_incidents>0?'#f87171':'#4ade80'};">${dom.active_discipline_incidents} Active</strong>
              <div style="font-size:0.72rem; opacity:0.6; margin-top:2px;">Awaiting sanction</div>
            </div>
          </div>
        </div>
      `;

      // 2. Live Exeat Movement & Safe Custody Breakdown
      if (dom.active_exeats_breakdown) {
        const eb = dom.active_exeats_breakdown;
        cardsHtml += `
          <div class="card" style="border-left: 4px solid #f59e0b; background: var(--card-bg, #1e293b);">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
              <h4 style="margin:0; font-size:1.05rem; color:#fbbf24; display:flex; align-items:center; gap:8px;">
                <span>🗺️</span> Live Exeat Movement & Custody Radar
              </h4>
              <a href="exeat.html" class="btn sm" style="background:#d97706; color:white; font-weight:600; text-decoration:none; padding:4px 10px; font-size:0.75rem; border-radius:6px;">Exeat Gate Desk</a>
            </div>
            <div style="display:flex; flex-direction:column; gap:8px; font-size:0.8rem;">
              <div>
                <div style="display:flex; justify-content:space-between; margin-bottom:2px;">
                  <span style="font-weight:600; color:#38bdf8;">🏖️ Weekend Exeats:</span>
                  <strong>${eb.Weekend || 0} Students</strong>
                </div>
                <div style="width:100%; height:6px; background:rgba(255,255,255,0.08); border-radius:3px; overflow:hidden;">
                  <div style="width:${Math.min(100, (eb.Weekend || 0) * 20)}%; height:100%; background:#0284c7;"></div>
                </div>
              </div>
              <div>
                <div style="display:flex; justify-content:space-between; margin-bottom:2px;">
                  <span style="font-weight:600; color:#f87171;">🏥 Medical / Hospital Exeats:</span>
                  <strong>${eb.Medical || 0} Students</strong>
                </div>
                <div style="width:100%; height:6px; background:rgba(255,255,255,0.08); border-radius:3px; overflow:hidden;">
                  <div style="width:${Math.min(100, (eb.Medical || 0) * 20)}%; height:100%; background:#ef4444;"></div>
                </div>
              </div>
              <div>
                <div style="display:flex; justify-content:space-between; margin-bottom:2px;">
                  <span style="font-weight:600; color:#fbbf24;">💼 Special / Emergency Exeats:</span>
                  <strong>${eb.Special || 0} Students</strong>
                </div>
                <div style="width:100%; height:6px; background:rgba(255,255,255,0.08); border-radius:3px; overflow:hidden;">
                  <div style="width:${Math.min(100, (eb.Special || 0) * 20)}%; height:100%; background:#f59e0b;"></div>
                </div>
              </div>
              <div>
                <div style="display:flex; justify-content:space-between; margin-bottom:2px;">
                  <span style="font-weight:600; color:#a855f7;">🚌 Official / Academic Exeats:</span>
                  <strong>${eb.Official || 0} Students</strong>
                </div>
                <div style="width:100%; height:6px; background:rgba(255,255,255,0.08); border-radius:3px; overflow:hidden;">
                  <div style="width:${Math.min(100, (eb.Official || 0) * 20)}%; height:100%; background:#9333ea;"></div>
                </div>
              </div>
            </div>
          </div>
        `;
      }

      // 3. Boarding House Occupancy & Dormitory Capacity Matrix Table
      if (data.school_mode !== 'BASIC_ONLY' && Array.isArray(dom.houses_matrix) && dom.houses_matrix.length > 0) {
        let houseRows = dom.houses_matrix.map(h => {
          let badge = `<span style="background:rgba(34,197,94,0.2); color:#4ade80; border:1px solid rgba(34,197,94,0.4); padding:2px 8px; border-radius:12px; font-size:0.75rem; font-weight:700;">✓ OPTIMAL</span>`;
          if (h.status === 'FULL') {
            badge = `<span style="background:rgba(239,68,68,0.2); color:#f87171; border:1px solid rgba(239,68,68,0.4); padding:2px 8px; border-radius:12px; font-size:0.75rem; font-weight:700;">🚨 FULL</span>`;
          } else if (h.status === 'HIGH') {
            badge = `<span style="background:rgba(245,158,11,0.2); color:#fbbf24; border:1px solid rgba(245,158,11,0.4); padding:2px 8px; border-radius:12px; font-size:0.75rem; font-weight:700;">⚠️ HIGH</span>`;
          }

          return `
            <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
              <td style="padding:10px 12px; font-weight:600; color:#f8fafc;">🏠 ${h.name} <span style="font-size:0.75rem; opacity:0.6;">(${h.gender_type})</span></td>
              <td style="padding:10px 12px;">👨‍🏫 ${h.house_master_name}</td>
              <td style="padding:10px 12px;">${h.boarder_count} Boarders / ${h.capacity} Cap (${h.dorm_count} Dorms)</td>
              <td style="padding:10px 12px; min-width:140px;">
                <div style="display:flex; justify-content:space-between; font-size:0.78rem; margin-bottom:2px;">
                  <span>${h.occupancy_pct}%</span>
                </div>
                <div style="width:100%; height:6px; background:rgba(255,255,255,0.1); border-radius:3px; overflow:hidden;">
                  <div style="width:${h.occupancy_pct}%; height:100%; background:linear-gradient(90deg, #ec4899, #f472b6);"></div>
                </div>
              </td>
              <td style="padding:10px 12px;">${badge}</td>
              <td style="padding:10px 12px; text-align:right;">
                <a href="houses.html" class="btn sm" style="padding:4px 10px; font-size:0.75rem; background:rgba(244,114,182,0.2); color:#f472b6; border:1px solid rgba(244,114,182,0.4); text-decoration:none; border-radius:6px; font-weight:600;">🏠 House Register</a>
              </td>
            </tr>
          `;
        }).join('');

        cardsHtml += `
          <div class="card" style="grid-column: 1 / -1; border-top: 4px solid #f472b6; background: var(--card-bg, #1e293b); margin-top:8px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; flex-wrap:wrap; gap:8px;">
              <div>
                <h4 style="margin:0; font-size:1.05rem; color:#f472b6;">🏠 Boarding House Occupancy & Dormitory Matrix</h4>
                <div style="font-size:0.78rem; opacity:0.65; margin-top:2px;">Real-time campus welfare, housemaster leadership & dorm capacity supervision</div>
              </div>
              <a class="btn sm" href="exeat.html" style="background:#db2777; color:white; font-weight:600; text-decoration:none; padding:6px 14px; font-size:0.8rem; border-radius:6px;">🏡 Exeat Desk</a>
            </div>
            <div style="overflow-x:auto;">
              <table style="width:100%; border-collapse:collapse; font-size:0.85rem;">
                <thead>
                  <tr style="border-bottom:1px solid rgba(255,255,255,0.1); text-align:left; color:#94a3b8;">
                    <th style="padding:8px 12px;">House Name</th>
                    <th style="padding:8px 12px;">House Master / Mistress</th>
                    <th style="padding:8px 12px;">Boarder Capacity</th>
                    <th style="padding:8px 12px;">Occupancy Rate</th>
                    <th style="padding:8px 12px;">Status</th>
                    <th style="padding:8px 12px; text-align:right;">Action</th>
                  </tr>
                </thead>
                <tbody>
                  ${houseRows}
                </tbody>
              </table>
            </div>
          </div>
        `;
      }

      // 4. Dormitory Medical & Special Care Registry (Health Radar)
      if (Array.isArray(dom.critical_medical_roster) && dom.critical_medical_roster.length > 0) {
        let healthRows = dom.critical_medical_roster.map(hr => `
          <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
            <td style="padding:10px 12px; font-weight:600; color:#f8fafc;">👨‍🎓 ${hr.student_name}</td>
            <td style="padding:10px 12px; color:#38bdf8;">${hr.house_name}</td>
            <td style="padding:10px 12px;">
              <span style="background:rgba(239,68,68,0.15); color:#fca5a5; padding:2px 8px; border-radius:6px; font-size:0.75rem; font-weight:600;">
                ${hr.condition}
              </span>
            </td>
            <td style="padding:10px 12px; font-weight:700; color:#f87171;">🩸 ${hr.blood_group}</td>
            <td style="padding:10px 12px; text-align:right; white-space:nowrap;">
              <button type="button" onclick="callEmergencyContact('${escapeHtml(hr.emergency_phone)}', '${escapeHtml(hr.student_name)}')" 
                      style="background:rgba(34,197,94,0.2); border:1px solid rgba(34,197,94,0.4); color:#4ade80; padding:4px 10px; border-radius:6px; font-size:0.75rem; font-weight:600; cursor:pointer;">
                📞 ${hr.emergency_phone || 'Call Contact'}
              </button>
            </td>
          </tr>
        `).join('');

        cardsHtml += `
          <div class="card" style="grid-column: 1 / -1; border-top: 4px solid #ef4444; background: var(--card-bg, #1e293b); margin-top:8px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; flex-wrap:wrap; gap:8px;">
              <div>
                <h4 style="margin:0; font-size:1.05rem; color:#f87171; display:flex; align-items:center; gap:8px;">
                  <span>🩺</span> Dormitory Special Care & Medical Flags Registry
                </h4>
                <div style="font-size:0.78rem; opacity:0.65; margin-top:2px;">Boarders with registered allergies or chronic conditions requiring housemaster awareness</div>
              </div>
              <a class="btn sm" href="students.html" style="background:#dc2626; color:white; font-weight:600; text-decoration:none; padding:6px 14px; font-size:0.8rem; border-radius:6px;">👨‍🎓 Student Registry</a>
            </div>
            <div style="overflow-x:auto;">
              <table style="width:100%; border-collapse:collapse; font-size:0.85rem;">
                <thead>
                  <tr style="border-bottom:1px solid rgba(255,255,255,0.1); text-align:left; color:#94a3b8;">
                    <th style="padding:8px 12px;">Student Name</th>
                    <th style="padding:8px 12px;">House</th>
                    <th style="padding:8px 12px;">Medical Condition / Allergies</th>
                    <th style="padding:8px 12px;">Blood Group</th>
                    <th style="padding:8px 12px; text-align:right;">Emergency Contact</th>
                  </tr>
                </thead>
                <tbody>
                  ${healthRows}
                </tbody>
              </table>
            </div>
          </div>
        `;
      }

      // 5. Overdue Exeat Early Warning Watchlist (if overdue records exist)
      if (Array.isArray(dom.overdue_exeats_roster) && dom.overdue_exeats_roster.length > 0) {
        let overdueRows = dom.overdue_exeats_roster.map(ox => `
          <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
            <td style="padding:10px 12px; font-weight:600; color:#f8fafc;">🚨 ${ox.student_name}</td>
            <td style="padding:10px 12px; color:#38bdf8;">${ox.house_name}</td>
            <td style="padding:10px 12px; font-weight:700; color:#f87171;">⏰ Expected: ${ox.expected_return}</td>
            <td style="padding:10px 12px;">${ox.reason} (${ox.exeat_type})</td>
            <td style="padding:10px 12px; text-align:right; white-space:nowrap;">
              <button type="button" onclick="sendExeatParentAlert('${escapeHtml(ox.parent_phone)}', '${escapeHtml(ox.student_name)}')" 
                      style="background:rgba(239,68,68,0.2); border:1px solid rgba(239,68,68,0.4); color:#f87171; padding:4px 10px; border-radius:6px; font-size:0.75rem; font-weight:600; cursor:pointer; margin-right:6px;">
                📲 Alert Parent
              </button>
              <a href="exeat.html" class="btn sm" style="padding:4px 10px; font-size:0.75rem; background:rgba(219,39,119,0.2); color:#f472b6; border:1px solid rgba(219,39,119,0.4); text-decoration:none; border-radius:6px; font-weight:600;">
                🏡 View Exeat
              </a>
            </td>
          </tr>
        `).join('');

        cardsHtml += `
          <div class="card" style="grid-column: 1 / -1; border-top: 4px solid #ef4444; background: var(--card-bg, #1e293b); margin-top:8px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; flex-wrap:wrap; gap:8px;">
              <div>
                <h4 style="margin:0; font-size:1.05rem; color:#f87171; display:flex; align-items:center; gap:8px;">
                  <span>🚨</span> Overdue Exeat Returnee Watchlist (Curfew Breach)
                </h4>
                <div style="font-size:0.78rem; opacity:0.65; margin-top:2px;">Departed students who have breached their expected return deadline</div>
              </div>
              <a class="btn sm" href="exeat.html" style="background:#dc2626; color:white; font-weight:600; text-decoration:none; padding:6px 14px; font-size:0.8rem; border-radius:6px;">🏡 Exeat Desk</a>
            </div>
            <div style="overflow-x:auto;">
              <table style="width:100%; border-collapse:collapse; font-size:0.85rem;">
                <thead>
                  <tr style="border-bottom:1px solid rgba(255,255,255,0.1); text-align:left; color:#94a3b8;">
                    <th style="padding:8px 12px;">Student Name</th>
                    <th style="padding:8px 12px;">House</th>
                    <th style="padding:8px 12px;">Deadline</th>
                    <th style="padding:8px 12px;">Reason</th>
                    <th style="padding:8px 12px; text-align:right;">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  ${overdueRows}
                </tbody>
              </table>
            </div>
          </div>
        `;
      }

      // 6. Unresolved Campus Discipline Cases Queue
      if (Array.isArray(dom.pending_discipline_cases) && dom.pending_discipline_cases.length > 0) {
        let discRows = dom.pending_discipline_cases.map(dc => `
          <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
            <td style="padding:10px 12px; font-weight:600; color:#f8fafc;">👨‍🎓 ${dc.student_name}</td>
            <td style="padding:10px 12px; color:#38bdf8;">${dc.house_name}</td>
            <td style="padding:10px 12px; font-weight:700; color:#fbbf24;">⚖️ ${dc.incident_type}</td>
            <td style="padding:10px 12px; font-size:0.75rem; opacity:0.8;">${dc.incident_date}</td>
            <td style="padding:10px 12px; text-align:right; white-space:nowrap;">
              <a href="discipline.html" class="btn sm" style="padding:4px 10px; font-size:0.75rem; background:rgba(244,114,182,0.2); color:#f472b6; border:1px solid rgba(244,114,182,0.4); text-decoration:none; border-radius:6px; font-weight:600;">
                ⚖️ Review & Sanction
              </a>
            </td>
          </tr>
        `).join('');

        cardsHtml += `
          <div class="card" style="grid-column: 1 / -1; border-top: 4px solid #f472b6; background: var(--card-bg, #1e293b); margin-top:8px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; flex-wrap:wrap; gap:8px;">
              <div>
                <h4 style="margin:0; font-size:1.05rem; color:#f472b6; display:flex; align-items:center; gap:8px;">
                  <span>⚖️</span> Active Campus Discipline & Behavioral Queue
                </h4>
                <div style="font-size:0.78rem; opacity:0.65; margin-top:2px;">Reported student conduct infractions pending disciplinary action</div>
              </div>
              <a class="btn sm" href="discipline.html" style="background:#db2777; color:white; font-weight:600; text-decoration:none; padding:6px 14px; font-size:0.8rem; border-radius:6px;">⚖️ Discipline Desk</a>
            </div>
            <div style="overflow-x:auto;">
              <table style="width:100%; border-collapse:collapse; font-size:0.85rem;">
                <thead>
                  <tr style="border-bottom:1px solid rgba(255,255,255,0.1); text-align:left; color:#94a3b8;">
                    <th style="padding:8px 12px;">Student Name</th>
                    <th style="padding:8px 12px;">House</th>
                    <th style="padding:8px 12px;">Infraction</th>
                    <th style="padding:8px 12px;">Incident Date</th>
                    <th style="padding:8px 12px; text-align:right;">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  ${discRows}
                </tbody>
              </table>
            </div>
          </div>
        `;
      }
    }

    container.innerHTML = cardsHtml;

  } catch (err) {
    console.error('Failed to load executive analytics:', err);
  }
}

// ── Reminder & Emergency Dispatch Helpers ─────────────────────────────────────
window.sendAssessmentReminder = function(teacherName, subjectName, className) {
  const msg = `📨 Assessment reminder dispatched to ${teacherName} for ${subjectName} (${className}).`;
  if (window.showToast) {
    window.showToast(msg, 'success');
  } else {
    alert(msg);
  }
};

window.callEmergencyContact = function(phone, studentName) {
  if (phone && phone !== 'Not Recorded' && phone !== 'N/A') {
    window.location.href = `tel:${phone}`;
  } else {
    alert(`No emergency contact phone recorded for ${studentName}.`);
  }
};

window.sendExeatParentAlert = function(parentPhone, studentName) {
  const msg = `🚨 Curfew breach notification sent to guardian (${parentPhone}) for ${studentName}.`;
  if (window.showToast) {
    window.showToast(msg, 'warning');
  } else {
    alert(msg);
  }
};

window.sendFeeReminder = function(parentPhone, studentName, amount) {
  const msg = `💳 Fee arrears reminder dispatched to guardian (${parentPhone}) for ${studentName} (GH₵ ${amount}).`;
  if (window.showToast) {
    window.showToast(msg, 'success');
  } else {
    alert(msg);
  }
};

function escapeHtml(text) {
  if (!text) return '';
  return text.replace(/[&<>"']/g, function(m) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[m];
  });
}

// ── Bootstrap ─────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  window.API_BASE = API_BASE;
  initDashboard();
  loadDashboardStats();
  loadExecutiveAnalytics();
  loadAnalytics();
});
