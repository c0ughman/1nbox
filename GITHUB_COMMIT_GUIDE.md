# GitHub Commit Guide - Deep Research Feature

## 📦 Files to Commit

### New Files (Add these)
```bash
git add 1nbox/_1nbox_ai/migrations/0007_add_deep_research_fields.py
git add DEEP_RESEARCH_IMPLEMENTATION.md
git add DEEP_RESEARCH_SUMMARY.md
git add DEEP_RESEARCH_TESTING_GUIDE.md
```

### Modified Files (Review and add)
```bash
# Backend changes
git add 1nbox/_1nbox_ai/models.py
git add 1nbox/_1nbox_ai/genie_views.py

# Frontend changes  
git add 1nbox-frontend/js/genie.js

# Note: 1nbox and 1nbox-frontend are submodules - commit those separately
```

---

## 🚀 Quick Commit Commands

### Step 1: Stage Deep Research Files

```bash
cd /Users/coughman/Desktop/Briefed/briefed/1nbox

# Add new migration
git add 1nbox/_1nbox_ai/migrations/0007_add_deep_research_fields.py

# Add documentation
git add DEEP_RESEARCH_IMPLEMENTATION.md
git add DEEP_RESEARCH_SUMMARY.md
git add DEEP_RESEARCH_TESTING_GUIDE.md

# Add modified backend files
git add 1nbox/_1nbox_ai/models.py
git add 1nbox/_1nbox_ai/genie_views.py

# Add modified frontend file
git add 1nbox-frontend/js/genie.js
```

### Step 2: Commit

```bash
git commit -m "feat: Add Gemini Deep Research integration to Genie

- Add Deep Research option (Quick/Comprehensive/Deep Research toggle)
- Start Deep Research in background when user clicks Generate
- Wait for Deep Research completion before final analysis
- Include Deep Research findings in comprehensive decision support reports
- Add database fields: research_type, deep_research_id, deep_research_results
- Add migration 0007_add_deep_research_fields
- Update frontend to support research type selection
- Add comprehensive documentation and testing guide

Features:
- Parallel execution: Deep Research runs while user answers questionnaire
- Smart waiting: Loading screen waits for research completion
- Decision-focused prompts: Research optimized for decision-making support
- Error handling: Clear error messages during development
- Cost-effective: Only runs when Deep Research is explicitly selected"
```

### Step 3: Push to GitHub

```bash
git push origin main
```

---

## 📝 Commit Message Template

If you prefer a different commit message:

```
feat(genie): Integrate Gemini Deep Research

Add Deep Research capability to Genie product:
- User can select Quick/Comprehensive/Deep Research modes
- Deep Research runs in parallel with questionnaire
- Final analysis includes comprehensive web research findings
- Database tracks research type and results

Technical changes:
- Add research_type, deep_research_id, deep_research_results fields
- Implement Deep Research start/poll functions
- Update questionnaire and analyze endpoints
- Frontend integration for research type selection

Documentation:
- Add implementation guide
- Add testing guide
- Add summary documentation
```

---

## ⚠️ Important Notes

### Submodules

If `1nbox` and `1nbox-frontend` are git submodules:

```bash
# Commit changes in submodules first
cd 1nbox
git add _1nbox_ai/models.py _1nbox_ai/genie_views.py _1nbox_ai/migrations/0007_add_deep_research_fields.py
git commit -m "feat: Add Deep Research fields and logic"
git push

cd ../1nbox-frontend
git add js/genie.js
git commit -m "feat: Add Deep Research frontend integration"
git push

# Then commit submodule updates in parent repo
cd ..
git add 1nbox 1nbox-frontend
git commit -m "chore: Update submodules for Deep Research feature"
```

### Don't Commit

- `__pycache__/` files (should be in .gitignore)
- `.env` files with API keys
- Database files
- Temporary test files

---

## ✅ Pre-Commit Checklist

- [ ] All tests pass (if you have tests)
- [ ] Migration file is correct
- [ ] No API keys in code
- [ ] Documentation is complete
- [ ] Code follows your style guide
- [ ] No console.logs or debug code (or remove before commit)

---

## 🔍 Verify After Commit

After pushing, verify on GitHub:

1. **Check files are committed**
   - Migration file exists
   - Documentation files exist
   - Code changes are present

2. **Review diff**
   - Ensure no sensitive data
   - Code looks correct
   - Documentation is helpful

3. **Test on fresh clone**
   ```bash
   git clone <your-repo>
   cd <repo>
   # Follow testing guide
   ```

---

## 📚 Related Documentation

After committing, these docs will be available:

- `DEEP_RESEARCH_IMPLEMENTATION.md` - Full technical guide
- `DEEP_RESEARCH_SUMMARY.md` - Quick reference
- `DEEP_RESEARCH_TESTING_GUIDE.md` - Testing instructions

