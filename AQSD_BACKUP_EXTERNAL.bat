@echo off
title AQSD External Backup
setlocal

set "SOURCE=C:\Users\megha\AQSD"
set "DEST=F:\AQSD_BACKUP\01_AQSD_PROJECT"

echo.
echo ==========================================
echo        AQSD EXTERNAL BACKUP
echo ==========================================
echo.
echo Source      : %SOURCE%
echo Destination : %DEST%
echo.

if not exist "%SOURCE%\" (
    echo ERROR: AQSD source folder not found.
    echo %SOURCE%
    pause
    exit /b 1
)

if not exist "F:\" (
    echo ERROR: External Drive F: is not available.
    echo Please connect WD My Passport Ultra.
    pause
    exit /b 1
)

if not exist "%DEST%\" mkdir "%DEST%"

echo Starting backup...
echo.

robocopy "%SOURCE%" "%DEST%" /E /COPY:DAT /DCOPY:T /R:2 /W:2 /XJ /XD "%SOURCE%\.git" "%SOURCE%\.venv" "%SOURCE%\.venv-fyers" "%SOURCE%\__pycache__" "%SOURCE%\.pytest_cache" "%SOURCE%\.mypy_cache" /XF "*.pyc" "*.pyo" "*.tmp"

set "RC=%ERRORLEVEL%"

echo.
echo ==========================================
echo          BACKUP COMPLETED
echo ==========================================
echo.

if %RC% GEQ 8 (
    echo BACKUP STATUS : FAILED
    echo Robocopy Exit Code : %RC%
) else (
    echo BACKUP STATUS : SUCCESS
    echo Robocopy Exit Code : %RC%
)

echo.
echo Mirror mode     : NOT USED
echo Delete at F:    : NOT PERFORMED
echo Backup location : %DEST%
echo.
pause

endlocal