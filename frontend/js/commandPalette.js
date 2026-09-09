/**
 * commandPalette.js — Enterprise Universal Command Palette (Ctrl + K)
 * Fast, keyboard-driven navigation, student search, school scope switching, and theme controls.
 * 100% Vanilla JavaScript & Offline-First.
 */

(function () {
  'use strict';

  const API_BASE = window.API_BASE || (window.location.origin.includes('http') ? (window.location.origin + '/api') : 'http://127.0.0.1:8000/api');

  function getToken() {
    return localStorage.getItem('accessToken');
  }

  function getUserRoles() {
    try {
      const raw = sessionStorage.getItem('userRoles') || localStorage.getItem('userRoles');
      if (raw) return JSON.parse(raw).map(r => r.toLowerCase());
      const single = localStorage.getItem('userRole') || '';
      return [single.toLowerCase()];
    } catch {
      return [(localStorage.getItem('userRole') || '').toLowerCase()];
    }
  }

  function isSuperAdmin() {
    const roles = getUserRoles();
    return localStorage.getItem('is_super_admin') === 'true' ||
           localStorage.getItem('username') === 'superadmin' ||
           roles.includes('super_admin');
  }

  function getHeaders(headers = {}) {
    const token = getToken();
    const h = { ...headers };
    if (token) h['Authorization'] = `Bearer ${token}`;
    const schoolId = sessionStorage.getItem('school_id') || localStorage.getItem('school_id');
    if (schoolId && schoolId !== 'all') h['X-School-Id'] = schoolId;
    return h;
  }

  // ── Navigation Catalog ─────────────────────────────────────────────────────
  const NAV_ITEMS = [
    { title: 'Dashboard & Analytics', url: 'dashboard.html', icon: '📊', category: 'Pages', keywords: 'home overview kpis analytics stats charts' },
    { title: 'Students Roster & Enrollment', url: 'students.html', icon: '👥', category: 'Pages', keywords: 'students admission enroll cssps guardians profile' },
    { title: 'Broadsheet & Terminal Marks', url: 'broadsheet.html', icon: '📑', category: 'Pages', keywords: 'broadsheet grades marks assessment positions ranks transcripts' },
    { title: 'Teacher Score Entry', url: 'scores.html', icon: '📝', category: 'Pages', keywords: 'scores sba exam marks enter grading continuous assessment' },
    { title: 'Student Attendance Register', url: 'attendance.html', icon: '📅', category: 'Pages', keywords: 'attendance present absent roll call daily period exeat' },
    { title: 'Class Sections & Stages', url: 'classes.html', icon: '🏫', category: 'Pages', keywords: 'classes form arms streams levels stages form master' },
    { title: 'Subjects & Classifications', url: 'subjects.html', icon: '📚', category: 'Pages', keywords: 'subjects core elective wassce ncca curriculum stem' },
    { title: 'Academic Programs & Tracks', url: 'programs.html', icon: '🎓', category: 'Pages', keywords: 'programs courses tracks packages combinations general science arts' },
    { title: 'Academic Departments & HODs', url: 'departments.html', icon: '🏛️', category: 'Pages', keywords: 'departments faculty hod head of department teachers' },
    { title: 'Fees & Financial Billing', url: 'fees.html', icon: '💰', category: 'Pages', keywords: 'fees billing receipts payments transactions arrears invoices' },
    { title: 'Timetable & Scheduling', url: 'timetable.html', icon: '⏰', category: 'Pages', keywords: 'timetable master schedule rooms periods free periods teacher schedule' },
    { title: 'Terminal Report Cards', url: 'report-card.html', icon: '📜', category: 'Pages', keywords: 'report cards print term remarks terminal summary pdf' },
    { title: 'Cumulative Academic Record', url: 'cumulative-record.html', icon: '🗂️', category: 'Pages', keywords: 'cumulative continuous history folder 3-year record' },
    { title: 'Boarding Houses & Dormitories', url: 'houses.html', icon: '🏠', category: 'Pages', keywords: 'houses boarding dorms housemaster bed allocation' },
    { title: 'Exeat & Gate Permissions', url: 'exeat.html', icon: '🎫', category: 'Pages', keywords: 'exeat pass gate security exit permission weekend medical' },
    { title: 'Disciplinary Records', url: 'discipline.html', icon: '⚖️', category: 'Pages', keywords: 'discipline offense suspension warning misconduct record' },
    { title: 'Staff & User Management', url: 'users.html', icon: '👤', category: 'Pages', keywords: 'users staff accounts teachers passwords roles permissions' },
    { title: 'System Settings & Branding', url: 'settings.html', icon: '⚙️', category: 'Pages', keywords: 'settings config branding crest theme backup general mode' },
    { title: 'Master Multi-Tenant Portal', url: 'super-admin.html', icon: '🌐', category: 'Pages', superAdminOnly: true, keywords: 'super admin master schools cloud database operations subscriptions' },
  ];

  // ── Action Items ───────────────────────────────────────────────────────────
  const ACTION_ITEMS = [
    { title: 'Switch Theme: ☀️ Clean Light', icon: '☀️', category: 'Theme', action: () => window.applyTheme && window.applyTheme('light'), keywords: 'light mode theme day clean' },
    { title: 'Switch Theme: 🌙 Midnight Dark', icon: '🌙', category: 'Theme', action: () => window.applyTheme && window.applyTheme('dark'), keywords: 'dark mode theme night midnight' },
    { title: 'Switch Theme: 🌿 Emerald Oasis', icon: '🌿', category: 'Theme', action: () => window.applyTheme && window.applyTheme('emerald'), keywords: 'emerald green theme nature' },
    { title: 'Switch Theme: 🌊 Ocean Sapphire', icon: '🌊', category: 'Theme', action: () => window.applyTheme && window.applyTheme('ocean'), keywords: 'ocean blue sapphire sea theme' },
    { title: 'Table Density: Compact Mode', icon: '📐', category: 'Preferences', action: () => window.setDensity && window.setDensity('compact'), keywords: 'table density compact small dense rows' },
    { title: 'Table Density: Comfortable Mode', icon: '📏', category: 'Preferences', action: () => window.setDensity && window.setDensity('comfortable'), keywords: 'table density comfortable spacious wide rows' },
    { title: 'Table Density: Default Mode', icon: '⚖️', category: 'Preferences', action: () => window.setDensity && window.setDensity('default'), keywords: 'table density default standard normal rows' },
    { title: 'Log Out of Session', icon: '🚪', category: 'Account', action: () => window.logout ? window.logout() : (localStorage.clear(), window.location.href = 'auth.html'), keywords: 'logout exit sign out leave' }
  ];

  let cachedSchools = [];
  let studentSearchTimer = null;
  let activeIndex = 0;
  let currentResults = [];
  let modalCreated = false;

  // ── DOM Elements ───────────────────────────────────────────────────────────
  let backdropEl, modalEl, inputEl, resultsEl;

  function createPaletteDOM() {
    if (modalCreated || document.getElementById('cmdPaletteBackdrop')) return;

    backdropEl = document.createElement('div');
    backdropEl.id = 'cmdPaletteBackdrop';
    backdropEl.className = 'cmd-palette-backdrop';

    modalEl = document.createElement('div');
    modalEl.id = 'cmdPaletteModal';
    modalEl.className = 'cmd-palette-modal';

    modalEl.innerHTML = `
      <div class="cmd-palette-header">
        <span class="cmd-palette-search-icon">🔍</span>
        <input 
          type="text" 
          id="cmdPaletteInput" 
          class="cmd-palette-input" 
          placeholder="Type a page, @student name, >command, or school..." 
          autocomplete="off" 
          spellcheck="false"
        />
        <span class="cmd-palette-esc-badge" title="Press Escape to close">ESC</span>
      </div>

      <div class="cmd-palette-quick-chips">
        <button type="button" class="cmd-chip active" data-filter="all">🌟 All</button>
        <button type="button" class="cmd-chip" data-filter="pages">📄 Pages</button>
        <button type="button" class="cmd-chip" data-filter="students">👤 Students</button>
        <button type="button" class="cmd-chip" data-filter="themes">🎨 Themes</button>
        ${isSuperAdmin() ? '<button type="button" class="cmd-chip" data-filter="schools">🏫 Schools</button>' : ''}
      </div>

      <div id="cmdPaletteResults" class="cmd-palette-results"></div>

      <div class="cmd-palette-footer">
        <div class="cmd-palette-hints">
          <span><kbd>↑</kbd><kbd>↓</kbd> Navigate</span>
          <span><kbd>↵</kbd> Select</span>
          <span><kbd>ESC</kbd> Close</span>
          <span style="opacity:0.75; margin-left:8px;">💡 Tip: Type <kbd>@</kbd> for students</span>
        </div>
      </div>
    `;

    backdropEl.appendChild(modalEl);
    document.body.appendChild(backdropEl);

    inputEl = modalEl.querySelector('#cmdPaletteInput');
    resultsEl = modalEl.querySelector('#cmdPaletteResults');

    // Event listeners
    backdropEl.addEventListener('click', (e) => {
      if (e.target === backdropEl) closePalette();
    });

    inputEl.addEventListener('input', handleSearchInput);
    inputEl.addEventListener('keydown', handleKeyNavigation);

    modalEl.querySelectorAll('.cmd-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        modalEl.querySelectorAll('.cmd-chip').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        const filter = chip.getAttribute('data-filter');
        if (filter === 'students') {
          if (!inputEl.value.startsWith('@')) inputEl.value = '@ ' + inputEl.value.trim();
        } else if (filter === 'schools') {
          if (!inputEl.value.startsWith('> school')) inputEl.value = '> school ' + inputEl.value.replace(/^>/, '').trim();
        } else if (filter === 'themes') {
          if (!inputEl.value.startsWith('> theme')) inputEl.value = '> theme ';
        } else if (filter === 'pages') {
          inputEl.value = inputEl.value.replace(/^[@>]\s*/, '');
        }
        inputEl.focus();
        handleSearchInput();
      });
    });

    modalCreated = true;
  }

  // ── Open / Close ───────────────────────────────────────────────────────────
  function openPalette(initialQuery = '') {
    if (!getToken()) return; // Don't open on unauthenticated pages
    createPaletteDOM();

    backdropEl.classList.add('active');
    document.body.style.overflow = 'hidden';

    if (initialQuery) {
      inputEl.value = initialQuery;
    } else {
      inputEl.value = '';
    }

    activeIndex = 0;
    inputEl.focus();
    renderResults();

    // Fetch schools for Super Admins in background
    if (isSuperAdmin() && cachedSchools.length === 0) {
      fetchSchools();
    }
  }

  function closePalette() {
    if (!backdropEl) return;
    backdropEl.classList.remove('active');
    document.body.style.overflow = '';
    if (inputEl) inputEl.value = '';
  }

  async function fetchSchools() {
    try {
      const res = await fetch(`${API_BASE}/super-admin/schools`, { headers: getHeaders() });
      if (res.ok) {
        cachedSchools = await res.json();
      }
    } catch (_) {}
  }

  // ── Search & Filter Logic ──────────────────────────────────────────────────
  function handleSearchInput() {
    const rawVal = inputEl.value.trim();
    if (rawVal.startsWith('@') && rawVal.length >= 2) {
      // Debounce student search
      clearTimeout(studentSearchTimer);
      studentSearchTimer = setTimeout(() => {
        searchStudents(rawVal.substring(1).trim());
      }, 250);
    } else {
      clearTimeout(studentSearchTimer);
      renderResults();
    }
  }

  async function searchStudents(query) {
    if (!query) {
      renderResults();
      return;
    }
    resultsEl.innerHTML = '<div class="cmd-empty-state"><span class="cmd-spinner">⏳</span> Searching student roster...</div>';
    
    try {
      const res = await fetch(`${API_BASE}/students/?limit=10&search=${encodeURIComponent(query)}`, { headers: getHeaders() });
      if (res.ok) {
        const students = await res.json();
        const studentItems = (students || []).map(s => {
          const fullName = s.full_name || `${s.first_name || ''} ${s.last_name || ''}`.trim() || 'Student';
          const code = s.student_code || s.bece_index_number || s.enrolment_code || 'ID: ' + s.id;
          const className = s.class_section ? s.class_section.name : (s.class_name || 'Unassigned');
          return {
            title: fullName,
            subtitle: `${code} • Class: ${className} • ${s.residential_status === 'B' ? '🏠 Boarding' : '🎒 Day'}`,
            icon: '👤',
            category: 'Students',
            action: () => {
              window.location.href = `students.html?search=${encodeURIComponent(code)}`;
            }
          };
        });

        currentResults = studentItems;
        activeIndex = 0;
        displayResults(currentResults, 'Students matching "' + query + '"');
      } else {
        renderResults();
      }
    } catch (e) {
      renderResults();
    }
  }

  function renderResults() {
    const query = (inputEl ? inputEl.value : '').toLowerCase().trim();
    const isSuper = isSuperAdmin();

    let list = [];

    // 1. Navigation items
    const allowedNav = NAV_ITEMS.filter(item => {
      if (item.superAdminOnly && !isSuper) return false;
      return true;
    });

    if (!query) {
      // Default initial state: Top Pages + Quick Actions + School context
      list = [
        ...allowedNav.slice(0, 7).map(item => ({
          ...item,
          action: () => window.location.href = item.url
        })),
        ...ACTION_ITEMS.slice(0, 4)
      ];
    } else if (query.startsWith('>')) {
      // Action/Theme command mode
      const cleanQ = query.replace(/^>\s*/, '').toLowerCase();
      list = ACTION_ITEMS.filter(a => 
        a.title.toLowerCase().includes(cleanQ) || 
        a.keywords.toLowerCase().includes(cleanQ)
      );
      if (isSuper && 'switch schools tenant'.includes(cleanQ)) {
        list.push(...cachedSchools.map(s => ({
          title: `Switch Tenant: ${s.name}`,
          subtitle: `Code: ${s.code || 'SCH'} • Mode: ${s.school_mode || 'SHS'}`,
          icon: '🏫',
          category: 'Tenant Schools',
          action: () => {
            if (window.enterSchoolView) window.enterSchoolView(s.id, s.name);
            else {
              sessionStorage.setItem('school_id', s.id);
              sessionStorage.setItem('school_name', s.name);
              sessionStorage.setItem('is_super_admin_viewing', 'true');
              window.location.reload();
            }
          }
        })));
      }
    } else {
      // General fuzzy match across pages, actions, and schools
      const navMatches = allowedNav.filter(item => 
        item.title.toLowerCase().includes(query) || 
        item.keywords.toLowerCase().includes(query)
      ).map(item => ({
        ...item,
        action: () => window.location.href = item.url
      }));

      const actionMatches = ACTION_ITEMS.filter(a => 
        a.title.toLowerCase().includes(query) || 
        a.keywords.toLowerCase().includes(query)
      );

      let schoolMatches = [];
      if (isSuper && cachedSchools.length > 0) {
        schoolMatches = cachedSchools.filter(s => 
          s.name.toLowerCase().includes(query) || 
          (s.code && s.code.toLowerCase().includes(query))
        ).map(s => ({
          title: `Switch to: ${s.name}`,
          subtitle: `Code: ${s.code || 'SCH'} • Mode: ${s.school_mode || 'SHS'}`,
          icon: '🏫',
          category: 'Schools',
          action: () => {
            if (window.enterSchoolView) window.enterSchoolView(s.id, s.name);
            else {
              sessionStorage.setItem('school_id', s.id);
              sessionStorage.setItem('school_name', s.name);
              sessionStorage.setItem('is_super_admin_viewing', 'true');
              window.location.reload();
            }
          }
        }));
      }

      list = [...navMatches, ...schoolMatches, ...actionMatches];
    }

    currentResults = list;
    activeIndex = 0;
    displayResults(currentResults, query ? `Results for "${query}"` : 'Quick Jump');
  }

  function displayResults(items, title) {
    if (!resultsEl) return;

    if (!items || items.length === 0) {
      resultsEl.innerHTML = `
        <div class="cmd-empty-state">
          <span style="font-size:2rem; display:block; margin-bottom:8px;">🔍</span>
          <p style="margin:0 0 4px; font-weight:600; color:var(--text-primary);">No matching items found</p>
          <p style="margin:0; font-size:0.82rem; color:var(--text-secondary);">Try searching for a page name, <kbd>@</kbd> for students, or <kbd>&gt;</kbd> for actions.</p>
        </div>
      `;
      return;
    }

    // Group by category
    const categories = {};
    items.forEach((item, idx) => {
      const cat = item.category || 'General';
      if (!categories[cat]) categories[cat] = [];
      categories[cat].push({ ...item, globalIndex: idx });
    });

    let html = '';
    Object.keys(categories).forEach(catName => {
      html += `<div class="cmd-category-header">${catName}</div>`;
      categories[catName].forEach(item => {
        const isSelected = item.globalIndex === activeIndex;
        html += `
          <div 
            class="cmd-result-item ${isSelected ? 'active' : ''}" 
            data-index="${item.globalIndex}"
          >
            <span class="cmd-item-icon">${item.icon || '📄'}</span>
            <div class="cmd-item-text">
              <div class="cmd-item-title">${escapeHtml(item.title)}</div>
              ${item.subtitle ? `<div class="cmd-item-subtitle">${escapeHtml(item.subtitle)}</div>` : ''}
            </div>
            <span class="cmd-item-action-hint">Jump ↵</span>
          </div>
        `;
      });
    });

    resultsEl.innerHTML = html;

    // Attach click handlers & hover sync
    resultsEl.querySelectorAll('.cmd-result-item').forEach(el => {
      el.addEventListener('click', () => {
        const idx = parseInt(el.getAttribute('data-index'), 10);
        executeItem(idx);
      });
      el.addEventListener('mouseenter', () => {
        const idx = parseInt(el.getAttribute('data-index'), 10);
        setActiveIndex(idx, false);
      });
    });

    scrollToActive();
  }

  function setActiveIndex(newIdx, scroll = true) {
    if (newIdx < 0) newIdx = currentResults.length - 1;
    if (newIdx >= currentResults.length) newIdx = 0;
    activeIndex = newIdx;

    const items = resultsEl.querySelectorAll('.cmd-result-item');
    items.forEach(el => {
      const idx = parseInt(el.getAttribute('data-index'), 10);
      el.classList.toggle('active', idx === activeIndex);
    });

    if (scroll) scrollToActive();
  }

  function scrollToActive() {
    const activeEl = resultsEl.querySelector('.cmd-result-item.active');
    if (activeEl) {
      activeEl.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
  }

  function executeItem(idx) {
    const item = currentResults[idx];
    if (!item) return;
    closePalette();
    if (typeof item.action === 'function') {
      item.action();
    } else if (item.url) {
      window.location.href = item.url;
    }
  }

  function handleKeyNavigation(e) {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIndex(activeIndex + 1);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIndex(activeIndex - 1);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      executeItem(activeIndex);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      closePalette();
    }
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str).replace(/[&<>"']/g, m => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[m]));
  }

  // ── Global Keyboard Listener ───────────────────────────────────────────────
  document.addEventListener('keydown', (e) => {
    // Ctrl + K or Cmd + K
    if ((e.ctrlKey || e.metaKey) && (e.key === 'k' || e.key === 'K')) {
      e.preventDefault();
      if (backdropEl && backdropEl.classList.contains('active')) {
        closePalette();
      } else {
        openPalette();
      }
      return;
    }

    // '/' trigger (only when not typing in form inputs)
    if (e.key === '/' && !['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName)) {
      e.preventDefault();
      openPalette();
      return;
    }

    // Escape closes palette if open
    if (e.key === 'Escape' && backdropEl && backdropEl.classList.contains('active')) {
      closePalette();
    }
  });

  // Export to window
  window.openCommandPalette = openPalette;
  window.closeCommandPalette = closePalette;

})();
