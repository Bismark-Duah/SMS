# EduManage 360 — Production CORS Hardening Specification

## Overview
Cross-Origin Resource Sharing (CORS) is configured to enforce strict tenant isolation, environment-specific origin boundaries, and W3C credential protection.

## Environment-Specific Configuration

### 1. Production Mode (`ENVIRONMENT=production`)
- **Strict Wildcard Prohibition**: Wildcard origins (`*`) are prohibited by security policy. Any attempt to start or configure the application in production mode with `CORS_ORIGINS=*` (or containing `*`) triggers a fail-secure `ValueError` and prevents startup.
- **Default Production Origins**: If `CORS_ORIGINS` is not explicitly set, the backend defaults to authorized production domains:
  - `https://smsghana.onrender.com`
  - `https://smsgh.onrender.com`
- **Credentials Policy**: `allow_credentials=True` is enabled strictly for verified, explicit origin lists.
- **Methods**: Explicitly allows `GET, POST, PUT, PATCH, DELETE, OPTIONS`.
- **Headers Exposed**: Exposes correlation tracing `X-Request-ID` and download header `Content-Disposition`.
- **Preflight Cache**: `max_age=600` (10 minutes) to minimize preflight round-trips.

### 2. Development & Test Mode (`ENVIRONMENT=development`)
- **Local Dev Origins**: Defaults to trusted local loopback ports:
  - `http://localhost:8000`, `http://127.0.0.1:8000` (FastAPI / Swagger)
  - `http://localhost:3000`, `http://127.0.0.1:3000` (React / Next.js)
  - `http://localhost:5173`, `http://127.0.0.1:5173` (Vite)
  - `http://localhost:5500`, `http://127.0.0.1:5500` (Live Server)
- **Wildcard Handling**: If `CORS_ORIGINS=*` is explicitly set in development, `allow_credentials` is automatically set to `False` to prevent browser security exceptions under the W3C CORS specification.

## Configuration Guide (`.env`)
```bash
# Production Example:
ENVIRONMENT=production
CORS_ORIGINS=https://smsghana.onrender.com,https://app.edumanage360.com

# Local Development Example:
ENVIRONMENT=development
CORS_ORIGINS=http://localhost:8000,http://localhost:5173
```
