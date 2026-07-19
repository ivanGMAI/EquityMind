import { useEffect, useMemo, useState } from 'react'
import { ChevronLeft } from 'lucide-react'
import { analyzeApi } from '../api/client'

export function Sidebar({
  tickers,
  onTickersChange,
  onAnalyze,
  disabled,
  period,
  onPeriodChange,
  source,
  onSourceChange,
  open = false,
  onClose,
}) {
  const [catalog, setCatalog] = useState([])
  const [query, setQuery] = useState('')

  // Каталог бумаг: Мосбиржа — живой список с ISS (~500 бумаг), Yahoo — подборка.
  useEffect(() => {
    let alive = true
    analyzeApi
      .getTickers(source)
      .then((res) => {
        if (alive) setCatalog(res.data.tickers || [])
      })
      .catch(() => {
        if (alive) setCatalog([])
      })
    return () => {
      alive = false
    }
  }, [source])

  const matches = useMemo(() => {
    const q = query.trim().toUpperCase()
    if (!q) return []
    return catalog
      .filter((e) => !tickers.includes(e.ticker))
      .filter(
        (e) =>
          e.ticker.toUpperCase().startsWith(q) ||
          e.name.toUpperCase().includes(q)
      )
      .slice(0, 8)
  }, [query, catalog, tickers])

  const addTicker = (t) => {
    onTickersChange([...tickers, t])
    setQuery('')
  }

  const removeTicker = (t) => {
    onTickersChange(tickers.filter((x) => x !== t))
  }

  const handleTickerInput = (e) => {
    const text = e.target.value
    const items = text
      .split(',')
      .map((t) => t.trim().toUpperCase())
      .filter((t) => t)
    onTickersChange(items)
  }

  return (
    <div
      className={`w-72 max-w-[85vw] bg-white dark:bg-night-card border-r border-gray-200 dark:border-night-border p-6 shadow-sm overflow-y-auto
        fixed lg:static inset-y-0 left-0 z-40 transform transition-transform duration-200 lg:translate-x-0 ${
          open ? 'translate-x-0' : '-translate-x-full'
        }`}
    >
      {/* Логотип + сворачивание (на мобиле) */}
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-full bg-gradient-to-br from-sber-500 to-teal-400" />
          <h2 className="text-2xl font-bold">EquityMind</h2>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Свернуть панель"
          className="lg:hidden p-2 rounded-xl text-gray-500 hover:bg-gray-100 dark:text-night-sub dark:hover:bg-night-hover transition-colors"
        >
          <ChevronLeft size={22} />
        </button>
      </div>

      {/* Источник данных */}
      <div className="mb-6">
        <label className="block text-sm font-semibold text-gray-700 dark:text-night-sub mb-2">
          Источник данных
        </label>
        <select
          value={source}
          onChange={(e) => onSourceChange(e.target.value)}
          disabled={disabled}
          className="w-full px-3 py-2 input-base"
        >
          <option value="moex">Мосбиржа (SBER, GAZP, LKOH)</option>
          <option value="yfinance">Yahoo (AAPL, MSFT, BTC-USD)</option>
        </select>
      </div>

      {/* Поиск по каталогу */}
      <div className="mb-2 relative">
        <label className="block text-sm font-semibold text-gray-700 dark:text-night-sub mb-2">
          Найти бумагу
        </label>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          disabled={disabled}
          placeholder={catalog.length ? `Поиск среди ${catalog.length} бумаг…` : 'Каталог недоступен'}
          className="w-full px-3 py-2 input-base"
        />
        {matches.length > 0 && (
          <ul className="absolute z-10 mt-1 w-full bg-white dark:bg-night-hover border border-gray-200 dark:border-night-border rounded-xl shadow-lg overflow-hidden">
            {matches.map((e) => (
              <li key={e.ticker}>
                <button
                  type="button"
                  onClick={() => addTicker(e.ticker)}
                  className="w-full text-left px-3 py-2 text-sm hover:bg-sber-50 dark:hover:bg-night-border flex justify-between gap-2"
                >
                  <span className="font-semibold">{e.ticker}</span>
                  <span className="text-gray-500 dark:text-night-mut truncate">{e.name}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Выбранные бумаги */}
      <div className="mb-6">
        {tickers.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-2">
            {tickers.map((t) => (
              <span
                key={t}
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-sber-100 text-sber-800 dark:bg-sber-900 dark:text-sber-200 text-xs font-semibold"
              >
                {t}
                <button
                  type="button"
                  onClick={() => removeTicker(t)}
                  disabled={disabled}
                  className="hover:text-sber-900 dark:hover:text-sber-100"
                  aria-label={`Убрать ${t}`}
                >
                  ✕
                </button>
              </span>
            ))}
          </div>
        )}
        <textarea
          value={tickers.join(', ')}
          onChange={handleTickerInput}
          disabled={disabled}
          placeholder="Или введи тикеры через запятую"
          className="w-full px-3 py-2 font-mono input-base"
          rows={2}
        />
        <p className="text-xs text-gray-500 dark:text-night-mut mt-2">
          Выбрано: {tickers.length}
          {tickers.length > 8 && ' — анализ займёт несколько минут'}
        </p>
      </div>

      {/* Период */}
      <div className="mb-8">
        <label className="block text-sm font-semibold text-gray-700 dark:text-night-sub mb-2">
          Окно истории
        </label>
        <select
          value={period}
          onChange={(e) => onPeriodChange(e.target.value)}
          disabled={disabled}
          className="w-full px-3 py-2 input-base"
        >
          <option value="1mo">1 месяц</option>
          <option value="3mo">3 месяца</option>
          <option value="6mo">6 месяцев</option>
          <option value="1y">1 год</option>
          <option value="2y">2 года</option>
          <option value="5y">5 лет</option>
          <option value="max">Максимум</option>
        </select>
      </div>

      {/* Кнопка запуска */}
      <button
        onClick={onAnalyze}
        disabled={disabled || tickers.length === 0}
        className="w-full btn btn-primary disabled:opacity-50 disabled:cursor-not-allowed mb-4"
      >
        {disabled ? 'Анализирую…' : 'Запустить анализ'}
      </button>

      {/* Подсказки */}
      <div className="text-xs text-gray-500 dark:text-night-mut space-y-2 border-t border-gray-200 dark:border-night-border pt-4 mt-8">
        <p>
          💡 <strong>Совет:</strong> начни печатать тикер или название — появятся
          подсказки из каталога
        </p>
        <p>
          ⏱️ <strong>Время:</strong> ~30 секунд на бумагу с AI-комментарием
        </p>
      </div>
    </div>
  )
}
