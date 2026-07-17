import { FileText, Presentation, FileSpreadsheet } from 'lucide-react'

const FORMATS = [
  { fmt: 'markdown', label: 'Markdown', Icon: FileText },
  { fmt: 'pptx', label: 'PowerPoint', Icon: Presentation },
  { fmt: 'xlsx', label: 'Excel', Icon: FileSpreadsheet },
]

/** Скачивание готового отчёта. Обычные ссылки: браузер сам сохранит файл. */
export function ExportButtons({ jobId }) {
  if (!jobId) return null
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-sm text-gray-500 mr-1">Скачать отчёт:</span>
      {FORMATS.map(({ fmt, label, Icon }) => (
        <a
          key={fmt}
          href={`/api/export/${jobId}/${fmt}`}
          download
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-sber-200 text-sber-700 text-sm font-medium hover:bg-sber-50 transition-colors"
        >
          <Icon size={15} />
          {label}
        </a>
      ))}
    </div>
  )
}
