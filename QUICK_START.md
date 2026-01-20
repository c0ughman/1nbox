# Quick Start Guide - Cluster News System

## 🚀 Deploy in 3 Steps

### Step 1: Run Migration (2 minutes)
```bash
cd /path/to/your/project/1nbox
python manage.py migrate
```

Expected output:
```
Running migrations:
  Applying _1nbox_ai.0006_add_current_clusters_to_topic... OK
```

### Step 2: Test It Works (5 minutes)
```bash
python manage.py runclusternews
```

Check the log:
```bash
tail -f cluster_news_processing.log
```

You should see:
- ✅ "Retrieved X articles from..."
- ✅ "Generated X clusters"
- ✅ "Successfully saved new summary"

### Step 3: Setup Railway Cron (5 minutes)

**In Railway Dashboard:**

**Cron Job 1: Main Processing**
- Name: `cluster-news-processor`
- Schedule: `*/15 * * * *` (every 15 minutes)
- Command: `python manage.py runclusternews`

**Cron Job 2: Daily Cleanup**
- Name: `cleanup-old-summaries`
- Schedule: `0 2 * * *` (daily at 2 AM)
- Command: `python manage.py runclusternews --cleanup`

## ✅ Done!

Your system is now:
- Fetching news every 15 minutes
- Clustering automatically
- Creating summaries when content changes >40%
- Cleaning up old data after 30 days

## 📊 Monitor It

### Check if it's working
```bash
# View recent summaries
python manage.py shell

>>> from _1nbox_ai.models import Summary
>>> from datetime import datetime, timedelta
>>> recent = Summary.objects.filter(created_at__gte=datetime.now()-timedelta(hours=1))
>>> print(f"Summaries created in last hour: {recent.count()}")
```

### Check logs
```bash
# Watch real-time
tail -f cluster_news_processing.log

# Search for errors
grep "Error" cluster_news_processing.log

# Count summaries created today
grep "Successfully saved" cluster_news_processing.log | wc -l
```

## 🔧 Common Commands

```bash
# Run processing manually
python manage.py runclusternews

# Run with cleanup
python manage.py runclusternews --cleanup

# Force full regeneration (bypass 40% check)
python manage.py runnews

# Check database
python manage.py dbshell
SELECT COUNT(*) FROM _1nbox_ai_summary WHERE created_at > NOW() - INTERVAL '1 day';
```

## 🎯 What You Should See

**First Hour After Deploy:**
- 2-4 Summary records created per topic (initial summaries)

**Ongoing (Every 15 min):**
- New Summary created if news changed >40%
- No new Summary if nothing changed

**After 30 Days:**
- Old summaries automatically deleted
- Database size stable

## ❓ Troubleshooting One-Liners

```bash
# No summaries being created?
python manage.py runclusternews 2>&1 | tee debug.log

# Check if articles fetching?
grep "Retrieved" cluster_news_processing.log

# Check if clustering working?
grep "Generated" cluster_news_processing.log

# Force a summary?
python manage.py runnews

# Clean up old summaries?
python manage.py runclusternews --cleanup
```

## 📚 Full Documentation

- **Comprehensive Guide**: `CLUSTER_NEWS_SYSTEM_README.md`
- **Implementation Details**: `IMPLEMENTATION_SUMMARY.md`
- **This Quick Start**: `QUICK_START.md`

## 🆘 Need Help?

1. Check logs: `cluster_news_processing.log`
2. Test manually: `python manage.py runclusternews`
3. Use fallback: `python manage.py runnews`

---

**That's it!** Your cluster news system is ready to go. 🎉

