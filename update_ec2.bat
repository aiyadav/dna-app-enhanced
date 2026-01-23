@echo off
echo === Updating EC2 Application ===

set PROFILE=devops-genai-dna-dev-engineer-role
set REGION=us-east-1
set INSTANCE_ID=i-0f9ad702f1e04d899

echo Step 1: Pulling latest code...
aws ssm send-command --profile %PROFILE% --region %REGION% --instance-ids %INSTANCE_ID% --document-name "AWS-RunShellScript" --parameters "commands=['cd /home/ec2-user/dna-app-enhanced && git pull']" --output text --query "Command.CommandId" > temp_cmd.txt
set /p CMD_ID=<temp_cmd.txt

echo Waiting for git pull...
timeout /t 5 /nobreak > nul

echo Step 2: Restarting application...
aws ssm send-command --profile %PROFILE% --region %REGION% --instance-ids %INSTANCE_ID% --document-name "AWS-RunShellScript" --parameters "commands=['pkill -f \"python.*app.py\"', 'sleep 2', 'cd /home/ec2-user/dna-app-enhanced && nohup python3.11 app.py > nohup.out 2>&1 &', 'sleep 2', 'ps aux | grep app.py | grep -v grep']" --output text --query "Command.CommandId" > temp_cmd2.txt
set /p CMD_ID2=<temp_cmd2.txt

echo Waiting for restart...
timeout /t 5 /nobreak > nul

echo Step 3: Checking status...
aws ssm get-command-invocation --profile %PROFILE% --region %REGION% --command-id %CMD_ID2% --instance-id %INSTANCE_ID% --query "StandardOutputContent" --output text

del temp_cmd.txt temp_cmd2.txt

echo.
echo === Update Complete ===
echo Check application at: http://44.205.255.62:5000
pause
