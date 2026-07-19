import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
  ReferenceLine,
} from 'recharts'
import { useChartTheme, TOOLTIP_CLASS } from '../theme'

const MONTHS = ['янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек']

function formatDate(iso) {
  const [, m, d] = iso.split('-')
  return `${parseInt(d, 10)} ${MONTHS[parseInt(m, 10) - 1]}`
}

function formatDateFull(iso) {
  const [y, m, d] = iso.split('-')
  return `${parseInt(d, 10)} ${MONTHS[parseInt(m, 10) - 1]} ${y}`
}

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload || !payload.length) return null
  // Сортируем по значению, чтобы порядок в тултипе совпадал с порядком линий на экране
  const sorted = [...payload].sort((a, b) => (b.value ?? 0) - (a.value ?? 0))
  return (
    <div className={TOOLTIP_CLASS}>
      <p className="font-semibold text-gray-900 dark:text-night-text mb-1">{formatDateFull(label)}</p>
      {sorted.map((item) => (
        <p key={item.dataKey} className="text-gray-700 dark:text-night-sub num flex items-center gap-2">
          <span
            className="inline-block w-2.5 h-2.5 rounded-full"
            style={{ background: item.color }}
          />
          {item.name}:{' '}
          <span className="font-semibold">
            {item.value != null ? item.value.toFixed(1) : '—'}
          </span>
        </p>
      ))}
    </div>
  )
}

/** Собирает ряды всех активов в одну таблицу: дата -> {тикер: индекс}.
 *  Каждый ряд приведён к 100 на первой точке — иначе бумаги с разной
 *  ценой (5 ₽ и 5000 ₽) нельзя сравнивать на одной оси. */
function buildRebasedData(assets, benchmark) {
  const byDate = {}
  const tickers = []

  const addSeries = (name, hist) => {
    if (!hist || hist.length < 2) return false
    const base = hist[0].close
    if (!base) return false
    hist.forEach((p) => {
      if (p.close == null) return
      if (!byDate[p.date]) byDate[p.date] = { date: p.date }
      byDate[p.date][name] = +((100 * p.close) / base).toFixed(2)
    })
    return true
  }

  Object.entries(assets).forEach(([ticker, asset]) => {
    if (addSeries(ticker, asset.history)) tickers.push(ticker)
  })

  let benchName = null
  if (benchmark?.ticker && !tickers.includes(benchmark.ticker)) {
    if (addSeries(benchmark.ticker, benchmark.history)) benchName = benchmark.ticker
  }

  const data = Object.values(byDate).sort((a, b) => a.date.localeCompare(b.date))
  return { data, tickers, benchName }
}

export function ComparisonChart({ assets, benchmark }) {
  const t = useChartTheme()
  const { data, tickers, benchName } = buildRebasedData(assets || {}, benchmark)
  if (tickers.length < 2) return null

  return (
    <div className="card">
      <h3 className="card-title">Относительная динамика</h3>
      <p className="card-text mb-4">
        Все бумаги приведены к 100 на старте периода: выше 100 — выросла, ниже — упала.
        {benchName && ` Серый пунктир — индекс ${benchName}: сразу видно, кто обогнал рынок`}
      </p>
      <div className="h-80">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 8 }}>
            <CartesianGrid stroke={t.grid} strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="date"
              tickFormatter={formatDate}
              tick={{ fontSize: 12, fill: t.tick }}
              tickLine={false}
              axisLine={{ stroke: t.axisLine }}
              minTickGap={48}
            />
            <YAxis
              domain={['auto', 'auto']}
              tick={{ fontSize: 12, fill: t.tick }}
              tickLine={false}
              axisLine={false}
              width={48}
            />
            <ReferenceLine y={100} stroke={t.refLine} strokeDasharray="4 4" />
            <Tooltip
              content={<ChartTooltip />}
              cursor={{ stroke: t.cursor, strokeDasharray: '4 4' }}
            />
            <Legend
              formatter={(value) => (
                <span className="text-sm text-gray-700 dark:text-night-sub">{value}</span>
              )}
              iconType="plainline"
            />
            {tickers.map((ticker, i) => (
              <Line
                key={ticker}
                type="monotone"
                dataKey={ticker}
                name={ticker}
                stroke={t.palette[i % t.palette.length]}
                strokeWidth={2}
                dot={false}
                connectNulls
                activeDot={{ r: 4, strokeWidth: 2, stroke: '#fff' }}
              />
            ))}
            {benchName && (
              <Line
                type="monotone"
                dataKey={benchName}
                name={`${benchName} (бенчмарк)`}
                stroke={t.refLine}
                strokeWidth={1.5}
                strokeDasharray="6 4"
                dot={false}
                connectNulls
              />
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
