# Cron Job Fix - Summary

## 🎯 The Core Problem

When you clicked "Run" on Railway's cron job, it was executing `start.sh`, which:
1. ✅ Ran environment checks
2. ✅ Collected static files  
3. ✅ Ran database migrations
4. ❌ **Started Gunicorn** (a web server that runs indefinitely)
5. ❌ **Never executed the `runnews` command**

**Result:** The cron job would start a web server and run forever, never processing any news.

---

## 🔧 What Was Changed

### 1. Created `run-cron.sh`
**Purpose:** A dedicated startup script for cron jobs that executes commands and exits.

**What it does:**
```bash
#!/bin/bash
# 1. Run environment check
# 2. Run migrations (if needed)
# 3. Execute the management command (runnews, runmessage, or runbites)
# 4. Exit (does NOT start Gunicorn)
```

**Usage:**
```bash
bash run-cron.sh runnews         # Normal mode (time-based)
bash run-cron.sh runnews --force # Force mode (bypasses time checks)
bash run-cron.sh runmessage      # Email summaries
bash run-cron.sh runbites        # Bites digests
```

### 2. Modified `_1nbox_ai/management/commands/runnews.py`
**Added:** `--force` flag for testing

**Why:** The news processing only runs for organizations where the current time exactly matches their scheduled time (30 minutes before `summary_time`). For testing, you need to bypass this check.

**Usage:**
```bash
python manage.py runnews         # Only processes orgs at scheduled time
python manage.py runnews --force # Processes ALL organizations immediately
```

### 3. Modified `_1nbox_ai/news.py`
**Added:** `force` parameter to `process_all_topics()` function

**What it does:**
- When `force=True`: Processes ALL organizations, ignoring time checks
- When `force=False` (default): Only processes organizations at their scheduled time

### 4. Created Documentation
- `RAILWAY_CRON_SETUP.md` - Comprehensive guide with technical details
- `RAILWAY_QUICK_START.md` - Quick reference for Railway setup
- `CRON_FIX_SUMMARY.md` - This file

### 5. Updated `railway.json`
**Added:** Comment documenting that cron jobs use different command

---

## 🧠 How It Works Now

### The Complete Workflow

```
Railway Cron Trigger
        ↓
bash run-cron.sh runnews --force
        ↓
1. Environment check (test_env.py)
        ↓
2. Database migrations
        ↓
3. python manage.py runnews --force
        ↓
4. Django loads settings
        ↓
5. Command instantiated → handle() called
        ↓
6. process_all_topics(force=True) called
        ↓
7. If force=True:
   - Get ALL organizations (not inactive)
   - Skip time checking
   - Process all immediately
   
   If force=False (production):
   - Get ALL organizations (not inactive)
   - Check current UTC time
   - Convert to each org's timezone
   - Only process orgs where:
     local_time == (summary_time - 30 minutes)
        ↓
8. For each valid organization:
   - Delete old comments
   - Delete old summaries (>7 days)
   - Get all topics for organization
        ↓
9. For each topic:
   - Fetch articles from RSS feeds
   - Cluster articles by similarity
   - Generate AI summaries
   - Save to database
        ↓
10. Log results and exit
        ↓
Container terminates (job complete)
```

### Time-Based Processing Example

**Organization Setup:**
- Name: "Acme Corp"
- Timezone: "America/New_York" (EST, UTC-5)
- Summary Time: 09:00 AM EST

**Expected Behavior:**
- Cron runs every hour: 8:00, 9:00, 10:00, 11:00...
- At 8:30 AM EST (13:30 UTC):
  - Current UTC: 13:30
  - Org local time: 08:30 EST
  - Expected run time: 08:30 EST (9:00 - 0:30)
  - ✅ **Match! Process this organization**
- At 9:30 AM EST (14:30 UTC):
  - Current UTC: 14:30
  - Org local time: 09:30 EST
  - Expected run time: 08:30 EST
  - ❌ **No match. Skip this organization**

---

## 🚀 Railway Setup (Step by Step)

### What You Need to Do

1. **Create Cron Job Service in Railway:**
   - Click "New" → "Cron Job"
   - Name: `news-processing-cron`

2. **Set Command:**
   ```bash
   bash run-cron.sh runnews --force
   ```
   (Use `--force` for testing, remove for production)

3. **Set Schedule:**
   ```
   0 * * * *
   ```
   (Every hour at minute 0)

4. **Copy Environment Variables:**
   From web service to cron service:
   - `DATABASE_URL` ⚠️ **CRITICAL**
   - `DJANGO_SECRET_KEY` ⚠️ **CRITICAL**
   - `OPENAI_API_KEY`
   - `GEMINI_API_KEY`
   - `SENDGRID_API_KEY`
   - `FIREBASE_PROJECT_ID`
   - `FIREBASE_PRIVATE_KEY`
   - `FIREBASE_CLIENT_EMAIL`

5. **Click "Run Now" to Test**

---

## ✅ Expected Output

### With `--force` Flag (Testing)
```
================================
STARTING CRON JOB
================================
Running environment check...
✓ DATABASE_URL: postgresql://postgres:...
✓ DJANGO_SECRET_KEY: mBXj...
...
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
🗑️ Deleted comments for organization: Test Org
🗑️ Deleted 5 old summaries for organization: Test Org
📥 Processing topic: Technology News
   Fetched 47 articles from 3 sources
   Created 4 clusters
   Generated summaries
✅ Completed: Test Org (processed 3 topics)
News processing completed successfully.
================================
CRON JOB COMPLETED
================================
```

### Without `--force` Flag (Production)
If no organizations match the current time:
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

If organizations match:
```
...
==== Starting process_all_topics ====
Current UTC Time: 13:30
Org: Test Org | Local Now: 08:30 | Expected Run Time: 08:30
✅ Running process for Test Org (Time Matched)
🔄 Processing organization: Test Org
[... processing details ...]
```

---

## 🔍 Debugging Guide

### Issue: No output at all
**Cause:** Wrong command in Railway  
**Fix:** Ensure command is `bash run-cron.sh runnews`, NOT `bash start.sh`

### Issue: "Command not found: bash" or "Command not found: python"
**Cause:** Command syntax error  
**Fix:** Use exactly: `bash run-cron.sh runnews --force`

### Issue: "DATABASE_URL environment variable is required"
**Cause:** Environment variables not set in cron service  
**Fix:** Copy ALL env vars from web service to cron service

### Issue: "No organizations matched the time check"
**Cause:** No organizations scheduled for current time (normal in production)  
**Fix:** Use `--force` flag for testing, or check organization `summary_time` settings

### Issue: Gunicorn starts and job never completes
**Cause:** Using `start.sh` instead of `run-cron.sh`  
**Fix:** Change command to `bash run-cron.sh runnews`

---

## 📊 Key Differences

| Aspect | Web Service (`start.sh`) | Cron Job (`run-cron.sh`) |
|--------|-------------------------|--------------------------|
| **Purpose** | Serve HTTP requests | Execute scheduled tasks |
| **Process** | Gunicorn (web server) | Management command |
| **Duration** | Runs indefinitely | Executes and exits |
| **Restart** | On failure | No restart |
| **Port** | Binds to 8080 | No port binding |
| **Healthcheck** | `/health/` endpoint | No healthcheck |

---

## 🎓 What You Learned

1. **Cron jobs need different startup scripts** than web services
2. **Time-based processing** requires exact time matching (or force flag)
3. **Environment variables** must be duplicated across Railway services
4. **Container lifecycle** matters - cron jobs should exit after completing
5. **Logging is crucial** for debugging scheduled tasks

---

## 📝 Files You Need to Deploy

These files should be in your repository and deployed to Railway:

✅ `run-cron.sh` - New file (executable)  
✅ `_1nbox_ai/management/commands/runnews.py` - Modified  
✅ `_1nbox_ai/news.py` - Modified  
✅ `railway.json` - Updated with comment  
✅ `RAILWAY_CRON_SETUP.md` - New documentation  
✅ `RAILWAY_QUICK_START.md` - New quick reference  
✅ `CRON_FIX_SUMMARY.md` - This file  

Unchanged:
- `start.sh` - Still used for web service
- All other application code

---

## 🚀 Next Steps

1. **Commit and push these changes to your repository**
2. **Redeploy your Railway services** (web + cron)
3. **Configure the cron job in Railway Dashboard** (see RAILWAY_QUICK_START.md)
4. **Test with `--force` flag first**
5. **Remove `--force` for production** once confirmed working
6. **Monitor logs** to ensure scheduled runs happen correctly

---

## 💡 Pro Tips

1. **Always test with `--force` first** to verify the command works
2. **Check timezone settings** for all organizations in your database
3. **Monitor cron logs regularly** to catch issues early
4. **Use Railway's "Run Now" button** for immediate testing
5. **Keep `--force` flag in a separate cron job** for manual triggers

---

## ✨ Success Criteria

You'll know it's working when:
- ✅ Cron job completes and exits (doesn't run forever)
- ✅ You see "Starting news processing..." in logs
- ✅ Organizations are processed (with --force) or time checks happen (without)
- ✅ Articles are fetched, clustered, and summarized
- ✅ Database updates with new summaries
- ✅ Job logs "CRON JOB COMPLETED"

