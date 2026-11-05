@echo off
cd /d "%~dp0"

if not exist .venv\Scripts\python.exe (
    echo === Creating virtual environment ===
    py -3 -m venv .venv 2>nul || python -m venv .venv
    if not exist .venv\Scripts\python.exe (
        echo.
        echo ERROR: Python 3.11+ not found. Install it with:
        echo     winget install Python.Python.3.13
        echo then close this window and run run.bat again.
        goto :fail
    )
)

.venv\Scripts\python -c "import django, docx, openpyxl, fitz, PIL, whitenoise, waitress" 2>nul || (
    echo === Installing requirements ===
    .venv\Scripts\python -m pip install --upgrade pip
    .venv\Scripts\python -m pip install -r requirements.txt || (
        echo.
        echo ERROR: package install failed. Check the internet connection and run run.bat again.
        goto :fail
    )
)

.venv\Scripts\python manage.py migrate --noinput || goto :fail
.venv\Scripts\python manage.py load_sample || goto :fail
.venv\Scripts\python manage.py shell -c "import sys; from django.contrib.auth.models import User; sys.exit(0 if User.objects.exists() else 1)"
if errorlevel 1 (
    echo.
    echo === Create the first login account ===
    .venv\Scripts\python manage.py createsuperuser || goto :fail
)

start "" http://127.0.0.1:8000/
.venv\Scripts\python manage.py runserver 127.0.0.1:8000
goto :eof

:fail
echo.
pause
exit /b 1
