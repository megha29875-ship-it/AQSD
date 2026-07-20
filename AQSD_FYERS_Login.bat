@echo off
title AQSD FYERS LOGIN

cd /d C:\Users\megha\AQSD

call .venv-fyers\Scripts\activate.bat

python -m Scripts.option_intelligence.fyers_token_assistant

pause