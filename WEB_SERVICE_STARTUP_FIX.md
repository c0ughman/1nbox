# Web Service Startup Fix

## Problem
The main web service was crashing on startup, causing healthcheck failures. The cron service deployed fine, but the web service couldn't start.

## Root Cause
1. **Environment Variable Check**: The startup script was too strict - `GEMINI_KEY` was being checked but it's only needed when actually using the Gemini API, not at startup
2. **Missing Error Visibility**: Errors during Django startup weren't being caught early enough
3. **No Django Import Test**: Django import errors weren't being detected before Gunicorn started

## Fixes Applied

### 1. Made GEMINI_KEY Optional ✅
- `GEMINI_KEY` is now optional in environment checks
- Only `DATABASE_URL` and `DJANGO_SECRET_KEY` are required for Django to start
- API keys are checked but won't prevent startup if missing

### 2. Improved Error Logging ✅
- Added environment variable status logging before Gunicorn starts
- Added Django import test to catch errors early
- Better error messages to help diagnose issues

### 3. Added Django Import Test ✅
- Tests Django import before starting Gunicorn
- Catches configuration errors early
- Provides clear error messages if Django fails to load

## What Changed

### `test_env.py`
- Made `GEMINI_KEY`, `OPENAI_KEY`, `SENDGRID_API_KEY` optional (warnings instead of errors)
- Only `DATABASE_URL` and `DJANGO_SECRET_KEY` are required
- Better categorization of variables (required vs optional vs API keys)

### `start.sh`
- Added environment variable status logging
- Added Django import test before Gunicorn starts
- Removed `--preload` flag (can cause issues with Django)
- Better error messages

## Next Steps

### 1. Verify Environment Variables in Railway
Make sure your **web service** has these environment variables set:

**REQUIRED (service won't start without these):**
- `DATABASE_URL`
- `DJANGO_SECRET_KEY`

**OPTIONAL (features won't work without these, but service will start):**
- `GEMINI_KEY` - For Gemini API features
- `OPENAI_KEY` - For OpenAI features  
- `SENDGRID_API_KEY` - For email features
- `FIREBASE_PROJECT_ID`, `FIREBASE_PRIVATE_KEY`, `FIREBASE_CLIENT_EMAIL` - For Firebase auth

### 2. Check Railway Logs
After redeploying, check the logs for:
- Environment variable status messages
- Django import test results
- Any error messages during startup

### 3. Compare Web Service vs Cron Service
The cron service worked fine, so compare:
- Environment variables between web service and cron service
- Make sure web service has all the same variables as cron service

## Expected Startup Logs

You should now see:
```
================================
STARTING DEPLOYMENT
================================
Running environment check...
================================
ENVIRONMENT VARIABLE CHECK
================================

REQUIRED VARIABLES (Django startup):
✓ DATABASE_URL: postgresql://...
✓ DJANGO_SECRET_KEY: ...

API KEYS (needed for specific features):
✓ GEMINI_KEY: ...
⚠ OPENAI_KEY: NOT SET (optional)
...

Starting Gunicorn on port 8000...
Environment variables available:
  - DATABASE_URL: SET
  - DJANGO_SECRET_KEY: SET
  - GEMINI_KEY: SET
  - PORT: 8000
Testing Django import...
✓ Django loaded successfully
Starting Gunicorn server...
[INFO] Starting gunicorn 23.0.0
...
```

## If Service Still Fails

1. **Check Railway Logs** - Look for the error message after "Testing Django import..."
2. **Verify Environment Variables** - Make sure `DATABASE_URL` and `DJANGO_SECRET_KEY` are set in the web service
3. **Compare with Cron Service** - Copy all environment variables from the working cron service to the web service
4. **Check Database Connection** - Verify `DATABASE_URL` is correct and database is accessible

## Key Difference: Web Service vs Cron Service

- **Cron Service**: Runs a Django management command and exits (doesn't need to pass healthcheck)
- **Web Service**: Starts Gunicorn server that must respond to healthcheck requests

The web service needs to:
1. Start successfully
2. Respond to `/health/` endpoint
3. Stay running

The cron service only needs to:
1. Start successfully
2. Run the command
3. Exit

This is why the cron service worked but the web service didn't - the web service has more requirements.

