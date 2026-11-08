$log = Join-Path $PSScriptRoot "attendance-agent.log"
$uri = "http://127.0.0.1:8000/api/erp/attendance/home/run"

"[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Agent started" |
    Out-File $log -Append

try {
    $response = Invoke-RestMethod `
        -Method Post `
        -Uri $uri `
        -ContentType "application/json" `
        -Body '{"confirm_home_office":true}' `
        -TimeoutSec 120

    $response |
        ConvertTo-Json -Depth 10 |
        Out-File $log -Append

} catch {
    "ERROR: $($_.Exception.Message)" |
        Out-File $log -Append

    if ($_.ErrorDetails.Message) {
        "RESPONSE: $($_.ErrorDetails.Message)" |
            Out-File $log -Append
    }
}

"[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Agent finished" |
    Out-File $log -Append