@echo off
echo ========================================
echo Setting up local development environment
echo ========================================
echo.

REM Check if .env.local already exists
if exist .env.local (
    echo .env.local already exists. Skipping...
) else (
    echo Creating .env.local from template...
    copy .env.local.example .env.local
    echo [OK] .env.local created
)

REM Copy .env.local to .env for local use
echo Copying .env.local to .env for local development...
copy /Y .env.local .env
echo [OK] .env configured for local development

echo.
echo ========================================
echo Setup complete!
echo ========================================
echo.
echo You can now run: python app.py
echo.
pause
