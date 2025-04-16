@echo off
echo Cleaning temporary files...
echo ---------------------------------

:: Grant admin rights
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Please run this script as Administrator!
    pause
    exit
)

:: Delete files in %temp%
rd /s /q "%temp%"

:: Delete files in Windows Temp folder
rd /s /q "C:\Windows\Temp"

:: Delete files in Prefetch folder (use file deletion instead of folder removal)
del /f /s /q "C:\Windows\Prefetch\*.*"

:: Delete recent files
rd /s /q "%APPDATA%\Microsoft\Windows\Recent"

echo Temporary files and recent files cleaned successfully!
pause