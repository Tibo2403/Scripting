@echo off
setlocal
set "PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if not exist "%PYTHON%" (
  echo Python Codex introuvable.
  pause
  exit /b 1
)
"%PYTHON%" "%~dp0scripts\python\codex_astra_switch.py" %*
if errorlevel 1 (
  pause
  exit /b 1
)
