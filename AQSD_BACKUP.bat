@echo off
title AQSD Backup Manager

echo.
echo ==========================================
echo         AQSD BACKUP STARTED
echo ==========================================
echo Date : %date%
echo Time : %time%
echo.

robocopy "C:\Users\megha\AQSD" "E:\Mirror\AQSD" ^
/MIR ^
/FFT ^
/R:2 ^
/W:2 ^
/XJ ^
/XD "__pycache__" ".venv" "Logs" ^
/XF "*.pyc" "*.tmp" "*.log" "~$*.xlsx" ^
/LOG+:"E:\Mirror\AQSD_Backup.log"

echo.
echo ==========================================
echo Backup Finished Successfully
echo Date : %date%
echo Time : %time%
echo ==========================================

pause