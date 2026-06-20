# Chapter 6: Developer Setup & Operations Manual

## 6.1 Backend Development Setup

The MedSync backend is built using Python 3.12+ and the Django Web Framework (v4.2+). The local setup uses SQLite for development and Postgres for production.

### 6.1.1 Local Installation Steps
1. Navigate to the backend workspace directory:
   ```bash
   cd medsync-backend
   ```
2. Create and activate a Python virtual environment:
   ```bash
   python -m venv .venv
   # On Windows (PowerShell):
   .venv\Scripts\Activate.ps1
   # On macOS/Linux:
   source .venv/bin/activate
   ```
3. Install the required local and test dependencies:
   ```bash
   pip install -r requirements-local.txt
   ```
4. Perform database migrations to create the SQLite schema:
   ```bash
   python manage.py migrate
   ```
5. Run the development server:
   ```bash
   python manage.py runserver
   ```
   The API will be live on `http://localhost:8000/api/v1/`.

### 6.1.2 Backend Environment Configuration (`.env`)
Create a `.env` file in the `medsync-backend/` root directory by copying `.env.example`:
```bash
cp .env.example .env
```

Key variables to configure:

| Variable | Default | Purpose |
|---|---|---|
| `DEBUG` | `True` | Enable debug mode (set `False` in production) |
| `ENV` | `development` | Runtime environment (`development` / `production`) |
| `SECRET_KEY` | — | Django secret key (required; long random string) |
| `FIELD_ENCRYPTION_KEY` | — | AES key for PHI field-level encryption |
| `AUDIT_LOG_SIGNING_KEY` | — | HMAC key for tamper-evident audit log chain |
| `DATABASE_URL` | PostgreSQL URI | Use `sqlite:///db.sqlite3` for local dev |
| `BREAK_GLASS_WINDOW_MINUTES` | `15` | Duration of break-glass emergency access window |
| `ADMIN_URL` | `admin/` | Non-guessable Django admin path (required in production) |
| `SENTRY_DSN` | _(blank)_ | Optional Sentry error tracking DSN |
| `WEBAUTHN_RP_ID` | `localhost` | Passkey relying party domain |
| `WEBAUTHN_ORIGIN` | `http://localhost:3000` | Passkey allowed origin (must match frontend URL) |

> **Email:** By default, emails (OTP codes, password resets) print to the console log. To deliver real email, set `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend` and configure SMTP credentials in `.env` (Mailtrap, SendGrid, Mailgun, or Gmail App Password are all supported — see `.env.example` for templates).

---

## 6.2 Frontend Development Setup

The frontend is a modern SPA/SSR web application constructed with Next.js 16 (App Router), React 19, and Tailwind CSS 4.

### 6.2.1 Installation Steps
1. Navigate to the frontend directory:
   ```bash
   cd medsync-frontend
   ```
2. Install npm packages:
   ```bash
   npm install
   ```
3. Create a local environment file:
   ```bash
   cp .env.example .env
   ```
   Ensure the following parameter points to the active backend API:
   ```env
   NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
   ```
4. Start the frontend development server:
   ```bash
   npm run dev
   ```
   Open `http://localhost:3000` in the browser to interact with the application.

---

## 6.3 Database Seeding & Custom Management Commands

MedSync includes custom Django management commands under `medsync-backend/core/management/commands/` to automate database initialization:

- **Seed Development Data:**
  ```bash
  python manage.py setup_dev
  ```
  This command seeds the database with mock clinics (Korle Bu, Komfo Anokye), test users for all 10 roles, wards, beds, departments, and active patients.
- **Generate TOTP Code for Dev Accounts:**
  ```bash
  python manage.py dev_totp_code --email doctor@korlebu.org
  ```
  Retrieves the current active 6-digit MFA OTP for a development login session.
- **Enable MFA Globally:**
  ```bash
  python manage.py enable_mfa
  ```
  Forces MFA enforcement flag activation for all clinician users.
- **Configure Super Admin Projection:**
  ```bash
  python manage.py manage_superadmin_access --grant --admin superadmin@medsync.gov --hospital-code KBTH
  ```
  Authorizes a super admin profile access to view a target hospital's database context.

---

## 6.3.1 Interactive API Documentation (Swagger / ReDoc)

MedSync exposes an OpenAPI 3.1 schema via `drf-spectacular`. Once the backend server is running, open:

- **Swagger UI:** `http://localhost:8000/api/v1/docs/`
- **ReDoc:** `http://localhost:8000/api/v1/redoc/`
- **Raw OpenAPI JSON:** `http://localhost:8000/api/v1/schema/`

---

## 6.4 Verification & Testing Suites

To ensure database schema constraints and clinical rules function correctly, the codebase includes comprehensive unit, integration, and E2E test suites.

### 6.4.1 Running Backend Tests (Pytest)
Django tests verify multi-tenancy isolation rules, rate limiting, and password recovery states:
```bash
cd medsync-backend
python -m pytest api/tests/ -v
```

### 6.4.2 Running Frontend Tests (Vitest)
Unit tests verify React components, state changes, and client routing protections:
```bash
cd medsync-frontend
npm run test
```

### 6.4.3 End-to-End Testing (Playwright)
E2E tests verify complete workflows (login, MFA bypass, cross-facility patient registration, break-glass requests). 

*Prerequisites: Both backend and frontend servers must be running locally in test modes.*
```bash
cd medsync-frontend
# Install playwright browser engines
npx playwright install
# Run E2E specs
npm run test:e2e
```
