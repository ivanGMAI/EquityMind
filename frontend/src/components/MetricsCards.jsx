import { TrendingUp, TrendingDown, BarChart3, AlertCircle } from 'lucide-react'

export function MetricsCards({ assets }) {
  if (!assets || Object.keys(assets).length === 0) return null

  const tickers = Object.keys(assets)

  // Средняя (не суммарная!) накопленная доходность по активам
  const avgReturn =
    tickers.reduce((sum, ticker) => {
      const asset = assets[ticker]
      return sum + (asset.metrics?.cumulative_return_pct || 0)
    }, 0) / tickers.length

  const avgVolatility =
    tickers.reduce((sum, ticker) => {
      const asset = assets[ticker]
      return sum + (asset.metrics?.volatility?.annualized_pct || 0)
    }, 0) / tickers.length

  const avgSharpe =
    tickers.reduce((sum, ticker) => {
      const asset = assets[ticker]
      const perf = asset.metrics?.performance || {}
      return sum + (perf.sharpe || 0)
    }, 0) / tickers.length

  const maxDrawdown = Math.min(
    ...tickers.map(
      (ticker) => assets[ticker].metrics?.risk?.max_drawdown_pct || 0
    )
  )

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {/* Средняя доходность */}
      <div className="metric-card">
        <div className="flex items-center justify-between mb-4">
          <div>
            <p className="card-text">Средняя доходность</p>
            <p className="text-3xl font-bold mt-2 num">
              {avgReturn >= 0 ? '+' : ''}{avgReturn.toFixed(2)}%
            </p>
          </div>
          {avgReturn >= 0 ? (
            <TrendingUp className="w-12 h-12 text-sber-500 opacity-50" />
          ) : (
            <TrendingDown className="w-12 h-12 text-red-500 opacity-50" />
          )}
        </div>
        <p
          className={`text-sm font-medium ${
            avgReturn >= 0 ? 'text-sber-600' : 'text-red-600'
          }`}
        >
          накопленная, в среднем по {tickers.length} актив(ам)
        </p>
      </div>

      {/* Средняя волатильность */}
      <div className="metric-card">
        <div className="flex items-center justify-between mb-4">
          <div>
            <p className="card-text">Средняя волатильность</p>
            <p className="text-3xl font-bold mt-2 num">
              {avgVolatility.toFixed(1)}%
            </p>
          </div>
          <BarChart3 className="w-12 h-12 text-sber-500 opacity-50" />
        </div>
        <p className="text-sm text-gray-600">
          {avgVolatility > 30
            ? 'Высокая — цены сильно колеблются'
            : avgVolatility > 15
              ? 'Умеренная'
              : 'Низкая — спокойные бумаги'}
        </p>
      </div>

      {/* Средний Шарп */}
      <div className="metric-card">
        <div className="flex items-center justify-between mb-4">
          <div>
            <p className="card-text">Средний коэф. Шарпа</p>
            <p className="text-3xl font-bold mt-2 num">
              {avgSharpe.toFixed(2)}
            </p>
          </div>
          <div className="w-12 h-12 rounded-xl bg-sber-100 flex items-center justify-center text-sber-600 font-bold opacity-70">
            λ
          </div>
        </div>
        <p className="text-sm text-gray-600">
          Доходность на единицу риска:{' '}
          {avgSharpe > 1 ? 'хорошо' : avgSharpe > 0 ? 'положительно' : 'отрицательно'}
        </p>
      </div>

      {/* Максимальная просадка */}
      <div className="metric-card border-l-warning">
        <div className="flex items-center justify-between mb-4">
          <div>
            <p className="card-text">Макс. просадка</p>
            <p className="text-3xl font-bold mt-2 text-red-600 num">
              {maxDrawdown.toFixed(2)}%
            </p>
          </div>
          <AlertCircle className="w-12 h-12 text-amber-500 opacity-50" />
        </div>
        <p className="text-sm text-gray-600">Худшее падение от пика до дна</p>
      </div>
    </div>
  )
}
