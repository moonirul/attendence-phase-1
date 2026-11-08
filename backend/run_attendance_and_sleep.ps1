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
