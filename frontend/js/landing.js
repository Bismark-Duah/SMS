/**
 * EduManage 360 — Enterprise Landing Page Logic
 * 100% Offline-First • Zero Cloud Latency
 */

document.addEventListener('DOMContentLoaded', () => {
  initMobileDrawer();
  initPersonaTabs();
  initTourTabs();
  initCalculator();
  initConsultationModal();
  initEduBot();
});

/* ─── 1. Mobile Navigation Drawer ──────────────────────────────── */
function initMobileDrawer() {
  const menuBtn = document.getElementById('mobileMenuBtn');
  const drawer = document.getElementById('mobileNavDrawer');
  const backdrop = document.getElementById('mobileDrawerBackdrop');
  const closeBtn = document.getElementById('drawerCloseBtn');

  if (!menuBtn || !drawer || !backdrop) return;

  function openDrawer() {
    drawer.classList.add('open');
    backdrop.classList.add('open');
    document.body.style.overflow = 'hidden';
  }

  function closeDrawer() {
    drawer.classList.remove('open');
    backdrop.classList.remove('open');
    document.body.style.overflow = '';
  }

  menuBtn.addEventListener('click', openDrawer);
  if (closeBtn) closeBtn.addEventListener('click', closeDrawer);
  backdrop.addEventListener('click', closeDrawer);

  // Close drawer on clicking any anchor link inside it
  drawer.querySelectorAll('a').forEach(link => {
    link.addEventListener('click', closeDrawer);
  });
}

/* ─── 2. Stakeholder Persona Switcher ──────────────────────────── */
function initPersonaTabs() {
  const tabs = document.querySelectorAll('.persona-tab-btn');
  const panels = document.querySelectorAll('.persona-panel');

  if (!tabs.length || !panels.length) return;

  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const targetId = tab.getAttribute('data-target');

      tabs.forEach(t => t.classList.remove('active'));
      panels.forEach(p => p.classList.remove('active'));

      tab.classList.add('active');
      const activePanel = document.getElementById(targetId);
      if (activePanel) activePanel.classList.add('active');
    });
  });
}

/* ─── 3. Interactive Live Product Tour ─────────────────────────── */
function initTourTabs() {
  const buttons = document.querySelectorAll('.tour-tab-btn');
  const panels = document.querySelectorAll('.tour-view-panel');

  if (!buttons.length || !panels.length) return;

  window.switchTourTab = function(tabKey) {
    buttons.forEach(btn => {
      const onclickAttr = btn.getAttribute('onclick') || '';
      btn.classList.toggle('active', onclickAttr.includes(tabKey));
    });
    panels.forEach(panel => {
      panel.classList.toggle('active', panel.id === `tour-${tabKey}`);
    });
  };
}

/* ─── 4. Institutional ROI Calculator ──────────────────────────── */
function initCalculator() {
  const studentRange = document.getElementById('calcStudentRange');
  const staffRange = document.getElementById('calcStaffRange');
  const studentDisplay = document.getElementById('calcStudentDisplay');
  const staffDisplay = document.getElementById('calcStaffDisplay');
  const hoursDisplay = document.getElementById('calcHoursSaved');
  const costDisplay = document.getElementById('calcCostSaved');

  if (!studentRange || !staffRange) return;

  window.updateCalculator = function() {
    const students = parseInt(studentRange.value, 10) || 650;
    const staff = parseInt(staffRange.value, 10) || 45;

    if (studentDisplay) studentDisplay.textContent = `${students.toLocaleString()} Students`;
    if (staffDisplay) staffDisplay.textContent = `${staff} Staff`;

    // Institutional formulas (hours and financial resource savings per academic term)
    const hoursSaved = Math.round(students * 0.26);
    const costSaved = Math.round(students * 6.5);

    if (hoursDisplay) hoursDisplay.textContent = `${hoursSaved.toLocaleString()} hrs`;
    if (costDisplay) costDisplay.textContent = `GHS ${costSaved.toLocaleString()}`;
  };

  studentRange.addEventListener('input', window.updateCalculator);
  staffRange.addEventListener('input', window.updateCalculator);

  window.updateCalculator();
}

/* ─── 5. Consultation / Demo Request Modal ─────────────────────── */
function initConsultationModal() {
  const modal = document.getElementById('consultationModal');
  const openBtns = document.querySelectorAll('.trigger-demo-modal');
  const closeBtn = document.getElementById('modalCloseBtn');
  const form = document.getElementById('consultationForm');
  const successMsg = document.getElementById('consultationSuccess');

  if (!modal) return;

  function openModal(e) {
    if (e) e.preventDefault();
    modal.classList.add('open');
    document.body.style.overflow = 'hidden';
  }

  function closeModal() {
    modal.classList.remove('open');
    document.body.style.overflow = '';
    if (form) form.reset();
    if (successMsg) successMsg.style.display = 'none';
    if (form) form.style.display = 'block';
  }

  openBtns.forEach(btn => btn.addEventListener('click', openModal));
  if (closeBtn) closeBtn.addEventListener('click', closeModal);

  modal.addEventListener('click', (e) => {
    if (e.target === modal) closeModal();
  });

  if (form) {
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      // Store lead locally in browser localStorage for offline durability
      const lead = {
        schoolName: document.getElementById('leadSchoolName')?.value || '',
        contactPerson: document.getElementById('leadContactPerson')?.value || '',
        phone: document.getElementById('leadPhone')?.value || '',
        region: document.getElementById('leadRegion')?.value || '',
        studentCount: document.getElementById('leadStudentCount')?.value || '',
        timestamp: new Date().toISOString()
      };

      try {
        const existingLeads = JSON.parse(localStorage.getItem('edumanage_leads') || '[]');
        existingLeads.push(lead);
        localStorage.setItem('edumanage_leads', JSON.stringify(existingLeads));
      } catch (err) {
        console.warn('Could not save lead to localStorage', err);
      }

      form.style.display = 'none';
      if (successMsg) successMsg.style.display = 'block';

      setTimeout(() => {
        closeModal();
      }, 3500);
    });
  }
}

/* ─── 6. EduBot Offline Assistant ──────────────────────────────── */
function initEduBot() {
  const KB = [
    {
      keys: ['add student', 'new student', 'enroll', 'admission', 'register'],
      answer: '🎓 <b>Student Management:</b><br/>Log in → click <b>Students</b> in the sidebar → select <b>Add New Student</b>. For CSSPS/BECE bulk batch placements, use the <b>Enrollment</b> module.'
    },
    {
      keys: ['broadsheet', 'report', 'waec', 'terminal report', 'grades'],
      answer: '📜 <b>Broadsheets & Grading:</b><br/>Go to <b>Academic & Broadsheets</b>. EduManage 360 automatically computes terminal continuous assessments (30/70 weighting) and assigns WAEC grades (A1 to F9) with 1-click printable PDF cards.'
    },
    {
      keys: ['fee', 'payment', 'momo', 'receipt', 'ledger', 'cash'],
      answer: '💰 <b>Fee Reconciliation:</b><br/>Under <b>Fees</b>, record cash or MoMo transactions with automated SMS alerts and printable receipts with audit timestamps.'
    },
    {
      keys: ['attendance', 'roll call', 'absent', 'present'],
      answer: '✅ <b>1-Tap Attendance:</b><br/>Teachers use <b>Attendance</b> to take daily roll calls in seconds. Daily tallies and automated absence SMS triggers keep parents updated.'
    },
    {
      keys: ['exeat', 'gate', 'security', 'leave'],
      answer: '🚪 <b>Exeat & Gate Control:</b><br/>Issue boarding exeat permits with verifiable QR codes that campus security can validate at the school gate.'
    },
    {
      keys: ['offline', 'internet', 'connection', 'network', 'lan'],
      answer: '📴 <b>100% Offline Capability:</b><br/>EduManage 360 runs completely offline on your campus local area network (LAN) using high-performance SQLite WAL technology. No internet connection is required.'
    },
    {
      keys: ['demo', 'sandbox', 'test', 'try'],
      answer: '🚀 <b>Live Demo Sandbox:</b><br/>Click <b>Explore Live Demo</b> in the header or hero to preview real student broadsheets, fee ledgers, and institutional analytics.'
    },
    {
      keys: ['hello', 'hi', 'hey', 'start', 'help'],
      answer: '👋 Hello! I am <b>EduBot</b>, your offline institutional guide. Ask me about student admissions, WAEC broadsheets, MoMo fee reconciliation, attendance, or offline LAN setup.'
    }
  ];

  const FALLBACK = "🤔 I can help you with student enrollment, WAEC grading, fee ledgers, attendance, or offline setup. Or click <a href='auth.html'><b>School Portal</b></a> to log in.";

  function findAnswer(text) {
    const t = text.toLowerCase();
    for (const entry of KB) {
      if (entry.keys.some(k => t.includes(k))) return entry.answer;
    }
    return FALLBACK;
  }

  const toggle = document.getElementById('edubot-toggle');
  const win = document.getElementById('edubot-window');
  const msgs = document.getElementById('bot-messages');
  const input = document.getElementById('bot-input');
  const sendBtn = document.getElementById('bot-send');
  const quickRep = document.getElementById('quick-replies');

  if (!toggle || !win || !msgs || !input) return;

  let opened = false;
  const QUICK = ['WAEC Broadsheets', 'Record MoMo Fee', 'Take Attendance', 'Offline LAN Info'];

  function appendMsg(html, role) {
    const div = document.createElement('div');
    div.className = `bot-msg ${role}`;
    div.innerHTML = html;
    msgs.appendChild(div);
    msgs.scrollTop = msgs.scrollHeight;
  }

  function buildQuickReplies() {
    if (!quickRep) return;
    quickRep.innerHTML = '';
    QUICK.forEach(q => {
      const btn = document.createElement('button');
      btn.className = 'qr-btn';
      btn.textContent = q;
      btn.onclick = () => sendMessage(q);
      quickRep.appendChild(btn);
    });
  }

  function sendMessage(text) {
    const msg = text.trim();
    if (!msg) return;
    appendMsg(msg, 'user');
    input.value = '';
    if (quickRep) quickRep.innerHTML = '';

    setTimeout(() => {
      appendMsg(findAnswer(msg), 'bot');
      buildQuickReplies();
    }, 400);
  }

  toggle.addEventListener('click', () => {
    opened = !opened;
    win.classList.toggle('open', opened);
    toggle.classList.toggle('open', opened);
    toggle.textContent = opened ? '✕' : '💬';
    if (opened && msgs.children.length === 0) {
      appendMsg('👋 Welcome to <b>EduManage 360</b>. How can I assist your school administration today?', 'bot');
      buildQuickReplies();
    }
  });

  if (sendBtn) sendBtn.addEventListener('click', () => sendMessage(input.value));
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter') sendMessage(input.value);
  });
}
