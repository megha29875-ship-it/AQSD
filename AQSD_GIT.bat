@echo off
title AQSD Git Manager

cd /d C:\Users\megha\AQSD

echo.
echo ==========================================
echo            AQSD GIT MANAGER
echo ==========================================
echo.

git status

echo.
set /p MSG=Enter Commit Message :

echo.
echo Adding files...
git add -A

echo.
echo Committing...
git commit -m "%MSG%"

echo.
echo Pushing to GitHub...
git push

echo.
echo ==========================================
echo        GIT OPERATION COMPLETED
echo ==========================================

pause