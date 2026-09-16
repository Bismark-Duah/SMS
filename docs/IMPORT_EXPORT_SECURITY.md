# Enterprise Import and Export Security & Workflow Specification

## 1. Threat Model & Overview
Import and export workflows are high-risk threat vectors in multi-tenant educational ERP systems. In an offline-first deployment, schools process external data files from government agencies (e.g. CSSPS placement lists, WAEC registers, GES master files) and export ledgers, broadsheets, and financial summaries into desktop spreadsheet engines (Microsoft Excel, LibreOffice Calc, Apple Numbers, Google Sheets).

This document outlines the enterprise security controls implemented in **Prompt 27** across `backend/app/services/import_export_service.py` and associated routing modules.

---

## 2. Core Defenses Implemented

### 2.1 CSV / Formula Injection Defense (CWE-1236)
- **Vulnerability:** When a CSV export contains cell data starting with `=`, `+`, `-`, `@`, `\t`, or `\r`, spreadsheet engines interpret the string as a dynamic executable formula or DDE (Dynamic Data Exchange) macro, enabling arbitrary code execution or local file exfiltration.
- **Sanitization Mechanism:**
  - `sanitize_csv_cell(val)` inspects string values.
  - If a cell's stripped value begins with any dangerous formula trigger (`=`, `+`, `-`, `@`, `\t`, `\r`), it is safely prefixed with a single quote `'`.
  - Spreadsheet engines render `'=SUM(A1:B1)` as the literal text `=SUM(A1:B1)` rather than executing it.
  - All report exports (`/api/reports/export-students`, `/api/reports/class-summary/{id}/export`, `/api/reports/financial-summary/export`, `/api/reports/broadsheet-csv/{id}`) and internal matrix generators enforce cell sanitization through `generate_safe_csv_content` and `sanitize_row_for_export`.

### 2.2 File Upload & Encoding Safety
- **Size Limit:** Uniformly capped at 10MB (`10 * 1024 * 1024` bytes) across all import routes (`/api/students/import-csv`, `/api/auth/import-users-csv`, `/api/cssps/import-csv`).
- **Binary/Executable Rejection:** Inspects the initial 2KB byte header for null bytes (`\x00`), rejecting masqueraded binary executables, PE/ELF payloads, or corrupt byte streams before string decoding.
- **Multi-Encoding Decoding:** Automatically handles:
  1. `utf-8-sig` (strips UTF-8 Byte Order Marks produced by Windows Excel).
  2. Standard `utf-8`.
  3. `latin-1` (graceful ISO-8859-1 fallback for older regional institution archives).
- **Extension & MIME Validation:** Rejects non-`.csv` files with explicit HTTP 400 bad request responses.

### 2.3 Path Traversal Prevention (CWE-22)
- Filenames used in `Content-Disposition: attachment; filename="..."` headers or stored upload directories are scrubbed through `sanitize_filename()`.
- Directory separators (`/`, `\`), null bytes (`\0`), and path traversal tokens (`../`, `..\`) are stripped.
- Filenames are normalized to safe alphanumeric, hyphen, dot, and underscore sequences.

### 2.4 Multi-Tenant Boundary Enforcement
- School-specific imports (`/api/students/import-csv`, `/api/cssps/import-csv`) automatically force `school_id` from the authenticated caller's JWT token via `get_school_id(current_user)`.
- User imports (`/api/auth/import-users-csv`) prohibit non-super-admins from targeting other schools or assigning administrative (`super_admin`, `admin`, `headmaster`) privileges via CSV rows.
- Data exports (`/api/reports/*`) strictly filter all queries by `Student.school_id == school_id`, preventing cross-tenant leakage.

### 2.5 Granular Error Reporting & Transaction Safety
- Import batch processing uses SQLAlchemy nested transactions (`with db.begin_nested():`) on each row.
- If an individual row fails validation or encounters duplicate keys, only that row is rolled back while valid rows succeed.
- Returns structured audit responses:
  ```json
  {
    "status": "partial_success",
    "imported": 42,
    "skipped": 3,
    "total": 45,
    "errors": [
      "Row 12: Missing username",
      "Row 27: Student with code 'STU-10293' already exists"
    ]
  }
  ```
