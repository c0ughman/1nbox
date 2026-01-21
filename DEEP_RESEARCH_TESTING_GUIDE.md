# Deep Research Testing Guide

## 🚀 Quick Start Testing

### Prerequisites

1. **API Key**: You need a Gemini API key with **Interactions API** access
2. **Database Migration**: Run the migration to add new fields
3. **Python Package**: Ensure `google-generativeai` package is up to date

---

## 📋 Step-by-Step Testing Instructions

### 1. Environment Setup

#### Required Environment Variable

You need **ONE** of these set (both work, code checks both):

```bash
export GEMINI_API_KEY="your-gemini-api-key-here"
# OR
export GEMINI_KEY="your-gemini-api-key-here"
```

**Important**: Your Gemini API key must have access to the **Interactions API** (which includes Deep Research).

#### Check Your API Key

The same API key you use for regular Gemini calls should work. If you get errors about "Interactions API not available", you may need to:
- Enable the Interactions API in Google AI Studio
- Check your API key permissions
- Ensure you're using a valid Gemini API key (not Vertex AI)

---

### 2. Database Migration

**CRITICAL**: Run this before testing!

```bash
cd /Users/coughman/Desktop/Briefed/briefed/1nbox
python manage.py migrate _1nbox_ai
```

Expected output:
```
Running migrations:
  Applying _1nbox_ai.0007_add_deep_research_fields... OK
```

---

### 3. Python Package Check

The code uses:
- `google.generativeai` (for regular Gemini calls) ✅ Already in requirements.txt
- `google.genai` (for Interactions API) ⚠️ May need update

**Check if package is installed:**

```bash
python3 -c "from google import genai; print('✅ google.genai available')"
```

If you get an error, update the package:

```bash
pip install --upgrade google-generativeai
```

**Note**: The `google-generativeai` package should include both `google.generativeai` and `google.genai`. If not, you may need to install `google-genai` separately (check Google's latest docs).

---

### 4. Test Quick/Comprehensive Mode (No Deep Research)

**Purpose**: Verify existing functionality still works

1. **Start your backend server**
   ```bash
   python manage.py runserver
   ```

2. **Open Genie in browser**
   - Navigate to your Genie page
   - Make sure "Comprehensive" is selected (not "Deep Research")

3. **Enter a test query**
   ```
   What are the latest trends in AI?
   ```

4. **Click "Generate Insight"**
   - Should generate questionnaire quickly (2-3 seconds)
   - No Deep Research should start

5. **Complete questionnaire**
   - Answer all questions
   - Select topics
   - Click "Generate Analysis"

6. **Expected Result**
   - Analysis generates normally (5-10 seconds)
   - No Deep Research involved
   - Works exactly as before

**✅ If this works, your basic setup is correct!**

---

### 5. Test Deep Research Mode

**Purpose**: Verify Deep Research integration works end-to-end

#### Test A: Simple Query (5-8 minutes)

1. **Open Genie**
   - Select **"Deep Research"** from the Analysis Depth dropdown
   - This is critical - must select Deep Research!

2. **Enter query**
   ```
   Should we invest in AI infrastructure in the next 6 months?
   ```

3. **Click "Generate Insight"**
   - Check browser console (F12 → Console)
   - Should see: `Deep Research started: interactions/...`
   - Questionnaire should appear

4. **Complete questionnaire** (1-2 minutes)
   - Answer questions normally
   - Deep Research is running in background

5. **Click "Generate Analysis"**
   - Loading screen should show: "Conducting deep research..."
   - Button text: "Conducting deep research..."

6. **Wait for completion** (5-10 minutes)
   - Backend polls every 10 seconds
   - Check backend logs for progress

7. **Expected Result**
   - Analysis includes Deep Research findings
   - Response has `deep_research_included: true`
   - More comprehensive than Quick/Comprehensive mode

#### Test B: Complex Query (10-15 minutes)

1. **Select "Deep Research"**
2. **Enter complex query**
   ```
   What is the competitive landscape for enterprise AI solutions, and what are the risks and opportunities for a mid-size SaaS company entering this market in the next 12 months?
   ```

3. **Follow same steps as Test A**
4. **Expected**: Takes longer but provides more comprehensive research

---

### 6. Monitor Backend Logs

**What to look for:**

#### Successful Flow:
```
Deep Research started: interactions/abc123xyz
Polling for Deep Research results: interactions/abc123xyz
Deep Research still processing... 540s remaining
Deep Research still processing... 480s remaining
...
Deep Research completed: interactions/abc123xyz
Deep Research completed successfully. Length: 15234 chars
```

#### Error Scenarios:
```
Failed to start Deep Research: [error message]
# OR
Deep Research failed: [error message]
# OR
Deep Research timed out: Deep Research exceeded 15 minute timeout
```

---

### 7. Verify Database

**Check that data is stored correctly:**

```python
# In Django shell: python manage.py shell
from _1nbox_ai.models import GenieAnalysis

# Get latest analysis
analysis = GenieAnalysis.objects.latest('created_at')

# Check fields
print(f"Research Type: {analysis.research_type}")
print(f"Deep Research ID: {analysis.deep_research_id}")
print(f"Has Results: {bool(analysis.deep_research_results)}")
print(f"Results Length: {len(analysis.deep_research_results) if analysis.deep_research_results else 0}")
```

**Expected for Deep Research:**
- `research_type`: `'deep'`
- `deep_research_id`: `'interactions/...'`
- `deep_research_results`: Long text string with research findings

---

### 8. Test Error Scenarios

#### Test A: Invalid API Key

```bash
# Temporarily set invalid key
export GEMINI_API_KEY="invalid-key"
# Restart server
```

**Expected**: Error message when starting Deep Research
```
Failed to start Deep Research: [API error]
```

#### Test B: Network Issues

- Simulate network interruption during polling
- **Expected**: Timeout after 15 minutes with error message

#### Test C: Missing Research Type

- Don't select Deep Research, but try to use it
- **Expected**: No Deep Research starts (normal flow)

---

## 🔍 Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'google.genai'"

**Solution:**
```bash
pip install --upgrade google-generativeai
# OR if that doesn't work:
pip install google-genai
```

**Check Google's latest documentation** - package name may have changed.

### Issue: "Failed to start Deep Research: Interactions API not available"

**Possible Causes:**
1. API key doesn't have Interactions API access
2. API key is for Vertex AI (not Google AI Studio)
3. Interactions API not enabled for your project

**Solution:**
- Get API key from [Google AI Studio](https://aistudio.google.com/)
- Ensure Interactions API is enabled
- Check API key permissions

### Issue: "Deep Research timed out"

**Normal Behavior:**
- Complex queries can take 10-15 minutes
- Some queries may exceed 15-minute timeout

**Solution:**
- Increase timeout in `get_deep_research_results()` function
- Or retry with simpler query

### Issue: Analysis doesn't include Deep Research

**Check:**
1. Response JSON: Look for `deep_research_included: true`
2. Database: Check `deep_research_results` field
3. Backend logs: Verify Deep Research completed

**Solution:**
- Check backend logs for errors
- Verify Deep Research actually completed
- Check database fields populated

### Issue: Frontend doesn't show "Deep Research" option

**Check:**
- HTML file: `1nbox-frontend/pages/genie.html`
- Should have dropdown with "Deep Research" option
- Already exists in your codebase!

---

## ✅ Success Criteria

Your implementation is working correctly if:

1. ✅ Quick/Comprehensive modes work as before
2. ✅ Deep Research option appears in dropdown
3. ✅ Selecting Deep Research starts research in background
4. ✅ Loading screen waits for Deep Research
5. ✅ Final analysis includes Deep Research findings
6. ✅ Database stores all Deep Research data
7. ✅ Error messages are clear and helpful

---

## 📊 Expected Performance

| Mode | Questionnaire | Research | Final Analysis | Total Time |
|------|--------------|----------|----------------|------------|
| Quick | 2-3 sec | N/A | 5-10 sec | ~10 seconds |
| Comprehensive | 2-3 sec | N/A | 5-10 sec | ~10 seconds |
| Deep Research | 2-3 sec | 5-15 min | 5-10 sec | ~5-15 minutes |

**Cost per Request:**
- Quick/Comprehensive: ~$0.10-0.50
- Deep Research: ~$2-5

---

## 🎯 Testing Checklist

Before deploying to production:

- [ ] Environment variable set (`GEMINI_API_KEY` or `GEMINI_KEY`)
- [ ] Database migration run successfully
- [ ] Python package installed/updated (`google-generativeai`)
- [ ] Quick mode tested (works as before)
- [ ] Comprehensive mode tested (works as before)
- [ ] Deep Research mode tested (simple query)
- [ ] Deep Research mode tested (complex query)
- [ ] Backend logs checked (no errors)
- [ ] Database verified (fields populated)
- [ ] Error scenarios tested (invalid key, timeout)
- [ ] Frontend UI verified (dropdown works)
- [ ] Loading messages verified (correct text shown)

---

## 🚨 Common Mistakes

1. **Forgot to select "Deep Research"** - Most common! Must select from dropdown
2. **API key not set** - Check environment variable
3. **Migration not run** - Database fields missing
4. **Wrong API key type** - Need Google AI Studio key, not Vertex AI
5. **Package not updated** - `google-generativeai` needs to be latest version

---

## 📞 Getting Help

If you encounter issues:

1. **Check backend logs** - Most errors are logged there
2. **Check browser console** - Frontend errors appear here
3. **Verify API key** - Test with simple Gemini call first
4. **Check database** - Verify migration ran successfully
5. **Review documentation** - See `DEEP_RESEARCH_IMPLEMENTATION.md`

---

## 🎉 Ready to Test!

Follow the steps above and you should be able to test Deep Research successfully. Start with Quick/Comprehensive mode to verify basic setup, then test Deep Research with a simple query.

Good luck! 🚀

