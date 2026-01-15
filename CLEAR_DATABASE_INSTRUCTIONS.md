# How to Clear Database Data in Railway

## Method 1: Railway Dashboard (Easiest)

### Step 1: Access PostgreSQL Service
1. Go to **Railway Dashboard**: https://railway.app
2. Select your **Briefed project**
3. Find your **PostgreSQL service** (usually named "Postgres" or "Database")
4. Click on it

### Step 2: Open Query Tab
1. Look for tabs: **"Data"**, **"Query"**, **"SQL"**, or **"Connect"**
2. Click on **"Query"** or **"Data"** tab
3. You should see a SQL query editor/interface

### Step 3: Run SQL Commands
Copy and paste these commands (one at a time or all together):

```sql
DELETE FROM _1nbox_ai_bitesdigest;
DELETE FROM _1nbox_ai_bitessubscription;
DELETE FROM _1nbox_ai_genieanalysis;
DELETE FROM _1nbox_ai_chatmessage;
DELETE FROM _1nbox_ai_chatconversation;
DELETE FROM _1nbox_ai_comment;
DELETE FROM _1nbox_ai_summary;
DELETE FROM _1nbox_ai_topic;
DELETE FROM _1nbox_ai_user;
DELETE FROM _1nbox_ai_organization;
```

Click **"Run"** or **"Execute"**

---

## Method 2: Use Railway Web Service Terminal

### Step 1: Access Web Service Terminal
1. Go to **Railway Dashboard** → Your **Web Service**
2. Click **"Deployments"** tab
3. Click on the latest deployment
4. Look for **"Terminal"**, **"Console"**, or **"Shell"** button
5. Click it to open a terminal

### Step 2: Run Management Command
In the terminal, run:

```bash
python manage.py clear_all_data --database-only --confirm
```

This will delete all database data without asking for confirmation.

---

## Method 3: Connect via psql (Advanced)

If Railway provides connection details:

1. Railway Dashboard → PostgreSQL → **"Connect"** or **"Variables"**
2. Copy the `DATABASE_URL` or connection string
3. Use psql locally:
   ```bash
   psql <DATABASE_URL>
   ```
4. Run the SQL commands from `clear_database.sql`

---

## What Gets Deleted

- All Organizations
- All Users  
- All Topics
- All Summaries
- All Comments
- All Chat Conversations & Messages
- All Genie Analyses
- All Bites Subscriptions & Digests

---

## After Clearing

You can now create a new user via the signup flow, and they will be the initial admin.

