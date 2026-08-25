/**
 * theme.js — Theme Management & Offline Logo Color Extractor
 * Supports: Midnight Dark, Light Executive, Emerald Oasis, Ocean Sapphire, and Auto-Logo Branding
 */

(function () {
  // Immediately enforce sidebar layout mode for application pages (excluding public landing & auth pages)
  const _initialPage = (window.location.pathname.split("/").pop() || "").toLowerCase();
  const _publicPages = ["index.html", "auth.html", "login.html", ""];
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

  // ── 3. Theme Application ──────────────────────────────────────────────────
  window.applyTheme = function (themeName, customColors) {
    const root = document.documentElement;
    const selectedTheme = themeName || localStorage.getItem("system_theme") || "midnight";
    localStorage.setItem("system_theme", selectedTheme);

    if (selectedTheme === "auto") {
      let colors = customColors;
      if (!colors) {
        try {
          colors = JSON.parse(localStorage.getItem("logo_theme_colors"));
        } catch (_) {}
      }

      if (colors && colors.primary) {
        root.setAttribute("data-theme", "auto");
        root.style.setProperty("--primary", colors.primary);
        root.style.setProperty("--primary-hover", colors.primaryHover || adjustBrightness(colors.primary, -15));
        root.style.setProperty("--primary-light", colors.primary + "26");
        root.style.setProperty("--secondary", colors.secondary || "#06b6d4");

        // Calculate luminance of primary color to adapt background & text contrast
        const hex = colors.primary.replace("#", "");
        const r = parseInt(hex.substring(0, 2), 16) || 0;
        const g = parseInt(hex.substring(2, 4), 16) || 0;
        const b = parseInt(hex.substring(4, 6), 16) || 0;
        const lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255;

        if (lum > 0.7) {
          // Dark background for bright primary logo colors
          root.style.setProperty("--bg", "#0f172a");
          root.style.setProperty("--bg-gradient", `radial-gradient(circle at top right, ${colors.primary}22, #0f172a 70%)`);
          root.style.setProperty("--card-bg", "rgba(30, 41, 59, 0.85)");
          root.style.setProperty("--border-color", `${colors.primary}33`);
          root.style.setProperty("--text-primary", "#f8fafc");
          root.style.setProperty("--text-secondary", "#94a3b8");
          root.style.setProperty("--input-bg", "rgba(15, 23, 42, 0.7)");
        } else {
          // Clean modern light background tinted with primary logo accent
          root.style.setProperty("--bg", "#f8fafc");
          root.style.setProperty("--bg-gradient", `linear-gradient(135deg, ${colors.primary}12 0%, #f1f5f9 100%)`);
          root.style.setProperty("--card-bg", "#ffffff");
          root.style.setProperty("--border-color", `${colors.primary}30`);
          root.style.setProperty("--text-primary", "#0f172a");
          root.style.setProperty("--text-secondary", "#475569");
          root.style.setProperty("--input-bg", "#ffffff");
        }
        return;
      }
    }

    // Reset element-level overrides for named presets
    root.style.removeProperty("--primary");
    root.style.removeProperty("--primary-hover");
    root.style.removeProperty("--primary-light");
    root.style.removeProperty("--secondary");
    root.style.removeProperty("--bg");
    root.style.removeProperty("--bg-gradient");
    root.style.removeProperty("--card-bg");
    root.style.removeProperty("--border-color");
    root.style.removeProperty("--text-primary");
    root.style.removeProperty("--text-secondary");
    root.style.removeProperty("--input-bg");
    root.setAttribute("data-theme", selectedTheme);
  };

  // ── 4. Sidebar View Layout Controller & Navigation ────────────────────
  window.applyLayout = function (layoutMode) {
    const currentPath = (window.location.pathname.split("/").pop() || "").toLowerCase();
    if (currentPath === "auth.html" || currentPath === "login.html") {
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
          if (href.includes('programs.html') || href.includes('departments.html') || href.includes('transcript') || href.includes('houses.html')) {
            item.style.display = 'none';
            return;
          }
        }
        if (isShsOnly && href.includes('cumulative-record.html')) {
          item.style.display = 'none';
          return;
        }
        if (boardingStatus === 'DAY_ONLY' && (href.includes('houses.html') || href.includes('exeat.html'))) {
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
    if (document.body && (document.body.id === "public-landing-page" || document.body.classList.contains("public-landing-page"))) return;
    const currentPath = (window.location.pathname.split("/").pop() || "").toLowerCase().split("?")[0];
    const publicPages = ["index.html", "auth.html", "login.html", ""];
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

    const accordionStates = JSON.parse(localStorage.getItem('sidebar_accordion_states') || '{}');

    // ── Use centralized feature gate (from featureGate.js) ────────────────────
    // Falls back gracefully if featureGate.js is not yet loaded.
    const F = (window.SchoolFeatures && window.SchoolFeatures.version)
      ? window.SchoolFeatures
      : (window.FeatureGate ? window.FeatureGate.getFeatures() : null);

    const schoolMode     = F ? F.schoolMode     : (localStorage.getItem('school_mode')     || 'COMBINED').toUpperCase();
    const boardingStatus = F ? F.boardingStatus : (localStorage.getItem('boarding_status') || 'BOARDING_AND_DAY').toUpperCase();
    const isBasicOnly    = F ? F.isBasicOnly    : (schoolMode === 'BASIC_ONLY');
    const isShsOnly      = F ? F.isShsOnly      : (schoolMode === 'SHS_ONLY');
    const isCombined     = F ? F.isCombined     : (schoolMode === 'COMBINED');
    const isBoarding     = F ? F.isBoarding     : (boardingStatus === 'BOARDING_AND_DAY');

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
      { href: 'exeat.html', icon: '🎟️', label: 'Exeat Management', boardingOnly: true },
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
    const publicPages = ['index.html', 'auth.html', 'login.html', ''];
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
    const publicPages = ['index.html', 'auth.html', 'login.html', ''];
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

  // Boot breadcrumb after sidebar is mounted
  setTimeout(() => mountBreadcrumb(), 400);

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
      chips: ['Switch School', 'Backup Database', 'Add School', 'User Roles']
    },
    'dashboard.html': {
      title: 'Dashboard Copilot',
      greeting: '👋 Welcome to your Executive Overview! What module would you like to explore today?',
      chips: ['Enter Marks', 'Record Fees', 'Take Attendance', 'Class Broadsheet']
    }
  };

  function mountEduBotGlobal() {
    const curPage = (window.location.pathname.split('/').pop() || 'index.html').toLowerCase().split('?')[0];
    const publicPages = ['index.html', 'auth.html', 'login.html', ''];
    if (publicPages.includes(curPage)) return;

    // Avoid double injection if global launcher or local edubot toggle is present
    if (document.getElementById('edubot-global-launcher') || document.getElementById('edubot-toggle')) return;
    if (!document.body) return;
    const ctx = PAGE_CONTEXT_MAP[curPage] || {
      title: 'EduBot Copilot',
      greeting: '👋 Hi! I\'m <b>EduBot</b>, your in-app assistant. How can I help you today?',
      chips: ['Enter Marks', 'Class Broadsheet', 'Record Payment', 'Take Attendance']
    };

    // 1. Create Floating Launcher
    const launcher = document.createElement('button');
    launcher.id = 'edubot-global-launcher';
    launcher.className = 'no-print';
    launcher.setAttribute('aria-label', 'Open EduBot Assistant');
    launcher.setAttribute('title', 'EduBot In-App Copilot (Alt+E)');
    launcher.innerHTML = '💬<span class="edubot-launcher-pulse"></span>';
    document.body.appendChild(launcher);

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
            <h4>EduBot Copilot</h4>
            <span class="edubot-context-pill">● ${ctx.title} · Offline Ready</span>
          </div>
        </div>
        <button class="edubot-close-btn" id="edubot-close-btn" aria-label="Close">✕</button>
      </div>
      <div class="edubot-modal-body" id="edubot-modal-msgs"></div>
      <div class="edubot-chips-bar" id="edubot-modal-chips"></div>
      <div class="edubot-input-footer">
        <input id="edubot-global-input" type="text" placeholder="Ask EduBot anything (or press ?)…" autocomplete="off" />
        <button id="edubot-global-send" aria-label="Send">➤</button>
      </div>
    `;
    document.body.appendChild(modal);

    const msgsBox = document.getElementById('edubot-modal-msgs');
    const chipsBox = document.getElementById('edubot-modal-chips');
    const input = document.getElementById('edubot-global-input');
    const sendBtn = document.getElementById('edubot-global-send');
    const closeBtn = document.getElementById('edubot-close-btn');

    let isOpen = false;

    function renderMessage(text, role, action) {
      const msgDiv = document.createElement('div');
      msgDiv.className = `edubot-chat-msg ${role}`;
      let content = text.replace(/\n/g, '<br/>');
      if (action && action.href) {
        content += `<br/><a href="${action.href}" class="edubot-deep-btn">${action.label} →</a>`;
      }
      msgDiv.innerHTML = content;
      msgsBox.appendChild(msgDiv);
      msgsBox.scrollTop = msgsBox.scrollHeight;
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

    function findAnswer(query) {
      const q = query.toLowerCase();
      for (const item of EDUBOT_KB) {
        if (item.keys.some(k => q.includes(k))) return item;
      }
      return {
        answer: "🤔 I'm not sure about that specific query. You can ask about <b>marks entry</b>, <b>broadsheets</b>, <b>fees</b>, <b>attendance</b>, or <b>report cards</b>, or use the Command Palette (<b>Ctrl+K</b>).",
        action: null
      };
    }

    function handleSend(text) {
      const q = (text || input.value).trim();
      if (!q) return;
      renderMessage(q, 'user');
      input.value = '';
      chipsBox.innerHTML = '';
      showTyping();
      setTimeout(() => {
        hideTyping();
        const res = findAnswer(q);
        renderMessage(res.answer, 'bot', res.action);
        renderChips(ctx.chips);
      }, 450);
    }

    function toggleModal(open) {
      isOpen = open !== undefined ? open : !isOpen;
      modal.classList.toggle('open', isOpen);
      launcher.classList.toggle('open', isOpen);
      launcher.innerHTML = isOpen ? '✕' : '💬<span class="edubot-launcher-pulse"></span>';
      if (isOpen) {
        if (msgsBox.children.length === 0) {
          renderMessage(ctx.greeting, 'bot');
          renderChips(ctx.chips);
        }
        setTimeout(() => input.focus(), 150);
      }
    }

    launcher.addEventListener('click', () => toggleModal());
    closeBtn.addEventListener('click', () => toggleModal(false));
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





