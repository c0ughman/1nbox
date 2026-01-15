# SendGrid 401 Unauthorized Error - Troubleshooting Guide

## What I Fixed in the Code

### Issues Found:
1. **No API Key Validation**: Code was creating SendGrid client even if API key was `None` or invalid
2. **Poor Error Handling**: Generic exception catching didn't show specific 401 error details
3. **Duplicate Initialization**: SendGrid client was initialized twice in `message.py`
4. **No Response Status Checking**: Didn't check if SendGrid returned non-200 status codes

### Fixes Applied:
1. ✅ Added `get_sendgrid_client()` function with API key validation
2. ✅ Validates API key exists and starts with `'SG.'` format
3. ✅ Enhanced error logging with specific 401 troubleshooting steps
4. ✅ Added response status code checking
5. ✅ Removed duplicate SendGrid initialization

## Common Causes of 401 Errors (Besides IP Allowlist)

### 1. **Missing or Incorrect API Key** ⚠️ MOST COMMON
- **Check**: Railway environment variables → `SENDGRID_API_KEY`
- **Verify**: API key starts with `SG.` (e.g., `SG.xxxxxxxxxxxxx`)
- **Fix**: Copy the API key from SendGrid Dashboard → Settings → API Keys

### 2. **API Key Revoked or Expired**
- **Check**: SendGrid Dashboard → Settings → API Keys
- **Verify**: The API key shows as "Active" (not revoked)
- **Fix**: Create a new API key and update Railway

### 3. **API Key Missing Permissions**
- **Check**: SendGrid Dashboard → Settings → API Keys → Click your key
- **Verify**: "Mail Send" permission is enabled
- **Fix**: Edit the API key and enable "Mail Send" permission

### 4. **Unverified Sender Email**
- **Check**: SendGrid Dashboard → Settings → Sender Authentication
- **Verify**: `feed@trybriefed.com` is verified/authenticated
- **Fix**: Complete Single Sender Verification or Domain Authentication

### 5. **API Key Format Issues**
- **Check**: Railway logs will now show first 10 characters of API key
- **Verify**: Key starts with `SG.` and is the full key (not truncated)
- **Fix**: Re-copy the entire API key from SendGrid

### 6. **Environment Variable Not Set in Railway**
- **Check**: Railway Dashboard → Your Service → Variables
- **Verify**: `SENDGRID_API_KEY` exists and has a value
- **Fix**: Add the environment variable in Railway

## How to Debug 401 Errors Now

The updated code will now log detailed information when a 401 occurs:

```
⚠️  401 Unauthorized - Check:
   1. SENDGRID_API_KEY is set in Railway environment variables
   2. API key is correct and starts with 'SG.'
   3. API key has 'Mail Send' permissions
   4. API key hasn't been revoked
   5. Current API key value (first 10 chars): SG.xxxxx...
   6. Sender email 'feed@trybriefed.com' is verified in SendGrid
```

## Quick Checklist

- [ ] `SENDGRID_API_KEY` is set in Railway environment variables
- [ ] API key starts with `SG.` (correct format)
- [ ] API key has "Mail Send" permissions enabled
- [ ] API key is active (not revoked) in SendGrid
- [ ] Sender email `feed@trybriefed.com` is verified in SendGrid
- [ ] IP Allowlist is empty (or Railway IPs are added)
- [ ] Railway service has been redeployed after adding the API key

## Next Steps

1. **Check Railway Logs**: After deploying, try sending an email/invitation
2. **Look for the detailed error messages** I added - they'll tell you exactly what's wrong
3. **Verify each item** in the checklist above
4. **Most likely issue**: API key not set in Railway or incorrect format

## Testing

After deploying these fixes, the logs will show:
- ✅ Success messages with status codes
- ❌ Detailed error messages with troubleshooting steps
- ⚠️ Specific validation errors if API key is missing/invalid

This will make it much easier to identify the exact cause of 401 errors!

