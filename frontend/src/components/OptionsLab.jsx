import { useEffect, useMemo, useRef, useState } from 'react'
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ReferenceLine,
} from 'recharts'
import client from '../api/client'
import { useChartTheme, TOOLTIP_CLASS } from '../theme'

const STRATEGIES = [
  { value: 'long_call', label: 'Купить колл (Long call)' },
  { value: 'long_put', label: 'Купить пут (Long put)' },
  { value: 'straddle', label: 'Стрэддл (колл + пут)' },
  { value: 'covered_call', label: 'Покрытый колл' },
  { value: 'protective_put', label: 'Защитный пут' },
  { value: 'bull_call_spread', label: 'Бычий колл-спред' },
]

const GREEK_INFO = [
  { key: 'delta', label: 'Delta', hint: 'чувствительность к цене актива' },
  { key: 'gamma', label: 'Gamma', hint: 'скорость изменения дельты' },
  { key: 'vega_per_pct', label: 'Vega (на 1%)', hint: 'чувствительность к волатильности' },
  { key: 'theta_per_day', label: 'Theta (в день)', hint: 'потеря стоимости за день' },
]

function Num({ label, value, onChange, step = 1, disabled = false }) {
  return (
    <label className="block">
      <span className="block text-xs font-semibold text-gray-700 dark:text-night-sub mb-1">{label}</span>
      <input
        type="number"
        value={value}
        step={step}
        disabled={disabled}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="w-full px-2 py-1.5 num input-base rounded-lg disabled:opacity-40"
      />
    </label>
  )
}

function PayoffTooltip({ active, payload }) {
  if (!active || !payload || !payload.length) return null
  const p = payload[0].payload
  return (
    <div className={TOOLTIP_CLASS + ' num'}>
      <p className="text-gray-700 dark:text-night-sub">
        Цена на экспирации: <strong>{p.spot.toFixed(2)}</strong>
      </p>
      <p className={p.pnl >= 0 ? 'text-sber-600 dark:text-sber-400' : 'text-red-600 dark:text-red-400'}>
        P&L: <strong>{p.pnl >= 0 ? '+' : ''}{p.pnl.toFixed(2)}</strong>
      </p>
    </div>
  )
}

export function OptionsLab() {
  const t = useChartTheme()
  const [params, setParams] = useState({
    strategy: 'long_call',
    spot: 100,
    strike: 100,
    strike2: 110,
    maturity_years: 0.5,
    volatility: 0.25,
    rate: 0.08,
    dividend_yield: 0,
  })
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const timer = useRef(null)

  const set = (key) => (value) => setParams((p) => ({ ...p, [key]: value }))

  // Живой пересчёт с дебаунсом: меняешь параметр — график обновляется.
  useEffect(() => {
    const invalid = Object.values(params).some(
      (v) => typeof v === 'number' && !Number.isFinite(v)
    )
    if (invalid) return
    clearTimeout(timer.current)
    timer.current = setTimeout(async () => {
      try {
        const res = await client.post('/api/options', params)
        setData(res.data)
        setError(null)
      } catch (err) {
        setError(err.response?.data?.detail || 'Ошибка расчёта')
      }
    }, 300)
    return () => clearTimeout(timer.current)
  }, [params])

  // Градиент payoff: зелёная заливка выше нуля, красная ниже.
  const gradientOffset = useMemo(() => {
    const payoff = data?.payoff || []
    if (!payoff.length) return 0.5
    const max = Math.max(...payoff.map((p) => p.pnl))
    const min = Math.min(...payoff.map((p) => p.pnl))
    if (max <= 0) return 0
    if (min >= 0) return 1
    return max / (max - min)
  }, [data])

  const summary = data?.summary
  const isSpread = params.strategy === 'bull_call_spread'

  return (
    <div className="card">
      <h3 className="card-title">🧮 Опционная лаборатория</h3>
      <p className="card-text mb-4">
        Цена европейского опциона по Блэку–Шоулзу, греки и прибыль/убыток стратегии
        на дату экспирации. Меняй параметры — график пересчитывается сам
      </p>

      {/* Параметры */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-3 mb-6">
        <label className="block col-span-2">
          <span className="block text-xs font-semibold text-gray-700 dark:text-night-sub mb-1">Стратегия</span>
          <select
            value={params.strategy}
            onChange={(e) => set('strategy')(e.target.value)}
            className="w-full px-2 py-1.5 input-base rounded-lg"
          >
            {STRATEGIES.map((s) => (
              <option key={s.value} value={s.value}>{s.label}</option>
            ))}
          </select>
        </label>
        <Num label="Спот" value={params.spot} onChange={set('spot')} />
        <Num label="Страйк" value={params.strike} onChange={set('strike')} />
        <Num label="Верхний страйк" value={params.strike2} onChange={set('strike2')} disabled={!isSpread} />
        <Num label="Срок, лет" value={params.maturity_years} onChange={set('maturity_years')} step={0.25} />
        <Num label="Вола σ" value={params.volatility} onChange={set('volatility')} step={0.05} />
        <Num label="Ставка r" value={params.rate} onChange={set('rate')} step={0.01} />
      </div>

      {error && (
        <p className="text-sm text-red-600 dark:text-red-400 mb-4">{error}</p>
      )}

      {data && (
        <>
          {/* Сводка */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
            <div className="bg-gray-50 dark:bg-night-hover rounded-xl p-3">
              <p className="text-xs text-gray-500 dark:text-night-mut">Дебет / кредит</p>
              <p className="text-lg font-bold num">{summary.net_cost >= 0 ? '+' : ''}{summary.net_cost.toFixed(2)}</p>
            </div>
            <div className="bg-gray-50 dark:bg-night-hover rounded-xl p-3">
              <p className="text-xs text-gray-500 dark:text-night-mut">Макс. прибыль</p>
              <p className="text-lg font-bold text-sber-600 dark:text-sber-400 num">
                {summary.max_profit == null ? '∞' : `+${summary.max_profit.toFixed(2)}`}
              </p>
            </div>
            <div className="bg-gray-50 dark:bg-night-hover rounded-xl p-3">
              <p className="text-xs text-gray-500 dark:text-night-mut">Макс. убыток</p>
              <p className="text-lg font-bold text-red-600 dark:text-red-400 num">
                {summary.max_loss == null ? '−∞' : summary.max_loss.toFixed(2)}
              </p>
            </div>
            <div className="bg-gray-50 dark:bg-night-hover rounded-xl p-3">
              <p className="text-xs text-gray-500 dark:text-night-mut">Безубыток</p>
              <p className="text-lg font-bold num">
                {summary.breakevens.length ? summary.breakevens.map((b) => b.toFixed(1)).join(', ') : '—'}
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Payoff-диаграмма */}
            <div className="lg:col-span-2 h-72">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={data.payoff} margin={{ top: 8, right: 8, bottom: 0, left: 8 }}>
                  <defs>
                    <linearGradient id="pnlSplit" x1="0" y1="0" x2="0" y2="1">
                      <stop offset={gradientOffset} stopColor="#21A038" stopOpacity={0.25} />
                      <stop offset={gradientOffset} stopColor="#E64646" stopOpacity={0.25} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke={t.grid} strokeDasharray="3 3" vertical={false} />
                  <XAxis
                    dataKey="spot"
                    type="number"
                    domain={['dataMin', 'dataMax']}
                    tick={{ fontSize: 12, fill: t.tick }}
                    tickLine={false}
                    axisLine={{ stroke: t.axisLine }}
                    tickFormatter={(v) => v.toFixed(0)}
                  />
                  <YAxis
                    tick={{ fontSize: 12, fill: t.tick }}
                    tickLine={false}
                    axisLine={false}
                    width={48}
                  />
                  <Tooltip content={<PayoffTooltip />} cursor={{ stroke: t.cursor, strokeDasharray: '4 4' }} />
                  <ReferenceLine y={0} stroke={t.cursor} strokeWidth={1} />
                  <ReferenceLine
                    x={params.spot}
                    stroke={t.ink}
                    strokeDasharray="4 4"
                    label={{ value: 'спот', fontSize: 11, fill: t.ink, position: 'top' }}
                  />
                  {summary.breakevens.map((b) => (
                    <ReferenceLine key={b} x={b} stroke="#D97706" strokeDasharray="3 3" />
                  ))}
                  <Area
                    type="monotone"
                    dataKey="pnl"
                    stroke="#21A038"
                    strokeWidth={2}
                    fill="url(#pnlSplit)"
                    dot={false}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>

            {/* Греки */}
            <div>
              <p className="text-sm font-semibold text-gray-900 dark:text-night-text mb-2">Суммарные греки</p>
              <table className="w-full text-sm">
                <tbody>
                  {GREEK_INFO.map((g) => (
                    <tr key={g.key} className="border-b border-gray-100 dark:border-night-border">
                      <td className="py-1.5">
                        <span className="text-gray-900 dark:text-night-text">{g.label}</span>
                        <span className="block text-[10px] text-gray-400 dark:text-night-mut">{g.hint}</span>
                      </td>
                      <td className="py-1.5 text-right font-semibold num">
                        {data.greeks[g.key].toFixed(4)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="text-xs text-gray-400 dark:text-night-mut mt-3">
                Ноги стратегии: {data.legs.map((l) => `${l.quantity > 0 ? '+' : ''}${l.quantity} ${l.kind}${l.strike ? ' @' + l.strike : ''}`).join(', ')}
              </p>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
