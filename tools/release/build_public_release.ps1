[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$appName = "DualSense Haptic Translator"
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
$appVersionSource = Join-Path $projectRoot "dht_app\version.py"
$allowlistPath = Join-Path $PSScriptRoot "release_allowlist.json"
$readmeSource = Join-Path $PSScriptRoot "README_FIRST.txt"
$versionInfoSource = Join-Path $PSScriptRoot "windows_version_info.txt"
$firstRunVerifier = Join-Path $PSScriptRoot "verify_first_run.py"
$rpmHudVerifier = Join-Path $PSScriptRoot "verify_rpm_hud.py"
$releaseDefaultsVerifier = Join-Path $PSScriptRoot "verify_release_defaults.py"
$hapticParityVerifier = Join-Path $PSScriptRoot "verify_haptic_legacy_parity.py"
$triggerReleaseVerifier = Join-Path $PSScriptRoot "verify_trigger_release_fixes.py"
$inlineDescriptionsVerifier = Join-Path $PSScriptRoot "verify_inline_descriptions.py"
$hudUiScaleVerifier = Join-Path $PSScriptRoot "verify_hud_ui_scale_independence.py"
$hapticEqBoostVerifier = Join-Path $PSScriptRoot "verify_haptic_eq_boost.py"
$artifactsRoot = Join-Path $projectRoot "artifacts"
$assetRoot = Join-Path $artifactsRoot "public_assets"
$buildRoot = Join-Path $artifactsRoot "public_build"
$distRoot = Join-Path $artifactsRoot "public_release"
$specRoot = Join-Path $artifactsRoot "public_spec"
$outputPublishRoot = Join-Path $artifactsRoot "output_runtime"
$releaseRoot = Join-Path $distRoot $appName

function Assert-FileExists {
    param([Parameter(Mandatory)][string]$LiteralPath)

    if (-not (Test-Path -LiteralPath $LiteralPath -PathType Leaf)) {
        throw "Required file not found: $LiteralPath"
    }
}

function Reset-GeneratedDirectory {
    param([Parameter(Mandatory)][string]$LiteralPath)

    $fullPath = [System.IO.Path]::GetFullPath($LiteralPath)
    $allowedRoot = [System.IO.Path]::GetFullPath($artifactsRoot).TrimEnd('\') + '\'
    if (-not $fullPath.StartsWith($allowedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to clean a path outside the project artifacts folder: $fullPath"
    }
    if (Test-Path -LiteralPath $fullPath) {
        Remove-Item -LiteralPath $fullPath -Recurse -Force
    }
    New-Item -ItemType Directory -Path $fullPath -Force | Out-Null
}

function Copy-AllowlistedFiles {
    param(
        [Parameter(Mandatory)][string]$SourceRoot,
        [Parameter(Mandatory)][string]$DestinationRoot,
        [Parameter(Mandatory)][object[]]$RelativePaths
    )

    $sourceFull = [System.IO.Path]::GetFullPath($SourceRoot).TrimEnd('\') + '\'
    foreach ($relativePathValue in $RelativePaths) {
        $relativePath = [string]$relativePathValue
        if ([System.IO.Path]::IsPathRooted($relativePath) -or $relativePath -match '(^|[\\/])\.\.([\\/]|$)') {
            throw "Unsafe allowlist path: $relativePath"
        }
        $source = [System.IO.Path]::GetFullPath((Join-Path $SourceRoot $relativePath))
        if (-not $source.StartsWith($sourceFull, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Allowlist path escapes its source folder: $relativePath"
        }
        Assert-FileExists $source
        $destination = Join-Path $DestinationRoot $relativePath
        $destinationDirectory = Split-Path -Parent $destination
        New-Item -ItemType Directory -Path $destinationDirectory -Force | Out-Null
        Copy-Item -LiteralPath $source -Destination $destination -Force
    }
}

function Assert-ExactRelativeFiles {
    param(
        [Parameter(Mandatory)][string]$Root,
        [Parameter(Mandatory)][object[]]$ExpectedPaths
    )

    $rootFull = [System.IO.Path]::GetFullPath($Root).TrimEnd('\') + '\'
    $actual = @(
        Get-ChildItem -LiteralPath $Root -Recurse -File |
            ForEach-Object { $_.FullName.Substring($rootFull.Length).Replace('\', '/') } |
            Sort-Object
    )
    $expected = @($ExpectedPaths | ForEach-Object { ([string]$_).Replace('\', '/') } | Sort-Object)
    $difference = @(Compare-Object -ReferenceObject $expected -DifferenceObject $actual)
    if ($difference.Count -gt 0) {
        $summary = ($difference | ForEach-Object { "{0} {1}" -f $_.SideIndicator, $_.InputObject }) -join '; '
        throw "Allowlist mismatch under ${Root}: $summary"
    }
}

Assert-FileExists $appVersionSource
$appVersionText = Get-Content -LiteralPath $appVersionSource -Raw
$appVersionMatch = [regex]::Match($appVersionText, '(?m)^APP_VERSION\s*=\s*"([^"]+)"\s*$')
if (-not $appVersionMatch.Success) {
    throw "Could not read APP_VERSION from $appVersionSource"
}
$releaseVersion = $appVersionMatch.Groups[1].Value
$releaseNotesFileName = "RELEASE_NOTES_$releaseVersion.txt"
$releaseNotesSource = Join-Path $PSScriptRoot $releaseNotesFileName
$archivePath = Join-Path $distRoot "$appName $releaseVersion.zip"

Assert-FileExists $allowlistPath
Assert-FileExists $readmeSource
Assert-FileExists $releaseNotesSource
Assert-FileExists $versionInfoSource
Assert-FileExists $firstRunVerifier
Assert-FileExists $rpmHudVerifier
Assert-FileExists $releaseDefaultsVerifier
Assert-FileExists $hapticParityVerifier
Assert-FileExists $triggerReleaseVerifier
Assert-FileExists $inlineDescriptionsVerifier
Assert-FileExists $hudUiScaleVerifier
Assert-FileExists $hapticEqBoostVerifier
$allowlist = Get-Content -LiteralPath $allowlistPath -Raw | ConvertFrom-Json

if ($allowlist.release_root_files -notcontains $releaseNotesFileName) {
    throw "Release allowlist does not include $releaseNotesFileName"
}

foreach ($verifier in @(
    $firstRunVerifier,
    $rpmHudVerifier,
    $releaseDefaultsVerifier,
    $hapticParityVerifier,
    $triggerReleaseVerifier,
    $inlineDescriptionsVerifier,
    $hudUiScaleVerifier,
    $hapticEqBoostVerifier
)) {
    & py -3.10 -B $verifier
    if ($LASTEXITCODE -ne 0) {
        throw "Release verification failed: $verifier (exit code $LASTEXITCODE)."
    }
}

New-Item -ItemType Directory -Path $artifactsRoot -Force | Out-Null
Reset-GeneratedDirectory $assetRoot
Reset-GeneratedDirectory $buildRoot
Reset-GeneratedDirectory $distRoot
Reset-GeneratedDirectory $specRoot
Reset-GeneratedDirectory $outputPublishRoot

$outputProject = Join-Path $projectRoot "dht_app\dualsense_output_server\DualSenseOutputServer.csproj"
$soundProject = Join-Path $projectRoot "dht_app\sound_to_haptic_bridge\DualSenseSoundToHapticBridge.csproj"
Assert-FileExists $outputProject
Assert-FileExists $soundProject
& dotnet publish $outputProject -c Release --nologo --self-contained false -o $outputPublishRoot
if ($LASTEXITCODE -ne 0) {
    throw "DualSense output service publish failed with exit code $LASTEXITCODE."
}
& dotnet build $soundProject -c Release --nologo
if ($LASTEXITCODE -ne 0) {
    throw "Sound To Haptic bridge build failed with exit code $LASTEXITCODE."
}

$assetAppRoot = Join-Path $assetRoot "dht_app"
$resourceDestination = Join-Path $assetAppRoot "Resource"
$presetDestination = Join-Path $assetAppRoot "config_presets"
$runtimeDestination = Join-Path $assetAppRoot "runtime"
$soundDestination = Join-Path $assetAppRoot "sound_to_haptic_bridge\bin\Release\net8.0-windows"

Copy-AllowlistedFiles (Join-Path $projectRoot "dht_app\Resource") $resourceDestination $allowlist.resources
Copy-AllowlistedFiles (Join-Path $projectRoot "dht_app\config_presets") $presetDestination $allowlist.presets
Copy-AllowlistedFiles $outputPublishRoot $runtimeDestination $allowlist.output_runtime
Copy-AllowlistedFiles (Join-Path $projectRoot "dht_app\sound_to_haptic_bridge\bin\Release\net8.0-windows") $soundDestination $allowlist.sound_bridge
Set-Content -LiteralPath (Join-Path $assetAppRoot "PUBLIC_RELEASE") -Value "Public release package: developer modes disabled." -Encoding ascii

Assert-ExactRelativeFiles $resourceDestination $allowlist.resources
Assert-ExactRelativeFiles $presetDestination $allowlist.presets
Assert-ExactRelativeFiles $runtimeDestination $allowlist.output_runtime
Assert-ExactRelativeFiles $soundDestination $allowlist.sound_bridge

$iconPath = Join-Path $projectRoot "dht_app\Resource\icon_DHT.ico"
$entryPoint = Join-Path $projectRoot "main.py"
Assert-FileExists $iconPath
Assert-FileExists $entryPoint

$pyInstallerArguments = @(
    '-3.10',
    '-m', 'PyInstaller',
    '--noconfirm',
    '--clean',
    '--windowed',
    '--name', $appName,
    '--icon', $iconPath,
    '--version-file', $versionInfoSource,
    '--contents-directory', '_internal',
    '--distpath', $distRoot,
    '--workpath', $buildRoot,
    '--specpath', $specRoot,
    '--add-data', "${assetAppRoot};dht_app",
    '--exclude-module', 'dht_app.telemetry_test_packets',
    $entryPoint
)
& py @pyInstallerArguments
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE."
}

Assert-FileExists (Join-Path $releaseRoot "$appName.exe")
Copy-Item -LiteralPath $readmeSource -Destination (Join-Path $releaseRoot "README_FIRST.txt") -Force
Copy-Item -LiteralPath $releaseNotesSource -Destination (Join-Path $releaseRoot $releaseNotesFileName) -Force

$executableInfo = [System.Diagnostics.FileVersionInfo]::GetVersionInfo((Join-Path $releaseRoot "$appName.exe"))
$expectedFileVersion = "$releaseVersion.0.0"
if ($executableInfo.FileVersion -ne $expectedFileVersion -or $executableInfo.ProductVersion -ne $releaseVersion) {
    throw "Executable version metadata is incorrect: file=$($executableInfo.FileVersion), product=$($executableInfo.ProductVersion)"
}

$expectedRootNames = @($allowlist.release_root_files + $allowlist.release_root_directories | Sort-Object)
$actualRootNames = @(Get-ChildItem -LiteralPath $releaseRoot -Force | ForEach-Object Name | Sort-Object)
$rootDifference = @(Compare-Object -ReferenceObject $expectedRootNames -DifferenceObject $actualRootNames)
if ($rootDifference.Count -gt 0) {
    $summary = ($rootDifference | ForEach-Object { "{0} {1}" -f $_.SideIndicator, $_.InputObject }) -join '; '
    throw "Unexpected public release root contents: $summary"
}

$forbiddenExtensions = @($allowlist.forbidden_extensions | ForEach-Object { ([string]$_).ToLowerInvariant() })
$forbiddenDirectoryNames = @($allowlist.forbidden_directory_names | ForEach-Object { [string]$_ })
$forbiddenFileNames = @($allowlist.forbidden_file_names | ForEach-Object { [string]$_ })
$forbiddenItems = @(
    Get-ChildItem -LiteralPath $releaseRoot -Recurse -Force | Where-Object {
        if ($_.PSIsContainer) {
            return $forbiddenDirectoryNames -contains $_.Name
        }
        return ($forbiddenExtensions -contains $_.Extension.ToLowerInvariant()) -or ($forbiddenFileNames -contains $_.Name)
    }
)
if ($forbiddenItems.Count -gt 0) {
    throw "Forbidden public release item(s): $($forbiddenItems.FullName -join '; ')"
}

$packagedAppRoot = Join-Path $releaseRoot "_internal\dht_app"
Assert-FileExists (Join-Path $packagedAppRoot "PUBLIC_RELEASE")
Assert-ExactRelativeFiles (Join-Path $packagedAppRoot "Resource") $allowlist.resources
Assert-ExactRelativeFiles (Join-Path $packagedAppRoot "config_presets") $allowlist.presets
Assert-ExactRelativeFiles (Join-Path $packagedAppRoot "runtime") $allowlist.output_runtime
Assert-ExactRelativeFiles (Join-Path $packagedAppRoot "sound_to_haptic_bridge\bin\Release\net8.0-windows") $allowlist.sound_bridge

Compress-Archive -LiteralPath $releaseRoot -DestinationPath $archivePath -CompressionLevel Optimal
Assert-FileExists $archivePath

Write-Host ""
Write-Host "Public release build and audit passed." -ForegroundColor Green
Write-Host "Folder: $releaseRoot"
Write-Host "Archive: $archivePath"
