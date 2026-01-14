# Railway Cron Job - Quick Start

## 🎯 What You Need to Do in Railway

### 1. Create Cron Job Service
1. Open your Railway project
2. Click **"New"** → **"Cron Job"**
3. Name it: `news-processing-cron`

### 2. Configure Command

**For Testing (processes ALL orgs immediately):**
```bash
bash run-cron.sh runnews --force
```

**For Production (only processes orgs at scheduled time):**
```bash
bash run-cron.sh runnews
```

### 3. Set Schedule

**For Production:**
```
0 * * * *
```
(Runs every hour at minute 0)

**For Testing:**
- Use the **"Run Now"** button instead of setting a schedule

### 4. Copy Environment Variables
Copy ALL environment variables from your web service to the cron service:
- `DATABASE_URL`
- `DJANGO_SECRET_KEY`
- `OPENAI_API_KEY`
- `GEMINI_API_KEY`
- `SENDGRID_API_KEY`
- `FIREBASE_PROJECT_ID`
- `FIREBASE_PRIVATE_KEY`
- `FIREBASE_CLIENT_EMAIL`

### 5. Deploy
Click **"Deploy"** or **"Run Now"** to test

---

## ✅ Expected Output (with --force)

```
================================
STARTING CRON JOB
================================
Running environment check...
✓ DATABASE_URL: postgresql://...
✓ DJANGO_SECRET_KEY: ...
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
[... processing happens ...]
News processing completed successfully.
================================
CRON JOB COMPLETED
================================
```

---

## 🚨 If It's Not Working

**Check these in order:**

1. **Command is correct:**
   - Should be: `bash run-cron.sh runnews --force` (for testing)
   - NOT: `bash start.sh` (that's for web service)

2. **Environment variables are set:**
   - All variables from web service must be copied to cron service

3. **Working directory is `/app`:**
   - This should be automatic, but verify if issues occur

4. **Check logs:**
   - Go to cron service → Logs
   - Look for errors or "Starting news processing..." message

---

## 📖 Full Documentation
See `RAILWAY_CRON_SETUP.md` for complete details.

