const API_BASE = '/api';

document.addEventListener('DOMContentLoaded', () => {
    loadStudentDropdown();
});

async function loadStudentDropdown() {
    try {
        const res = await fetch(`${API_BASE}/students/`);
        if (res.ok) {
            const students = await res.json();
            const select = document.getElementById('student_select');
            select.innerHTML = '<option value="">-- Choose Pupil / Student --</option>';
            students.forEach(s => {
                select.innerHTML += `<option value="${s.id}">${s.full_name} (${s.student_code} - ${s.school_type || 'Basic'})</option>`;
            });
        }
    } catch (err) {
        console.error('Failed to load students:', err);
    }
}

async function loadCumulativeRecord() {
    const studentId = document.getElementById('student_select').value;
    const folder = document.getElementById('cumulative-folder');

    if (!studentId) {
        folder.style.display = 'none';
        return;
    }

    try {
        const res = await fetch(`${API_BASE}/cumulative-records/${studentId}`);
        if (res.ok) {
            const data = await res.json();
            folder.style.display = 'block';

            // 1. Personal
            document.getElementById('rec-name').innerText = data.full_name;
            document.getElementById('rec-code').innerText = data.student_code;
            document.getElementById('rec-stage').innerText = `${data.school_type} (Form ${data.form || 1})`;
            document.getElementById('rec-gender-dob').innerText = `${data.gender || 'N/A'} | DOB: ${data.date_of_birth || 'N/A'}`;
            document.getElementById('rec-guardian').innerText = `${data.family_background.guardian_name || 'N/A'} (${data.family_background.phone || 'N/A'})`;
            document.getElementById('rec-family-notes').innerText = data.family_background.family_background_notes || 'No family notes recorded.';

            // 2. Scholastic
            document.getElementById('rec-avg-score').innerText = `${data.scholastic_summary.overall_average}%`;
            document.getElementById('rec-total-assessments').innerText = data.scholastic_summary.total_assessments;

            const scoresList = document.getElementById('rec-scores-list');
            if (data.scholastic_summary.scores_breakdown.length > 0) {
                scoresList.innerHTML = data.scholastic_summary.scores_breakdown.map(s => `
                    <div style="display:flex; justify-content:space-between; padding:6px 0; border-bottom:1px solid rgba(255,255,255,0.05); font-size:0.88rem;">
                        <span>${s.subject_name}</span>
                        <span><strong>${s.total_score}</strong> (${s.grade || 'N/A'})</span>
                    </div>
                `).join('');
            } else {
                scoresList.innerHTML = '<p style="font-size:0.85rem; color:var(--text-muted);">No score records available.</p>';
            }

            // 3. Attendance
            document.getElementById('rec-att-rate').innerText = data.attendance_conduct.attendance_rate;
            document.getElementById('rec-days').innerText = `${data.attendance_conduct.days_present} Present / ${data.attendance_conduct.days_absent} Absent`;

            // 4. Health
            const h = data.health_physical;
            document.getElementById('rec-height-weight').innerText = `${h.height_cm ? h.height_cm + ' cm' : 'N/A'} | ${h.weight_kg ? h.weight_kg + ' kg' : 'N/A'}`;
            document.getElementById('rec-blood').innerText = h.blood_group || 'N/A';
            document.getElementById('rec-allergies').innerText = h.allergies || h.chronic_conditions || 'None reported.';
            document.getElementById('rec-pe').innerText = h.pe_limitations || 'No physical limitations.';

            // 5. Personality
            const p = data.personality_social;
            document.getElementById('rec-traits').innerText = p.personality_traits || 'No specific traits recorded.';
            document.getElementById('rec-leadership').innerText = p.leadership_notes || 'None recorded.';
            document.getElementById('rec-observations').innerText = p.teacher_observations || 'No observations added.';

            // 6. Co-curricular
            const c = data.cocurricular_talents;
            document.getElementById('rec-clubs').innerText = c.co_curricular_activities || 'None.';
            document.getElementById('rec-hobbies').innerText = c.hobbies_talents || 'None.';
            document.getElementById('rec-awards').innerText = c.awards || 'None.';
        }
    } catch (err) {
        console.error('Failed to load cumulative record:', err);
    }
}

function printRecord() {
    window.print();
}

async function downloadCumulativeFolderPDF() {
    const studentId = document.getElementById('student_select')?.value;
    if (!studentId) {
        alert('Please select a Pupil / Student first.');
        return;
    }

    try {
        const token = localStorage.getItem('accessToken') || sessionStorage.getItem('accessToken');
        const res = await fetch(`${API_BASE}/cumulative-records/pdf/${studentId}`, {
            headers: { 'Authorization': token ? `Bearer ${token}` : '' }
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: 'Failed to generate cumulative record folder PDF' }));
            alert(`⚠️ Error: ${err.detail || 'Failed to download PDF folder'}`);
            return;
        }

        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `Cumulative_Record_Folder_Student_${studentId}.pdf`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    } catch (err) {
        console.error('Failed to download cumulative folder:', err);
        alert('Network error while generating cumulative record folder PDF.');
    }
}

