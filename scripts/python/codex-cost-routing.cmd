@echo off
setlocal
set "SCRIPT_DIR=%~dp0"

if "%~1"=="" (
  set "ACTION=Status"
) else (
  set "ACTION=%~1"
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "& '%SCRIPT_DIR%Manage-CodexCostRouting.ps1' -Action '%ACTION%'"
