#!/bin/bash
# Start both backend and frontend for local dev

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Backend
echo "Starting backend on :8000 ..."
cd "$ROOT/backend"
[ ! -f .env ] && cp .env.example .env && echo "Created .env from .env.example — edit FUTU_HOST/PORT if needed"
pip install -q -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Frontend
echo "Starting frontend on :3000 ..."
cd "$ROOT/frontend"
npm install --silent
npm run dev &
FRONTEND_PID=$!

echo ""
echo "✓ Backend  http://localhost:8000"
echo "✓ Frontend http://localhost:3000"
echo "✓ API Docs http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop both."

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM
wait
