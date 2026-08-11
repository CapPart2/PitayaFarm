import { ChevronLeft, ChevronRight } from 'lucide-react'

function pageItems(currentPage, totalPages) {
  if (totalPages <= 7) return Array.from({ length: totalPages }, (_, index) => index + 1)

  const visible = new Set([1, totalPages, currentPage - 1, currentPage, currentPage + 1])
  if (currentPage <= 3) {
    visible.add(2)
    visible.add(3)
    visible.add(4)
    visible.add(5)
  }
  if (currentPage >= totalPages - 2) {
    visible.add(totalPages - 1)
    visible.add(totalPages - 2)
    visible.add(totalPages - 3)
    visible.add(totalPages - 4)
  }

  const pages = [...visible].filter((page) => page >= 1 && page <= totalPages).sort((a, b) => a - b)
  return pages.reduce((items, page, index) => {
    if (index && page - pages[index - 1] > 1) items.push(`ellipsis-${pages[index - 1]}`)
    items.push(page)
    return items
  }, [])
}

export default function AdminPagination({ currentPage, totalPages, onPageChange, start, end, total, accent = 'purple' }) {
  if (totalPages <= 1) return null

  const activeClass = accent === 'green' ? 'bg-green-600 border-green-600' : accent === 'blue' ? 'bg-blue-600 border-blue-600' : 'bg-purple-600 border-purple-600'
  const buttonClass = 'inline-flex h-10 min-w-10 items-center justify-center rounded-md border border-gray-300 bg-white px-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-purple-500 disabled:cursor-not-allowed disabled:opacity-45 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200 dark:hover:bg-gray-700'

  return (
    <div className="flex flex-col gap-3 border-t border-gray-200 px-4 py-4 dark:border-gray-700 sm:flex-row sm:items-center sm:justify-between sm:px-6">
      <p className="text-center text-sm text-gray-500 dark:text-gray-400 sm:text-left">
        Showing {start}-{end} of {total} entries
      </p>
      <nav className="flex flex-wrap items-center justify-center gap-1.5" aria-label="Pagination">
        <button type="button" onClick={() => onPageChange(currentPage - 1)} disabled={currentPage === 1} className={`${buttonClass} gap-1 px-3`} aria-label="Previous page">
          <ChevronLeft className="h-4 w-4" aria-hidden />
          <span className="hidden sm:inline">Prev</span>
        </button>
        {pageItems(currentPage, totalPages).map((item) =>
          typeof item === 'string' ? (
            <span key={item} className="flex h-10 min-w-5 items-center justify-center text-sm text-gray-500 dark:text-gray-400" aria-hidden>…</span>
          ) : (
            <button
              key={item}
              type="button"
              onClick={() => onPageChange(item)}
              aria-current={item === currentPage ? 'page' : undefined}
              className={`${buttonClass} ${item === currentPage ? `${activeClass} text-white hover:brightness-95 dark:text-white` : ''}`}
            >
              {item}
            </button>
          )
        )}
        <button type="button" onClick={() => onPageChange(currentPage + 1)} disabled={currentPage === totalPages} className={`${buttonClass} gap-1 px-3`} aria-label="Next page">
          <span className="hidden sm:inline">Next</span>
          <ChevronRight className="h-4 w-4" aria-hidden />
        </button>
      </nav>
    </div>
  )
}
