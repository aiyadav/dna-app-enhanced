#!/bin/bash

# Docker deployment script for EC2
set -e

echo "=== Docker Deployment for RSS Summarizer ==="

# Install Docker if not present
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    sudo yum update -y
    sudo yum install -y docker
    sudo systemctl start docker
    sudo systemctl enable docker
    sudo usermod -a -G docker ec2-user
fi

# Install Docker Compose if not present
if ! command -v docker-compose &> /dev/null; then
    echo "Installing Docker Compose..."
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
fi

# Create data directory
mkdir -p data

# Set AWS credentials (you'll need to set these)
echo "Setting up environment variables..."
cat > .env << EOF
AWS_ACCESS_KEY_ID=your_access_key_here
AWS_SECRET_ACCESS_KEY=your_secret_key_here
AWS_DEFAULT_REGION=us-east-1
EOF

echo "Please edit .env file with your actual AWS credentials"

# Build and run the container
echo "Building Docker image..."
docker-compose build

echo "Starting RSS Summarizer container..."
docker-compose up -d

echo "=== Deployment Complete ==="
echo "Application will be available at: http://44.205.255.62:5000"
echo "To view logs: docker-compose logs -f"
echo "To stop: docker-compose down"