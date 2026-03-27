# MedSync E2E Test Suite

Playwright end-to-end tests for role-based access, workflows, and authorization.

## Structure

- **auth/** – Login, logout, session, protected redirect, MFA
- **roles/** – Sidebar and dashboard visibility per role
- **security/** – Route authorization (forbidden URLs)
- **workflows/** – Role workflows (receptionist, nurse, doctor, lab tech, hospital_admin, super_admin) and handoffs
- **scoping/** – Hospital/facility scoping
- **ux/** – Loading, empty, validation, error states
- **network/** – API request/response assertions
- **pages/** – Page objects (Login, Sidebar)
- **fixtures/** – Auth fixtures (`loginAs`, `getCreds`)
- **utils/** – Constants, role/nav mapping

## Run

```bash
npm run test:e2e
```

With env (copy `.env.e2e.example` to `.env.e2e` and set credentials):

```bash
# Windows PowerShell
Get-Content .env.e2e | ForEach-Object { if ($_ -match '^([^#=]+)=(.*)$') { [Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process') } }
npx playwright test

# Or set E2E_BASE_URL and E2E_*_EMAIL / E2E_*_PASSWORD in CI
```

## Projects

- `npx playwright test --project=auth`
- `npx playwright test --project=roles`
- `npx playwright test --project=workflows`
- `npx playwright test --project=all`

## Prerequisites

- Frontend: `npm run dev` (default port 3000)
- Backend: running and reachable at `NEXT_PUBLIC_API_URL`
- Test users per role with MFA disabled, or `E2E_MFA_BACKUP_CODE` set

See `docs/E2E_TEST_PLAN.md` for full architecture and CI notes.
