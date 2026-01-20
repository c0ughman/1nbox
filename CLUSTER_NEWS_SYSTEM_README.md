# Cluster News System - Implementation Guide

## Overview

This system implements automatic news fetching, clustering, and conditional summarization that runs continuously throughout the day.

## How It Works

### The Flow

```
Every 15 minutes:
  1. Fetch articles from RSS (last 24 hours)
  2. Cluster them using existing algorithms
  3. Store current cluster state in Topic.current_clusters
  4. Compare with last saved Summary:
     - If clusters changed >40%: Generate NEW cluster summaries (OpenAI)
     - If cluster summaries changed >40%: Generate NEW final summary (Gemini)
     - If changes >40%: Save NEW Summary record
     - If changes <40%: Keep existing summary (no new record)

Result: You only save summaries when something actually changes
```

### Key Features

- ✅ **No arbitrary snapshot times** - summaries generated when content actually changes
- ✅ **No time-based restrictions** - runs whenever you trigger it
- ✅ **40% threshold** - smart detection of meaningful changes
- ✅ **Organic cluster lifecycle** - clusters naturally form, grow, and die based on 24-hour article window
- ✅ **30-day retention** - automatic cleanup of old summaries
- ✅ **Uses existing Summary model** - minimal database changes

## Database Changes

### New Field
- **Topic.current_clusters** (JSONField): Stores the current state of clusters for comparison

### New Migration
- `0006_add_current_clusters_to_topic.py`

### Existing Models (Unchanged)
- Summary model: Still stores clusters, cluster_summaries, final_summary
- All other models: No changes

## Management Commands

### 1. `runclusternews` - Main Command (Run Every 15 Minutes)

This is the primary command that does everything:

```bash
# Basic usage (recommended)
python manage.py runclusternews

# With custom parameters
python manage.py runclusternews --days 1 --common_word_threshold 2 --top_words_to_consider 3

# With cleanup (run this once per day)
python manage.py runclusternews --cleanup
```

**Parameters:**
- `--days`: Number of days to look back for articles (default: 1)
- `--common_word_threshold`: Words needed for clustering (default: 2)
- `--top_words_to_consider`: Top words to consider (default: 3)
- `--merge_threshold`: Words needed to merge clusters (default: 2)
- `--min_articles`: Minimum articles per cluster (default: 3)
- `--join_percentage`: Percentage match for reassignment (default: 0.5)
- `--final_merge_percentage`: Percentage for final merge (default: 0.5)
- `--sentences_final_summary`: Sentences per story in final summary (default: 3)
- `--title_only`: Only use article titles for clustering (flag)
- `--all_words`: Include all words, not just capitalized (flag)
- `--cleanup`: Delete summaries older than 30 days (flag)

**What it does:**
1. Fetches articles from all RSS sources (last 24 hours)
2. Extracts significant words
3. Clusters articles using existing algorithm
4. Compares with previous Summary:
   - Calculates cluster difference
   - If >40%: generates new cluster summaries
   - Calculates cluster summary difference
   - If >40%: generates new final summary
   - Saves new Summary record if changes detected
5. Updates Topic.current_clusters for next comparison

### 2. `runnews` - Legacy Command (Keep as Backup)

The original command still works but now processes ALL active organizations without time checks:

```bash
python manage.py runnews
```

This generates a full summary regardless of changes. Use this as a fallback or for manual regeneration.

## Railway Cron Setup

### Recommended Schedule

Create these cron jobs in Railway:

#### 1. Every 15 Minutes - Main Processing
```
Cron Expression: */15 * * * *
Command: python manage.py runclusternews
```

#### 2. Once Per Day - Cleanup
```
Cron Expression: 0 2 * * *  (2 AM daily)
Command: python manage.py runclusternews --cleanup
```

### Railway Configuration Example

```json
{
  "services": [
    {
      "name": "cluster-news-processor",
      "cron": {
        "schedule": "*/15 * * * *",
        "command": "python manage.py runclusternews"
      }
    },
    {
      "name": "cleanup-old-summaries",
      "cron": {
        "schedule": "0 2 * * *",
        "command": "python manage.py runclusternews --cleanup"
      }
    }
  ]
}
```

## How the 40% Threshold Works

### Cluster Difference Calculation

**IMPORTANT**: For cluster summaries, we only count NEW information (additions), not removals.
The logic is: we don't want to regenerate a cluster summary just because it has LESS information.
We only regenerate when there's NEW information to include.

```python
# Clusters are identified by their common_words
# Different common_words = different cluster

Changes counted for CLUSTER SUMMARIES:
1. New clusters (didn't exist before)
2. Modified clusters (same common_words but NEW articles added ≥40%)

Changes NOT counted:
- Removed clusters (clusters that disappeared)
- Removed articles from existing clusters (less information)

Formula: (new_clusters + modified_clusters) / total_current_clusters >= 0.40

For a cluster to be "modified":
- Must have same common_words (same identity)
- Must have NEW articles added
- NEW articles must be ≥40% of current cluster size
```

**Example 1: New Cluster Appears**
```
Previous state (10 AM):
- Cluster 1: ["Tesla", "Earnings"] - 5 articles
- Cluster 2: ["NATO", "Summit"] - 8 articles
Total: 2 clusters

Current state (10:15 AM):
- Cluster 1: ["Tesla", "Earnings"] - 5 articles (unchanged)
- Cluster 2: ["NATO", "Summit"] - 8 articles (unchanged)
- Cluster 3: ["Japan", "Earthquake"] - 6 articles (NEW cluster)
Total: 3 clusters

Calculation:
- New clusters: 1 (Japan Earthquake)
- Modified clusters: 0
- Total current clusters: 3
- Change: 1/3 = 33% < 40% ✗ Keep existing summaries
```

**Example 2: Cluster Gets New Articles**
```
Previous state (10 AM):
- Cluster 1: ["Tesla", "Earnings"] - 5 articles [A,B,C,D,E]
- Cluster 2: ["NATO", "Summit"] - 8 articles
Total: 2 clusters

Current state (10:15 AM):
- Cluster 1: ["Tesla", "Earnings"] - 8 articles [A,B,C,D,E,F,G,H]
  (3 NEW articles added: F,G,H)
- Cluster 2: ["NATO", "Summit"] - 8 articles (unchanged)
Total: 2 clusters

Calculation for Cluster 1:
- NEW articles: 3 (F,G,H)
- Current total: 8
- NEW percentage: 3/8 = 37.5% < 40% (not modified)

Overall:
- New clusters: 0
- Modified clusters: 0
- Change: 0/2 = 0% ✗ Keep existing summaries
```

**Example 3: Cluster Gets Many New Articles**
```
Previous state (10 AM):
- Cluster 1: ["Tesla", "Earnings"] - 5 articles [A,B,C,D,E]
- Cluster 2: ["NATO", "Summit"] - 8 articles
Total: 2 clusters

Current state (10:15 AM):
- Cluster 1: ["Tesla", "Earnings"] - 10 articles [A,B,C,D,E,F,G,H,I,J]
  (5 NEW articles: F,G,H,I,J)
- Cluster 2: ["NATO", "Summit"] - 8 articles (unchanged)
Total: 2 clusters

Calculation for Cluster 1:
- NEW articles: 5
- Current total: 10
- NEW percentage: 5/10 = 50% ≥ 40% (MODIFIED!)

Overall:
- New clusters: 0
- Modified clusters: 1 (Tesla)
- Change: 1/2 = 50% > 40% ✅ Generate new cluster summaries
```

**Example 4: Articles Drop Out (No New Summary!)**
```
Previous state (10 AM):
- Cluster 1: ["California", "Fires"] - 10 articles [A,B,C,D,E,F,G,H,I,J]
Total: 1 cluster

Current state (11 AM):
- Cluster 1: ["California", "Fires"] - 6 articles [A,B,C,D,E,F]
  (4 articles dropped out: G,H,I,J aged past 24 hours)
  (0 NEW articles)
Total: 1 cluster

Calculation for Cluster 1:
- NEW articles: 0
- Current total: 6
- NEW percentage: 0/6 = 0% (NOT modified - no new info)

Overall:
- New clusters: 0
- Modified clusters: 0
- Change: 0/1 = 0% ✗ Keep existing summary (less info, same story)
```

### Cluster Summary Difference Calculation

```python
# Compares the actual cluster summary texts
# Uses hash comparison to detect changes

Changes counted:
1. New summaries (for new clusters)
2. Removed summaries (for removed clusters)

Formula: (new + removed) / total_summaries >= 0.40
```

**Example:**
```
Previous summaries (10 AM):
- Summary A (Tesla)
- Summary B (NATO)
- Summary C (Fires)
Total: 3 summaries

Current summaries (11 AM):
- Summary A (Tesla) - same text
- Summary B (NATO) - same text
- Summary D (Japan) - new
- (Summary C removed)

Calculation:
- New: 1 (Japan)
- Removed: 1 (Fires)
- Total: 4
- Change: 2/4 = 50% > 40% ✅ Generate new final summary
```

## Data Flow & Storage

### During the Day (Continuous Operation)

```
15-min cycle:
  Articles fetched → Clustered → Compared → Conditionally summarized → Saved if >40% change
  
  Topic.current_clusters updated every cycle (for comparison)
  Summary records created only when changes detected
```

### Storage Pattern

```
Average day with moderate news activity:
- Morning (6-9 AM): 2-3 Summary records (breaking news)
- Midday (9 AM-3 PM): 1-2 Summary records (updates)
- Afternoon (3-6 PM): 2-3 Summary records (developing stories)
- Evening (6-11 PM): 1-2 Summary records (evening news)

Total: ~6-10 Summary records per topic per day
Over 30 days: ~180-300 Summary records per topic
```

### Automatic Cleanup

```bash
# Run daily cleanup (removes summaries >30 days old)
python manage.py runclusternews --cleanup
```

## Testing the System

### Step 1: Run Migration

```bash
python manage.py migrate
```

This adds the `current_clusters` field to the Topic model.

### Step 2: Test Manual Run

```bash
# Run once to generate initial summaries
python manage.py runclusternews

# Check logs
tail -f cluster_news_processing.log
```

### Step 3: Verify Database

```python
# In Django shell
python manage.py shell

from _1nbox_ai.models import Topic, Summary

# Check if current_clusters is populated
topic = Topic.objects.first()
print(topic.current_clusters)

# Check how many summaries were created
summaries = Summary.objects.filter(topic=topic).order_by('-created_at')
print(f"Total summaries: {summaries.count()}")
for s in summaries[:5]:
    print(f"- {s.created_at}: {len(s.clusters)} clusters")
```

### Step 4: Test Second Run (Should Not Create New Summary if <40% change)

```bash
# Run again immediately (should not create new summary if nothing changed)
python manage.py runclusternews

# Check if new summary was created
# If no new articles, it shouldn't create a new record
```

### Step 5: Setup Railway Cron

Configure in Railway dashboard:
1. Every 15 minutes: `python manage.py runclusternews`
2. Daily at 2 AM: `python manage.py runclusternews --cleanup`

## Monitoring & Logs

### Log Files

- **cluster_news_processing.log**: Main processing log
- **topic_processing.log**: Legacy log (still used by runnews)

### Key Log Messages

```
✅ - Success/completion
❌ - Error/failure
📰 - Article fetching
🔗 - Clustering
📊 - Statistics/metrics
💾 - Database save
🗑️ - Cleanup/deletion
🔄 - Processing
✋ - Skipped (no changes)
```

### Monitoring Queries

```sql
-- Check summary creation rate
SELECT 
    DATE(created_at) as date,
    COUNT(*) as summaries_created
FROM _1nbox_ai_summary
GROUP BY DATE(created_at)
ORDER BY date DESC
LIMIT 30;

-- Check average clusters per summary
SELECT 
    AVG(json_array_length(clusters)) as avg_clusters
FROM _1nbox_ai_summary
WHERE created_at > NOW() - INTERVAL '7 days';

-- Check topics with most updates
SELECT 
    t.name,
    COUNT(s.id) as summary_count
FROM _1nbox_ai_topic t
JOIN _1nbox_ai_summary s ON s.topic_id = t.id
WHERE s.created_at > NOW() - INTERVAL '1 day'
GROUP BY t.name
ORDER BY summary_count DESC;
```

## Troubleshooting

### Issue: No summaries being created

**Check:**
1. Are organizations active? `Organization.objects.exclude(plan='inactive')`
2. Do topics have RSS sources? `Topic.objects.filter(sources__len__gt=0)`
3. Are articles being fetched? Check log for "Retrieved X articles"
4. Is clustering working? Check log for "Generated X clusters"

**Solution:**
```bash
# Run with verbose logging
python manage.py runclusternews 2>&1 | tee debug.log
```

### Issue: Too many summaries being created

**Possible causes:**
1. Threshold might be too low (default 40%)
2. RSS sources updating very frequently
3. Clusters changing significantly every cycle

**Solution:**
```bash
# Increase thresholds (make it less sensitive)
# This would require modifying the 0.40 threshold in the code
```

### Issue: Summaries not reflecting recent news

**Check:**
1. Is the cron running every 15 minutes?
2. Are RSS sources responding? Check "failed_sources" in logs
3. Is the 24-hour window too narrow? Try `--days 2`

**Solution:**
```bash
# Force a full regeneration
python manage.py runnews
```

### Issue: Database growing too large

**Check:**
```sql
SELECT COUNT(*) FROM _1nbox_ai_summary;
SELECT pg_size_pretty(pg_total_relation_size('_1nbox_ai_summary'));
```

**Solution:**
```bash
# Run cleanup more frequently
python manage.py runclusternews --cleanup

# Or reduce retention period (modify timedelta(days=30) in code)
```

## API Changes

### No Frontend Changes Needed!

The frontend continues to work exactly as before:
- Gets latest Summary from `Summary.objects.filter(topic=topic).order_by('-created_at').first()`
- Summary model structure unchanged
- All endpoints unchanged

### For Chat/Genie Integration

```python
# Get historical summaries
summaries = Summary.objects.filter(
    topic=topic,
    created_at__gte=datetime.now() - timedelta(days=7)
).order_by('-created_at')

# Access cluster summaries
for summary in summaries:
    cluster_summaries = summary.cluster_summaries  # List of strings
    final_summary = summary.final_summary  # JSON dict
    clusters = summary.clusters  # List of cluster dicts
```

## Cost Estimation

### API Costs Per Day (per topic)

**Old System (1x per day):**
- OpenAI (cluster summaries): ~$0.10
- Gemini (final summary): ~$0.01
- Total: ~$0.11/day

**New System (conditional, ~6x per day):**
- OpenAI (cluster summaries): ~$0.60
- Gemini (final summary): ~$0.06
- Total: ~$0.66/day

**For 10 orgs × 3 topics each:**
- Old: ~$33/month
- New: ~$198/month (6x increase, but still very affordable)

### Database Growth

**Per topic over 30 days:**
- Summaries: ~200-300 records
- Average size per record: ~50 KB
- Total: ~10-15 MB per topic
- For 30 topics: ~300-450 MB (negligible)

## Migration from Old System

### During Transition

Both systems can run in parallel:
- Old `runnews`: Still works, generates summaries
- New `runclusternews`: Generates summaries when changes detected

### Recommended Approach

1. **Week 1**: Deploy new code, run migration
2. **Week 2**: Test `runclusternews` alongside `runnews`
3. **Week 3**: Setup Railway cron for `runclusternews` every 15 min
4. **Week 4**: Disable `runnews` cron (keep command for manual use)

### Rollback Plan

If issues arise:
1. Disable `runclusternews` cron
2. Re-enable `runnews` cron
3. System continues working with old behavior
4. No data loss (Summary records from both systems are compatible)

## Future Enhancements

### Possible Additions

1. **Playback Feature**: Visualize cluster evolution over time
   ```python
   # Get all summaries for a day
   summaries = Summary.objects.filter(
       topic=topic,
       created_at__date=date(2024, 1, 15)
   ).order_by('created_at')
   ```

2. **Custom Thresholds per Organization**:
   ```python
   # Add field to Organization model
   cluster_change_threshold = models.FloatField(default=0.40)
   summary_change_threshold = models.FloatField(default=0.40)
   ```

3. **Real-time Notifications**:
   ```python
   # When major change detected
   if cluster_diff > 0.60:  # More than 60% change
       notify_users(topic, "Major news update")
   ```

4. **Cluster Analytics**:
   ```python
   # Track cluster lifespan
   track_cluster_lifecycle(cluster_id, start_time, end_time)
   ```

## Summary

This implementation provides:
- ✅ Continuous news processing (every 15 minutes)
- ✅ Smart conditional summarization (40% threshold)
- ✅ Minimal database changes (1 new field)
- ✅ Backward compatible (old system still works)
- ✅ Easy to deploy (2 cron jobs)
- ✅ Cost-effective (~$200/month for 30 topics)
- ✅ Ready for production

**Next Steps:**
1. Run migration: `python manage.py migrate`
2. Test locally: `python manage.py runclusternews`
3. Setup Railway cron jobs
4. Monitor for a week
5. Disable old `runnews` cron

Questions? Check the logs at `cluster_news_processing.log`

