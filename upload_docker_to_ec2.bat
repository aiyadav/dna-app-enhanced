@echo off
echo === Uploading RSS Summarizer to EC2 for Docker Deployment ===

set EC2_IP=44.205.255.62
set KEY_FILE=openhands-key.pem

echo Uploading files to EC2...
scp -i %KEY_FILE% -r . ec2-user@%EC2_IP%:~/rss-summarizer/

echo Connecting to EC2 and deploying with Docker...
ssh -i %KEY_FILE% ec2-user@%EC2_IP% "cd ~/rss-summarizer && chmod +x docker_deploy.sh && ./docker_deploy.sh"

echo === Docker Deployment Complete ===
echo Application available at: http://%EC2_IP%:5000
pause