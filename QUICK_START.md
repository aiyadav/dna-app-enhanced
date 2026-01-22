# Quick Start Guide - Enterprise UI

## ✅ AWS Connection Verified!

Your AWS Bedrock connection is working correctly with profile: `devops-genai-dna-dev-engineer-role`

## Starting the Application

### Option 1: Using the Batch File (Recommended)
```cmd
start_local.bat
```

### Option 2: Manual Start
```cmd
set AWS_PROFILE=devops-genai-dna-dev-engineer-role
set AWS_DEFAULT_REGION=us-east-1
python app.py
```

### Option 3: PowerShell
```powershell
$env:AWS_PROFILE="devops-genai-dna-dev-engineer-role"
$env:AWS_DEFAULT_REGION="us-east-1"
python app.py
```

## Access the Application

Once started, open your browser to:
- **Dashboard**: http://localhost:5000/dashboard
- **Admin Panel**: http://localhost:5000/admin

## What's New in Enterprise UI

### 🎨 Visual Improvements
- Professional FRB-branded color scheme
- Modern card-based layouts
- Gradient backgrounds and shadows
- Smooth animations and transitions
- Responsive design for all devices

### 📊 Dashboard Enhancements
- Stats card with total articles
- Color-coded category navigation
- Enhanced article cards with better typography
- Improved metadata display with icons
- Better action buttons and toolbars

### ⚙️ Admin Panel Improvements
- Sidebar navigation with icons
- Better form layouts
- Enhanced table displays
- Color-coded status badges
- Streamlined configuration

### 🔔 User Experience
- Toast notifications (no more alert dialogs!)
- Better loading states
- Improved button grouping
- Better visual feedback
- Mobile-optimized navigation

## Testing the UI

1. **Start the application** using one of the methods above
2. **Go to Admin Panel** (http://localhost:5000/admin)
3. **Add RSS Feeds** - Try adding a few news feeds
4. **Configure Categories** - Set up your news categories with colors
5. **Add Topics** - Define topics with keywords
6. **Refresh News** - Click the "Actions" dropdown in navbar → "Refresh News"
7. **View Dashboard** - See your articles organized by category

## Troubleshooting

### If you see AWS credential errors:
1. Make sure you set the environment variable BEFORE starting Python:
   ```cmd
   set AWS_PROFILE=devops-genai-dna-dev-engineer-role
   ```

2. Verify it's set:
   ```cmd
   echo %AWS_PROFILE%
   ```

3. Test AWS connection:
   ```cmd
   python test_aws_connection.py
   ```

### If CSS doesn't load:
1. Clear browser cache (Ctrl + F5)
2. Check that `static/css/enterprise.css` exists
3. Restart the Flask application

### If you see layout issues:
1. Ensure you're using a modern browser (Chrome, Firefox, Edge, Safari)
2. Check browser console for JavaScript errors (F12)
3. Verify all template files were updated

## Key Files Modified

### New Files:
- `static/css/enterprise.css` - Enterprise styling
- `test_aws_connection.py` - AWS connection tester
- `start_local.bat` - Easy startup script
- `ENTERPRISE_UI_README.md` - Full documentation
- `QUICK_START.md` - This file

### Updated Templates:
- `templates/base.html` - New navbar with toast notifications
- `templates/dashboard.html` - Enhanced dashboard layout
- `templates/admin_base.html` - Improved admin navigation
- `templates/admin_feeds.html` - Better feed management
- `templates/admin_categories.html` - Enhanced category management
- `templates/admin_topics.html` - Improved topic configuration

### Updated Configuration:
- `.env` - Now uses AWS_PROFILE instead of access keys
- `app.py` - Better environment variable handling

## Next Steps

1. ✅ Start the application
2. ✅ Configure your feeds and categories in Admin Panel
3. ✅ Refresh news to see the new UI in action
4. ✅ Explore the enhanced dashboard
5. ✅ Test the toast notifications
6. ✅ Try the mobile responsive design

## Support

For issues or questions:
- Check `ENTERPRISE_UI_README.md` for detailed documentation
- Run `python test_aws_connection.py` to verify AWS setup
- Check Flask console output for error messages

---

**Ready to start!** Run `start_local.bat` or set AWS_PROFILE and run `python app.py`
