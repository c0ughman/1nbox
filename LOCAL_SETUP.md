# Local Development Setup for 1nbox

## Git Status

### Backend Repository (`1nbox/`)
- **Remote**: https://github.com/c0ughman/1nbox.git
- **Branch**: main
- **Status**: Up to date with origin/main, working tree clean

### Frontend Repository (`1nbox-frontend/`)
- **Remote**: https://github.com/c0ughman/1nbox-frontend.git
- **Branch**: main
- **Status**: Up to date with origin/main, working tree clean

## Quick Start

### Prerequisites
1. Python 3.11+ (you have Python 3.11.5 ✓)
2. Install backend dependencies:
   ```bash
   cd 1nbox
   pip3 install -r requirements.txt
   ```

### Starting the Servers

#### Option 1: Use the startup scripts (Recommended)

**Terminal 1 - Backend:**
```bash
cd /Users/coughman/Desktop/Briefed/briefed/1nbox
./start-backend.sh
```

**Terminal 2 - Frontend:**
```bash
cd /Users/coughman/Desktop/Briefed/briefed/1nbox
./start-frontend.sh
```

#### Option 2: Manual startup

**Terminal 1 - Backend:**
```bash
cd 1nbox
export DEBUG=true
python3 manage.py migrate
python3 manage.py runserver 8000
```

**Terminal 2 - Frontend:**
```bash
cd 1nbox-frontend
python3 -m http.server 3030
```

### Access the Application
- **Frontend**: http://localhost:3030
- **Backend API**: http://localhost:8000

## Running News Gathering Workflow

Once both servers are running, in a **Terminal 3**, run:

```bash
cd 1nbox
export DEBUG=true
python3 manage.py runnews
```

This will process all topics and gather news. You can add parameters:
```bash
python3 manage.py runnews --days 1 --min_articles 3
```

## Configuration Changes Made

1. **Backend (`1nbox/_1nbox_ai/settings.py`)**:
   - Added `localhost` to `ALLOWED_HOSTS`
   - Added `http://localhost:3030` and `http://127.0.0.1:3030` to `CORS_ALLOWED_ORIGINS`
   - Made `DEBUG` configurable via `DEBUG` environment variable
   - Made `django_heroku` optional (for local development)
   - Database defaults to SQLite if `DATABASE_URL` is not set

2. **Frontend**:
   - Created `js/api-config.js` to automatically redirect API calls from Heroku URL to localhost
   - Added API config script to `main.html`, `home.html`, `login.html`, and `signup.html`

## Notes

- The frontend will automatically redirect API calls from the production Heroku URL to `http://localhost:8000`
- You may need to sign up/login through the frontend to access the main dashboard
- The news gathering workflow runs as a Django management command and processes all topics in the database

## Troubleshooting

1. **ModuleNotFoundError**: Install dependencies with `pip3 install -r requirements.txt` in the `1nbox` directory
2. **Port already in use**: Change the port in the startup scripts or kill the process using the port
3. **Database errors**: Run `python3 manage.py migrate` in the `1nbox` directory
4. **CORS errors**: Make sure both servers are running and the frontend is accessing `http://localhost:3030`


