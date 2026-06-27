$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$grapherPath = Join-Path $root "telemetry_grapher.py"
$pythonCandidates = @(
    (Join-Path $env:LOCALAPPDATA "Programs\Python\Python310\python.exe"),
    "py",
    "python"
)

$python = $null
foreach ($candidate in $pythonCandidates) {
    if ($candidate -eq "py" -or $candidate -eq "python") {
        $command = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($command) {
            $python = $candidate
            break
        }
    } elseif (Test-Path -LiteralPath $candidate) {
        $python = $candidate
        break
    }
}

if (-not $python) {
    throw "Python executable was not found. Install Python 3.10 or add python.exe to PATH."
}

Write-Host "Checking for previous telemetry grapher..."
$oldGraphers = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -like "python*" -and $_.CommandLine -like "*$grapherPath*"
}
foreach ($old in $oldGraphers) {
    Write-Host "Stopping previous telemetry grapher pid=$($old.ProcessId)"
    Stop-Process -Id $old.ProcessId -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Milliseconds 200

Write-Host "Starting Forza telemetry grapher..."
if ($python -eq "py") {
    & $python -3 $grapherPath --host 0.0.0.0 --port 8800 --haptic-event-port 18801
} else {
    & $python $grapherPath --host 0.0.0.0 --port 8800 --haptic-event-port 18801
}
