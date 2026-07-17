import {
  ResponsiveContainer,
  ComposedChart,
  Scatter,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
  LabelList,
} from 'recharts'

// Цвета аллокаций — фиксированный порядок из проверенной палитры.
const ALLOC_META = {
  equal_weight: { label: 'Равные веса', color: '#2563EB' },
  min_variance: { label: 'Мин. дисперсия', color: '#D97706' },
  max_sharpe: { label: 'Макс. Шарп', color: '#21A038' },
  risk_parity: { label: 'Паритет риска', color: '#8B5CF6' },
}

/** Дивергентная окраска корреляции: янтарный (−1) ↔ нейтральный (0) ↔ зелёный (+1). */
function corrBg(v) {
  if (v == null) return 'transparent'
  const a = Math.min(Math.abs(v), 1) * 0.75
  return v >= 0 ? `rgba(33, 160, 56, ${a})` : `rgba(217, 119, 6, ${a})`
}

function FrontierTooltip({ active, payload }) {
  if (!active || !payload || !payload.length) return null
  const p = payload[0].payload
  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-md px-4 py-3 text-sm">
      <p className="font-semibold text-gray-900 mb-1">{p.name || 'Граница'}</p>
      <p className="text-gray-700 num">Волатильность: {p.volatility_pct?.toFixed(1)}%</p>
      <p className="text-gray-700 num">Доходность: {p.return_pct?.toFixed(1)}%</p>
      {p.sharpe != null && <p className="text-gray-700 num">Шарп: {p.sharpe.toFixed(2)}</p>}
    </div>
  )
}

export function PortfolioSection({ portfolio, assets }) {
  if (!portfolio || !portfolio.allocations) return null

  const tickers = portfolio.tickers || []
  const frontier = portfolio.frontier || []

  // Точки отдельных бумаг: годовая доходность × волатильность из метрик.
  const assetPoints = Object.entries(assets || {})
    .map(([ticker, a]) => {
      const perf = a.metrics?.performance || {}
      const vol = a.metrics?.volatility?.annualized_pct
      if (perf.annualized_return_pct == null || vol == null) return null
      return {
        name: ticker,
        volatility_pct: vol,
        return_pct: perf.annualized_return_pct,
      }
    })
    .filter(Boolean)

  const allocPoints = Object.entries(portfolio.allocations).map(([key, a]) => ({
    name: ALLOC_META[key]?.label || a.label,
    color: ALLOC_META[key]?.color || '#2563EB',
    volatility_pct: a.volatility_pct,
    return_pct: a.expected_return_pct,
    sharpe: a.sharpe,
    key,
  }))

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold mb-1">Портфельная аналитика</h2>
        <p className="text-sm text-gray-500">
          {tickers.length} бумаг · {portfolio.observations} пересекающихся наблюдений ·
          средняя парная корреляция {portfolio.average_correlation > 0 ? '+' : ''}
          {portfolio.average_correlation?.toFixed(2)} · безрисковая ставка{' '}
          {portfolio.risk_free_rate_pct}%
        </p>
      </div>

      {/* Эффективная граница */}
      {frontier.length > 0 && (
        <div className="card">
          <h3 className="card-title">Эффективная граница Марковица</h3>
          <p className="card-text mb-4">
            Каждая точка — портфель; кривая — лучшие возможные комбинации
            «риск-доходность». Наведи курсор, чтобы увидеть цифры
          </p>
          <div className="h-96">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart margin={{ top: 16, right: 24, bottom: 8, left: 8 }}>
                <CartesianGrid stroke="#E5E7EB" strokeDasharray="3 3" />
                <XAxis
                  type="number"
                  dataKey="volatility_pct"
                  name="Волатильность"
                  domain={['auto', 'auto']}
                  tick={{ fontSize: 12, fill: '#6B7280' }}
                  tickLine={false}
                  label={{
                    value: 'Годовая волатильность, %',
                    position: 'insideBottom',
                    offset: -4,
                    fontSize: 12,
                    fill: '#6B7280',
                  }}
                />
                <YAxis
                  type="number"
                  dataKey="return_pct"
                  name="Доходность"
                  domain={['auto', 'auto']}
                  tick={{ fontSize: 12, fill: '#6B7280' }}
                  tickLine={false}
                  axisLine={false}
                  width={56}
                  label={{
                    value: 'Годовая доходность, %',
                    angle: -90,
                    position: 'insideLeft',
                    fontSize: 12,
                    fill: '#6B7280',
                  }}
                />
                <Tooltip content={<FrontierTooltip />} />
                <Legend
                  formatter={(value) => (
                    <span className="text-sm text-gray-700">{value}</span>
                  )}
                />
                <Scatter
                  name="Эффективная граница"
                  data={frontier}
                  fill="#94A3B8"
                  line={{ stroke: '#94A3B8', strokeWidth: 2 }}
                  shape={() => null}
                />
                <Scatter name="Бумаги" data={assetPoints} fill="#334155">
                  <LabelList dataKey="name" position="top" style={{ fontSize: 11, fill: '#334155' }} />
                </Scatter>
                {allocPoints.map((p) => (
                  <Scatter key={p.key} name={p.name} data={[p]} fill={p.color} />
                ))}
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Матрица корреляций */}
        <div className="card">
          <h3 className="card-title">Матрица корреляций</h3>
          <p className="card-text mb-4">
            Зелёное — бумаги ходят вместе, янтарное — в противофазе (диверсификация)
          </p>
          <div className="overflow-x-auto">
            <table className="text-sm num">
              <thead>
                <tr>
                  <th className="p-2" />
                  {tickers.map((t) => (
                    <th key={t} className="p-2 font-semibold text-gray-700 text-center">
                      {t}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {tickers.map((row) => (
                  <tr key={row}>
                    <th className="p-2 font-semibold text-gray-700 text-left">{row}</th>
                    {tickers.map((col) => {
                      const v = portfolio.correlation?.[row]?.[col]
                      return (
                        <td
                          key={col}
                          className="p-2 text-center rounded"
                          style={{ background: corrBg(v) }}
                        >
                          {v != null ? (v > 0 ? '+' : '') + v.toFixed(2) : '—'}
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Эталонные аллокации */}
        <div className="card">
          <h3 className="card-title">Эталонные аллокации</h3>
          <p className="card-text mb-4">
            Четыре способа разложить капитал по этим бумагам — и что каждый даёт
          </p>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 text-gray-700">
                <th className="py-2 text-left font-semibold">Аллокация</th>
                <th className="py-2 text-right font-semibold">Доходн., %</th>
                <th className="py-2 text-right font-semibold">Волат., %</th>
                <th className="py-2 text-right font-semibold">Шарп</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(portfolio.allocations).map(([key, a]) => (
                <tr key={key} className="border-b border-gray-100 align-top">
                  <td className="py-2 pr-2">
                    <span className="flex items-center gap-2 font-medium text-gray-900">
                      <span
                        className="inline-block w-2.5 h-2.5 rounded-full flex-shrink-0"
                        style={{ background: ALLOC_META[key]?.color || '#2563EB' }}
                      />
                      {ALLOC_META[key]?.label || a.label}
                    </span>
                    <span className="block text-xs text-gray-500 mt-1 num">
                      {Object.entries(a.weights || {})
                        .map(([t, w]) => `${t} ${w > 0 ? '' : ''}${w}%`)
                        .join(' · ')}
                    </span>
                  </td>
                  <td className="py-2 text-right num">{a.expected_return_pct ?? '—'}</td>
                  <td className="py-2 text-right num">{a.volatility_pct ?? '—'}</td>
                  <td className="py-2 text-right num">{a.sharpe ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-xs text-gray-400 mt-3">
            Мин. дисперсия и макс. Шарп — без ограничений (возможны отрицательные
            веса, т.е. короткие позиции). Ожидаемые доходности — исторические
            средние, не прогноз.
          </p>
        </div>
      </div>
    </div>
  )
}
