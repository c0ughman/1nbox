# Installing google-genai Package on Railway

## ✅ Quick Fix: Trigger Rebuild

The `google-genai` package is already in `requirements.txt`. Railway just needs to rebuild to install it.

### Option 1: Railway CLI (Easiest)

```bash
# Navigate to your project
cd /Users/coughman/Desktop/Briefed/briefed/1nbox

# Link to your Railway project (if not already linked)
railway link

# Trigger a redeploy (this will rebuild and install new packages)
railway up
```

**OR** if you want to force a rebuild:

```bash
# Force a rebuild by pushing an empty commit
git commit --allow-empty -m "Trigger rebuild to install google-genai"
git push
```

### Option 2: Railway Dashboard (Manual)

1. Go to [Railway Dashboard](https://railway.app)
2. Select your project
3. Go to your service (the Django backend)
4. Click **"Deploy"** or **"Redeploy"** button
5. Railway will rebuild and install packages from `requirements.txt`

### Option 3: Push Latest Code

If you haven't pushed the updated `requirements.txt` yet:

```bash
cd /Users/coughman/Desktop/Briefed/briefed/1nbox
git add requirements.txt
git commit -m "Add google-genai package"
git push
```

Railway will automatically detect the push and rebuild.

---

## 🔍 Verify Installation

After rebuild, check the logs to verify the package was installed:

1. Go to Railway Dashboard → Your Service → Logs
2. Look for: `Collecting google-genai` or `Installing google-genai`
3. Check for any errors during installation

---

## ⚠️ If It Still Doesn't Work

If the package still isn't available after rebuild:

1. **Check Railway build logs** for installation errors
2. **Verify requirements.txt** is in the root of your project
3. **Check Python version** - `google-genai` requires Python 3.8+
4. **Try specifying version** in requirements.txt:
   ```
   google-genai>=1.0.0
   ```

---

## 🚀 Quick Command Summary

```bash
# Make sure requirements.txt is committed
cd /Users/coughman/Desktop/Briefed/briefed/1nbox
git add requirements.txt
git commit -m "Add google-genai package"
git push

# Railway will automatically rebuild
# Or trigger manually:
railway up
```

---

## ✅ Success Indicators

After rebuild, you should see in Railway logs:
- ✅ `Collecting google-genai`
- ✅ `Installing collected packages: google-genai`
- ✅ No import errors when starting the app
- ✅ Deep Research feature works

---

The package is already in `requirements.txt` - Railway just needs to rebuild to install it!

