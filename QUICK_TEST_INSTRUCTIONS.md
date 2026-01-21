# Quick Test Instructions - Deep Research

## 🎯 Fastest Way to Test

### 1. Prerequisites (2 minutes)

```bash
# Set API key (use your existing Gemini API key)
export GEMINI_API_KEY="your-api-key-here"

# Run migration
cd /Users/coughman/Desktop/Briefed/briefed/1nbox
python manage.py migrate _1nbox_ai

# Verify package (should already be installed)
pip show google-generativeai
# If not installed: pip install google-generativeai
```

**✅ That's it!** No additional API keys needed. Same Gemini API key works.

---

### 2. Test Quick Mode (30 seconds)

**Purpose**: Verify nothing broke

1. Open Genie
2. Keep "Comprehensive" selected (default)
3. Enter: `What are AI trends?`
4. Click "Generate Insight" → Complete questionnaire → Click "Generate Analysis"
5. **Expected**: Works exactly as before ✅

---

### 3. Test Deep Research (5-10 minutes)

**Purpose**: Verify Deep Research works

1. Open Genie
2. **Select "Deep Research"** from dropdown ⚠️ IMPORTANT!
3. Enter: `Should we invest in AI infrastructure in the next 6 months?`
4. Click "Generate Insight"
   - Check browser console (F12) → Should see: `Deep Research started: interactions/...`
5. Complete questionnaire (1-2 minutes)
6. Click "Generate Analysis"
   - Loading: "Conducting deep research..."
7. Wait 5-10 minutes
8. **Expected**: Comprehensive analysis with Deep Research findings ✅

---

## 🔍 What to Check

### Backend Logs

Look for:
```
Deep Research started: interactions/abc123
Polling for Deep Research results...
Deep Research completed successfully. Length: 12345 chars
```

### Browser Console

Look for:
```
Deep Research started: interactions/abc123xyz
```

### Database (Optional)

```python
python manage.py shell
>>> from _1nbox_ai.models import GenieAnalysis
>>> a = GenieAnalysis.objects.latest('created_at')
>>> print(a.research_type)  # Should be 'deep'
>>> print(bool(a.deep_research_results))  # Should be True
```

---

## ❌ Common Issues

### "Failed to start Deep Research"
- **Check**: API key is set (`echo $GEMINI_API_KEY`)
- **Check**: API key is valid (test with simple Gemini call)
- **Check**: API key has Interactions API access

### "ModuleNotFoundError: No module named 'google.genai'"
- **Fix**: `pip install --upgrade google-generativeai`
- The `google.genai` module is part of `google-generativeai` package

### Deep Research never completes
- **Normal**: Can take 5-15 minutes
- **Check**: Backend logs for polling status
- **Timeout**: Set to 15 minutes (configurable)

### Analysis doesn't include Deep Research
- **Check**: Did you select "Deep Research" from dropdown?
- **Check**: Response has `deep_research_included: true`
- **Check**: Database `deep_research_results` field populated

---

## ✅ Success Indicators

- ✅ Quick/Comprehensive modes work normally
- ✅ Deep Research option appears in dropdown
- ✅ Deep Research starts when selected
- ✅ Loading waits for Deep Research
- ✅ Final analysis includes research findings
- ✅ No errors in backend logs
- ✅ No errors in browser console

---

## 📞 Need Help?

1. Check `DEEP_RESEARCH_TESTING_GUIDE.md` for detailed instructions
2. Check backend logs for specific error messages
3. Verify API key is set correctly
4. Ensure migration ran successfully

---

## 🎉 That's It!

If Quick mode works and Deep Research completes successfully, you're all set! 🚀

