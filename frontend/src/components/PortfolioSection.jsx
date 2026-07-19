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
import { useChartTheme, TOOLTIP_CLASS } from '../theme'

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
    <div className={TOOLTIP_CLASS}>
      <p className="font-semibold text-gray-900 dark:text-night-text mb-1">{p.name || 'Граница'}</p>
      <p className="text-gray-700 dark:text-night-sub num">Волатильность: {p.volatility_pct?.toFixed(1)}%</p>
      <p className="text-gray-700 dark:text-night-sub num">Доходность: {p.return_pct?.toFixed(1)}%</p>
      {p.sharpe != null && <p className="text-gray-700 dark:text-night-sub num">Шарп: {p.sharpe.toFixed(2)}</p>}
    </div>
  )
}

export function PortfolioSection({ portfolio, assets }) {
  const t = useChartTheme()
  if (!portfolio || !portfolio.allocations) return null

  const tickers = portfolio.tickers || []

  // Бэкенд отдаёт обе ветви гиперболы. Эффективная (верхняя, от вершины с
  // минимальной волатильностью) рисуется сплошной линией, неэффективная
  // нижняя — пунктиром для контекста; вершина входит в обе, чтобы ветви
  // соединялись. Сортировка по риску — иначе линия зигзагом скачет.
  const rawFrontier = portfolio.frontier || []
  let frontier = []
  let lowerBranch = []
  if (rawFrontier.length) {
    const vertex = rawFrontier.reduce((a, b) =>
      b.volatility_pct < a.volatility_pct ? b : a
    )
    frontier = rawFrontier
      .filter((p) => p.return_pct >= vertex.return_pct)
      .sort((a, b) => a.volatility_pct - b.volatility_pct)
    lowerBranch = rawFrontier
      .filter((p) => p.return_pct <= vertex.return_pct)
      .sort((a, b) => a.volatility_pct - b.volatility_pct)
    if (lowerBranch.length < 2) lowerBranch = []
  }

  // Точки отдельных бумаг. Основной источник — portfolio.asset_points: те же
  // средние доходности и ковариация (то же окно наблюдений), что у портфелей
  // и границы, поэтому геометрия сходится — например, «равные веса» лежат на
  // хорде между бумагами. Фолбэк на метрики актива (CAGR по собственному окну
  // бумаги) — только для старых ответов API; он с границей не согласован.
  const assetPoints = portfolio.asset_points
    ? Object.entries(portfolio.asset_points).map(([ticker, a]) => ({
        name: ticker,
        volatility_pct: a.volatility_pct,
        return_pct: a.expected_return_pct,
        sharpe: a.sharpe,
      }))
    : Object.entries(assets || {})
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
        <p className="text-sm text-gray-500 dark:text-night-mut">
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
            Каждая точка — портфель; сплошная кривая — лучшие возможные комбинации
            «риск-доходность», пунктир — неэффективная ветвь. Доходности бумаг и
            портфелей — среднегодовые на общем окне наблюдений. Наведи курсор,
            чтобы увидеть цифры
          </p>
          <div className="h-96">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart margin={{ top: 16, right: 24, bottom: 8, left: 8 }}>
                <CartesianGrid stroke={t.grid} strokeDasharray="3 3" />
                <XAxis
                  type="number"
                  dataKey="volatility_pct"
                  name="Волатильность"
                  domain={['auto', 'auto']}
                  tick={{ fontSize: 12, fill: t.tick }}
                  tickLine={false}
                  axisLine={{ stroke: t.axisLine }}
                  label={{
                    value: 'Годовая волатильность, %',
                    position: 'insideBottom',
                    offset: -4,
                    fontSize: 12,
                    fill: t.tick,
                  }}
                />
                <YAxis
                  type="number"
                  dataKey="return_pct"
                  name="Доходность"
                  domain={['auto', 'auto']}
                  tick={{ fontSize: 12, fill: t.tick }}
                  tickLine={false}
                  axisLine={false}
                  width={56}
                  label={{
                    value: 'Годовая доходность, %',
                    angle: -90,
                    position: 'insideLeft',
                    fontSize: 12,
                    fill: t.tick,
                  }}
                />
                <Tooltip content={<FrontierTooltip />} />
                <Legend
                  formatter={(value) => (
                    <span className="text-sm text-gray-700 dark:text-night-sub">{value}</span>
                  )}
                />
                {lowerBranch.length > 0 && (
                  <Scatter
                    name="Неэффективная ветвь"
                    data={lowerBranch}
                    fill={t.refLine}
                    line={{ stroke: t.refLine, strokeWidth: 1.5, strokeDasharray: '5 4' }}
                    shape={() => null}
                    legendType="none"
                  />
                )}
                <Scatter
                  name="Эффективная граница"
                  data={frontier}
                  fill={t.refLine}
                  line={{ stroke: t.refLine, strokeWidth: 2 }}
                  shape={() => null}
                />
                <Scatter name="Бумаги" data={assetPoints} fill={t.ink}>
                  <LabelList dataKey="name" position="top" style={{ fontSize: 11, fill: t.ink }} />
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
                  {tickers.map((tk) => (
                    <th key={tk} className="p-2 font-semibold text-gray-700 dark:text-night-sub text-center">
                      {tk}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {tickers.map((row) => (
                  <tr key={row}>
                    <th className="p-2 font-semibold text-gray-700 dark:text-night-sub text-left">{row}</th>
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
              <tr className="border-b border-gray-200 dark:border-night-border text-gray-700 dark:text-night-sub">
                <th className="py-2 text-left font-semibold">Аллокация</th>
                <th className="py-2 text-right font-semibold">Доходн., %</th>
                <th className="py-2 text-right font-semibold">Волат., %</th>
                <th className="py-2 text-right font-semibold">Шарп</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(portfolio.allocations).map(([key, a]) => (
                <tr key={key} className="border-b border-gray-100 dark:border-night-border align-top">
                  <td className="py-2 pr-2">
                    <span className="flex items-center gap-2 font-medium text-gray-900 dark:text-night-text">
                      <span
                        className="inline-block w-2.5 h-2.5 rounded-full flex-shrink-0"
                        style={{ background: ALLOC_META[key]?.color || '#2563EB' }}
                      />
                      {ALLOC_META[key]?.label || a.label}
                    </span>
                    <span className="block text-xs text-gray-500 dark:text-night-mut mt-1 num">
                      {Object.entries(a.weights || {})
                        .map(([tk, w]) => `${tk} ${w}%`)
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
          <p className="text-xs text-gray-400 dark:text-night-mut mt-3">
            Мин. дисперсия и макс. Шарп — без ограничений (возможны отрицательные
            веса, т.е. короткие позиции). Ожидаемые доходности — исторические
            средние, не прогноз.
          </p>
        </div>
      </div>
    </div>
  )
}
