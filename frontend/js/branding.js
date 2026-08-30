/**
 * branding.js — Applies school name, logo, and page title from /api/settings/
 * Injected on every page that has a .topbar element.
 * Works without authentication (settings endpoint is public).
 */
window.applyBranding = async function(overrideSettings) {
  try {
    let s = overrideSettings;
    if (!s) {
      const API_BASE = window.API_BASE || (window.location.origin.includes('http') ? (window.location.origin + '/api') : 'http://127.0.0.1:8000/api');
      const headers = window.getAuthHeaders ? window.getAuthHeaders() : { 'Authorization': `Bearer ${localStorage.getItem('accessToken')}` };
      const res = await fetch(`${API_BASE}/settings/`, { headers });
      if (res.ok) {
        s = await res.json();
      }
    }
    s = s || {};

    const isViewing = (sessionStorage.getItem('is_super_admin_viewing') || localStorage.getItem('is_super_admin_viewing')) === 'true';
    const isSuperAdmin = ((sessionStorage.getItem('userRole') || localStorage.getItem('userRole')) === 'super_admin' || localStorage.getItem('is_super_admin') === 'true') && (sessionStorage.getItem('userRole') || localStorage.getItem('userRole')) !== 'admin' && !isViewing;

    let currentSchoolName = '';
    let currentSchoolAbbr = '';

    if (isSuperAdmin && !isViewing) {
      currentSchoolName = 'Master System Portal';
      currentSchoolAbbr = 'SUPER ADMIN';
      sessionStorage.setItem('school_name', currentSchoolName);
      sessionStorage.setItem('school_abbreviation', currentSchoolAbbr);
      localStorage.setItem('school_name', currentSchoolName);
      localStorage.setItem('school_abbreviation', currentSchoolAbbr);
    } else {
      currentSchoolName = sessionStorage.getItem('school_name') || s.school_name || localStorage.getItem('school_name') || 'School Management';
      currentSchoolAbbr = sessionStorage.getItem('school_abbreviation') || s.school_code || s.school_abbreviation || localStorage.getItem('school_abbreviation') || currentSchoolName;

      if (currentSchoolName && currentSchoolName !== 'Master System Portal') {
        sessionStorage.setItem('school_name', currentSchoolName);
        localStorage.setItem('school_name', currentSchoolName);
      }
      if (currentSchoolAbbr && currentSchoolAbbr !== 'SUPER ADMIN') {
        sessionStorage.setItem('school_abbreviation', currentSchoolAbbr);
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
        lDiv.className = 'topbar-brand-logo';
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

      // Clean up duplicate legacy topbar pill and ensure single master banner
      const existingViewingBanner = document.getElementById('topbarViewingModeBanner');
      if (existingViewingBanner) existingViewingBanner.remove();

      if (window.updateSuperAdminBanner) {
        window.updateSuperAdminBanner();
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
      sessionStorage.setItem('school_logo', s.school_logo);
      localStorage.setItem('school_logo', s.school_logo);
    } else if (isSuperAdmin && !isViewing) {
      sessionStorage.removeItem('school_logo');
      localStorage.removeItem('school_logo');
    }

    // ── Page <title> Disambiguation ──────────────────────────────────
    if (window.SMSStateBus && window.SMSStateBus.updateTabTitle) {
      window.SMSStateBus.updateTabTitle();
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
};

// Initial invocation on script load
window.applyBranding();


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

// ================================================================
// Enterprise In-App Modal, Dialog & Toast Engine
// Replaces browser address-bar popups with theme-adaptive modals
// ================================================================

(function initEnterpriseDialogs() {
  function getToastContainer() {
    let c = document.querySelector('.enterprise-toast-container');
    if (!c) {
      c = document.createElement('div');
      c.className = 'enterprise-toast-container';
      document.body.appendChild(c);
    }
    return c;
  }

  function escapeHtml(text) {
    if (!text) return '';
    return String(text).replace(/[&<>"']/g, function(m) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[m];
    });
  }

  window.showToast = function(message, type = 'info', duration = 3500) {
    const container = getToastContainer();
    const item = document.createElement('div');
    item.className = `enterprise-toast-item type-${type}`;

    let icon = 'ℹ️';
    if (type === 'success') icon = '✅';
    else if (type === 'warning') icon = '⚠️';
    else if (type === 'danger' || type === 'error') icon = '🚫';

    item.innerHTML = `
      <div style="display:flex; align-items:center; gap:8px;">
        <span style="font-size:1.1rem;">${icon}</span>
        <span>${escapeHtml(message)}</span>
      </div>
      <button type="button" style="background:none; border:none; color:inherit; font-size:1.1rem; cursor:pointer; opacity:0.6; padding:0 4px;" onclick="this.parentElement.remove()">✕</button>
    `;

    container.appendChild(item);
    setTimeout(() => {
      item.style.opacity = '0';
      item.style.transform = 'translateY(10px) scale(0.95)';
      setTimeout(() => item.remove(), 250);
    }, duration);
  };

  window.showAlertDialog = function(titleOrMessage, messageOrType, type = 'info', options = {}) {
    return new Promise((resolve) => {
      let title = 'System Notification';
      let message = '';
      let dialogType = type;

      if (messageOrType && typeof messageOrType === 'string' && !['info', 'success', 'warning', 'danger', 'error'].includes(messageOrType)) {
        title = titleOrMessage;
        message = messageOrType;
      } else if (['info', 'success', 'warning', 'danger', 'error'].includes(messageOrType)) {
        message = titleOrMessage;
        dialogType = messageOrType;
      } else {
        message = titleOrMessage;
      }

      const schoolName = localStorage.getItem('school_name') || 'School Management System';
      let icon = 'ℹ️';
      let badgeClass = '';
      if (dialogType === 'success' || message.includes('✅') || message.includes('success') || message.includes('Success')) {
        icon = '✅';
        badgeClass = 'type-success';
      } else if (dialogType === 'warning' || message.includes('⚠️') || message.includes('Warning') || message.includes('Curfew')) {
        icon = '⚠️';
        badgeClass = 'type-warning';
      } else if (dialogType === 'danger' || dialogType === 'error' || message.includes('🔴') || message.includes('Failed') || message.includes('Denied') || message.includes('Error')) {
        icon = '🚫';
        badgeClass = 'type-danger';
      }

      document.querySelectorAll('.enterprise-modal-backdrop').forEach(el => el.remove());

      const backdrop = document.createElement('div');
      backdrop.className = 'enterprise-modal-backdrop';

      backdrop.innerHTML = `
        <div class="enterprise-modal-card" role="dialog" aria-modal="true">
          <div class="enterprise-modal-header">
            <div class="enterprise-modal-icon-badge ${badgeClass}">
              ${icon}
            </div>
            <div>
              <h3 class="enterprise-modal-title">${escapeHtml(title)}</h3>
              <div style="font-size:0.75rem; opacity:0.65;">${escapeHtml(schoolName)}</div>
            </div>
          </div>
          <div class="enterprise-modal-body">${escapeHtml(message)}</div>
          <div class="enterprise-modal-actions">
            <button class="enterprise-modal-btn btn-primary" id="btnEntModalConfirm">
              <span>OK</span>
            </button>
          </div>
        </div>
      `;

      function cleanup() {
        window.removeEventListener('keydown', handleKey);
        backdrop.style.opacity = '0';
        setTimeout(() => backdrop.remove(), 180);
        resolve();
      }

      function handleKey(e) {
        if (e.key === 'Enter' || e.key === 'Escape') {
          e.preventDefault();
          cleanup();
        }
      }

      backdrop.querySelector('#btnEntModalConfirm').addEventListener('click', cleanup);
      backdrop.addEventListener('click', (e) => {
        if (e.target === backdrop) cleanup();
      });

      document.body.appendChild(backdrop);
      window.addEventListener('keydown', handleKey);
      setTimeout(() => {
        const btn = backdrop.querySelector('#btnEntModalConfirm');
        if (btn) btn.focus();
      }, 50);
    });
  };

  window.showConfirmDialog = function(titleOrMessage, message, confirmText = 'Confirm', cancelText = 'Cancel', type = 'confirm') {
    return new Promise((resolve) => {
      let title = 'Confirmation Required';
      let bodyText = message || titleOrMessage;
      if (message) {
        title = titleOrMessage;
      }

      const schoolName = localStorage.getItem('school_name') || 'School Management System';
      let icon = '❓';
      let badgeClass = '';
      if (type === 'warning' || bodyText.toLowerCase().includes('delete') || bodyText.toLowerCase().includes('reject')) {
        icon = '⚠️';
        badgeClass = 'type-warning';
      }

      document.querySelectorAll('.enterprise-modal-backdrop').forEach(el => el.remove());

      const backdrop = document.createElement('div');
      backdrop.className = 'enterprise-modal-backdrop';

      backdrop.innerHTML = `
        <div class="enterprise-modal-card" role="dialog" aria-modal="true">
          <div class="enterprise-modal-header">
            <div class="enterprise-modal-icon-badge ${badgeClass}">
              ${icon}
            </div>
            <div>
              <h3 class="enterprise-modal-title">${escapeHtml(title)}</h3>
              <div style="font-size:0.75rem; opacity:0.65;">${escapeHtml(schoolName)}</div>
            </div>
          </div>
          <div class="enterprise-modal-body">${escapeHtml(bodyText)}</div>
          <div class="enterprise-modal-actions">
            <button class="enterprise-modal-btn btn-secondary" id="btnEntModalCancel">
              <span>${escapeHtml(cancelText)}</span>
            </button>
            <button class="enterprise-modal-btn btn-primary" id="btnEntModalConfirm">
              <span>${escapeHtml(confirmText)}</span>
            </button>
          </div>
        </div>
      `;

      function closeWith(val) {
        window.removeEventListener('keydown', handleKey);
        backdrop.style.opacity = '0';
        setTimeout(() => backdrop.remove(), 180);
        resolve(val);
      }

      function handleKey(e) {
        if (e.key === 'Enter') {
          e.preventDefault();
          closeWith(true);
        } else if (e.key === 'Escape') {
          e.preventDefault();
          closeWith(false);
        }
      }

      backdrop.querySelector('#btnEntModalConfirm').addEventListener('click', () => closeWith(true));
      backdrop.querySelector('#btnEntModalCancel').addEventListener('click', () => closeWith(false));
      backdrop.addEventListener('click', (e) => {
        if (e.target === backdrop) closeWith(false);
      });

      document.body.appendChild(backdrop);
      window.addEventListener('keydown', handleKey);
      setTimeout(() => {
        const btn = backdrop.querySelector('#btnEntModalConfirm');
        if (btn) btn.focus();
      }, 50);
    });
  };

  window.showPromptDialog = function(title, message, defaultValue = '', placeholder = '') {
    return new Promise((resolve) => {
      const schoolName = localStorage.getItem('school_name') || 'School Management System';
      document.querySelectorAll('.enterprise-modal-backdrop').forEach(el => el.remove());

      const backdrop = document.createElement('div');
      backdrop.className = 'enterprise-modal-backdrop';

      backdrop.innerHTML = `
        <div class="enterprise-modal-card" role="dialog" aria-modal="true">
          <div class="enterprise-modal-header">
            <div class="enterprise-modal-icon-badge">
              ✏️
            </div>
            <div>
              <h3 class="enterprise-modal-title">${escapeHtml(title)}</h3>
              <div style="font-size:0.75rem; opacity:0.65;">${escapeHtml(schoolName)}</div>
            </div>
          </div>
          <div class="enterprise-modal-body">
            <div>${escapeHtml(message)}</div>
            <input type="text" class="enterprise-modal-input" id="entPromptInput" value="${escapeHtml(defaultValue)}" placeholder="${escapeHtml(placeholder)}" />
          </div>
          <div class="enterprise-modal-actions">
            <button class="enterprise-modal-btn btn-secondary" id="btnEntPromptCancel">Cancel</button>
            <button class="enterprise-modal-btn btn-primary" id="btnEntPromptSubmit">Submit</button>
          </div>
        </div>
      `;

      function closeWith(val) {
        window.removeEventListener('keydown', handleKey);
        backdrop.style.opacity = '0';
        setTimeout(() => backdrop.remove(), 180);
        resolve(val);
      }

      const input = backdrop.querySelector('#entPromptInput');

      function handleKey(e) {
        if (e.key === 'Enter') {
          e.preventDefault();
          closeWith(input.value);
        } else if (e.key === 'Escape') {
          e.preventDefault();
          closeWith(null);
        }
      }

      backdrop.querySelector('#btnEntPromptSubmit').addEventListener('click', () => closeWith(input.value));
      backdrop.querySelector('#btnEntPromptCancel').addEventListener('click', () => closeWith(null));
      backdrop.addEventListener('click', (e) => {
        if (e.target === backdrop) closeWith(null);
      });

      document.body.appendChild(backdrop);
      window.addEventListener('keydown', handleKey);
      setTimeout(() => {
        input.focus();
        input.select();
      }, 60);
    });
  };

  // ── Global Interceptors for legacy window.alert, confirm, prompt ──
  window.alert = function(msg) {
    return window.showAlertDialog(msg);
  };
  window.confirm = function(msg) {
    return window.showConfirmDialog('Confirmation', msg);
  };
  window.prompt = function(msg, def) {
    return window.showPromptDialog('Input Required', msg, def || '');
  };
})();


