/**
 * theme.js — Theme Management & Offline Logo Color Extractor
 * Supports: Midnight Dark, Light Executive, Emerald Oasis, Ocean Sapphire, and Auto-Logo Branding
 */

(function () {
  // Immediately enforce sidebar layout mode for all application pages
  const _initialPage = (window.location.pathname.split("/").pop() || "").toLowerCase();
  if (_initialPage !== "auth.html" && _initialPage !== "login.html") {
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
    const rawPath = window.location.pathname.split("/").pop() || "dashboard.html";
    const currentPath = rawPath.toLowerCase();
    if (currentPath === "auth.html" || currentPath === "login.html") return;
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

    const schoolMode = (localStorage.getItem('school_mode') || 'COMBINED').toUpperCase();
    const boardingStatus = (localStorage.getItem('boarding_status') || 'BOARDING_AND_DAY').toUpperCase();
    const isBasicOnly = schoolMode === 'BASIC_ONLY';
    const isShsOnly = schoolMode === 'SHS_ONLY';

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
    const isActiveAdmin = ['admin', 'super_admin'].includes(activeRole);

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
      const href = (i.href || '').toLowerCase();
      if (isBasicOnly) {
        if (i.shsOnly || href.includes('programs.html') || href.includes('departments.html') || href.includes('transcript') || href.includes('houses.html')) {
          return false;
        }
      }
      if (i.shsOnly && isBasicOnly) return false;
      if (i.basicOnly && isShsOnly) return false;
      if (i.boardingOnly && boardingStatus === 'DAY_ONLY') return false;

      if (!isActiveAdmin) {
        const cleanHref = href.split('?')[0].split('/').pop();
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

    const logoHtml = (isSuperAdmin && !isViewing)
      ? '<img src="assets/logo_compact.png" class="sidebar-logo-img" style="height:28px; width:28px; object-fit:cover; border-radius:6px; flex-shrink:0;" />'
      : (schoolLogo ? `<img src="${schoolLogo}" class="sidebar-logo-img" style="height:30px; width:30px; object-fit:cover; border-radius:8px; flex-shrink:0;" />` : '<span style="font-size:1.3rem; flex-shrink:0;">🏫</span>');

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

    // Remove any previously auto-injected hamburger buttons if present
    const existingHamburger = document.querySelector('.mobile-sidebar-toggle-btn');
    if (existingHamburger) {
      existingHamburger.remove();
    }

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

  // ── 5. Global Keyboard Shortcuts (Ctrl + K or '/') ─────────────────────────
  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey && e.key.toLowerCase() === 'k') || (e.key === '/' && !['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName))) {
      e.preventDefault();
      const sidebar = document.querySelector('.app-sidebar');
      if (sidebar && sidebar.classList.contains('collapsed')) {
        window.toggleSidebarCollapse();
      }
      const filterInput = document.getElementById('sidebarFilterInput');
      if (filterInput) {
        filterInput.focus();
        filterInput.select();
      }
    }
  });

  // Immediate execution + DOMContentLoaded fallback
  const savedTheme = localStorage.getItem("system_theme") || "midnight";
  window.applyTheme(savedTheme);

  if (document.readyState === 'loading') {
    document.addEventListener("DOMContentLoaded", () => window.applyLayout("sidebar"));
  } else {
    window.applyLayout("sidebar");
  }
})();



