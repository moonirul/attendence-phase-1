
$ErrorActionPreference = "Stop"

# ============================================
# BETOPIA ERP ATTENDANCE INSTALLER
# ============================================

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BackendPath = Join-Path $ProjectRoot "backend"

$SleepScript = Join-Path $BackendPath "run_attendance_and_sleep.ps1"
$BatchFile = Join-Path $BackendPath "start_backend.local.bat"

$BackendTaskName = "Betopia Backend Auto Start"
$AttendanceTaskName = "Betopia Home Attendance Agent"

$OpenApiUrl = "http://127.0.0.1:8000/openapi.json"

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
# BACKEND DIRECTORY CHECK
# ============================================

if (-not (Test-Path $BackendPath)) {
    throw "Backend directory not found: $BackendPath"
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
# GENERATE ATTENDANCE + SLEEP SCRIPT
# ============================================

$SleepScriptContent = @'
$ErrorActionPreference = "Stop"

$LogFile = Join-Path $PSScriptRoot "attendance_run.log"

$ErpHost = "erp.betopiagroup.com"
$AttendanceApi = "http://127.0.0.1:8000/api/erp/attendance/home/run"
$OpenApiUrl = "http://127.0.0.1:8000/openapi.json"

function Write-Log {
    param([string]$Message)

    $Line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - $Message"

    Add-Content -Path $LogFile -Value $Line
    Write-Host $Line
}

try {

    Write-Log "========================================"
    Write-Log "Attendance task started."

    # ----------------------------------------
    # WAIT FOR BACKEND
    # MAXIMUM 30 SECONDS
    # ----------------------------------------

    $BackendReady = $false

    for ($i = 0; $i -lt 30; $i++) {

        try {

            Invoke-RestMethod `
                -Uri $OpenApiUrl `
                -TimeoutSec 2 | Out-Null

            $BackendReady = $true
            break

        }
        catch {

            Start-Sleep -Seconds 1

        }
    }

    if (-not $BackendReady) {
        throw "Backend unavailable after 30 seconds."
    }

    Write-Log "Backend is ready."

    # ----------------------------------------
    # WAIT FOR ERP CONNECTION
    # MAXIMUM 3 MINUTES
    # ----------------------------------------

    $ConnectionReady = $false

    $Deadline = (Get-Date).AddSeconds(180)

    while ((Get-Date) -lt $Deadline) {

        try {

            $DnsResult = Resolve-DnsName `
                -Name $ErpHost `
                -Type A `
                -ErrorAction Stop

            if ($DnsResult) {

                $HttpsReady = Test-NetConnection `
                    -ComputerName $ErpHost `
                    -Port 443 `
                    -InformationLevel Quiet `
                    -WarningAction SilentlyContinue

                if ($HttpsReady) {

                    $ConnectionReady = $true
                    break

                }
            }

        }
        catch {

            # DNS or network unavailable.
        }

        Write-Log "ERP connection unavailable. Waiting 10 seconds..."

        Start-Sleep -Seconds 10
    }

    if (-not $ConnectionReady) {

        throw "ERP connection unavailable after 3 minutes. Check-in was not attempted."

    }

    Write-Log "ERP DNS and HTTPS connection established."

    # ----------------------------------------
    # CALL ATTENDANCE API ONLY ONCE
    # ----------------------------------------

    Write-Log "Calling attendance API."

    $Result = Invoke-RestMethod `
        -Uri $AttendanceApi `
        -Method Post `
        -ContentType "application/json" `
        -Body '{"confirm_home_office":true}' `
        -TimeoutSec 120

    # ----------------------------------------
    # VERIFY ATTENDANCE
    # ----------------------------------------

    if (
        $Result.ok -eq $true -and
        $Result.verified -eq $true -and
        $Result.action -in @("checked_in", "already_checked_in")
    ) {

        Write-Log "Attendance verified successfully."
        Write-Log "Action: $($Result.action)"
        Write-Log "PC will enter Sleep in 5 seconds."

        Start-Sleep -Seconds 5

        rundll32.exe powrprof.dll,SetSuspendState 0,1,0

    }
    else {

        throw "Attendance not verified. PC will remain awake."

    }

}
catch {

    Write-Log "ERROR: $($_.Exception.Message)"
    Write-Log "PC will remain awake."
    exit 1

}
'@

Set-Content `
    -Path $SleepScript `
    -Value $SleepScriptContent `
    -Encoding UTF8

Write-Host "Attendance script generated." -ForegroundColor Green

# ============================================
# REQUIRED FILE CHECK
# ============================================

$RequiredFiles = @(
    (Join-Path $BackendPath "app\main.py"),
    (Join-Path $BackendPath ".venv\Scripts\activate.bat")
)

foreach ($File in $RequiredFiles) {

    if (-not (Test-Path $File)) {
        throw "Required file not found: $File"
    }

}

# ============================================
# CREATE LOCAL BACKEND BATCH
# ============================================

$BatchContent = @"
@echo off
cd /d "$BackendPath"
set "BETOPIA_EXPECTED_EMPLOYEE=$EmployeeName"
call ".venv\Scripts\activate.bat"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
"@

Set-Content `
    -Path $BatchFile `
    -Value $BatchContent `
    -Encoding ASCII

Write-Host "Backend configuration created." -ForegroundColor Green

# ============================================
# CURRENT USER
# ============================================

$CurrentUserSid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value

# ============================================
# TASK REGISTRATION HELPER
# ============================================

function Register-XmlTask {

    param(
        [string]$Name,
        [string]$Xml
    )

    Register-ScheduledTask `
        -TaskName $Name `
        -Xml $Xml `
        -Force `
        -ErrorAction Stop | Out-Null

    Write-Host "Created/Updated: $Name" -ForegroundColor Green

}

# ============================================
# BACKEND TASK
# ============================================

$BatchXml = [Security.SecurityElement]::Escape($BatchFile)
$BackendXmlPath = [Security.SecurityElement]::Escape($BackendPath)

$BackendTaskXml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">

    <RegistrationInfo>
        <Description>Start Betopia Attendance Backend.</Description>
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
        <StartWhenAvailable>true</StartWhenAvailable>
        <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
        <AllowStartOnDemand>true</AllowStartOnDemand>
        <Enabled>true</Enabled>
        <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
        <Priority>7</Priority>
    </Settings>

    <Actions Context="Author">
        <Exec>
            <Command>cmd.exe</Command>
            <Arguments>/c call "$BatchXml"</Arguments>
            <WorkingDirectory>$BackendXmlPath</WorkingDirectory>
        </Exec>
    </Actions>

</Task>
"@

Register-XmlTask -Name $BackendTaskName -Xml $BackendTaskXml

# ============================================
# ATTENDANCE TASK
# ============================================

$PowerShellPath = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"

$PowerShellXml = [Security.SecurityElement]::Escape($PowerShellPath)
$SleepScriptXml = [Security.SecurityElement]::Escape($SleepScript)

$StartBoundary = (Get-Date).ToString("yyyy-MM-dd") + "T" + $AttendanceTime

$AttendanceTaskXml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">

    <RegistrationInfo>
        <Description>Wake PC and run authorized Home Office Attendance.</Description>
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
        <StartWhenAvailable>true</StartWhenAvailable>
        <WakeToRun>true</WakeToRun>
        <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
        <AllowStartOnDemand>true</AllowStartOnDemand>
        <Enabled>true</Enabled>
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

try {

    Invoke-RestMethod `
        -Uri $OpenApiUrl `
        -TimeoutSec 3 | Out-Null

    $BackendReady = $true

    Write-Host "Backend is already running." -ForegroundColor Green

}
catch {

    $BackendReady = $false

}

if (-not $BackendReady) {

    Start-ScheduledTask -TaskName $BackendTaskName

    for ($i = 0; $i -lt 30; $i++) {

        Start-Sleep -Seconds 1

        try {

            Invoke-RestMethod `
                -Uri $OpenApiUrl `
                -TimeoutSec 2 | Out-Null

            $BackendReady = $true
            break

        }
        catch {

            $BackendReady = $false

        }

    }

}

if ($BackendReady) {

    Write-Host ""
    Write-Host "Backend started successfully!" -ForegroundColor Green

}
else {

    Write-Warning "Backend did not start within 30 seconds."
    Write-Warning "Check the backend task and startup errors."

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
Write-Host "ERP Wait       : Maximum 3 Minutes"
Write-Host "API Retry      : Disabled (one call only)"
Write-Host "Backend Ready  : $BackendReady"

Write-Host ""
Write-Host "IMPORTANT:" -ForegroundColor Yellow
Write-Host "1. Disable Attendance task on non-WFH days."
Write-Host "2. Ensure ERP login session is valid."
Write-Host "3. First test while you are present."
Write-Host "4. Check backend\attendance_run.log after execution."

Write-Host ""
Write-Host "Backend Task Status:"

Get-ScheduledTask -TaskName $BackendTaskName |
    Select-Object TaskName, State |
    Format-Table -AutoSize

Write-Host "Attendance Task Information:"

Get-ScheduledTaskInfo -TaskName $AttendanceTaskName |
    Select-Object NextRunTime, LastRunTime, LastTaskResult |
    Format-List

Write-Host "====================================" -ForegroundColor Green
