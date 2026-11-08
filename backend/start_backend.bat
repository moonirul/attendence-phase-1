@echo off
cd /d "C:\Users\monir\Downloads\betopia-attendance-phase1\betopia-attendance-phase1\backend"

set BETOPIA_EXPECTED_EMPLOYEE=Md. Monirul Islam

call .venv\Scripts\activate.bat

uvicorn app.main:app --host 127.0.0.1 --port 8000
