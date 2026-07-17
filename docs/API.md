# EquityMind REST API Documentation

## Overview

The EquityMind REST API allows you to submit analysis jobs, track their progress in real-time, and retrieve results. Jobs run asynchronously in the background, making it suitable for long-running analyses.

## Quick Start

### 1. Install dependencies

```bash
uv sync
```

### 2. Run the server

```bash
python run_api_server.py
```

The server will start at `http://localhost:8000`.

### 3. Interactive API docs

Open `http://localhost:8000/docs` in your browser for Swagger UI with interactive documentation.

## Endpoints

### Health Check

```http
GET /api/health
```

**Response:**
```json
{
  "status": "ok",
  "timestamp": "2026-07-17T10:00:00.000Z"
}
```

---

### Submit Analysis

```http
POST /api/analyze
Content-Type: application/json

{
  "tickers": ["SBER", "GAZP", "LKOH"],
  "period": "1y",
  "interval": "1d",
  "return_basis": "cumulative",
  "with_ai": true,
  "with_backtest": true,
  "source": "moex"
}
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `tickers` | `list[str]` | required | Ticker symbols (e.g., `["SBER", "GAZP"]`) |
| `period` | `str` | `"1y"` | Historical period: `1mo`, `3mo`, `6mo`, `1y`, `2y`, `5y`, `max` |
| `interval` | `str` | `"1d"` | Bar interval: `1d`, `1wk`, `1mo` |
| `return_basis` | `str` | `"cumulative"` | Ranking basis: `cumulative`, `30d`, `7d`, `1d` |
| `with_ai` | `bool` | `true` | Include AI-generated commentary |
| `with_backtest` | `bool` | `true` | Include trend backtest |
| `source` | `str` | `"yfinance"` | Data source: `moex`, `yfinance`, `csv` |

**Response (202 Accepted):**
```json
{
  "job_id": "a1b2c3d4-e5f6-47g8-h9i0-j1k2l3m4n5o6",
  "status": "queued",
  "message": "Analysis started. Use /api/progress/{job_id} to track progress."
}
```

---

### Get Progress

```http
GET /api/progress/{job_id}
```

**Response:**
```json
{
  "job_id": "a1b2c3d4-e5f6-47g8-h9i0-j1k2l3m4n5o6",
  "status": "running",
  "progress": 0.45,
  "current_step": "Считаю метрики…",
  "error": null
}
```

**Statuses:**
- `queued` — waiting to start
- `running` — currently processing
- `done` — completed successfully
- `failed` — error occurred

---

### Get Result

```http
GET /api/result/{job_id}
```

**Response (when done, 200 OK):**
```json
{
  "generated_at": "2026-07-17 10:30 UTC",
  "ai_provider": "anthropic",
  "ai_model": "claude-opus-4-8",
  "assets": {
    "SBER": {
      "ticker": "SBER",
      "metrics": {
        "last_price": 123.45,
        "returns_pct": {
          "1d": 1.2,
          "7d": 3.5,
          "30d": 5.2
        },
        "volatility": {
          "annualized_pct": 18.5
        },
        "sharpe": 0.85,
        "max_drawdown_pct": -12.3
      },
      "commentary": {
        "provider": "anthropic",
        "model": "claude-opus-4-8",
        "summary": "SBER pokazывает stabilitу...",
        "key_signals": ["..."]
      },
      "backtest": {
        "trades": 42,
        "win_rate": 0.62
      }
    }
  },
  "comparison": [
    {
      "ticker": "GAZP",
      "return_pct": 8.5,
      "volatility_pct": 22.1,
      "sharpe": 0.92,
      "rank": 1
    }
  ],
  "alerts": [],
  "failures": {}
}
```

**Response (if still running, 202 Accepted):**
```json
{
  "message": "Analysis still running",
  "progress": 0.65
}
```

**Response (if failed, 400 Bad Request):**
```json
{
  "detail": "Analysis failed: Unable to load UNKNOWN_TICKER"
}
```

---

## Usage Examples

### Python + requests

```python
import requests
import time

# Start analysis
resp = requests.post("http://localhost:8000/api/analyze", json={
    "tickers": ["AAPL", "MSFT", "GOOGL"],
    "period": "1y",
    "with_ai": True,
})
job_id = resp.json()["job_id"]
print(f"Job started: {job_id}")

# Poll progress
while True:
    progress = requests.get(f"http://localhost:8000/api/progress/{job_id}").json()
    print(f"Progress: {progress['progress']*100:.0f}% — {progress['current_step']}")
    
    if progress["status"] == "done":
        break
    if progress["status"] == "failed":
        print(f"Error: {progress['error']}")
        break
    
    time.sleep(1)

# Get results
result = requests.get(f"http://localhost:8000/api/result/{job_id}").json()
print(f"Analysis complete: {len(result['assets'])} assets analyzed")
```

### JavaScript (Fetch API)

```javascript
async function runAnalysis() {
  // Start analysis
  const submitResp = await fetch('http://localhost:8000/api/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      tickers: ['AAPL', 'MSFT', 'GOOGL'],
      period: '1y',
      with_ai: true,
    }),
  });
  const { job_id } = await submitResp.json();
  console.log('Job started:', job_id);

  // Poll progress
  let done = false;
  while (!done) {
    const progressResp = await fetch(`http://localhost:8000/api/progress/${job_id}`);
    const progress = await progressResp.json();
    console.log(`Progress: ${(progress.progress * 100).toFixed(0)}% — ${progress.current_step}`);

    if (progress.status === 'done') done = true;
    if (progress.status === 'failed') {
      console.error(`Error: ${progress.error}`);
      break;
    }

    await new Promise(r => setTimeout(r, 1000));
  }

  // Get results
  const resultResp = await fetch(`http://localhost:8000/api/result/${job_id}`);
  const result = await resultResp.json();
  console.log('Analysis complete:', Object.keys(result.assets).length, 'assets');
  return result;
}

runAnalysis().then(console.log);
```

### cURL

```bash
# Start analysis
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "tickers": ["AAPL", "MSFT"],
    "period": "1y"
  }'

# Get progress
curl http://localhost:8000/api/progress/{job_id}

# Get result
curl http://localhost:8000/api/result/{job_id}
```

---

## Admin Endpoints

### List all jobs

```http
GET /api/jobs?status=running
```

Returns all jobs, optionally filtered by status.

### Delete a job

```http
DELETE /api/jobs/{job_id}
```

Removes a job from memory.

---

## Architecture

### Job Lifecycle

```
1. POST /api/analyze
   ↓
2. Job created with status="queued"
   ↓
3. Background task starts: status="running"
   ↓
4. Pipeline runs:
   - Load data
   - Compute metrics
   - Generate AI commentary (if enabled)
   - Run backtest (if enabled)
   ↓
5. Results serialized: status="done"
   ↓
6. GET /api/result/{job_id} returns results
```

### In-Memory Job Store

Currently, jobs are stored in memory (`_jobs` dict). This means:
- Jobs are lost when the server restarts
- All progress is local to this instance
- For production, use Redis or a database

To add Redis support, modify `server.py` to use RedisJobs instead of the in-memory dict.

---

## Error Handling

### Common HTTP Status Codes

| Status | Meaning |
|--------|---------|
| `200 OK` | Job done, results ready |
| `202 Accepted` | Job still running |
| `400 Bad Request` | Job failed with error |
| `404 Not Found` | Job ID not found |
| `422 Unprocessable Entity` | Invalid request format |

### Error Response Format

```json
{
  "detail": "Unable to load ticker UNKNOWN"
}
```

---

## Environment Variables

Configure the API via `.env`:

```bash
# Settings file (optional, uses config.yaml by default)
EQUITYMIND_CONFIG=config.yaml

# LLM provider
ANTHROPIC_API_KEY=sk-ant-...
# or
OPENROUTER_API_KEY=sk-or-...

# Data source
EQUITYMIND_LLM_PROVIDER=anthropic  # or openrouter
```

---

## Performance Notes

- **Analysis time** depends on number of tickers and data period (typically 5-30 seconds per asset)
- **Memory usage** increases with job queue size (each job stores full result in memory)
- **For production**, add:
  - Job persistence (database/Redis)
  - Job cleanup (remove old jobs)
  - Rate limiting
  - Authentication (JWT tokens)
  - Async I/O for better concurrency

---

## Next Steps

1. ✅ REST API server complete
2. React frontend (consume these endpoints)
3. Real-time progress with WebSocket (instead of polling)
4. Persistent job storage (Redis/PostgreSQL)
5. Authentication and rate limiting
