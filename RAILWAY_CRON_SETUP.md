# Railway Cron Job Setup Guide

## Overview
This guide explains how to set up and test cron jobs on Railway for the Briefed news processing system.

## The Problem (Before)
- Railway cron jobs were running `start.sh`, which starts Gunicorn (a web server)
- Gunicorn runs indefinitely and never executes the management command
- No news processing was happening

## The Solution (After)
- Created `run-cron.sh` - a dedicated script for cron jobs
- Cron jobs now execute the management command and exit properly
- Added `--force` flag for testing without time restrictions

---

## How the News Processing Works

### Time-Based Execution Flow
1. **Cron job runs** → Executes `python manage.py runnews`
2. **Command checks current UTC time** → Converts to each organization's timezone
3. **Time matching** → Only processes orgs where local time = (summary_time - 30 minutes)
4. **Processing** → Fetches articles, clusters them, generates summaries

### Example
- Organization: "Acme Corp"
- Timezone: "America/New_York" (EST)
- Summary Time: 09:00 AM EST
- **Cron must run at: 08:30 AM EST** (30 minutes before summary time)

### Why This Matters
The cron job runs EVERY hour, but only processes organizations whose scheduled time matches. This means:
- If you have orgs with summary_time at 9:00 AM, 10:00 AM, 11:00 AM, etc.
- The hourly cron will catch each one at the right time
- **Testing requires the `--force` flag** to bypass time checks

---

## Railway Configuration

### Step 1: Set Up Cron Job Service in Railway

1. **Go to your Railway project**
2. **Click "New" → "Cron Job"**
3. **Configure the cron job:**

   **Name:** `news-processing-cron`
   
   **Schedule:** Every hour
   ```
   0 * * * *
   ```
   
   **Command:**
   ```bash
   bash run-cron.sh runnews
   ```
   
   **OR for testing (bypasses time checks):**
   ```bash
   bash run-cron.sh runnews --force
   ```

4. **Set Environment Variables:**
   - Copy ALL environment variables from your web service
   - Required variables:
     - `DATABASE_URL`
     - `DJANGO_SECRET_KEY`
     - `OPENAI_API_KEY`
     - `GEMINI_API_KEY`
     - `SENDGRID_API_KEY`
     - `FIREBASE_PROJECT_ID`
     - `FIREBASE_PRIVATE_KEY`
     - `FIREBASE_CLIENT_EMAIL`
     - Any other custom variables

5. **Set Working Directory:** `/app` (should be automatic)

---

## Testing the Cron Job

### Option 1: Force Mode (Recommended for Testing)
This bypasses all time checks and processes ALL organizations:

**In Railway:**
- Command: `bash run-cron.sh runnews --force`
- Click "Run Now"

**Expected Output:**
```
================================
STARTING CRON JOB
================================
Running environment check...
✓ DATABASE_URL: postgresql://...
Running database migrations...
Operations to perform:
  No migrations to apply.
================================
EXECUTING MANAGEMENT COMMAND
================================
Running: python manage.py runnews
Starting news processing...
⚠️  FORCE MODE: Processing ALL organizations, bypassing time checks
==== Starting process_all_topics ====
Current UTC Time: 16:30
⚠️  FORCE MODE ENABLED: Processing ALL organizations, bypassing time checks
🔄 Processing organization: Test Org
... (processing details) ...
News processing completed successfully.
================================
CRON JOB COMPLETED
================================
```

### Option 2: Time-Based Mode (Production)
This only processes orgs at their scheduled time:

**In Railway:**
- Command: `bash run-cron.sh runnews`
- Click "Run Now"

**Expected Output (if no orgs match current time):**
```
================================
STARTING CRON JOB
================================
...
==== Starting process_all_topics ====
Current UTC Time: 16:30
Org: Test Org | Local Now: 11:30 | Expected Run Time: 08:30
❌ Skipping Test Org - Time did not match
No organizations matched the time check. Exiting.
================================
CRON JOB COMPLETED
================================
```

---

## Other Cron Jobs

### Email Summaries (`runmessage`)
Sends email summaries to users:

**Command:**
```bash
bash run-cron.sh runmessage
```

**Schedule:** Every hour (or match your email sending time)

### Bites Digests (`runbites`)
Processes Bites subscriptions:

**Command:**
```bash
bash run-cron.sh runbites
```

**Schedule:** Every 5 minutes (or as needed)

---

## Monitoring and Debugging

### 1. Check Cron Job Logs in Railway
- Go to your cron job service
- Click "Logs"
- Look for the execution output

### 2. Common Issues

**Issue: "Command not found: python"**
- **Fix:** The container uses `python` (not `python3`)
- The Railway Python environment sets `python` as the default

**Issue: "No organizations matched the time check"**
- **Fix:** Use `--force` flag for testing
- **Or:** Check that organizations have `summary_time` and `summary_timezone` set
- **Or:** Wait until the actual scheduled time

**Issue: "Environment check failed"**
- **Fix:** Ensure all environment variables are copied to the cron service

**Issue: "Database connection error"**
- **Fix:** Verify `DATABASE_URL` is set correctly
- **Fix:** Ensure database service is linked to cron service

### 3. Manual Testing from Railway CLI
```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Run command manually
railway run python manage.py runnews --force
```

---

## Production Setup

### Recommended Cron Schedule

**News Processing:**
```
0 * * * *  (Every hour)
Command: bash run-cron.sh runnews
```

**Email Summaries:**
```
0 * * * *  (Every hour)
Command: bash run-cron.sh runmessage
```

**Bites Digests:**
```
*/5 * * * *  (Every 5 minutes)
Command: bash run-cron.sh runbites
```

### Important Notes
1. **Don't use `--force` in production** - it bypasses time checks
2. **Ensure all env vars are set** - cron containers are separate from web containers
3. **Monitor logs regularly** - check for errors or skipped organizations
4. **Test timezone handling** - verify organizations in different timezones are processed correctly

---

## Files Modified/Created

### New Files
- `run-cron.sh` - Dedicated cron execution script

### Modified Files
- `_1nbox_ai/management/commands/runnews.py` - Added `--force` flag
- `_1nbox_ai/news.py` - Added force parameter to `process_all_topics()`

### Unchanged Files
- `start.sh` - Still used for web service (Gunicorn)
- `railway.json` - Only defines web service configuration

---

## Summary

✅ **Web Service:** Uses `start.sh` → Starts Gunicorn → Runs indefinitely
✅ **Cron Jobs:** Use `run-cron.sh` → Runs management command → Exits

The key insight: **Cron jobs need a different startup process** than web services!

