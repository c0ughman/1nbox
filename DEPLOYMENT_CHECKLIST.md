# 🚀 Deep Research Deployment Checklist

## ✅ Pre-Deployment Checklist

### 1. API Keys & Environment Variables

**✅ NO ADDITIONAL API KEYS NEEDED!**

You already have everything you need:
- ✅ **Same Gemini API Key**: Use your existing `GEMINI_API_KEY` or `GEMINI_KEY`
- ✅ **No new services**: Uses existing Google AI Studio API
- ✅ **No additional setup**: Just ensure API key has Interactions API access

**Environment Variable:**
```bash
export GEMINI_API_KEY="your-existing-gemini-api-key"
# OR
export GEMINI_KEY="your-existing-gemini-api-key"
```

**Note**: The same API key that works for regular Gemini calls should work for Deep Research. If you get errors, ensure:
- API key is from Google AI Studio (not Vertex AI)
- Interactions API is enabled for your project
- Billing is enabled (Deep Research costs $2-5 per request)

---

### 2. Python Packages

**✅ NO ADDITIONAL PACKAGES NEEDED!**

The code uses `google-generativeai` which is **already in your requirements.txt**.

**Verify installation:**
```bash
pip show google-generativeai
```

**If you get import errors:**
```bash
pip install --upgrade google-generativeai
```

The `google.genai` module (for Interactions API) is part of the `google-generativeai` package.

---

### 3. Database Migration

**✅ REQUIRED: Run migration before testing**

```bash
cd /Users/coughman/Desktop/Briefed/briefed/1nbox
python manage.py migrate _1nbox_ai
```

**Expected output:**
```
Running migrations:
  Applying _1nbox_ai.0007_add_deep_research_fields... OK
```

---

## 📦 Files Changed Summary

### Backend Files
- ✅ `1nbox/_1nbox_ai/models.py` - Added 3 new fields
- ✅ `1nbox/_1nbox_ai/genie_views.py` - Added Deep Research logic
- ✅ `1nbox/_1nbox_ai/migrations/0007_add_deep_research_fields.py` - NEW migration

### Frontend Files
- ✅ `1nbox-frontend/js/genie.js` - Added research type tracking

### Documentation Files (NEW)
- ✅ `DEEP_RESEARCH_IMPLEMENTATION.md` - Full technical guide
- ✅ `DEEP_RESEARCH_SUMMARY.md` - Quick reference
- ✅ `DEEP_RESEARCH_TESTING_GUIDE.md` - Detailed testing instructions
- ✅ `QUICK_TEST_INSTRUCTIONS.md` - Fast testing guide
- ✅ `GITHUB_COMMIT_GUIDE.md` - Commit instructions
- ✅ `DEPLOYMENT_CHECKLIST.md` - This file

---

## 🧪 Testing Instructions

### Quick Test (2 minutes)

1. **Set API key** (if not already set):
   ```bash
   export GEMINI_API_KEY="your-key"
   ```

2. **Run migration**:
   ```bash
   python manage.py migrate _1nbox_ai
   ```

3. **Start server**:
   ```bash
   python manage.py runserver
   ```

4. **Test Quick Mode**:
   - Open Genie
   - Keep "Comprehensive" selected
   - Enter query → Generate → Complete questionnaire
   - ✅ Should work as before

5. **Test Deep Research**:
   - Select "Deep Research" from dropdown
   - Enter: `Should we invest in AI in the next 6 months?`
   - Generate → Complete questionnaire → Wait 5-10 minutes
   - ✅ Should include comprehensive research

**See `QUICK_TEST_INSTRUCTIONS.md` for detailed steps.**

---

## 📤 Committing to GitHub

### Option 1: Simple Commit (Recommended)

```bash
cd /Users/coughman/Desktop/Briefed/briefed/1nbox

# Add all Deep Research files
git add 1nbox/_1nbox_ai/models.py
git add 1nbox/_1nbox_ai/genie_views.py
git add 1nbox/_1nbox_ai/migrations/0007_add_deep_research_fields.py
git add 1nbox-frontend/js/genie.js
git add DEEP_RESEARCH_*.md
git add QUICK_TEST_INSTRUCTIONS.md
git add GITHUB_COMMIT_GUIDE.md
git add DEPLOYMENT_CHECKLIST.md

# Commit
git commit -m "feat: Add Gemini Deep Research integration to Genie

- Add Deep Research option (Quick/Comprehensive/Deep Research)
- Start Deep Research in background when user clicks Generate
- Wait for Deep Research completion before final analysis
- Include Deep Research findings in comprehensive reports
- Add database fields and migration
- Update frontend to support research type selection
- Add comprehensive documentation"

# Push
git push origin main
```

### Option 2: If Using Submodules

If `1nbox` and `1nbox-frontend` are submodules:

```bash
# Commit in submodules first
cd 1nbox
git add _1nbox_ai/models.py _1nbox_ai/genie_views.py _1nbox_ai/migrations/0007_add_deep_research_fields.py
git commit -m "feat: Add Deep Research backend integration"
git push

cd ../1nbox-frontend
git add js/genie.js
git commit -m "feat: Add Deep Research frontend integration"
git push

# Then commit submodule updates
cd ..
git add 1nbox 1nbox-frontend
git add DEEP_RESEARCH_*.md QUICK_TEST_INSTRUCTIONS.md GITHUB_COMMIT_GUIDE.md DEPLOYMENT_CHECKLIST.md
git commit -m "feat: Add Deep Research feature with documentation"
git push
```

**See `GITHUB_COMMIT_GUIDE.md` for detailed instructions.**

---

## 🔍 What to Verify After Deployment

### 1. Backend Verification

**Check logs for:**
```
Deep Research started: interactions/abc123xyz
Polling for Deep Research results...
Deep Research completed successfully. Length: 12345 chars
```

**Test endpoints:**
- `POST /genie/questionnaire/` with `research_type: "deep"`
- Should return `deep_research_id` in response
- `POST /genie/analyze/` should wait for Deep Research

### 2. Frontend Verification

**Check browser console:**
- Should see: `Deep Research started: interactions/...`
- Loading message: "Conducting deep research..."

**UI checks:**
- Dropdown has "Deep Research" option
- Selecting it triggers Deep Research
- Loading screen shows correct message

### 3. Database Verification

```python
python manage.py shell
>>> from _1nbox_ai.models import GenieAnalysis
>>> a = GenieAnalysis.objects.filter(research_type='deep').first()
>>> print(a.research_type)  # 'deep'
>>> print(a.deep_research_id)  # 'interactions/...'
>>> print(len(a.deep_research_results))  # > 0
```

---

## ⚠️ Important Notes

### Cost Considerations

- **Quick/Comprehensive**: ~$0.10-0.50 per request (no change)
- **Deep Research**: ~$2-5 per request (new cost)

**Recommendation**: Consider adding usage limits per organization.

### Performance

- **Quick/Comprehensive**: ~10 seconds total
- **Deep Research**: ~5-15 minutes total
  - Most queries: 5-10 minutes
  - Complex queries: 10-15 minutes
  - Maximum: 60 minutes (Gemini limit)

### Error Handling

**Development Mode**: Errors are shown to users for debugging
**Production Mode**: Consider graceful fallback if Deep Research fails

Current behavior:
- If Deep Research fails → Error message returned
- If Deep Research times out → Error after 15 minutes
- If Deep Research not selected → Normal flow (no Deep Research)

---

## 🎯 Success Criteria

Your deployment is successful if:

- ✅ Migration runs without errors
- ✅ Quick/Comprehensive modes work as before
- ✅ Deep Research option appears in dropdown
- ✅ Deep Research starts when selected
- ✅ Loading waits for Deep Research completion
- ✅ Final analysis includes Deep Research findings
- ✅ Database stores research data correctly
- ✅ No errors in backend logs
- ✅ No errors in browser console

---

## 📚 Documentation Reference

After deployment, refer to:

1. **`QUICK_TEST_INSTRUCTIONS.md`** - Fast testing guide
2. **`DEEP_RESEARCH_TESTING_GUIDE.md`** - Comprehensive testing
3. **`DEEP_RESEARCH_IMPLEMENTATION.md`** - Technical details
4. **`DEEP_RESEARCH_SUMMARY.md`** - Quick reference

---

## 🆘 Troubleshooting

### Issue: "Failed to start Deep Research"

**Check:**
1. API key is set: `echo $GEMINI_API_KEY`
2. API key is valid (test with simple Gemini call)
3. API key has Interactions API access

**Solution:**
- Get API key from [Google AI Studio](https://aistudio.google.com/)
- Ensure Interactions API is enabled
- Check billing is enabled

### Issue: "ModuleNotFoundError: No module named 'google.genai'"

**Solution:**
```bash
pip install --upgrade google-generativeai
```

### Issue: Deep Research times out

**Normal**: Complex queries can take 10-15 minutes

**Solution:**
- Increase timeout in `get_deep_research_results()` function
- Or retry with simpler query

---

## ✅ Final Checklist

Before marking as complete:

- [ ] API key is set and working
- [ ] Migration ran successfully
- [ ] Quick mode tested (works as before)
- [ ] Deep Research tested (completes successfully)
- [ ] Backend logs show no errors
- [ ] Frontend console shows no errors
- [ ] Database fields populated correctly
- [ ] Documentation reviewed
- [ ] Code committed to GitHub
- [ ] Team notified of new feature

---

## 🎉 Ready to Deploy!

Everything is ready. Just:
1. Run migration
2. Test locally
3. Commit to GitHub
4. Deploy!

**Questions?** Check the documentation files or review the code comments.

Good luck! 🚀
