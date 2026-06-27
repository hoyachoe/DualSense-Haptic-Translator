$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:DOTNET_CLI_UI_LANGUAGE = "en"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$serverDir = Join-Path $root "dualsense_output_server"
$serverProject = Join-Path $serverDir "DualSenseOutputServer.csproj"
$serverDll = Join-Path $serverDir "bin\Debug\net8.0-windows\DualSenseOutputServer.dll"
$serverDllName = [System.IO.Path]::GetFileName($serverDll)
$logDir = Join-Path $root "logs"
if (-not (Test-Path -LiteralPath $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$serverOutLog = Join-Path $logDir "haptic_server_latest.out.log"
$serverErrLog = Join-Path $logDir "haptic_server_latest.err.log"
$settingsPath = Join-Path $root "telemetry_grapher_settings.json"
$outputDeviceNeedle = "DualSense"
$masterGainPercent = 100
$disableTriggerHid = $false
if (Test-Path -LiteralPath $settingsPath) {
    try {
        $settings = Get-Content -LiteralPath $settingsPath -Raw | ConvertFrom-Json
        if ($settings.dsx_audio_export_enabled -and -not [string]::IsNullOrWhiteSpace([string]$settings.dsx_audio_device)) {
            $outputDeviceNeedle = [string]$settings.dsx_audio_device
            if ($null -ne $settings.dsx_audio_volume_percent) {
                $parsedGain = 100
                if ([int]::TryParse([string]$settings.dsx_audio_volume_percent, [ref]$parsedGain)) {
                    $masterGainPercent = [Math]::Max(0, [Math]::Min(100, $parsedGain))
                }
            }
        }
        if ($settings.dsx_udp_enabled) {
            $disableTriggerHid = $true
        }
    } catch {
        Write-Host "Could not read telemetry_grapher_settings.json. Using default DualSense output."
    }
}

$running = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -in @("dotnet.exe", "DualSenseOutputServer.exe") -and $_.CommandLine -like "*$serverDllName*"
}
if ($running) {
    foreach ($proc in $running) {
        Write-Host "DualSense output server is already running. pid=$($proc.ProcessId)"
    }
    Write-Host "Server logs: $serverOutLog"
    exit 0
}

Write-Host "Building DualSense output server..."
dotnet build $serverProject --nologo -v minimal | Out-Host
if ($LASTEXITCODE -ne 0) { throw "DualSense output server build failed." }

foreach ($log in @($serverOutLog, $serverErrLog)) {
    if (Test-Path -LiteralPath $log) {
        Remove-Item -LiteralPath $log -Force
    }
}

Write-Host "Starting DualSense output server..."
$serverArgsList = @("`"$serverDll`"", "--event-port", "18801", "--no-keys", "--output-device", "`"$outputDeviceNeedle`"", "--master-gain-percent", "$masterGainPercent")
if ($disableTriggerHid) { $serverArgsList += "--no-trigger-hid" }
$serverArgs = $serverArgsList -join " "
Write-Host "Output device match: $outputDeviceNeedle"
Write-Host "Haptic audio volume: $masterGainPercent%"
if ($disableTriggerHid) { Write-Host "Trigger HID disabled because DSX UDP is enabled." }
$server = Start-Process -FilePath "dotnet" -ArgumentList $serverArgs -WorkingDirectory $serverDir -WindowStyle Hidden -RedirectStandardOutput $serverOutLog -RedirectStandardError $serverErrLog -PassThru
Start-Sleep -Milliseconds 1500
if ($server.HasExited) {
    Write-Host "DualSense output server exited immediately."
    Write-Host "stdout: $serverOutLog"
    if (Test-Path -LiteralPath $serverOutLog) { Get-Content -LiteralPath $serverOutLog | Out-Host }
    Write-Host "stderr: $serverErrLog"
    if (Test-Path -LiteralPath $serverErrLog) { Get-Content -LiteralPath $serverErrLog | Out-Host }
    throw "DualSense output server failed to start."
}

Write-Host "DualSense output server is running. pid=$($server.Id)"
Write-Host "Server logs: $serverOutLog"

