# Creating a New SendGrid API Key

## Why You Need a New Key

SendGrid **only shows the full API key once** when you create it - for security reasons. After that, you can only see:
- The API Key **ID** (like `key_123456`)
- The last few characters (like `...xxxxx`)
- But NOT the full secret key

Since you can't access Heroku to get the old key, you need to create a new one.

---

## Step-by-Step: Create New SendGrid API Key

### Step 1: Go to SendGrid Dashboard
1. Log into https://app.sendgrid.com
2. Make sure you're in the correct account (if you have multiple)

### Step 2: Navigate to API Keys
1. Click **"Settings"** in the left sidebar
2. Click **"API Keys"** under Settings

### Step 3: Create New API Key
1. Click the **"Create API Key"** button (usually top right)
2. You'll see a form with:
   - **API Key Name**: Enter `Briefed Production` (or any name you want)
   - **API Key Permissions**: Choose one:
     - ✅ **"Full Access"** (recommended - gives all permissions)
     - OR **"Restricted Access"** → Then select at minimum:
       - ✅ **"Mail Send"** permission
       - (You can add more permissions if needed later)

### Step 4: Copy the Key IMMEDIATELY
1. Click **"Create & View"** button
2. **⚠️ IMPORTANT**: SendGrid will show you the full API key **ONLY ONCE**
3. It will look like: `SG.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
   - Starts with `SG.`
   - About 69 characters long
4. **Copy the ENTIRE key immediately** - you won't see it again!
5. Store it somewhere safe temporarily (password manager, notes app, etc.)

### Step 5: Add to Railway
1. Go to **Railway Dashboard**: https://railway.app
2. Select your **Web Service** (the main backend service)
3. Click **"Variables"** tab
4. Click **"+ New Variable"** or **"Add Variable"**
5. Enter:
   - **Variable Name**: `SENDGRID_API_KEY`
   - **Value**: Paste the full API key you just copied (starts with `SG.`)
6. Click **"Add"** or **"Save"**

### Step 6: Redeploy Railway Service
1. Railway should auto-deploy, or
2. Go to **Deployments** tab and click **"Redeploy"**
3. Wait for deployment to complete

### Step 7: Test It
1. Try sending an email/invitation from your app
2. Check Railway logs for any SendGrid errors
3. If you see 401 errors, check:
   - API key is set correctly in Railway
   - No extra spaces or newlines
   - Key starts with `SG.`

---

## Optional: Revoke Old API Key (Recommended)

Since you can't access the old key anyway, you should revoke it for security:

1. Go back to SendGrid → Settings → API Keys
2. Find the old API key (might be named something like "Heroku" or "Production")
3. Click the **three dots** (...) or **actions** menu next to it
4. Click **"Delete"** or **"Revoke"**
5. Confirm deletion

**Why revoke it?**
- Prevents unauthorized access if someone has the old key
- Keeps your SendGrid account secure
- You can't use it anyway since you don't have the secret

---

## Quick Checklist

- [ ] Created new API key in SendGrid
- [ ] Copied the full key (starts with `SG.`)
- [ ] Added `SENDGRID_API_KEY` to Railway environment variables
- [ ] Value in Railway is the full key (no quotes, no spaces)
- [ ] Railway service redeployed
- [ ] Tested sending email - works!
- [ ] (Optional) Revoked old API key in SendGrid

---

## Troubleshooting

### "I didn't copy the key in time!"
- **Solution**: You'll need to create another new API key
- SendGrid cannot show you the key again for security reasons

### "The key doesn't start with SG."
- Make sure you copied the **entire** key
- Check you're copying from "API Keys" → "Create & View"
- Not from API Key ID or other sections

### "Still getting 401 errors"
- Verify the key is set in Railway (check Variables tab)
- Make sure there are no extra spaces before/after the key
- Check SendGrid → Settings → IP Access Management (should be empty)
- Verify sender email `feed@trybriefed.com` is verified

---

## Security Best Practices

1. **Never commit API keys to Git** - They're already in Railway env vars
2. **Use different keys for different environments** (dev, staging, production)
3. **Rotate keys periodically** (every 6-12 months)
4. **Revoke unused keys** - Delete old keys you're not using
5. **Use restricted access** when possible (only grant needed permissions)

---

That's it! Once you add the new key to Railway and redeploy, your SendGrid integration should work.

