import { ArrowUp, ArrowDown } from 'lucide-react'

export function RankingTable({ comparison, onSelectAsset }) {
  if (!comparison || !comparison.length) return null

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
      <div className="px-6 py-4 border-b border-gray-200">
        <h3 className="text-xl font-semibold">Рейтинг инструментов</h3>
        <p className="text-sm text-gray-500 mt-1">
          {comparison.length} актив(ов) · соотношение доходность/риск · нажми на строку для деталей
        </p>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200">
              <th className="px-6 py-3 text-left text-sm font-semibold text-gray-700">
                Место
              </th>
              <th className="px-6 py-3 text-left text-sm font-semibold text-gray-700">
                Тикер
              </th>
              <th className="px-6 py-3 text-right text-sm font-semibold text-gray-700">
                Доходность
              </th>
              <th className="px-6 py-3 text-right text-sm font-semibold text-gray-700">
                Волатильность
              </th>
              <th className="px-6 py-3 text-right text-sm font-semibold text-gray-700">
                Шарп
              </th>
            </tr>
          </thead>
          <tbody>
            {comparison.map((entry, idx) => (
              <tr
                key={entry.ticker}
                className="border-b border-gray-200 hover:bg-sber-50 cursor-pointer transition-colors"
                onClick={() => onSelectAsset?.(entry.ticker)}
              >
                <td className="px-6 py-4">
                  <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-sber-100 text-sber-700 font-semibold text-sm num">
                    {entry.rank || idx + 1}
                  </span>
                </td>
                <td className="px-6 py-4 font-semibold text-gray-900">
                  {entry.ticker}
                </td>
                <td className="px-6 py-4 text-right">
                  <div
                    className={`flex items-center justify-end gap-2 font-semibold num ${
                      entry.return_pct >= 0
                        ? 'text-sber-600'
                        : 'text-red-600'
                    }`}
                  >
                    {entry.return_pct >= 0 ? (
                      <ArrowUp size={16} />
                    ) : (
                      <ArrowDown size={16} />
                    )}
                    {Math.abs(entry.return_pct).toFixed(2)}%
                  </div>
                </td>
                <td className="px-6 py-4 text-right text-gray-700 num">
                  {entry.volatility_pct.toFixed(2)}%
                </td>
                <td className="px-6 py-4 text-right text-gray-700 num">
                  {entry.sharpe?.toFixed(2) || '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
