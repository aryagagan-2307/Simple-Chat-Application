@echo off
echo ============================================
echo   ChatApp - Windows Setup
echo ============================================
echo.
echo [1] Creating virtual environment...
python -m venv venv
if errorlevel 1 (
    echo ERROR: Python not found. Please install from python.org
    pause
    exit /b
)
echo [2] Activating virtual environment...
call venv\Scripts\activate.bat
echo [3] Installing all dependencies...
pip install flask==2.3.3 flask-socketio==5.3.6 python-socketio==5.11.2 python-engineio==4.9.1 Werkzeug==2.3.7 eventlet==0.36.1 requests==2.31.0 Pillow==10.3.0
echo.
echo ============================================
echo   Setup Complete!
echo   Run start_server.bat first
echo   Then run start_client.bat (open it twice)
echo ============================================
pause