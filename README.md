# Betopia ERP Attendance Adapter

## Installation (New Windows PC)

### Step 1: Clone Repository

```powershell
git clone https://github.com/moonirul/attendence-phase-1.git
cd attendence-phase-1
```

### Step 2: Setup Python Environment

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
```

### Step 3: First-Time ERP Login & MFA Setup

1. Start the backend:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

2. Open Swagger:

http://127.0.0.1:8000/docs

3. Execute `POST /api/erp/session/start`.
4. A browser window will open.
5. Log in to Betopia ERP using your own credentials.
6. Complete MFA verification manually.
7. Keep the ERP browser session open.

### Step 4: Test First Attendance

1. Confirm that you are authorized to work from home.
2. Set the first attendance time to **current time + 5 minutes**.
3. Open a new PowerShell window as Administrator.
4. Run:

```powershell
cd attendence-phase-1
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\install_tasks.ps1
```

5. Enter your ERP employee name.
6. Enter the attendance time in `HH:mm:ss` format.
7. Wait for the scheduled Check-In and verify the result.

### Step 5: Daily Setup / Change Attendance Time

From the project root, open PowerShell as Administrator:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\install_tasks.ps1
```

Enter:
- ERP employee name
- Desired daily attendance time (`HH:mm:ss`)

The installer updates the scheduled tasks.

### API Documentation

http://127.0.0.1:8000/docs

**Important:**
- Complete ERP login and MFA manually.
- Keep the PC connected to the internet.
- Disable the Attendance task on non-WFH days.
- Verify successful Check-In in Betopia ERP.
- The PC enters Sleep only after successful attendance verification.
- Never share your ERP credentials or browser profile.