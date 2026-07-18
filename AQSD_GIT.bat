@echo off
title AQSD Git Manager
color 0A

cd /d C:\Users\megha\AQSD

echo.
echo ======================================================
echo                 AQSD GIT MANAGER
echo ======================================================
echo.

echo Current Date : %date%
echo Current Time : %time%
echo.

echo Current Branch:
git branch --show-current

echo.
echo ======================================================
echo Current Git Status
echo ======================================================
git status

echo.
echo ======================================================
echo Adding All Files...
echo ======================================================
git add -A

echo.
echo ======================================================
echo Updated Git Status
echo ======================================================
git status

echo.
set /p MSG=Enter Commit Message :

echo.
echo ======================================================
echo Creating Commit...
echo ======================================================
git commit -m "%MSG%"

if errorlevel 1 (
    echo.
    echo **********************************************
    echo No new changes available to commit.
    echo **********************************************
    goto END
)

echo.
echo ======================================================
echo Pushing to GitHub...
echo ======================================================
git push

if errorlevel 1 (
    echo.
    echo **********************************************
    echo Push Failed.
    echo Please check your internet connection.
    echo **********************************************
    goto END
)

echo.
echo ======================================================
echo Latest Commit
echo ======================================================
git log -1 --oneline

echo.
echo ======================================================
echo          GIT OPERATION COMPLETED SUCCESSFULLY
echo ======================================================

:END
echo.
pause