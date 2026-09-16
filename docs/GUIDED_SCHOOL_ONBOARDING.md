# Guided School Onboarding Subsystem (Prompt 26)

## 1. Overview & Philosophy
New school proprietors, headmasters, and administrative clerks often face cognitive overload when navigating an enterprise School Management System for the first time. Without clear directional guidance, critical operational prerequisites—such as establishing an active academic term before enrolling students or defining grading standards before entering marks—are frequently skipped, leading to user confusion and orphan records.

The **Guided School Onboarding Subsystem** introduces progressive, milestone-driven guidance:
* Reduces initial cognitive load by providing a step-by-step roadmap.
* Preserves all business rules and tenant isolation boundaries without hardcoded bypasses.
* Remains 100% offline-first, functioning without external cloud dependencies.

---

## 2. The 10 Core Onboarding Milestones

| Step | Milestone | Target Area | Requirement & Business Value |
| :---: | :--- | :--- | :--- |
| **1** | **School Profile & Details** | `settings.html` | Official name, abbreviation code, phone, address, and crest for report cards and official receipts. |
| **2** | **Admin Account & Security** | `users.html` | Verified admin email and password security for offline disaster recovery and system integrity. |
| **3** | **Academic Year & Active Term** | `academic.html` | Current academic year (e.g. 2026/2027) with an active semester/term to anchor attendance, scores, and billing. |
| **4** | **Class Sections & Streams** | `classes.html` | Operating streams (e.g., Form 1 Gold, Class 1A) to receive student assignments. |
| **5** | **Curriculum & Active Subjects** | `subjects.html` | Accredited core and elective subjects mapped to the school's operating mode (SHS_ONLY, BASIC_ONLY, COMBINED). |
| **6** | **Staff & Teacher Accounts** | `users.html` | Provisioning faculty logins for subject masters, form masters, and accountants. |
| **7** | **Student Enrollment** | `students.html` | Adding initial student records manually or via CSV batch import. |
| **8** | **Fee Schedule & Billing** | `fees.html` | Term fee structures and student bill generation to activate ledger tracking and payment receipts. |
| **9** | **Grading Scale & SBA Weights** | `settings.html` | Continuous Assessment (SBA 30% / Exam 70%) and grading standards (WAEC / GES) setup. |
| **10** | **Role & Privilege Boundaries** | `users.html` | Least-privilege role assignment and permission verification. |

---

## 3. Architecture & API Contracts

### `GET /api/onboarding/status`
Returns real-time milestone completion status, overall completion percentage, next recommended step, and actionable guidance for the authenticated school admin.

```json
{
  "school_id": 1,
  "school_name": "Antoa Senior High School",
  "school_code": "ANTOA-SHS",
  "school_mode": "SHS_ONLY",
  "completed_count": 6,
  "total_steps": 10,
  "overall_progress_percent": 60,
  "is_complete": false,
  "is_dismissed": false,
  "next_step": {
    "id": "students",
    "title": "Student Enrollment",
    "description": "Enrol students individually or import an initial class roster via CSV.",
    "href": "students.html",
    "is_completed": false,
    "hint": "Add initial students or use CSV bulk import to seed records."
  },
  "milestones": [ ... ]
}
```

### `POST /api/onboarding/dismiss`
Stores user preference in school settings (`onboarding_banner_dismissed = true`) to collapse or hide the dashboard checklist once the administrator is comfortable.

### `POST /api/onboarding/reset`
Restores the checklist visibility at any time from General Settings or user profile.

---

## 4. Frontend Experience
* Embedded directly into `dashboard.html` via `js/dashboard.js`.
* Features an animated progress bar, next recommended step callout, and an expandable 10-step milestones grid.
* When 100% complete, celebrates full school operational readiness.
