@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
where python >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    python "%SCRIPT_DIR%vendor_update.py" %*
    exit /b %ERRORLEVEL%
)
where py >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    py -3 "%SCRIPT_DIR%vendor_update.py" %*
    exit /b %ERRORLEVEL%
)
echo Error: python not found in PATH 1>&2
exit /b 1
