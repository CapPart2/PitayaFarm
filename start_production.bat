@echo off
REM PITAYA Backend - Production Startup Script for Windows
REM This script starts the Flask API with Gunicorn for production deployment

REM Load environment variables from .env file if it exists
if exist .env (
    for /f "tokens=*" %%a in (.env) do (
        set %%a
    )
)

REM Default values if not set in .env
if "%HOST%"=="" set HOST=0.0.0.0
if "%PORT%"=="" set PORT=5000
if "%WORKERS%"=="" set WORKERS=4
if "%WORKER_CLASS%"=="" set WORKER_CLASS=sync
if "%TIMEOUT%"=="" set TIMEOUT=120
if "%LOG_LEVEL%"=="" set LOG_LEVEL=info

echo Starting PITAYA Backend with Gunicorn...
echo Host: %HOST%
echo Port: %PORT%
echo Workers: %WORKERS%
echo Worker Class: %WORKER_CLASS%
echo Timeout: %TIMEOUT%
echo Log Level: %LOG_LEVEL%

REM Start Gunicorn
gunicorn app:app --bind %HOST%:%PORT% --workers %WORKERS% --worker-class %WORKER_CLASS% --timeout %TIMEOUT% --log-level %LOG_LEVEL% --access-logfile - --error-logfile - --capture-output --enable-stdio-inheritance

pause
