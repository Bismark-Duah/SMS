const API_BASE = window.API_BASE || (window.location.origin.includes('http') ? (window.location.origin + '/api') : 'http://127.0.0.1:8000/api');

const token = localStorage.getItem('accessToken');
if (!token) {
  window.location.href = 'auth.html';
}

function getHeaders(headers = {}) {
  if (window.getAuthHeaders) return window.getAuthHeaders(headers);
  const h = { ...headers };
  const t = sessionStorage.getItem('accessToken') || localStorage.getItem('accessToken');
  if (t) h['Authorization'] = `Bearer ${t}`;
  const schId = sessionStorage.getItem('school_id') || localStorage.getItem('school_id');
  if (schId) h['X-School-Id'] = String(schId);
  return h;
}

let gradingRules = [];

function toggleGradingSection(val) {
    const section = document.getElementById('customGradingSection');
    if (section) {
        section.style.display = val === 'CUSTOM' ? 'block' : 'none';
    }
}

window.toggleBoardingHierarchyBox = function(val) {
    const label = document.getElementById('hierarchyModeLabel');
    if (label) {
        label.style.display = val === 'DAY_ONLY' ? 'none' : 'block';
    }
};

function renderGradingTiers() {
    const tbody = document.getElementById('gradingTiersBody');
    if (!tbody) return;

    // Sort rules descending by minimum score
    gradingRules.sort((a, b) => b.min_score - a.min_score);

    tbody.innerHTML = gradingRules.map((rule, index) => `
        <tr>
            <td><strong>${escapeHtml(rule.grade)}</strong></td>
            <td>${rule.min_score}%</td>
            <td>${escapeHtml(rule.remark)}</td>
            <td>${rule.point}</td>
            <td>
                <button type="button" class="btn danger" style="padding: 4px 8px; font-size: 0.8rem; margin: 0;" onclick="deleteTier(${index})">Remove</button>
            </td>
        </tr>
    `).join('');
}

function populateCustomTierDropdowns() {
    const gradeSel = document.getElementById('new_grade');
    const remarkSel = document.getElementById('new_remark');
    const pointsSel = document.getElementById('new_points');

    if (gradeSel) {
        const grades = ['A1', 'B2', 'B3', 'C4', 'C5', 'C6', 'D7', 'E8', 'F9', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'A', 'B', 'C', 'D', 'E', 'F'];
        gradeSel.innerHTML = '<option value="">Select Grade...</option>' + grades.map(g => `<option value="${g}">${g}</option>`).join('');
    }

    if (remarkSel) {
        const remarks = ['EXCELLENT', 'VERY GOOD', 'GOOD', 'CREDIT', 'PASS', 'WEAK PASS', 'FAIL', 'HIGHEST', 'VERY HIGH', 'HIGH', 'AVERAGE', 'FAIR', 'LOW', 'VERY LOW', 'LOWEST'];
        remarkSel.innerHTML = '<option value="">Select Remark...</option>' + remarks.map(r => `<option value="${r}">${r}</option>`).join('');
    }

    if (pointsSel) {
        const points = [1, 2, 3, 4, 5, 6, 7, 8, 9];
        pointsSel.innerHTML = points.map(p => `<option value="${p}">${p}</option>`).join('');
    }
}

window.updateGradingStandardDropdown = function(mode) {
    const stdSel = document.getElementById('grading_standard');
    if (!stdSel) return;

    const currentVal = stdSel.value;
    let html = '';

    if (mode === 'BASIC_ONLY') {
        html = `
            <option value="BECE">BECE System (1-9)</option>
            <option value="CUSTOM">Custom Grading System</option>
        `;
    } else if (mode === 'SHS_ONLY') {
        html = `
            <option value="WAEC">WASSCE / WAEC (A1-F9)</option>
            <option value="CUSTOM">Custom Grading System</option>
        `;
    } else {
        html = `
            <option value="BECE">BECE System (1-9)</option>
            <option value="WAEC">WASSCE / WAEC (A1-F9)</option>
            <option value="CUSTOM">Custom Grading System</option>
        `;
    }

    stdSel.innerHTML = html;
    if (['BECE', 'WAEC', 'CUSTOM'].includes(currentVal)) {
        if (mode === 'BASIC_ONLY' && currentVal === 'WAEC') {
            stdSel.value = 'BECE';
        } else if (mode === 'SHS_ONLY' && currentVal === 'BECE') {
            stdSel.value = 'WAEC';
        } else {
            stdSel.value = currentVal;
        }
    }
    toggleGradingSection(stdSel.value);
};

window.updateSettingsProfilePreview = function(mode, boarding) {
    const badgesContainer = document.getElementById('settingsProfileBadges');
    const titleEl = document.getElementById('settingsProfileTitle');
    if (!badgesContainer) return;

    const m = (mode || document.getElementById('school_mode')?.value || 'COMBINED').toUpperCase();
    const b = (boarding || document.getElementById('boarding_status')?.value || 'BOARDING_AND_DAY').toUpperCase();

    if (titleEl && window.FeatureGate) {
        titleEl.textContent = `🏫 ${window.FeatureGate.getProfileName(m, b)} — Active Features`;
    }

    const summary = window.FeatureGate ? window.FeatureGate.getProfileSummary(m, b) : [];
    badgesContainer.innerHTML = summary.map(f => `
        <span style="background:${f.enabled ? 'rgba(16,185,129,0.18)' : 'rgba(100,116,139,0.12)'}; color:${f.enabled ? '#34d399' : '#64748b'}; padding:3px 8px; border-radius:6px; font-weight:600; text-decoration:${f.enabled ? 'none' : 'line-through'};">
            ${f.enabled ? '✔' : '✕'} ${f.label}
        </span>
    `).join('');
};

window.onSettingsModeChange = function() {
    const mode = document.getElementById('school_mode')?.value || 'COMBINED';
    const boarding = document.getElementById('boarding_status')?.value || 'BOARDING_AND_DAY';
    
    // Auto-derive hierarchy mode
    const hierSelect = document.getElementById('boarding_hierarchy_mode');
    if (hierSelect) {
        hierSelect.value = (mode === 'BASIC_ONLY') ? 'BASIC_TWO_TIER' : 'SHS_THREE_TIER';
    }

    window.updateGradingStandardDropdown(mode);
    window.updateSettingsProfilePreview(mode, boarding);
};

function escapeHtml(str) {
    return str ? String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;") : '';
}

window.deleteTier = function(index) {
    gradingRules.splice(index, 1);
    renderGradingTiers();
};

async function loadSettings() {
    try {
        const res = await fetch(`${API_BASE}/settings/`, { headers: getHeaders() });
        const settings = await res.json();

        const setVal = (id, val) => { const el = document.getElementById(id); if (el && val) el.value = val; };

        setVal('school_name',          settings.school_name);
        setVal('school_abbreviation',  settings.school_abbreviation || 'JAK STEM');
        setVal('report_motto',         settings.report_motto);
        setVal('report_title',         settings.report_title);
        setVal('report_headmaster',    settings.report_headmaster);
        setVal('school_address',       settings.school_address);
        setVal('school_phone',         settings.school_phone);
        setVal('school_email',         settings.school_email);
        setVal('school_logo',          settings.school_logo);
        setVal('headmaster_signature', settings.headmaster_signature);
        setVal('code_of_conduct_text', settings.code_of_conduct_text);
        setVal('student_pledge_text', settings.student_pledge_text);
        setVal('code_of_conduct_pdf_url', settings.code_of_conduct_pdf_url);
        setVal('paystack_public_key', settings.paystack_public_key);
        setVal('paystack_secret_key', settings.paystack_secret_key);
        setVal('paystack_enabled', settings.paystack_enabled || 'false');

        if (settings.report_publishing_mode) {
            const pubRadio = document.querySelector(`input[name="publishing_mode_radio"][value="${settings.report_publishing_mode}"]`);
            if (pubRadio) pubRadio.checked = true;
        }

        if (settings.school_logo) {
            const previewContainer = document.getElementById('logo_preview_container');
            const previewImg = document.getElementById('logo_preview');
            if (previewContainer && previewImg) {
                previewImg.src = settings.school_logo;
                previewContainer.style.display = 'flex';
            }
        }

        if (settings.headmaster_signature) {
            const previewContainer = document.getElementById('sig_preview_container');
            const previewImg = document.getElementById('sig_preview');
            if (previewContainer && previewImg) {
                previewImg.src = settings.headmaster_signature;
                previewContainer.style.display = 'flex';
            }
        }

        populateCustomTierDropdowns();
        const mode = settings.school_mode || 'COMBINED';
        setVal('school_mode', mode);
        localStorage.setItem('school_mode', mode);
        window.updateGradingStandardDropdown(mode);

        // Strict Super Admin check — locks school registration parameters from school admin override
        const isSuperAdmin = (localStorage.getItem('userRole') === 'super_admin' || localStorage.getItem('is_super_admin') === 'true' || localStorage.getItem('username') === 'superadmin');
        const superOnlyFields = ['school_name', 'school_abbreviation', 'school_mode', 'boarding_status', 'boarding_hierarchy_mode'];
        superOnlyFields.forEach(fieldId => {
            const el = document.getElementById(fieldId);
            if (el) {
                if (!isSuperAdmin) {
                    el.disabled = true;
                    el.title = "This parameter is provisioned and managed by the Platform Super-Admin.";
                    el.style.opacity = '0.7';
                    el.style.cursor = 'not-allowed';
                } else {
                    if (fieldId !== 'boarding_hierarchy_mode') {
                        el.disabled = false;
                        el.style.opacity = '1';
                        el.style.cursor = 'default';
                    }
                }
            }
        });

        const lockNotice = document.getElementById('schoolModeLockNotice');
        if (lockNotice) {
            lockNotice.textContent = isSuperAdmin ? '(⭐ Super-Admin Editable)' : '(🔒 Managed by Super-Admin)';
        }
        const bLockNotice = document.getElementById('boardingStatusLockNotice');
        if (bLockNotice) {
            bLockNotice.textContent = isSuperAdmin ? '(⭐ Super-Admin Editable)' : '(🔒 Managed by Super-Admin)';
        }

        const bStatus = settings.boarding_status || 'BOARDING_AND_DAY';
        setVal('boarding_status', bStatus);
        localStorage.setItem('boarding_status', bStatus);
        const bHierarchy = settings.boarding_hierarchy_mode || (mode === 'BASIC_ONLY' ? 'BASIC_TWO_TIER' : 'SHS_THREE_TIER');
        setVal('boarding_hierarchy_mode', bHierarchy);
        localStorage.setItem('boarding_hierarchy_mode', bHierarchy);
        window.updateSettingsProfilePreview(mode, bStatus);
        window.toggleBoardingHierarchyBox(bStatus);

        setVal('class_score_weight', settings.class_score_weight || 30);
        localStorage.setItem('class_score_weight', settings.class_score_weight || 30);
        setVal('exam_score_weight', settings.exam_score_weight || 70);
        localStorage.setItem('exam_score_weight', settings.exam_score_weight || 70);

        if (settings.grading_standard) {
            setVal('grading_standard', settings.grading_standard);
            toggleGradingSection(settings.grading_standard);
        }

        // Load academic years and semesters for settings selects
        try {
            const [yrRes, semRes] = await Promise.all([
                fetch(`${API_BASE}/academic/years`, { headers: getHeaders() }),
                fetch(`${API_BASE}/academic/semesters`, { headers: getHeaders() })
            ]);
            if (yrRes.ok) {
                const years = await yrRes.json();
                const yrSel = document.getElementById('active_academic_year_id');
                if (yrSel) {
                    yrSel.innerHTML = '<option value="">Select Active Academic Year...</option>' +
                        years.map(y => `<option value="${y.id}">${y.label}${y.is_current ? ' (Current)' : ''}</option>`).join('');
                    if (settings.active_academic_year_id) yrSel.value = settings.active_academic_year_id;
                }
            }
            if (semRes.ok) {
                const semesters = await semRes.json();
                const semSel = document.getElementById('active_semester_id');
                const isBasic = (settings.school_mode === 'BASIC_ONLY');
                if (semSel) {
                    semSel.innerHTML = '<option value="">Select Active Term / Semester...</option>' +
                        semesters.map(s => {
                            const name = isBasic ? s.name.replace(/Semester/i, 'Term') : s.name;
                            return `<option value="${s.id}">${name}${s.is_current ? ' (Current)' : ''}</option>`;
                        }).join('');
                    if (settings.active_semester_id) semSel.value = settings.active_semester_id;
                }
            }
        } catch (_) {}

        const savedTheme = settings.system_theme || localStorage.getItem('system_theme') || 'midnight';
        setVal('system_theme', savedTheme);
        if (window.SMSStateBus && window.SMSStateBus.setTheme) {
            window.SMSStateBus.setTheme(savedTheme);
        } else if (window.applyTheme) {
            window.applyTheme(savedTheme);
        }
        if (window.SMSStateBus && window.SMSStateBus.updateBranding) {
            window.SMSStateBus.updateBranding(settings);
        }

        if (settings.grading_standard) {
            setVal('grading_standard', settings.grading_standard);
            toggleGradingSection(settings.grading_standard);
        }
        if (settings.grading_rules) {
            try { gradingRules = JSON.parse(settings.grading_rules); } catch (e) { gradingRules = []; }
        } else {
            gradingRules = [];
        }
        renderGradingTiers();

        setVal('admission_voucher_price', settings.admission_voucher_price || '0.10');
        setVal('admission_momo_recipient_number', settings.admission_momo_recipient_number || '0508929456');
        setVal('admission_momo_recipient_name', settings.admission_momo_recipient_name || 'Duah Bismark');
        setVal('admission_momo_recipient_network', settings.admission_momo_recipient_network || 'Telecel');

        if (window.applySchoolModeVisibility) window.applySchoolModeVisibility();
    } catch (error) {
        console.error('Error loading settings:', error);
    }
}

document.getElementById('grading_standard').addEventListener('change', (e) => {
    toggleGradingSection(e.target.value);
});

const addTierBtn = document.getElementById('addTierBtn');
if (addTierBtn) {
    addTierBtn.addEventListener('click', () => {
        const gradeInput = document.getElementById('new_grade');
        const minScoreInput = document.getElementById('new_min_score');
        const remarkInput = document.getElementById('new_remark');
        const pointsInput = document.getElementById('new_points');

        const grade = gradeInput.value.trim();
        const minScore = minScoreInput.value.trim();
        const remark = remarkInput.value.trim();
        const points = pointsInput.value.trim();

        if (!grade || minScore === "" || !remark || points === "") {
            alert("Please fill all grading tier fields.");
            return;
        }

        const minScoreNum = parseInt(minScore);
        const pointsNum = parseInt(points);

        if (isNaN(minScoreNum) || minScoreNum < 0 || minScoreNum > 100) {
            alert("Min score must be a number between 0 and 100.");
            return;
        }
        if (isNaN(pointsNum) || pointsNum < 1 || pointsNum > 9) {
            alert("Points must be a number between 1 and 9.");
            return;
        }

        // Avoid duplicate grades
        if (gradingRules.some(r => r.grade.toUpperCase() === grade.toUpperCase())) {
            alert(`A tier for grade ${grade} already exists.`);
            return;
        }

        gradingRules.push({
            grade: grade,
            min_score: minScoreNum,
            remark: remark,
            point: pointsNum
        });

        // Reset inputs
        gradeInput.value = "";
        minScoreInput.value = "";
        remarkInput.value = "";
        pointsInput.value = "1";

        renderGradingTiers();
    });
}

const settingsForm = document.getElementById('settingsForm');
if (settingsForm) {
    settingsForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const standard = document.getElementById('grading_standard').value;
        if (standard === 'CUSTOM' && gradingRules.length === 0) {
            alert("Please define at least one grading tier for Custom standard.");
            return;
        }

        const classWeightNum = parseInt(document.getElementById('class_score_weight').value);
        const examWeightNum = parseInt(document.getElementById('exam_score_weight').value);
        if (isNaN(classWeightNum) || isNaN(examWeightNum) || (classWeightNum + examWeightNum !== 100)) {
            alert("SBA Class Weight and Exam Weight must sum to exactly 100%.");
            return;
        }

        const schoolMode = document.getElementById('school_mode')?.value || 'COMBINED';
        const themeVal = document.getElementById('system_theme')?.value || 'midnight';
        const activeYearId = document.getElementById('active_academic_year_id')?.value || '';
        const activeSemesterId = document.getElementById('active_semester_id')?.value || '';
        const boardingStatus = document.getElementById('boarding_status')?.value || 'BOARDING_AND_DAY';
        const boardingHierarchyMode = document.getElementById('boarding_hierarchy_mode')?.value || 'SHS_THREE_TIER';

        const pubRadio = document.querySelector('input[name="publishing_mode_radio"]:checked');
        const reportPublishingMode = pubRadio ? pubRadio.value : 'HYBRID_BOTH';

        const payload = {
            school_name:              document.getElementById('school_name').value,
            school_abbreviation:      document.getElementById('school_abbreviation') ? document.getElementById('school_abbreviation').value : 'JAK STEM',
            report_motto:             document.getElementById('report_motto').value,
            report_title:             document.getElementById('report_title').value,
            report_headmaster:        document.getElementById('report_headmaster').value,
            school_address:           document.getElementById('school_address').value,
            school_phone:             document.getElementById('school_phone').value,
            school_email:             document.getElementById('school_email').value,
            school_mode:              schoolMode,
            boarding_status:          boardingStatus,
            boarding_hierarchy_mode:   boardingHierarchyMode,
            class_score_weight:       classWeightNum,
            exam_score_weight:        examWeightNum,
            system_theme:             themeVal,
            active_academic_year_id:  activeYearId,
            active_semester_id:       activeSemesterId,
            grading_standard:         standard,
            report_publishing_mode:   reportPublishingMode,
            school_logo:              document.getElementById('school_logo').value,
            headmaster_signature:     document.getElementById('headmaster_signature').value,
            grading_rules:            JSON.stringify(gradingRules)
        };

        if (window.SMSStateBus) {
            window.SMSStateBus.setTheme(themeVal);
            window.SMSStateBus.set('school_mode', schoolMode);
            window.SMSStateBus.set('boarding_status', boardingStatus);
            window.SMSStateBus.updateBranding(payload);
        } else {
            localStorage.setItem('system_theme', themeVal);
            localStorage.setItem('school_mode', schoolMode);
            localStorage.setItem('boarding_status', boardingStatus);
            if (window.applyTheme) window.applyTheme(themeVal);
        }

        if (window.applyBranding) window.applyBranding(payload);
        if (window.applySchoolModeVisibility) window.applySchoolModeVisibility(schoolMode, boardingStatus);

        const res = await fetch(`${API_BASE}/settings/`, {
            method: 'PUT',
            headers: getHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify(payload)
        });

        const msgEl = document.getElementById('settingsMsg');
        if (res.ok) {
            msgEl.innerHTML = '<span style="color:var(--success-color)">✔ Settings saved successfully!</span>';
            loadSettings();
            if (window.FeatureGate && window.FeatureGate.refresh) {
                window.FeatureGate.refresh();
            }
            if (window.applyBranding) window.applyBranding(payload);
            if (window.applySchoolModeVisibility) window.applySchoolModeVisibility(schoolMode, boardingStatus);
            if (window.mountSidebarNav) window.mountSidebarNav();
        } else {
            msgEl.innerHTML = '<span style="color:var(--error-color)">❌ Failed to save settings.</span>';
        }
    });
}

const schoolLogoFile = document.getElementById('school_logo_file');
if (schoolLogoFile) {
    schoolLogoFile.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        if (file.size > 2 * 1024 * 1024) {
            alert('Please select an image smaller than 2MB.');
            return;
        }

        // Instant local preview
        const previewContainer = document.getElementById('logo_preview_container');
        const previewImg = document.getElementById('logo_preview');
        const reader = new FileReader();
        reader.onload = (ev) => {
            if (previewImg) previewImg.src = ev.target.result;
            if (previewContainer) previewContainer.style.display = 'flex';
        };
        reader.readAsDataURL(file);

        const formData = new FormData();
        formData.append('file', file);

        try {
            const res = await fetch(`${API_BASE}/settings/upload-logo`, {
                method: 'POST',
                headers: getHeaders(),
                body: formData
            });

            if (!res.ok) {
                const err = await res.json();
                alert(`Upload failed: ${err.detail || 'Unknown error'}`);
                return;
            }

            const data = await res.json();
            const schoolLogoInput = document.getElementById('school_logo');

            if (schoolLogoInput) schoolLogoInput.value = data.logo_url;
            if (previewImg) previewImg.src = data.logo_url;
            if (previewContainer) previewContainer.style.display = 'flex';

            localStorage.setItem('school_logo', data.logo_url);

            // Update Topbar and Sidebar live in DOM
            const schAbbr = localStorage.getItem('school_abbreviation') || 'SMS';
            const topbarLogoContainer = document.getElementById('topbarLogoContainer');
            if (topbarLogoContainer) {
                topbarLogoContainer.innerHTML = `<img src="${data.logo_url}" alt="${schAbbr}" class="topbar-logo-img" style="height:34px; width:34px; object-fit:cover; border-radius:8px; flex-shrink:0; box-shadow:0 2px 6px rgba(0,0,0,0.15);" onerror="this.outerHTML = window.createDefaultCrestSvg ? window.createDefaultCrestSvg('${schAbbr}', 34) : '';" />`;
            }
            const sidebarHeader = document.querySelector('.sidebar-header');
            if (sidebarHeader) {
                const existingSidebarLogo = sidebarHeader.querySelector('.sidebar-logo-img, .school-crest-svg, .sidebar-header > span:first-child');
                const newImg = document.createElement('img');
                newImg.src = data.logo_url;
                newImg.className = 'sidebar-logo-img';
                newImg.style.cssText = 'height:30px; width:30px; object-fit:cover; border-radius:8px; flex-shrink:0;';
                newImg.onerror = function() {
                    this.outerHTML = window.createDefaultCrestSvg ? window.createDefaultCrestSvg(schAbbr, 30) : '';
                };
                if (existingSidebarLogo) existingSidebarLogo.replaceWith(newImg);
            }

            if (window.extractLogoColors) {
                window.extractLogoColors(data.logo_url, function(colors) {
                    if (window.applyTheme) window.applyTheme('auto', colors);
                    const themeSel = document.getElementById('system_theme');
                    if (themeSel) themeSel.value = 'auto';
                });
            }

        } catch (error) {
            console.error('Error uploading logo:', error);
            alert('An error occurred while uploading the logo.');
        }
    });
}

window.resetSchoolLogo = async function() {
    const ok = await (window.showConfirmDialog ? window.showConfirmDialog(
        '🛡️ Reset School Crest',
        'Are you sure you want to reset the school logo to the default vector crest?',
        'Reset to Default Crest',
        'Cancel'
    ) : Promise.resolve(confirm('Are you sure you want to reset the school logo to the default vector crest?')));

    if (!ok) return;
    try {
        const res = await fetch(`${API_BASE}/settings/logo`, {
            method: 'DELETE',
            headers: getHeaders()
        });
        if (res.ok) {
            localStorage.removeItem('school_logo');
            const schoolLogoInput = document.getElementById('school_logo');
            const previewContainer = document.getElementById('logo_preview_container');
            const previewImg = document.getElementById('logo_preview');
            const fileInput = document.getElementById('school_logo_file');
            if (schoolLogoInput) schoolLogoInput.value = '';
            if (previewImg) previewImg.src = '';
            if (previewContainer) previewContainer.style.display = 'none';
            if (fileInput) fileInput.value = '';

            const schAbbr = localStorage.getItem('school_abbreviation') || 'SMS';
            const topbarLogoContainer = document.getElementById('topbarLogoContainer');
            if (topbarLogoContainer && window.createDefaultCrestSvg) {
                topbarLogoContainer.innerHTML = window.createDefaultCrestSvg(schAbbr, 34);
            }
            const sidebarHeader = document.querySelector('.sidebar-header');
            if (sidebarHeader && window.createDefaultCrestSvg) {
                const existing = sidebarHeader.querySelector('.sidebar-logo-img, .school-crest-svg');
                if (existing) {
                    const temp = document.createElement('div');
                    temp.innerHTML = window.createDefaultCrestSvg(schAbbr, 30);
                    existing.replaceWith(temp.firstElementChild);
                }
            }
        }
    } catch (err) {
        console.error('Error resetting logo:', err);
    }
};

const headmasterSigFile = document.getElementById('headmaster_signature_file');
if (headmasterSigFile) {
    headmasterSigFile.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        // Instant local preview
        const previewContainer = document.getElementById('sig_preview_container');
        const previewImg = document.getElementById('sig_preview');
        const reader = new FileReader();
        reader.onload = (ev) => {
            if (previewImg) previewImg.src = ev.target.result;
            if (previewContainer) previewContainer.style.display = 'flex';
        };
        reader.readAsDataURL(file);

        const formData = new FormData();
        formData.append('file', file);

        try {
            const res = await fetch(`${API_BASE}/settings/upload-signature`, {
                method: 'POST',
                headers: getHeaders(),
                body: formData
            });

            if (!res.ok) {
                const err = await res.json();
                alert(`Upload failed: ${err.detail || 'Unknown error'}`);
                return;
            }

            const data = await res.json();
            const headmasterSigInput = document.getElementById('headmaster_signature');

            if (headmasterSigInput) headmasterSigInput.value = data.signature_url;
            if (previewImg) previewImg.src = data.signature_url;
            if (previewContainer) previewContainer.style.display = 'flex';

        } catch (error) {
            console.error('Error uploading signature:', error);
            alert('An error occurred while uploading the signature.');
        }
    });
}

window.resetSignature = function() {
    const headmasterSigInput = document.getElementById('headmaster_signature');
    const previewContainer = document.getElementById('sig_preview_container');
    const previewImg = document.getElementById('sig_preview');
    const fileInput = document.getElementById('headmaster_signature_file');
    if (headmasterSigInput) headmasterSigInput.value = '';
    if (previewImg) previewImg.src = '';
    if (previewContainer) previewContainer.style.display = 'none';
    if (fileInput) fileInput.value = '';
};

window.saveConductSettings = async function(event) {
  event.preventDefault();
  const msgEl = document.getElementById('conductMsg');
  if (msgEl) { msgEl.style.color = '#38bdf8'; msgEl.textContent = 'Saving Code of Conduct & Pledge...'; }

  const payload = {
    code_of_conduct_text: document.getElementById('code_of_conduct_text').value,
    student_pledge_text: document.getElementById('student_pledge_text').value
  };

  try {
    const res = await fetch(`${API_BASE}/settings/`, {
      method: 'PUT',
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      if (msgEl) { msgEl.style.color = '#34d399'; msgEl.textContent = '✔ Code of Conduct & Pledge saved successfully!'; }
    } else {
      const err = await res.json().catch(() => ({ detail: 'Failed to save' }));
      if (msgEl) { msgEl.style.color = '#f87171'; msgEl.textContent = `❌ ${err.detail || 'Save failed'}`; }
    }
  } catch (e) {
    if (msgEl) { msgEl.style.color = '#f87171'; msgEl.textContent = `❌ Network error saving conduct settings: ${e.message}`; }
  }
};

window.uploadConductPDF = async function(event) {
  const file = event.target.files && event.target.files[0];
  if (!file) return;

  const msgEl = document.getElementById('conductMsg');
  if (msgEl) { msgEl.style.color = '#38bdf8'; msgEl.textContent = 'Uploading Code of Conduct PDF...'; }

  const formData = new FormData();
  formData.append('file', file);

  try {
    const res = await fetch(`${API_BASE}/settings/upload-code-of-conduct`, {
      method: 'POST',
      headers: getHeaders(),
      body: formData
    });
    const data = await res.json();
    if (res.ok) {
      const inputEl = document.getElementById('code_of_conduct_pdf_url');
      if (inputEl) inputEl.value = data.document_url;
      if (msgEl) { msgEl.style.color = '#34d399'; msgEl.textContent = '✔ Code of Conduct document uploaded successfully!'; }
    } else {
      if (msgEl) { msgEl.style.color = '#f87171'; msgEl.textContent = `❌ ${data.detail || 'Upload failed'}`; }
    }
  } catch (e) {
    if (msgEl) { msgEl.style.color = '#f87171'; msgEl.textContent = `❌ Network error uploading file: ${e.message}`; }
  }
};

window.savePaystackSettings = async function(event) {
  event.preventDefault();
  const msgEl = document.getElementById('paystackMsg');
  if (msgEl) { msgEl.style.color = '#38bdf8'; msgEl.textContent = 'Saving Paystack Gateway Settings...'; }

  const payload = {
    paystack_enabled: document.getElementById('paystack_enabled').value,
    paystack_public_key: document.getElementById('paystack_public_key').value.trim(),
    paystack_secret_key: document.getElementById('paystack_secret_key').value.trim()
  };

  try {
    const res = await fetch(`${API_BASE}/settings/`, {
      method: 'PUT',
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      if (msgEl) { msgEl.style.color = '#34d399'; msgEl.textContent = '✔ Paystack Gateway Settings saved successfully!'; }
    } else {
      const err = await res.json().catch(() => ({ detail: 'Failed to save' }));
      if (msgEl) { msgEl.style.color = '#f87171'; msgEl.textContent = `❌ ${err.detail || 'Save failed'}`; }
    }
  } catch (e) {
    if (msgEl) { msgEl.style.color = '#f87171'; msgEl.textContent = `❌ Network error saving Paystack settings: ${e.message}`; }
  }
};

window.saveVoucherSettings = async function(event) {
  event.preventDefault();
  const msgEl = document.getElementById('voucherSettingsMsg');
  if (msgEl) { msgEl.style.color = '#38bdf8'; msgEl.textContent = 'Saving Voucher & Settlement Settings...'; }

  const payload = {
    admission_voucher_price: document.getElementById('admission_voucher_price').value.trim(),
    admission_momo_recipient_number: document.getElementById('admission_momo_recipient_number').value.trim(),
    admission_momo_recipient_name: document.getElementById('admission_momo_recipient_name').value.trim(),
    admission_momo_recipient_network: document.getElementById('admission_momo_recipient_network').value
  };

  try {
    const res = await fetch(`${API_BASE}/settings/`, {
      method: 'PUT',
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      if (msgEl) { msgEl.style.color = '#34d399'; msgEl.textContent = '✔ Voucher & Settlement settings saved successfully!'; }
    } else {
      const err = await res.json().catch(() => ({ detail: 'Failed to save' }));
      if (msgEl) { msgEl.style.color = '#f87171'; msgEl.textContent = `❌ ${err.detail || 'Save failed'}`; }
    }
  } catch (e) {
    if (msgEl) { msgEl.style.color = '#f87171'; msgEl.textContent = `❌ Network error: ${e.message}`; }
  }
};
 
window.loadSchoolSubaccount = async function() {
  try {
    const res = await fetch(`${API_BASE}/settings/subaccount`, { headers: getHeaders() });
    if (res.ok) {
      const data = await res.json();
      if (data.settlement_bank) document.getElementById('sub_settlement_bank').value = data.settlement_bank;
      if (data.account_number) document.getElementById('sub_account_number').value = data.account_number;
      if (data.account_name) document.getElementById('sub_account_name').value = data.account_name;
      const badge = document.getElementById('subaccountBadge');
      if (badge && data.paystack_subaccount_code) {
        badge.textContent = `SUBACCOUNT: ${data.paystack_subaccount_code}`;
        badge.style.background = 'rgba(16,185,129,0.15)';
        badge.style.color = '#34d399';
      }
    }
  } catch (_) {}
};

window.saveSchoolSubaccount = async function(event) {
  event.preventDefault();
  const msgEl = document.getElementById('subSaveMsg');
  if (msgEl) { msgEl.style.color = '#38bdf8'; msgEl.textContent = 'Saving subaccount...'; }
  const payload = {
    settlement_bank: document.getElementById('sub_settlement_bank').value,
    account_number: document.getElementById('sub_account_number').value.trim(),
    account_name: document.getElementById('sub_account_name').value.trim()
  };
  try {
    const res = await fetch(`${API_BASE}/settings/subaccount`, {
      method: 'POST',
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (res.ok) {
      if (msgEl) { msgEl.style.color = '#34d399'; msgEl.textContent = `✔ Saved! (${data.subaccount_code})`; }
      window.loadSchoolSubaccount();
    } else {
      if (msgEl) { msgEl.style.color = '#f87171'; msgEl.textContent = `❌ ${data.detail || 'Failed'}`; }
    }
  } catch (e) {
    if (msgEl) { msgEl.style.color = '#f87171'; msgEl.textContent = `❌ ${e.message}`; }
  }
};

window.loadSchoolSmsConfig = async function() {
  try {
    const res = await fetch(`${API_BASE}/settings/sms-config`, { headers: getHeaders() });
    if (res.ok) {
      const data = await res.json();
      if (data.sender_id) document.getElementById('sms_sender_id').value = data.sender_id;
    }
  } catch (_) {}
};

window.saveSchoolSmsConfig = async function(event) {
  event.preventDefault();
  const msgEl = document.getElementById('smsSaveMsg');
  if (msgEl) { msgEl.style.color = '#38bdf8'; msgEl.textContent = 'Updating Sender ID...'; }
  const payload = {
    sender_id: document.getElementById('sms_sender_id').value.trim().toUpperCase()
  };
  try {
    const res = await fetch(`${API_BASE}/settings/sms-config`, {
      method: 'POST',
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (res.ok) {
      if (msgEl) { msgEl.style.color = '#34d399'; msgEl.textContent = `✔ Sender ID set to ${data.sender_id}!`; }
    } else {
      if (msgEl) { msgEl.style.color = '#f87171'; msgEl.textContent = `❌ ${data.detail || 'Failed'}`; }
    }
  } catch (e) {
    if (msgEl) { msgEl.style.color = '#f87171'; msgEl.textContent = `❌ ${e.message}`; }
  }
};

window.loadActiveSessions = async function() {
  const tbody = document.getElementById('activeSessionsTableBody');
  if (!tbody) return;
  try {
    const res = await fetch(`${API_BASE}/settings/sessions`, { headers: getHeaders() });
    if (res.ok) {
      const list = await res.json();
      if (list.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; padding:12px; opacity:0.6;">No active sessions found.</td></tr>';
        return;
      }
      tbody.innerHTML = list.map(s => `
        <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
          <td style="padding:10px 8px;">
            <strong>${escapeHtml(s.device_name)}</strong>
            ${s.is_current ? '<span style="background:rgba(34,197,94,0.15); color:#4ade80; font-size:0.7rem; padding:2px 6px; border-radius:4px; margin-left:6px;">Current Device</span>' : ''}
          </td>
          <td style="padding:10px 8px; font-family:monospace; color:#94a3b8;">${escapeHtml(s.ip_address)}</td>
          <td style="padding:10px 8px; font-size:0.82rem; color:#cbd5e1;">${escapeHtml(s.last_active)}</td>
          <td style="padding:10px 8px;">
            <span style="color:${s.is_current ? '#4ade80' : '#818cf8'}; font-weight:bold; font-size:0.8rem;">● ACTIVE</span>
          </td>
        </tr>
      `).join('');
    }
  } catch (_) {
    tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; padding:12px; color:#f87171;">Failed to load device sessions.</td></tr>';
  }
};

window.revokeOtherSessions = async function() {
  if (!confirm('Are you sure you want to terminate all other logged-in device sessions? You will stay logged in on this device.')) return;
  try {
    const res = await fetch(`${API_BASE}/settings/sessions/revoke-others`, {
      method: 'POST',
      headers: getHeaders()
    });
    if (res.ok) {
      alert('✔ Successfully revoked all other active sessions.');
      window.loadActiveSessions();
    } else {
      alert('❌ Failed to revoke sessions.');
    }
  } catch (e) {
    alert(`❌ Error: ${e.message}`);
  }
};

loadSettings();
if (window.loadSchoolSubaccount) window.loadSchoolSubaccount();
if (window.loadSchoolSmsConfig) window.loadSchoolSmsConfig();
if (window.loadActiveSessions) window.loadActiveSessions();

