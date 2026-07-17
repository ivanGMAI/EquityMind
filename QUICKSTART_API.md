# FastAPI Server — Quick Start

## Prerequisites

✅ Python 3.10+  
✅ FastAPI installed: `pip install fastapi uvicorn[standard]`  
✅ Project dependencies: `uv sync` or `pip install -r requirements.txt`

## Run the Server

### Option 1: Direct Python

```bash
cd EquityMind
python run_api_server.py
```

Server will start at `http://localhost:8000`

### Option 2: With Uvicorn directly

```bash
cd EquityMind
uvicorn src.equitymind.api.server:app --host 0.0.0.0 --port 8000 --reload
```

### Option 3: Inside virtual environment

```bash
cd EquityMind
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
python run_api_server.py
```

## Verify Server is Running

Open in browser or curl:

```bash
curl http://localhost:8000/api/health
```

Response should be:
```json
{
  "status": "ok",
  "timestamp": "2026-07-17T10:00:00.000Z"
}
```

## Interactive API Docs

Once server is running, open these in your browser:

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

You can test endpoints directly here!

## Test with Python

```bash
python test_api.py
```

This will:
1. Check health endpoint
2. Submit an analysis job
3. Poll progress every 2 seconds
4. Display results when done

Expected runtime: 30-120 seconds (depending on tickers and data)

## Environment Setup

Create `.env` file in project root:

```bash
# LLM API keys (for AI commentary)
ANTHROPIC_API_KEY=sk-ant-...
# OR
OPENROUTER_API_KEY=sk-or-...

# Data source (default: yfinance)
EQUITYMIND_DATA_SOURCE=moex  # or yfinance, csv

# Config file
EQUITYMIND_CONFIG=config.yaml
```

## Example API Calls

### 1. Submit Analysis

```bash
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "tickers": ["SBER", "GAZP", "LKOH"],
    "period": "1y",
    "interval": "1d",
    "return_basis": "cumulative",
    "with_ai": true,
    "with_backtest": true,
    "source": "moex"
  }'
```

Response:
```json
{
  "job_id": "a1b2c3d4-e5f6-47g8-h9i0-j1k2l3m4n5o6",
  "status": "queued",
  "message": "Analysis started..."
}
```

### 2. Check Progress

```bash
curl http://localhost:8000/api/progress/a1b2c3d4-e5f6-47g8-h9i0-j1k2l3m4n5o6
```

Response:
```json
{
  "job_id": "a1b2c3d4-e5f6-47g8-h9i0-j1k2l3m4n5o6",
  "status": "running",
  "progress": 0.45,
  "current_step": "Calculating metrics...",
  "error": null
}
```

### 3. Get Result

```bash
curl http://localhost:8000/api/result/a1b2c3d4-e5f6-47g8-h9i0-j1k2l3m4n5o6
```

Response: Full analysis result with assets, comparison ranking, alerts

## Troubleshooting

### "Address already in use"

```bash
# Kill process using port 8000
lsof -i :8000
kill -9 <PID>

# Or use different port
uvicorn src.equitymind.api.server:app --port 8001
```

### "No module named equitymind"

Make sure you're in the project root and installed dependencies:

```bash
cd EquityMind
pip install -e .
# or
uv sync
```

### "Failed to load ticker"

Check:
1. Ticker symbol is correct (e.g., SBER not SBER.RTS)
2. Data source matches ticker (MOEX tickers need `source: "moex"`)
3. Yahoo tickers (AAPL, MSFT) need `source: "yfinance"`

### "Analysis taking too long"

- First analysis may be slow (data download + cache)
- Check `/api/progress/{job_id}` to see current step
- Timeout is 3+ minutes depending on tickers and period

## Production Checklist

Before deploying to production:

- [ ] Add authentication (JWT tokens)
- [ ] Add rate limiting (prevent abuse)
- [ ] Use persistent storage (Redis/PostgreSQL for jobs)
- [ ] Add job cleanup (remove old jobs from memory)
- [ ] Enable HTTPS (use reverse proxy like Nginx)
- [ ] Set `allow_origins` in CORS to specific domain
- [ ] Add monitoring & logging (Sentry, CloudWatch, etc.)
- [ ] Use environment variables for secrets
- [ ] Run behind application server (Gunicorn, Waitress)

## Next Steps

1. ✅ REST API server is running
2. Create React frontend (coming next)
3. Connect React to API endpoints
4. Deploy both to cloud (AWS, GCP, Vercel, etc.)
