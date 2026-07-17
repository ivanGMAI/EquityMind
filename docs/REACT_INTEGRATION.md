# React + FastAPI Integration Guide

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   React Frontend                             │
│  (localhost:3000)                                             │
├─────────────────────────────────────────────────────────────┤
│  - Dashboard.tsx: Main page                                  │
│  - ProgressStream.tsx: Real-time progress bar               │
│  - RankingTable.tsx: Asset ranking with sorting             │
│  - MetricsCards.tsx: Key metrics display                    │
│  - AssetAnalysis.tsx: Detailed asset view                   │
└─────────────────────────────────────────────────────────────┘
              ↓ HTTP (Fetch/Axios)
┌─────────────────────────────────────────────────────────────┐
│           FastAPI Server (EquityMind)                        │
│  (localhost:8000)                                            │
├─────────────────────────────────────────────────────────────┤
│  - POST /api/analyze: Start analysis                        │
│  - GET /api/progress/{job_id}: Get status                   │
│  - GET /api/result/{job_id}: Get results                    │
└─────────────────────────────────────────────────────────────┘
              ↓ Python
┌─────────────────────────────────────────────────────────────┐
│        IntelligencePipeline (Existing)                       │
│  - Load data (MOEX/Yahoo)                                    │
│  - Calculate metrics                                         │
│  - Generate AI commentary                                    │
│  - Run backtest                                              │
└─────────────────────────────────────────────────────────────┘
```

## API Client Hook (React)

Create `src/hooks/useAnalysis.ts`:

```typescript
import { useState, useCallback } from 'react';

export interface AnalysisParams {
  tickers: string[];
  period: string;
  interval: string;
  return_basis: string;
  with_ai: boolean;
  with_backtest: boolean;
  source: string;
}

export interface Progress {
  job_id: string;
  status: 'queued' | 'running' | 'done' | 'failed';
  progress: number; // 0.0 - 1.0
  current_step: string;
  error?: string;
}

export interface AnalysisResult {
  generated_at: string;
  ai_provider: string;
  ai_model: string;
  assets: Record<string, any>;
  comparison: ComparisonEntry[];
  alerts: Alert[];
  failures: Record<string, string>;
}

export interface ComparisonEntry {
  ticker: string;
  return_pct: number;
  volatility_pct: number;
  sharpe?: number;
  rank: number;
}

export interface Alert {
  severity: 'warning' | 'critical';
  message: string;
}

export function useAnalysis() {
  const [jobId, setJobId] = useState<string | null>(null);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const submitAnalysis = useCallback(
    async (params: AnalysisParams) => {
      setLoading(true);
      setError(null);
      setJobId(null);
      setProgress(null);
      setResult(null);

      try {
        const response = await fetch('http://localhost:8000/api/analyze', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(params),
        });

        if (!response.ok) throw new Error(`API error: ${response.status}`);
        const data = await response.json();
        setJobId(data.job_id);

        // Start polling progress
        pollProgress(data.job_id);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
        setLoading(false);
      }
    },
    []
  );

  const pollProgress = useCallback(async (id: string) => {
    const pollInterval = setInterval(async () => {
      try {
        const response = await fetch(`http://localhost:8000/api/progress/${id}`);
        if (!response.ok) throw new Error(`Progress API error: ${response.status}`);
        const data = await response.json();
        setProgress(data);

        if (data.status === 'done' || data.status === 'failed') {
          clearInterval(pollInterval);
          if (data.status === 'done') {
            fetchResult(id);
          } else {
            setError(data.error || 'Analysis failed');
          }
          setLoading(false);
        }
      } catch (err) {
        clearInterval(pollInterval);
        setError(err instanceof Error ? err.message : 'Poll error');
        setLoading(false);
      }
    }, 1000); // Poll every second
  }, []);

  const fetchResult = useCallback(async (id: string) => {
    try {
      const response = await fetch(`http://localhost:8000/api/result/${id}`);
      if (!response.ok) throw new Error(`Result API error: ${response.status}`);
      const data = await response.json();
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch result');
    }
  }, []);

  return {
    submitAnalysis,
    jobId,
    progress,
    result,
    error,
    loading,
  };
}
```

## Dashboard Component

Create `src/components/Dashboard.tsx`:

```typescript
import { useState } from 'react';
import { useAnalysis } from '../hooks/useAnalysis';
import { Sidebar } from './Sidebar';
import { ProgressStream } from './ProgressStream';
import { RankingTable } from './RankingTable';
import { MetricsCards } from './MetricsCards';
import { AssetAnalysis } from './AssetAnalysis';

export function Dashboard() {
  const {
    submitAnalysis,
    jobId,
    progress,
    result,
    error,
    loading,
  } = useAnalysis();

  const [tickers, setTickers] = useState<string[]>(['SBER', 'GAZP']);
  const [selectedAsset, setSelectedAsset] = useState<string | null>(null);

  const handleAnalyze = async () => {
    await submitAnalysis({
      tickers,
      period: '1y',
      interval: '1d',
      return_basis: 'cumulative',
      with_ai: true,
      with_backtest: true,
      source: 'moex',
    });
  };

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <Sidebar
        tickers={tickers}
        onTickersChange={setTickers}
        onAnalyze={handleAnalyze}
        disabled={loading}
      />

      {/* Main content */}
      <div className="flex-1 overflow-auto p-6">
        <div className="max-w-7xl mx-auto">
          <h1 className="text-4xl font-bold mb-2">EquityMind</h1>
          <p className="text-gray-600 mb-6">Quantitative market analytics with AI insights</p>

          {error && (
            <div className="bg-red-50 border border-red-200 p-4 rounded-lg mb-6">
              <p className="text-red-800">Error: {error}</p>
            </div>
          )}

          {/* Progress */}
          {loading && progress && (
            <ProgressStream progress={progress} />
          )}

          {/* Results */}
          {result && !loading && (
            <>
              <div className="mb-8">
                <h2 className="text-2xl font-bold mb-4">Ranking</h2>
                <RankingTable comparison={result.comparison} />
              </div>

              <div className="mb-8">
                <h2 className="text-2xl font-bold mb-4">Key Metrics</h2>
                <MetricsCards assets={result.assets} />
              </div>

              {selectedAsset && result.assets[selectedAsset] && (
                <div className="mb-8">
                  <h2 className="text-2xl font-bold mb-4">{selectedAsset} Analysis</h2>
                  <AssetAnalysis asset={result.assets[selectedAsset]} />
                </div>
              )}
            </>
          )}

          {!loading && !result && (
            <div className="text-center py-12">
              <p className="text-gray-600 text-lg">
                Select tickers and click "Analyze" to get started
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
```

## Running Together

### Terminal 1: Start FastAPI server

```bash
cd EquityMind
python run_api_server.py
# Server running at http://localhost:8000
# API docs at http://localhost:8000/docs
```

### Terminal 2: Start React dev server

```bash
cd equitymind-react
npm run dev
# React app at http://localhost:3000
```

### Terminal 3 (optional): Run tests

```bash
cd EquityMind
python test_api.py
# or
pytest tests/
```

## API Response Flow

### 1. Submit Analysis

```javascript
POST /api/analyze
→ { job_id: "uuid", status: "queued" }
```

### 2. Poll Progress (every 1-2 seconds)

```javascript
GET /api/progress/{job_id}
→ {
    status: "running",
    progress: 0.45,
    current_step: "Calculating metrics..."
  }
```

### 3. Get Result (when status === "done")

```javascript
GET /api/result/{job_id}
→ {
    assets: { SBER: {...}, GAZP: {...} },
    comparison: [{ticker, return_pct, rank}, ...],
    alerts: [...]
  }
```

## Handling Different Data Sources

The API automatically adjusts the benchmark based on the source:

- **MOEX** (`source: "moex"`) → benchmark: `IMOEX`
- **Yahoo** (`source: "yfinance"`) → benchmark: `SPY`
- **CSV** (`source: "csv"`) → no benchmark

## Environment Variables

Create `.env` files for both projects:

**EquityMind/.env:**
```
EQUITYMIND_CONFIG=config.yaml
ANTHROPIC_API_KEY=sk-ant-...
# or
OPENROUTER_API_KEY=sk-or-...
```

**equitymind-react/.env.local:**
```
VITE_API_BASE_URL=http://localhost:8000
```

## Error Handling

The React app should handle these cases:

1. **Network error** → Show "Unable to connect to API"
2. **Invalid tickers** → Show "Failed to load: UNKNOWN"
3. **API timeout** → Show "Analysis taking longer than expected"
4. **Invalid credentials** → Show "API key error"

Example:

```typescript
if (error.includes('402')) {
  // Credit card error
  showError('Credit limit reached on LLM provider');
} else if (error.includes('UNKNOWN')) {
  // Ticker error
  showError('One or more tickers not found');
} else {
  // Generic error
  showError(`Analysis failed: ${error}`);
}
```

## Next Steps

1. ✅ FastAPI REST API complete
2. Create React project
3. Implement components (Sidebar, ProgressStream, RankingTable, etc.)
4. Add TailwindCSS for styling
5. Integrate Recharts for interactive graphs
6. Deploy to production (Docker + Vercel)
