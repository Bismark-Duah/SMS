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

    const topbar = document.querySelector('.topbar');
    if (topbar) {
      let nameEl = document.getElementById('schoolNameHeader');
      let logoContainer = document.getElementById('topbarLogoContainer');

      if (nameEl) nameEl.textContent = currentSchoolName;

      if (!logoContainer && nameEl && nameEl.parentElement) {
        const lDiv = document.createElement('div');
        lDiv.id = 'topbarLogoContainer';
        lDiv.style.cssText = 'display:flex; align-items:center; flex-shrink:0;';
        nameEl.parentElement.prepend(lDiv);
        logoContainer = lDiv;
      }

      if (logoContainer) {
        if (s.school_logo && (!isSuperAdmin || isViewing)) {
          logoContainer.innerHTML = `<img src="${s.school_logo}" alt="School Logo" style="height:34px; width:34px; object-fit:cover; border-radius:8px; flex-shrink:0;" />`;
        } else if (!isSuperAdmin || isViewing) {
          logoContainer.innerHTML = `<span style="font-size:1.4rem; flex-shrink:0;">🏫</span>`;
        } else {
          logoContainer.innerHTML = `<span style="font-size:1.4rem; flex-shrink:0;">🌐</span>`;
        }
      }
    }

    const sidebarNameEl = document.getElementById('sidebarSchoolName');
    if (sidebarNameEl) {
      sidebarNameEl.textContent = currentSchoolAbbr;
      sidebarNameEl.title = currentSchoolName;
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

    if (s.school_logo && (!isSuperAdmin || isViewing)) {
      if (window.extractLogoColors) {
        window.extractLogoColors(s.school_logo, function (colors) {
          const activeTheme = localStorage.getItem('system_theme') || 'midnight';
          if (activeTheme === 'auto' && window.applyTheme) {
            window.applyTheme('auto', colors);
          }
        });
      }

      const topbar = document.querySelector('.topbar');
      if (topbar && !topbar.querySelector('.topbar-logo')) {
        const logoImg = document.createElement('img');
        logoImg.src = s.school_logo;
        logoImg.alt = s.school_name || 'School Logo';
        logoImg.className = 'topbar-logo';
        logoImg.style.cssText = 'height:36px;width:36px;object-fit:cover;border-radius:8px;margin-right:10px;flex-shrink:0;';
        const firstChild = topbar.firstElementChild;
        if (firstChild) {
          firstChild.style.display = 'flex';
          firstChild.style.alignItems = 'center';
          firstChild.prepend(logoImg);
        }
      }
    } else {
      const topbar = document.querySelector('.topbar');
      if (topbar) {
        const existingLogo = topbar.querySelector('.topbar-logo');
        if (existingLogo && isSuperAdmin && !isViewing) existingLogo.remove();
      }
      if (isSuperAdmin && !isViewing) {
        const sidebarLogoImg = document.querySelector('.sidebar-logo-img');
        if (sidebarLogoImg) {
          const globalIcon = document.createElement('span');
          globalIcon.style.cssText = 'font-size:1.3rem; flex-shrink:0;';
          globalIcon.textContent = '🌐';
          sidebarLogoImg.replaceWith(globalIcon);
        }
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
  const currentMode = (mode || localStorage.getItem('school_mode') || 'COMBINED').toUpperCase();
  const boardingStatus = (bStatus || localStorage.getItem('boarding_status') || 'BOARDING_AND_DAY').toUpperCase();
  
  // Hide or show SHS specific links (Programs, Houses/Dormitories, Departments, CSSPS Enrollment)
  const shsLinks = document.querySelectorAll('a[href*="programs.html"], a[href*="houses.html"], a[href*="departments.html"], a[href*="enrollment.html"]');
  shsLinks.forEach(link => {
    const isHouseLink = link.getAttribute('href').includes('houses.html');
    if (currentMode === 'BASIC_ONLY') {
      link.style.display = 'none';
      if (link.parentElement && (link.parentElement.tagName === 'LI' || link.parentElement.classList.contains('nav-item'))) {
        link.parentElement.style.display = 'none';
      }
    } else {
      if (isHouseLink && boardingStatus === 'DAY_ONLY') {
        link.style.display = 'none';
        if (link.parentElement && (link.parentElement.tagName === 'LI' || link.parentElement.classList.contains('nav-item'))) {
          link.parentElement.style.display = 'none';
        }
      } else {
        link.style.display = '';
        if (link.parentElement && (link.parentElement.tagName === 'LI' || link.parentElement.classList.contains('nav-item'))) {
          link.parentElement.style.display = '';
        }
      }
    }
  });

  // Hide or show Basic specific links (Cumulative Record Folder)
  const basicLinks = document.querySelectorAll('a[href*="cumulative-record.html"]');
  basicLinks.forEach(link => {
    if (currentMode === 'SHS_ONLY') {
      link.style.display = 'none';
      if (link.parentElement && (link.parentElement.tagName === 'LI' || link.parentElement.classList.contains('nav-item'))) {
        link.parentElement.style.display = 'none';
      }
    } else {
      link.style.display = '';
      if (link.parentElement && (link.parentElement.tagName === 'LI' || link.parentElement.classList.contains('nav-item'))) {
        link.parentElement.style.display = '';
      }
    }
  });

  // Exeat Management link visibility based on boarding status
  const exeatLinks = document.querySelectorAll('a[href*="exeat.html"]');
  exeatLinks.forEach(link => {
    if (boardingStatus === 'DAY_ONLY' || currentMode === 'BASIC_ONLY') {
      link.style.display = 'none';
      if (link.parentElement && (link.parentElement.tagName === 'LI' || link.parentElement.classList.contains('nav-item'))) {
        link.parentElement.style.display = 'none';
      }
    } else {
      link.style.display = '';
      if (link.parentElement && (link.parentElement.tagName === 'LI' || link.parentElement.classList.contains('nav-item'))) {
        link.parentElement.style.display = '';
      }
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
