import {
  ResponsiveContainer,
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
} from 'recharts'

// Дата "2026-07-17" -> "17 июл"
const MONTHS = ['янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек']

function formatDate(iso) {
  const [, m, d] = iso.split('-')
  return `${parseInt(d, 10)} ${MONTHS[parseInt(m, 10) - 1]}`
}

function formatDateFull(iso) {
  const [y, m, d] = iso.split('-')
  return `${parseInt(d, 10)} ${MONTHS[parseInt(m, 10) - 1]} ${y}`
}

const SERIES = [
  { key: 'close', name: 'Цена закрытия', color: '#21A038' },
  { key: 'sma20', name: 'SMA 20', color: '#D97706' },
  { key: 'sma50', name: 'SMA 50', color: '#8B5CF6' },
]

function ChartTooltip({ active, payload, label, currency }) {
  if (!active || !payload || !payload.length) return null
  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-md px-4 py-3 text-sm">
      <p className="font-semibold text-gray-900 mb-1">{formatDateFull(label)}</p>
      {payload.map((item) => (
        <p key={item.dataKey} className="text-gray-700 num flex items-center gap-2">
          <span
            className="inline-block w-2.5 h-2.5 rounded-full"
            style={{ background: item.color }}
          />
          {item.name}:{' '}
          <span className="font-semibold">
            {item.value != null ? item.value.toLocaleString('ru-RU', { maximumFractionDigits: 2 }) : '—'}
            {currency ? ` ${currency}` : ''}
          </span>
        </p>
      ))}
    </div>
  )
}

export function PriceChart({ history, ticker, currency }) {
  if (!history || history.length < 2) return null

  return (
    <div className="card">
      <h3 className="card-title">{ticker} — цена и скользящие средние</h3>
      <p className="card-text mb-4">
        Наведи курсор на график, чтобы увидеть цену в конкретный день
      </p>
      <div className="h-80">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={history} margin={{ top: 8, right: 8, bottom: 0, left: 8 }}>
            <defs>
              <linearGradient id="closeFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#21A038" stopOpacity={0.18} />
                <stop offset="100%" stopColor="#21A038" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="#E5E7EB" strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="date"
              tickFormatter={formatDate}
              tick={{ fontSize: 12, fill: '#6B7280' }}
              tickLine={false}
              axisLine={{ stroke: '#E5E7EB' }}
              minTickGap={48}
            />
            <YAxis
              domain={['auto', 'auto']}
              tick={{ fontSize: 12, fill: '#6B7280' }}
              tickLine={false}
              axisLine={false}
              width={64}
              tickFormatter={(v) => v.toLocaleString('ru-RU', { maximumFractionDigits: 0 })}
            />
            <Tooltip
              content={<ChartTooltip currency={currency} />}
              cursor={{ stroke: '#9CA3AF', strokeDasharray: '4 4' }}
            />
            <Legend
              formatter={(value) => <span className="text-sm text-gray-700">{value}</span>}
              iconType="plainline"
            />
            <Area
              type="monotone"
              dataKey="close"
              name="Цена закрытия"
              stroke="#21A038"
              strokeWidth={2}
              fill="url(#closeFill)"
              dot={false}
              activeDot={{ r: 4, strokeWidth: 2, stroke: '#fff' }}
            />
            <Line
              type="monotone"
              dataKey="sma20"
              name="SMA 20"
              stroke="#D97706"
              strokeWidth={1.5}
              dot={false}
              connectNulls
            />
            <Line
              type="monotone"
              dataKey="sma50"
              name="SMA 50"
              stroke="#8B5CF6"
              strokeWidth={1.5}
              dot={false}
              connectNulls
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <p className="text-xs text-gray-400 mt-2">
        SMA — среднее за 20/50 дней: сглаживает шум и показывает направление тренда.
      </p>
    </div>
  )
}
