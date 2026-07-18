# Building DualSense Haptic Translator 1.1

Normal users should download the prebuilt ZIP from the GitHub Releases page. These instructions are for source review and reproducible public builds.

## Requirements

- Windows 10 or Windows 11, 64-bit
- Python 3.10
- .NET 8 SDK or a newer SDK capable of building `net8.0-windows`

Install the Python dependencies from the repository root:

```powershell
py -3.10 -m pip install -r requirements.txt
```

The optional `sounddevice` Python package can add another local audio-device discovery path, but the bundled .NET output service is the primary device scanner.

## Run From Source

```bat
run_public_mode.bat
```

The source tree contains the .NET output-service project. The first source run or build can restore its NuGet dependencies.

## Build The Public Release

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\release\build_public_release.ps1
```

The script:

1. Runs the first-run, RPM HUD, release-default, haptic, trigger, inline-description, HUD-scale migration, and EQ Boost verification gates.
2. Publishes the DualSense output service and builds the Sound To Haptic bridge.
3. Packages the PySide6 application with PyInstaller.
4. Audits the release folder against the public allowlist.
5. Produces both a one-folder build and a distribution ZIP under `artifacts\public_release`.

The public package excludes source files, developer launchers, internal documents, logs, caches, and personal settings.
