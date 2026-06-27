param(
    [string]$Version = "0.9.0",
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $root
try {
    $appName = "DualSense Haptic Translator"
    $uiName = "DualSense Haptic Translator UI"
    $iconPath = Join-Path $root "DualSense Haptic Translator.ico"
    $mainPy = Join-Path $root "telemetry_grapher.py"
    $serverProject = Join-Path $root "dualsense_output_server\DualSenseOutputServer.csproj"
    $launcherProject = Join-Path $root "dualsense_launcher\DualSenseHapticTranslatorLauncher.csproj"
    $releaseRoot = Join-Path $root "release"
    $stageDir = Join-Path $releaseRoot "$appName-v$Version"
    $appDir = Join-Path $stageDir "app"
    $runtimeDir = Join-Path $stageDir "runtime"
    $serverPublishDir = Join-Path $releaseRoot "server-publish"
    $launcherPublishDir = Join-Path $releaseRoot "launcher-publish"
    $zipPath = Join-Path $releaseRoot "$appName-v$Version-windows-x64.zip"

    function Require-File($path, $message) {
        if (-not (Test-Path -LiteralPath $path)) {
            throw $message
        }
    }

    Require-File $mainPy "telemetry_grapher.py was not found."
    Require-File $iconPath "DualSense Haptic Translator.ico was not found."
    Require-File $serverProject "DualSenseOutputServer.csproj was not found."
    Require-File $launcherProject "DualSenseHapticTranslatorLauncher.csproj was not found."

    $pyInstallerVersion = & py -3.10 -m PyInstaller --version
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller is not available for Python 3.10. Install it with: py -3.10 -m pip install pyinstaller"
    }
    Write-Host "PyInstaller $pyInstallerVersion"

    if ($Clean) {
        foreach ($path in @(
            (Join-Path $root "build"),
            (Join-Path $root "dist"),
            $releaseRoot,
            (Join-Path $root "$uiName.spec")
        )) {
            if (Test-Path -LiteralPath $path) {
                Write-Host "Removing $path"
                Remove-Item -LiteralPath $path -Recurse -Force
            }
        }
    }

    New-Item -ItemType Directory -Path $releaseRoot -Force | Out-Null

    Write-Host "Building Python UI executable..."
    & py -3.10 -m PyInstaller `
        --noconfirm `
        --clean `
        --windowed `
        --name $uiName `
        --icon $iconPath `
        $mainPy
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }

    Write-Host "Publishing DualSense output server..."
    & dotnet publish $serverProject `
        -c Release `
        -r win-x64 `
        --self-contained false `
        -p:PublishSingleFile=false `
        -o $serverPublishDir
    if ($LASTEXITCODE -ne 0) { throw "dotnet publish failed." }

    Write-Host "Publishing release launcher..."
    & dotnet publish $launcherProject `
        -c Release `
        -r win-x64 `
        --self-contained false `
        -p:PublishSingleFile=false `
        -o $launcherPublishDir
    if ($LASTEXITCODE -ne 0) { throw "launcher publish failed." }

    if (Test-Path -LiteralPath $stageDir) {
        Remove-Item -LiteralPath $stageDir -Recurse -Force
    }
    New-Item -ItemType Directory -Path $stageDir -Force | Out-Null
    New-Item -ItemType Directory -Path $appDir -Force | Out-Null
    New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null

    Copy-Item -LiteralPath (Join-Path $launcherPublishDir "$appName.exe") -Destination (Join-Path $stageDir "$appName.exe") -Force
    Copy-Item -Path (Join-Path $root "dist\$uiName\*") -Destination $appDir -Recurse -Force
    Copy-Item -LiteralPath $iconPath -Destination $stageDir -Force
    Copy-Item -LiteralPath (Join-Path $root "README_FIRST.txt") -Destination $stageDir -Force

    foreach ($folder in @("config_presets")) {
        $src = Join-Path $root $folder
        if (Test-Path -LiteralPath $src) {
            Copy-Item -LiteralPath $src -Destination (Join-Path $stageDir $folder) -Recurse -Force
        }
    }

    Copy-Item -Path (Join-Path $serverPublishDir "*") -Destination $runtimeDir -Recurse -Force
    New-Item -ItemType Directory -Path (Join-Path $stageDir "logs") -Force | Out-Null

    if (Test-Path -LiteralPath $zipPath) {
        Remove-Item -LiteralPath $zipPath -Force
    }
    Compress-Archive -Path (Join-Path $stageDir "*") -DestinationPath $zipPath -Force

    Write-Host ""
    Write-Host "Release folder: $stageDir"
    Write-Host "Release zip:    $zipPath"
    Write-Host "Done."
}
finally {
    Pop-Location
}



