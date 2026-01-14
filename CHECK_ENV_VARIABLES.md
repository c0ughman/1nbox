# How to Check Environment Variables

## Step 1: Check Environment Variables in Railway Dashboard

### For Web Service:
1. Go to Railway Dashboard
2. Click on your **web service** (the one that's failing)
3. Click on **"Variables"** tab
4. Look for these REQUIRED variables:
   - `DATABASE_URL` - Should start with `postgresql://` or `postgres://`
   - `DJANGO_SECRET_KEY` - Should be a long random string

### For Cron Service (for comparison):
1. Go to Railway Dashboard
2. Click on your **cron service** (the one that works)
3. Click on **"Variables"** tab
4. Note down the values of:
   - `DATABASE_URL`
   - `DJANGO_SECRET_KEY`

## Step 2: Compare Values

### Check if DATABASE_URL exists:
- ✅ **Good**: Variable exists and has a value starting with `postgresql://`
- ❌ **Bad**: Variable missing or empty
- ❌ **Bad**: Value doesn't start with `postgresql://` or `postgres://`

### Check if DJANGO_SECRET_KEY exists:
- ✅ **Good**: Variable exists and has a long random string value
- ❌ **Bad**: Variable missing or empty
- ❌ **Bad**: Value is too short (should be at least 50 characters)

## Step 3: Verify Values Match Between Services

**IMPORTANT**: The web service and cron service should have:
- **Same** `DATABASE_URL` (they use the same database)
- **Same** `DJANGO_SECRET_KEY` (they're the same Django app)

### If they don't match:
1. Copy `DATABASE_URL` from cron service → web service
2. Copy `DJANGO_SECRET_KEY` from cron service → web service
3. Save and redeploy

## Step 4: Test Environment Variables Manually

You can test if the variables are set correctly by creating a simple test:

### Option A: Add a test endpoint (temporary)
Add this to your `_1nbox_ai/views.py`:

```python
def test_env(request):
    import os
    return JsonResponse({
        'DATABASE_URL': 'SET' if os.environ.get('DATABASE_URL') else 'MISSING',
        'DJANGO_SECRET_KEY': 'SET' if os.environ.get('DJANGO_SECRET_KEY') else 'MISSING',
        'GEMINI_KEY': 'SET' if os.environ.get('GEMINI_KEY') else 'MISSING',
    })
```

Then add to `urls.py`:
```python
path('test_env/', views.test_env),
```

### Option B: Check Railway logs after deploy
After deploying with the improved logging, you should see:
```
REQUIRED VARIABLES (Django startup):
✓ DATABASE_URL: postgresql://...
✓ DJANGO_SECRET_KEY: ...
```

If you see:
```
✗ DATABASE_URL: NOT SET - REQUIRED!
✗ DJANGO_SECRET_KEY: NOT SET - REQUIRED!
```

Then those variables are missing.

## Step 5: Verify Database Connection

If `DATABASE_URL` exists, verify it's valid:

1. Copy the `DATABASE_URL` value from Railway
2. It should look like: `postgresql://user:password@host:port/database`
3. Check:
   - ✅ Has `postgresql://` or `postgres://` prefix
   - ✅ Has username, password, host, port, database name
   - ✅ No extra spaces or quotes

## Step 6: Common Issues

### Issue: Variable exists but service still fails
**Possible causes:**
- Variable has extra spaces: `" value "` instead of `"value"`
- Variable has quotes: `"'value'"` instead of `"value"`
- Variable is in wrong service (check you're looking at web service, not cron)

### Issue: Variables match but web service still fails
**Possible causes:**
- Different service has different variable values
- Variable was set but not saved
- Need to redeploy after setting variables

## Quick Checklist

Before disabling healthcheck, verify:

- [ ] `DATABASE_URL` exists in web service
- [ ] `DATABASE_URL` starts with `postgresql://` or `postgres://`
- [ ] `DJANGO_SECRET_KEY` exists in web service
- [ ] `DJANGO_SECRET_KEY` is long (50+ characters)
- [ ] Both variables match between web service and cron service
- [ ] Variables are saved (not just typed but saved in Railway)

## If Variables Are Missing

1. **Copy from Cron Service:**
   - Go to cron service → Variables
   - Copy `DATABASE_URL` value
   - Copy `DJANGO_SECRET_KEY` value

2. **Paste to Web Service:**
   - Go to web service → Variables
   - Add `DATABASE_URL` = (paste value)
   - Add `DJANGO_SECRET_KEY` = (paste value)
   - Click "Save" or "Add Variable"

3. **Redeploy:**
   - Railway should auto-redeploy
   - Or manually trigger a deploy

## Next: After Verifying Variables

Once you've confirmed the variables are set correctly, we'll disable the healthcheck to see the actual startup logs.

