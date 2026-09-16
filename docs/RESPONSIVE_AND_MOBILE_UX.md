# Responsive & Mobile UX Architecture (Prompt 24)

## 1. Overview & Mission
EduManage 360 is an enterprise offline-first School Management System designed to be operated across the full spectrum of educational hardware:
* **Mobile Smartphones** (320px – 480px, e.g., Android Go, iPhone SE, modern flagships)
* **Tablets & Phablets** (600px – 1024px, e.g., iPad, Galaxy Tab, teacher handhelds)
* **Laptops** (1025px – 1440px)
* **Desktop Workstations & Projectors** (>= 1441px, high-density 1080p/4K administrative displays)

The Responsive UX subsystem guarantees that high-density administrative workflows remain fully functional, visually elegant, and touch-accessible without horizontal viewport blowout or text clipping, while preserving desktop visual hierarchy.

---

## 2. High-Use Workflow Audit & Responsive Hardening

| Workflow | Page | Mobile / Tablet Adaptations |
| :--- | :--- | :--- |
| **Authentication** | `auth.html` | Body allows vertical scroll on short screens/keyboards; right panel switches to fluid 100% width; input fonts set to 16px to prevent iOS Safari auto-zoom; 44px touch buttons. |
| **Dashboard** | `dashboard.html`, `index.html` | KPI cards and statistics grids scale from 4 columns to 2 on tablets (<= 1024px) and 1 column on mobile (<= 640px); chart containers scale fluidly. |
| **Sidebar Navigation** | `theme.js`, `.app-sidebar` | Off-canvas drawer (max 85vw) with 44px min-height touch targets; backdrop overlay with tap-to-dismiss; mobile hamburger button (`☰`, min 44x44px touch area) injected into sticky topbar. |
| **Student Records** | `students.html` | Action button bar wraps gracefully; filter bars stack into full-width inputs; student directory table wraps in `.table-responsive` with touch inertia. |
| **Attendance** | `attendance.html` | Date pickers and class selectors stack cleanly; quick-action buttons ("Mark All Present", "Save") wrap without overflow; student attendance list scrolls horizontally on small displays. |
| **Assessments & Marks Entry** | `results.html`, `bulk-entry.html` | Spreadsheet-like score entry matrices maintain cell readability with sticky column headers and touch scroll wrappers; numeric inputs sized for thumb entry. |
| **Fees & Billing** | `fees.html` | Summary metric cards stack; fee payment collection form collapses to single-column on mobile; payment history and receipt tables wrapped in responsive containers. |
| **Terminal Reports & Broadsheets** | `report-card.html`, `reports.html`, `broadsheet.html` | Student bio grids stack to 1 column on mobile; terminal score tables and WASSCE matrices scroll within `.table-responsive` containers; `@media print` rules preserve perfect A4 layout. |
| **Messaging & Notifications** | `messaging.html` | Recipient selection tables and SMS outbox delivery history wrapped in scrollable `.table-responsive` containers; preview modal expands to comfortable bottom-sheet. |
| **Parent Portal** | `parent-view.html` | Single-child and multi-child cards display cleanly; attendance gauge, fee balances, and latest exam summaries stack into accessible mobile cards. |

---

## 3. Responsive Breakpoint Architecture

```
┌─────────────────────────┬──────────────────────────┬────────────────────────┐
│   Mobile (<= 640px)     │   Tablet (641 - 1024px)  │   Desktop (>= 1025px)  │
├─────────────────────────┼──────────────────────────┼────────────────────────┤
│ • 1-column KPI grids    │ • 2-column KPI grids     │ • 4+ column KPI grids  │
│ • Bottom-sheet modals   │ • Standard modals        │ • Centered dialogs     │
│ • Drawer sidebar        │ • Drawer/compact sidebar │ • Fixed/pinned sidebar │
│ • 16px form inputs      │ • 14px form inputs       │ • 14px form inputs     │
│ • Wrapped topbar        │ • Flexible topbar        │ • Inline topbar        │
└─────────────────────────┴──────────────────────────┴────────────────────────┘
```

### Key Technical Safeguards:
1. **Viewport Meta Tag Coverage:**
   100% of all 35 HTML files in `frontend/` contain `<meta name="viewport" content="width=device-width, initial-scale=1.0" />`.
2. **Touch Targets (WCAG 2.5.5 / 2.5.8):**
   Interactive buttons, form controls, and navigation items enforce `min-height: 42px` (and 44px for primary triggers and hamburger buttons) for touch accessibility.
3. **Table Containment (`.table-responsive`):**
   Tables are housed within overflow containers featuring `-webkit-overflow-scrolling: touch`, horizontal scrolling, and custom styled scrollbars so wide tabular records never break page boundaries.
4. **Offline Resilience:**
   All responsive CSS rules are embedded directly in `frontend/css/styles.css` with zero external CDN dependencies, ensuring 100% functionality in offline rural school deployments.
