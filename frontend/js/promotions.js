const API_BASE = window.API_BASE || (window.location.origin.includes('http') ? (window.location.origin + '/api') : 'http://127.0.0.1:8000/api');

const token = localStorage.getItem('accessToken') || localStorage.getItem('token');
if (!token) {
  window.location.href = 'auth.html';
}

function getHeaders(headers = {}) {
  const h = { ...headers };
  if (token) h['Authorization'] = `Bearer ${token}`;
  return h;
}

window.switchTab = function(mode) {
    const promoteBtn = document.getElementById('tabPromote');
    const graduateBtn = document.getElementById('tabGraduate');
    const promoteForm = document.getElementById('promoteForm');
    const graduateForm = document.getElementById('graduateForm');
    
    if (mode === 'promote') {
        promoteBtn.classList.add('active');
        graduateBtn.classList.remove('active');
        promoteForm.style.display = 'grid';
        graduateForm.style.display = 'none';
    } else {
        promoteBtn.classList.remove('active');
        graduateBtn.classList.add('active');
        promoteForm.style.display = 'none';
        graduateForm.style.display = 'grid';
    }
};

let classesList = [];
let currentCandidates = [];

async function init() {
    await loadClasses();
    setupListeners();
}

async function loadClasses() {
    try {
        const res = await fetch(`${API_BASE}/classes/`, { headers: getHeaders() });
        classesList = await res.json();

        const options = '<option value="">Select Class Section...</option>' + 
            classesList.map(c => `<option value="${c.id}">${c.name}</option>`).join('');

        document.getElementById('promote_source_class').innerHTML = options;
        document.getElementById('promote_target_class').innerHTML = options;
        document.getElementById('graduate_source_class').innerHTML = options;
    } catch (e) {
        console.error("Error loading classes:", e);
    }
}

function setupListeners() {
    // Source class change in Promotions tab
    document.getElementById('promote_source_class').addEventListener('change', async (e) => {
        const classId = e.target.value;
        await loadStudentsForPromotion(classId);
    });

    // Class change in Graduation tab
    document.getElementById('graduate_source_class').addEventListener('change', async (e) => {
        const classId = e.target.value;
        await loadStudentsForGraduation(classId);
    });

    // Promote Form submit
    document.getElementById('promoteForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const sourceClassId = document.getElementById('promote_source_class').value;
        const targetClassId = document.getElementById('promote_target_class').value;
        const incrementForm = document.getElementById('increment_form').checked;

        if (!sourceClassId) {
            alert("Please select a source class section.");
            return;
        }

        if (sourceClassId === targetClassId) {
            alert("Source and Target Class Sections cannot be the same.");
            return;
        }

        const checkedBoxes = document.querySelectorAll('#promoteStudentsList input[type="checkbox"]:checked');
        const studentIds = Array.from(checkedBoxes).map(cb => parseInt(cb.value));

        if (studentIds.length === 0) {
            alert("Please select at least one student to promote.");
            return;
        }

        const targetClassName = classesList.find(c => String(c.id) === String(targetClassId))?.name || "target class";

        if (!confirm(`Are you sure you want to promote ${studentIds.length} selected students to ${targetClassName}?`)) {
            return;
        }

        const payload = {
            student_ids: studentIds,
            target_class_section_id: parseInt(targetClassId),
            increment_form: incrementForm
        };

        try {
            const res = await fetch(`${API_BASE}/promotions/promote`, {
                method: 'POST',
                headers: getHeaders({ 'Content-Type': 'application/json' }),
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                const data = await res.json();
                alert(data.message || `Successfully promoted ${studentIds.length} students.`);
                await loadStudentsForPromotion(sourceClassId);
            } else {
                const data = await res.json();
                alert(`Failed to promote: ${data.detail || 'Server error'}`);
            }
        } catch (err) {
            console.error(err);
            alert("Network error executing promotion.");
        }
    });

    // Graduate Form submit
    document.getElementById('graduateForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const sourceClassId = document.getElementById('graduate_source_class').value;

        const checkedBoxes = document.querySelectorAll('#graduateStudentsList input[type="checkbox"]:checked');
        const studentIds = Array.from(checkedBoxes).map(cb => parseInt(cb.value));

        if (studentIds.length === 0) {
            alert("Please select at least one candidate for graduation.");
            return;
        }

        if (!confirm(`Are you sure you want to graduate ${studentIds.length} selected students? This will set their status as GRADUATED and deactivate their enrolment.`)) {
            return;
        }

        const payload = {
            student_ids: studentIds
        };

        try {
            const res = await fetch(`${API_BASE}/promotions/graduate`, {
                method: 'POST',
                headers: getHeaders({ 'Content-Type': 'application/json' }),
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                const data = await res.json();
                alert(data.message || `Successfully graduated ${studentIds.length} students.`);
                await loadStudentsForGraduation(sourceClassId);
            } else {
                const data = await res.json();
                alert(`Failed to graduate: ${data.detail || 'Server error'}`);
            }
        } catch (err) {
            console.error(err);
            alert("Network error executing graduation.");
        }
    });
}

async function loadStudentsForPromotion(classId) {
    const listContainer = document.getElementById('promoteStudentsList');
    if (!classId) {
        listContainer.innerHTML = '<p style="color: #666; text-align: center; margin-top: 20px;">Select a source class to view students.</p>';
        return;
    }

    listContainer.innerHTML = '<p style="text-align: center; margin-top: 20px;">Loading candidates...</p>';

    try {
        const res = await fetch(`${API_BASE}/promotions/candidates/${classId}`, { headers: getHeaders() });
        if (!res.ok) throw new Error("Failed to fetch promotion candidates");
        currentCandidates = await res.json();

        if (currentCandidates.length === 0) {
            listContainer.innerHTML = '<p style="color: #666; text-align: center; margin-top: 20px;">No active students found in this class section.</p>';
            return;
        }

        listContainer.innerHTML = currentCandidates.map(s => {
            const isRecPromote = s.recommendation === "Promoted" || s.recommendation === "Pending";
            const isRepeated = s.recommendation === "Repeated";

            let badgeHtml = "";
            if (isRepeated) {
                badgeHtml = '<span style="background:rgba(239,68,68,0.2); color:#ef4444; border:1px solid #ef4444; padding:2px 8px; border-radius:10px; font-size:0.75rem; font-weight:700;">⚠️ Repeat Recommended</span>';
            } else if (s.recommendation === "Promoted") {
                badgeHtml = '<span style="background:rgba(34,197,94,0.2); color:#22c55e; border:1px solid #22c55e; padding:2px 8px; border-radius:10px; font-size:0.75rem; font-weight:700;">🟢 Recommended</span>';
            } else {
                badgeHtml = '<span style="background:rgba(148,163,184,0.2); color:#94a3b8; border:1px solid #94a3b8; padding:2px 8px; border-radius:10px; font-size:0.75rem; font-weight:700;">Pending</span>';
            }

            return `
                <div class="student-checkbox-item" data-rec="${s.recommendation}">
                    <input type="checkbox" id="promote_s_${s.id}" value="${s.id}" ${isRecPromote ? 'checked' : ''} />
                    <label for="promote_s_${s.id}" style="flex:1; display:flex; justify-content:space-between; align-items:center; cursor:pointer; margin:0;">
                        <div>
                            <strong>${escapeHtml(s.full_name)}</strong>
                            <div style="font-size:0.78rem; opacity:0.7;">Code: ${s.student_code} · Form ${s.form}</div>
                        </div>
                        <div>${badgeHtml}</div>
                    </label>
                </div>
            `;
        }).join('');
    } catch (err) {
        console.error(err);
        listContainer.innerHTML = '<p style="color: red; text-align: center; margin-top: 20px;">Error loading promotion candidates.</p>';
    }
}

async function loadStudentsForGraduation(classId) {
    const listContainer = document.getElementById('graduateStudentsList');
    if (!classId) {
        listContainer.innerHTML = '<p style="color: #666; text-align: center; margin-top: 20px;">Select a graduating class to view candidates.</p>';
        return;
    }

    listContainer.innerHTML = '<p style="text-align: center; margin-top: 20px;">Loading graduating candidates...</p>';

    try {
        const res = await fetch(`${API_BASE}/promotions/candidates/${classId}`, { headers: getHeaders() });
        if (!res.ok) throw new Error("Failed to fetch candidates");
        const students = await res.json();

        if (students.length === 0) {
            listContainer.innerHTML = '<p style="color: #666; text-align: center; margin-top: 20px;">No active students found in this class section.</p>';
            return;
        }

        listContainer.innerHTML = students.map(s => `
            <div class="student-checkbox-item">
                <input type="checkbox" id="graduate_s_${s.id}" value="${s.id}" checked />
                <label for="graduate_s_${s.id}" style="flex:1; display:flex; justify-content:space-between; align-items:center; cursor:pointer; margin:0;">
                    <div>
                        <strong>${escapeHtml(s.full_name)}</strong>
                        <div style="font-size:0.78rem; opacity:0.7;">Code: ${s.student_code} · Form ${s.form}</div>
                    </div>
                    <span style="background:rgba(124,58,237,0.2); color:#a78bfa; border:1px solid #7c3aed; padding:2px 8px; border-radius:10px; font-size:0.75rem; font-weight:700;">🎓 Graduation Candidate</span>
                </label>
            </div>
        `).join('');
    } catch (err) {
        console.error(err);
        listContainer.innerHTML = '<p style="color: red; text-align: center; margin-top: 20px;">Error loading graduation candidates.</p>';
    }
}

function filterSelection(mode) {
    const checkboxes = document.querySelectorAll('#promoteStudentsList .student-checkbox-item');
    checkboxes.forEach(item => {
        const cb = item.querySelector('input[type="checkbox"]');
        const rec = item.getAttribute('data-rec');
        if (mode === 'recommended') {
            cb.checked = (rec === 'Promoted' || rec === 'Pending');
        } else if (mode === 'all') {
            cb.checked = true;
        } else if (mode === 'none') {
            cb.checked = false;
        }
    });
}

function escapeHtml(str) {
    return str ? String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;") : '';
}

init();
