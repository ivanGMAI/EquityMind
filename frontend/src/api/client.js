import axios from 'axios'

// Пустой baseURL = относительные запросы к /api/... на тот же origin.
// В dev их проксирует Vite (vite.config.js), в Docker — nginx (nginx.conf).
// VITE_API_URL нужен только если API живёт на другом хосте.
const API_BASE_URL = import.meta.env.VITE_API_URL || ''

const client = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

export const analyzeApi = {
  health: () => client.get('/api/health'),

  getTickers: (source) => client.get('/api/tickers', { params: { source } }),

  submit: (params) =>
    client.post('/api/analyze', {
      tickers: params.tickers,
      period: params.period || '1y',
      interval: params.interval || '1d',
      return_basis: params.return_basis || 'cumulative',
      with_ai: params.with_ai !== false,
      with_backtest: params.with_backtest !== false,
      source: params.source || 'yfinance',
    }),

  getProgress: (jobId) => client.get(`/api/progress/${jobId}`),

  getResult: (jobId) => client.get(`/api/result/${jobId}`),

  // Агент думает и вызывает инструменты — даём до 5 минут.
  askAgent: (jobId, question) =>
    client.post('/api/agent', { job_id: jobId, question }, { timeout: 300000 }),
}

export default client
