# Developer Setup Guide

## Quick Start

```bash
pip install -r requirements.txt
python app.py
```

Works on both local and EC2 with the same `.env` file!

## How It Works

The app auto-detects the environment:
- **Local**: Uses `AWS_PROFILE` from `.env`
- **EC2**: Ignores `AWS_PROFILE`, uses instance IAM role automatically

Same `.env` file, zero configuration needed.
