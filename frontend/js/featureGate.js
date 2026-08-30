/**
 * featureGate.js — EduManage360 Central Feature Flag Service
 * =============================================================
 * Single Source of Truth for all school-configuration-driven UI visibility.
 * Reads school_mode + boarding_status from localStorage (zero network calls).
 * Must be loaded BEFORE theme.js, branding.js, and all module scripts.
 *
 * School Profiles supported:
 *   1. SHS_ONLY   + DAY_ONLY          — Pure SHS Day School
 *   2. SHS_ONLY   + BOARDING_AND_DAY  — SHS with Boarding
 *   3. BASIC_ONLY + DAY_ONLY          — Basic/JHS Day School
 *   4. BASIC_ONLY + BOARDING_AND_DAY  — Basic Boarding Preparatory School
 *   5. COMBINED   + DAY_ONLY          — Combined Basic+SHS Day School
 *   6. COMBINED   + BOARDING_AND_DAY  — Full Combined School with Boarding
 *
 * @version 1.0.0
 */

(function () {
  'use strict';

  // ── Version ──────────────────────────────────────────────────────────────────
  // Bump this whenever feature flag logic changes to force client refresh.
  const FEATURE_GATE_VERSION = '1.0.0';

  // ── Read tenant configuration from sessionStorage (tab-isolated) & localStorage ──
  // Graceful defaults: if storage is not yet populated (pre-login),
  // default to COMBINED + BOARDING_AND_DAY (show everything) — never crash.
  function getConfig() {
    try {
      const mode    = (sessionStorage.getItem('school_mode')    || localStorage.getItem('school_mode')    || 'COMBINED').toUpperCase().trim();
      const boarding = (sessionStorage.getItem('boarding_status') || localStorage.getItem('boarding_status') || 'BOARDING_AND_DAY').toUpperCase().trim();
      // Validate values — if unexpected string, fall back safely
      const validModes    = ['SHS_ONLY', 'BASIC_ONLY', 'COMBINED'];
      const validBoarding = ['DAY_ONLY', 'BOARDING_AND_DAY'];
      return {
        mode:     validModes.includes(mode)     ? mode    : 'COMBINED',
        boarding: validBoarding.includes(boarding) ? boarding : 'BOARDING_AND_DAY',
      };
    } catch (_) {
      return { mode: 'COMBINED', boarding: 'BOARDING_AND_DAY' };
    }
  }

  // ── Core Feature Computation ──────────────────────────────────────────────
  /**
   * Computes the full feature-flag object for the current tenant's configuration.
   * @param {string} [mode]    - Override school_mode (optional, uses localStorage)
   * @param {string} [boarding] - Override boarding_status (optional, uses localStorage)
   * @returns {Object} Feature flags
   */
  function computeFeatures(mode, boarding) {
    const cfg = (mode && boarding)
      ? { mode: mode.toUpperCase(), boarding: boarding.toUpperCase() }
      : getConfig();

    const isBasicOnly = cfg.mode === 'BASIC_ONLY';
    const isShsOnly   = cfg.mode === 'SHS_ONLY';
    const isCombined  = cfg.mode === 'COMBINED';
    const isBoarding  = cfg.boarding === 'BOARDING_AND_DAY';
    const isDay       = cfg.boarding === 'DAY_ONLY';

    return {
      // ── Raw config values ─────────────────────────────────────────────────
      schoolMode:     cfg.mode,
      boardingStatus: cfg.boarding,
      version:        FEATURE_GATE_VERSION,

      // ── Derived booleans for convenience ─────────────────────────────────
      isBasicOnly,
      isShsOnly,
      isCombined,
      isBoarding,
      isDay,

      // ── Navigation & Module Visibility ────────────────────────────────────
      /** Exeat Management — boarding schools only */
      showExeat:             isBoarding,
      /** Houses & Dormitories — boarding schools only */
      showHousesDorms:       isBoarding,
      /** Programs (Science, Business, etc.) — SHS and Combined only */
      showPrograms:          !isBasicOnly,
      /** Departments (HOD structure) — SHS and Combined only */
      showDepartments:       !isBasicOnly,
      /** School Code of Conduct & Student Honor Pledge Hub — SHS/Combined only */
      showConductHub:        !isBasicOnly,
      /** Official SHS Transcripts — SHS and Combined only */
      showTranscripts:       !isBasicOnly,
      /** Final Year Clearance — SHS and Combined only */
      showFinalYearClearance: !isBasicOnly,
      /** CSSPS Enrollment — SHS and Combined only */
      showCsspsEnrollment:   !isBasicOnly,
      /** Cumulative Record Folder — Basic and Combined only */
      showCumulativeRecord:  !isShsOnly,

      // ── Student Form Fields ───────────────────────────────────────────────
      /** CSSPS placement form tab/section — SHS and Combined only */
      showCsspsForm:         !isBasicOnly,
      /** Basic school registration form tab/section — Basic and Combined only */
      showBasicForm:         !isShsOnly,
      /** Section toggle (CSSPS SHS / Basic School) — COMBINED only */
      showSectionToggle:     isCombined,
      /** Residential Status field — boarding schools only (hidden for day-only) */
      showResidentialStatus: isBoarding,
      /** Boarding House assignment field */
      showBoardingHouseField: isBoarding,
      /** Dormitory assignment field */
      showDormitoryField:    isBoarding,
      /** Programs dropdown in student form */
      showProgramField:      !isBasicOnly,
      /** BECE Index Number — SHS and Combined only (CSSPS identifier) */
      showBeceIndexNumber:   !isBasicOnly,
      /** CSSPS Placement, Boarding status KPI chips in student list */
      showStudentCsspsChips: !isBasicOnly,
      showStudentBoardingChip: isBoarding,
      /** Default residential_status for new students */
      defaultResidentialStatus: isDay ? 'D' : null,  // null = let admin choose

      // ── Dashboard KPI Cards ───────────────────────────────────────────────
      showBoardingKpi:  isBoarding,
      showCsspsKpi:     !isBasicOnly,

      // ── Houses Module ─────────────────────────────────────────────────────
      /**
       * Boarding hierarchy tier for boarding schools:
       * - SHS_THREE_TIER: Senior In-Charge → House Master → Assistant House Master
       * - BASIC_TWO_TIER: House Master → Headteacher (no Senior In-Charge tier)
       */
      boardingHierarchy: isBasicOnly ? 'BASIC_TWO_TIER' : 'SHS_THREE_TIER',
      /** Whether to show house-type selector (BOARDING vs ACADEMIC_SPORTS) */
      showHouseTypeSelector: !isBasicOnly && isBoarding,

      // ── Staff Roles ───────────────────────────────────────────────────────
      /** Boarding-specific staff roles visible in user management */
      showBoardingRoles: isBoarding,
      /** SHS-specific staff roles (HOD, etc.) */
      showShsStaffRoles: !isBasicOnly,

      // ── Fee Management ────────────────────────────────────────────────────
      /** Boarding fee categories (Boarding Levy, Feeding Fee, etc.) */
      showBoardingFeeCategories: isBoarding,

      // ── Attendance ────────────────────────────────────────────────────────
      /** Boarding roll-call tab (evening/morning checks) */
      showBoardingRollCall: isBoarding,

      // ── Settings Page ─────────────────────────────────────────────────────
      /** Whether boarding-related settings sections are shown */
      showBoardingSettingsSection: isBoarding,
    };
  }

  // ── DOM Application Helper ─────────────────────────────────────────────────
  /**
   * Applies feature flags to DOM elements using data attributes.
   * Elements with data-feature="<flagName>" are shown/hidden based on
   * whether SchoolFeatures[flagName] is true/false.
   *
   * Usage in HTML:
   *   <div data-feature="showExeat">...</div>      — shown only for boarding
   *   <div data-feature-hide="showExeat">...</div>  — hidden only for boarding
   */
  function applyToDOM(features) {
    try {
      // Show elements when feature is true
      document.querySelectorAll('[data-feature]').forEach(el => {
        const flag = el.getAttribute('data-feature');
        if (flag in features) {
          el.style.display = features[flag] ? '' : 'none';
        }
      });

      // Hide elements when feature is true (inverse gate)
      document.querySelectorAll('[data-feature-hide]').forEach(el => {
        const flag = el.getAttribute('data-feature-hide');
        if (flag in features) {
          el.style.display = features[flag] ? 'none' : '';
        }
      });
    } catch (_) {
      // Fail silently — DOM may not be ready yet
    }
  }

  // ── Refresh Hook ──────────────────────────────────────────────────────────
  /**
   * Call this after updating storage or fetching tenant settings.
   * Recomputes features and re-applies to DOM.
   */
  function refreshFeatures(overrideMode, overrideBoarding) {
    if (overrideMode) {
      sessionStorage.setItem('school_mode', overrideMode);
      localStorage.setItem('school_mode', overrideMode);
    }
    if (overrideBoarding) {
      sessionStorage.setItem('boarding_status', overrideBoarding);
      localStorage.setItem('boarding_status', overrideBoarding);
    }
    window.SchoolFeatures = computeFeatures(overrideMode, overrideBoarding);
    applyToDOM(window.SchoolFeatures);
    if (window.applySchoolModeVisibility) {
      window.applySchoolModeVisibility(window.SchoolFeatures.schoolMode, window.SchoolFeatures.boardingStatus);
    }
    if (window.renderDashboardNavCards) {
      window.renderDashboardNavCards();
    }
    if (window.mountSidebarNav) {
      window.mountSidebarNav();
    }
    // Dispatch event so modules can react without polling
    window.dispatchEvent(new CustomEvent('schoolFeaturesRefreshed', {
      detail: window.SchoolFeatures,
    }));
  }

  // ── Profile Description Helper ────────────────────────────────────────────
  /**
   * Returns a human-readable profile name for the current configuration.
   * Used for Super Admin preview tooltips and school admin config display.
   */
  function getProfileName(mode, boarding) {
    const m = (mode    || 'COMBINED').toUpperCase();
    const b = (boarding || 'BOARDING_AND_DAY').toUpperCase();
    const modeLabel    = { SHS_ONLY: 'SHS Only', BASIC_ONLY: 'Basic Only', COMBINED: 'Combined' }[m] || m;
    const boardingLabel = b === 'DAY_ONLY' ? 'Day Only' : 'Day & Boarding';
    return `${modeLabel} — ${boardingLabel}`;
  }

  /**
   * Returns an array of enabled/disabled feature descriptions for a given profile.
   * Used in the Super Admin "Profile Preview" panel.
   */
  function getProfileSummary(mode, boarding) {
    const f = computeFeatures(mode, boarding);
    return [
      { label: 'CSSPS Enrollment',            enabled: f.showCsspsForm },
      { label: 'Programs & Departments',       enabled: f.showPrograms },
      { label: 'Code of Conduct Hub',          enabled: f.showConductHub },
      { label: 'Final Year Clearance',         enabled: f.showFinalYearClearance },
      { label: 'Cumulative Record Folder',     enabled: f.showCumulativeRecord },
      { label: 'Houses & Dormitories',         enabled: f.showHousesDorms },
      { label: 'Exeat Management',             enabled: f.showExeat },
      { label: 'Boarding Staff Roles',         enabled: f.showBoardingRoles },
      { label: 'Boarding Fee Categories',      enabled: f.showBoardingFeeCategories },
      { label: 'Boarding Roll-Call Attendance',enabled: f.showBoardingRollCall },
    ];
  }

  // ── Initialise ────────────────────────────────────────────────────────────
  // Compute and expose immediately (synchronous — no network needed)
  const initialFeatures = computeFeatures();
  window.SchoolFeatures = initialFeatures;

  // Expose public API on window
  window.FeatureGate = {
    version:           FEATURE_GATE_VERSION,
    getFeatures:       computeFeatures,
    refresh:           refreshFeatures,
    applyToDOM:        applyToDOM,
    getProfileName:    getProfileName,
    getProfileSummary: getProfileSummary,
  };

  // Apply to DOM when ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => applyToDOM(window.SchoolFeatures));
  } else {
    applyToDOM(window.SchoolFeatures);
  }

  // Listen for storage changes across tabs (multi-tab tenancy support)
  window.addEventListener('storage', function (e) {
    if (e.key === 'school_mode' || e.key === 'boarding_status') {
      refreshFeatures();
    }
  });

})();
