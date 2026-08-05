@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m pytest guards/ -q
    exit /b %errorlevel%
)
where python >nul 2>nul && (
    python -m pytest guards/ -q
    exit /b %errorlevel%
)
"%LOCALAPPDATA%\Programs\Python\Python312\python.exe" -m pytest guards/ -q
