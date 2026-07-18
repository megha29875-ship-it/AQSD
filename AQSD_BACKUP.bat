@echo off
setlocal

title AQSD Backup Manager
color 0B

set "SOURCE=C:\Users\megha\AQSD"
set "DESTINATION=E:\Mirror\AQSD"
set "LOG_FOLDER=C:\Users\megha\AQSD\Logs"

if not exist "%LOG_FOLDER%" mkdir "%LOG_FOLDER%"
if not exist "%DESTINATION%" mkdir "%DESTINATION%"

for /f "tokens=1-4 delims=/-. " %%a in ("%date%") do (
    set "DATESTAMP=%%d-%%b-%%c"
)

for /f "tokens=1-3 delims=:., " %%a in ("%time%") do (
    set "TIMESTAMP=%%a-%%b-%%c"
)

set "LOG_FILE=%LOG_FOLDER%\AQSD_Backup_%DATESTAMP%_%TIMESTAMP%.log"

echo.
echo ======================================================
echo                 AQSD BACKUP MANAGER
echo ======================================================
echo.
echo Source      : %SOURCE%
echo Destination : %DESTINATION%
echo Log File    : %LOG_FILE%
echo Date        : %date%
echo Time        : %time%
echo.

echo Starting Robocopy backup...
echo.

robocopy "%SOURCE%" "%DESTINATION%" /MIR /Z /R:3 /W:5 /COPY:DAT /DCOPY:T /XJ /FFT /TEE /LOG:"%LOG_FILE%" ^
/XD ".git" ".venv" ".venv-fyers" "__pycache__" "Backup" "Backups" "Z-Back Ups" ^
/XF "*.pyc" "*.tmp" "*.log"

set "RC=%ERRORLEVEL%"

echo.
echo ======================================================
echo                  BACKUP RESULT
echo ======================================================

if %RC% LEQ 7 (
    color 0A
    echo Backup completed successfully.
    echo Robocopy exit code: %RC%
) else (
    color 0C
    echo Backup failed.
    echo Robocopy exit code: %RC%
    echo Please check the log file:
    echo %LOG_FILE%
)

echo.
echo ======================================================
echo              BACKUP OPERATION FINISHED
echo ======================================================
echo.

pause
endlocal