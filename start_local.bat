@echo off
echo ========================================
echo Starting Daily News AI Application
echo ========================================
echo.

REM Load IAM role and region from YAML config
for /f "tokens=2 delims=: " %%a in ('findstr "iam_role_name" ec2_service_role.yml') do set AWS_PROFILE=%%a
for /f "tokens=2 delims=: " %%a in ('findstr "default_region" ec2_service_role.yml') do set AWS_DEFAULT_REGION=%%a

echo AWS Profile: %AWS_PROFILE%
echo AWS Region: %AWS_DEFAULT_REGION%
echo.

REM Verify AWS credentials
echo Verifying AWS credentials...
aws sts get-caller-identity --profile %AWS_PROFILE% >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: AWS credentials not valid for profile %AWS_PROFILE%
    echo Please configure AWS credentials first
    pause
    exit /b 1
)
echo AWS credentials verified successfully!
echo.

REM Start the application
echo ========================================
echo Starting Flask Application...
echo ========================================
echo Application will be available at: http://localhost:5000
echo Press Ctrl+C to stop the server
echo.

python app.py
