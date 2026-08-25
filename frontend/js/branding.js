/**
 * branding.js — Applies school name, logo, and page title from /api/settings/
 * Injected on every page that has a .topbar element.
 * Works without authentication (settings endpoint is public).
 */
(async function applyBranding() {
  try {
    const API_BASE = window.API_BASE || (window.location.origin.includes('http') ? (window.location.origin + '/api') : 'http://127.0.0.1:8000/api');
    const token = localStorage.getItem('accessToken');
    const headers = token ? { 'Authorization': `Bearer ${token}` } : {};
    const res = await fetch(`${API_BASE}/settings/`, { headers });
    if (!res.ok) return;
    const s = await res.json();

    const isSuperAdmin = (localStorage.getItem('is_super_admin') === 'true' || localStorage.getItem('userRole') === 'super_admin') && localStorage.getItem('userRole') !== 'admin' && !localStorage.getItem('is_super_admin_viewing');
    const isViewing = localStorage.getItem('is_super_admin_viewing') === 'true';

    let currentSchoolName = '';
    let currentSchoolAbbr = '';

    if (isSuperAdmin && !isViewing) {
      currentSchoolName = 'Master System Portal';
      currentSchoolAbbr = 'SUPER ADMIN';
      localStorage.setItem('school_name', currentSchoolName);
      localStorage.setItem('school_abbreviation', currentSchoolAbbr);
    } else {
      currentSchoolName = (isViewing ? localStorage.getItem('school_name') : null) || s.school_name || localStorage.getItem('school_name') || 'School Management';
      currentSchoolAbbr = (isViewing ? localStorage.getItem('school_abbreviation') : null) || s.school_code || s.school_abbreviation || localStorage.getItem('school_abbreviation') || currentSchoolName;

      if (currentSchoolName && currentSchoolName !== 'Master System Portal') {
        localStorage.setItem('school_name', currentSchoolName);
      }
      if (currentSchoolAbbr && currentSchoolAbbr !== 'SUPER ADMIN') {
        localStorage.setItem('school_abbreviation', currentSchoolAbbr);
      }
    }

    // ── Unified Vector School Crest Generator ───────────────────────
    window.createDefaultCrestSvg = function(abbr, size = 34) {
      const cleanAbbr = (abbr || 'SMS').trim().substring(0, 4).toUpperCase();
      const fontSize = cleanAbbr.length >= 4 ? 9 : (cleanAbbr.length === 3 ? 11 : 13);
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

    const topbar = document.querySelector('.topbar');
    if (topbar) {
      let nameEl = document.getElementById('schoolNameHeader');
      let logoContainer = document.getElementById('topbarLogoContainer');

      if (nameEl) nameEl.textContent = currentSchoolName;

      // Clean up any legacy or duplicate .topbar-logo elements
      topbar.querySelectorAll('.topbar-logo').forEach(el => el.remove());

      if (!logoContainer && nameEl && nameEl.parentElement) {
        const lDiv = document.createElement('div');
        lDiv.id = 'topbarLogoContainer';
        lDiv.style.cssText = 'display:flex; align-items:center; flex-shrink:0; margin-right:8px;';
        nameEl.parentElement.prepend(lDiv);
        logoContainer = lDiv;
      }

      if (logoContainer) {
        if (isSuperAdmin && !isViewing) {
          logoContainer.innerHTML = `<span style="font-size:1.4rem; flex-shrink:0;" title="Master System Portal">🌐</span>`;
        } else if (s.school_logo) {
          logoContainer.innerHTML = `<img src="${s.school_logo}" alt="${currentSchoolAbbr || 'School Logo'}" class="topbar-logo-img" style="height:34px; width:34px; object-fit:cover; border-radius:8px; flex-shrink:0; box-shadow:0 2px 6px rgba(0,0,0,0.15);" onerror="this.outerHTML = window.createDefaultCrestSvg('${currentSchoolAbbr}', 34);" />`;
        } else {
          logoContainer.innerHTML = window.createDefaultCrestSvg(currentSchoolAbbr, 34);
        }
      }
    }

    const sidebarNameEl = document.getElementById('sidebarSchoolName');
    if (sidebarNameEl) {
      sidebarNameEl.textContent = currentSchoolAbbr;
      sidebarNameEl.title = currentSchoolName;
    }

    const sidebarHeader = document.querySelector('.sidebar-header');
    if (sidebarHeader) {
      const existingSidebarLogo = sidebarHeader.querySelector('.sidebar-logo-img, .school-crest-svg, .sidebar-header > span:first-child');
      if (isSuperAdmin && !isViewing) {
        if (existingSidebarLogo && existingSidebarLogo.tagName !== 'SPAN') {
          const globalIcon = document.createElement('span');
          globalIcon.style.cssText = 'font-size:1.3rem; flex-shrink:0;';
          globalIcon.textContent = '🌐';
          existingSidebarLogo.replaceWith(globalIcon);
        }
      } else if (s.school_logo) {
        const newImg = document.createElement('img');
        newImg.src = s.school_logo;
        newImg.className = 'sidebar-logo-img';
        newImg.style.cssText = 'height:30px; width:30px; object-fit:cover; border-radius:8px; flex-shrink:0;';
        newImg.onerror = function() {
          this.outerHTML = window.createDefaultCrestSvg(currentSchoolAbbr, 30);
        };
        if (existingSidebarLogo) existingSidebarLogo.replaceWith(newImg);
      }
    }

    if (s.school_logo && (!isSuperAdmin || isViewing)) {
      localStorage.setItem('school_logo', s.school_logo);
    } else if (isSuperAdmin && !isViewing) {
      localStorage.removeItem('school_logo');
    }

    // ── Page <title> ──────────────────────────────────────────────────
    if (s.school_name) {
      const currentTitle = document.title;
      // Append school name if not already in title
      if (!currentTitle.includes(s.school_name)) {
        const suffix = currentTitle.replace(/\s*[–—-]\s*School Management System\s*/i, '').trim();
        document.title = suffix
          ? `${suffix} – ${s.school_name}`
          : s.school_name;
      }
    }

    // ── Global Server Theme ───────────────────────────────────────────
    if (s.system_theme) {
      localStorage.setItem('system_theme', s.system_theme);
      if (window.applyTheme) window.applyTheme(s.system_theme);
    }

    // ── Active Period Badge in Topbar ─────────────────────────────────
    if (s.active_year_label || s.active_term_name) {
      const topbar = document.querySelector('.topbar');
      if (topbar && !topbar.querySelector('.topbar-period-badge')) {
        const periodBadge = document.createElement('span');
        periodBadge.className = 'topbar-period-badge';
        periodBadge.style.cssText = 'font-size:0.75rem;font-weight:700;padding:4px 10px;border-radius:12px;background:var(--primary-light);color:var(--primary);border:1px solid var(--border-color);margin-left:10px;white-space:nowrap;display:inline-flex;align-items:center;';
        
        const mode = s.school_mode || localStorage.getItem('school_mode') || 'COMBINED';
        const yearLabel = s.active_year_label || '';
        const rawPeriod = s.active_term_name || '';

        let displayText = '';
        if (mode === 'BASIC_ONLY') {
          const termName = rawPeriod ? rawPeriod.replace(/Semester/i, 'Term') : 'Term 1';
          displayText = `📅 ${yearLabel} ${termName ? '· ' + termName : ''}`.trim();
        } else if (mode === 'SHS_ONLY') {
          const semName = rawPeriod ? rawPeriod.replace(/Term/i, 'Semester') : 'Semester 1';
          displayText = `📅 ${yearLabel} ${semName ? '· ' + semName : ''}`.trim();
        } else {
          const termName = rawPeriod.replace(/Semester/i, 'Term');
          const semName = rawPeriod.replace(/Term/i, 'Semester');
          displayText = `📅 ${yearLabel} · ${termName} | ${semName}`.trim();
        }

        periodBadge.textContent = displayText;
        const firstDiv = topbar.firstElementChild;
        if (firstDiv) {
          firstDiv.appendChild(periodBadge);
        }
      }
    }

    // Color extraction for dynamic theme branding
    if (s.school_logo && (!isSuperAdmin || isViewing)) {
      if (window.extractLogoColors) {
        window.extractLogoColors(s.school_logo, function (colors) {
          const activeTheme = localStorage.getItem('system_theme') || 'midnight';
          if (activeTheme === 'auto' && window.applyTheme) {
            window.applyTheme('auto', colors);
          }
        });
      }
    }

    // ── Topbar Theme & Layout Switcher ────────────────────────────────
    if (window.mountThemeSelector) {
      window.mountThemeSelector();
    }

    // ── School Mode Visibility ─────────────────────────────────────────
    if (s.school_mode) {
      localStorage.setItem('school_mode', s.school_mode);
    }
    if (s.boarding_status) {
      localStorage.setItem('boarding_status', s.boarding_status);
    }
    if (s.class_score_weight !== undefined) {
      localStorage.setItem('class_score_weight', s.class_score_weight);
    }
    if (s.exam_score_weight !== undefined) {
      localStorage.setItem('exam_score_weight', s.exam_score_weight);
    }
    if (window.applySchoolModeVisibility) {
      window.applySchoolModeVisibility(s.school_mode, s.boarding_status);
    }

  } catch (_) {
    // Non-critical — fail silently
  }
})();

window.applySchoolModeVisibility = function(mode, bStatus) {
  const F = (window.SchoolFeatures && window.SchoolFeatures.version)
    ? window.SchoolFeatures
    : (window.FeatureGate ? window.FeatureGate.getFeatures(mode, bStatus) : null);

  if (window.FeatureGate && window.FeatureGate.applyToDOM && F) {
    window.FeatureGate.applyToDOM(F);
  }

  const currentMode = F ? F.schoolMode : (mode || localStorage.getItem('school_mode') || 'COMBINED').toUpperCase();
  const isBoarding = F ? F.isBoarding : ((bStatus || localStorage.getItem('boarding_status') || 'BOARDING_AND_DAY').toUpperCase() === 'BOARDING_AND_DAY');

  // Hide or show SHS specific links (Programs, Departments, CSSPS Enrollment, Transcripts)
  const shsLinks = document.querySelectorAll('a[href*="programs.html"], a[href*="departments.html"], a[href*="enrollment.html"], a[href*="report-card.html?mode=transcript"], a[href*="clearance.html"]');
  shsLinks.forEach(link => {
    const shouldShow = (currentMode !== 'BASIC_ONLY');
    link.style.display = shouldShow ? '' : 'none';
    if (link.parentElement && (link.parentElement.tagName === 'LI' || link.parentElement.classList.contains('nav-item'))) {
      link.parentElement.style.display = shouldShow ? '' : 'none';
    }
  });

  // Hide or show Houses/Dormitories link based on Boarding status
  const houseLinks = document.querySelectorAll('a[href*="houses.html"]');
  houseLinks.forEach(link => {
    link.style.display = isBoarding ? '' : 'none';
    if (link.parentElement && (link.parentElement.tagName === 'LI' || link.parentElement.classList.contains('nav-item'))) {
      link.parentElement.style.display = isBoarding ? '' : 'none';
    }
  });

  // Hide or show Basic specific links (Cumulative Record Folder)
  const basicLinks = document.querySelectorAll('a[href*="cumulative-record.html"]');
  basicLinks.forEach(link => {
    const shouldShow = (currentMode !== 'SHS_ONLY');
    link.style.display = shouldShow ? '' : 'none';
    if (link.parentElement && (link.parentElement.tagName === 'LI' || link.parentElement.classList.contains('nav-item'))) {
      link.parentElement.style.display = shouldShow ? '' : 'none';
    }
  });

  // Exeat Management link visibility based on boarding status
  const exeatLinks = document.querySelectorAll('a[href*="exeat.html"]');
  exeatLinks.forEach(link => {
    link.style.display = isBoarding ? '' : 'none';
    if (link.parentElement && (link.parentElement.tagName === 'LI' || link.parentElement.classList.contains('nav-item'))) {
      link.parentElement.style.display = isBoarding ? '' : 'none';
    }
  });

  const shsElements = document.querySelectorAll('.shs-only-feature');
  shsElements.forEach(el => {
    el.style.display = (currentMode === 'BASIC_ONLY') ? 'none' : '';
  });
  
  const basicElements = document.querySelectorAll('.basic-only-feature');
  basicElements.forEach(el => {
    el.style.display = (currentMode === 'SHS_ONLY') ? 'none' : '';
  });

  const boardingElements = document.querySelectorAll('.boarding-only-feature');
  boardingElements.forEach(el => {
    el.style.display = isBoarding ? '' : 'none';
  });
};


window.handleThemeSelectChange = async function(val) {
  if (window.applyTheme) window.applyTheme(val);
  localStorage.setItem('system_theme', val);
  const token = localStorage.getItem('accessToken');
  if (token) {
    try {
      await fetch(`${API_BASE}/settings/`, {
        method: 'PUT',
        headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ system_theme: val })
      });
    } catch (_) {}
  }
};

document.addEventListener('DOMContentLoaded', () => {
  if (window.applySchoolModeVisibility) window.applySchoolModeVisibility();
});

