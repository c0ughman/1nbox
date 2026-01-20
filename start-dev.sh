#!/bin/bash

# Development startup script for 1nbox
# This script starts both backend and frontend servers

echo "Starting 1nbox Development Environment..."
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if we're in the right directory
if [ ! -f "1nbox/manage.py" ]; then
    echo "Error: Please run this script from the 1nbox root directory"
    exit 1
fi

# Function to check if a port is in use
check_port() {
    lsof -Pi :$1 -sTCP:LISTEN -t >/dev/null
    return $?
}

# Check if ports are available
if check_port 8000; then
    echo -e "${YELLOW}Warning: Port 8000 is already in use${NC}"
fi

if check_port 3030; then
    echo -e "${YELLOW}Warning: Port 3030 is already in use${NC}"
fi

# Start backend in background
echo -e "${BLUE}Starting Django backend on http://localhost:8000...${NC}"
cd 1nbox
python3 manage.py runserver 8000 > ../backend.log 2>&1 &
BACKEND_PID=$!
cd ..

# Wait a moment for backend to start
sleep 3

# Start frontend
echo -e "${BLUE}Starting frontend on http://localhost:3030...${NC}"
cd 1nbox-frontend
python3 -m http.server 3030 > ../frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..

echo ""
echo -e "${GREEN}✓ Backend running on http://localhost:8000 (PID: $BACKEND_PID)${NC}"
echo -e "${GREEN}✓ Frontend running on http://localhost:3030 (PID: $FRONTEND_PID)${NC}"
echo ""
echo "Logs:"
echo "  Backend:  tail -f backend.log"
echo "  Frontend: tail -f frontend.log"
echo ""
echo "To stop servers, run: kill $BACKEND_PID $FRONTEND_PID"
echo ""
echo "Press Ctrl+C to stop all servers"

# Wait for user interrupt
trap "echo ''; echo 'Stopping servers...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT
wait


