# EquityMind React Frontend

Modern React frontend for EquityMind, a quantitative market analytics system with AI-generated insights.

## Features

✨ **Real-time Analysis Progress** — See live updates as data loads and metrics calculate  
📊 **Interactive Asset Ranking** — Compare instruments by return, volatility, and Sharpe ratio  
💡 **Key Metrics Dashboard** — Portfolio overview with aggregate statistics  
🧠 **AI Commentary** — Machine-generated analysis of trends and risks  
📈 **Detailed Views** — Deep dive into individual assets with full metrics  
🎨 **Modern UI** — Clean, responsive design with TailwindCSS  

## Prerequisites

- **Node.js** 16+ (npm or yarn)
- **FastAPI server** running at `http://localhost:8000` (see `../QUICKSTART_API.md`)

## Quick Start

### 1. Install dependencies

```bash
cd frontend
npm install
```

### 2. Start development server

```bash
npm run dev
```

Open `http://localhost:3000` in your browser.

### 3. Make sure API server is running

In another terminal:

```bash
cd ..
python run_api_server.py
# or
uvicorn src.equitymind.api.server:app --reload
```

The frontend will try to connect to the API at `http://localhost:8000`.

## Project Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── Dashboard.jsx       # Main dashboard component
│   │   ├── Sidebar.jsx         # Ticker selection and controls
│   │   ├── ProgressStream.jsx  # Real-time progress visualization
│   │   ├── RankingTable.jsx    # Asset ranking table
│   │   ├── MetricsCards.jsx    # Key metrics display
│   │   └── AssetAnalysis.jsx   # Detailed asset analysis
│   ├── hooks/
│   │   └── useAnalysis.js      # API communication hook
│   ├── api/
│   │   └── client.js           # Axios client
│   ├── App.jsx                 # App root
│   ├── main.jsx                # React entry point
│   └── index.css               # Global styles (TailwindCSS)
├── package.json
├── vite.config.js
├── tailwind.config.js
├── postcss.config.js
└── index.html
```

## Usage

1. **Select Tickers** — Enter comma-separated ticker symbols (e.g., "SBER, GAZP, LKOH" for MOEX or "AAPL, MSFT, GOOGL" for Yahoo)
2. **Choose Period** — Select historical period (1 month to max available)
3. **Select Source** — MOEX for Russian stocks, Yahoo for international
4. **Click Analyze** — Start the analysis
5. **Watch Progress** — See real-time updates as data loads
6. **View Results** — Rankings, metrics, and detailed analysis per asset

## Key Components

### Dashboard
Main layout combining sidebar, progress, ranking table, and detailed views.

### Sidebar
- Ticker input (comma-separated)
- Data source selection (MOEX / Yahoo)
- Period selection (1mo to max)
- Analyze button
- Tips and settings

### ProgressStream
Shows real-time progress with:
- Percentage complete (0-100%)
- Current step (Data, Metrics, AI, Complete)
- Visual progress bar
- Step indicators

### RankingTable
Sortable table with:
- Rank and ticker
- Return percentage (color-coded: green/red)
- Volatility
- Sharpe ratio
- Click to view detailed analysis

### MetricsCards
4-card grid showing:
- Portfolio return (aggregate)
- Average volatility
- Average Sharpe ratio
- Max drawdown

### AssetAnalysis
Detailed view with:
- Key metrics (price, returns, volatility, ratios)
- Risk metrics (Sharpe, Sortino, VaR, drawdown, beta, alpha)
- AI commentary (summary, trend, risk analysis, key signals)
- Backtest results (SMA crossover strategy)

## API Integration

The frontend uses the `useAnalysis` hook to communicate with the FastAPI backend:

```javascript
const { submitAnalysis, progress, result, error, loading } = useAnalysis()

// Submit analysis
await submitAnalysis({
  tickers: ['SBER', 'GAZP'],
  period: '1y',
  source: 'moex',
  with_ai: true,
  with_backtest: true,
})

// Hook returns:
// - progress: {status, progress, current_step}
// - result: {assets, comparison, alerts, failures}
// - error: error message if any
// - loading: true while analysis is running
```

See `../docs/REACT_INTEGRATION.md` for detailed API documentation.

## Styling

Uses **TailwindCSS** for all styles. Key utility classes:

- `.card` — White card with border and shadow
- `.btn`, `.btn-primary`, `.btn-secondary` — Button styles
- `.metric-card` — Metric display card with left border
- `.progress-bar`, `.progress-fill` — Progress bar

Custom components in `src/index.css`.

## Environment Variables

Create `.env.local`:

```bash
VITE_API_URL=http://localhost:8000
```

## Build for Production

```bash
npm run build
# Output: dist/

npm run preview
# Preview production build locally
```

## Deployment

### Vercel (Recommended)

```bash
npm install -g vercel
vercel
```

### Docker

```dockerfile
FROM node:18-alpine AS build
WORKDIR /app
COPY . .
RUN npm ci && npm run build

FROM node:18-alpine
WORKDIR /app
RUN npm install -g serve
COPY --from=build /app/dist ./dist
CMD ["serve", "-s", "dist", "-l", "3000"]
```

### GitHub Pages

```bash
npm run build
# Deploy dist/ folder
```

## Troubleshooting

### "Cannot connect to API"

Make sure FastAPI is running:

```bash
cd ..
python run_api_server.py
```

Should see: `Uvicorn running on http://localhost:8000`

### "Ticker not found"

Check:
1. Ticker symbol is correct (e.g., SBER not SBER.RTS)
2. Data source matches (MOEX tickers need source="moex")
3. Yahoo tickers (AAPL, MSFT) need source="yfinance"

### Blank page / white screen

1. Check browser console for errors
2. Make sure API is running
3. Try refreshing the page

### Slow analysis

- First run may be slow (data download + caching)
- More tickers = longer analysis
- Check `/api/progress/{job_id}` to see current step

## Development

### Add a new component

1. Create file in `src/components/MyComponent.jsx`
2. Import in `Dashboard.jsx`
3. Use TailwindCSS classes for styling

Example:

```jsx
export function MyComponent({ data }) {
  return (
    <div className="card">
      <h3 className="card-title">My Component</h3>
      <p className="card-text">{data}</p>
    </div>
  )
}
```

### Modify API calls

Edit `src/api/client.js` or the `useAnalysis` hook in `src/hooks/useAnalysis.js`.

### Change styling

Edit `src/index.css` (component styles) or `tailwind.config.js` (theme colors).

## Performance

- Lazy loads API results
- Stores preferences in localStorage (tickers, period, source)
- Efficient re-renders with React hooks
- TailwindCSS purges unused styles on build

## Browser Support

- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

## License

Same as EquityMind project.

## Next Steps

1. ✅ React frontend ready
2. Connect to running FastAPI server
3. Test with real data
4. Deploy to production (Vercel, AWS, etc.)
5. Add WebSocket for real-time updates (optional)
6. Add charting library (Recharts, Plotly) for price history graphs
