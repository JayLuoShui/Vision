@echo off
chcp 65001 >nul
set "SCRIPT=%~dp0copy_images_from_list.ps1"

if "%~1"=="" (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%"
) else (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" -ListPath "%~1"
)

if errorlevel 1 (
    echo.
    echo 执行失败，请查看上方错误。
) else (
    echo.
    echo 执行成功。
)

pause
