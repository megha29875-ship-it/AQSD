@echo off
title AQSD Option Intelligence

cd /d C:\Users\megha\AQSD

call .venv-fyers\Scripts\activate.bat

python -m Scripts.option_intelligence.option_intelligence_control_center

exit