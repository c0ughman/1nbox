# SendGrid Setup Guide for Railway

## Problem: 401 Unauthorized Errors

When you get `401 Unauthorized` errors from SendGrid, it's usually one of these issues:

1. **API Key not set** in Railway environment variables
2. **IP Allowlist blocking** Railway's IP addresses
3. **Sender verification** not completed for `feed@trybriefed.com`
4. **API Key permissions** insufficient

---

## Step-by-Step Fix

### Step 1: Verify API Key in Railway

1. Go to **Railway Dashboard** → Your **Web Service**
2. Click **"Variables"** tab
3. Check if `SENDGRID_API_KEY` exists
4. If missing, add it:
   - Variable name: `SENDGRID_API_KEY`
   - Value: Your SendGrid API key (starts with `SG.`)

---

### Step 2: Get/Create SendGrid API Key

1. Go to **SendGrid Dashboard**: https://app.sendgrid.com
2. Navigate to **Settings** → **API Keys**
3. Click **"Create API Key"**
4. Name it: `Briefed Production`
5. Select **"Full Access"** (or at minimum: **"Mail Send"** permissions)
6. Click **"Create & View"**
7. **Copy the API key immediately** (you won't see it again!)
8. Add it to Railway as `SENDGRID_API_KEY`

---

### Step 3: Remove IP Allowlist (Required for Railway)

**What is IP Allowlist?**
- IP Allowlist restricts SendGrid API access to **specific IP addresses only**
- When enabled, SendGrid **ONLY accepts API calls** from IPs in the list
- If your app's IP isn't in the list → **401 Unauthorized error**
- Railway uses **dynamic IPs** that change with each deployment → breaks allowlist

**The IP You See:**
- The IP address showing your city is likely from:
  - Your **Heroku backend** (old hosting)
  - Your **local machine** (if you tested locally)
  - Not Railway's current IP (which changes constantly)

**How to Fix (Remove All IPs):**

1. Go to **SendGrid Dashboard** → **Settings** → **IP Access Management**
2. You'll see a list of allowed IP addresses
3. **Delete/Remove ALL IP addresses** from the list:
   - Click the **trash/delete icon** (🗑️) next to each IP
   - Or select the IP and click **"Remove"** or **"Delete"** button
   - Remove every IP until the list is **empty**
4. **Empty allowlist = No IP restrictions**
   - SendGrid will accept API calls from any IP
   - Security comes from your API key (not IP address)

**Why This Works:**
- When allowlist is **empty**, SendGrid doesn't restrict by IP
- Railway can use any IP address (since they're dynamic)
- Your API key provides the security instead

**Important**: Make sure you have your API key saved before removing IPs, in case you get locked out!

---

### Step 4: Verify Sender Email

SendGrid needs to verify the sender email address:

1. Go to **SendGrid Dashboard** → **Settings** → **Sender Authentication**
2. Look for **"Single Sender Verification"** or **"Domain Authentication"**

   **Option A: Single Sender Verification (Quick)**
   - Click **"Verify a Single Sender"**
   - Enter: `feed@trybriefed.com`
   - Fill in the form (name, company, address, etc.)
   - Check your email and click the verification link
   - Status should show **"Verified"**

   **Option B: Domain Authentication (Better for Production)**
   - Click **"Authenticate Your Domain"**
   - Enter: `trybriefed.com`
   - Follow DNS setup instructions
   - Add the required DNS records to your domain
   - Status should show **"Authenticated"**

**Current code uses**: `feed@trybriefed.com`

---

### Step 5: Check API Key Permissions

1. Go to **SendGrid Dashboard** → **Settings** → **API Keys**
2. Find your API key
3. Click on it to view permissions
4. Ensure these are enabled:
   - ✅ **Mail Send** (required)
   - ✅ **Mail Send - Full Access** (if available)

---

### Step 6: Test the Configuration

After making changes:

1. **Redeploy** your Railway service (to pick up new env vars)
2. Try sending a test email:
   ```bash
   # On Railway terminal
   python manage.py runmessage --force
   ```
3. Check Railway logs for SendGrid errors
4. Check SendGrid Dashboard → **Activity** → **Email Activity** for delivery status

---

## Common Issues & Solutions

### Issue: "401 Unauthorized"
- ✅ Check `SENDGRID_API_KEY` is set in Railway
- ✅ Verify API key is correct (starts with `SG.`)
- ✅ Disable IP allowlist in SendGrid
- ✅ Check API key hasn't been revoked

### Issue: "403 Forbidden"
- ✅ Check sender email is verified (`feed@trybriefed.com`)
- ✅ Verify API key has "Mail Send" permissions
- ✅ Check if account is suspended (SendGrid Dashboard)

### Issue: "Email not sending but no error"
- ✅ Check SendGrid Activity Feed
- ✅ Verify sender email is verified
- ✅ Check spam folder
- ✅ Verify recipient email is valid

---

## Railway Environment Variable

Make sure this is set in **Railway Dashboard** → **Web Service** → **Variables**:

```
SENDGRID_API_KEY = SG.your-actual-api-key-here
```

**Important**: 
- No quotes around the value
- No spaces
- Copy the entire key (it's long)

---

## Verification Checklist

- [ ] `SENDGRID_API_KEY` is set in Railway
- [ ] API key starts with `SG.` and is correct
- [ ] IP Allowlist is **DISABLED** in SendGrid
- [ ] `feed@trybriefed.com` is verified in SendGrid
- [ ] API key has "Mail Send" permissions
- [ ] Railway service has been redeployed after adding env var

---

## Need Help?

If you're still getting 401 errors after these steps:

1. Check Railway logs for the exact error message
2. Check SendGrid Dashboard → **Activity** → **API Activity** for failed requests
3. Verify the API key is active (not revoked) in SendGrid

