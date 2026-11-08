# Betopia ERP Attendance Adapter — Phase 1

Phase 1 provides a local FastAPI service, a Next.js control panel, a visible Playwright browser, manual ERP authentication, and read-only DOM inspection.

**It does not submit attendance, click punch buttons, store ERP credentials, bypass MFA, or claim that URL changes prove authentication.**

## Requirements

- Python 3.11+
- Node.js 20+
- Docker Desktop (for PostgreSQL; database is not yet used in Phase 1)
- Windows, macOS, or Linux desktop for visible manual browser login

## 1. Backend setup

From the repository root:

```bash
cd backend
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

macOS/Linux activation:

```bash
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Keep this terminal running. The browser profile is stored in `backend/.browser-profile/` and is ignored by Git. Do not share it; it may contain authenticated session data.

## 2. Frontend setup

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000.

## 3. Start PostgreSQL (optional in Phase 1)

Copy `.env.example` to `.env`, set a strong unique password, then run:

```bash
docker compose up -d postgres
```

Phase 1 does not yet write application data to PostgreSQL. Database models and migrations arrive in a later phase.

## 4. Manual login and inspection

1. Click **Open ERP login**.
2. A visible Chromium window opens at the Betopia ERP login page.
3. Complete username/password and Microsoft Entra ID MFA manually.
4. Return to the dashboard and click **Inspect current page**.
5. Review the returned JSON report. It captures visible button candidates, input labels/attributes, status-like DOM elements, page title/URL and possible session-expiration text.
6. Save the report locally if needed, but redact employee identifiers and personal data before sharing it.

The inspection report is evidence for selector design, not a verified attendance map. Accessible names are approximated from visible text/ARIA attributes; Phase 2 will review actual DOM and establish robust accessible locators.

## API

- `GET /health`
- `POST /api/erp/session/start` — body `{}`; opens visible browser
- `GET /api/erp/session/status` — URL-based authentication hint only
- `POST /api/erp/dashboard/inspect` — read-only DOM inspection
- `POST /api/erp/session/stop`

API docs: http://localhost:8000/docs

## Security notes

- Run the backend bound to `127.0.0.1`; do not expose it publicly.
- No password or MFA input is collected by this app.
- Never commit `.browser-profile/`, `.env`, screenshots or raw inspection reports.
- The browser profile is sensitive. Use a dedicated OS account/device where practical.
- Only use an ERP account and actions you are authorized to access.
- The current API is intended for a single-user local development environment, not multi-user production deployment.

## Phase 1 limitations

- Authentication is not yet verified from ERP-specific DOM evidence.
- Employee identity, attendance schedule, presence, work mode and duplicate records are not detected.
- No punch-in/punch-out action exists.
- No scheduler, notifications, audit database, or real ERP integration claim is made.
- The session uses a persistent local browser profile to preserve manual login state; close the session when finished.

## Next phase

Use a real authorized account to produce a sanitized inspection report. Phase 2 will use that evidence to implement dashboard/session detection and stable selectors. Do not send passwords, MFA codes, cookies, storage-state files, or the browser profile.
