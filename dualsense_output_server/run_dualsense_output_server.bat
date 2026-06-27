@echo off
setlocal
cd /d "%~dp0"
dotnet run --project DualSenseOutputServer.csproj -- --event-port 18801
pause
