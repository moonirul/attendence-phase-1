
$ErrorActionPreference = "Stop"

# ============================================
# BETOPIA ATTENDANCE INSTALLER
# ============================================

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BackendPath = Join-Path $ProjectRoot "backend"

$SleepScript = Join-Path $BackendPath "run_attendance_and_sleep.ps1"
$BatchFile = Join-Path $BackendPath "start_backend.local.bat"

$BackendTaskName = "Betopia Backend Auto Start"
$AttendanceTaskName = "Betopia Home Attendance Agent"

# ============================================
# ADMIN CHECK
# ============================================

$IsAdmin = ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent()
).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $IsAdmin) {
    throw "Please run PowerShell as Administrator."
}

# ============================================
# CHECK REQUIRED FILES
# ============================================

$RequiredFiles = @(
    (Join-Path $BackendPath "app\main.py"),
    $SleepScript,
    (Join-Path $BackendPath ".venv\Scripts\activate.bat")
)

foreach ($File in $RequiredFiles) {
    if (-not (Test-Path $File)) {
        throw "Required file not found: $File"
    }
}

# ============================================
# USER CONFIGURATION
# ============================================

Write-Host ""
Write-Host "====================================" -ForegroundColor Cyan
Write-Host " BETOPIA ATTENDANCE INSTALLER" -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan

$EmployeeName = Read-Host "Enter your ERP employee name"

if ([string]::IsNullOrWhiteSpace($EmployeeName)) {
    throw "Employee name cannot be empty."
}

if ($EmployeeName -notmatch "^[\p{L}\p{M}0-9 .'-]+$") {
    throw "Invalid employee name."
}

$AttendanceTime = Read-Host "Enter attendance time (HH:mm:ss, e.g. 14:30:00)"

try {
    $ParsedTime = [datetime]::ParseExact(
        $AttendanceTime,
        "HH:mm:ss",
        [Globalization.CultureInfo]::InvariantCulture
    )
}
catch {
    throw "Invalid time format. Use HH:mm:ss"
}

$AttendanceLabel = $ParsedTime.ToString("hh:mm tt")

# ============================================
# CREATE LOCAL BACKEND START SCRIPT
# ============================================

$BatchContent = @"
@echo off
cd /d "$BackendPath"
set "BETOPIA_EXPECTED_EMPLOYEE=$EmployeeName"
call ".venv\Scripts\activate.bat"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
"@

Set-Content -Path $BatchFile -Value $BatchContent -Encoding ASCII

Write-Host ""
Write-Host "Local backend configuration created." -ForegroundColor Green

# ============================================
# TASK SCHEDULER XML HELPER
# ============================================

$CurrentUserSid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value

function Register-XmlTask {
    param(
        [string]$Name,
        [string]$Xml
    )

    try {
        Register-ScheduledTask `
            -TaskName $Name `
            -Xml $Xml `
            -Force `
            -ErrorAction Stop | Out-Null

        Write-Host "Created/Updated: $Name" -ForegroundColor Green
    }
    catch {
        Write-Host "FAILED: $Name" -ForegroundColor Red
        throw
    }
}

# ============================================
# BACKEND AUTO START TASK
# Login + Unlock
# ============================================

$BatchXml = [Security.SecurityElement]::Escape($BatchFile)
$BackendXmlPath = [Security.SecurityElement]::Escape($BackendPath)

$BackendTaskXml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">

    <RegistrationInfo>
        <Description>Automatically start Betopia ERP attendance backend.</Description>
    </RegistrationInfo>

    <Triggers>

        <LogonTrigger>
            <Enabled>true</Enabled>
            <UserId>$CurrentUserSid</UserId>
        </LogonTrigger>

        <SessionStateChangeTrigger>
            <Enabled>true</Enabled>
            <UserId>$CurrentUserSid</UserId>
            <StateChange>SessionUnlock</StateChange>
        </SessionStateChangeTrigger>

    </Triggers>

    <Principals>
        <Principal id="Author">
            <UserId>$CurrentUserSid</UserId>
            <LogonType>InteractiveToken</LogonType>
            <RunLevel>LeastPrivilege</RunLevel>
        </Principal>
    </Principals>

    <Settings>
        <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
        <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
        <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
        <AllowHardTerminate>true</AllowHardTerminate>
        <StartWhenAvailable>true</StartWhenAvailable>
        <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
        <AllowStartOnDemand>true</AllowStartOnDemand>
        <Enabled>true</Enabled>
        <Hidden>false</Hidden>
        <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
        <Priority>7</Priority>
    </Settings>

    <Actions Context="Author">
        <Exec>
            <Command>cmd.exe</Command>
            <Arguments>/c start "" /min "$BatchXml"</Arguments>
            <WorkingDirectory>$BackendXmlPath</WorkingDirectory>
        </Exec>
    </Actions>

</Task>
"@

Register-XmlTask -Name $BackendTaskName -Xml $BackendTaskXml

# ============================================
# ATTENDANCE DAILY TASK
# ============================================

$PowerShellPath = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"

$SleepScriptXml = [Security.SecurityElement]::Escape($SleepScript)
$PowerShellXml = [Security.SecurityElement]::Escape($PowerShellPath)

$StartBoundary = (Get-Date).ToString("yyyy-MM-dd") + "T" + $AttendanceTime

$AttendanceTaskXml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">

    <RegistrationInfo>
        <Description>Wake PC and execute authorized Betopia Home Office attendance.</Description>
    </RegistrationInfo>

    <Triggers>

        <CalendarTrigger>
            <StartBoundary>$StartBoundary</StartBoundary>
            <Enabled>true</Enabled>

            <ScheduleByDay>
                <DaysInterval>1</DaysInterval>
            </ScheduleByDay>
        </CalendarTrigger>

    </Triggers>

    <Principals>
        <Principal id="Author">
            <UserId>$CurrentUserSid</UserId>
            <LogonType>InteractiveToken</LogonType>
            <RunLevel>LeastPrivilege</RunLevel>
        </Principal>
    </Principals>

    <Settings>
        <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
        <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
        <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
        <AllowHardTerminate>true</AllowHardTerminate>
        <StartWhenAvailable>true</StartWhenAvailable>
        <WakeToRun>true</WakeToRun>
        <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
        <AllowStartOnDemand>true</AllowStartOnDemand>
        <Enabled>true</Enabled>
        <Hidden>false</Hidden>
        <ExecutionTimeLimit>PT15M</ExecutionTimeLimit>
        <Priority>7</Priority>
    </Settings>

    <Actions Context="Author">
        <Exec>
            <Command>$PowerShellXml</Command>
            <Arguments>-NoProfile -ExecutionPolicy Bypass -File "$SleepScriptXml"</Arguments>
            <WorkingDirectory>$BackendXmlPath</WorkingDirectory>
        </Exec>
    </Actions>

</Task>
"@

Register-XmlTask -Name $AttendanceTaskName -Xml $AttendanceTaskXml

# ============================================
# START BACKEND IMMEDIATELY
# ============================================

Write-Host ""
Write-Host "Starting Betopia Backend..." -ForegroundColor Cyan

$BackendReady = $false
$OpenApiUrl = "http://127.0.0.1:8000/openapi.json"

# Check existing backend first
try {
    Invoke-RestMethod -Uri $OpenApiUrl -TimeoutSec 3 | Out-Null
    $BackendReady = $true

    Write-Host "Backend is already running." -ForegroundColor Green
}
catch {
    $BackendReady = $false
}

# Start backend task if not running
if (-not $BackendReady) {

    Start-ScheduledTask -TaskName $BackendTaskName

    for ($i = 0; $i -lt 30; $i++) {

        Start-Sleep -Seconds 1

        try {
            Invoke-RestMethod -Uri $OpenApiUrl -TimeoutSec 2 | Out-Null

            $BackendReady = $true
            break
        }
        catch {
            $BackendReady = $false
        }
    }
}

if ($BackendReady) {
    Write-Host "Backend started successfully!" -ForegroundColor Green
}
else {
    Write-Warning "Backend did not start within 30 seconds."
    Write-Warning "Check port 8000 and Task Scheduler."
}

# ============================================
# INSTALLATION SUMMARY
# ============================================

Write-Host ""
Write-Host "====================================" -ForegroundColor Cyan
Write-Host " INSTALLATION COMPLETED" -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan

Write-Host "Employee       : $EmployeeName"
Write-Host "Backend        : Login + Unlock + Immediate Start"
Write-Host "Attendance     : Daily at $AttendanceLabel"
Write-Host "Wake from Sleep: Enabled"
Write-Host "Backend Ready  : $BackendReady"

Write-Host ""
Write-Host "IMPORTANT:" -ForegroundColor Yellow
Write-Host "Disable the Attendance task on non-WFH days."
Write-Host "First test the complete workflow while you are present."

Write-Host ""
Write-Host "Scheduled Task Information:" -ForegroundColor Cyan

Get-ScheduledTaskInfo -TaskName $AttendanceTaskName |
    Select-Object NextRunTime, LastRunTime, LastTaskResult |
    Format-List

Write-Host "====================================" -ForegroundColor Green
