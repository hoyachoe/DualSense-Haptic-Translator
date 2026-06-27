$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$serverDll = Join-Path $root "dualsense_output_server\bin\Debug\net8.0-windows\DualSenseOutputServer.dll"
$serverDllName = [System.IO.Path]::GetFileName($serverDll)

$running = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -in @("dotnet.exe", "DualSenseOutputServer.exe") -and $_.CommandLine -like "*$serverDllName*"
}
if (-not $running) {
    Write-Host "No DualSense output server is running."
    exit 0
}

foreach ($proc in $running) {
    Write-Host "Stopping DualSense output server pid=$($proc.ProcessId)"
    Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
}
Write-Host "DualSense output server stopped."
