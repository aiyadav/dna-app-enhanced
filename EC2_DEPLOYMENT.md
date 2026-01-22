# EC2 Deployment Guide

## Prerequisites

1. **EC2 Instance** (Ubuntu/Amazon Linux recommended)
2. **IAM Role** `devops-genai-dna-dev-engineer-role` attached to EC2
3. **Security Group** allowing inbound traffic on port 5000
4. **Python 3.11+** (for non-Docker) OR **Docker** (for Docker deployment)

## Setup Steps (Common for Both Options)

### 1. Attach IAM Role to EC2
```bash
# Attach the role: devops-genai-dna-dev-engineer-role
# This role already has Bedrock permissions
```

### 2. Clone Repository
```bash
git clone <your-repo-url>
cd Daily_News_Analysis-RSS_Summarizer/RSS_Summarizer
```

### 3. Create .env File
```bash
# Copy the EC2 template
cp .env.ec2 .env

# Generate a secure secret key
SECRET_KEY=$(openssl rand -hex 32)

# Update the .env file
sed -i "s/CHANGE_THIS_TO_RANDOM_KEY/$SECRET_KEY/" .env

# Verify the configuration
cat .env
```

Your `.env` file should look like:
```
AWS_DEFAULT_REGION=us-east-1
SECRET_KEY=<random-generated-key>
RSS_SCHEDULE_HOUR=9
RSS_SCHEDULE_MINUTE=0
```

**Important**: Do NOT set `AWS_PROFILE` on EC2. The app will automatically use the IAM role.

---

## Option 1: Direct Python Deployment (Recommended)

### Advantages:
- ✅ Simpler and faster
- ✅ Easier to debug
- ✅ Direct access to logs
- ✅ Less resource overhead

### Installation

```bash
# Install Python 3.11 (if not already installed)
sudo apt update
sudo apt install python3.11 python3.11-venv python3-pip -y

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Start Application

```bash
# Run directly
python app.py
```

### Run as Background Service (Recommended for Production)

Create systemd service:

```bash
sudo nano /etc/systemd/system/news-app.service
```

Add this content:

```ini
[Unit]
Description=Daily News AI Assistant
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/Daily_News_Analysis-RSS_Summarizer/RSS_Summarizer
Environment="PATH=/home/ubuntu/Daily_News_Analysis-RSS_Summarizer/RSS_Summarizer/venv/bin"
ExecStart=/home/ubuntu/Daily_News_Analysis-RSS_Summarizer/RSS_Summarizer/venv/bin/python app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable news-app
sudo systemctl start news-app
```

### Manage Service

```bash
# Check status
sudo systemctl status news-app

# View logs
sudo journalctl -u news-app -f

# Restart
sudo systemctl restart news-app

# Stop
sudo systemctl stop news-app
```

---

## Option 2: Docker Deployment

### Advantages:
- ✅ Containerized environment
- ✅ Easy to scale
- ✅ Consistent across environments
- ✅ Isolated dependencies

### Installation

```bash
# Install Docker
sudo apt update
sudo apt install docker.io docker-compose -y

# Start Docker service
sudo systemctl start docker
sudo systemctl enable docker

# Add user to docker group (optional, to run without sudo)
sudo usermod -aG docker $USER
newgrp docker
```

### Start Application

```bash
# Build and start
docker-compose up -d
```

### Manage Docker Application

```bash
# Check status
docker-compose ps

# View logs
docker-compose logs -f

# Restart
docker-compose restart

# Stop
docker-compose down

# Rebuild after code changes
docker-compose down
docker-compose build
docker-compose up -d
```

---

## Verification (Both Options)

### Test Application
```bash
curl http://localhost:5000
```

### Verify IAM Role
```bash
# This should return the role name
curl http://169.254.169.254/latest/meta-data/iam/security-credentials/
```

### Test AWS Credentials
```bash
# For Python deployment
source venv/bin/activate
python -c "import boto3; print(boto3.client('sts').get_caller_identity())"

# For Docker deployment
docker-compose exec rss-summarizer python -c "import boto3; print(boto3.client('sts').get_caller_identity())"
```

### Access Application
```
http://<ec2-public-ip>:5000
```

## Troubleshooting

### Verify IAM Role is Attached
```bash
# This should return the role name
curl http://169.254.169.254/latest/meta-data/iam/security-credentials/
```

### Check Bedrock Permissions
```bash
# Test Bedrock access
aws bedrock list-foundation-models --region us-east-1
```

### Port Not Accessible
- Update EC2 security group to allow inbound TCP 5000
- Or use nginx reverse proxy on port 80/443

### Database Permissions
```bash
chmod 666 news.db
```

## Production Setup

### 1. Use Nginx Reverse Proxy
```bash
sudo apt install nginx
```

```nginx
# /etc/nginx/sites-available/news-app
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

### 2. Enable and Start
```bash
sudo ln -s /etc/nginx/sites-available/news-app /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 3. Add SSL (Optional)
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

## Monitoring

```bash
# Application logs
docker-compose logs --tail=100 -f

# Resource usage
docker stats

# Application health
curl http://localhost:5000/
```

## Backup

```bash
# Backup database
cp news.db news.db.backup.$(date +%Y%m%d)

# Automated daily backup
echo "0 2 * * * cd /path/to/app && cp news.db news.db.backup.\$(date +\%Y\%m\%d)" | crontab -
```

## Updates

```bash
# Pull latest changes
git pull

# Rebuild and restart
docker-compose down
docker-compose build
docker-compose up -d
```
