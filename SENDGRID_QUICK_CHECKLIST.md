# SendGrid Setup - Quick Checklist

## ✅ What You Need to Do

### 1. Create New API Key in SendGrid
- Go to SendGrid → Settings → API Keys → Create API Key
- Name: `Briefed Production`
- Permissions: **"Full Access"** (or at minimum "Mail Send")
- **Copy the key immediately** (starts with `SG.`)

### 2. Add to Railway
- Railway Dashboard → Your Web Service → Variables
- Add: `SENDGRID_API_KEY` = (paste the full key)
- **Redeploy** the service

### 3. Verify These SendGrid Settings (Should Already Be Done)

These were likely already configured, but double-check:

#### ✅ IP Allowlist
- **Should be EMPTY** (no IPs listed)
- Go to: SendGrid → Settings → IP Access Management
- If there are any IPs, delete them all
- **Why**: Railway uses dynamic IPs, so allowlisting breaks

#### ✅ Sender Email Verification
- **Should be VERIFIED**: `feed@trybriefed.com`
- Go to: SendGrid → Settings → Sender Authentication
- Check if `feed@trybriefed.com` shows as "Verified"
- **If not verified**: Complete Single Sender Verification
- **Why**: SendGrid requires verified senders

#### ✅ API Key Permissions (When Creating)
- Make sure the new key has **"Mail Send"** permission
- Or use **"Full Access"** for simplicity
- **Why**: Without permissions, API calls will fail

---

## Summary

**Minimum Required Changes:**
1. ✅ Create new API key in SendGrid
2. ✅ Add `SENDGRID_API_KEY` to Railway environment variables
3. ✅ Redeploy Railway service

**Quick Verification (Takes 2 minutes):**
1. ✅ Check IP Allowlist is empty
2. ✅ Check sender email is verified

**Optional but Recommended:**
- Revoke old API key in SendGrid (for security)

---

## That's It!

Once you:
1. Create the new key
2. Add it to Railway
3. Redeploy

Your SendGrid integration should work. The code will automatically use the new key from the environment variable.

If you still get 401 errors after this, check the Railway logs - they'll show detailed error messages about what's wrong.

