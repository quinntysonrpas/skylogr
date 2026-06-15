@echo off
echo ========================================
echo   Skylogr - Professional Flight Logging
echo ========================================
echo.
python app.py
if %errorlevel% neq 0 (
    echo.
    echo Skylogr exited with an error. See above for details.
    pause
)
