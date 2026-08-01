@echo off
setlocal

title AQSD Backup Manager

echo.
echo ============================================================
echo                  AQSD BACKUP MANAGER
echo ============================================================
echo.

REM ============================================================
REM AQSD BACKUP ARCHITECTURE
REM
REM C:\Users\megha\AQSD   = Source Code / Project
REM D:\AQSD_DATA          = Primary Market Data / Databases
REM E:\AQSD_BACKUP        = Backup Destination
REM ============================================================

set "PROJECT_SOURCE=C:\Users\megha\AQSD"
set "DATA_SOURCE=D:\AQSD_DATA"

set "BACKUP_ROOT=E:\AQSD_BACKUP"
set "PROJECT_BACKUP=%BACKUP_ROOT%\PROJECT"
set "DATA_BACKUP=%BACKUP_ROOT%\DATA"

echo Source Project : %PROJECT_SOURCE%
echo Source Data    : %DATA_SOURCE%
echo Backup Root    : %BACKUP_ROOT%
echo.

REM ------------------------------------------------------------
REM Validate drives
REM ------------------------------------------------------------

if not exist "D:\" (
    echo ERROR: D: drive not found.
    goto :FAILED
)

if not exist "E:\" (
    echo ERROR: E: drive not found.
    goto :FAILED
)

if not exist "%PROJECT_SOURCE%\" (
    echo ERROR: AQSD project folder not found.
    goto :FAILED
)

if not exist "%DATA_SOURCE%\" (
    echo ERROR: AQSD_DATA folder not found.
    goto :FAILED
)

REM ------------------------------------------------------------
REM Create backup folders
REM ------------------------------------------------------------

if not exist "%BACKUP_ROOT%" mkdir "%BACKUP_ROOT%"
if not exist "%PROJECT_BACKUP%" mkdir "%PROJECT_BACKUP%"
if not exist "%DATA_BACKUP%" mkdir "%DATA_BACKUP%"

echo ============================================================
echo STEP 1 OF 2 - BACKING UP AQSD PROJECT
echo ============================================================
echo.

robocopy "%PROJECT_SOURCE%" "%PROJECT_BACKUP%" /MIR /Z /FFT /R:2 /W:2 /XJ ^
 /XD ".git" ".venv" ".venv-fyers" "__pycache__" ".pytest_cache" ^
 "Backups" ^
 /XF "*.pyc" "*.pyo"

set "RC_PROJECT=%ERRORLEVEL%"

if %RC_PROJECT% GEQ 8 (
    echo.
    echo ERROR: Project backup failed.
    echo Robocopy Exit Code: %RC_PROJECT%
    goto :FAILED
)

echo.
echo Project backup completed successfully.
echo Robocopy Exit Code: %RC_PROJECT%
echo.

echo ============================================================
echo STEP 2 OF 2 - BACKING UP AQSD PRIMARY DATA
echo ============================================================
echo.

robocopy "%DATA_SOURCE%" "%DATA_BACKUP%" /MIR /Z /FFT /R:2 /W:2 /XJ

set "RC_DATA=%ERRORLEVEL%"

if %RC_DATA% GEQ 8 (
    echo.
    echo ERROR: Data backup failed.
    echo Robocopy Exit Code: %RC_DATA%
    goto :FAILED
)

echo.
echo Data backup completed successfully.
echo Robocopy Exit Code: %RC_DATA%
echo.

echo ============================================================
echo                    BACKUP SUCCESS
echo ============================================================
echo.
echo Project:
echo   %PROJECT_SOURCE%
echo       --^> %PROJECT_BACKUP%
echo.
echo Primary Data:
echo   %DATA_SOURCE%
echo       --^> %DATA_BACKUP%
echo.
echo AQSD backup architecture is protected.
echo ============================================================
echo.

pause
exit /b 0


:FAILED
echo.
echo ============================================================
echo                     BACKUP FAILED
echo ============================================================
echo.
echo No source data has been intentionally deleted.
echo Check the error shown above.
echo.
pause
exit /b 1