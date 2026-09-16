# EduManage 360 — Frontend Security Architecture & Server Boundary Specification

## 1. Executive Summary
This document audits client-side security assumptions across the EduManage 360 frontend application. It codifies the architectural principle that **the backend server is the sole authoritative security boundary**. Client-side UI affordances (e.g. hiding buttons, filtering navigation links, or checking `localStorage.getItem('userRole')`) serve exclusively as User Experience (UX) optimizations, never as security access controls.

---

## 2. Audit Findings & Threat Analysis

| Client-Side Mechanism | UX Purpose | Security Risk if Unchecked | Backend Security Enforcement |
| :--- | :--- | :--- | :--- |
| **Hidden Navigation / Buttons** (`display: none` / conditional DOM rendering) | Simplifies interface for non-administrative users (teachers, parents). | Attacker inspects DOM or submits direct API requests. | All API routes (`/api/users`, `/api/fees`, `/api/settings`, etc.) enforce dependency role checks (`_is_admin`, `require_super_admin`). |
| **Local Storage `userRole`** | Determines sidebar styling and active view persona. | Tampering with `localStorage.setItem('userRole', 'super_admin')`. | Backend verifies cryptographic JWT signature and database roles. Client tampering only modifies local CSS before any API call is rejected with HTTP 403. |
| **Client-Supplied `school_id`** (`X-School-Id` or query param) | Allows Super-Admin to switch active school view. | Tenant user attempts to access another school by altering `school_id` in localStorage. | Backend tenant isolation middleware and dependencies strictly force `current_user.school_id` for non-superadmin users. Untrusted tenant overrides are discarded. |
| **Page Guard (`guard.js` `PAGE_ROLES`)** | Redirects unauthorized users from opening admin HTML files directly. | Direct browser URL navigation to `/users.html`. | Even if an unauthorized user views the static HTML, all backend endpoints fetching data return 401/403, displaying no data. |

---

## 3. Automated Global Fetch Interception (`guard.js`)
To guarantee predictable behavior across all 37+ frontend views, `frontend/js/guard.js` installs a transparent, non-intrusive global `window.fetch` interceptor:

1. **Automatic Header Injection**:
   - Every outbound request targeting an `/api/` endpoint automatically receives `Authorization: Bearer <token>` and `X-School-Id` if present in session storage.
2. **Global HTTP 401 Unauthorized Interceptor**:
   - Triggers when an access token expires, the user's password is changed elsewhere, or session is terminated.
   - Cleanses local and session storage caches.
   - Redirects cleanly to `auth.html?msg=Session%20expired` without recursive redirect loops.
3. **Global HTTP 403 Forbidden Interceptor**:
   - Triggers when an authenticated user attempts an action outside their role privileges or tenant boundary.
   - Alerts user with a non-disruptive, user-friendly "Access Denied" notification instead of causing script errors.
