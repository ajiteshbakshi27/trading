@echo off
REM Double-click me. Runs the PowerShell mover with a one-time policy bypass.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0move-to-d-drive.ps1"
