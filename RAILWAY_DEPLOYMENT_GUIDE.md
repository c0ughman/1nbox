# Railway Deployment Guide - Cluster News System

## 🚀 Complete Railway Setup Instructions

### Prerequisites
- Railway account
- Your project already deployed on Railway
- Database service linked

---

## Step 1: Deploy the Code Changes (5 minutes)

### 1.1 Commit and Push Changes

```bash
cd /Users/coughman/Desktop/Briefed/briefed/1nbox

# Check what changed
git status

# Add the changes
git add 1nbox/_1nbox_ai/models.py
git add 1nbox/_1nbox_ai/news.py
git add 1nbox/_1nbox_ai/management/commands/runclusternews.py
git add 1nbox/_1nbox_ai/migrations/0006_add_current_clusters_to_topic.py

# Commit
git commit -m "Add cluster news system with conditional summarization"

# Push to your main branch (Railway will auto-deploy)
git push origin main
```

### 1.2 Wait for Railway Deployment

- Go to Railway dashboard
- Watch your service deploy
- Wait for "Deployed" status (usually 2-3 minutes)

### 1.3 Run Migration

Once deployed, run the migration:

**Option A: In Railway Dashboard**
1. Go to your service
2. Click "Deployments" tab
3. Click latest deployment
4. Click "View Logs"
5. In the service, go to "Settings" → "Deploy"
6. Add a one-time command: `python manage.py migrate`

**Option B: Using Railway CLI**
```bash
railway run python manage.py migrate
```

**Option C: Via Shell (if you have shell access)**
1. Go to service in Railway
2. Click on "Shell" or "Terminal"
3. Run: `python manage.py migrate`

You should see:
```
Running migrations:
  Applying _1nbox_ai.0006_add_current_clusters_to_topic... OK
```

---

## Step 2: Test It Works (5 minutes)

### 2.1 Run Test Command

In Railway shell or via CLI:
```bash
python manage.py runclusternews
```

### 2.2 Check the Output

You should see logs like:
```
Starting cluster news processing...
🔄 Processing organization: [Organization Name]
📰 Starting processing for topic: [Topic Name]
✅ Retrieved 45 articles from http://...
✅ Retrieved 32 articles from http://...
🔗 Generated 8 clusters for topic [Topic Name]
📊 Cluster difference: 100.00% (threshold: 40%)
✅ Clusters changed >40%, generating new cluster summaries
Summarizing cluster 1/8: Tesla, Earnings
Summarizing cluster 2/8: NATO, Summit
...
✅ Successfully generated final summary
💾 Successfully saved new summary for topic [Topic Name] (ID: 123)
Cluster news processing completed successfully.
```

### 2.3 Verify Database

Check that summaries were created:
```bash
python manage.py shell

>>> from _1nbox_ai.models import Summary, Topic
>>> from datetime import datetime, timedelta
>>> 
>>> # Check recent summaries
>>> recent = Summary.objects.filter(created_at__gte=datetime.now()-timedelta(hours=1))
>>> print(f"Summaries in last hour: {recent.count()}")
>>> 
>>> # Check a specific topic
>>> topic = Topic.objects.first()
>>> print(f"Topic: {topic.name}")
>>> print(f"Has current_clusters: {topic.current_clusters is not None}")
>>> summaries = Summary.objects.filter(topic=topic).order_by('-created_at')[:5]
>>> for s in summaries:
...     print(f"- {s.created_at}: {len(s.clusters)} clusters, {s.number_of_articles} articles")
>>> 
>>> exit()
```

---

## Step 3: Create Cron Services (10 minutes)

### 3.1 Create First Cron Service - Main Processing

**In Railway Dashboard:**

1. **Go to your project**
2. **Click "+ New" → "Cron Job"**
3. **Configure the cron job:**

```
Service Name: cluster-news-processor
```

4. **Set the Schedule:**
```
Cron Schedule: */15 * * * *
```
(This means: every 15 minutes)

5. **Set the Command:**
```
Command: python manage.py runclusternews
```

6. **Link the Database:**
   - In the service settings
   - Go to "Variables" tab
   - Click "Reference Variables"
   - Select your database service
   - This will automatically add `DATABASE_URL`

7. **Add Environment Variables:**
   - Copy all environment variables from your main web service
   - You need:
     - `DATABASE_URL` (automatically added when you link database)
     - `OPENAI_KEY`
     - `GEMINI_API_KEY` or `GEMINI_KEY`
     - `DJANGO_SECRET_KEY`
     - All Firebase variables
     - Any other variables your app uses

8. **Save and Deploy**

### 3.2 Create Second Cron Service - Daily Cleanup

**In Railway Dashboard:**

1. **Click "+ New" → "Cron Job"**
2. **Configure the cron job:**

```
Service Name: cleanup-old-summaries
```

3. **Set the Schedule:**
```
Cron Schedule: 0 2 * * *
```
(This means: daily at 2:00 AM UTC)

4. **Set the Command:**
```
Command: python manage.py runclusternews --cleanup
```

5. **Link Database and Add Environment Variables** (same as step 3.1)

6. **Save and Deploy**

---

## Step 4: Verify Cron Jobs Are Running (15 minutes)

### 4.1 Wait for First Run

The 15-minute cron will run at:
- :00, :15, :30, :45 of each hour

So if it's currently 2:07 PM, the next run is at 2:15 PM.

### 4.2 Check Cron Logs

**In Railway Dashboard:**
1. Go to the `cluster-news-processor` service
2. Click "Deployments" tab
3. Click on latest run
4. View logs

You should see the processing logs.

### 4.3 Verify Summaries Are Being Created

Run this every hour to check:
```bash
python manage.py shell

>>> from _1nbox_ai.models import Summary
>>> from datetime import datetime, timedelta
>>> 
>>> # Count summaries created in last hour
>>> one_hour_ago = datetime.now() - timedelta(hours=1)
>>> recent = Summary.objects.filter(created_at__gte=one_hour_ago)
>>> print(f"Summaries created in last hour: {recent.count()}")
>>> 
>>> # Show breakdown by topic
>>> for summary in recent:
...     print(f"- {summary.topic.name}: {summary.created_at.strftime('%H:%M')}")
```

---

## Step 5: Monitor for 24 Hours (Ongoing)

### 5.1 Check Logs Regularly

**View real-time logs:**
- Go to `cluster-news-processor` service in Railway
- Click "Logs" tab
- Watch for successful runs every 15 minutes

**Look for these patterns:**
```
✅ Success: "Successfully saved new summary"
✋ No changes: "Clusters didn't change enough (<40%), keeping existing summary"
❌ Errors: "Error" or "Failed"
```

### 5.2 Database Size Check

After 24 hours, check database growth:
```bash
python manage.py shell

>>> from _1nbox_ai.models import Summary
>>> from datetime import datetime, timedelta
>>> 
>>> # Count summaries per day
>>> today = datetime.now().date()
>>> for i in range(7):
...     date = today - timedelta(days=i)
...     count = Summary.objects.filter(created_at__date=date).count()
...     print(f"{date}: {count} summaries")
```

Expected: 6-10 summaries per topic per day.

### 5.3 Cost Monitoring

Monitor your OpenAI and Gemini API usage:
- OpenAI Dashboard: https://platform.openai.com/usage
- Google Cloud Console: Check Gemini API usage

Expected costs (per topic per day):
- OpenAI: ~$0.40-0.60
- Gemini: ~$0.04-0.06
- Total: ~$0.50-0.70 per topic per day

For 10 organizations × 3 topics = 30 topics:
- Daily: ~$15-20
- Monthly: ~$450-600

---

## Railway Service Configuration Summary

### Service 1: Web Service (Your main app)
```
Type: Web Service
Deploy: Git (main branch)
Start Command: gunicorn _1nbox_ai.wsgi --log-file -
Environment Variables: All your existing variables
```

### Service 2: cluster-news-processor (NEW)
```
Type: Cron Job
Schedule: */15 * * * *
Command: python manage.py runclusternews
Environment Variables: Same as web service
Linked: Database service
```

### Service 3: cleanup-old-summaries (NEW)
```
Type: Cron Job
Schedule: 0 2 * * *
Command: python manage.py runclusternews --cleanup
Environment Variables: Same as web service
Linked: Database service
```

---

## Environment Variables Checklist

Make sure these are set in BOTH cron services:

### Required
- ✅ `DATABASE_URL` (auto-added when linking database)
- ✅ `OPENAI_KEY`
- ✅ `GEMINI_API_KEY` or `GEMINI_KEY`
- ✅ `DJANGO_SECRET_KEY`

### Firebase (Required for models)
- ✅ `FIREBASE_PROJECT_ID`
- ✅ `FIREBASE_PRIVATE_KEY_ID`
- ✅ `FIREBASE_PRIVATE_KEY`
- ✅ `FIREBASE_CLIENT_EMAIL`
- ✅ `FIREBASE_CLIENT_ID`
- ✅ `FIREBASE_CLIENT_CERT_URL`

### Optional (but recommended)
- `SENDGRID_API_KEY` (if you're still using email)
- Any other custom variables your app uses

---

## Troubleshooting

### Cron job not running?

**Check 1: Verify schedule**
```bash
# In Railway shell
date
# Make sure timezone is correct (UTC)
```

**Check 2: View cron logs**
- Go to cron service in Railway
- Click "Logs"
- Look for errors

**Check 3: Test manually**
```bash
# SSH into Railway or use shell
python manage.py runclusternews
# Watch for errors
```

### No summaries being created?

**Check 1: Are articles being fetched?**
```bash
# Look in logs for:
"Retrieved X articles from..."
```

**Check 2: Are clusters forming?**
```bash
# Look for:
"Generated X clusters"
```

**Check 3: Is 40% threshold being met?**
```bash
# Look for:
"Cluster difference: X.XX% (threshold: 40%)"
# If it says "didn't change enough", that's normal
```

### Too many summaries?

If you're getting summaries every 15 minutes (4 per hour = 96 per day):
- The 40% threshold might be too sensitive
- Or your RSS sources are extremely active
- Check logs to see what's changing

**Solution:** Increase the threshold in code
```python
# In news.py, change:
if cluster_diff >= 0.40:  # Change to 0.50 or 0.60
```

### Database growing too fast?

**Check current size:**
```sql
SELECT 
    COUNT(*) as total_summaries,
    pg_size_pretty(pg_total_relation_size('_1nbox_ai_summary')) as table_size
FROM _1nbox_ai_summary;
```

**Run cleanup manually:**
```bash
python manage.py runclusternews --cleanup
```

**Run cleanup more often:**
- Change daily cleanup cron from `0 2 * * *` to `0 */6 * * *` (every 6 hours)

---

## Testing Checklist

After deployment, verify:

### Day 1 (First 24 Hours)
- [ ] Migration ran successfully
- [ ] Test command works: `python manage.py runclusternews`
- [ ] Cron service `cluster-news-processor` is created
- [ ] Cron service `cleanup-old-summaries` is created
- [ ] Environment variables set in both cron services
- [ ] Database linked to both cron services
- [ ] First cron run completed successfully (check logs)
- [ ] Summaries are being created (check database)
- [ ] Frontend shows new summaries (check website)

### Week 1 (Monitor)
- [ ] Summaries updating throughout the day
- [ ] Not creating summaries when nothing changes (<40%)
- [ ] Cleanup ran successfully (after first night)
- [ ] Old summaries being deleted (after 30 days, if any exist)
- [ ] Costs are within expected range
- [ ] No errors in logs

### After Week 1 (Optimize)
- [ ] Review average summaries per day
- [ ] Adjust 40% threshold if needed
- [ ] Check if any RSS sources are failing consistently
- [ ] Verify Chat/Genie have access to historical summaries

---

## Quick Reference Commands

```bash
# Test the command
python manage.py runclusternews

# Run with cleanup
python manage.py runclusternews --cleanup

# Force full regeneration (bypass 40% check)
python manage.py runnews

# Check recent summaries
python manage.py shell
>>> from _1nbox_ai.models import Summary
>>> from datetime import datetime, timedelta
>>> Summary.objects.filter(created_at__gte=datetime.now()-timedelta(hours=1)).count()

# View logs (in Railway)
# Go to service → Logs tab

# Run migration (one-time)
python manage.py migrate
```

---

## Success Indicators

After 24 hours, you should see:
- ✅ 6-10 Summary records per topic created
- ✅ Clusters updating every 15 minutes in logs
- ✅ Some runs skip summary generation (<40% change)
- ✅ Some runs create new summaries (>40% change)
- ✅ Frontend shows latest summaries
- ✅ No errors in cron logs
- ✅ Costs within $15-20/day for 30 topics

---

## Next Steps After Successful Deployment

1. **Week 1**: Monitor and verify everything works
2. **Week 2**: Review costs and adjust thresholds if needed
3. **Week 3**: Consider disabling old `runnews` cron (keep command for manual use)
4. **Future**: Add playback feature, custom thresholds per org, etc.

---

## Support Resources

- **Logs**: Railway Dashboard → Service → Logs
- **Database**: Railway Dashboard → Database → Query
- **Shell**: Railway Dashboard → Service → Shell
- **Docs**: See `CLUSTER_NEWS_SYSTEM_README.md` for detailed technical info

---

## 🎉 You're Ready!

Follow these steps in order:
1. ✅ Commit and push code
2. ✅ Wait for Railway deployment
3. ✅ Run migration
4. ✅ Test manually
5. ✅ Create cron services
6. ✅ Monitor for 24 hours

After 24 hours of successful operation, you're all set! The system will automatically:
- Fetch news every 15 minutes
- Create summaries when content changes
- Clean up old summaries after 30 days
- Provide continuous updates for your users

Good luck! 🚀

