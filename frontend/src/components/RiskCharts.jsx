import { useMemo } from 'react'
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ReferenceLine,
  Cell,
} from 'recharts'

const MONTHS = ['янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек']

function fmtDate(iso) {
  const [, m, d] = iso.split('-')
  return `${parseInt(d, 10)} ${MONTHS[parseInt(m, 10) - 1]}`
}

/** Дневные доходности в процентах из ценового ряда. */
function dailyReturns(history) {
  const out = []
  for (let i = 1; i < history.length; i++) {
    const prev = history[i - 1].close
    const cur = history[i].close
    if (prev && cur) out.push({ date: history[i].date, ret: (cur / prev - 1) * 100 })
  }
  return out
}

function std(values) {
  if (values.length < 2) return null
  const mean = values.reduce((s, v) => s + v, 0) / values.length
  const varSum = values.reduce((s, v) => s + (v - mean) ** 2, 0) / (values.length - 1)
  return { mean, sd: Math.sqrt(varSum) }
}

function SimpleTooltip({ active, payload, label, suffix = '%', digits = 2 }) {
  if (!active || !payload || !payload.length) return null
  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-md px-3 py-2 text-sm num">
      {label && <p className="font-semibold text-gray-900">{fmtDate(label)}</p>}
      {payload.map((p) => (
        <p key={p.dataKey} className="text-gray-700">
          {p.name}: <strong>{p.value?.toFixed(digits)}{suffix}</strong>
        </p>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------- underwater
function DrawdownChart({ history }) {
  const data = useMemo(() => {
    let peak = -Infinity
    return history.map((p) => {
      peak = Math.max(peak, p.close)
      return { date: p.date, dd: (p.close / peak - 1) * 100 }
    })
  }, [history])

  const worst = Math.min(...data.map((d) => d.dd))

  return (
    <div className="card">
      <h3 className="card-title">Просадки (underwater)</h3>
      <p className="card-text mb-3">
        Насколько цена ниже своего исторического максимума. Худшая точка:{' '}
        <strong className="text-red-600 num">{worst.toFixed(1)}%</strong>
      </p>
      <div className="h-52">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 4 }}>
            <CartesianGrid stroke="#E5E7EB" strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="date"
              tickFormatter={fmtDate}
              tick={{ fontSize: 11, fill: '#6B7280' }}
              tickLine={false}
              minTickGap={56}
            />
            <YAxis
              tick={{ fontSize: 11, fill: '#6B7280' }}
              tickLine={false}
              axisLine={false}
              width={44}
              tickFormatter={(v) => `${v.toFixed(0)}%`}
            />
            <Tooltip content={<SimpleTooltip />} cursor={{ stroke: '#9CA3AF', strokeDasharray: '4 4' }} />
            <ReferenceLine y={0} stroke="#6B7280" />
            <Area
              type="monotone"
              dataKey="dd"
              name="Просадка"
              stroke="#E64646"
              strokeWidth={1.5}
              fill="#E64646"
              fillOpacity={0.18}
              dot={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------- histogram
function ReturnsHistogram({ history, varPct, confidence }) {
  const { bins, skewLabel } = useMemo(() => {
    const rets = dailyReturns(history).map((r) => r.ret)
    if (rets.length < 10) return { bins: [], skewLabel: null }
    const min = Math.min(...rets)
    const max = Math.max(...rets)
    const n = 31
    const width = (max - min) / n || 1
    const counts = new Array(n).fill(0)
    rets.forEach((r) => {
      const idx = Math.min(n - 1, Math.floor((r - min) / width))
      counts[idx] += 1
    })
    const s = std(rets)
    const skew =
      s && s.sd > 0
        ? rets.reduce((acc, r) => acc + ((r - s.mean) / s.sd) ** 3, 0) / rets.length
        : 0
    return {
      bins: counts.map((c, i) => ({
        mid: min + (i + 0.5) * width,
        count: c,
      })),
      skewLabel: skew.toFixed(2),
    }
  }, [history])

  if (!bins.length) return null
  const varValue = varPct != null ? -Math.abs(varPct) : null

  return (
    <div className="card">
      <h3 className="card-title">Распределение дневных доходностей</h3>
      <p className="card-text mb-3">
        {varValue != null && (
          <>
            Левее янтарной линии — худшие {100 - (confidence || 95)}% дней (VaR{' '}
            {confidence || 95}% = <strong className="num">{varValue.toFixed(2)}%</strong>).{' '}
          </>
        )}
        Асимметрия: <span className="num">{skewLabel}</span>
      </p>
      <div className="h-52">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={bins} margin={{ top: 4, right: 8, bottom: 0, left: 4 }} barCategoryGap={1}>
            <CartesianGrid stroke="#E5E7EB" strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="mid"
              type="number"
              domain={['dataMin', 'dataMax']}
              tick={{ fontSize: 11, fill: '#6B7280' }}
              tickLine={false}
              tickFormatter={(v) => `${v.toFixed(1)}%`}
            />
            <YAxis
              tick={{ fontSize: 11, fill: '#6B7280' }}
              tickLine={false}
              axisLine={false}
              width={32}
              allowDecimals={false}
            />
            <Tooltip
              formatter={(value) => [value, 'дней']}
              labelFormatter={(v) => `около ${Number(v).toFixed(2)}%`}
              cursor={{ fill: 'rgba(0,0,0,0.04)' }}
            />
            {varValue != null && (
              <ReferenceLine
                x={varValue}
                stroke="#D97706"
                strokeWidth={2}
                strokeDasharray="4 4"
                label={{ value: 'VaR', fontSize: 11, fill: '#D97706', position: 'top' }}
              />
            )}
            <Bar dataKey="count" name="Дней" radius={[3, 3, 0, 0]}>
              {bins.map((b, i) => (
                <Cell key={i} fill={b.mid < 0 ? '#E64646' : '#21A038'} fillOpacity={0.65} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------- rolling
function RollingChart({ history }) {
  const data = useMemo(() => {
    const rets = dailyReturns(history)
    const out = []
    const VOL_W = 21
    const SHARPE_W = 63
    for (let i = 0; i < rets.length; i++) {
      const point = { date: rets[i].date, vol: null, sharpe: null }
      if (i >= VOL_W - 1) {
        const win = rets.slice(i - VOL_W + 1, i + 1).map((r) => r.ret)
        const s = std(win)
        if (s) point.vol = (s.sd / 100) * Math.sqrt(252) * 100
      }
      if (i >= SHARPE_W - 1) {
        const win = rets.slice(i - SHARPE_W + 1, i + 1).map((r) => r.ret)
        const s = std(win)
        if (s && s.sd > 0) point.sharpe = (s.mean / s.sd) * Math.sqrt(252)
      }
      out.push(point)
    }
    return out
  }, [history])

  if (data.length < 30) return null

  return (
    <div className="card">
      <h3 className="card-title">Метрики во времени</h3>
      <p className="card-text mb-3">
        Волатильность (окно 21 день) и Шарп (окно 63 дня) не постоянны — важно
        видеть, как они менялись
      </p>
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-2">
        <div className="h-44">
          <p className="text-xs font-semibold text-gray-700 mb-1">Волатильность, % годовых</p>
          <ResponsiveContainer width="100%" height="90%">
            <LineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 4 }}>
              <CartesianGrid stroke="#E5E7EB" strokeDasharray="3 3" vertical={false} />
              <XAxis
                dataKey="date"
                tickFormatter={fmtDate}
                tick={{ fontSize: 10, fill: '#6B7280' }}
                tickLine={false}
                minTickGap={56}
              />
              <YAxis tick={{ fontSize: 10, fill: '#6B7280' }} tickLine={false} axisLine={false} width={36} />
              <Tooltip content={<SimpleTooltip suffix="%" digits={1} />} />
              <Line type="monotone" dataKey="vol" name="Вола" stroke="#D97706" strokeWidth={1.8} dot={false} connectNulls />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <div className="h-44">
          <p className="text-xs font-semibold text-gray-700 mb-1">Скользящий Шарп</p>
          <ResponsiveContainer width="100%" height="90%">
            <LineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 4 }}>
              <CartesianGrid stroke="#E5E7EB" strokeDasharray="3 3" vertical={false} />
              <XAxis
                dataKey="date"
                tickFormatter={fmtDate}
                tick={{ fontSize: 10, fill: '#6B7280' }}
                tickLine={false}
                minTickGap={56}
              />
              <YAxis tick={{ fontSize: 10, fill: '#6B7280' }} tickLine={false} axisLine={false} width={36} />
              <Tooltip content={<SimpleTooltip suffix="" digits={2} />} />
              <ReferenceLine y={0} stroke="#9CA3AF" strokeDasharray="4 4" />
              <Line type="monotone" dataKey="sharpe" name="Шарп" stroke="#8B5CF6" strokeWidth={1.8} dot={false} connectNulls />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}

/** Блок риск-графиков для карточки актива. */
export function RiskCharts({ history, tail }) {
  if (!history || history.length < 30) return null
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <DrawdownChart history={history} />
        <ReturnsHistogram
          history={history}
          varPct={tail?.historical_var_pct}
          confidence={tail?.confidence_pct}
        />
      </div>
      <RollingChart history={history} />
    </div>
  )
}
