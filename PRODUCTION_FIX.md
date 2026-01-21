# 🚨 Production Fix - CORS 500 Error

## Problem

The backend is returning a 500 error because the database migration hasn't been run on production. The new code tries to access fields that don't exist yet.

## Solution

### Step 1: Run Migration on Production

**If using Railway:**
```bash
# SSH into your Railway instance or use Railway CLI
railway run python manage.py migrate _1nbox_ai
```

**If using other hosting:**
```bash
# SSH into your production server
cd /path/to/your/app
python manage.py migrate _1nbox_ai
```

**Expected output:**
```
Running migrations:
  Applying _1nbox_ai.0007_add_deep_research_fields... OK
```

### Step 2: Restart Your Server

After running the migration, restart your Django server:

**Railway:**
- The server should auto-restart, or manually redeploy

**Other hosting:**
- Restart your gunicorn/uwsgi process
- Or restart your service: `sudo systemctl restart your-app`

### Step 3: Verify It Works

1. Check that the migration ran successfully
2. Try accessing Genie again from `https://trybriefed.com`
3. Check production logs for any remaining errors

---

## Alternative: Quick Fix (If Migration Fails)

If you can't run the migration immediately, you can temporarily make the new fields optional in the code:

**In `genie_views.py`, find the `analyze()` function and add try/except:**

```python
# Around line 700-710, modify:
analysis = GenieAnalysis.objects.create(
    user=user,
    organization=organization,
    query=query,
    status='processing',
    research_type=research_type,  # This might fail if field doesn't exist
    deep_research_id=deep_research_id
)

# Change to:
analysis = GenieAnalysis.objects.create(
    user=user,
    organization=organization,
    query=query,
    status='processing'
)
# Then update fields if they exist
try:
    analysis.research_type = research_type
    analysis.deep_research_id = deep_research_id
    analysis.save()
except:
    pass  # Fields don't exist yet, skip
```

**But this is a temporary fix - you MUST run the migration!**

---

## Why This Happened

The new code uses database fields that were added in migration `0007_add_deep_research_fields.py`. When Django tries to save data to these fields, it fails because the columns don't exist in the database yet.

---

## Prevention

Always run migrations before deploying new code that uses new database fields!

---

## Need Help?

Check production logs for the exact error:
- Railway: View logs in Railway dashboard
- Other: Check your server logs (`/var/log/` or wherever your logs are)

The error should show something like:
```
column "research_type" does not exist
```

This confirms the migration needs to be run.

