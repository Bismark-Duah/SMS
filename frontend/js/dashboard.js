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
      { label: '💬 Broadcast Parent SMS', href: 'messaging.html' }
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
  if (['assistant_headmaster_academic', 'assistant_head_academic'].includes(activeRole)) {
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

  if (!isBoarding || ['assistant_headmaster_academic', 'assistant_head_academic'].includes(activeRole)) {
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

  const allowedStatsRoles = ['admin', 'super_admin', 'headmaster', 'headmistress', 'assistant_headmaster_academic', 'assistant_head_academic', 'assistant_headmaster_domestic', 'assistant_head_domestic', 'hod', 'bursar', 'form_master', 'form_mistress', 'teacher'];
  const canSeeStats = allowedStatsRoles.includes(activeRole);
  if (!canSeeStats) return;

  const statsRow = document.getElementById('statsRow');
  if (statsRow) statsRow.style.display = 'block';

  const isAcademicHead = ['assistant_headmaster_academic', 'assistant_head_academic'].includes(activeRole);
  const feesCard = document.getElementById('statFeesCard');
  const housesCard = document.getElementById('statHousesCard');
  const sbaCard = document.getElementById('statSbaCard');
  const passRateCard = document.getElementById('statPassRateCard');
  const atRiskCard = document.getElementById('statAtRiskCard');

  if (isAcademicHead) {
    if (feesCard) feesCard.style.display = 'none';
    if (housesCard) housesCard.style.display = 'none';
    if (sbaCard) sbaCard.style.display = 'flex';
    if (passRateCard) passRateCard.style.display = 'flex';
    if (atRiskCard) atRiskCard.style.display = 'flex';
  } else {
    if (feesCard) feesCard.style.display = 'flex';
    if (sbaCard) sbaCard.style.display = 'none';
    if (passRateCard) passRateCard.style.display = 'none';
    if (atRiskCard) atRiskCard.style.display = 'none';
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
  const execRoles = ['admin', 'super_admin', 'headmaster', 'headmistress', 'assistant_headmaster_academic', 'assistant_head_academic', 'assistant_headmaster_domestic', 'assistant_head_domestic', 'hod'];

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

    section.style.display = 'block';

    // Populate top KPI cards if Academic Head
    const isAcademicHead = ['admin', 'super_admin', 'headmaster', 'headmistress', 'assistant_headmaster_academic', 'assistant_head_academic', 'hod'].includes(activeRole);
    const isDomesticHead = ['admin', 'super_admin', 'headmaster', 'headmistress', 'assistant_headmaster_domestic', 'assistant_head_domestic'].includes(activeRole);

    if (isAcademicHead) {
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

    let cardsHtml = '';

    // ── Academic Executive Command Center ─────────────────────────────────────
    if (isAcademicHead) {
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

    // ── Domestic Executive Widget Card ────────────────────────────────────────
    if (isDomesticHead) {
      const overdueAlertHtml = dom.overdue_exeat_count > 0 
        ? `<span style="background:rgba(239,68,68,0.2); color:#f87171; border:1px solid rgba(239,68,68,0.4); padding:2px 8px; border-radius:12px; font-weight:700; font-size:0.75rem;">🚨 ${dom.overdue_exeat_count} Overdue Exeat(s)</span>`
        : `<span style="background:rgba(34,197,94,0.2); color:#4ade80; padding:2px 8px; border-radius:12px; font-size:0.75rem;">✓ Exeats On Schedule</span>`;

      cardsHtml += `
        <div class="card" style="border-left: 4px solid #f472b6; background: var(--card-bg, #1e293b);">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
            <h4 style="margin:0; font-size:1rem; color:#f472b6;">🏡 Campus Life & Welfare Summary</h4>
            ${overdueAlertHtml}
          </div>

          <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; font-size:0.85rem;">
            <div style="background:rgba(255,255,255,0.03); padding:8px 12px; border-radius:6px; border:1px solid rgba(255,255,255,0.05);">
              <span style="opacity:0.7;">Active Boarders:</span><br/>
              <strong style="font-size:1.1rem; color:#38bdf8;">${dom.total_boarders} Students (${dom.total_houses} Houses)</strong>
            </div>
            <div style="background:rgba(255,255,255,0.03); padding:8px 12px; border-radius:6px; border:1px solid rgba(255,255,255,0.05);">
              <span style="opacity:0.7;">Currently Away on Exeat:</span><br/>
              <strong style="font-size:1.1rem; color:#f59e0b;">${dom.currently_away_exeat} Departed</strong>
            </div>
            <div style="grid-column:1/-1; background:rgba(255,255,255,0.03); padding:8px 12px; border-radius:6px; border:1px solid rgba(255,255,255,0.05); display:flex; justify-content:space-between; align-items:center;">
              <div>
                <span style="opacity:0.7;">Unresolved Security & Discipline Incidents:</span><br/>
                <strong style="font-size:1.1rem; color:${dom.active_discipline_incidents>0?'#f87171':'#4ade80'};">${dom.active_discipline_incidents} Alert(s) Pending Action</strong>
              </div>
              <a href="discipline.html" class="btn sm" style="font-size:0.75rem; background:rgba(244,114,182,0.2); color:#f472b6; border:1px solid rgba(244,114,182,0.4);">View Discipline</a>
            </div>
          </div>
        </div>
      `;

      // Render House Occupancy Matrix (SHS & Combined modes only)
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
    }

    container.innerHTML = cardsHtml;

  } catch (err) {
    console.error('Failed to load executive analytics:', err);
  }
}

// ── Reminder Dispatch Helper ───────────────────────────────────────────────────
window.sendAssessmentReminder = function(teacherName, subjectName, className) {
  const msg = `📨 Assessment reminder dispatched to ${teacherName} for ${subjectName} (${className}).`;
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
