@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
    py -3 -m venv .venv
    .venv\Scripts\python -m pip install -r requirements.txt
)
.venv\Scripts\python manage.py migrate --noinput
.venv\Scripts\python manage.py load_sample
.venv\Scripts\python manage.py shell -c "import sys; from django.contrib.auth.models import User; sys.exit(0 if User.objects.exists() else 1)"
if errorlevel 1 (
    echo.
    echo === Create the first login account ===
    .venv\Scripts\python manage.py createsuperuser
)
start "" http://127.0.0.1:8000/
.venv\Scripts\python manage.py runserver 127.0.0.1:8000
