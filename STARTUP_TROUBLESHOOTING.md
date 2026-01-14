# Startup Troubleshooting Guide

## Problem
Service builds successfully but healthcheck fails - no startup logs visible.

## Root Cause Analysis

The fact that **NO logs appear** from `start.sh` suggests:
1. Script crashes before first `echo` statement
2. Output buffering prevents logs from appearing
3. Railway isn't capturing stdout/stderr properly
4. Django import fails silently during WSGI loading

## Fixes Applied

### 1. **Removed `set -e`** ✅
- Changed to `set +e` so we can see WHERE failures occur
- Script won't exit immediately on first error

### 2. **Explicit Logging** ✅
- All `echo` statements now use `>&2` to force stderr output
- Railway captures stderr better than stdout
- Added `PYTHONUNBUFFERED=1` for immediate Python output

### 3. **Detailed Error Tracking** ✅
- Each step now captures exit codes
- Django import test prints full traceback on failure
- Better error messages at each stage

### 4. **Increased Healthcheck Timeout** ✅
- Changed from 300s (5 min) to 600s (10 min)
- Gives more time for Django to start if it's slow

### 5. **Debug Logging** ✅
- Changed Gunicorn log level to `debug`
- More verbose output to see what's happening

## What to Check After Next Deploy

### 1. **Look for Startup Logs**
You should now see:
```
================================
STARTING DEPLOYMENT
================================
Current directory: /app
Python path: /opt/venv/bin/python
Python version: Python 3.11.x
Running environment check...
================================
ENVIRONMENT VARIABLE CHECK
================================
...
```

### 2. **If You See Environment Check Logs**
- ✅ Good: Script is running
- Check if it passes or fails
- Look for missing required variables

### 3. **If You See Django Import Error**
- Look for the traceback
- Common causes:
  - Missing environment variable
  - Database connection issue
  - Import error in settings.py
  - Module-level code requiring GEMINI_KEY

### 4. **If Still No Logs**
- Railway might not be running `start.sh` at all
- Check Railway dashboard → Service → Settings → Start Command
- Should be: `bash start.sh`

## Common Issues & Solutions

### Issue: "Environment check failed"
**Solution:** 
- Verify `DATABASE_URL` and `DJANGO_SECRET_KEY` are set
- Copy from working cron service

### Issue: "Django failed to load"
**Solution:**
- Check the traceback in logs
- Common causes:
  - Database connection string invalid
  - Missing required environment variable
  - Import error in `_1nbox_ai/settings.py`

### Issue: "Gunicorn won't start"
**Solution:**
- Check if port is available
- Verify Django WSGI application loads
- Check for module-level imports that fail

### Issue: "Healthcheck times out"
**Solution:**
- Service might be starting but too slow
- Check if `/health/` endpoint is accessible
- Verify Gunicorn is actually running

## Nuclear Option: Disable Healthcheck Temporarily

If you need to see what's happening without healthcheck interference:

1. **Temporarily remove healthcheck** in `railway.json`:
```json
"deploy": {
  "startCommand": "bash start.sh",
  "restartPolicyType": "ON_FAILURE",
  "restartPolicyMaxRetries": 10
}
```

2. **Deploy and check logs** - service will start without healthcheck

3. **Manually test** `/health/` endpoint once service is running

4. **Re-enable healthcheck** once you've fixed the issue

## Next Steps

1. **Deploy** and watch logs carefully
2. **Look for** the new detailed logging output
3. **Identify** where exactly it's failing
4. **Fix** the specific issue based on error message
5. **Re-deploy** and verify

## If Still Not Working

1. **Compare with Cron Service:**
   - Copy ALL environment variables from cron service to web service
   - Verify they're identical

2. **Check Railway Logs:**
   - Look for ANY output from start.sh
   - Even errors should now be visible

3. **Test Locally:**
   - Run `bash start.sh` locally with same environment variables
   - See if it works locally

4. **Contact Railway Support:**
   - If logs still don't appear, might be Railway issue
   - Provide them with service ID and deployment logs

