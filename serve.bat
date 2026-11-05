@echo off
rem Production-mode server on this PC (reachable from other computers on the network on port 8000).
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
    echo Run run.bat once first to set up the environment.
    pause
    exit /b 1
)
.venv\Scripts\python -m pip install -q -r requirements.txt || goto :fail
set DJANGO_DEBUG=0
if "%DJANGO_ALLOWED_HOSTS%"=="" set DJANGO_ALLOWED_HOSTS=*
.venv\Scripts\python manage.py migrate --noinput || goto :fail
.venv\Scripts\python manage.py collectstatic --noinput -v 0 || goto :fail
echo.
echo Serving on http://0.0.0.0:8000/  (Ctrl+C to stop)
.venv\Scripts\waitress-serve --listen=0.0.0.0:8000 --threads=8 --channel-timeout=300 oshms.wsgi:application
goto :eof

:fail
echo.
pause
exit /b 1
