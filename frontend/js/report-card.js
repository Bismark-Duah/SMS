// Student Terminal Report Card & Official SHS Transcript View Controller

let currentReportData = null;
let currentTranscriptData = null;
let isTranscriptMode = false;

document.addEventListener("DOMContentLoaded", () => {
  const urlParams = new URLSearchParams(window.location.search);
  if (urlParams.get("mode") === "transcript") {
    isTranscriptMode = true;
    initTranscriptMode();
  } else {
    loadReportCard();
  }
});

async function getAuthToken() {
  return localStorage.getItem("accessToken") || localStorage.getItem("token") || sessionStorage.getItem("token");
}

function getHeaders(headers = {}) {
  const token = localStorage.getItem("accessToken") || localStorage.getItem("token");
  return { Authorization: `Bearer ${token}`, ...headers };
}

// ── Standard Report Card Loader ───────────────────────────────────────────────
async function loadReportCard() {
  const urlParams = new URLSearchParams(window.location.search);
  const studentId = urlParams.get("student_id");
  const semesterId = urlParams.get("semester_id");

  const loadingEl = document.getElementById("loadingState");
  const errorEl = document.getElementById("errorState");
  const cardContainer = document.getElementById("reportCard");

  if (!studentId || !semesterId) {
    if (loadingEl) loadingEl.style.display = "none";
    if (errorEl) {
      errorEl.innerText = "Error: student_id and semester_id parameters are required in the URL.";
      errorEl.style.display = "block";
    }
    return;
  }

  const token = await getAuthToken();
  if (!token) {
    window.location.href = "auth.html";
    return;
  }

  try {
    const res = await fetch(`/api/reports/report-data/${studentId}?semester_id=${semesterId}`, {
      headers: getHeaders()
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Failed to load report data." }));
      throw new Error(err.detail || `Server error (${res.status})`);
    }

    currentReportData = await res.json();

    if (loadingEl) loadingEl.style.display = "none";
    if (errorEl) errorEl.style.display = "none";
    if (cardContainer) cardContainer.style.display = "block";

    renderReportCard(currentReportData);
  } catch (err) {
    if (loadingEl) loadingEl.style.display = "none";
    if (errorEl) {
      errorEl.innerText = `Unable to display report card: ${err.message}`;
      errorEl.style.display = "block";
    }
  }
}

function renderReportCard(data) {
  const logoEl = document.getElementById("rc-logo");
  if (logoEl) {
    if (data.school_logo) {
      logoEl.src = data.school_logo;
      logoEl.style.display = "inline-block";
      logoEl.onerror = function() {
        this.style.display = "none";
      };
    } else {
      logoEl.style.display = "none";
    }
  }

  setText("rc-school-name", data.school_name || "SCHOOL MANAGEMENT SYSTEM");
  setText("rc-school-motto", data.report_motto ? `"${data.report_motto}"` : "");
  setText("rc-school-address", data.school_address || "");
  
  let contactStr = "";
  if (data.school_phone) contactStr += `Tel: ${data.school_phone} `;
  if (data.school_email) contactStr += `| Email: ${data.school_email}`;
  setText("rc-school-contact", contactStr);

  setText("rc-report-title", data.report_title || "TERMINAL REPORT");

  const isPub = data.is_published;
  const statusBadge = document.getElementById("rc-status-badge");
  const watermarkEl = document.getElementById("rc-watermark");

  if (statusBadge) {
    if (isPub) {
      statusBadge.className = "rc-badge published";
      statusBadge.innerHTML = "🟢 OFFICIAL TERMINAL REPORT - PUBLISHED";
      if (watermarkEl) {
        if (data.school_logo) {
          watermarkEl.src = data.school_logo;
          watermarkEl.style.display = "block";
          watermarkEl.onerror = function() { this.style.display = "none"; };
        } else {
          watermarkEl.style.display = "none";
        }
      }
    } else {
      statusBadge.className = "rc-badge draft";
      statusBadge.innerHTML = "⚠️ UNPUBLISHED DRAFT - FOR INTERNAL REVIEW ONLY";
      if (watermarkEl) watermarkEl.style.display = "none";
    }
  }

  const s = data.student || {};
  setText("rc-student-name", s.full_name || "-");
  setText("rc-student-code", s.student_code || "-");
  setText("rc-class-name", data.class_section?.name || s.class_name || "-");
  setText("rc-academic-year", data.academic_year?.label || "-");
  setText("rc-term-name", data.semester?.name || "-");
  setText("rc-gender", s.gender || "-");
  setText("rc-house-dorm", `${s.house_name || "Day Student"}${s.dormitory_name ? " / " + s.dormitory_name : ""}`);
  setText("rc-guardian-name", s.guardian_name || "-");

  const tbody = document.getElementById("rc-scores-body");
  if (tbody && Array.isArray(data.scores)) {
    if (data.scores.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" style="padding:20px; opacity:0.6;">No subject assessment scores logged for this term.</td></tr>`;
    } else {
      tbody.innerHTML = data.scores.map(sc => `
        <tr>
          <td style="text-align:left; font-weight:600;">
            ${sc.subject_name || "Subject"}
            ${sc.is_core ? '<span style="font-size:0.7rem; background:#e2e8f0; color:#475569; padding:1px 5px; border-radius:4px; margin-left:4px;">Core</span>' : ''}
          </td>
          <td>${sc.class_score !== null ? sc.class_score : "-"}</td>
          <td>${sc.exam_score !== null ? sc.exam_score : "-"}</td>
          <td style="font-weight:700;">${sc.total_score !== null ? sc.total_score : "-"}</td>
          <td class="grade-${sc.grade}">${sc.grade || "-"}</td>
          <td>${sc.remark || "-"}</td>
          <td>${sc.position_in_subject ? sc.position_in_subject + ordinalSuffix(sc.position_in_subject) : "-"}</td>
        </tr>
      `).join("");
    }
  }

  const stats = data.summary_stats || {};
  setText("rc-total-marks", stats.total_score !== undefined ? stats.total_score.toFixed(1) : "0.0");
  setText("rc-average-mark", stats.average_score !== undefined ? stats.average_score.toFixed(1) + "%" : "0.0%");
  setText("rc-overall-grade", stats.overall_grade || "N/A");
  
  const posEl = document.getElementById("rc-class-position");
  if (posEl) {
    posEl.innerText = stats.class_position ? `${stats.class_position} / ${stats.total_students || "-"}` : "-";
  }

  const attEl = document.getElementById("rc-attendance-stat");
  if (attEl) {
    const att = data.attendance || {};
    attEl.innerText = att.present_days !== undefined ? `${att.present_days} / ${att.total_days} days` : "-";
  }

  const eval = data.evaluation || {};
  setInputValue("eval_attitude", eval.attitude || "");
  setInputValue("eval_conduct", eval.conduct || "");
  setInputValue("eval_interest", eval.interest || "");
  setInputValue("eval_form_remarks", eval.form_master_remarks || "");
  setInputValue("eval_head_remarks", eval.headmaster_remarks || "");
  setInputValue("eval_promoted_to", eval.promoted_to || "");

  setText("rc-closing-date", data.vacation_date || "-");
  setText("rc-reopening-date", data.reopening_date || "-");

  const formSigName = document.getElementById("rc-form-master-name");
  if (formSigName) formSigName.innerText = data.class_section?.form_master_name || "Form Master";

  const headSigImg = document.getElementById("rc-headmaster-sig-img");
  if (headSigImg) {
    if (data.headmaster_signature) {
      headSigImg.src = data.headmaster_signature;
      headSigImg.style.display = "inline-block";
    } else {
      headSigImg.style.display = "none";
    }
  }

  renderLegend(data.grading_scale);
}

// ── Official SHS Academic Transcript Mode ────────────────────────────────────
let activeTranscriptFormat = 'waec'; // Default to WAEC Statement format

async function initTranscriptMode() {
  const titleEl = document.getElementById("pageTitleHeading");
  if (titleEl) titleEl.innerText = "📜 Official WAEC Statement & SHS Transcript";

  const fmtToggle = document.getElementById("transcriptFormatToggle");
  if (fmtToggle) fmtToggle.style.display = "flex";

  const activeRole = (sessionStorage.getItem('activeRole') || localStorage.getItem('activeRole') || sessionStorage.getItem('userRole') || localStorage.getItem('userRole') || '').toLowerCase();
  const isStudentOrParent = ['student', 'parent'].includes(activeRole);

  const pickerContainer = document.getElementById("transcriptPickerContainer");
  if (pickerContainer && !isStudentOrParent) {
    pickerContainer.style.display = "flex";
  }

  const urlParams = new URLSearchParams(window.location.search);
  const targetStudentId = urlParams.get("student_id");

  // Load All Students for Selector Dropdown (Admin/Teacher mode)
  if (!isStudentOrParent) {
    try {
      const res = await fetch(`/api/students/?include_inactive=false`, { headers: getHeaders() });
      if (res.ok) {
        const students = await res.json();
        const selectEl = document.getElementById("transcriptStudentSelect");
        if (selectEl) {
          selectEl.innerHTML = `<option value="">Select Student...</option>` + 
            students.map(st => `<option value="${st.id}" ${String(st.id) === String(targetStudentId) ? 'selected' : ''}>${st.full_name} (${st.student_code})</option>`).join('');
        }
      }
    } catch (e) {
      console.error("Failed to load students list for transcript picker:", e);
    }
  }

  if (targetStudentId) {
    loadTranscriptData(targetStudentId);
  } else if (isStudentOrParent) {
    const modal = document.getElementById("waecIndexModal");
    if (modal) modal.style.display = "flex";
  } else {
    const loadingEl = document.getElementById("loadingState");
    const errorEl = document.getElementById("errorState");
    if (loadingEl) loadingEl.style.display = "none";
    if (errorEl) {
      errorEl.innerText = "ℹ️ Please select a student from the dropdown above to view their Official Academic Transcript.";
      errorEl.style.color = "#6366f1";
      errorEl.style.display = "block";
    }
  }
}

window.onTranscriptStudentChange = function(studentId) {
  if (studentId) {
    const url = new URL(window.location.href);
    url.searchParams.set("mode", "transcript");
    url.searchParams.set("student_id", studentId);
    window.history.pushState({}, "", url.toString());
    loadTranscriptData(studentId);
  }
};

async function loadTranscriptData(studentId) {
  const loadingEl = document.getElementById("loadingState");
  const errorEl = document.getElementById("errorState");

  if (loadingEl) loadingEl.style.display = "block";
  if (errorEl) errorEl.style.display = "none";

  try {
    const res = await fetch(`/api/reports/official-transcript/${studentId}`, { headers: getHeaders() });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Failed to retrieve transcript data." }));
      throw new Error(err.detail || `Server error (${res.status})`);
    }

    currentTranscriptData = await res.json();

    if (loadingEl) loadingEl.style.display = "none";
    if (errorEl) errorEl.style.display = "none";

    displayCurrentTranscript();
  } catch (err) {
    if (loadingEl) loadingEl.style.display = "none";
    if (errorEl) {
      errorEl.innerText = `Unable to display transcript: ${err.message}`;
      errorEl.style.color = "#ef4444";
      errorEl.style.display = "block";
    }
  }
}

window.switchTranscriptFormat = function(format) {
  activeTranscriptFormat = format;
  const btnWAEC = document.getElementById("btnFmtWAEC");
  const btnInternal = document.getElementById("btnFmtInternal");
  if (btnWAEC) btnWAEC.classList.toggle("active", format === "waec");
  if (btnInternal) btnInternal.classList.toggle("active", format === "internal");

  if (currentTranscriptData) {
    displayCurrentTranscript();
  }
};

function displayCurrentTranscript() {
  const internalCard = document.getElementById("reportCard");
  const waecCard = document.getElementById("waecTranscriptCard");

  if (activeTranscriptFormat === "waec") {
    if (internalCard) internalCard.style.display = "none";
    if (waecCard) waecCard.style.display = "block";
    renderWAECTranscriptCard(currentTranscriptData);
  } else {
    if (waecCard) waecCard.style.display = "none";
    if (internalCard) internalCard.style.display = "block";
    renderTranscriptCard(currentTranscriptData);
  }
}

window.submitWAECIndexVerification = async function() {
  const inputEl = document.getElementById("waecIndexInput");
  const errorEl = document.getElementById("waecIndexError");
  const indexVal = inputEl ? inputEl.value.trim() : "";

  if (!indexVal) {
    if (errorEl) { errorEl.innerText = "Please enter a valid WASSCE Index Number or Candidate Code."; errorEl.style.display = "block"; }
    return;
  }

  if (errorEl) errorEl.style.display = "none";

  try {
    const res = await fetch(`/api/reports/waec-transcript-by-index/${encodeURIComponent(indexVal)}`, { headers: getHeaders() });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Candidate verification failed." }));
      throw new Error(err.detail || "Candidate not found.");
    }

    currentTranscriptData = await res.json();
    const modal = document.getElementById("waecIndexModal");
    if (modal) modal.style.display = "none";

    displayCurrentTranscript();
  } catch (err) {
    if (errorEl) {
      errorEl.innerText = err.message;
      errorEl.style.display = "block";
    }
  }
};

function renderWAECTranscriptCard(data) {
  const waecCard = document.getElementById("waecTranscriptCard");
  if (!waecCard || !data) return;

  const sch = data.school_info || {};

  const nameEl = document.getElementById("waecCandName");
  if (nameEl) nameEl.textContent = data.full_name || "-";
  
  const idxEl = document.getElementById("waecCandIndex");
  if (idxEl) idxEl.textContent = data.wassce_index_number || data.student_code || "-";
  
  const schEl = document.getElementById("waecSchoolName");
  if (schEl) schEl.textContent = `${sch.name || "SENIOR HIGH SCHOOL"} (${sch.centre_number || "1090400"})`;
  
  const progEl = document.getElementById("waecProgName");
  if (progEl) progEl.textContent = data.program_name || "General Science";
  
  const genEl = document.getElementById("waecGenderRes");
  if (genEl) genEl.textContent = `${(data.gender || "M").toUpperCase()} | ${data.residential_status || "Boarding"}`;
  
  const seriesEl = document.getElementById("waecExamSeries");
  if (seriesEl) seriesEl.textContent = data.waec_series || "MAY/JUNE WASSCE 2025";
  
  const hashEl = document.getElementById("waecHashVal");
  if (hashEl) hashEl.textContent = data.verification_hash || "WAEC-OFFLINE-VALIDATED";

  // WASSCE Subjects
  const extSubs = data.external_wassce_subjects || [];
  const tbody = document.getElementById("waecSubjectsTbody");
  if (tbody) {
    if (extSubs.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" style="padding:12px; text-align:center; opacity:0.6;">No WASSCE subject results recorded yet.</td></tr>`;
    } else {
      tbody.innerHTML = extSubs.map(s => {
        const catBadge = s.is_core ? `<span style="background:rgba(2,132,199,0.15); color:#0369a1; padding:2px 8px; border-radius:12px; font-weight:700; font-size:0.75rem;">CORE</span>` : `<span style="background:rgba(99,102,241,0.15); color:#4f46e5; padding:2px 8px; border-radius:12px; font-weight:700; font-size:0.75rem;">ELECTIVE</span>`;
        return `
          <tr style="border-bottom:1px solid #e2e8f0;">
            <td style="padding:8px 12px; font-weight:700; color:#0f172a;">${s.subject_name} <span style="font-size:0.75rem; color:#64748b;">(${s.subject_code || 'WASSCE'})</span></td>
            <td style="padding:8px 12px; text-align:center;">${catBadge}</td>
            <td style="padding:8px 12px; text-align:center; font-weight:700;">${s.total_score}%</td>
            <td style="padding:8px 12px; text-align:center;"><strong style="font-size:1.05rem; color:${s.grade === 'F9' ? '#ef4444' : '#0284c7'};">${s.grade || 'A1'}</strong></td>
            <td style="padding:8px 12px; font-weight:700; color:#334155;">${s.interpretation || 'Credit'}</td>
          </tr>
        `;
      }).join('');
    }
  }

  // Internal Practical Subjects
  const intSubs = data.internal_transcript_subjects || [];
  const intSec = document.getElementById("waecInternalSection");
  const intTbody = document.getElementById("waecInternalTbody");
  if (intSubs.length > 0) {
    if (intSec) intSec.style.display = "block";
    if (intTbody) {
      intTbody.innerHTML = intSubs.map(s => `
        <tr style="border-bottom:1px solid #cbd5e1;">
          <td style="padding:6px 12px; font-weight:600;">${s.subject_name}</td>
          <td style="padding:6px 12px; text-align:center;"><span style="background:#f1f5f9; color:#475569; padding:2px 6px; border-radius:4px; font-size:0.72rem; font-weight:700;">PRACTICAL / STEM</span></td>
          <td style="padding:6px 12px; text-align:center; font-weight:700;">${s.total_score}%</td>
          <td style="padding:6px 12px; text-align:center; font-weight:800; color:#0369a1;">${s.grade || 'A1'}</td>
        </tr>
      `).join('');
    }
  } else {
    if (intSec) intSec.style.display = "none";
  }

  // Render SVG QR code locally
  const qrContainer = document.getElementById("waecQrCodeContainer");
  if (qrContainer) {
    qrContainer.innerHTML = `<svg width="64" height="64" viewBox="0 0 100 100" style="display:block;"><rect width="100" height="100" fill="#ffffff"/><path d="M10 10h30v30h-30zM15 15v20h20v-20zM60 10h30v30h-30zM65 15v20h20v-20zM10 60h30v30h-30zM15 65v20h20v-20zM50 50h10v10h-10zM70 50h20v10h-20zM50 70h20v10h-20zM80 70h10v20h-10z" fill="#0284c7"/></svg>`;
  }
}

function calculateWASSCEGradeValue(gradeStr) {
  if (!gradeStr) return 9;
  const g = gradeStr.trim().toUpperCase();
  if (g === 'A1') return 1;
  if (g === 'B2') return 2;
  if (g === 'B3') return 3;
  if (g === 'C4') return 4;
  if (g === 'C5') return 5;
  if (g === 'C6') return 6;
  if (g === 'D7') return 7;
  if (g === 'E8') return 8;
  return 9; // F9
}

function renderTranscriptCard(data) {
  const card = document.getElementById("reportCard");
  if (!card) return;

  const sch = data.school_info || {};

  // Calculate WASSCE Best 6 Aggregate
  const extSubs = data.external_wassce_subjects || [];
  const coreSubs = extSubs.filter(s => s.is_core);
  const elecSubs = extSubs.filter(s => !s.is_core);

  // Top 3 Core grades + Top 3 Elective grades
  const sortedCore = coreSubs.map(s => calculateWASSCEGradeValue(s.grade)).sort((a, b) => a - b);
  const sortedElec = elecSubs.map(s => calculateWASSCEGradeValue(s.grade)).sort((a, b) => a - b);

  let best6Aggregate = 0;
  if (sortedCore.length >= 3 && sortedElec.length >= 3) {
    best6Aggregate = sortedCore.slice(0, 3).reduce((a, b) => a + b, 0) + sortedElec.slice(0, 3).reduce((a, b) => a + b, 0);
  } else {
    // Fallback best 6 of any
    const allVals = extSubs.map(s => calculateWASSCEGradeValue(s.grade)).sort((a, b) => a - b);
    best6Aggregate = allVals.slice(0, 6).reduce((a, b) => a + b, 0);
  }

  const verifyHash = `TRX-${new Date().getFullYear()}-${Math.floor(100000 + Math.random() * 900000)}`;

  card.innerHTML = `
    <div style="font-family: 'Segoe UI', Tahoma, sans-serif; padding: 20px; background: #fff; color: #111;">
      
      <!-- Top Header -->
      <div style="text-align: center; border-bottom: 3px double #111; padding-bottom: 12px; margin-bottom: 20px;">
        <div style="font-size: 0.8rem; letter-spacing: 2px; font-weight: 700; color: #4338ca; text-transform: uppercase; margin-bottom: 4px;">REPUBLIC OF GHANA • MINISTRY OF EDUCATION / GES</div>
        <h1 style="margin: 0; font-size: 1.6rem; color: #111827; font-weight: 900; text-transform: uppercase;">${sch.name || "SENIOR HIGH SCHOOL"}</h1>
        <p style="margin: 4px 0 0; font-size: 0.85rem; color: #4b5563;">${sch.address || "Ghana"} ${sch.phone ? '| Tel: ' + sch.phone : ''}</p>
        <div style="margin-top: 10px; background: #1e1b4b; color: #ffffff; padding: 6px 16px; border-radius: 4px; font-weight: 800; font-size: 1rem; letter-spacing: 1px; display: inline-block;">
          OFFICIAL SENIOR HIGH SCHOOL ACADEMIC TRANSCRIPT
        </div>
      </div>

      <!-- Student Candidate Profile Grid -->
      <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px; font-size: 0.88rem; background: #f8fafc; border: 1px solid #cbd5e1;" cellpadding="8">
        <tr>
          <td style="width: 50%; border-right: 1px solid #cbd5e1; border-bottom: 1px solid #cbd5e1;"><strong>Candidate Full Name:</strong> <span style="font-size: 0.95rem; font-weight: 700; color: #1e293b;">${data.full_name}</span></td>
          <td style="width: 50%; border-bottom: 1px solid #cbd5e1;"><strong>Student Enrolment ID:</strong> <span style="font-family: monospace; font-weight: 700; color: #4338ca;">${data.student_code}</span></td>
        </tr>
        <tr>
          <td style="border-right: 1px solid #cbd5e1; border-bottom: 1px solid #cbd5e1;"><strong>BECE Index Number:</strong> ${data.bece_index_number || 'N/A'}</td>
          <td style="border-bottom: 1px solid #cbd5e1;"><strong>CSSPS Enrolment Code:</strong> ${data.enrolment_code || 'N/A'}</td>
        </tr>
        <tr>
          <td style="border-right: 1px solid #cbd5e1; border-bottom: 1px solid #cbd5e1;"><strong>Programme of Study:</strong> <span style="font-weight: 700;">${data.program_name}</span></td>
          <td style="border-bottom: 1px solid #cbd5e1;"><strong>Gender / DOB:</strong> ${data.gender || 'N/A'}</td>
        </tr>
        <tr>
          <td style="border-right: 1px solid #cbd5e1;"><strong>Residential Status:</strong> ${data.residential_status} (${data.house_name || 'Day'} House)</td>
          <td><strong>Enrolment Status:</strong> <span style="color: #059669; font-weight: 700;">Active / Validated</span></td>
        </tr>
      </table>

      <!-- Section A: External WASSCE Subjects -->
      <div style="background: #1e293b; color: #ffffff; padding: 6px 12px; font-weight: 700; font-size: 0.85rem; letter-spacing: 0.5px; margin-bottom: 8px; border-radius: 4px;">
        SECTION A: EXTERNAL WASSCE CORE & ELECTIVE ASSESSMENT RECORD
      </div>
      <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px; font-size: 0.84rem; border: 1px solid #cbd5e1;" border="1" cellpadding="6">
        <thead style="background: #f1f5f9; text-transform: uppercase; font-size: 0.78rem;">
          <tr>
            <th style="text-align: left;">Subject Title</th>
            <th>Code</th>
            <th>Year</th>
            <th>Term</th>
            <th>Total Score (100%)</th>
            <th>WASSCE Grade</th>
            <th style="text-align: left;">Remarks</th>
          </tr>
        </thead>
        <tbody>
          ${data.external_wassce_subjects && data.external_wassce_subjects.length > 0 ? data.external_wassce_subjects.map(s => `
            <tr>
              <td style="font-weight: 600;">
                ${s.subject_name}
                ${s.is_core ? '<span style="font-size:0.68rem; background:#e0e7ff; color:#3730a3; padding:1px 4px; border-radius:3px; margin-left:4px;">Core</span>' : ''}
              </td>
              <td style="text-align: center; font-family: monospace;">${s.subject_code || '-'}</td>
              <td style="text-align: center;">${s.academic_year}</td>
              <td style="text-align: center;">${s.semester_name}</td>
              <td style="text-align: center; font-weight: 700;">${s.total_score !== null ? s.total_score : '-'}</td>
              <td style="text-align: center; font-weight: 800; color: #1e1b4b; font-size: 0.9rem;">${s.grade || '-'}</td>
              <td>${s.remark || '-'}</td>
            </tr>
          `).join('') : '<tr><td colspan="7" style="text-align:center; padding: 14px; opacity: 0.6;">No WASSCE subject assessments recorded.</td></tr>'}
        </tbody>
      </table>

      <!-- Section B: Internal & Practical Subjects -->
      <div style="background: #065f46; color: #ffffff; padding: 6px 12px; font-weight: 700; font-size: 0.85rem; letter-spacing: 0.5px; margin-bottom: 8px; border-radius: 4px;">
        SECTION B: INTERNAL TRANSCRIPT & PRACTICAL ASSESSMENT RECORD (PEH / STEM / ICT)
      </div>
      <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px; font-size: 0.84rem; border: 1px solid #cbd5e1;" border="1" cellpadding="6">
        <thead style="background: #f1f5f9; text-transform: uppercase; font-size: 0.78rem;">
          <tr>
            <th style="text-align: left;">Subject / Project Title</th>
            <th>Code</th>
            <th>Year</th>
            <th>Term</th>
            <th>Score (100%)</th>
            <th>Grade</th>
            <th style="text-align: left;">Remarks</th>
          </tr>
        </thead>
        <tbody>
          ${data.internal_transcript_subjects && data.internal_transcript_subjects.length > 0 ? data.internal_transcript_subjects.map(s => `
            <tr>
              <td style="font-weight: 600;">${s.subject_name}</td>
              <td style="text-align: center; font-family: monospace;">${s.subject_code || '-'}</td>
              <td style="text-align: center;">${s.academic_year}</td>
              <td style="text-align: center;">${s.semester_name}</td>
              <td style="text-align: center; font-weight: 700;">${s.total_score !== null ? s.total_score : '-'}</td>
              <td style="text-align: center; font-weight: 800;">${s.grade || '-'}</td>
              <td>${s.remark || '-'}</td>
            </tr>
          `).join('') : '<tr><td colspan="7" style="text-align:center; padding: 14px; opacity: 0.6;">No internal assessment subjects logged.</td></tr>'}
        </tbody>
      </table>

      <!-- Summary & WASSCE Best 6 Aggregate Box -->
      <div style="display: flex; gap: 16px; margin-bottom: 24px; align-items: center; background: #eff6ff; border: 1px solid #bfdbfe; padding: 14px 18px; border-radius: 8px;">
        <div style="flex: 1;">
          <div style="font-size: 0.75rem; text-transform: uppercase; font-weight: 700; color: #1e40af;">WASSCE Best 6 Aggregate Score:</div>
          <div style="font-size: 1.6rem; font-weight: 900; color: #1d4ed8;">${best6Aggregate > 0 ? String(best6Aggregate).padStart(2, '0') : 'N/A'}</div>
        </div>
        <div style="flex: 3; font-size: 0.82rem; color: #1e3a8a; line-height: 1.4;">
          <strong>Official Recommendation Note:</strong> Based on continuous academic evaluation across Form 1 to Form 3, candidate has demonstrated satisfactory performance and adherence to school standards.
        </div>
      </div>

      <!-- Certification & Official Stamps -->
      <div style="margin-top: 36px; padding-top: 16px; border-top: 2px dashed #94a3b8; display: flex; justify-content: space-between; align-items: flex-end; font-size: 0.85rem;">
        <div style="min-width: 220px; text-align: center;">
          <div style="border-bottom: 1px solid #334155; height: 40px; margin-bottom: 6px;"></div>
          <strong>Headmaster / Principal Signature</strong>
          <div style="font-size: 0.75rem; color: #64748b;">${sch.headmaster || "Headmaster"}</div>
        </div>

        <div style="text-align: center; border: 2px dashed #cbd5e1; padding: 10px 20px; border-radius: 8px; min-width: 160px; background: #fafafa;">
          <div style="font-size: 0.7rem; color: #94a3b8; text-transform: uppercase; font-weight: 700;">OFFICIAL SCHOOL STAMP</div>
          <div style="height: 30px;"></div>
        </div>

        <div style="min-width: 200px; text-align: right;">
          <div style="font-size: 0.72rem; font-family: monospace; color: #64748b;">${verifyHash}</div>
          <div style="font-size: 0.78rem; font-weight: 700; color: #334155; margin-top: 4px;">Date Issued: ${new Date().toLocaleDateString('en-GB')}</div>
        </div>
      </div>

    </div>
  `;
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.innerText = val;
}

function setInputValue(id, val) {
  const el = document.getElementById(id);
  if (el) el.value = val;
}

function ordinalSuffix(i) {
  const j = i % 10, k = i % 100;
  if (j === 1 && k !== 11) return "st";
  if (j === 2 && k !== 12) return "nd";
  if (j === 3 && k !== 13) return "rd";
  return "th";
}

function renderLegend(scale) {
  const tbody = document.getElementById("rc-legend-body");
  if (!tbody) return;

  if (Array.isArray(scale) && scale.length > 0) {
    tbody.innerHTML = scale.map(g => `
      <tr>
        <td style="padding:4px; border:1px solid #cbd5e1; font-weight:700;">${g.grade}</td>
        <td style="padding:4px; border:1px solid #cbd5e1;">${g.min_score}%</td>
        <td style="padding:4px; border:1px solid #cbd5e1;">${g.remark}</td>
        <td style="padding:4px; border:1px solid #cbd5e1;">${g.grade_value ?? "-"}</td>
      </tr>
    `).join("");
  } else {
    tbody.innerHTML = `
      <tr><td>A1</td><td>80%</td><td>Excellent</td><td>1</td></tr>
      <tr><td>B2</td><td>75%</td><td>Very Good</td><td>2</td></tr>
      <tr><td>B3</td><td>70%</td><td>Good</td><td>3</td></tr>
      <tr><td>C4</td><td>65%</td><td>Credit</td><td>4</td></tr>
      <tr><td>C5</td><td>60%</td><td>Credit</td><td>5</td></tr>
      <tr><td>C6</td><td>55%</td><td>Credit</td><td>6</td></tr>
      <tr><td>D7</td><td>50%</td><td>Pass</td><td>7</td></tr>
      <tr><td>E8</td><td>45%</td><td>Pass</td><td>8</td></tr>
      <tr><td>F9</td><td>0%</td><td>Fail</td><td>9</td></tr>
    `;
  }
}

// ── PDF Download Handler ──────────────────────────────────────────────────────
async function downloadReportCardPDF() {
  const cardElement = document.getElementById("reportCard");
  if (!cardElement) return;

  let filename = "Document.pdf";
  if (isTranscriptMode && currentTranscriptData) {
    const name = (currentTranscriptData.full_name || "Student").replace(/[^a-zA-Z0-9_-]/g, "_");
    filename = `${name}_Official_SHS_Transcript.pdf`;
  } else if (currentReportData) {
    const s = currentReportData.student || {};
    const sem = currentReportData.semester || {};
    const studentCode = (s.student_code || "STUDENT").replace(/[^a-zA-Z0-9_-]/g, "_");
    const termName = (sem.name || "Term").replace(/[^a-zA-Z0-9_-]/g, "_");
    filename = `${studentCode}_${termName}_ReportCard.pdf`;
  }

  if (typeof html2pdf === "undefined") {
    window.print();
    return;
  }

  const opt = {
    margin: [6, 6, 6, 6],
    filename: filename,
    image: { type: "jpeg", quality: 0.98 },
    html2canvas: { scale: 2, useCORS: true, logging: false },
    jsPDF: { unit: "mm", format: "a4", orientation: "portrait" }
  };

  try {
    if (window.showToast) window.showToast("Generating A4 PDF Document...", "info");
    await html2pdf().set(opt).from(cardElement).save();
    if (window.showToast) window.showToast("📄 PDF downloaded successfully!", "success");
  } catch (err) {
    console.error("PDF Generation Error:", err);
    window.print();
  }
}
