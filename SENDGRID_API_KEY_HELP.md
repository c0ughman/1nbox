# SendGrid API Key - Where to Find It

## ⚠️ Important: Make Sure You're Copying the Right Thing!

If your API key doesn't start with `SG.`, you might be copying the wrong value from SendGrid.

## Where to Find Your SendGrid API Key

### Step 1: Go to SendGrid Dashboard
1. Log into https://app.sendgrid.com
2. Navigate to **Settings** → **API Keys**

### Step 2: Create or View API Key

**If creating a new key:**
1. Click **"Create API Key"**
2. Name it: `Briefed Production`
3. Select **"Full Access"** or **"Mail Send"** permissions
4. Click **"Create & View"**
5. **IMPORTANT**: Copy the key immediately - it shows only once!
6. The key will look like: `SG.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
   - Starts with `SG.`
   - About 69 characters long
   - Contains letters, numbers, dots, and dashes

**If viewing an existing key:**
- ⚠️ **You CANNOT see the full key again** after creation
- SendGrid only shows the last few characters (like `...xxxxx`)
- You'll need to create a new key if you lost the original

## What NOT to Copy

### ❌ API Key ID
- This is just an identifier (like `key_123456`)
- Does NOT start with `SG.`
- Cannot be used for authentication

### ❌ Webhook Secret
- Used for webhook verification
- Does NOT start with `SG.`
- Different format entirely

### ❌ API Key Name
- Just the name you gave it
- Not the actual key

## What the API Key Should Look Like

✅ **Correct Format:**
```
SG.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

- Starts with `SG.`
- About 69 characters total
- Contains: letters, numbers, dots (.), dashes (-), underscores (_)

## Common Mistakes

1. **Copying only part of the key** - Make sure you copy the ENTIRE key
2. **Copying API Key ID instead** - The ID is not the secret key
3. **Adding extra spaces** - No spaces before or after the key
4. **Copying from wrong place** - Must be from Settings → API Keys → Create & View

## If Your Key Doesn't Start with "SG."

If you have a key that doesn't start with `SG.`:

1. **Check where you got it from:**
   - Did you copy it from "API Keys" section?
   - Or from somewhere else (webhooks, settings, etc.)?

2. **Verify it's the right type:**
   - API Keys → Create & View → Shows full key starting with `SG.`
   - If you see something else, it's probably not the API key

3. **Create a new key:**
   - Go to Settings → API Keys
   - Create a new one
   - Copy it immediately (it shows only once)
   - Make sure it starts with `SG.`

4. **Check for whitespace:**
   - Make sure there are no spaces before/after the key
   - No newlines or extra characters

## Setting in Railway

When adding to Railway:
- Variable name: `SENDGRID_API_KEY`
- Value: The full key starting with `SG.` (no quotes, no spaces)
- Example: `SG.abc123def456ghi789jkl012mno345pqr678stu901vwx234yz`

## Still Having Issues?

If your key truly doesn't start with `SG.` but you got it from SendGrid:
1. Check SendGrid's documentation for your account type
2. Some older accounts might have different formats (rare)
3. Contact SendGrid support to verify your API key format
4. Try creating a fresh API key to see the current format

