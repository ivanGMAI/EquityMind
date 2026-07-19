import { useState, useEffect, useRef } from 'react'
import { useAnalysis } from '../hooks/useAnalysis'
import { Sidebar } from './Sidebar'
import { ProgressStream } from './ProgressStream'
import { RankingTable } from './RankingTable'
import { MetricsCards } from './MetricsCards'
import { AssetAnalysis } from './AssetAnalysis'
import { ComparisonChart } from './ComparisonChart'
import { AgentWidget } from './AgentWidget'
import { PortfolioSection } from './PortfolioSection'
import { HomeChart } from './HomeChart'
import { ExportButtons } from './ExportButtons'
import { AlertCircle, Menu } from 'lucide-react'

// Верхний селектор таймфрейма: управляет и графиком индекса, и окном анализа.
const PERIODS = [
  { value: '1mo', label: 'Месяц' },
  { value: '3mo', label: '3 мес' },
  { value: '6mo', label: '6 мес' },
  { value: '1y', label: 'Год' },
  { value: '5y', label: '5 лет' },
  { value: 'max', label: 'Всё время' },
]

export function Dashboard() {
  const {
    submitAnalysis,
    jobId,
    progress,
    result,
    error,
    loading,
    reset,
  } = useAnalysis()

  const [tickers, setTickers] = useState(
    localStorage.getItem('equitymind_tickers')?.split(',') || ['SBER', 'GAZP']
  )
  const [period, setPeriod] = useState(
    localStorage.getItem('equitymind_period') || '1y'
  )
  const [source, setSource] = useState(
    localStorage.getItem('equitymind_source') || 'moex'
  )
  // Какие плашки «Подробный анализ» развёрнуты: { SBER: true, LKOH: false }
  const [openAssets, setOpenAssets] = useState({})
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const analysisRefs = useRef({})

  const toggleAsset = (ticker) =>
    setOpenAssets((prev) => ({ ...prev, [ticker]: !prev[ticker] }))

  // Клик по строке рейтинга: развернуть анализ тикера и прокрутить к его плашке.
  const handleSelectFromRanking = (ticker) => {
    setOpenAssets((prev) => ({ ...prev, [ticker]: true }))
    // Ждём рендер развёрнутого блока, затем скроллим к нему.
    setTimeout(() => {
      analysisRefs.current[ticker]?.scrollIntoView({
        behavior: 'smooth',
        block: 'start',
      })
    }, 100)
  }

  // После анализа сразу открываем графики топового инструмента, чтобы они были
  // видны без дополнительного клика по строке рейтинга.
  useEffect(() => {
    if (!result?.assets) return
    const tickers = Object.keys(result.assets)
    if (!tickers.length) return
    const top = result.comparison?.[0]?.ticker
    setOpenAssets({ [top && result.assets[top] ? top : tickers[0]]: true })
  }, [result])

  // Плашки анализа идут в порядке рейтинга; активы вне рейтинга — в конце.
  const orderedTickers = (() => {
    if (!result?.assets) return []
    const ranked = (result.comparison || [])
      .map((e) => e.ticker)
      .filter((t) => result.assets[t])
    const rest = Object.keys(result.assets).filter((t) => !ranked.includes(t))
    return [...ranked, ...rest]
  })()

  const handleTickersChange = (newTickers) => {
    setTickers(newTickers)
    localStorage.setItem('equitymind_tickers', newTickers.join(','))
  }

  const handlePeriodChange = (newPeriod) => {
    setPeriod(newPeriod)
    localStorage.setItem('equitymind_period', newPeriod)
  }

  const handleSourceChange = (newSource) => {
    setSource(newSource)
    localStorage.setItem('equitymind_source', newSource)
  }

  const handleAnalyze = async () => {
    if (tickers.length === 0) return
    setSidebarOpen(false)
    setOpenAssets({})
    await submitAnalysis({
      tickers,
      period,
      interval: '1d',
      return_basis: 'cumulative',
      with_ai: true,
      with_backtest: false,
      source,
    })
  }

  return (
    <div className="flex h-screen bg-[#F4F7F4] dark:bg-night-bg">
      {/* Боковая панель */}
      <Sidebar
        tickers={tickers}
        onTickersChange={handleTickersChange}
        onAnalyze={handleAnalyze}
        disabled={loading}
        period={period}
        onPeriodChange={handlePeriodChange}
        source={source}
        onSourceChange={handleSourceChange}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      {/* Затемнение под панелью (мобиле) */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/30 z-30 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Основной контент */}
      <div className="flex-1 overflow-auto">
        <div className="p-4 sm:p-8">
          <div className="max-w-7xl mx-auto">
            {/* Кнопка открытия панели (мобиле) */}
            <button
              type="button"
              onClick={() => setSidebarOpen(true)}
              className="lg:hidden mb-4 inline-flex items-center gap-2 px-3 py-2 rounded-xl bg-white dark:bg-night-card border border-gray-200 dark:border-night-border shadow-sm font-medium text-gray-700 dark:text-night-sub"
            >
              <Menu size={18} /> Параметры анализа
            </button>

            {/* Шапка + компактный статус справа */}
            <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 sm:gap-4 mb-6">
              <div>
                <h1 className="text-2xl sm:text-4xl font-bold mb-2">
                  Аналитика рынков{' '}
                  <span className="bg-gradient-to-r from-sber-500 to-teal-500 bg-clip-text text-transparent">
                    EquityMind
                  </span>
                </h1>
                <p className="text-gray-600 dark:text-night-sub">
                  Количественная аналитика с AI-комментариями — без советов и прогнозов
                </p>
              </div>
              <span className="shrink-0 mt-2 inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium bg-white dark:bg-night-card border border-gray-200 dark:border-night-border shadow-sm">
                <span
                  className={`w-2 h-2 rounded-full ${
                    loading ? 'bg-amber-500 animate-pulse' : 'bg-sber-500'
                  }`}
                />
                {loading ? 'Идёт анализ…' : result ? 'Готово' : 'Готов к анализу'}
              </span>
            </div>

            {/* Таймфрейм: график индекса и окно анализа */}
            <div className="flex flex-wrap gap-2 mb-6">
              {PERIODS.map((p) => (
                <button
                  key={p.value}
                  onClick={() => handlePeriodChange(p.value)}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                    period === p.value
                      ? 'bg-sber-500 text-white'
                      : 'bg-white dark:bg-night-card text-gray-600 dark:text-night-sub border border-gray-200 dark:border-night-border hover:bg-gray-50 dark:hover:bg-night-hover'
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>

            {/* Ошибка */}
            {error && (
              <div className="bg-red-50 border border-red-200 dark:bg-red-950/40 dark:border-red-900 rounded-xl p-4 mb-6 flex gap-3">
                <AlertCircle className="w-5 h-5 text-red-600 dark:text-red-400 flex-shrink-0 mt-0.5" />
                <div>
                  <h3 className="font-semibold text-red-900 dark:text-red-200">Ошибка</h3>
                  <p className="text-red-700 dark:text-red-300 text-sm mt-1">{error}</p>
                  <button
                    onClick={reset}
                    className="text-sm text-red-600 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300 font-medium mt-2"
                  >
                    Попробовать снова
                  </button>
                </div>
              </div>
            )}

            {/* Прогресс */}
            {loading && progress && <ProgressStream progress={progress} />}

            {/* Результаты */}
            {result && !loading && (
              <>
                {/* Оповещения */}
                {result.alerts && result.alerts.length > 0 && (
                  <div className="mb-8 space-y-3">
                    {result.alerts.map((alert, idx) => (
                      <div
                        key={idx}
                        className={`p-4 rounded-xl border ${
                          alert.severity === 'critical'
                            ? 'bg-red-50 border-red-200 dark:bg-red-950/40 dark:border-red-900'
                            : 'bg-amber-50 border-amber-200 dark:bg-amber-950/30 dark:border-amber-900'
                        }`}
                      >
                        <p
                          className={`text-sm font-medium ${
                            alert.severity === 'critical'
                              ? 'text-red-900 dark:text-red-200'
                              : 'text-amber-900 dark:text-amber-200'
                          }`}
                        >
                          ⚠️ {alert.message}
                        </p>
                      </div>
                    ))}
                  </div>
                )}

                {/* Экспорт */}
                <div className="mb-6 flex justify-end">
                  <ExportButtons jobId={jobId} />
                </div>

                {/* Карточки метрик */}
                <div className="mb-8">
                  <h2 className="text-2xl font-bold mb-4">Обзор портфеля</h2>
                  <MetricsCards assets={result.assets} />
                </div>

                {/* Сравнение динамики (при 2+ активах) */}
                <div className="mb-8">
                  <ComparisonChart
                    assets={result.assets}
                    benchmark={result.benchmark}
                  />
                </div>

                {/* Рейтинг */}
                <div className="mb-8">
                  <RankingTable
                    comparison={result.comparison}
                    onSelectAsset={handleSelectFromRanking}
                  />
                </div>

                {/* Портфельная аналитика: граница, корреляции, аллокации */}
                {result.portfolio && (
                  <div className="mb-8">
                    <PortfolioSection
                      portfolio={result.portfolio}
                      assets={result.assets}
                    />
                  </div>
                )}

                {/* Не загрузилось */}
                {result.failures && Object.keys(result.failures).length > 0 && (
                  <div className="bg-amber-50 border border-amber-200 dark:bg-amber-950/30 dark:border-amber-900 rounded-xl p-4 mb-8">
                    <p className="text-sm text-amber-900 dark:text-amber-200 font-medium">
                      Не удалось загрузить: {Object.keys(result.failures).join(', ')}.
                      Подсказка: тикеры Мосбиржи (SBER, GAZP…) требуют источник «Мосбиржа»,
                      а AAPL/BTC-USD — «Yahoo».
                    </p>
                  </div>
                )}

                {/* Подробный анализ: своя плашка на каждый инструмент */}
                {orderedTickers.length > 0 && (
                  <div className="mb-8 space-y-4">
                    {orderedTickers.map((ticker) => (
                      <div
                        key={ticker}
                        ref={(el) => (analysisRefs.current[ticker] = el)}
                        className="scroll-mt-4"
                      >
                        <button
                          onClick={() => toggleAsset(ticker)}
                          className="w-full flex items-center justify-between px-4 py-3 rounded-xl bg-white dark:bg-night-card border border-gray-200 dark:border-night-border hover:bg-gray-50 dark:hover:bg-night-hover transition-colors font-semibold text-gray-800 dark:text-night-text"
                        >
                          <span>
                            Подробный анализ — {ticker} (графики, метрики, AI)
                          </span>
                          <span className="text-gray-400 dark:text-night-mut">
                            {openAssets[ticker] ? '▲ Скрыть' : '▼ Показать'}
                          </span>
                        </button>

                        {openAssets[ticker] && (
                          <div className="mt-4">
                            <AssetAnalysis
                              ticker={ticker}
                              asset={result.assets[ticker]}
                              onClose={() => toggleAsset(ticker)}
                            />
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                {/* Дисклеймер */}
                <p className="text-xs text-gray-400 dark:text-night-mut border-t border-gray-200 dark:border-night-border pt-4 mt-4">
                  Учебная аналитика рынков — не является индивидуальной инвестиционной
                  рекомендацией. Все показатели описывают прошлое и не предсказывают
                  будущую доходность.
                </p>
              </>
            )}

            {/* Главный экран без анализа: живой график индекса Мосбиржи */}
            {!loading && !result && (
              <div className="space-y-3">
                <HomeChart period={period} />
                <p className="text-sm text-gray-500 dark:text-night-mut text-center">
                  Выбери инструменты в боковой панели и нажми «Запустить анализ».
                  Таймфрейм графика меняется кнопками сверху.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Плавающий AI-аналитик (кружок в правом нижнем углу) */}
      <AgentWidget jobId={jobId} />
    </div>
  )
}
