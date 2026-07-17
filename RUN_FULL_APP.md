# Running the Full EquityMind Application

Complete guide to run both FastAPI backend and React frontend together.

## Architecture

```
┌────────────────────────────────┐
│   React Frontend               │
│   localhost:3000               │
├────────────────────────────────┤
│  - Dashboard                   │
│  - Sidebar (ticker selection)  │
│  - ProgressStream              │
│  - RankingTable                │
│  - MetricsCards                │
│  - AssetAnalysis               │
└────────────┬───────────────────┘
             ↓ HTTP (Fetch/Axios)
┌────────────────────────────────┐
│   FastAPI Backend              │
│   localhost:8000               │
├────────────────────────────────┤
│  POST   /api/analyze           │
│  GET    /api/progress/{job_id} │
│  GET    /api/result/{job_id}   │
│  GET    /api/health            │
└────────────┬───────────────────┘
             ↓ Python
┌────────────────────────────────┐
│   IntelligencePipeline         │
│  - Data Loading                │
│  - Metrics Computation         │
│  - AI Commentary               │
│  - Backtesting                 │
└────────────────────────────────┘
```

## Prerequisites

✅ Python 3.10+  
✅ Node.js 16+  
✅ npm or yarn  
✅ FastAPI + dependencies installed  

Check:
```bash
python --version    # 3.10+
node --version      # 16+
npm --version       # 8+
```

## Terminal Setup (3 windows recommended)

Open 3 terminals in the EquityMind directory:

```bash
cd /path/to/EquityMind
```

---

## ✅ Terminal 1: Start FastAPI Server

```bash
python run_api_server.py
```

Expected output:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

Or with uvicorn directly:
```bash
uvicorn src.equitymind.api.server:app --reload --host 0.0.0.0 --port 8000
```

**✓ API is ready when you see "Application startup complete"**

---

## ✅ Terminal 2: Start React Dev Server

```bash
cd frontend
npm install        # First time only
npm run dev
```

Expected output:
```
VITE v... ready in ... ms

➜  Local:   http://localhost:3000/
➜  press h to show help
```

**✓ Frontend is ready when you see "Local: http://localhost:3000/"**

---

## ✅ Terminal 3: Optional - Run Tests (while both servers running)

### Test API Server

```bash
python test_api.py
```

This will:
1. Check health endpoint
2. Submit a test analysis job
3. Poll progress every 2 seconds
4. Display results

Expected output:
```
🔍 Health check...
  Status: 200
  Response: {'status': 'ok', ...}

📊 Submitting analysis...
  Status: 200
  Response: {'job_id': 'uuid', ...}

✓ Job submitted: a1b2c3d4-...

⏳ Polling progress...
  [████░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 20% — Calculating metrics...
  [████████░░░░░░░░░░░░░░░░░░░░░░░░] 40% — ...
  ...
  [████████████████████████████████] 100% — Complete!

✅ Analysis complete!
```

---

## 🌐 Open in Browser

Once both servers are running, open:

**http://localhost:3000**

You should see:
- EquityMind dashboard
- Sidebar with ticker input
- "Ready to analyze?" message

### First Analysis

1. **Select tickers**: Enter "SBER, GAZP" (or use your own)
2. **Choose period**: "1 year" (default)
3. **Select source**: "Мосбиржа" (for MOEX tickers)
4. **Click Analyze**
5. **Watch progress**: Real-time progress bar updates
6. **View results**: Ranking table and detailed metrics

**Typical time**: 30-120 seconds depending on tickers

---

## Troubleshooting

### "Cannot connect to API"

**Problem**: Frontend shows "API Connection Error"

**Solution**:
1. Check Terminal 1 (FastAPI) is running
2. Verify output shows "Application startup complete"
3. Try health check:
   ```bash
   curl http://localhost:8000/api/health
   ```
4. Check no other app is using port 8000:
   ```bash
   # On Windows
   netstat -ano | findstr :8000
   # On Mac/Linux
   lsof -i :8000
   ```

### "Port 8000/3000 already in use"

```bash
# Kill process on port 8000
# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Mac/Linux
lsof -i :8000 | grep LISTEN
kill -9 <PID>

# Or use different port
uvicorn src.equitymind.api.server:app --port 8001
# Then set VITE_API_URL=http://localhost:8001 in frontend
```

### "Ticker not found"

Check:
1. Ticker symbol is correct (e.g., SBER not SBER.RTS)
2. Source matches:
   - MOEX tickers (SBER, GAZP, LKOH) → select "Мосбиржа"
   - Yahoo tickers (AAPL, MSFT, GOOGL) → select "Yahoo"
3. Check API logs in Terminal 1 for errors

### Blank page on Frontend

1. Check browser console (`F12` → Console tab)
2. Verify both servers are running
3. Try hard refresh (`Ctrl+Shift+R` or `Cmd+Shift+R`)
4. Check `http://localhost:8000/docs` to verify API

### Analysis is slow

- First run may take longer (data download + caching)
- Monitor Terminal 1 for logs
- Check `/api/progress/{job_id}` endpoint in browser

### "CORS error"

Backend should handle CORS automatically. If you see CORS errors:

1. Make sure FastAPI is running (includes CORS middleware)
2. Check API is on http://localhost:8000 (not https)
3. Restart both servers

---

## Development Workflow

### Edit Frontend Components

```bash
# Terminal 2 (frontend already running with --reload)
# Edit src/components/Dashboard.jsx
# Changes auto-reload at localhost:3000
```

### Edit Backend API

```bash
# Terminal 1 (server running with --reload)
# Edit src/equitymind/api/server.py
# Changes auto-reload automatically
```

### Add New Feature

Example: Add more metrics to AssetAnalysis

1. Backend (`src/equitymind/api/models.py`):
   ```python
   # Add field to AnalysisResultResponse
   ```

2. Frontend (`src/components/AssetAnalysis.jsx`):
   ```jsx
   // Display new field from result.assets[ticker]
   ```

3. Both servers auto-reload on save

---

## Production Deployment

### Deploy Backend

Option 1: Railway.app
```bash
# Create Railway project
railway init
railway up
```

Option 2: AWS Lambda / Google Cloud Functions
```bash
# Use serverless framework
serverless deploy
```

### Deploy Frontend

Option 1: Vercel (Recommended)
```bash
cd frontend
npm install -g vercel
vercel
```

Option 2: GitHub Pages
```bash
cd frontend
npm run build
# Deploy dist/ folder
```

Option 3: Docker
```bash
docker build -t equitymind-frontend .
docker run -p 3000:3000 equitymind-frontend
```

---

## Docker Compose (Single Command)

Create `docker-compose.yml`:

```yaml
version: '3'
services:
  backend:
    build: .
    ports:
      - "8000:8000"
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    depends_on:
      - backend
```

Run:
```bash
docker-compose up
```

Open `http://localhost:3000`

---

## Performance Tips

1. **Caching**: Backend caches price data locally (`.equitymind_cache/`)
2. **Polling interval**: Frontend polls every 1 second (configurable in `useAnalysis.js`)
3. **Lazy loading**: Results load only when needed
4. **Local storage**: Frontend caches ticker selection and period

---

## Environment Variables

### Backend (`.env` in EquityMind root)
```bash
ANTHROPIC_API_KEY=sk-ant-...     # For AI commentary
EQUITYMIND_DATA_SOURCE=moex      # Default: yfinance
EQUITYMIND_CONFIG=config.yaml
```

### Frontend (`frontend/.env.local`)
```bash
VITE_API_URL=http://localhost:8000
```

---

## Next Steps

1. ✅ Both servers running
2. Try analyzing a few assets
3. Check `http://localhost:8000/docs` for API details
4. Explore browser DevTools → Network tab to see API calls
5. Customize colors/styling in `frontend/src/index.css`
6. Deploy when ready!

---

## Stopping the Application

### Clean shutdown:

**Terminal 1 (Backend)**:
```bash
# Press Ctrl+C
```

**Terminal 2 (Frontend)**:
```bash
# Press Ctrl+C
```

### Kill ports if stuck:

```bash
# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Mac/Linux
lsof -i :8000 | grep LISTEN
kill -9 <PID>
```

---

## Support

For issues:

1. Check logs in both terminals
2. Try `npm install` (frontend) or `uv sync` (backend)
3. Check API docs: `http://localhost:8000/docs`
4. Read `docs/API.md` and `frontend/README.md`

Enjoy EquityMind! 🚀📈
