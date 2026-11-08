# Betopia ERP Attendance Adapter

## Project Overview

### 1. Project Objective
- Automate daily Home Office Check-In.
- Eliminate repetitive manual attendance tasks.
- Ensure timely and verified attendance.

### 2. Problem Statement
- Employees need to manually log in to Betopia ERP.
- Navigate to HRMS → Attendances → Home Attendance.
- Manually click the Check-In button every working day.
- Risk of missing or delaying attendance.

### 3. Project Motivation
- Reduce manual effort and human errors.
- Improve productivity through automation.
- Apply browser automation to a real-world ERP system.

### 4. Proposed Solution
- Automate ERP interaction using Playwright.
- Maintain an authenticated browser session.
- Perform scheduled Home Office Check-In.
- Verify attendance automatically.
- Put the PC into Sleep mode after successful Check-In.

### 5. Key Technologies
- Python
- FastAPI
- Playwright
- Windows Task Scheduler
- PowerShell

### 6. Expected Outcome
- No daily manual ERP navigation or Check-In.
- Automated and verified attendance.
- Reduced repetitive work and unnecessary PC running time.

---

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
.\backend\scripts\install_tasks.ps1
```

5. Enter your ERP employee name.
6. Enter the attendance time in `HH:mm:ss` format.
7. Wait for the scheduled Check-In and verify the result.

### Step 5: Daily Setup / Change Attendance Time

From the project root, open PowerShell as Administrator:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\backend\scripts\install_tasks.ps1
```

Enter:
- ERP employee name
- Desired daily attendance time (`HH:mm:ss`)

The installer updates the scheduled tasks.

### Step 6: Weekend Setup (Friday Off)

Friday is your weekly weekend. Disable the Attendance task on Friday so automatic Check-In does not run.

**Every Friday – Disable Attendance:**

Open PowerShell as Administrator and run:

```powershell
Disable-ScheduledTask -TaskName "Betopia Home Attendance Agent"
```

**Every Saturday – Enable Attendance:**

Run:

```powershell
Enable-ScheduledTask -TaskName "Betopia Home Attendance Agent"
```

After enabling, the daily scheduled Check-In will resume.

**Important:** Complete the initial installation before using these commands. Do not disable the Backend Auto Start task; only disable the Attendance task.

### API Documentation

http://127.0.0.1:8000/docs

**Important:**
- Complete ERP login and MFA manually.
- Keep the PC connected to the internet.
- Disable the Attendance task on non-WFH days.
- Friday is the weekly weekend; disable Attendance on Friday and enable it on Saturday.
- Verify successful Check-In in Betopia ERP.
- The PC enters Sleep only after successful attendance verification.
- Never share your ERP credentials or browser profile.