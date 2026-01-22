# Quick Setup Guide

## For New Developers (Local Development)

1. Clone the repository
2. Run the setup script:
   ```bash
   setup_local.bat
   ```
3. Start the app:
   ```bash
   python app.py
   ```

That's it! The setup script automatically creates `.env.local` and `.env` for you.

## For EC2 Deployment

1. Clone the repository
2. The `.env` file is already configured for EC2
3. Make sure IAM role `devops-genai-dna-dev-engineer-role` is attached to EC2
4. Start the app:
   ```bash
   python app.py
   ```

## How It Works

- **Local**: Uses `USE_EC2_ROLE=false` and `AWS_PROFILE` from `.env.local`
- **EC2**: Uses `USE_EC2_ROLE=true` and IAM instance role (no profile needed)
- Same codebase works in both environments automatically!
