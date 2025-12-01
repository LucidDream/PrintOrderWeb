@echo off

REM Activate virtual environment
call .venv\Scripts\activate.bat

echo Clearing Python cache...

REM Delete all __pycache__ directories
for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"

REM Delete all .pyc files
del /s /q *.pyc 2>nul

REM Delete .pytest_cache if it exists
if exist .pytest_cache rd /s /q .pytest_cache

REM Delete Flask session cache if it exists
if exist flask_session rd /s /q flask_session

echo Cache cleared successfully!
echo.
echo Starting Print Order Web application...
echo.

REM Start the Flask application
python app.py

pause
