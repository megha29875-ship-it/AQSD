@echo off
title AQSD Internal Backup

echo.
echo ==========================================
echo          AQSD INTERNAL BACKUP
echo ==========================================
echo.

set "SOURCE=C:\Users\megha\AQSD"
set "DEST=E:\AQSD_BACKUP"

echo Source      : %SOURCE%
echo Destination : %DEST%
echo.
echo Starting backup...
echo.

if not exist "%SOURCE%\" (
    echo ERROR: AQSD source folder not found.
    echo %SOURCE%
    echo.
    pause
    exit /b 1
)

if not exist "E:\" (
    echo ERROR: Drive E: is not available.
    echo.
    pause
    exit /b 1
)

if not exist "%DEST%\" (
    echo Creating backup folder...
    mkdir "%DEST%"
)

robocopy "%SOURCE%" "%DEST%" /E /COPY:DAT /DCOPY:DAT /R:2 /W:2 /XJ

set "RC=%ERRORLEVEL%"

echo.
echo ==========================================
echo             BACKUP FINISHED
echo ==========================================
echo.

if %RC% LEQ 7 (
    echo AQSD Internal Backup completed successfully.
    echo Robocopy Exit Code: %RC%
) else (
    echo WARNING: AQSD Internal Backup encountered errors.
    echo Robocopy Exit Code: %RC%
)

echo.
echo IMPORTANT:
echo This backup does NOT use MIRROR mode.
echo Files deleted from AQSD will NOT automatically
echo be deleted from this backup.
echo.
echo Backup Location:
echo %DEST%
echo.

pause