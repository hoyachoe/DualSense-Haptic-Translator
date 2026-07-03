param(
    [string]$Version = "0.9.2",
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $root
try {
    $appName = "DualSense Haptic Translator"
    $uiName = "DualSense Haptic Translator UI"
    $iconPath = Join-Path $root "assets\DualSense Haptic Translator.ico"
    $dualsenseIconPng = Join-Path $root "assets\DualSense_icon.png"
    $mainPy = Join-Path $root "telemetry_grapher.py"
    $releaseSettings = Join-Path $root "telemetry_grapher_release_settings.json"
    $serverProject = Join-Path $root "dualsense_output_server\DualSenseOutputServer.csproj"
    $launcherProject = Join-Path $root "dualsense_launcher\DualSenseHapticTranslatorLauncher.csproj"
    $releaseRoot = Join-Path $root "release"
    $stageDir = Join-Path $releaseRoot "$appName-v$Version"
    $appDir = Join-Path $stageDir "app"
    $runtimeDir = Join-Path $stageDir "runtime"
    $docsDir = Join-Path $stageDir "docs"
    $sourceDir = Join-Path $stageDir "source"
    $sourceServerDir = Join-Path $sourceDir "dualsense_output_server"
    $serverPublishDir = Join-Path $releaseRoot "server-publish"
    $launcherPublishDir = Join-Path $releaseRoot "launcher-publish"
    $zipPath = Join-Path $releaseRoot "$appName-v$Version-windows-x64.zip"

    function Require-File($path, $message) {
        if (-not (Test-Path -LiteralPath $path)) {
            throw $message
        }
    }

    Require-File $mainPy "telemetry_grapher.py was not found."
    Require-File $iconPath "assets\DualSense Haptic Translator.ico was not found."
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

    Write-Host "Exporting release-safe settings..."
    & py -3.10 $mainPy --export-release-settings $releaseSettings
    if ($LASTEXITCODE -ne 0) { throw "release settings export failed." }
    Require-File $releaseSettings "telemetry_grapher_release_settings.json was not created."

    New-Item -ItemType Directory -Path $releaseRoot -Force | Out-Null

    Write-Host "Building Python UI executable..."
    $pyInstallerArgs = @(
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name", $uiName,
        "--icon", $iconPath
    )
    if (Test-Path -LiteralPath $dualsenseIconPng) {
        $pyInstallerArgs += @("--add-data", "$dualsenseIconPng;assets")
    }
    $pyInstallerArgs += $mainPy
    & py -3.10 -m PyInstaller @pyInstallerArgs
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
        -p:PublishSingleFile=true `
        -p:DebugType=None `
        -p:DebugSymbols=false `
        -o $launcherPublishDir
    if ($LASTEXITCODE -ne 0) { throw "launcher publish failed." }

    if (Test-Path -LiteralPath $stageDir) {
        Remove-Item -LiteralPath $stageDir -Recurse -Force
    }
    New-Item -ItemType Directory -Path $stageDir -Force | Out-Null
    New-Item -ItemType Directory -Path $appDir -Force | Out-Null
    New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
    New-Item -ItemType Directory -Path $docsDir -Force | Out-Null
    New-Item -ItemType Directory -Path $sourceDir -Force | Out-Null
    New-Item -ItemType Directory -Path $sourceServerDir -Force | Out-Null

    $launcherExe = Join-Path $launcherPublishDir "$appName.exe"
    Require-File $launcherExe "Launcher executable was not created."
    Copy-Item -LiteralPath $launcherExe -Destination $stageDir -Force
    Copy-Item -Path (Join-Path $root "dist\$uiName\*") -Destination $appDir -Recurse -Force
    Copy-Item -LiteralPath (Join-Path $root "README_FIRST.txt") -Destination $stageDir -Force
    foreach ($docName in @("LICENSE", "README.md", "SUPPORT.md", "FEATURE_GUIDE_KR.md", "FEATURE_GUIDE_EN.md")) {
        $docPath = Join-Path $root $docName
        if (Test-Path -LiteralPath $docPath) {
            Copy-Item -LiteralPath $docPath -Destination $docsDir -Force
        }
    }
    Copy-Item -LiteralPath $releaseSettings -Destination $appDir -Force

    foreach ($folder in @("config_presets")) {
        $src = Join-Path $root $folder
        if (Test-Path -LiteralPath $src) {
            Copy-Item -LiteralPath $src -Destination (Join-Path $stageDir $folder) -Recurse -Force
        }
    }

    Copy-Item -Path (Join-Path $serverPublishDir "*") -Destination $runtimeDir -Recurse -Force
    Copy-Item -LiteralPath $mainPy -Destination $sourceDir -Force
    Copy-Item -LiteralPath $releaseSettings -Destination $sourceDir -Force
    foreach ($docName in @("LICENSE", "README.md", "SUPPORT.md", "FEATURE_GUIDE_KR.md", "FEATURE_GUIDE_EN.md")) {
        $docPath = Join-Path $root $docName
        if (Test-Path -LiteralPath $docPath) {
            Copy-Item -LiteralPath $docPath -Destination $sourceDir -Force
        }
    }
    New-Item -ItemType Directory -Path (Join-Path $sourceDir "assets") -Force | Out-Null
    Copy-Item -LiteralPath $iconPath -Destination (Join-Path $sourceDir "assets") -Force
    if (Test-Path -LiteralPath $dualsenseIconPng) {
        Copy-Item -LiteralPath $dualsenseIconPng -Destination (Join-Path $sourceDir "assets") -Force
    }
    foreach ($scriptName in @(
        "run_telemetry_grapher.bat",
        "run_telemetry_grapher.ps1",
        "start_haptic_server.bat",
        "start_haptic_server.ps1",
        "stop_haptic_server.bat",
        "stop_haptic_server.ps1"
    )) {
        $scriptPath = Join-Path $root $scriptName
        if (Test-Path -LiteralPath $scriptPath) {
            Copy-Item -LiteralPath $scriptPath -Destination $sourceDir -Force
        }
    }
    foreach ($serverFile in @("DualSenseOutputServer.csproj", "Program.cs", "DualSenseTriggerWriter.cs", "run_dualsense_output_server.bat")) {
        $serverPath = Join-Path (Join-Path $root "dualsense_output_server") $serverFile
        if (Test-Path -LiteralPath $serverPath) {
            Copy-Item -LiteralPath $serverPath -Destination $sourceServerDir -Force
        }
    }

    foreach ($forbiddenName in @("PROJECT_NOTES.md", "INTERNAL_DHE_ANALYSIS.md", "TRIGGER_CORE_PRESETS.md")) {
        if (Test-Path -LiteralPath (Join-Path $stageDir $forbiddenName)) {
            throw "$forbiddenName must not be included in the public release root."
        }
        if (Test-Path -LiteralPath (Join-Path $sourceDir $forbiddenName)) {
            throw "$forbiddenName must not be included in the public release source folder."
        }
    }

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
