@echo off
cd /d "D:\Private\attendence-phase-1\backend"
set "BETOPIA_EXPECTED_EMPLOYEE=Md. Monirul Islam"
call ".venv\Scripts\activate.bat"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
