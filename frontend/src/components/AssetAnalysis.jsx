import { PriceChart } from './PriceChart'
import { RiskCharts } from './RiskCharts'

export function AssetAnalysis({ ticker, asset, onClose }) {
  if (!asset) return null

  // API отдаёт metrics уже в виде payload (см. to_payload на бэке)
  const payload = asset.metrics || {}
  const rets = payload.returns_pct || {}
  const risk = payload.risk || {}
  const perf = payload.performance || {}
  const tail = payload.tail_risk || {}
  const bench = payload.benchmark
  const commentary = asset.commentary
  const conf = tail.confidence_pct || 95

  const riskBandColor =
    risk.band === 'high' || risk.band === 'высокий'
      ? 'bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300'
      : risk.band === 'medium' || risk.band === 'средний'
        ? 'bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300'
        : 'bg-sber-100 text-sber-700 dark:bg-sber-900 dark:text-sber-300'

  const posNeg = (v) =>
    (v || 0) >= 0 ? 'text-sber-600 dark:text-sber-400' : 'text-red-600 dark:text-red-400'

  return (
    <div className="space-y-6">
      {/* Заголовок */}
      <div className="flex justify-between items-start">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <h2 className="text-3xl font-bold">{ticker}</h2>
            {risk.score != null && (
              <span className={`px-3 py-1 rounded-full text-sm font-semibold ${riskBandColor}`}>
                Риск {risk.score}/100
              </span>
            )}
          </div>
          <p className="text-gray-600 dark:text-night-sub">Подробный анализ и метрики</p>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700 dark:text-night-mut dark:hover:text-night-sub"
          >
            ✕
          </button>
        )}
      </div>

      {/* Ключевые метрики */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="card">
          <p className="card-text">Последняя цена</p>
          <p className="text-2xl font-bold mt-2 num">
            {payload.last_price?.toFixed(2) || '—'}
          </p>
          <p className="text-xs text-gray-500 dark:text-night-mut mt-1">{payload.currency || ''}</p>
        </div>

        <div className="card">
          <p className="card-text">Доходность 1 день</p>
          <p className={`text-2xl font-bold mt-2 num ${posNeg(rets['1d'])}`}>
            {(rets['1d'] || 0) >= 0 ? '+' : ''}{(rets['1d'] || 0).toFixed(2)}%
          </p>
        </div>

        <div className="card">
          <p className="card-text">Доходность 30 дней</p>
          <p className={`text-2xl font-bold mt-2 num ${posNeg(rets['30d'])}`}>
            {(rets['30d'] || 0) >= 0 ? '+' : ''}{(rets['30d'] || 0).toFixed(2)}%
          </p>
        </div>

        <div className="card">
          <p className="card-text">Годовая волатильность</p>
          <p className="text-2xl font-bold mt-2 num">
            {(payload.volatility?.annualized_pct || 0).toFixed(1)}%
          </p>
        </div>
      </div>

      {/* Интерактивный график цены */}
      <PriceChart
        history={asset.history}
        ticker={ticker}
        currency={payload.currency}
      />

      {/* Риск-графики: просадки, распределение доходностей, метрики во времени */}
      <RiskCharts history={asset.history} tail={tail} />

      {/* Показатели эффективности */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <div className="card">
          <p className="card-text">Коэф. Шарпа</p>
          <p className="text-2xl font-bold mt-2 num">
            {perf.sharpe?.toFixed(2) ?? '—'}
          </p>
          <p className="text-xs text-gray-500 dark:text-night-mut mt-1">доходность на единицу риска</p>
        </div>

        <div className="card">
          <p className="card-text">Коэф. Сортино</p>
          <p className="text-2xl font-bold mt-2 num">
            {perf.sortino?.toFixed(2) ?? '—'}
          </p>
          <p className="text-xs text-gray-500 dark:text-night-mut mt-1">учитывает только падения</p>
        </div>

        <div className="card">
          <p className="card-text">VaR {conf}%</p>
          <p className="text-2xl font-bold mt-2 text-red-600 dark:text-red-400 num">
            {tail.historical_var_pct != null ? `${tail.historical_var_pct.toFixed(2)}%` : '—'}
          </p>
          <p className="text-xs text-gray-500 dark:text-night-mut mt-1">дневная потеря в худших {100 - conf}% случаев</p>
        </div>
      </div>

      {/* Таблица доходности и риска */}
      <div className="card">
        <h3 className="card-title">Доходность и риск</h3>
        <div className="overflow-x-auto mt-4">
          <table className="w-full text-sm">
            <tbody>
              <tr className="border-b border-gray-200 dark:border-night-border">
                <td className="py-2 text-gray-700 dark:text-night-sub">Накопленная доходность</td>
                <td className="py-2 text-right font-semibold num">
                  {payload.cumulative_return_pct?.toFixed(2) ?? '—'}%
                </td>
              </tr>
              <tr className="border-b border-gray-200 dark:border-night-border">
                <td className="py-2 text-gray-700 dark:text-night-sub">Годовая доходность (CAGR)</td>
                <td className="py-2 text-right font-semibold num">
                  {perf.annualized_return_pct?.toFixed(2) ?? '—'}%
                </td>
              </tr>
              <tr className="border-b border-gray-200 dark:border-night-border">
                <td className="py-2 text-gray-700 dark:text-night-sub">Максимальная просадка</td>
                <td className="py-2 text-right font-semibold text-red-600 dark:text-red-400 num">
                  {risk.max_drawdown_pct?.toFixed(2) ?? '—'}%
                </td>
              </tr>
              <tr className="border-b border-gray-200 dark:border-night-border">
                <td className="py-2 text-gray-700 dark:text-night-sub">CVaR {conf}% (ист.)</td>
                <td className="py-2 text-right font-semibold text-red-600 dark:text-red-400 num">
                  {tail.historical_cvar_pct != null ? `${tail.historical_cvar_pct.toFixed(2)}%` : '—'}
                </td>
              </tr>
              {bench && (
                <>
                  <tr className="border-b border-gray-200 dark:border-night-border">
                    <td className="py-2 text-gray-700 dark:text-night-sub">Бета к {bench.benchmark}</td>
                    <td className="py-2 text-right font-semibold num">
                      {bench.beta?.toFixed(2) ?? '—'}
                    </td>
                  </tr>
                  <tr>
                    <td className="py-2 text-gray-700 dark:text-night-sub">Альфа (годовая)</td>
                    <td className="py-2 text-right font-semibold num">
                      {bench.alpha_annual_pct?.toFixed(2) ?? '—'}%
                    </td>
                  </tr>
                </>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* AI-комментарий */}
      {commentary && (
        <div className="card bg-gradient-to-br from-sber-50 to-teal-50 dark:from-[#14351F] dark:to-[#0E2A1D] border-sber-200 dark:border-sber-900">
          <h3 className="card-title">🧠 Комментарий AI-аналитика</h3>
          <div className="mt-4 space-y-4 text-sm">
            <div>
              <p className="font-semibold text-gray-900 dark:text-night-text">Сводка</p>
              <p className="text-gray-700 dark:text-night-sub mt-1">{commentary.summary}</p>
            </div>
            <div>
              <p className="font-semibold text-gray-900 dark:text-night-text">Тренд</p>
              <p className="text-gray-700 dark:text-night-sub mt-1">{commentary.trend_explanation}</p>
            </div>
            <div>
              <p className="font-semibold text-gray-900 dark:text-night-text">Анализ риска</p>
              <p className="text-gray-700 dark:text-night-sub mt-1">{commentary.risk_analysis}</p>
            </div>
            {commentary.key_signals && commentary.key_signals.length > 0 && (
              <div>
                <p className="font-semibold text-gray-900 dark:text-night-text">Ключевые сигналы</p>
                <ul className="list-disc list-inside text-gray-700 dark:text-night-sub mt-1">
                  {commentary.key_signals.map((signal, idx) => (
                    <li key={idx}>{signal}</li>
                  ))}
                </ul>
              </div>
            )}
            <p className="text-xs text-gray-500 dark:text-night-mut pt-2 border-t border-sber-200 dark:border-sber-900">
              Сгенерировано: {commentary.provider} ({commentary.model})
            </p>
          </div>
        </div>
      )}

    </div>
  )
}
