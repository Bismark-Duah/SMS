/**
 * theme.js — Theme Management & Offline Logo Color Extractor
 * Supports: Midnight Dark, Light Executive, Emerald Oasis, Ocean Sapphire, and Auto-Logo Branding
 */

(function () {
  // Immediately enforce sidebar layout mode for application pages (excluding public landing, auth, and student portals)
  const _initialPage = (window.location.pathname.split("/").pop() || "").toLowerCase();
  const _publicPages = ["index.html", "auth.html", "login.html", "enrollment.html", "parent-view.html", ""];
  if (!_publicPages.includes(_initialPage)) {
    document.documentElement.setAttribute("data-layout", "sidebar");
  }

  // ── 1. Color Utility Functions ─────────────────────────────────────────────
  function rgbToHex(r, g, b) {
    return "#" + [r, g, b].map(x => {
      const hex = x.toString(16);
      return hex.length === 1 ? "0" + hex : hex;
    }).join("");
  }

  function adjustBrightness(hex, percent) {
    let num = parseInt(hex.replace("#", ""), 16),
      amt = Math.round(2.55 * percent),
      R = (num >> 16) + amt,
      G = (num >> 8 & 0x00FF) + amt,
      B = (num & 0x0000FF) + amt;
    return "#" + (
      0x1000000 +
      (R < 255 ? (R < 1 ? 0 : R) : 255) * 0x10000 +
      (G < 255 ? (G < 1 ? 0 : G) : 255) * 0x100 +
      (B < 255 ? (B < 1 ? 0 : B) : 255)
    ).toString(16).slice(1);
  }

  // ── 2. Offline HTML5 Canvas Logo Color Extractor ─────────────────────────
  window.extractLogoColors = function (imgSrc, callback) {
    if (!imgSrc) return;
    const img = new Image();
    img.crossOrigin = "Anonymous";
    img.onload = function () {
      try {
        const canvas = document.createElement("canvas");
        const ctx = canvas.getContext("2d");
        canvas.width = 100;
        canvas.height = 100;
        ctx.drawImage(img, 0, 0, 100, 100);

        const imgData = ctx.getImageData(0, 0, 100, 100).data;
        const colorCounts = {};

        for (let i = 0; i < imgData.length; i += 4) {
          const r = imgData[i];
          const g = imgData[i + 1];
          const b = imgData[i + 2];
          const a = imgData[i + 3];

          // Skip transparent or near-white / near-black background pixels
          if (a < 128) continue;
          if (r > 235 && g > 235 && b > 235) continue;
          if (r < 20 && g < 20 && b < 20) continue;

          // Quantize color into buckets of 16 for clustering
          const qr = Math.floor(r / 16) * 16;
          const qg = Math.floor(g / 16) * 16;
          const qb = Math.floor(b / 16) * 16;
          const key = `${qr},${qg},${qb}`;

          colorCounts[key] = (colorCounts[key] || 0) + 1;
        }

        const sortedColors = Object.keys(colorCounts).sort(
          (a, b) => colorCounts[b] - colorCounts[a]
        );

        if (sortedColors.length > 0) {
          const [r1, g1, b1] = sortedColors[0].split(",").map(Number);
          const primaryHex = rgbToHex(r1, g1, b1);
          let secondaryHex = "#06b6d4";

          if (sortedColors.length > 1) {
            const [r2, g2, b2] = sortedColors[1].split(",").map(Number);
            secondaryHex = rgbToHex(r2, g2, b2);
          }

          const extracted = {
            primary: primaryHex,
            primaryHover: adjustBrightness(primaryHex, -15),
            secondary: secondaryHex
          };

          localStorage.setItem("logo_theme_colors", JSON.stringify(extracted));
          if (callback) callback(extracted);
        }
      } catch (e) {
        console.warn("Canvas logo color extraction failed (non-critical):", e);
      }
    };
    img.src = imgSrc;
  };

  // ── 3. Theme Application & Enterprise State Bus ───────────────────────────
  if (!window.SMSStateBus) {
    const CHANNEL_NAME = 'sms_enterprise_bus';
    let broadcastChannel = null;
    try {
      if (typeof window.BroadcastChannel === 'function') {
        broadcastChannel = new BroadcastChannel(CHANNEL_NAME);
      }
    } catch (_) {}

    const _store = new Map();
    const _subscribers = new Map();

    window.SMSStateBus = {
      version: '2.0.0',
      get(key, defaultValue = null) {
        if (_store.has(key)) return _store.get(key);
        try {
          const stored = localStorage.getItem(key);
          if (stored !== null) {
            try {
              const parsed = JSON.parse(stored);
              _store.set(key, parsed);
              return parsed;
            } catch (_) {
              _store.set(key, stored);
              return stored;
            }
          }
        } catch (_) {}
        return defaultValue;
      },
      set(key, value, options = {}) {
        _store.set(key, value);
        try {
          if (typeof value === 'object' && value !== null) {
            localStorage.setItem(key, JSON.stringify(value));
          } else if (value === null || value === undefined) {
            localStorage.removeItem(key);
          } else {
            localStorage.setItem(key, String(value));
          }
        } catch (_) {}
        if (_subscribers.has(key)) {
          _subscribers.get(key).forEach(cb => { try { cb(value); } catch (_) {} });
        }
        window.dispatchEvent(new CustomEvent(`sms:${key}`, { detail: { key, value } }));
        if (!options.skipBroadcast && broadcastChannel) {
          try { broadcastChannel.postMessage({ type: 'STATE_CHANGE', key, value, timestamp: Date.now() }); } catch (_) {}
        }
        return value;
      },
      subscribe(key, cb) {
        if (!_subscribers.has(key)) _subscribers.set(key, new Set());
        _subscribers.get(key).add(cb);
        const cur = this.get(key);
        if (cur !== null && cur !== undefined) { try { cb(cur); } catch (_) {} }
        return () => { if (_subscribers.has(key)) _subscribers.get(key).delete(cb); };
      },
      setTheme(themeName, customColors) {
        const selectedTheme = themeName || this.get('system_theme', 'midnight');
        this.set('system_theme', selectedTheme);
        const root = document.documentElement;
        if (selectedTheme === 'auto') {
          let colors = customColors;
          if (!colors) { try { colors = JSON.parse(localStorage.getItem('logo_theme_colors')); } catch (_) {} }
          if (colors && colors.primary) {
            root.setAttribute('data-theme', 'auto');
            root.style.setProperty('--primary', colors.primary);
            root.style.setProperty('--primary-hover', colors.primaryHover || adjustBrightness(colors.primary, -15));
            root.style.setProperty('--primary-light', colors.primary + '26');
            root.style.setProperty('--secondary', colors.secondary || '#06b6d4');
            const hex = colors.primary.replace('#', '');
            const r = parseInt(hex.substring(0, 2), 16) || 0;
            const g = parseInt(hex.substring(2, 4), 16) || 0;
            const b = parseInt(hex.substring(4, 6), 16) || 0;
            const lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
            if (lum > 0.7) {
              root.style.setProperty('--bg', '#0f172a');
              root.style.setProperty('--bg-gradient', `radial-gradient(circle at top right, ${colors.primary}22, #0f172a 70%)`);
              root.style.setProperty('--card-bg', 'rgba(30, 41, 59, 0.85)');
              root.style.setProperty('--border-color', `${colors.primary}33`);
              root.style.setProperty('--text-primary', '#f8fafc');
              root.style.setProperty('--text-secondary', '#94a3b8');
              root.style.setProperty('--input-bg', 'rgba(15, 23, 42, 0.7)');
            } else {
              root.style.setProperty('--bg', '#f8fafc');
              root.style.setProperty('--bg-gradient', `linear-gradient(135deg, ${colors.primary}12 0%, #f1f5f9 100%)`);
              root.style.setProperty('--card-bg', '#ffffff');
              root.style.setProperty('--border-color', `${colors.primary}30`);
              root.style.setProperty('--text-primary', '#0f172a');
              root.style.setProperty('--text-secondary', '#475569');
              root.style.setProperty('--input-bg', '#ffffff');
            }
          }
        } else {
          root.style.removeProperty('--primary');
          root.style.removeProperty('--primary-hover');
          root.style.removeProperty('--primary-light');
          root.style.removeProperty('--secondary');
          root.style.removeProperty('--bg');
          root.style.removeProperty('--bg-gradient');
          root.style.removeProperty('--card-bg');
          root.style.removeProperty('--border-color');
          root.style.removeProperty('--text-primary');
          root.style.removeProperty('--text-secondary');
          root.style.removeProperty('--input-bg');
          root.setAttribute('data-theme', selectedTheme);
        }
        document.querySelectorAll('#guardThemeSelect, #system_theme, select[name="theme"]').forEach(sel => {
          if (sel && sel.value !== selectedTheme) sel.value = selectedTheme;
        });
        window.dispatchEvent(new CustomEvent('themechange', { detail: { theme: selectedTheme } }));
        return selectedTheme;
      },
      updateBranding(payload = {}) {
        if (window.applyBranding) window.applyBranding(payload);
      },
      broadcastLogout() {
        try {
          localStorage.removeItem('accessToken');
          localStorage.removeItem('token');
          localStorage.removeItem('userRole');
          localStorage.removeItem('activeRole');
        } catch (_) {}
        if (broadcastChannel) {
          try { broadcastChannel.postMessage({ type: 'AUTH_LOGOUT', timestamp: Date.now() }); } catch (_) {}
        }
        window.location.href = 'auth.html';
      }
    };
    window.SMSState = window.SMSStateBus;

    if (broadcastChannel) {
      broadcastChannel.onmessage = function (ev) {
        const msg = ev.data;
        if (!msg || typeof msg !== 'object') return;
        if (msg.type === 'STATE_CHANGE' && msg.key === 'system_theme') {
          window.SMSStateBus.setTheme(msg.value);
        } else if (msg.type === 'AUTH_LOGOUT') {
          const publicPages = ['index.html', 'auth.html', 'login.html', 'enrollment.html', 'parent-view.html', ''];
          const curPage = (window.location.pathname.split('/').pop() || '').toLowerCase();
          if (!publicPages.includes(curPage)) window.location.href = 'auth.html';
        }
      };
    }
  }

  window.applyTheme = function (themeName, customColors) {
    if (window.SMSStateBus && window.SMSStateBus.setTheme) {
      return window.SMSStateBus.setTheme(themeName, customColors);
    }
  };
  window.setTheme = window.applyTheme;


  // ── 4. Sidebar View Layout Controller & Navigation ────────────────────
  window.applyLayout = function (layoutMode) {
    const currentPath = (window.location.pathname.split("/").pop() || "").toLowerCase();
    if (_publicPages.includes(currentPath)) {
      document.documentElement.removeAttribute("data-layout");
      return;
    }
    // Always enforce sidebar layout
    localStorage.setItem("system_layout_mode", "sidebar");
    document.documentElement.setAttribute("data-layout", "sidebar");
    window.mountSidebarNav();
  };

  window.toggleSidebarCollapse = function () {
    const sidebar = document.querySelector(".app-sidebar");
    if (!sidebar) return;
    const isCollapsed = sidebar.classList.toggle("collapsed");
    document.body.classList.toggle("sidebar-collapsed", isCollapsed);
    localStorage.setItem("sidebar_collapsed", isCollapsed);
    const icon = sidebar.querySelector(".sidebar-collapse-icon");
    if (icon) icon.textContent = isCollapsed ? '▶' : '◀';
  };

  window.toggleMobileSidebar = function () {
    const sidebar = document.querySelector(".app-sidebar");
    if (!sidebar) return;
    const isOpen = sidebar.classList.toggle("open");
    let backdrop = document.getElementById("sidebarBackdrop");
    if (!backdrop) {
      backdrop = document.createElement("div");
      backdrop.id = "sidebarBackdrop";
      backdrop.className = "sidebar-backdrop";
      backdrop.onclick = window.toggleMobileSidebar;
      document.body.appendChild(backdrop);
    }
    backdrop.style.display = isOpen ? "block" : "none";
  };

  window.toggleSidebarGroup = function (groupId) {
    const groupItems = document.getElementById(groupId);
    const groupHeader = document.getElementById(groupId + '-header');
    if (!groupItems) return;
    const isHidden = groupItems.style.display === 'none';
    groupItems.style.display = isHidden ? 'block' : 'none';

    // Ensure only eligible child items in the group are visible when expanded
    if (isHidden) {
      const childItems = groupItems.querySelectorAll('.sidebar-item');
      const schoolMode = (localStorage.getItem('school_mode') || 'COMBINED').toUpperCase();
      const boardingStatus = (localStorage.getItem('boarding_status') || 'BOARDING_AND_DAY').toUpperCase();
      const isBasicOnly = schoolMode === 'BASIC_ONLY';
      const isShsOnly = schoolMode === 'SHS_ONLY';

      childItems.forEach(item => {
        const href = (item.getAttribute('href') || '').toLowerCase();
        if (isBasicOnly) {
          if (href.includes('programs.html') || href.includes('departments.html') || href.includes('transcript') || href.includes('houses.html') || href.includes('exeat.html') || href.includes('enrollment.html') || href.includes('clearance.html')) {
            item.style.display = 'none';
            return;
          }
        }
        if (isShsOnly && href.includes('cumulative-record.html')) {
          item.style.display = 'none';
          return;
        }
        if ((boardingStatus === 'DAY_ONLY' || isBasicOnly) && (href.includes('houses.html') || href.includes('exeat.html'))) {
          item.style.display = 'none';
          return;
        }
        item.style.display = 'flex';
      });
    }

    const states = JSON.parse(localStorage.getItem('sidebar_accordion_states') || '{}');
    states[groupId] = isHidden;
    localStorage.setItem('sidebar_accordion_states', JSON.stringify(states));

    if (groupHeader) {
      const arrow = groupHeader.querySelector('.accordion-arrow');
      if (arrow) arrow.textContent = isHidden ? '▾' : '▸';
    }
  };

  window.mountSidebarNav = function () {
    if (document.body && (document.body.id === "public-landing-page" || document.body.classList.contains("public-landing-page") || document.body.classList.contains("public-portal"))) return;
    const currentPath = (window.location.pathname.split("/").pop() || "").toLowerCase().split("?")[0];
    const publicPages = ["index.html", "auth.html", "login.html", "enrollment.html", "parent-view.html", ""];
    if (publicPages.includes(currentPath)) return;
    if (document.querySelector(".app-sidebar")) return;
    if (!document.body) {
      if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => window.mountSidebarNav());
      }
      return;
    }

    const sidebar = document.createElement("aside");
    sidebar.className = "app-sidebar";

    const isCollapsed = localStorage.getItem("sidebar_collapsed") === "true";
    if (isCollapsed) sidebar.classList.add("collapsed");
    document.body.classList.toggle("sidebar-collapsed", isCollapsed);

    const accordionStates = JSON.parse(localStorage.getItem('sidebar_accordion_states') || '{}');

    // ── Use centralized feature gate (from featureGate.js) ────────────────────
    // Falls back gracefully if featureGate.js is not yet loaded.
    const F = (window.SchoolFeatures && window.SchoolFeatures.version)
      ? window.SchoolFeatures
      : (window.FeatureGate ? window.FeatureGate.getFeatures() : null);

    const schoolMode     = (sessionStorage.getItem('school_mode') || localStorage.getItem('school_mode') || (F ? F.schoolMode : 'COMBINED')).toUpperCase();
    const boardingStatus = (sessionStorage.getItem('boarding_status') || localStorage.getItem('boarding_status') || (F ? F.boardingStatus : 'BOARDING_AND_DAY')).toUpperCase();
    const isBasicOnly    = (schoolMode === 'BASIC_ONLY');
    const isShsOnly      = (schoolMode === 'SHS_ONLY');
    const isCombined     = (schoolMode === 'COMBINED');
    const isBoarding     = (boardingStatus === 'BOARDING_AND_DAY') && !isBasicOnly;

    // Enterprise Taxonomy Definition
    let academicItems = [
      { href: 'programs.html', icon: '🎯', label: 'Programs', shsOnly: true },
      { href: 'departments.html', icon: '🏢', label: 'Departments', shsOnly: true },
      { href: 'subjects.html', icon: '📚', label: 'Subjects' },
      { href: 'classes.html', icon: '🏫', label: 'Classes' },
      { href: 'assignments.html', icon: '👩‍🏫', label: 'Teacher Assignments' },
      { href: 'timetable.html', icon: '📅', label: 'Timetable' }
    ];

    let studentLifeItems = [
      { href: 'students.html', icon: '👥', label: 'Students' },
      { href: 'attendance.html', icon: '📋', label: 'Attendance' },
      { href: 'houses.html', icon: '🏠', label: 'Houses & Dorms', shsOnly: true, boardingOnly: true },
      { href: 'exeat.html', icon: '🎟️', label: 'Exeat Management', shsOnly: true, boardingOnly: true },
      { href: 'enrollment.html', icon: '📝', label: 'CSSPS Enrollment', shsOnly: true, csspsOnly: true },
      { href: 'discipline.html', icon: '⚖️', label: 'Discipline Records' },
      { href: 'cumulative-record.html', icon: '📁', label: 'Cumulative Record Folder', basicOnly: true },
      { href: 'clearance.html', icon: '🎓', label: 'Final Year Clearance', shsOnly: true },
      { href: 'promotions.html', icon: '🎓', label: 'Promotions' }
    ];

    let assessmentItems = [
      { href: 'bulk-entry.html', icon: '✍️', label: 'Results (Marks Entry)' },
      { href: 'broadsheet.html', icon: '📈', label: 'Class Broadsheet' },
      { href: 'reports.html', icon: '📄', label: 'Report Cards & Reports' },
      { href: 'report-card.html?mode=transcript', icon: '📜', label: 'Official SHS Transcripts', shsOnly: true }
    ];

    const activeRole = (sessionStorage.getItem('activeRole') || localStorage.getItem('activeRole') || sessionStorage.getItem('userRole') || localStorage.getItem('userRole') || '').toLowerCase();
    const rawRolesStr = sessionStorage.getItem('userRoles') || localStorage.getItem('userRoles');
    const userRoles = rawRolesStr ? JSON.parse(rawRolesStr).map(r => r.toLowerCase()) : [activeRole];
    const isSuperAdminUser = localStorage.getItem('is_super_admin') === 'true' || localStorage.getItem('username') === 'superadmin' || activeRole === 'super_admin' || userRoles.includes('super_admin');
    const isActiveAdmin = ['admin', 'super_admin'].includes(activeRole) || userRoles.includes('admin') || userRoles.includes('super_admin') || isSuperAdminUser;

    const EXEC_ACADEMIC = ['admin', 'super_admin', 'headmaster', 'headmistress', 'assistant_headmaster_academic', 'assistant_head_academic', 'assistant_headmaster_admin', 'assistant_head_admin'];
    const EXEC_DOMESTIC = ['admin', 'super_admin', 'headmaster', 'headmistress', 'assistant_headmaster_domestic', 'assistant_head_domestic', 'assistant_headmaster_admin', 'assistant_head_admin'];
    const EXEC_ADMIN = ['admin', 'super_admin', 'headmaster', 'headmistress', 'assistant_headmaster_admin', 'assistant_head_admin'];
    const HOUSE_STAFF = ['senior_housemaster', 'senior_housemistress', 'senior_house_master', 'senior_house_mistress', 'house_master', 'house_mistress', 'assistant_house_master', 'assistant_house_mistress'];
    const FORM_STAFF = ['form_master', 'form_mistress'];

    const NAV_PAGE_ROLES = {
      'users.html':         ['admin', 'super_admin', ...EXEC_ADMIN],
      'students.html':      ['admin', 'super_admin', ...EXEC_ACADEMIC, ...EXEC_DOMESTIC, 'bursar', ...FORM_STAFF, 'teacher'],
      'classes.html':       ['admin', 'super_admin', ...EXEC_ACADEMIC, 'hod'],
      'subjects.html':      ['admin', 'super_admin', ...EXEC_ACADEMIC, 'hod', 'teacher', ...FORM_STAFF],
      'programs.html':      ['admin', 'super_admin', ...EXEC_ACADEMIC],
      'departments.html':   ['admin', 'super_admin', ...EXEC_ACADEMIC, 'hod'],
      'academic.html':      ['admin', 'super_admin', ...EXEC_ACADEMIC],
      'assignments.html':   ['admin', 'super_admin', ...EXEC_ACADEMIC, 'hod'],
      'promotions.html':    ['admin', 'super_admin', ...EXEC_ACADEMIC, ...FORM_STAFF],
      'clearance.html':     ['admin', 'super_admin', ...EXEC_ACADEMIC, ...EXEC_DOMESTIC, 'bursar', 'storekeeper', ...HOUSE_STAFF],
      'fees.html':          ['admin', 'super_admin', ...EXEC_ADMIN, 'bursar'],
      'assets.html':        ['admin', 'super_admin', ...EXEC_ADMIN, 'storekeeper'],
      'houses.html':        ['admin', 'super_admin', ...EXEC_DOMESTIC, ...HOUSE_STAFF],
      'exeat.html':         ['admin', 'super_admin', ...EXEC_DOMESTIC, ...HOUSE_STAFF, 'security_officer'],
      'discipline.html':    ['admin', 'super_admin', ...EXEC_DOMESTIC, ...HOUSE_STAFF, ...FORM_STAFF, 'hod', 'teacher'],
      'data-tools.html':    ['admin', 'super_admin', ...EXEC_ADMIN, 'storekeeper'],
      'settings.html':      ['admin', 'super_admin', ...EXEC_ADMIN],
      'bulk-entry.html':    ['admin', 'super_admin', ...EXEC_ACADEMIC, 'hod', 'teacher'],
      'results.html':       ['admin', 'super_admin', ...EXEC_ACADEMIC, 'hod', 'teacher'],
      'broadsheet.html':    ['admin', 'super_admin', ...EXEC_ACADEMIC, ...FORM_STAFF, 'hod'],
      'reports.html':       ['admin', 'super_admin', ...EXEC_ACADEMIC, ...FORM_STAFF, 'teacher', 'parent', 'student'],
      'announcements.html': ['admin', 'super_admin', ...EXEC_ADMIN, ...EXEC_DOMESTIC],
      'timetable.html':     ['admin', 'super_admin', ...EXEC_ACADEMIC, 'teacher', ...FORM_STAFF, 'hod'],
      'attendance.html':    ['admin', 'super_admin', ...EXEC_ACADEMIC, ...EXEC_DOMESTIC, ...HOUSE_STAFF, ...FORM_STAFF, 'teacher'],
      'parent-view.html':   ['admin', 'super_admin', ...EXEC_ACADEMIC, 'teacher', 'parent'],
      'enrollment.html':    ['admin', 'super_admin', ...EXEC_ADMIN],
      'cumulative-record.html': ['admin', 'super_admin', ...EXEC_ACADEMIC, ...FORM_STAFF],
    };

    const filterItems = (items) => items.filter(i => {
      const href = (i.href || '').toLowerCase().split('?')[0];

      // ── Boarding gate: hide boarding-only items for DAY_ONLY schools ──────
      if (i.boardingOnly && !isBoarding) return false;

      // ── School Mode gates ─────────────────────────────────────────────────
      // shsOnly: only show for SHS_ONLY or COMBINED (i.e., hide for BASIC_ONLY)
      if (i.shsOnly && isBasicOnly) return false;
      // basicOnly: only show for BASIC_ONLY or COMBINED (i.e., hide for SHS_ONLY)
      if (i.basicOnly && isShsOnly) return false;

      // ── Role gate ─────────────────────────────────────────────────────────
      if (!isActiveAdmin) {
        const cleanHref = href.split('/').pop();
        const allowedRoles = NAV_PAGE_ROLES[cleanHref];
        if (allowedRoles && !allowedRoles.includes(activeRole)) {
          return false;
        }
      }
      return true;
    });

    const groups = [
      { id: 'group-academic', title: 'ACADEMIC MANAGEMENT', items: filterItems(academicItems) },
      { id: 'group-student-life', title: 'STUDENT AFFAIRS & SCHOOL LIFE', items: filterItems(studentLifeItems) },
      { id: 'group-assessments', title: 'ASSESSMENTS & GRADING', items: filterItems(assessmentItems) },
      { id: 'group-finance', title: 'FINANCE & OPERATIONS', items: filterItems([
        { href: 'fees.html', icon: '💰', label: 'Fee Management' },
        { href: 'assets.html', icon: '🗄️', label: 'Asset Management' }
      ]) },
      { id: 'group-communications', title: 'COMMUNICATIONS', items: filterItems([
          { href: 'messaging.html', icon: '💬', label: 'Bulk Messaging' },
          { href: 'parent-view.html', icon: '👨‍👩‍👧', label: 'Parent Portal' }
        ])
      }
    ].filter(g => g.items.length > 0);

    const configItemsFiltered = filterItems([
      { href: 'users.html', icon: '👤', label: 'Users' },
      { href: 'data-tools.html', icon: '🛠️', label: 'Data Tools' },
      { href: 'settings.html', icon: '⚙️', label: 'Settings' }
    ]);

    const configGroup = {
      id: 'group-config',
      title: 'SYSTEM CONFIGURATION',
      items: configItemsFiltered
    };

    // Determine auto-expanded group based on active page
    let activeGroupId = null;
    groups.forEach(g => {
      if (g.items.some(i => i.href === currentPath)) {
        activeGroupId = g.id;
      }
    });

    let groupsHtml = '';
    groups.forEach(g => {
      const containsActive = g.items.some(i => i.href === currentPath);
      const isOpen = accordionStates[g.id] !== false;
      
      let itemsHtml = '';
      g.items.forEach(i => {
        const isActive = currentPath === i.href;
        itemsHtml += `
          <a href="${i.href}" class="sidebar-item ${isActive ? 'active' : ''}">
            <span class="sidebar-icon">${i.icon}</span>
            <span class="sidebar-text">${i.label}</span>
          </a>
        `;
      });

      groupsHtml += `
        <div class="sidebar-group">
          <div class="sidebar-group-title" id="${g.id}-header" data-group-id="${g.id}" style="cursor:pointer; display:flex; justify-content:space-between; align-items:center; user-select:none;">
            <span>${g.title}</span>
            <span class="accordion-arrow" style="font-size:0.75rem; opacity:0.7;">${isOpen ? '▾' : '▸'}</span>
          </div>
          <div class="sidebar-group-items" id="${g.id}" style="display: ${isOpen ? 'block' : 'none'};">
            ${itemsHtml}
          </div>
        </div>
      `;
    });

    // Pinned bottom config items
    const configContainsActive = configGroup.items.some(i => i.href === currentPath);
    const configIsOpen = configContainsActive || accordionStates[configGroup.id] !== false;
    let configItemsHtml = '';
    configGroup.items.forEach(i => {
      const isActive = currentPath === i.href;
      configItemsHtml += `
        <a href="${i.href}" class="sidebar-item ${isActive ? 'active' : ''}">
          <span class="sidebar-icon">${i.icon}</span>
          <span class="sidebar-text">${i.label}</span>
        </a>
      `;
    });

    function getSchoolAbbreviation(name) {
      const isSuperAdmin = localStorage.getItem('is_super_admin') === 'true' && (localStorage.getItem('userRole') === 'super_admin' || localStorage.getItem('username') === 'superadmin') && !localStorage.getItem('is_super_admin_viewing');
      if (isSuperAdmin) return 'SUPER ADMIN';

      const savedAbbr = localStorage.getItem('school_abbreviation');
      if (savedAbbr && savedAbbr.trim().length > 0 && savedAbbr !== 'SUPER ADMIN') return savedAbbr;
      if (!name || name === 'Master System Portal' || name === 'School Management System' || name === 'School Management') return 'SMS';
      const clean = name.replace(/[^a-zA-Z0-9\s]/g, '').trim();
      const words = clean.split(/\s+/).filter(w => w.length > 0);
      if (words.length === 1) return words[0].substring(0, 6).toUpperCase();
      return words.map(w => w[0]).join('').toUpperCase();
    }

    const isSuperAdmin = localStorage.getItem('is_super_admin') === 'true' && (localStorage.getItem('userRole') === 'super_admin' || localStorage.getItem('username') === 'superadmin') && !localStorage.getItem('is_super_admin_viewing');
    const isViewing = localStorage.getItem('is_super_admin_viewing') === 'true';
    if (isSuperAdmin && !isViewing) {
      localStorage.removeItem('school_logo');
    }

    const dashHref = (isSuperAdmin && !isViewing) ? 'super-admin.html' : 'dashboard.html';
    const dashboardActive = currentPath === dashHref || currentPath === '' || (dashHref === 'dashboard.html' && currentPath === 'index.html');

    const schoolName = localStorage.getItem('school_name') || 'School Management';
    const rawSchoolLogo = localStorage.getItem('school_logo') || '';
    const schoolLogo = (isSuperAdmin && !isViewing) ? '' : rawSchoolLogo;
    const schoolAbbr = getSchoolAbbreviation(schoolName);

    window.createDefaultCrestSvg = window.createDefaultCrestSvg || function(abbr, size = 30) {
      const cleanAbbr = (abbr || 'SMS').trim().substring(0, 4).toUpperCase();
      const fontSize = cleanAbbr.length >= 4 ? 9 : (cleanAbbr.length === 3 ? 10 : 12);
      return `<svg width="${size}" height="${size}" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" class="school-crest-svg" style="flex-shrink:0; border-radius:8px; display:inline-block; vertical-align:middle; box-shadow:0 2px 8px rgba(0,0,0,0.18);">
        <defs>
          <linearGradient id="crestGrad_${size}" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#4f46e5" />
            <stop offset="100%" stop-color="#06b6d4" />
          </linearGradient>
        </defs>
        <rect width="40" height="40" rx="8" fill="url(#crestGrad_${size})" />
        <path d="M20 6 L32 11 V20 C32 27.5 26.8 33 20 35 C13.2 33 8 27.5 8 20 V11 L20 6 Z" fill="rgba(255,255,255,0.18)" stroke="#ffffff" stroke-width="1.2" />
        <text x="20" y="24.5" text-anchor="middle" font-family="'Outfit', 'Inter', -apple-system, sans-serif" font-size="${fontSize}" font-weight="800" fill="#ffffff" letter-spacing="0.5">${cleanAbbr}</text>
      </svg>`;
    };

    const logoHtml = (isSuperAdmin && !isViewing)
      ? '<img src="assets/logo_compact.png" class="sidebar-logo-img" style="height:28px; width:28px; object-fit:cover; border-radius:6px; flex-shrink:0;" onerror="this.outerHTML=\'<span style=\\\'font-size:1.3rem; flex-shrink:0;\\\'>🌐</span>\';" />'
      : (schoolLogo 
          ? `<img src="${schoolLogo}" class="sidebar-logo-img" style="height:30px; width:30px; object-fit:cover; border-radius:8px; flex-shrink:0;" onerror="this.outerHTML = window.createDefaultCrestSvg('${schoolAbbr}', 30);" />` 
          : window.createDefaultCrestSvg(schoolAbbr, 30));

    sidebar.innerHTML = `
      <div class="sidebar-header" style="display:flex; align-items:center; gap:10px; padding:14px 16px;">
        ${logoHtml}
        <span class="sidebar-text" id="sidebarSchoolName" style="font-weight:800; font-size:1.05rem; color:var(--text-primary); letter-spacing:0.04em; text-overflow:ellipsis; overflow:hidden; white-space:nowrap;" title="${schoolName}">${schoolAbbr}</span>
        <button onclick="window.toggleSidebarCollapse()" style="margin-left:auto; background:none; border:none; color:var(--text-secondary); cursor:pointer; font-size:0.9rem; flex-shrink:0;" title="Toggle Sidebar">
          <span class="sidebar-collapse-icon">${isCollapsed ? '▶' : '◀'}</span>
        </button>
      </div>

      <!-- Quick Filter Search Input (Anti-Autofill Protected) -->
      <div style="padding: 8px 12px 4px;">
        <input type="search" placeholder="🔍 Filter menu..." id="sidebarFilterInput" name="search_menu_no_autofill" value="" autocomplete="off" readonly onfocus="this.removeAttribute('readonly')" oninput="window.filterSidebarMenu(this.value)" style="width:100%; padding:6px 10px; font-size:0.78rem; background:rgba(15,23,42,0.6); color:var(--text-primary); border:1px solid var(--border-color); border-radius:6px; outline:none;" />
      </div>

      <div class="sidebar-nav" style="flex: 1; overflow-y: auto;">
        <!-- Standalone Dashboard Link -->
        <div style="margin-bottom: 8px;">
          <a href="${dashHref}" class="sidebar-item ${dashboardActive ? 'active' : ''}" style="font-weight: 700;">
            <span class="sidebar-icon">📊</span>
            <span class="sidebar-text">DASHBOARD</span>
          </a>
        </div>
        ${groupsHtml}
      </div>

      <!-- Fixed Bottom System Configuration Footer -->
      <div class="sidebar-footer-config" style="padding: 8px 12px 12px; border-top: 1px solid var(--border-color); background: var(--card-bg);">
        <div class="sidebar-group-title" id="${configGroup.id}-header" data-group-id="${configGroup.id}" style="cursor:pointer; display:flex; justify-content:space-between; align-items:center; user-select:none;">
          <span>${configGroup.title}</span>
          <span class="accordion-arrow" style="font-size:0.75rem; opacity:0.7;">${configIsOpen ? '▾' : '▸'}</span>
        </div>
        <div class="sidebar-group-items" id="${configGroup.id}" style="display: ${configIsOpen ? 'block' : 'none'}; margin-top: 4px;">
          ${configItemsHtml}
        </div>
      </div>
    `;

    // Click event listener for accordion toggling
    sidebar.addEventListener('click', (e) => {
      const header = e.target.closest('.sidebar-group-title');
      if (header) {
        const groupId = header.getAttribute('data-group-id');
        if (groupId) {
          window.toggleSidebarGroup(groupId);
        }
      }
    });

    window.filterSidebarMenu = function(query) {
      const q = (query || '').toLowerCase().trim();
      const groups = sidebar.querySelectorAll('.sidebar-group, .sidebar-footer-config');
      
      if (!q) {
        // Reset all item displays when search is empty
        const allItems = sidebar.querySelectorAll('.sidebar-item');
        allItems.forEach(item => item.style.display = 'flex');
        return;
      }

      // Keyword aliases map for smart search
      const aliases = {
        'admin': ['users', 'settings', 'data tools', 'configuration', 'assignments', 'system'],
        'academic': ['programs', 'departments', 'subjects', 'classes', 'assignments', 'timetable'],
        'student': ['students', 'attendance', 'houses', 'exeat', 'discipline', 'promotions'],
        'report': ['reports', 'report cards', 'broadsheet', 'results'],
        'finance': ['fees', 'fee management', 'finance']
      };

      let matchedKeywords = [q];
      Object.keys(aliases).forEach(alias => {
        if (q.includes(alias) || alias.includes(q)) {
          matchedKeywords = matchedKeywords.concat(aliases[alias]);
        }
      });

      groups.forEach(group => {
        const titleEl = group.querySelector('.sidebar-group-title');
        const titleText = titleEl ? titleEl.textContent.toLowerCase() : '';
        const items = group.querySelectorAll('.sidebar-item');
        let groupHasMatch = matchedKeywords.some(kw => titleText.includes(kw));

        items.forEach(item => {
          const text = item.textContent.toLowerCase();
          const matches = groupHasMatch || matchedKeywords.some(kw => text.includes(kw));
          if (matches) {
            item.style.display = 'flex';
            groupHasMatch = true;
          } else {
            item.style.display = 'none';
          }
        });

        const itemsContainer = group.querySelector('.sidebar-group-items');
        if (itemsContainer) {
          if (groupHasMatch) {
            itemsContainer.style.display = 'block';
            if (titleEl) {
              const arrow = titleEl.querySelector('.accordion-arrow');
              if (arrow) arrow.textContent = '▾';
            }
          }
        }
      });
    };

    document.body.prepend(sidebar);

    // Auto-inject mobile hamburger button into .topbar if present
    const topbar = document.querySelector('.topbar');
    if (topbar && !topbar.querySelector('.mobile-hamburger-btn')) {
      const topbarFirstChild = topbar.firstElementChild;
      const hamburger = document.createElement('button');
      hamburger.type = 'button';
      hamburger.className = 'mobile-hamburger-btn';
      hamburger.setAttribute('aria-label', 'Open Navigation Menu');
      hamburger.innerHTML = '☰';
      hamburger.onclick = (e) => {
        e.stopPropagation();
        window.toggleMobileSidebar();
      };

      if (topbarFirstChild) {
        topbarFirstChild.prepend(hamburger);
      } else {
        topbar.prepend(hamburger);
      }
    }

    // Auto-close sidebar on mobile when a navigation link is clicked
    sidebar.addEventListener('click', (e) => {
      const item = e.target.closest('.sidebar-item');
      if (item && window.innerWidth <= 768) {
        const sidebarEl = document.querySelector('.app-sidebar');
        if (sidebarEl && sidebarEl.classList.contains('open')) {
          window.toggleMobileSidebar();
        }
      }
    });

    const filterInput = document.getElementById('sidebarFilterInput');
    if (filterInput) {
      filterInput.value = '';
      window.filterSidebarMenu('');
      setTimeout(() => {
        if (filterInput) {
          filterInput.value = '';
          window.filterSidebarMenu('');
        }
      }, 100);
      setTimeout(() => {
        if (filterInput) {
          filterInput.value = '';
          window.filterSidebarMenu('');
        }
      }, 400);
    }
  };

  // ── 5. Command Palette (Ctrl+K) ────────────────────────────────────────────
  const CMD_PAGES = [
    { icon: '📊', label: 'Dashboard',              href: 'dashboard.html',        group: 'General' },
    { icon: '👥', label: 'Students',               href: 'students.html',         group: 'Academic' },
    { icon: '🏫', label: 'Classes',                href: 'classes.html',          group: 'Academic' },
    { icon: '📚', label: 'Subjects',               href: 'subjects.html',         group: 'Academic' },
    { icon: '🎯', label: 'Programs',               href: 'programs.html',         group: 'Academic' },
    { icon: '🏢', label: 'Departments',            href: 'departments.html',      group: 'Academic' },
    { icon: '📅', label: 'Timetable',              href: 'timetable.html',        group: 'Academic' },
    { icon: '👩‍🏫', label: 'Teacher Assignments',  href: 'assignments.html',      group: 'Academic' },
    { icon: '📋', label: 'Attendance',             href: 'attendance.html',       group: 'Student Life' },
    { icon: '🏠', label: 'Houses & Dorms',         href: 'houses.html',           group: 'Student Life' },
    { icon: '🎟️', label: 'Exeat Management',       href: 'exeat.html',            group: 'Student Life' },
    { icon: '⚖️', label: 'Discipline Records',     href: 'discipline.html',       group: 'Student Life' },
    { icon: '🎓', label: 'Promotions',             href: 'promotions.html',       group: 'Student Life' },
    { icon: '🎓', label: 'Final Year Clearance',   href: 'clearance.html',        group: 'Student Life' },
    { icon: '✍️', label: 'Results / Marks Entry',  href: 'bulk-entry.html',       group: 'Assessment' },
    { icon: '📈', label: 'Class Broadsheet',       href: 'broadsheet.html',       group: 'Assessment' },
    { icon: '📄', label: 'Report Cards',           href: 'reports.html',          group: 'Assessment' },
    { icon: '📁', label: 'Cumulative Record',      href: 'cumulative-record.html',group: 'Assessment' },
    { icon: '💰', label: 'Fee Management',         href: 'fees.html',             group: 'Finance' },
    { icon: '🗄️', label: 'Asset Management',       href: 'assets.html',           group: 'Finance' },
    { icon: '💬', label: 'Bulk Messaging',         href: 'messaging.html',        group: 'Communications' },
    { icon: '👨‍👩‍👧', label: 'Parent Portal',       href: 'parent-view.html',      group: 'Communications' },
    { icon: '👤', label: 'Users',                  href: 'users.html',            group: 'Admin' },
    { icon: '🛠️', label: 'Data Tools',             href: 'data-tools.html',       group: 'Admin' },
    { icon: '⚙️', label: 'Settings',              href: 'settings.html',         group: 'Admin' },
  ];

  const CMD_ALIASES = {
    'grade': ['Results', 'Broadsheet', 'Report Cards'],
    'payment': ['Fee Management'],
    'money': ['Fee Management'],
    'house': ['Houses & Dorms'],
    'dorm': ['Houses & Dorms'],
    'boarding': ['Houses & Dorms', 'Exeat Management'],
    'mark': ['Results / Marks Entry', 'Attendance'],
    'score': ['Results / Marks Entry'],
    'class': ['Classes', 'Class Broadsheet', 'Teacher Assignments'],
    'teacher': ['Teacher Assignments', 'Subjects'],
    'parent': ['Parent Portal'],
    'message': ['Bulk Messaging'],
    'sms': ['Bulk Messaging'],
    'user': ['Users'],
    'config': ['Settings'],
    'setup': ['Settings'],
    'tool': ['Data Tools'],
    'report': ['Report Cards', 'Class Broadsheet'],
    'enroll': ['Students', 'Promotions'],
    'leave': ['Exeat Management'],
  };

  let cmdActiveIdx = 0;
  let cmdOverlay = null;
  let cmdFilteredItems = [];

  function buildCmdResults(query) {
    const q = (query || '').toLowerCase().trim();
    let items = CMD_PAGES;

    if (q) {
      // Expand aliases
      let expandedTerms = [q];
      Object.keys(CMD_ALIASES).forEach(alias => {
        if (q.includes(alias) || alias.includes(q)) {
          expandedTerms = expandedTerms.concat(CMD_ALIASES[alias].map(s => s.toLowerCase()));
        }
      });

      items = CMD_PAGES.filter(p =>
        expandedTerms.some(term =>
          p.label.toLowerCase().includes(term) ||
          p.group.toLowerCase().includes(term) ||
          p.href.toLowerCase().includes(term)
        )
      );
    }

    cmdFilteredItems = items;
    cmdActiveIdx = 0;

    const container = document.getElementById('cmdResults');
    if (!container) return;

    if (items.length === 0) {
      container.innerHTML = `<div class="cmd-empty">No results for "<strong>${query}</strong>"</div>`;
      return;
    }

    // Group items
    const groups = {};
    items.forEach(item => {
      if (!groups[item.group]) groups[item.group] = [];
      groups[item.group].push(item);
    });

    let html = '';
    let globalIdx = 0;
    Object.keys(groups).forEach(groupName => {
      if (!q) html += `<div class="cmd-section-label">${groupName}</div>`;
      groups[groupName].forEach(item => {
        const idx = globalIdx++;
        html += `
          <div class="cmd-item ${idx === 0 ? 'active' : ''}" data-idx="${idx}" data-href="${item.href}" onclick="window._cmdNavigate('${item.href}')">
            <span class="cmd-item-icon">${item.icon}</span>
            <span class="cmd-item-label">${item.label}</span>
            ${q ? '' : `<span class="cmd-item-group">${item.group}</span>`}
          </div>`;
      });
    });

    container.innerHTML = html;
  }

  function cmdUpdateActive() {
    const items = document.querySelectorAll('#cmdResults .cmd-item');
    items.forEach((el, i) => el.classList.toggle('active', i === cmdActiveIdx));
    if (items[cmdActiveIdx]) {
      items[cmdActiveIdx].scrollIntoView({ block: 'nearest' });
    }
  }

  window._cmdNavigate = function(href) {
    closeCmdPalette();
    window.location.href = href;
  };

  function closeCmdPalette() {
    if (cmdOverlay && cmdOverlay.parentNode) {
      cmdOverlay.style.animation = 'overlayFadeIn 0.12s ease reverse both';
      setTimeout(() => cmdOverlay && cmdOverlay.parentNode && cmdOverlay.parentNode.removeChild(cmdOverlay), 120);
    }
    cmdOverlay = null;
  }

  function openCmdPalette() {
    if (cmdOverlay) { closeCmdPalette(); return; }

    cmdOverlay = document.createElement('div');
    cmdOverlay.className = 'cmd-overlay';
    cmdOverlay.id = 'cmdPaletteOverlay';
    cmdOverlay.innerHTML = `
      <div class="cmd-modal" id="cmdModal" role="dialog" aria-label="Command Palette">
        <div class="cmd-search-row">
          <span class="cmd-search-icon">🔍</span>
          <input type="text" class="cmd-input" id="cmdInput" placeholder="Search pages, actions..." autocomplete="off" spellcheck="false" />
          <span class="cmd-esc-hint">ESC</span>
        </div>
        <div class="cmd-results" id="cmdResults"></div>
        <div class="cmd-footer">
          <span class="cmd-hint"><kbd>↑↓</kbd> navigate</span>
          <span class="cmd-hint"><kbd>↵</kbd> open</span>
          <span class="cmd-hint"><kbd>ESC</kbd> close</span>
        </div>
      </div>`;

    document.body.appendChild(cmdOverlay);

    // Close on overlay click (outside modal)
    cmdOverlay.addEventListener('click', (e) => {
      if (e.target === cmdOverlay) closeCmdPalette();
    });

    const input = document.getElementById('cmdInput');
    if (input) {
      input.addEventListener('input', (e) => buildCmdResults(e.target.value));
      input.addEventListener('keydown', (e) => {
        if (e.key === 'ArrowDown') {
          e.preventDefault();
          cmdActiveIdx = Math.min(cmdActiveIdx + 1, cmdFilteredItems.length - 1);
          cmdUpdateActive();
        } else if (e.key === 'ArrowUp') {
          e.preventDefault();
          cmdActiveIdx = Math.max(cmdActiveIdx - 1, 0);
          cmdUpdateActive();
        } else if (e.key === 'Enter') {
          e.preventDefault();
          if (cmdFilteredItems[cmdActiveIdx]) {
            window._cmdNavigate(cmdFilteredItems[cmdActiveIdx].href);
          }
        } else if (e.key === 'Escape') {
          closeCmdPalette();
        }
      });
      setTimeout(() => input.focus(), 30);
    }

    buildCmdResults('');
  }

  // ── 5b. Global keyboard shortcuts ──────────────────────────────────────────
  document.addEventListener('keydown', (e) => {
    // Ctrl+K or '/' outside inputs → open command palette
    if ((e.ctrlKey && e.key.toLowerCase() === 'k') ||
        (e.key === '/' && !['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName))) {
      e.preventDefault();
      openCmdPalette();
    }
    // Global escape to close command palette
    if (e.key === 'Escape' && cmdOverlay) {
      closeCmdPalette();
    }
  });

  // ── 6. Notification Bell ────────────────────────────────────────────────────
  let notifPanelOpen = false;
  let notifReadIds = new Set(JSON.parse(localStorage.getItem('notif_read_ids') || '[]'));

  async function loadNotificationBell() {
    const token = localStorage.getItem('accessToken');
    if (!token) return;

    const currentPage = (window.location.pathname.split('/').pop() || '').toLowerCase();
    const publicPages = ['index.html', 'auth.html', 'login.html', 'enrollment.html', 'parent-view.html', ''];
    if (publicPages.includes(currentPage)) return;

    const topbar = document.querySelector('.topbar');
    if (!topbar || topbar.querySelector('.notif-bell-btn')) return;

    // Build bell button container
    const controlsDiv = document.createElement('div');
    controlsDiv.className = 'topbar-controls';
    controlsDiv.id = 'topbarControls';

    const bellBtn = document.createElement('button');
    bellBtn.className = 'notif-bell-btn';
    bellBtn.id = 'notifBellBtn';
    bellBtn.title = 'Notifications';
    bellBtn.setAttribute('aria-label', 'Notifications');
    bellBtn.innerHTML = '🔔';

    controlsDiv.appendChild(bellBtn);
    topbar.appendChild(controlsDiv);

    // Fetch notifications from existing endpoints
    const notifications = await fetchNotifications(token);
    const unread = notifications.filter(n => !notifReadIds.has(n.id));

    if (unread.length > 0) {
      const badge = document.createElement('span');
      badge.className = 'notif-badge';
      badge.id = 'notifBadge';
      badge.textContent = unread.length > 9 ? '9+' : unread.length;
      bellBtn.appendChild(badge);
    }

    bellBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      toggleNotifPanel(notifications, controlsDiv);
    });

    // Close panel when clicking outside
    document.addEventListener('click', (e) => {
      if (notifPanelOpen && !controlsDiv.contains(e.target)) {
        closeNotifPanel();
      }
    });
  }

  async function fetchNotifications(token) {
    const notifications = [];
    const headers = { 'Authorization': `Bearer ${token}` };
    const API = window.API_BASE || (window.location.hostname === 'localhost' ? 'http://localhost:8000/api' : '/api');

    try {
      // Check outstanding fees
      const feesRes = await fetch(`${API}/fees/summary`, { headers });
      if (feesRes.ok) {
        const fees = await feesRes.json();
        const outstanding = fees.total_outstanding_amount || fees.outstanding || 0;
        const count = fees.students_with_outstanding || fees.outstanding_count || 0;
        if (outstanding > 0 || count > 0) {
          notifications.push({
            id: 'fees-outstanding',
            icon: '💰',
            text: count > 0 ? `${count} students have outstanding fee balances` : 'Outstanding fee balances detected',
            href: 'fees.html',
            time: 'Finance',
            unread: true,
          });
        }
      }
    } catch (_) {}

    try {
      // Check today's attendance
      const attRes = await fetch(`${API}/attendance/today-stats`, { headers });
      if (attRes.ok) {
        const att = await attRes.json();
        if (!att.total_marked || att.total_marked === 0) {
          notifications.push({
            id: 'attendance-not-marked',
            icon: '📋',
            text: "Today's attendance hasn't been marked yet",
            href: 'attendance.html',
            time: 'Today',
            unread: true,
          });
        }
      }
    } catch (_) {}

    try {
      // Check pending exeat requests
      const exeatRes = await fetch(`${API}/exeat/?status=pending`, { headers });
      if (exeatRes.ok) {
        const exeats = await exeatRes.json();
        const pending = Array.isArray(exeats) ? exeats.filter(e => (e.status || '').toLowerCase() === 'pending') : [];
        if (pending.length > 0) {
          notifications.push({
            id: 'exeat-pending',
            icon: '🎟️',
            text: `${pending.length} exeat request${pending.length > 1 ? 's' : ''} awaiting approval`,
            href: 'exeat.html',
            time: 'Boarding',
            unread: true,
          });
        }
      }
    } catch (_) {}

    // Filter out already-read items for unread count, but keep all for display
    return notifications;
  }

  function toggleNotifPanel(notifications, container) {
    if (notifPanelOpen) {
      closeNotifPanel();
      return;
    }

    notifPanelOpen = true;
    const unread = notifications.filter(n => !notifReadIds.has(n.id));

    let itemsHtml = '';
    if (notifications.length === 0) {
      itemsHtml = `<div class="notif-empty">✅ You're all caught up!</div>`;
    } else {
      notifications.forEach(n => {
        const isUnread = !notifReadIds.has(n.id);
        itemsHtml += `
          <a href="${n.href}" class="notif-item ${isUnread ? 'unread' : ''}" onclick="window._markNotifRead('${n.id}')">
            <span class="notif-item-icon">${n.icon}</span>
            <div class="notif-item-body">
              <div class="notif-item-text">${n.text}</div>
              <div class="notif-item-time">${n.time}</div>
            </div>
          </a>`;
      });
    }

    const panel = document.createElement('div');
    panel.className = 'notif-panel';
    panel.id = 'notifPanel';
    panel.innerHTML = `
      <div class="notif-panel-header">
        <span class="notif-panel-title">🔔 Notifications</span>
        ${unread.length > 0 ? `<button class="notif-mark-all" onclick="window._markAllNotifsRead()">Mark all read</button>` : ''}
      </div>
      <div class="notif-list">${itemsHtml}</div>`;

    container.appendChild(panel);
  }

  function closeNotifPanel() {
    const panel = document.getElementById('notifPanel');
    if (panel) panel.parentNode.removeChild(panel);
    notifPanelOpen = false;
  }

  window._markNotifRead = function(id) {
    notifReadIds.add(id);
    localStorage.setItem('notif_read_ids', JSON.stringify([...notifReadIds]));
    const badge = document.getElementById('notifBadge');
    if (badge) badge.parentNode.removeChild(badge);
  };

  window._markAllNotifsRead = function() {
    document.querySelectorAll('.notif-item').forEach(el => {
      const onclick = el.getAttribute('onclick') || '';
      const match = onclick.match(/'([^']+)'/);
      if (match) notifReadIds.add(match[1]);
    });
    localStorage.setItem('notif_read_ids', JSON.stringify([...notifReadIds]));
    const badge = document.getElementById('notifBadge');
    if (badge) badge.parentNode.removeChild(badge);
    document.querySelectorAll('.notif-item.unread').forEach(el => el.classList.remove('unread'));
    const markAllBtn = document.querySelector('.notif-mark-all');
    if (markAllBtn) markAllBtn.parentNode.removeChild(markAllBtn);
    closeNotifPanel();
  };

  // Immediate execution + DOMContentLoaded + load fallback
  const savedTheme = localStorage.getItem("system_theme") || "midnight";
  window.applyTheme(savedTheme);

  // ── 6. PWA & Offline Service Worker Registration ───────────────────────────
  if (!document.querySelector('link[rel="manifest"]')) {
    const manifestLink = document.createElement('link');
    manifestLink.rel = 'manifest';
    manifestLink.href = '/manifest.json';
    document.head.appendChild(manifestLink);
  }

  if (!document.querySelector('meta[name="theme-color"]')) {
    const themeMeta = document.createElement('meta');
    themeMeta.name = 'theme-color';
    themeMeta.content = '#0f172a';
    document.head.appendChild(themeMeta);
  }

  if ('serviceWorker' in navigator && window.location.protocol.startsWith('http')) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/sw.js').catch(() => {});
    });
  }

  const triggerSidebar = () => {
    window.applyLayout("sidebar");
  };

  if (document.readyState === 'loading') {
    document.addEventListener("DOMContentLoaded", triggerSidebar);
    window.addEventListener("load", triggerSidebar);
  } else {
    triggerSidebar();
  }
  setTimeout(triggerSidebar, 50);
  setTimeout(triggerSidebar, 300);

  // Inject notification bell after sidebar + topbar are fully mounted
  setTimeout(() => loadNotificationBell(), 600);

  // ── 7. Breadcrumb Navigation ─────────────────────────────────────────────────
  const BREADCRUMB_MAP = {
    'dashboard.html':        { label: 'Dashboard',              icon: '📊', group: null },
    'students.html':         { label: 'Students',               icon: '👥', group: { label: 'Academic',      href: 'dashboard.html' } },
    'classes.html':          { label: 'Classes',                icon: '🏫', group: { label: 'Academic',      href: 'dashboard.html' } },
    'subjects.html':         { label: 'Subjects',               icon: '📚', group: { label: 'Academic',      href: 'dashboard.html' } },
    'programs.html':         { label: 'Programs',               icon: '🎯', group: { label: 'Academic',      href: 'dashboard.html' } },
    'departments.html':      { label: 'Departments',            icon: '🏢', group: { label: 'Academic',      href: 'dashboard.html' } },
    'assignments.html':      { label: 'Teacher Assignments',    icon: '👩‍🏫', group: { label: 'Academic',      href: 'dashboard.html' } },
    'timetable.html':        { label: 'Timetable',              icon: '📅', group: { label: 'Academic',      href: 'dashboard.html' } },
    'attendance.html':       { label: 'Attendance',             icon: '📋', group: { label: 'Student Life',  href: 'dashboard.html' } },
    'houses.html':           { label: 'Houses & Dorms',         icon: '🏠', group: { label: 'Student Life',  href: 'dashboard.html' } },
    'exeat.html':            { label: 'Exeat Management',       icon: '🎟️', group: { label: 'Student Life',  href: 'dashboard.html' } },
    'discipline.html':       { label: 'Discipline Records',     icon: '⚖️', group: { label: 'Student Life',  href: 'dashboard.html' } },
    'promotions.html':       { label: 'Promotions',             icon: '🎓', group: { label: 'Student Life',  href: 'dashboard.html' } },
    'clearance.html':        { label: 'Final Year Clearance',   icon: '🎓', group: { label: 'Student Life',  href: 'dashboard.html' } },
    'cumulative-record.html':{ label: 'Cumulative Record',      icon: '📁', group: { label: 'Assessment',    href: 'dashboard.html' } },
    'bulk-entry.html':       { label: 'Marks Entry',            icon: '✍️', group: { label: 'Assessment',    href: 'dashboard.html' } },
    'broadsheet.html':       { label: 'Class Broadsheet',       icon: '📈', group: { label: 'Assessment',    href: 'dashboard.html' } },
    'reports.html':          { label: 'Report Cards',           icon: '📄', group: { label: 'Assessment',    href: 'dashboard.html' } },
    'report-card.html':      { label: 'Student Report Card',    icon: '📄', group: { label: 'Assessment',    href: 'reports.html'   } },
    'fees.html':             { label: 'Fee Management',         icon: '💰', group: { label: 'Finance',       href: 'dashboard.html' } },
    'assets.html':           { label: 'Asset Management',       icon: '🗄️', group: { label: 'Finance',       href: 'dashboard.html' } },
    'messaging.html':        { label: 'Bulk Messaging',         icon: '💬', group: { label: 'Communications',href: 'dashboard.html' } },
    'parent-view.html':      { label: 'Parent Portal',          icon: '👨‍👩‍👧', group: { label: 'Communications',href: 'dashboard.html' } },
    'announcements.html':    { label: 'Announcements',          icon: '📢', group: { label: 'Communications',href: 'dashboard.html' } },
    'users.html':            { label: 'Users',                  icon: '👤', group: { label: 'Admin',         href: 'dashboard.html' } },
    'data-tools.html':       { label: 'Data Tools',             icon: '🛠️', group: { label: 'Admin',         href: 'dashboard.html' } },
    'settings.html':         { label: 'Settings',               icon: '⚙️', group: { label: 'Admin',         href: 'dashboard.html' } },
    'super-admin.html':      { label: 'Super Admin',            icon: '👑', group: null },
  };

  function mountBreadcrumb() {
    const currentPage = (window.location.pathname.split('/').pop() || '').toLowerCase().split('?')[0];
    const publicPages = ['index.html', 'auth.html', 'login.html', 'enrollment.html', 'parent-view.html', ''];
    if (publicPages.includes(currentPage)) return;

    const topbar = document.querySelector('.topbar');
    if (!topbar || document.querySelector('.breadcrumb-bar')) return;

    const meta = BREADCRUMB_MAP[currentPage];
    if (!meta) return;

    const crumbs = [];

    // Always start with Dashboard (unless we are on dashboard)
    if (currentPage !== 'dashboard.html' && currentPage !== 'super-admin.html') {
      crumbs.push({ label: 'Dashboard', href: 'dashboard.html', icon: '📊' });
    }

    // Add group if present
    if (meta.group) {
      crumbs.push({ label: meta.group.label, href: meta.group.href, icon: '' });
    }

    // Add current page as last (non-clickable)
    crumbs.push({ label: meta.label, href: null, icon: meta.icon, current: true });

    // Build HTML
    let html = '';
    crumbs.forEach((crumb, i) => {
      if (i > 0) html += '<span class="breadcrumb-sep">›</span>';
      if (crumb.current) {
        html += `<span class="breadcrumb-item current">${crumb.icon ? crumb.icon + ' ' : ''}${crumb.label}</span>`;
      } else {
        html += `<a href="${crumb.href}" class="breadcrumb-item">${crumb.icon ? crumb.icon + ' ' : ''}${crumb.label}</a>`;
      }
    });

    const bar = document.createElement('nav');
    bar.className = 'breadcrumb-bar no-print';
    bar.setAttribute('aria-label', 'breadcrumb');
    bar.innerHTML = html;

    // Insert after topbar
    topbar.insertAdjacentElement('afterend', bar);

    // Stamp print metadata on body
    const schoolName = localStorage.getItem('school_name') || 'School Management System';
    const printDate = new Date().toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
    document.body.setAttribute('data-school-name', schoolName);
    document.body.setAttribute('data-print-date', printDate);
  }

  // ═══════════════════════════════════════════════════════════════
  // LAN WI-FI MULTI-DEVICE SHARING HUB & OFFLINE QR GENERATOR
  // ═══════════════════════════════════════════════════════════════
  function mountLANSharingHub() {
    const currentPage = (window.location.pathname.split('/').pop() || '').toLowerCase().split('?')[0];
    const publicPages = ['index.html', 'auth.html', 'login.html', 'enrollment.html', 'parent-view.html', ''];
    if (publicPages.includes(currentPage)) return;

    const container = document.querySelector('.breadcrumb-bar') || document.querySelector('.topbar') || document.querySelector('.page-header');
    if (!container || document.getElementById('lan-hub-btn')) return;

    // 1. Create Trigger Button
    const btn = document.createElement('button');
    btn.id = 'lan-hub-btn';
    btn.className = 'lan-hub-trigger no-print';
    btn.innerHTML = '📡 Connect Devices';
    btn.title = "Connect teachers' phones & tablets over local Wi-Fi / Hotspot";
    btn.onclick = () => openLANSharingModal();

    if (container.classList.contains('breadcrumb-bar')) {
      btn.style.marginLeft = 'auto';
      container.appendChild(btn);
    } else {
      container.appendChild(btn);
    }

    // 2. Create Modal if not present
    if (!document.getElementById('lan-sharing-modal')) {
      const modal = document.createElement('div');
      modal.id = 'lan-sharing-modal';
      modal.className = 'no-print';
      modal.setAttribute('role', 'dialog');
      modal.setAttribute('aria-label', 'LAN Multi-Device Sharing Hub');
      modal.innerHTML = `
        <div class="lan-modal-box">
          <div class="lan-modal-header">
            <div style="display:flex; align-items:center; gap:10px;">
              <div style="font-size:1.3rem;">📡</div>
              <div>
                <h3 style="margin:0; font-size:1rem; font-weight:800;">LAN Wi-Fi Multi-Device Hub</h3>
                <span style="font-size:0.72rem; color:#34d399;">100% Offline School Network Sharing</span>
              </div>
            </div>
            <button class="edubot-close-btn" id="lan-modal-close" style="font-size:1.2rem;">✕</button>
          </div>
          <div class="lan-modal-body">
            <div style="font-size:0.84rem; color:var(--text-secondary, #64748b);">
              Connect teachers' smartphones, tablets, and laptops to this server machine via local Wi-Fi or phone hotspot.
            </div>

            <!-- Interface Selector -->
            <div id="lan-interface-select-wrap" style="display:none; flex-direction:column; gap:4px;">
              <label style="font-size:0.75rem; font-weight:700; text-transform:uppercase;">Select Network Interface:</label>
              <select id="lan-interface-select" style="padding:8px 12px; border-radius:8px; border:1.5px solid #cbd5e1; font-size:0.84rem; outline:none; background:var(--card-bg, #fff); color:var(--text-primary, #0f172a);"></select>
            </div>

            <!-- QR Code Box -->
            <div class="lan-qr-container">
              <div class="lan-qr-box" id="lan-qr-display"></div>
              <span style="font-size:0.75rem; font-weight:600; color:#64748b; margin-top:8px;">📱 Scan with Phone / Tablet Camera</span>
            </div>

            <!-- URL Bar with 1-Click Copy -->
            <div class="lan-url-bar">
              <span class="lan-url-text" id="lan-url-display">http://127.0.0.1:8000</span>
              <button class="lan-copy-btn" id="lan-copy-btn">📋 Copy URL</button>
            </div>

            <!-- Quick Instructions -->
            <div class="lan-guide-card">
              <div style="font-weight:700; margin-bottom:4px;">💡 3-Step Teacher Quick Connect:</div>
              <div style="margin-bottom:2px;"><b>1.</b> Connect teacher's device to the school's local Wi-Fi or this PC's hotspot.</div>
              <div style="margin-bottom:2px;"><b>2.</b> Scan the QR code above or type the URL into any mobile browser.</div>
              <div><b>3.</b> Log in with teacher credentials to take attendance or input marks offline.</div>
            </div>
          </div>
        </div>
      `;
      document.body.appendChild(modal);

      document.getElementById('lan-modal-close').onclick = () => closeLANSharingModal();
      modal.onclick = (e) => { if (e.target === modal) closeLANSharingModal(); };
      document.getElementById('lan-copy-btn').onclick = () => copyLANUrl();
    }
  }

  let lanInfoData = null;

  async function openLANSharingModal() {
    const modal = document.getElementById('lan-sharing-modal');
    if (!modal) return;
    modal.classList.add('open');

    const isCloud = !['localhost', '127.0.0.1'].includes(window.location.hostname) && 
                    !window.location.hostname.startsWith('192.168.') && 
                    !window.location.hostname.startsWith('10.') && 
                    !window.location.hostname.startsWith('172.');

    if (isCloud) {
      renderLANInfo({
        primary_url: window.location.origin,
        is_cloud: true,
        interfaces: [{ ip: window.location.hostname, label: 'Cloud Web Application', url: window.location.origin, is_primary: true }]
      });
      return;
    }

    const apiBase = window.API_BASE || (window.location.origin.includes('http') ? (window.location.origin + '/api') : 'http://127.0.0.1:8000/api');
    try {
      const res = await fetch(`${apiBase}/settings/lan-info`);
      if (res.ok) {
        lanInfoData = await res.json();
        renderLANInfo(lanInfoData);
      }
    } catch (_) {
      renderLANInfo({
        primary_url: window.location.origin,
        is_cloud: false,
        interfaces: [{ ip: window.location.hostname, label: 'Current Address', url: window.location.origin }]
      });
    }
  }

  function closeLANSharingModal() {
    const modal = document.getElementById('lan-sharing-modal');
    if (modal) modal.classList.remove('open');
  }

  function renderLANInfo(data) {
    const isCloud = data.is_cloud || (!['localhost', '127.0.0.1'].includes(window.location.hostname) && !window.location.hostname.startsWith('192.168.') && !window.location.hostname.startsWith('10.'));
    
    const titleEl = document.querySelector('#lan-sharing-modal h3');
    const subTitleEl = document.querySelector('#lan-sharing-modal h3 + span');
    const descEl = document.querySelector('#lan-sharing-modal .lan-modal-body > div');
    const guideEl = document.querySelector('#lan-sharing-modal .lan-guide-card');

    if (isCloud) {
      if (titleEl) titleEl.textContent = '🌐 Cloud Mobile Portal Hub';
      if (subTitleEl) {
        subTitleEl.textContent = 'Worldwide Cloud Access';
        subTitleEl.style.color = '#38bdf8';
      }
      if (descEl) descEl.textContent = 'Scan or share this link to access the live EduManage360 cloud system from any smartphone or tablet worldwide.';
      if (guideEl) {
        guideEl.innerHTML = `
          <div style="font-weight:700; margin-bottom:4px; color:#38bdf8;">💡 Cloud Quick Connect:</div>
          <div style="margin-bottom:2px;"><b>1.</b> Scan the QR code with your phone camera or copy the URL.</div>
          <div style="margin-bottom:2px;"><b>2.</b> Works on any cellular data or Wi-Fi network worldwide.</div>
          <div><b>3.</b> Log in with your institutional credentials.</div>
        `;
      }
    } else {
      if (titleEl) titleEl.textContent = 'LAN Wi-Fi Multi-Device Hub';
      if (subTitleEl) {
        subTitleEl.textContent = '100% Offline School Network Sharing';
        subTitleEl.style.color = '#34d399';
      }
      if (descEl) descEl.textContent = "Connect teachers' smartphones, tablets, and laptops to this server machine via local Wi-Fi or phone hotspot.";
      if (guideEl) {
        guideEl.innerHTML = `
          <div style="font-weight:700; margin-bottom:4px;">💡 3-Step Teacher Quick Connect:</div>
          <div style="margin-bottom:2px;"><b>1.</b> Connect teacher's device to the school's local Wi-Fi or this PC's hotspot.</div>
          <div style="margin-bottom:2px;"><b>2.</b> Scan the QR code above or type the URL into any mobile browser.</div>
          <div><b>3.</b> Log in with teacher credentials to take attendance or input marks offline.</div>
        `;
      }
    }

    const select = document.getElementById('lan-interface-select');
    const selectWrap = document.getElementById('lan-interface-select-wrap');
    const ifaces = data.interfaces || [];

    if (ifaces.length > 1 && !isCloud) {
      selectWrap.style.display = 'flex';
      select.innerHTML = '';
      ifaces.forEach((iface, idx) => {
        const opt = document.createElement('option');
        opt.value = iface.url;
        opt.textContent = `${iface.label} (${iface.url})`;
        if (idx === 0) opt.selected = true;
        select.appendChild(opt);
      });
      select.onchange = () => updateLANDisplay(select.value);
    } else {
      selectWrap.style.display = 'none';
    }

    const targetUrl = isCloud ? window.location.origin : (data.primary_url || (ifaces[0] && ifaces[0].url) || window.location.origin);
    updateLANDisplay(targetUrl);
  }

  function updateLANDisplay(targetUrl) {
    const urlDisplay = document.getElementById('lan-url-display');
    const qrDisplay = document.getElementById('lan-qr-display');
    if (urlDisplay) urlDisplay.textContent = targetUrl;
    if (qrDisplay) {
      qrDisplay.innerHTML = generateStandardSvgQrCode(targetUrl, 5, 4);
    }
  }

  function copyLANUrl() {
    const text = document.getElementById('lan-url-display').textContent;
    navigator.clipboard.writeText(text).then(() => {
      const btn = document.getElementById('lan-copy-btn');
      btn.textContent = '✅ Copied!';
      setTimeout(() => { btn.textContent = '📋 Copy URL'; }, 2000);
    });
  }

  // ── 100% Offline ISO/IEC 18004 Standard QR Code Encoder ───────────────────
  function QR8bitByte(data) { this.mode = 4; this.data = data; }
  QR8bitByte.prototype = {
    getLength: function() { return this.data.length; },
    write: function(buf) { for (var i = 0; i < this.data.length; i++) buf.put(this.data.charCodeAt(i), 8); }
  };

  function QRCodeModel(typeNumber, errorCorrectLevel) {
    this.typeNumber = typeNumber;
    this.errorCorrectLevel = errorCorrectLevel;
    this.modules = null;
    this.moduleCount = 0;
    this.dataCache = null;
    this.dataList = [];
  }

  QRCodeModel.prototype = {
    addData: function(data) { this.dataList.push(new QR8bitByte(data)); this.dataCache = null; },
    isDark: function(row, col) { return this.modules[row][col]; },
    getModuleCount: function() { return this.moduleCount; },
    make: function() {
      if (this.typeNumber < 1) {
        var typeNumber = 1;
        for (typeNumber = 1; typeNumber < 40; typeNumber++) {
          var rsBlocks = QRRSBlock.getRSBlocks(typeNumber, this.errorCorrectLevel);
          var buffer = new QRBitBuffer();
          var totalDataCount = 0;
          for (var i = 0; i < rsBlocks.length; i++) totalDataCount += rsBlocks[i].dataCount;
          for (var j = 0; j < this.dataList.length; j++) {
            var data = this.dataList[j];
            buffer.put(data.mode, 4);
            buffer.put(data.getLength(), QRUtil.getLengthInBits(data.mode, typeNumber));
            data.write(buffer);
          }
          if (buffer.getLengthInBits() <= totalDataCount * 8) break;
        }
        this.typeNumber = typeNumber;
      }
      this.makeImpl(false, this.getBestMaskPattern());
    },
    makeImpl: function(test, maskPattern) {
      this.moduleCount = this.typeNumber * 4 + 17;
      this.modules = new Array(this.moduleCount);
      for (var row = 0; row < this.moduleCount; row++) {
        this.modules[row] = new Array(this.moduleCount);
        for (var col = 0; col < this.moduleCount; col++) this.modules[row][col] = null;
      }
      this.setupPositionProbePattern(0, 0);
      this.setupPositionProbePattern(this.moduleCount - 7, 0);
      this.setupPositionProbePattern(0, this.moduleCount - 7);
      this.setupPositionAdjustPattern();
      this.setupTimingPattern();
      this.setupTypeInfo(test, maskPattern);
      if (this.typeNumber >= 7) this.setupTypeNumber(test);
      if (this.dataCache == null) this.dataCache = QRCodeModel.createData(this.typeNumber, this.errorCorrectLevel, this.dataList);
      this.mapData(this.dataCache, maskPattern);
    },
    setupPositionProbePattern: function(row, col) {
      for (var r = -1; r <= 7; r++) {
        if (row + r <= -1 || this.moduleCount <= row + r) continue;
        for (var c = -1; c <= 7; c++) {
          if (col + c <= -1 || this.moduleCount <= col + c) continue;
          if ((0 <= r && r <= 6 && (c == 0 || c == 6)) ||
              (0 <= c && c <= 6 && (r == 0 || r == 6)) ||
              (2 <= r && r <= 4 && 2 <= c && c <= 4)) {
            this.modules[row + r][col + c] = true;
          } else {
            this.modules[row + r][col + c] = false;
          }
        }
      }
    },
    getBestMaskPattern: function() {
      var minLostPoint = 0, pattern = 0;
      for (var i = 0; i < 8; i++) {
        this.makeImpl(true, i);
        var lostPoint = QRUtil.getLostPoint(this);
        if (i == 0 || minLostPoint > lostPoint) { minLostPoint = lostPoint; pattern = i; }
      }
      return pattern;
    },
    setupTimingPattern: function() {
      for (var r = 8; r < this.moduleCount - 8; r++) { if (this.modules[r][6] == null) this.modules[r][6] = (r % 2 == 0); }
      for (var c = 8; c < this.moduleCount - 8; c++) { if (this.modules[6][c] == null) this.modules[6][c] = (c % 2 == 0); }
    },
    setupPositionAdjustPattern: function() {
      var pos = QRUtil.getPatternPosition(this.typeNumber);
      for (var i = 0; i < pos.length; i++) {
        for (var j = 0; j < pos.length; j++) {
          var row = pos[i], col = pos[j];
          if (this.modules[row][col] != null) continue;
          for (var r = -2; r <= 2; r++) {
            for (var c = -2; c <= 2; c++) {
              this.modules[row + r][col + c] = (r == -2 || r == 2 || c == -2 || c == 2 || (r == 0 && c == 0));
            }
          }
        }
      }
    },
    setupTypeNumber: function(test) {
      var bits = QRUtil.getBCHTypeNumber(this.typeNumber);
      for (var i = 0; i < 18; i++) {
        var mod = (!test && ((bits >> i) & 1) == 1);
        this.modules[Math.floor(i / 3)][i % 3 + this.moduleCount - 8 - 3] = mod;
        this.modules[i % 3 + this.moduleCount - 8 - 3][Math.floor(i / 3)] = mod;
      }
    },
    setupTypeInfo: function(test, maskPattern) {
      var data = (this.errorCorrectLevel << 3) | maskPattern;
      var bits = QRUtil.getBCHTypeInfo(data);
      for (var i = 0; i < 15; i++) {
        var mod = (!test && ((bits >> i) & 1) == 1);
        if (i < 6) this.modules[i][8] = mod;
        else if (i < 8) this.modules[i + 1][8] = mod;
        else this.modules[this.moduleCount - 15 + i][8] = mod;
        if (i < 8) this.modules[8][this.moduleCount - i - 1] = mod;
        else if (i < 9) this.modules[8][15 - i - 1 + 1] = mod;
        else this.modules[8][15 - i - 1] = mod;
      }
      this.modules[this.moduleCount - 8][8] = !test;
    },
    mapData: function(data, maskPattern) {
      var inc = -1, row = this.moduleCount - 1, bitIndex = 7, byteIndex = 0;
      var maskFunc = QRUtil.getMaskFunction(maskPattern);
      for (var col = this.moduleCount - 1; col > 0; col -= 2) {
        if (col == 6) col--;
        while (true) {
          for (var c = 0; c < 2; c++) {
            if (this.modules[row][col - c] == null) {
              var dark = false;
              if (byteIndex < data.length) dark = (((data[byteIndex] >>> bitIndex) & 1) == 1);
              if (maskFunc(row, col - c)) dark = !dark;
              this.modules[row][col - c] = dark;
              bitIndex--;
              if (bitIndex == -1) { byteIndex++; bitIndex = 7; }
            }
          }
          row += inc;
          if (row < 0 || this.moduleCount <= row) { row -= inc; inc = -inc; break; }
        }
      }
    },
    createSvgTag: function(cellSize, margin) {
      cellSize = cellSize || 5;
      margin = (typeof margin == 'undefined') ? 4 : margin;
      var size = this.getModuleCount();
      var fullSize = (size + margin * 2) * cellSize;
      var rects = '';
      for (var r = 0; r < size; r++) {
        for (var c = 0; c < size; c++) {
          if (this.isDark(r, c)) {
            var x = (c + margin) * cellSize;
            var y = (r + margin) * cellSize;
            rects += '<rect x="' + x + '" y="' + y + '" width="' + cellSize + '" height="' + cellSize + '" fill="#0f172a" />';
          }
        }
      }
      return '<svg width="' + fullSize + '" height="' + fullSize + '" viewBox="0 0 ' + fullSize + ' ' + fullSize + '" xmlns="http://www.w3.org/2000/svg"><rect width="' + fullSize + '" height="' + fullSize + '" fill="#ffffff" rx="6" />' + rects + '</svg>';
    }
  };

  QRCodeModel.createData = function(typeNumber, errorCorrectLevel, dataList) {
    var rsBlocks = QRRSBlock.getRSBlocks(typeNumber, errorCorrectLevel);
    var buffer = new QRBitBuffer();
    for (var i = 0; i < dataList.length; i++) {
      var data = dataList[i];
      buffer.put(data.mode, 4);
      buffer.put(data.getLength(), QRUtil.getLengthInBits(data.mode, typeNumber));
      data.write(buffer);
    }
    var totalDataCount = 0;
    for (var i = 0; i < rsBlocks.length; i++) totalDataCount += rsBlocks[i].dataCount;
    if (buffer.getLengthInBits() > totalDataCount * 8) throw new Error("QR length overflow");
    if (buffer.getLengthInBits() + 4 <= totalDataCount * 8) buffer.put(0, 4);
    while (buffer.getLengthInBits() % 8 != 0) buffer.putBit(false);
    while (true) {
      if (buffer.getLengthInBits() >= totalDataCount * 8) break;
      buffer.put(236, 8);
      if (buffer.getLengthInBits() >= totalDataCount * 8) break;
      buffer.put(17, 8);
    }
    return QRCodeModel.createBytes(buffer, rsBlocks);
  };

  QRCodeModel.createBytes = function(buffer, rsBlocks) {
    var offset = 0, maxDcCount = 0, maxEcCount = 0;
    var dcdata = new Array(rsBlocks.length), ecdata = new Array(rsBlocks.length);
    for (var r = 0; r < rsBlocks.length; r++) {
      var dcCount = rsBlocks[r].dataCount, ecCount = rsBlocks[r].totalCount - dcCount;
      maxDcCount = Math.max(maxDcCount, dcCount);
      maxEcCount = Math.max(maxEcCount, ecCount);
      dcdata[r] = new Array(dcCount);
      for (var i = 0; i < dcdata[r].length; i++) dcdata[r][i] = 0xff & buffer.buffer[i + offset];
      offset += dcCount;
      var rsPoly = QRUtil.getErrorCorrectPolynomial(ecCount);
      var rawPoly = new QRPolynomial(dcdata[r], rsPoly.getLength() - 1);
      var modPoly = rawPoly.mod(rsPoly);
      ecdata[r] = new Array(rsPoly.getLength() - 1);
      for (var i = 0; i < ecdata[r].length; i++) {
        var modIndex = i + modPoly.getLength() - ecdata[r].length;
        ecdata[r][i] = (modIndex >= 0) ? modPoly.get(modIndex) : 0;
      }
    }
    var totalCodeCount = 0;
    for (var i = 0; i < rsBlocks.length; i++) totalCodeCount += rsBlocks[i].totalCount;
    var data = new Array(totalCodeCount), index = 0;
    for (var i = 0; i < maxDcCount; i++) {
      for (var r = 0; r < rsBlocks.length; r++) { if (i < dcdata[r].length) data[index++] = dcdata[r][i]; }
    }
    for (var i = 0; i < maxEcCount; i++) {
      for (var r = 0; r < rsBlocks.length; r++) { if (i < ecdata[r].length) data[index++] = ecdata[r][i]; }
    }
    return data;
  };

  function QRRSBlock(totalCount, dataCount) { this.totalCount = totalCount; this.dataCount = dataCount; }
  var RS_BLOCK_TABLE = [
    [1, 26, 19], [1, 26, 16], [1, 26, 13], [1, 26, 9],
    [1, 44, 34], [1, 44, 28], [1, 44, 22], [1, 44, 16],
    [1, 70, 55], [1, 70, 44], [2, 35, 17], [2, 35, 13],
    [1, 100, 80], [2, 50, 32], [2, 50, 24], [4, 25, 9],
    [1, 134, 108], [2, 67, 43], [2, 33, 15, 2, 34, 16], [2, 33, 11, 2, 34, 12],
    [2, 86, 68], [4, 43, 27], [4, 43, 19], [4, 43, 15],
    [2, 98, 78], [4, 49, 31], [2, 32, 14, 4, 33, 15], [4, 39, 13, 1, 40, 14],
    [2, 121, 97], [2, 60, 38, 2, 61, 39], [4, 40, 18, 2, 41, 19], [4, 40, 14, 2, 41, 15]
  ];
  QRRSBlock.getRSBlocks = function(typeNumber, errorCorrectLevel) {
    var rsBlock = RS_BLOCK_TABLE[(typeNumber - 1) * 4 + errorCorrectLevel];
    var length = rsBlock.length / 3, list = [];
    for (var i = 0; i < length; i++) {
      list.push(new QRRSBlock(rsBlock[i * 3 + 1], rsBlock[i * 3 + 2]));
    }
    return list;
  };

  function QRBitBuffer() { this.buffer = []; this.length = 0; }
  QRBitBuffer.prototype = {
    put: function(num, length) { for (var i = 0; i < length; i++) this.putBit(((num >>> (length - i - 1)) & 1) == 1); },
    getLengthInBits: function() { return this.length; },
    putBit: function(bit) {
      var bufIndex = Math.floor(this.length / 8);
      if (this.buffer.length <= bufIndex) this.buffer.push(0);
      if (bit) this.buffer[bufIndex] |= (0x80 >>> (this.length % 8));
      this.length++;
    }
  };

  var QRMath = {
    glog: function(n) { return QRMath.LOG_TABLE[n]; },
    gexp: function(n) { while (n < 0) n += 255; while (n >= 256) n -= 255; return QRMath.EXP_TABLE[n]; },
    EXP_TABLE: new Array(256),
    LOG_TABLE: new Array(256)
  };
  for (var i = 0; i < 8; i++) QRMath.EXP_TABLE[i] = 1 << i;
  for (var i = 8; i < 256; i++) QRMath.EXP_TABLE[i] = QRMath.EXP_TABLE[i - 4] ^ QRMath.EXP_TABLE[i - 5] ^ QRMath.EXP_TABLE[i - 6] ^ QRMath.EXP_TABLE[i - 8];
  for (var i = 0; i < 255; i++) QRMath.LOG_TABLE[QRMath.EXP_TABLE[i]] = i;

  function QRPolynomial(num, shift) {
    var offset = 0;
    while (offset < num.length && num[offset] == 0) offset++;
    this.num = new Array(num.length - offset + shift);
    for (var i = 0; i < num.length - offset; i++) this.num[i] = num[i + offset];
  }
  QRPolynomial.prototype = {
    get: function(index) { return this.num[index]; },
    getLength: function() { return this.num.length; },
    multiply: function(e) {
      var num = new Array(this.getLength() + e.getLength() - 1);
      for (var i = 0; i < this.getLength(); i++) {
        for (var j = 0; j < e.getLength(); j++) num[i + j] ^= QRMath.gexp(QRMath.glog(this.get(i)) + QRMath.glog(e.get(j)));
      }
      return new QRPolynomial(num, 0);
    },
    mod: function(e) {
      if (this.getLength() - e.getLength() < 0) return this;
      var ratio = QRMath.glog(this.get(0)) - QRMath.glog(e.get(0));
      var num = new Array(this.getLength());
      for (var i = 0; i < this.getLength(); i++) num[i] = this.get(i);
      for (var i = 0; i < e.getLength(); i++) num[i] ^= QRMath.gexp(QRMath.glog(e.get(i)) + ratio);
      return new QRPolynomial(num, 0).mod(e);
    }
  };

  var QRUtil = {
    PATTERN_POSITION_TABLE: [[], [6, 18], [6, 22], [6, 26], [6, 30], [6, 34], [6, 22, 38], [6, 24, 42]],
    getPatternPosition: function(typeNumber) { return QRUtil.PATTERN_POSITION_TABLE[typeNumber - 1] || []; },
    getMaskFunction: function(maskPattern) {
      switch (maskPattern) {
        case 0: return function(i, j) { return (i + j) % 2 == 0; };
        case 1: return function(i, j) { return i % 2 == 0; };
        case 2: return function(i, j) { return j % 3 == 0; };
        case 3: return function(i, j) { return (i + j) % 3 == 0; };
        case 4: return function(i, j) { return (Math.floor(i / 2) + Math.floor(j / 3)) % 2 == 0; };
        case 5: return function(i, j) { return (i * j) % 2 + (i * j) % 3 == 0; };
        case 6: return function(i, j) { return ((i * j) % 2 + (i * j) % 3) % 2 == 0; };
        case 7: return function(i, j) { return ((i * j) % 3 + (i + j) % 2) % 2 == 0; };
        default: throw new Error("bad maskPattern:" + maskPattern);
      }
    },
    getErrorCorrectPolynomial: function(errorCorrectLength) {
      var a = new QRPolynomial([1], 0);
      for (var i = 0; i < errorCorrectLength; i++) a = a.multiply(new QRPolynomial([1, QRMath.gexp(i)], 0));
      return a;
    },
    getLengthInBits: function(mode, type) {
      if (type < 10) { return mode == 4 ? 8 : 8; }
      else { return mode == 4 ? 16 : 8; }
    },
    getLostPoint: function(qrCode) {
      var moduleCount = qrCode.getModuleCount(), lostPoint = 0;
      for (var row = 0; row < moduleCount; row++) {
        for (var col = 0; col < moduleCount; col++) {
          var sameCount = 0, dark = qrCode.isDark(row, col);
          for (var r = -1; r <= 1; r++) {
            if (row + r < 0 || moduleCount <= row + r) continue;
            for (var c = -1; c <= 1; c++) {
              if (col + c < 0 || moduleCount <= col + c || (r == 0 && c == 0)) continue;
              if (dark == qrCode.isDark(row + r, col + c)) sameCount++;
            }
          }
          if (sameCount > 5) lostPoint += (3 + sameCount - 5);
        }
      }
      return lostPoint;
    },
    getBCHTypeInfo: function(data) {
      var d = data << 10;
      while (QRUtil.getBCHDigit(d) - QRUtil.getBCHDigit(1335) >= 0) d ^= (1335 << (QRUtil.getBCHDigit(d) - QRUtil.getBCHDigit(1335)));
      return ((data << 10) | d) ^ 21522;
    },
    getBCHTypeNumber: function(data) {
      var d = data << 12;
      while (QRUtil.getBCHDigit(d) - QRUtil.getBCHDigit(7973) >= 0) d ^= (7973 << (QRUtil.getBCHDigit(d) - QRUtil.getBCHDigit(7973)));
      return (data << 12) | d;
    },
    getBCHDigit: function(data) { var digit = 0; while (data != 0) { digit++; data >>>= 1; } return digit; }
  };

  function generateStandardSvgQrCode(text, cellSize, margin) {
    if (!text) return '';
    try {
      cellSize = cellSize || 5;
      margin = (typeof margin === 'undefined') ? 4 : margin;
      var qr = new QRCodeModel(0, 1); // Level M
      qr.addData(String(text));
      qr.make();
      return qr.createSvgTag(cellSize, margin);
    } catch (e) {
      console.error("QR Code Generation Error:", e);
      return '';
    }
  }

  window.generateStandardSvgQrCode = generateStandardSvgQrCode;
  window.generateOfflineSvgQrCode = generateStandardSvgQrCode;

  // Boot breadcrumb and LAN Hub after sidebar is mounted
  setTimeout(() => {
    mountBreadcrumb();
    mountLANSharingHub();
  }, 400);

  // ═══════════════════════════════════════════════════════════════
  // GLOBAL EDUBOT IN-APP COPILOT SYSTEM
  // ═══════════════════════════════════════════════════════════════
  const EDUBOT_KB = [
    {
      keys: ['score', 'marks', 'entry', 'grade', 'bulk', 'input score', 'enter marks', 'enter score'],
      answer: '✍️ <b>Bulk Score Entry</b>:\n1. Open <b>Marks Entry</b> in sidebar.\n2. Select Class & Subject.\n3. Type marks and use <b>Arrow Keys</b> / <b>Enter</b> to jump between cells instantly.\n4. Real-time validation flags any score > 100.',
      action: { label: '🚀 Open Marks Entry', href: 'bulk-entry.html' }
    },
    {
      keys: ['broadsheet', 'rank', 'grading', 'a1', 'b2', 'waec', 'ges', 'position', 'terminal broadsheet'],
      answer: '📈 <b>Class Broadsheet & Ranking</b>:\n• Broadsheet automatically computes Total Scores, WAEC Grade equivalents (A1-F9), and Class Ranks.\n• Click <b>🖨️ Print Broadsheet</b> for an A4 landscape official sheet.',
      action: { label: '📈 Open Class Broadsheet', href: 'broadsheet.html' }
    },
    {
      keys: ['fee', 'payment', 'record payment', 'receipt', 'balance', 'momo', 'owing', 'debtor'],
      answer: '💰 <b>Fee Management</b>:\n• Search student name → Click <b>Record Payment</b>.\n• Supports MoMo, Bank, and Cash.\n• Receipts with official audit timestamps are generated automatically.',
      action: { label: '💰 Open Fee Ledger', href: 'fees.html' }
    },
    {
      keys: ['attendance', 'roll', 'present', 'absent', 'late', 'excused', 'take attendance'],
      answer: '📋 <b>1-Tap Attendance Register</b>:\n• Tap <b>[ P ]</b>, <b>[ A ]</b>, <b>[ L ]</b>, or <b>[ E ]</b> pills for rapid roll marking.\n• Use <b>[ All Present ]</b> for 1-click batch marking.\n• Tally strip updates class attendance % in real time.',
      action: { label: '📋 Open Attendance', href: 'attendance.html' }
    },
    {
      keys: ['report card', 'terminal report', 'pdf', 'generate report', 'print report'],
      answer: '📄 <b>Terminal Report Cards</b>:\n• Select Class & Term → Click <b>Generate Report Cards</b>.\n• Produces official portrait PDFs with school crest, grades, and headmaster signature line.',
      action: { label: '📄 Open Report Cards', href: 'reports.html' }
    },
    {
      keys: ['student', 'add student', 'enroll', 'admission', 'cssps', 'bece'],
      answer: '🎓 <b>Student Management</b>:\n• Add single students via <b>Students → Add New</b>.\n• Or import full CSSPS / BECE placement batches in bulk from Excel/CSV.',
      action: { label: '🎓 Open Student Directory', href: 'students.html' }
    },
    {
      keys: ['exeat', 'leave', 'permission', 'out pass', 'boarding'],
      answer: '🚪 <b>Exeat & Leave Passes</b>:\n• Log requests with departure date, expected return, and guardian contact.\n• Instant printable gate pass is produced upon approval.',
      action: { label: '🚪 Open Exeat Manager', href: 'exeat.html' }
    },
    {
      keys: ['discipline', 'incident', 'sanction', 'behaviour', 'punishment'],
      answer: '⚖️ <b>Discipline Records</b>:\n• Log infractions, disciplinary hearings, sanctions, and parent notifications with full history tracking.',
      action: { label: '⚖️ Open Discipline Records', href: 'discipline.html' }
    },
    {
      keys: ['timetable', 'schedule', 'period', 'class routine'],
      answer: '📅 <b>Timetable Builder</b>:\n• Allocate subjects and teachers to class periods with automatic teacher conflict detection.',
      action: { label: '📅 Open Timetable', href: 'timetable.html' }
    },
    {
      keys: ['super admin', 'multi school', 'switch school', 'all schools', 'backup', 'database'],
      answer: '👑 <b>Super Admin & Multi-School</b>:\n• Manage institutions, switch school context, monitor system telemetry, and perform SQLite database backups.',
      action: { label: '👑 Open Super Admin', href: 'super-admin.html' }
    },
    {
      keys: ['user', 'password', 'reset password', 'account', 'role', 'permission'],
      answer: '👤 <b>User & Role Management</b>:\n• Administrators can reset user passwords, assign roles (Teacher, Accountant, Form Master), and manage permissions.',
      action: { label: '👤 Open Users Module', href: 'users.html' }
    },
    {
      keys: ['message', 'sms', 'announcement', 'broadcast', 'parent notification'],
      answer: '💬 <b>Bulk Messaging & Announcements</b>:\n• Send targeted broadcasts to staff, classes, or parents via internal messaging or bulk SMS.',
      action: { label: '💬 Open Messaging Hub', href: 'messaging.html' }
    },
    {
      keys: ['offline', 'internet', 'sync', 'sqlite'],
      answer: '📴 <b>100% Offline Architecture</b>:\n• EduManage360 functions completely offline with local SQLite storage.\n• No internet connection is needed for daily operations.'
    }
  ];

  const ROLE_PERSONA_MAP = {
    super_admin: {
      title: 'Super Admin Copilot',
      greeting: '👑 Greetings, Super Administrator! How can I assist with multi-school governance, cloud synchronization, or database backups today?',
      chips: ['⚡ Cloud Pull Sync', '⚙️ Accredit Tracks', '📦 Backup Database', '📊 Multi-School Stats']
    },
    admin: {
      title: 'Administration Copilot',
      greeting: '🏫 Welcome, School Administrator! How can I help oversee academic operations, staff allocations, or student enrollment today?',
      chips: ['🎓 Enroll Student', '👥 Staff Directory', '📢 Broadcast Notice', '💰 Fee Ledger']
    },
    headmaster: {
      title: 'Executive Copilot',
      greeting: '🏛️ Welcome, Head of Institution! Ready to review school-wide analytics, class broadsheets, or staff workload today?',
      chips: ['📈 Broadsheets', '📊 Executive Analytics', '📢 Send Announcement', '🚨 At-Risk Students']
    },
    bursar: {
      title: 'Bursary & Finance Copilot',
      greeting: '💰 Welcome, Bursar! Ready to record fee payments, audit MoMo receipts, or inspect fee defaulters today?',
      chips: ['💰 Record Payment', '⚠️ Fee Debtors', '📢 SMS Reminders', '🧾 Print Receipt']
    },
    accountant: {
      title: 'Bursary & Finance Copilot',
      greeting: '💰 Welcome, Finance Officer! Ready to record payments, audit MoMo receipts, or inspect fee arrears today?',
      chips: ['💰 Record Payment', '⚠️ Fee Debtors', '📢 SMS Reminders', '🧾 Print Receipt']
    },
    housemaster: {
      title: 'Boarding & Exeat Copilot',
      greeting: '🏠 Welcome, Housemaster! How can I assist with boarding dormitories, nightly roll-call, or student gate passes today?',
      chips: ['📋 Night Roll Call', '🚪 Active Exeats', '⏰ Overdue Curfews', '🛏️ Dormitory Beds']
    },
    teacher: {
      title: 'Teaching & SBA Copilot',
      greeting: '✍️ Welcome, Educator! Ready to enter marks, inspect class broadsheets, or review lesson timetables today?',
      chips: ['✍️ Enter Marks', '⌨️ Speed Shortcuts', '📈 Class Broadsheet', '📅 My Timetable']
    },
    security_officer: {
      title: 'Security Gate Copilot',
      greeting: '🛡️ Welcome, Security Gate Officer! Ready to verify student exeat gate passes or log gate movements today?',
      chips: ['🚪 Scan/Verify Pass', '🚨 Security Incident', '📋 Gate Movements', '⏰ Curfew Check']
    }
  };

  const PAGE_CONTEXT_MAP = {
    'fees.html': {
      title: 'Fees Copilot',
      greeting: '👋 Hello! Need help logging payments, reconciling MoMo, or viewing fee defaulters?',
      chips: ['Record Payment', 'Debtor List', 'Print Receipt', 'MoMo Reconcile']
    },
    'broadsheet.html': {
      title: 'Broadsheet Copilot',
      greeting: '👋 Welcome to Class Broadsheets! Need help with WAEC score weighting, ranks, or printing?',
      chips: ['Class Rank Formula', 'WAEC Grading Scale', 'Print Broadsheet', 'Form Master Remarks']
    },
    'bulk-entry.html': {
      title: 'Marks Entry Copilot',
      greeting: '👋 Working on student marks? Use keyboard arrow keys to jump cells at top speed.',
      chips: ['Keyboard Shortcuts', 'Score Validation', 'Class Broadsheet', 'Report Cards']
    },
    'attendance.html': {
      title: 'Attendance Copilot',
      greeting: '👋 Ready to take attendance? Tap P/A/L pills or use Batch All Present for 1-click marking.',
      chips: ['Rapid Marking', 'Monthly Register', 'Absence Alerts', 'Print Register']
    },
    'students.html': {
      title: 'Student Directory Copilot',
      greeting: '👋 Managing student profiles? Use the quick filter chips above to filter by Boys, Girls, or Boarders.',
      chips: ['Add Student', 'CSSPS Import', 'Filter Chips', 'House Allocation']
    },
    'super-admin.html': {
      title: 'Super Admin Copilot',
      greeting: '👑 Welcome, Super Administrator! Manage institutions, database backups, and health diagnostics.',
      chips: ['Cloud Pull Sync', 'Accredit Tracks', 'Backup Database', 'Multi-School Stats']
    },
    'exeat.html': {
      title: 'Exeat & Gate Pass Copilot',
      greeting: '🚪 Managing student leaves? Check active gate passes, overdue curfews, or sign-out approvals.',
      chips: ['Issue Gate Pass', 'Overdue Exeats', 'Security Roster', 'Gate Sign In']
    },
    'dashboard.html': {
      title: 'Executive Copilot',
      greeting: '👋 Welcome to your Executive Overview! What module would you like to explore today?',
      chips: ['Enter Marks', 'Record Fees', 'Take Attendance', 'Class Broadsheet']
    }
  };

  function getAuthUserContext() {
    const token = localStorage.getItem('accessToken');
    let userRole = (localStorage.getItem('user_role') || '').toLowerCase();
    let username = localStorage.getItem('username') || '';
    if (token) {
      try {
        const payload = JSON.parse(atob(token.split('.')[1]));
        if (!username && payload.sub) username = payload.sub;
        if (!userRole && payload.roles && payload.roles.length) userRole = String(payload.roles[0]).toLowerCase();
      } catch (_) {}
    }
    return { username: username || 'Educator', role: userRole || 'staff' };
  }

  function mountEduBotGlobal() {
    const curPage = (window.location.pathname.split('/').pop() || 'index.html').toLowerCase().split('?')[0];
    const publicPages = ['index.html', 'auth.html', 'login.html', 'enrollment.html', 'parent-view.html', ''];
    if (publicPages.includes(curPage)) return;

    // Avoid double injection if global launcher or local edubot toggle is present
    if (document.getElementById('edubot-global-launcher') || document.getElementById('edubot-toggle')) return;
    if (!document.body) return;

    const userCtx = getAuthUserContext();
    const rolePersona = ROLE_PERSONA_MAP[userCtx.role] || null;
    const pageCtx = PAGE_CONTEXT_MAP[curPage] || null;

    const ctx = {
      title: (pageCtx && pageCtx.title) || (rolePersona && rolePersona.title) || 'EduBot Copilot',
      greeting: (pageCtx && pageCtx.greeting) || (rolePersona && rolePersona.greeting) || `👋 Hi <b>${userCtx.username}</b>! I'm <b>EduBot</b>, your in-app assistant. How can I help you today?`,
      chips: (pageCtx && pageCtx.chips) || (rolePersona && rolePersona.chips) || ['Enter Marks', 'Class Broadsheet', 'Record Payment', 'Take Attendance']
    };

    // 1. Create Floating Launcher with Drag & Position Memory
    const launcher = document.createElement('button');
    launcher.id = 'edubot-global-launcher';
    launcher.className = 'no-print';
    launcher.setAttribute('aria-label', 'Open EduBot Assistant');
    launcher.setAttribute('title', 'EduBot In-App Copilot (Alt+E)');
    launcher.innerHTML = '💬<span class="edubot-launcher-pulse"></span>';

    // Restore saved launcher position if available
    try {
      const savedPos = JSON.parse(localStorage.getItem('edubot_launcher_pos') || 'null');
      if (savedPos && savedPos.x !== undefined && savedPos.y !== undefined) {
        launcher.style.left = `${Math.min(Math.max(10, savedPos.x), window.innerWidth - 64)}px`;
        launcher.style.top = `${Math.min(Math.max(10, savedPos.y), window.innerHeight - 64)}px`;
        launcher.style.right = 'auto';
        launcher.style.bottom = 'auto';
      }
    } catch (_) {}

    document.body.appendChild(launcher);

    // Draggable Launcher Behavior
    let isDragging = false;
    let dragStartX = 0, dragStartY = 0;
    let initialX = 0, initialY = 0;
    let hasMoved = false;

    launcher.addEventListener('pointerdown', (e) => {
      isDragging = true;
      hasMoved = false;
      dragStartX = e.clientX;
      dragStartY = e.clientY;
      const rect = launcher.getBoundingClientRect();
      initialX = rect.left;
      initialY = rect.top;
      launcher.setPointerCapture(e.pointerId);
    });

    launcher.addEventListener('pointermove', (e) => {
      if (!isDragging) return;
      const dx = e.clientX - dragStartX;
      const dy = e.clientY - dragStartY;
      if (Math.abs(dx) > 5 || Math.abs(dy) > 5) {
        hasMoved = true;
        const newX = Math.min(Math.max(10, initialX + dx), window.innerWidth - 64);
        const newY = Math.min(Math.max(10, initialY + dy), window.innerHeight - 64);
        launcher.style.left = `${newX}px`;
        launcher.style.top = `${newY}px`;
        launcher.style.right = 'auto';
        launcher.style.bottom = 'auto';
      }
    });

    launcher.addEventListener('pointerup', (e) => {
      if (!isDragging) return;
      isDragging = false;
      try { launcher.releasePointerCapture(e.pointerId); } catch (_) {}
      if (hasMoved) {
        const rect = launcher.getBoundingClientRect();
        localStorage.setItem('edubot_launcher_pos', JSON.stringify({ x: rect.left, y: rect.top }));
      } else {
        toggleModal();
      }
    });

    // 2. Create Floating Dialog Modal
    const modal = document.createElement('div');
    modal.id = 'edubot-global-modal';
    modal.className = 'no-print';
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-label', 'EduBot Assistant');
    modal.innerHTML = `
      <div class="edubot-modal-header">
        <div class="edubot-header-left">
          <div class="edubot-avatar-box">🤖</div>
          <div class="edubot-title-wrap">
            <h4>${ctx.title}</h4>
            <span class="edubot-context-pill">● ${userCtx.role.toUpperCase()} · Offline Ready</span>
          </div>
        </div>
        <div class="edubot-header-actions">
          <button class="edubot-clear-btn" id="edubot-clear-chat-btn" title="Clear Chat History">🧹 Clear</button>
          <button class="edubot-close-btn" id="edubot-close-btn" aria-label="Close">✕</button>
        </div>
      </div>
      <div class="edubot-modal-body" id="edubot-modal-msgs"></div>
      <div class="edubot-chips-bar" id="edubot-modal-chips"></div>
      <div class="edubot-voice-status-bar" id="edubot-voice-status" style="display:none;"></div>
      <div class="edubot-input-footer">
        <input id="edubot-global-input" type="text" placeholder="Ask, or type 'find [student / class / teacher / house]'…" autocomplete="off" />
        <button id="edubot-voice-btn" class="no-print" title="Voice Search (Hands-Free Dictation)" aria-label="Voice Search">🎙️</button>
        <button id="edubot-global-send" aria-label="Send">➤</button>
      </div>
    `;
    document.body.appendChild(modal);

    const msgsBox = document.getElementById('edubot-modal-msgs');
    const chipsBox = document.getElementById('edubot-modal-chips');
    const voiceStatusEl = document.getElementById('edubot-voice-status');
    const input = document.getElementById('edubot-global-input');
    const voiceBtn = document.getElementById('edubot-voice-btn');
    const sendBtn = document.getElementById('edubot-global-send');
    const closeBtn = document.getElementById('edubot-close-btn');
    const clearBtn = document.getElementById('edubot-clear-chat-btn');

    let isOpen = false;

    let voiceStatusTimer = null;
    function showVoiceStatus(htmlMsg, statusType = 'info', autoHideMs = 0) {
      if (voiceStatusTimer) clearTimeout(voiceStatusTimer);
      if (!voiceStatusEl) return;
      voiceStatusEl.className = `edubot-voice-status-bar ${statusType}`;
      voiceStatusEl.innerHTML = htmlMsg;
      voiceStatusEl.style.display = 'flex';
      if (autoHideMs > 0) {
        voiceStatusTimer = setTimeout(() => hideVoiceStatus(), autoHideMs);
      }
    }

    function hideVoiceStatus() {
      if (voiceStatusEl) voiceStatusEl.style.display = 'none';
    }

    // Voice Dictation (Web Speech API) with Proactive Permission Priming
    let recognition = null;
    let isListening = false;
    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRec) {
      try {
        recognition = new SpeechRec();
        recognition.continuous = false;
        recognition.interimResults = false;
        recognition.lang = 'en-US';

        recognition.onstart = () => {
          isListening = true;
          voiceBtn.classList.add('listening');
          voiceBtn.setAttribute('title', 'Listening… speak now');
          showVoiceStatus('🔴 <b>Listening…</b> Say e.g. <i>"find Kojo Mensah"</i> or <i>"class 1 Science"</i>', 'listening');
        };

        recognition.onaudiostart = () => {
          showVoiceStatus('🔴 <b>Listening…</b> Speak clearly into your microphone', 'listening');
        };

        recognition.onresult = (evt) => {
          const transcript = evt.results[0][0].transcript;
          if (transcript) {
            input.value = transcript;
            showVoiceStatus(`✨ <b>Heard:</b> "${transcript}"`, 'transcribing', 1800);
            handleSend(transcript);
          }
        };

        recognition.onerror = (evt) => {
          isListening = false;
          voiceBtn.classList.remove('listening');
          if (evt.error === 'not-allowed' || evt.error === 'service-not-allowed') {
            showVoiceStatus('⚠️ <b>Microphone blocked.</b> Click the <b>🔒 lock icon</b> in your browser address bar to allow microphone.', 'error', 8000);
          } else if (evt.error === 'no-speech') {
            showVoiceStatus('👂 <b>No speech heard.</b> Tap 🎙️ and speak again.', 'warning', 3500);
          } else {
            showVoiceStatus(`⚠️ <b>Voice notice:</b> ${evt.error || 'Check microphone'}`, 'warning', 4000);
          }
        };

        recognition.onend = () => {
          isListening = false;
          voiceBtn.classList.remove('listening');
          voiceBtn.setAttribute('title', 'Voice Search (Hands-Free Dictation)');
        };

        voiceBtn.addEventListener('click', () => {
          if (!recognition) return;
          if (isListening) {
            recognition.stop();
            hideVoiceStatus();
          } else {
            showVoiceStatus('🎙️ <b>Activating microphone…</b> (Click <b>Allow</b> if prompted above)', 'info');
            try {
              recognition.start();
            } catch (_) {
              try {
                recognition.stop();
                setTimeout(() => recognition.start(), 150);
              } catch (e) {}
            }
          }
        });
      } catch (_) {
        if (voiceBtn) voiceBtn.style.display = 'none';
      }
    } else if (voiceBtn) {
      voiceBtn.style.display = 'none';
    }

    // Chat History in LocalStorage
    function saveHistory(msgObj) {
      try {
        let history = JSON.parse(localStorage.getItem('edubot_chat_history') || '[]');
        history.push(msgObj);
        if (history.length > 20) history = history.slice(-20);
        localStorage.setItem('edubot_chat_history', JSON.stringify(history));
      } catch (_) {}
    }

    function loadHistory() {
      try {
        const history = JSON.parse(localStorage.getItem('edubot_chat_history') || '[]');
        if (history.length > 0) {
          history.forEach(m => renderMessage(m.text, m.role, m.action, m.html, false));
          return true;
        }
      } catch (_) {}
      return false;
    }

    function clearHistory() {
      localStorage.removeItem('edubot_chat_history');
      msgsBox.innerHTML = '';
      renderMessage(ctx.greeting, 'bot', null, null, false);
      renderChips(ctx.chips);
    }

    function renderMessage(text, role, action, rawHtml, persist = true) {
      const msgDiv = document.createElement('div');
      msgDiv.className = `edubot-chat-msg ${role}`;
      let content = text ? text.replace(/\n/g, '<br/>') : '';
      if (rawHtml) {
        content += rawHtml;
      }
      if (action && action.href) {
        content += `<br/><a href="${action.href}" class="edubot-deep-btn">${action.label} →</a>`;
      }
      msgDiv.innerHTML = content;
      msgsBox.appendChild(msgDiv);
      msgsBox.scrollTop = msgsBox.scrollHeight;

      if (persist) {
        saveHistory({ text, role, action, html: rawHtml });
      }
    }

    function showTyping() {
      const t = document.createElement('div');
      t.className = 'edubot-typing-box';
      t.id = 'edubot-typing-indicator';
      t.innerHTML = '<span></span><span></span><span></span>';
      msgsBox.appendChild(t);
      msgsBox.scrollTop = msgsBox.scrollHeight;
    }

    function hideTyping() {
      const t = document.getElementById('edubot-typing-indicator');
      if (t) t.remove();
    }

    function renderChips(chipsList) {
      chipsBox.innerHTML = '';
      (chipsList || ctx.chips).forEach(chip => {
        const btn = document.createElement('button');
        btn.className = 'edubot-qr-chip';
        btn.textContent = chip;
        btn.onclick = () => handleSend(chip);
        chipsBox.appendChild(btn);
      });
    }

    // Multi-Entity Search Engine (Students, Classes, Teachers/Staff, Houses)
    async function executeUniversalEntitySearch(rawQuery) {
      const qClean = rawQuery.replace(/^(find|search|lookup|who is|check fee for|balance for|exeat for)\s+/i, '').trim();
      if (!qClean) return null;

      const token = localStorage.getItem('accessToken');
      const apiBase = window.API_BASE || (window.location.origin.includes('http') ? (window.location.origin + '/api') : 'http://127.0.0.1:8000/api');
      const headers = token ? { 'Authorization': `Bearer ${token}` } : {};

      const lowerQ = qClean.toLowerCase();

      // 1. Check if query is targeting a Class / Form section
      if (lowerQ.startsWith('class') || lowerQ.startsWith('form') || lowerQ.startsWith('stream') || lowerQ.startsWith('grade')) {
        const term = lowerQ.replace(/^(class|form|stream|grade)\s*/i, '').trim();
        try {
          const res = await fetch(`${apiBase}/classes/`, { headers });
          if (res.ok) {
            const classes = await res.json();
            const matched = classes.filter(c => !term || (c.name && c.name.toLowerCase().includes(term)) || (c.stage_name && c.stage_name.toLowerCase().includes(term)));
            if (matched.length > 0) {
              const top = matched.slice(0, 3);
              const cards = top.map(c => `
                <div class="edubot-entity-card">
                  <div class="edubot-entity-header">
                    <div class="edubot-entity-avatar" style="background: linear-gradient(135deg, #6366f1, #4f46e5);">🏫</div>
                    <div>
                      <div style="display:flex; align-items:center; gap:6px;">
                        <strong style="color:var(--text-primary, #fff); font-size:0.88rem;">${c.name}</strong>
                        <span class="edubot-entity-badge class">Class</span>
                      </div>
                      <div style="font-size:0.75rem; opacity:0.8;">${c.stage_name || ''} • ${c.program_name || 'General Program'}</div>
                    </div>
                  </div>
                  <div class="edubot-entity-details">
                    <span>🧑‍🏫 Form Master: <b>${c.form_master_name || 'Unassigned'}</b></span>
                  </div>
                  <div class="edubot-entity-actions">
                    <a href="attendance.html" class="edubot-card-btn">📋 Attendance</a>
                    <a href="broadsheet.html" class="edubot-card-btn">📈 Broadsheet</a>
                    <a href="bulk-entry.html" class="edubot-card-btn">📝 Marks</a>
                    <a href="students.html" class="edubot-card-btn">👥 Students</a>
                  </div>
                </div>
              `).join('');
              return {
                text: `🏫 Found <b>${matched.length}</b> class section match${matched.length > 1 ? 'es' : ''}:`,
                html: cards
              };
            }
          }
        } catch (_) {}
      }

      // 2. Check if query is targeting a House / Dormitory
      if (lowerQ.startsWith('house') || lowerQ.startsWith('dorm') || lowerQ.startsWith('hall')) {
        const term = lowerQ.replace(/^(house|dorm|dormitory|hall)\s*/i, '').trim();
        try {
          const res = await fetch(`${apiBase}/houses/`, { headers });
          if (res.ok) {
            const houses = await res.json();
            const matched = houses.filter(h => !term || (h.name && h.name.toLowerCase().includes(term)));
            if (matched.length > 0) {
              const top = matched.slice(0, 3);
              const cards = top.map(h => `
                <div class="edubot-entity-card">
                  <div class="edubot-entity-header">
                    <div class="edubot-entity-avatar" style="background: linear-gradient(135deg, #ec4899, #db2777);">🏠</div>
                    <div>
                      <div style="display:flex; align-items:center; gap:6px;">
                        <strong style="color:var(--text-primary, #fff); font-size:0.88rem;">${h.name}</strong>
                        <span class="edubot-entity-badge house">House</span>
                      </div>
                      <div style="font-size:0.75rem; opacity:0.8;">Gender: ${h.gender || 'Mixed'} • Capacity: ${h.capacity || 0} Beds</div>
                    </div>
                  </div>
                  <div class="edubot-entity-details">
                    <span>🧑‍💼 Housemaster: <b>${h.house_master_name || 'Unassigned'}</b></span>
                  </div>
                  <div class="edubot-entity-actions">
                    <a href="exeat.html" class="edubot-card-btn">🚪 Exeats</a>
                    <a href="houses.html" class="edubot-card-btn">🏠 House Manager</a>
                    <a href="students.html" class="edubot-card-btn">👥 Boarders</a>
                  </div>
                </div>
              `).join('');
              return {
                text: `🏠 Found <b>${matched.length}</b> boarding house match${matched.length > 1 ? 'es' : ''}:`,
                html: cards
              };
            }
          }
        } catch (_) {}
      }

      // 3. Check if query is targeting a Teacher / Staff Member
      if (lowerQ.startsWith('teacher') || lowerQ.startsWith('staff') || lowerQ.startsWith('sir') || lowerQ.startsWith('madam') || lowerQ.startsWith('mr') || lowerQ.startsWith('mrs')) {
        const term = lowerQ.replace(/^(teacher|staff|sir|madam|mr|mrs|ms)\s*/i, '').trim();
        try {
          const res = await fetch(`${apiBase}/users/`, { headers });
          if (res.ok) {
            const users = await res.json();
            const matched = users.filter(u => {
              const uName = (u.username || '').toLowerCase();
              const uEmail = (u.email || '').toLowerCase();
              return term && (uName.includes(term) || uEmail.includes(term));
            });
            if (matched.length > 0) {
              const top = matched.slice(0, 3);
              const cards = top.map(u => {
                const rolesList = (u.roles || []).map(r => typeof r === 'string' ? r : r.name).join(', ') || 'Staff';
                return `
                  <div class="edubot-entity-card">
                    <div class="edubot-entity-header">
                      <div class="edubot-entity-avatar" style="background: linear-gradient(135deg, #f59e0b, #d97706);">🧑‍🏫</div>
                      <div>
                        <div style="display:flex; align-items:center; gap:6px;">
                          <strong style="color:var(--text-primary, #fff); font-size:0.88rem;">${u.username}</strong>
                          <span class="edubot-entity-badge teacher">${rolesList.split(',')[0]}</span>
                        </div>
                        <div style="font-size:0.75rem; opacity:0.8;">${u.email || 'No email'} • ${u.department_name || 'Academic Dept'}</div>
                      </div>
                    </div>
                    <div class="edubot-entity-details">
                      <span>🔑 Roles: <b>${rolesList}</b></span>
                    </div>
                    <div class="edubot-entity-actions">
                      <a href="timetable.html" class="edubot-card-btn">📅 Timetable</a>
                      <a href="messaging.html" class="edubot-card-btn">✉️ Message</a>
                      <a href="users.html" class="edubot-card-btn">👤 User Account</a>
                    </div>
                  </div>
                `;
              }).join('');
              return {
                text: `🧑‍🏫 Found <b>${matched.length}</b> staff match${matched.length > 1 ? 'es' : ''}:`,
                html: cards
              };
            }
          }
        } catch (_) {}
      }

      // 4. Default / Student Entity Search
      try {
        const res = await fetch(`${apiBase}/students/?search=${encodeURIComponent(qClean)}`, { headers });
        if (res.ok) {
          const students = await res.json();
          if (students && students.length > 0) {
            const topMatches = students.slice(0, 3);
            const cardsHtml = topMatches.map(s => {
              const sName = s.full_name || `${s.first_name || ''} ${s.last_name || ''}`.trim() || 'Student';
              const sClass = s.class_section?.name || s.class_name || 'Unassigned Class';
              const sHouse = s.house?.name || s.house_name || (s.residential_status === 'Day' ? 'Day Student' : 'Boarding');
              const bal = typeof s.fee_balance === 'number' ? s.fee_balance : 0;

              return `
                <div class="edubot-entity-card">
                  <div class="edubot-entity-header">
                    <div class="edubot-entity-avatar">🎓</div>
                    <div>
                      <div style="display:flex; align-items:center; gap:6px;">
                        <strong style="color:var(--text-primary, #fff); font-size:0.88rem;">${sName}</strong>
                        <span class="edubot-entity-badge student">Student</span>
                      </div>
                      <div style="font-size:0.75rem; opacity:0.8;">ID: ${s.index_number || s.id} • ${sClass}</div>
                    </div>
                  </div>
                  <div class="edubot-entity-details">
                    <span>🏠 ${sHouse}</span>
                    <span>💰 Balance: GH₵ ${bal.toLocaleString('en-US', { minimumFractionDigits: 2 })}</span>
                  </div>
                  <div class="edubot-entity-actions">
                    <a href="students.html" class="edubot-card-btn">👤 Profile</a>
                    <a href="fees.html" class="edubot-card-btn">💰 Fees</a>
                    <a href="exeat.html" class="edubot-card-btn">🚪 Exeat</a>
                    <a href="bulk-entry.html" class="edubot-card-btn">📝 Marks</a>
                  </div>
                </div>
              `;
            }).join('');

            return {
              text: `🔍 Found <b>${students.length}</b> student match${students.length > 1 ? 'es' : ''} in the local database:`,
              html: cardsHtml
            };
          }
        }
      } catch (_) {}

      return {
        text: `🔍 I searched the school directory for "<b>${qClean}</b>", but found no matching records. Try searching for a specific <b>student</b>, <b>class</b> (e.g. <i>class 1 Science</i>), <b>teacher</b> (e.g. <i>teacher Kwame</i>), or <b>house</b> (e.g. <i>house Aggrey</i>).`,
        html: null
      };
    }

    async function processQuery(query) {
      const q = query.toLowerCase().trim();

      // 1. Direct System Commands
      if (q === 'dark mode' || q === 'midnight') {
        if (window.setTheme) window.setTheme('midnight');
        else document.body.setAttribute('data-theme', 'midnight');
        return { text: '🌙 Switched to Midnight Dark theme.', action: null, html: null };
      }
      if (q === 'light mode') {
        if (window.setTheme) window.setTheme('light');
        else document.body.setAttribute('data-theme', 'light');
        return { text: '☀️ Switched to Crisp Light theme.', action: null, html: null };
      }
      if (q === 'emerald') {
        if (window.setTheme) window.setTheme('emerald');
        return { text: '🌲 Switched to Forest Emerald theme.', action: null, html: null };
      }
      if (q === 'clear' || q === 'clear chat') {
        clearHistory();
        return null;
      }

      // 2. Universal Entity Search Detection
      const searchTriggers = ['find', 'search', 'lookup', 'student', 'class', 'form', 'stream', 'teacher', 'staff', 'house', 'who is', 'check fee', 'balance for', 'exeat for'];
      const isSearchIntent = searchTriggers.some(t => q.startsWith(t)) || (q.split(' ').length <= 3 && !EDUBOT_KB.some(k => k.keys.some(key => q.includes(key))));

      if (isSearchIntent) {
        const searchResult = await executeUniversalEntitySearch(query);
        if (searchResult) {
          return { text: searchResult.text, html: searchResult.html, action: null };
        }
      }

      // 3. Static KB Matcher
      for (const item of EDUBOT_KB) {
        if (item.keys.some(k => q.includes(k))) {
          return { text: item.answer, action: item.action, html: null };
        }
      }

      // 4. Fallback Guidance
      return {
        text: `🤔 I didn't recognize that exact request. You can:\n• Type <b>"find [Student / Class / Teacher / House]"</b> to look up institutional records\n• Tap 🎙️ for hands-free voice dictation\n• Ask about <b>marks entry</b>, <b>broadsheets</b>, <b>fees</b>, or <b>exeats</b>\n• Use the Command Palette (<b>Ctrl+K</b>)`,
        action: null,
        html: null
      };
    }

    async function handleSend(text) {
      const q = (text || input.value).trim();
      if (!q) return;
      renderMessage(q, 'user');
      input.value = '';
      chipsBox.innerHTML = '';
      showTyping();

      const res = await processQuery(q);
      hideTyping();

      if (res) {
        renderMessage(res.text, 'bot', res.action, res.html);
        renderChips(ctx.chips);
      }
    }

    function toggleModal(open) {
      isOpen = open !== undefined ? open : !isOpen;
      modal.classList.toggle('open', isOpen);
      launcher.classList.toggle('open', isOpen);
      launcher.innerHTML = isOpen ? '✕' : '💬<span class="edubot-launcher-pulse"></span>';
      if (isOpen) {
        if (msgsBox.children.length === 0) {
          const hadHistory = loadHistory();
          if (!hadHistory) {
            renderMessage(ctx.greeting, 'bot', null, null, false);
          }
          renderChips(ctx.chips);
        }
        setTimeout(() => input.focus(), 150);
      }
    }

    closeBtn.addEventListener('click', () => toggleModal(false));
    clearBtn.addEventListener('click', () => clearHistory());
    sendBtn.addEventListener('click', () => handleSend());
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') handleSend();
    });

    // Global keyboard shortcut: Alt+E or '?' when not typing in an input
    document.addEventListener('keydown', (e) => {
      if (e.altKey && (e.key === 'e' || e.key === 'E')) {
        e.preventDefault();
        toggleModal();
      } else if (e.key === '?' && !['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName)) {
        e.preventDefault();
        toggleModal(true);
      } else if (e.key === 'Escape' && isOpen) {
        toggleModal(false);
      }
    });
  }

  // Boot Global EduBot Copilot
  setTimeout(() => mountEduBotGlobal(), 450);
})();





