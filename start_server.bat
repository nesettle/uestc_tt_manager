@echo off
cd /d C:\Users\Theta\uestc_tt_manager
if exist .venv\Scripts\activate.bat (
  call .venv\Scripts\activate.bat
)
uvicorn app.main:app --host 127.0.0.1 --port 8050 --reload
