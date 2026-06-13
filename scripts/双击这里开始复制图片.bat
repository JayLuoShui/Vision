@echo off
title Copy Images From List
set "SCRIPT=%~dp0copy_images_from_list.ps1"

if not exist "%SCRIPT%" (
    echo ERROR: PowerShell script not found:
    echo %SCRIPT%
    echo.
    pause
    exit /b 1
)

if "%~1"=="" (
    "%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%"
) else (
    "%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" -ListPath "%~1"
)

set "EXIT_CODE=%ERRORLEVEL%"
echo.
if not "%EXIT_CODE%"=="0" (
    echo FAILED. See the error above.
) else (
    echo DONE.
)
pause
exit /b %EXIT_CODE%
