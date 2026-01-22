@echo off

REM Load IAM role from YAML config
for /f "tokens=2 delims=: " %%a in ('findstr "iam_role_name" ec2_service_role.yml') do set AWS_PROFILE=%%a

echo Starting application with AWS Profile: %AWS_PROFILE%
python app.py
