# 🚀 Deployment Checklist - Railway

## ✅ Pre-Deployment (Do This First)

- [ ] Read `RAILWAY_DEPLOYMENT_GUIDE.md` (comprehensive guide)
- [ ] Have Railway account ready
- [ ] Have git access to your repository

---

## 📦 Step 1: Push Code to Railway (5 min)

```bash
cd /Users/coughman/Desktop/Briefed/briefed/1nbox

# Check status
git status

# Add files
git add 1nbox/_1nbox_ai/models.py
git add 1nbox/_1nbox_ai/news.py
git add 1nbox/_1nbox_ai/management/commands/runclusternews.py
git add 1nbox/_1nbox_ai/migrations/0006_add_current_clusters_to_topic.py

# Commit
git commit -m "Add cluster news system with conditional summarization"

# Push (Railway auto-deploys)
git push origin main
```

**Checklist:**
- [ ] Code committed
- [ ] Code pushed to main branch
- [ ] Railway deployment started (check dashboard)
- [ ] Deployment completed successfully

---

## 🗄️ Step 2: Run Migration (2 min)

In Railway dashboard or CLI:

```bash
python manage.py migrate
```

**Expected Output:**
```
Running migrations:
  Applying _1nbox_ai.0006_add_current_clusters_to_topic... OK
```

**Checklist:**
- [ ] Migration ran successfully
- [ ] No errors in output

---

## 🧪 Step 3: Test It Works (5 min)

Run test command:

```bash
python manage.py runclusternews
```

**Check for these in logs:**
- ✅ "Retrieved X articles from..."
- ✅ "Generated X clusters"
- ✅ "Successfully saved new summary"

**Checklist:**
- [ ] Command runs without errors
- [ ] Articles are being fetched
- [ ] Clusters are being generated
- [ ] Summaries are being saved
- [ ] Can see new Summary records in database

---

## ⏰ Step 4: Create First Cron - Main Processor (5 min)

**In Railway Dashboard:**

1. Click "+ New" → "Cron Job"

**Configuration:**
```
Service Name: cluster-news-processor
Cron Schedule: */15 * * * *
Command: python manage.py runclusternews
```

2. Link Database Service
3. Copy ALL environment variables from web service:
   - DATABASE_URL (auto-added when linking)
   - OPENAI_KEY
   - GEMINI_API_KEY or GEMINI_KEY
   - DJANGO_SECRET_KEY
   - All Firebase variables
   - All other variables

**Checklist:**
- [ ] Cron service created
- [ ] Schedule set to `*/15 * * * *`
- [ ] Command is `python manage.py runclusternews`
- [ ] Database linked
- [ ] All environment variables added
- [ ] Service deployed successfully

---

## 🧹 Step 5: Create Second Cron - Cleanup (5 min)

**In Railway Dashboard:**

1. Click "+ New" → "Cron Job"

**Configuration:**
```
Service Name: cleanup-old-summaries
Cron Schedule: 0 2 * * *
Command: python manage.py runclusternews --cleanup
```

2. Link Database Service
3. Copy ALL environment variables (same as step 4)

**Checklist:**
- [ ] Cron service created
- [ ] Schedule set to `0 2 * * *`
- [ ] Command is `python manage.py runclusternews --cleanup`
- [ ] Database linked
- [ ] All environment variables added
- [ ] Service deployed successfully

---

## 👀 Step 6: Verify First Cron Run (15 min)

**Wait for next 15-minute mark** (e.g., if it's 2:07 PM, wait until 2:15 PM)

**Then check:**

1. **View Logs:**
   - Go to `cluster-news-processor` in Railway
   - Click "Logs" tab
   - Should see processing logs

2. **Check Database:**
```bash
python manage.py shell

>>> from _1nbox_ai.models import Summary
>>> from datetime import datetime, timedelta
>>> recent = Summary.objects.filter(created_at__gte=datetime.now()-timedelta(hours=1))
>>> print(f"Summaries in last hour: {recent.count()}")
```

**Checklist:**
- [ ] Cron ran at scheduled time
- [ ] Logs show successful processing
- [ ] New summaries created (or logs show "didn't change enough")
- [ ] No errors in logs

---

## 📊 Step 7: Monitor for 24 Hours

### After 1 Hour:
- [ ] At least 1 cron run completed
- [ ] Summaries visible in database
- [ ] Frontend showing new summaries

### After 4 Hours:
- [ ] Multiple cron runs completed (at least 16 runs)
- [ ] Some runs created summaries (>40% change)
- [ ] Some runs skipped summaries (<40% change)
- [ ] No consistent errors

### After 24 Hours:
- [ ] ~96 cron runs total (4 per hour × 24 hours)
- [ ] 6-10 summaries created per topic
- [ ] Cleanup cron ran once (at 2 AM)
- [ ] Costs within expected range

---

## 🎯 Success Indicators

After 24 hours, you should see:

### In Logs:
```
✅ "Retrieved X articles from..."
✅ "Generated X clusters"  
✅ "Successfully saved new summary" (when changes >40%)
✋ "didn't change enough (<40%)" (when no changes)
📊 "Cluster difference: X.XX%"
```

### In Database:
- 6-10 Summary records per topic over 24 hours
- All recent summaries have `current_clusters` in Topic model
- Old summaries (if >30 days) getting deleted

### In Frontend:
- Latest summaries showing
- Summaries updating throughout the day
- No errors or stale data

### Costs (for 30 topics):
- OpenAI usage: $12-18/day
- Gemini usage: $1.20-1.80/day
- Total: ~$13-20/day (~$400-600/month)

---

## ⚠️ Common Issues & Fixes

### Issue: Cron not running
**Check:**
- [ ] Cron service is "Active" in Railway
- [ ] Cron schedule is correct (`*/15 * * * *`)
- [ ] Environment variables are set
- [ ] Database is linked

**Fix:** Redeploy the cron service

### Issue: No summaries being created
**Check logs for:**
- "Retrieved 0 articles" → RSS sources might be down
- "No articles found" → Check topic has sources configured
- "didn't change enough" → This is normal! It means <40% change

**Fix:** Run `python manage.py runnews` to force a summary

### Issue: Too many summaries
**If getting 4 summaries per hour (96/day):**
- 40% threshold might be too sensitive
- RSS sources are very active

**Fix:** Increase threshold in code (change 0.40 to 0.50)

### Issue: Database errors
**Check:**
- [ ] DATABASE_URL is set
- [ ] Database is linked to cron service
- [ ] Migration ran successfully

**Fix:** Re-run migration, check database connection

---

## 📝 Environment Variables Required

Make sure these are in BOTH cron services:

### Critical (Must Have):
- `DATABASE_URL` ← Auto-added when linking database
- `OPENAI_KEY` ← For cluster summaries
- `GEMINI_API_KEY` or `GEMINI_KEY` ← For final summaries
- `DJANGO_SECRET_KEY` ← Django required

### Firebase (Required):
- `FIREBASE_PROJECT_ID`
- `FIREBASE_PRIVATE_KEY_ID`
- `FIREBASE_PRIVATE_KEY`
- `FIREBASE_CLIENT_EMAIL`
- `FIREBASE_CLIENT_ID`
- `FIREBASE_CLIENT_CERT_URL`

### Optional:
- `SENDGRID_API_KEY` (if using email)
- Any custom variables your app uses

---

## 🔧 Quick Commands Reference

```bash
# Test manually
python manage.py runclusternews

# Test with cleanup
python manage.py runclusternews --cleanup

# Force full regeneration
python manage.py runnews

# Check recent summaries
python manage.py shell
>>> from _1nbox_ai.models import Summary
>>> from datetime import datetime, timedelta
>>> Summary.objects.filter(created_at__gte=datetime.now()-timedelta(hours=1)).count()

# View logs in Railway
# Dashboard → Service → Logs tab

# Check cron schedule
# Dashboard → Cron Service → Settings
```

---

## 📚 Documentation Files

If you need more details:

1. **`RAILWAY_DEPLOYMENT_GUIDE.md`** ← Full deployment guide
2. **`CLUSTER_NEWS_SYSTEM_README.md`** ← Technical documentation
3. **`IMPLEMENTATION_SUMMARY.md`** ← What changed
4. **`QUICK_START.md`** ← 3-step quick guide
5. **`DEPLOYMENT_CHECKLIST.md`** ← This file

---

## ✅ Final Checklist

Before calling it done:

- [ ] Code pushed to Railway
- [ ] Migration ran successfully
- [ ] Test command works
- [ ] First cron service created (every 15 min)
- [ ] Second cron service created (daily cleanup)
- [ ] Both cron services have all environment variables
- [ ] Both cron services linked to database
- [ ] First cron run completed successfully
- [ ] Summaries visible in database
- [ ] Frontend showing updated summaries
- [ ] No errors in logs
- [ ] Monitoring for 24 hours planned

---

## 🎉 You're Done!

Once all checkboxes are complete, your system is:
- ✅ Fetching news every 15 minutes
- ✅ Clustering automatically
- ✅ Creating summaries when content changes >40%
- ✅ Cleaning up old data after 30 days
- ✅ Providing continuous updates to users

**Next:** Monitor for 24-48 hours, then you can relax! 🚀

---

## 🆘 Need Help?

1. Check logs: Railway Dashboard → Service → Logs
2. Test manually: `python manage.py runclusternews`
3. Check documentation: `RAILWAY_DEPLOYMENT_GUIDE.md`
4. Review this checklist again
5. Verify all environment variables are set

