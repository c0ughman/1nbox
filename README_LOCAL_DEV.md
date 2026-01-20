# 1nbox Local Development Setup - Complete ✅

## Status Summary

✅ **Backend**: Running on http://localhost:8000  
✅ **Frontend**: Running on http://localhost:3030  
✅ **Git Status**: Both repos are up to date with origin/main  
✅ **Configuration**: Localhost routing configured

## Git Repositories

### Backend (`1nbox/`)
- **Remote**: https://github.com/c0ughman/1nbox.git
- **Latest Commit**: f3bafab Update news.py
- **Status**: Up to date with origin/main, working tree clean

### Frontend (`1nbox-frontend/`)
- **Remote**: https://github.com/c0ughman/1nbox-frontend.git
- **Latest Commit**: 1dde632 Delete Desktop/Gather/gather directory
- **Status**: Up to date with origin/main, working tree clean

## Access Your Application

- **Frontend**: http://localhost:3030
- **Backend API**: http://localhost:8000
- **Django Admin**: http://localhost:8000/admin/

## Running News Gathering Workflow

To run the news gathering workflow, open a **new terminal** and run:

```bash
cd /Users/coughman/Desktop/Briefed/briefed/1nbox/1nbox
export DEBUG=true
python3 manage.py runnews
```

### Available Parameters:
- `--days`: Number of days to look back (default: 1)
- `--min_articles`: Minimum articles per cluster (default: 3)
- `--common_word_threshold`: Common words for clustering (default: 2)
- `--top_words_to_consider`: Top words to consider (default: 3)
- `--merge_threshold`: Merge threshold (default: 2)
- `--join_percentage`: Join percentage (default: 0.5)
- `--final_merge_percentage`: Final merge percentage (default: 0.5)
- `--sentences_final_summary`: Sentences per topic (default: 3)
- `--title_only`: Use only titles for clustering
- `--all_words`: Include all words, not just capitalized

Example:
```bash
python3 manage.py runnews --days 2 --min_articles 5
```

## Server Management

### Check Running Servers
```bash
ps aux | grep -E "(runserver|server.py)" | grep -v grep
```

### Stop Servers
```bash
# Stop backend
pkill -f "manage.py runserver 8000"

# Stop frontend
pkill -f "server.py"
```

### Restart Servers

**Backend:**
```bash
cd /Users/coughman/Desktop/Briefed/briefed/1nbox/1nbox
export DEBUG=true
python3 manage.py runserver 8000
```

**Frontend:**
```bash
cd /Users/coughman/Desktop/Briefed/briefed/1nbox/1nbox-frontend
python3 server.py
```

Note: The frontend now uses a custom server (`server.py`) that properly handles SPA (Single Page Application) routing, so routes like `/main`, `/pricing`, `/login` will work correctly.

## What Was Configured

### Backend Changes (`1nbox/_1nbox_ai/settings.py`)
1. Added `localhost` to `ALLOWED_HOSTS`
2. Added `http://localhost:3030` to `CORS_ALLOWED_ORIGINS`
3. Made `DEBUG` configurable via environment variable
4. Made `django_heroku` optional (for local development)
5. Database defaults to SQLite if `DATABASE_URL` is not set
6. Firebase initialization made optional (graceful fallback if credentials missing)

### Frontend Changes
1. Created `js/api-config.js` - Automatically redirects API calls from Heroku to localhost
2. Added API config script to:
   - `pages/main.html`
   - `pages/home.html`
   - `pages/login.html`
   - `pages/signup.html`

## Notes

- **Firebase**: The app will run without Firebase credentials, but authentication features won't work. You'll need to set up Firebase environment variables for full functionality.
- **Database**: Using SQLite (`db.sqlite3`) for local development
- **API Routing**: The frontend automatically redirects all API calls from the production Heroku URL to `http://localhost:8000`
- **Sign Up**: You can sign up through the frontend at http://localhost:3030/pages/signup.html (though Firebase auth will need credentials)

## Next Steps

1. **Access the frontend**: Open http://localhost:3030 in your browser
2. **Sign up/Login**: Use the authentication pages (may need Firebase credentials)
3. **Run news gathering**: Use the command above to process news
4. **View results**: Check the main dashboard after running the news gathering workflow

## Troubleshooting

- **Backend won't start**: Check if port 8000 is available, or change the port
- **Frontend won't start**: Check if port 3030 is available, or change the port
- **CORS errors**: Ensure both servers are running and frontend accesses `http://localhost:3030`
- **Firebase errors**: Set Firebase environment variables or the app will run in limited mode

