import jsPDF from 'jspdf'
import autoTable from 'jspdf-autotable'
import { AlertTriangle, BarChart2, Calendar, Download, Eye, FileText, Filter, Search, Trash2, TrendingUp, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { getPitayaUserScopeHeaders } from '../api/userScope'

/* ─── helpers ─────────────────────────────────────────────── */
const MANILA_TIME_ZONE = 'Asia/Manila'
const parseReportTimestamp = (ts) => {
  const value = String(ts || '').trim()
  if (!value) return null

  // Older Railway records were saved as UTC without an offset. Treat only
  // those offset-free ISO-like values as UTC; new records include +08:00.
  const hasOffset = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(value)
  return new Date(hasOffset ? value : `${value.replace(' ', 'T')}Z`)
}
const fmt = (ts) => {
  if (!ts) return '—'
  try { return parseReportTimestamp(ts).toLocaleString('en-PH', { timeZone: MANILA_TIME_ZONE }) } catch { return ts }
}
const fmtDate = (ts) => {
  if (!ts) return '—'
  try { return parseReportTimestamp(ts).toLocaleDateString('en-PH', { timeZone: MANILA_TIME_ZONE }) } catch { return ts }
}
const csvEscape = (v) => {
  const s = String(v ?? '')
  return s.includes(',') || s.includes('"') || s.includes('\n') ? `"${s.replace(/"/g, '""')}"` : s
}

/* ─── PDF builder ─────────────────────────────────────────── */
const buildPdf = (rows, isSingle = false) => {
  const doc = new jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4' })

  // header bar
  doc.setFillColor(22, 163, 74)
  doc.rect(0, 0, 297, 18, 'F')
  doc.setTextColor(255, 255, 255)
  doc.setFontSize(14)
  doc.setFont('helvetica', 'bold')
  doc.text('Pitaya Farm — Yield Detection Report', 14, 12)
  doc.setFontSize(9)
  doc.setFont('helvetica', 'normal')
  doc.text(`Generated: ${new Date().toLocaleString()}`, 250, 12, { align: 'right' })

  if (!isSingle) {
    const total = rows.length
    const totalFruits = rows.reduce((s, r) => s + (r.predicted_yield || 0), 0)
    const blocks = new Set(rows.map(r => r.location)).size
    doc.setTextColor(55, 65, 81)
    doc.setFontSize(9)
    doc.setFont('helvetica', 'normal')
    doc.text(`Total Records: ${total}   |   Total Fruits Detected: ${totalFruits}   |   Unique Blocks: ${blocks}`, 14, 26)
  }

  const startY = isSingle ? 24 : 32

  autoTable(doc, {
    startY,
    head: [['#', 'Date & Time', 'Upload Type', 'Fruits Detected', 'Season']],
    body: rows.map((r, i) => [
      i + 1,
      fmt(r.prediction_date),
      r.upload_type === 'video' ? 'Video' : 'Image',
      r.predicted_yield,
      r.season,
    ]),
    styles: { fontSize: 9, cellPadding: 3 },
    headStyles: { fillColor: [22, 163, 74], textColor: 255, fontStyle: 'bold' },
    alternateRowStyles: { fillColor: [240, 253, 244] },
    columnStyles: { 0: { halign: 'center', cellWidth: 12 }, 3: { halign: 'center' } },
  })

  const pageCount = doc.internal.getNumberOfPages()
  for (let i = 1; i <= pageCount; i++) {
    doc.setPage(i)
    doc.setFontSize(8)
    doc.setTextColor(150)
    doc.text(`Page ${i} of ${pageCount}`, doc.internal.pageSize.width - 14, doc.internal.pageSize.height - 6, { align: 'right' })
  }

  return doc
}

/* ─── CSV builder ─────────────────────────────────────────── */
const buildCsv = (rows) => {
  const header = ['ID', 'Date & Time', 'Upload Type', 'Fruits Detected', 'Season']
  const body = rows.map(r => [r.id, fmt(r.prediction_date), r.upload_type === 'video' ? 'Video' : 'Image', r.predicted_yield, r.season])
  return [header, ...body].map(row => row.map(csvEscape).join(',')).join('\n')
}

const triggerDownload = (content, filename, mime) => {
  const blob = new Blob([content], { type: mime })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = filename
  document.body.appendChild(a); a.click()
  URL.revokeObjectURL(url); document.body.removeChild(a)
}

/* ═══════════════════════════════════════════════════════════ */
const YieldReport = () => {
  const [records, setRecords] = useState([])
  const [filtered, setFiltered] = useState([])
  const [loading, setLoading] = useState(true)
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedRecord, setSelectedRecord] = useState(null)   // detail modal
  const [previewTarget, setPreviewTarget] = useState(undefined) // undefined=closed, null=all, obj=single
  const [previewFormat, setPreviewFormat] = useState('csv')    // 'csv' | 'pdf'
  const [confirmDelete, setConfirmDelete] = useState(null)      // { id, label } | null
  const [currentPage, setCurrentPage] = useState(1)
  const itemsPerPage = 10

  useEffect(() => { fetchRecords() }, [])
  useEffect(() => {
    const h = () => fetchRecords()
    window.addEventListener('pitaya:refresh', h)
    return () => window.removeEventListener('pitaya:refresh', h)
  }, [])
  useEffect(() => { applyFilter(); setCurrentPage(1) }, [records, searchTerm])

  const fetchRecords = async () => {
    try {
      const res = await fetch('/api/dashboard/yield-predictions', {
        headers: getPitayaUserScopeHeaders(),
      })
      const root = await res.json()
      setRecords((root.data || []).map(r => ({
        id: r.id,
        prediction_date: r.prediction_date,
        location: r.location || 'Unknown',
        predicted_yield: r.predicted_yield ?? 0,
        season: r.season || '—',
        actual_yield: r.actual_yield,
        accuracy_score: r.accuracy_score,
        created_at: r.created_at,
        upload_type: r.upload_type || 'image',
      })))
    } catch (e) { console.error(e) }
    finally { setLoading(false) }
  }

  const applyFilter = () => {
    let r = [...records]
    if (searchTerm) {
      const t = searchTerm.toLowerCase()
      r = r.filter(x =>
        x.location.toLowerCase().includes(t) ||
        x.season.toLowerCase().includes(t) ||
        String(x.predicted_yield).includes(t)
      )
    }
    setFiltered(r)
  }

  const deleteRecord = async (id) => {
    try {
      const res = await fetch(`/api/dashboard/yield-predictions/${id}`, {
        method: 'DELETE',
        headers: getPitayaUserScopeHeaders(),
      })
      if (res.ok) {
        setRecords(p => p.filter(r => r.id !== id))
        if (selectedRecord?.id === id) setSelectedRecord(null)
      }
    } catch (e) { console.error(e) }
  }

  const askDelete = (id, label) => setConfirmDelete({ id, label })

  const confirmAndDelete = async () => {
    if (!confirmDelete) return
    await deleteRecord(confirmDelete.id)
    setConfirmDelete(null)
  }

  /* ─── download / preview ──────────────────────────────────── */
  const openPreview = (record = null) => {
    setPreviewTarget(record)   // null = all records
    setPreviewFormat('csv')
  }

  const doDownload = () => {
    const rows = previewTarget ? [previewTarget] : filtered
    const stamp = previewTarget ? `_${previewTarget.id}` : '_filtered'
    const base = `yield_report${stamp}`
    if (previewFormat === 'pdf') {
      buildPdf(rows, !!previewTarget).save(`${base}.pdf`)
    } else {
      triggerDownload(buildCsv(rows), `${base}.csv`, 'text/csv')
    }
    setPreviewTarget(undefined)
  }

  /* ─── stats ─────────────────────────────────────────────── */
  const stats = (() => {
    const total = records.length
    const totalFruits = Math.round(records.reduce((s, r) => s + (r.predicted_yield || 0), 0) * 10) / 10
    const videoCount = records.filter(r => r.upload_type === 'video').length
    const imageCount = records.filter(r => r.upload_type === 'image').length
    const latest = records[0]?.prediction_date
    return { total, totalFruits, videoCount, imageCount, latest }
  })()

  const totalPages = Math.ceil(filtered.length / itemsPerPage)
  const pageStart = (currentPage - 1) * itemsPerPage
  const pageRecords = filtered.slice(pageStart, pageStart + itemsPerPage)
  const previewRows = previewTarget ? [previewTarget] : filtered.slice(0, 8)
  const previewIsOpen = previewTarget !== undefined

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-green-600" />
    </div>
  )

  return (
    <div className="max-w-7xl mx-auto p-4 sm:p-6">

      {/* ── Header ─────────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6 sm:mb-8">
        <div className="flex items-center gap-3">
          <BarChart2 className="w-6 h-6 sm:w-8 sm:h-8 text-green-600 dark:text-green-400" />
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-gray-100">Yield Report</h1>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => openPreview(null)}
            className="px-4 py-2 bg-green-600 dark:bg-green-700 text-white rounded-lg hover:bg-green-700 dark:hover:bg-green-800 transition-colors flex items-center gap-2"
          >
            <Download className="w-4 h-4" />
            Export All
          </button>
        </div>
      </div>

      {/* ── Stat Cards ─────────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 mb-6">
        {[
          { icon: BarChart2, label: 'Total Records', value: stats.total, color: 'green' },
          { icon: TrendingUp, label: 'Total Fruits', value: stats.totalFruits, color: 'blue' },
          { icon: Filter, label: 'Video Uploads', value: stats.videoCount, color: 'purple' },
          { icon: Calendar, label: 'Latest Entry', value: fmtDate(stats.latest) || '—', color: 'orange', small: true },
        ].map(({ icon: Icon, label, value, color, small }) => (
          <div key={label} className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-4">
            <div className="flex items-center gap-2">
              <Icon className={`w-5 h-5 text-${color}-600 dark:text-${color}-400`} />
              <span className="text-sm font-medium text-gray-600 dark:text-gray-300">{label}</span>
            </div>
            <p className={`${small ? 'text-sm' : 'text-2xl'} font-bold text-${color}-600 dark:text-${color}-400 mt-1 truncate`}>{value}</p>
          </div>
        ))}
      </div>

      {/* Search */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-4 mb-6">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 dark:text-gray-500 w-5 h-5" />
          <input
            type="text"
            placeholder="Search by block, season, or fruit count…"
            value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
          />
        </div>
      </div>

      {/* Table */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 dark:bg-gray-700 border-b border-gray-200 dark:border-gray-600">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Date &amp; Time</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Upload Type</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Fruits Detected</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Season</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
              {pageRecords.length === 0 ? (
                <tr>
                  <td colSpan="5" className="px-6 py-12 text-center">
                    <BarChart2 className="w-16 h-16 text-gray-300 dark:text-gray-600 mx-auto mb-4" />
                    <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-2">No yield records found</h3>
                    <p className="text-gray-600 dark:text-gray-400">
                      {searchTerm ? 'Try adjusting your search.' : 'Save detections from the Yield Prediction page to see records here.'}
                    </p>
                  </td>
                </tr>
              ) : (
                pageRecords.map(record => (
                  <tr key={record.id} className="hover:bg-gray-50 dark:hover:bg-gray-700">
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-gray-100">
                      <div className="flex items-center gap-2">
                        <Calendar className="w-4 h-4 text-gray-400 dark:text-gray-500 shrink-0" />
                        {fmt(record.prediction_date)}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`px-2 py-1 rounded-full text-xs font-medium border ${
                        record.upload_type === 'video' 
                          ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-300 border-blue-300 dark:border-blue-700'
                          : 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300 border-green-300 dark:border-green-700'
                      }`}>
                        {record.upload_type === 'video' ? '📹 Video' : '📷 Image'}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center gap-2">
                        <div className="flex-1 max-w-[120px] bg-gray-200 dark:bg-gray-600 rounded-full h-2">
                          <div
                            className="bg-green-500 h-2 rounded-full"
                            style={{ width: `${Math.min(100, (record.predicted_yield / 200) * 100)}%` }}
                          />
                        </div>
                        <span className="text-sm font-semibold text-gray-900 dark:text-gray-100">{record.predicted_yield}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600 dark:text-gray-300">
                      {record.season}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => setSelectedRecord(record)}
                          className="p-1 text-blue-600 dark:text-blue-400 hover:text-blue-800 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded"
                          title="View Details"
                        >
                          <Eye className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => openPreview(record)}
                          className="p-1 text-green-600 dark:text-green-400 hover:text-green-800 hover:bg-green-50 dark:hover:bg-green-900/20 rounded"
                          title="Download"
                        >
                          <Download className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => askDelete(record.id, `Record #${record.id} — ${record.location} (${record.predicted_yield} fruits)`)}
                          className="p-1 text-red-600 dark:text-red-400 hover:text-red-800 hover:bg-red-50 dark:hover:bg-red-900/20 rounded"
                          title="Delete Record"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-4 mt-4">
          <div className="text-sm text-gray-600 dark:text-gray-300">
            Showing {pageStart + 1}–{Math.min(pageStart + itemsPerPage, filtered.length)} of {filtered.length} records
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
              disabled={currentPage === 1}
              className="px-3 py-1 rounded-lg text-sm font-medium bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              Previous
            </button>
            {Array.from({ length: totalPages }, (_, i) => i + 1).map(page => (
              <button
                key={page}
                onClick={() => setCurrentPage(page)}
                className={`px-3 py-1 rounded-lg text-sm font-medium transition-colors ${
                  currentPage === page
                    ? 'bg-green-600 text-white'
                    : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
                }`}
              >
                {page}
              </button>
            ))}
            <button
              onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages}
              className="px-3 py-1 rounded-lg text-sm font-medium bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              Next
            </button>
          </div>
        </div>
      )}

      {/* Detail Modal */}
      {selectedRecord && (
        <div className="fixed inset-0 bg-black bg-opacity-50 dark:bg-gray-900/80 flex items-center justify-center p-4 z-50">
          <div className="bg-white dark:bg-gray-800 rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              {/* Modal Header */}
              <div className="flex items-start justify-between mb-6">
                <div>
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-1">Yield Detection Report</h2>
                  <div className="flex items-center gap-3 text-sm text-gray-600 dark:text-gray-300">
                    <span className="flex items-center gap-1">
                      <Calendar className="w-4 h-4" />
                      {fmt(selectedRecord.prediction_date)}
                    </span>
                    <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300 border border-green-300 dark:border-green-700">
                      {selectedRecord.location}
                    </span>
                  </div>
                </div>
                <button
                  onClick={() => setSelectedRecord(null)}
                  className="text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300"
                >
                  <X className="w-6 h-6" />
                </button>
              </div>

              {/* Info Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
                <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
                  <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-3">Detection Information</h3>
                  <div className="space-y-2">
                    {[
                      ['Record ID', `#${selectedRecord.id}`],
                      ['Upload Type', selectedRecord.upload_type === 'video' ? '📹 Video' : '📷 Image'],
                      ['Fruits Detected', selectedRecord.predicted_yield, 'green'],
                      ['Season', selectedRecord.season],
                      ...(selectedRecord.actual_yield != null ? [['Actual Yield', selectedRecord.actual_yield]] : []),
                      ...(selectedRecord.accuracy_score != null ? [['Accuracy Score', `${selectedRecord.accuracy_score}%`]] : []),
                    ].map(([label, value, color]) => (
                      <div key={label} className="flex justify-between">
                        <span className="text-sm text-gray-600 dark:text-gray-300">{label}:</span>
                        <span className={`text-sm font-${color ? 'bold' : 'medium'} ${color ? `text-${color}-600 dark:text-${color}-400` : 'text-gray-900 dark:text-gray-100'}`}>{value}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
                  <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-3">Download Options</h3>
                  <div className="space-y-2">
                    <button
                      onClick={() => { setSelectedRecord(null); openPreview(selectedRecord) }}
                      className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
                    >
                      <Download className="w-4 h-4" />
                      Download Report (CSV / PDF)
                    </button>
                    <button
                      onClick={() => { setSelectedRecord(null); askDelete(selectedRecord.id, `Record #${selectedRecord.id} — ${selectedRecord.location} (${selectedRecord.predicted_yield} fruits)`) }}
                      className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                      Delete Record
                    </button>
                  </div>
                </div>
              </div>

              {/* Summary section */}
              <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-4">
                <h3 className="text-sm font-semibold text-green-800 dark:text-green-300 mb-2">Detection Summary</h3>
                <ul className="space-y-1">
                  {[
                    <><strong>{selectedRecord.predicted_yield}</strong> mature dragon fruits were detected in this session.</>,
                    <>Recorded for block / location: <strong>{selectedRecord.location}</strong>.</>,
                    <>Detected on <strong>{fmt(selectedRecord.prediction_date)}</strong> during season <strong>{selectedRecord.season}</strong>.</>,
                  ].map((content, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-green-700 dark:text-green-300">
                      <span className="mt-1">•</span><span>{content}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════
          DOWNLOAD PREVIEW MODAL
      ═══════════════════════════════════════════════════════ */}
      {previewIsOpen && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center p-4 z-50">
          <div className="bg-white dark:bg-gray-800 rounded-xl max-w-3xl w-full max-h-[90vh] flex flex-col shadow-2xl">

            {/* modal header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
              <div className="flex items-center gap-3">
                <FileText className="w-5 h-5 text-green-600 dark:text-green-400" />
                <h2 className="text-lg font-bold text-gray-900 dark:text-gray-100">
                  {previewTarget ? `Download Record #${previewTarget.id}` : `Export All Records (${records.length})`}
                </h2>
              </div>
              <button onClick={() => setPreviewTarget(undefined)} className="text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300">
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* format toggle */}
            <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">Select download format</p>
              <div className="flex gap-3">
                {['csv', 'pdf'].map(f => (
                  <button
                    key={f}
                    onClick={() => setPreviewFormat(f)}
                    className={`flex items-center gap-2 px-5 py-2.5 rounded-lg border-2 font-semibold text-sm transition-all ${
                      previewFormat === f
                        ? 'border-green-600 bg-green-50 dark:bg-green-900/30 text-green-700 dark:text-green-300'
                        : 'border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:border-green-400'
                    }`}
                  >
                    {f === 'csv' ? <FileText className="w-4 h-4" /> : <Download className="w-4 h-4" />}
                    {f.toUpperCase()}
                    {previewFormat === f && <span className="ml-1 text-xs font-normal opacity-70">selected</span>}
                  </button>
                ))}
              </div>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
                {previewFormat === 'csv'
                  ? 'Comma-separated values — opens in Excel, Google Sheets, etc.'
                  : 'PDF document — formatted report with table and header, ready to print or share.'}
              </p>
            </div>

            {/* preview area */}
            <div className="flex-1 overflow-y-auto px-6 py-4">
              <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-3">
                Preview {previewTarget ? '(1 record)' : `(showing first ${Math.min(8, filtered.length)} of ${filtered.length})`}
              </p>

              {/* PDF visual preview */}
              {previewFormat === 'pdf' && (
                <div className="bg-white dark:bg-gray-100 border border-gray-300 dark:border-gray-600 rounded-lg p-4 mb-3 shadow-sm">
                  <div className="bg-green-600 text-white px-4 py-2 rounded-t mb-3">
                    <div className="font-bold text-sm">Pitaya Farm — Yield Detection Report</div>
                    <div className="text-xs opacity-80 mt-1">{new Date().toLocaleString()}</div>
                  </div>
                  {!previewTarget && (
                    <div className="bg-green-50 dark:bg-green-100 px-4 py-2 rounded text-xs text-green-800 dark:text-green-900 mb-3 border border-green-200 dark:border-green-300">
                      <div className="font-semibold mb-1">Summary Statistics</div>
                      <div>Total Records: {filtered.length} | Total Fruits: {Math.round(filtered.reduce((s, r) => s + (r.predicted_yield || 0), 0) * 10) / 10} | Video Uploads: {filtered.filter(r => r.upload_type === 'video').length}</div>
                    </div>
                  )}
                  <div className="text-xs text-gray-500 dark:text-gray-700 mb-2">
                    📄 This is a preview of the PDF document layout. The actual PDF will contain the complete table with all data.
                  </div>
                  <div className="border-t border-gray-200 dark:border-gray-300 pt-2 mt-2">
                    <div className="text-xs text-gray-400 dark:text-gray-500 text-center">
                      Page 1 of {previewTarget ? 1 : Math.ceil(filtered.length / 20)}
                    </div>
                  </div>
                </div>
              )}

              {/* CSV raw preview */}
              {previewFormat === 'csv' && (
                <pre className="bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-3 text-xs text-gray-700 dark:text-gray-300 overflow-x-auto mb-3 font-mono whitespace-pre">
                  {buildCsv(previewRows)}
                  {!previewTarget && filtered.length > 8 ? `\n… and ${filtered.length - 8} more rows` : ''}
                </pre>
              )}

              {/* shared table preview */}
              <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700">
                <table className="w-full text-sm">
                  <thead className="bg-green-600 text-white">
                    <tr>
                      {['#', 'Date & Time', 'Upload Type', 'Fruits Detected', 'Season'].map(h => (
                        <th key={h} className="px-4 py-2 text-left font-semibold text-xs">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                    {previewRows.map((r, i) => (
                      <tr key={r.id} className={i % 2 === 0 ? 'bg-white dark:bg-gray-800' : 'bg-green-50 dark:bg-green-900/10'}>
                        <td className="px-4 py-2 text-gray-500 dark:text-gray-400">{i + 1}</td>
                        <td className="px-4 py-2 text-gray-900 dark:text-gray-100">{fmt(r.prediction_date)}</td>
                        <td className="px-4 py-2">
                          <span className={`px-2 py-0.5 rounded-full text-xs border ${
                            r.upload_type === 'video' 
                              ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-300 border-blue-300 dark:border-blue-700'
                              : 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300 border-green-300 dark:border-green-700'
                          }`}>
                            {r.upload_type === 'video' ? '📹 Video' : '📷 Image'}
                          </span>
                        </td>
                        <td className="px-4 py-2 font-semibold text-green-700 dark:text-green-400">{r.predicted_yield}</td>
                        <td className="px-4 py-2 text-gray-600 dark:text-gray-300">{r.season}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {!previewTarget && filtered.length > 8 && (
                <p className="text-xs text-gray-500 dark:text-gray-400 text-center mt-2">… and {filtered.length - 8} more records will be included in the download.</p>
              )}
            </div>

            {/* footer */}
            <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-200 dark:border-gray-700">
              <button
                onClick={() => setPreviewTarget(undefined)}
                className="px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors text-sm"
              >
                Cancel
              </button>
              <button
                onClick={doDownload}
                className="px-6 py-2 rounded-lg bg-green-600 hover:bg-green-700 text-white font-semibold flex items-center gap-2 transition-colors text-sm"
              >
                <Download className="w-4 h-4" />
                Download {previewFormat.toUpperCase()}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════
          CONFIRM DELETE DIALOG
      ═══════════════════════════════════════════════════════ */}
      {confirmDelete && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 z-[60] animate-in fade-in duration-200">
          <div className="bg-white dark:bg-gray-800 rounded-2xl max-w-md w-full shadow-2xl animate-in slide-in-from-bottom-4 duration-300">
            <div className="p-6">
              {/* Header */}
              <div className="flex items-center gap-4 mb-6">
                <div className="w-14 h-14 rounded-full bg-gradient-to-br from-red-100 to-red-200 dark:from-red-900/40 dark:to-red-800/30 flex items-center justify-center shrink-0 shadow-sm">
                  <Trash2 className="w-7 h-7 text-red-600 dark:text-red-400" />
                </div>
                <div>
                  <h3 className="text-xl font-bold text-gray-900 dark:text-gray-100">Delete Record</h3>
                  <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">This action cannot be undone</p>
                </div>
              </div>

              {/* Content Box */}
              <div className="bg-gradient-to-r from-gray-50 to-gray-100 dark:from-gray-700/50 dark:to-gray-800/50 rounded-xl px-5 py-4 mb-6 border border-gray-200 dark:border-gray-700">
                <div className="flex items-center gap-3">
                  <div className="w-2 h-2 rounded-full bg-red-500"></div>
                  <p className="text-sm text-gray-700 dark:text-gray-300 font-medium">{confirmDelete.label}</p>
                </div>
              </div>

              {/* Warning Message */}
              <div className="flex items-start gap-3 mb-6 p-4 bg-amber-50 dark:bg-amber-900/20 rounded-lg border border-amber-200 dark:border-amber-800">
                <AlertTriangle className="w-5 h-5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
                <p className="text-sm text-amber-800 dark:text-amber-200">
                  Deleting this record will permanently remove it from the database. Make sure you have a backup if needed.
                </p>
              </div>

              {/* Action Buttons */}
              <div className="flex gap-3">
                <button
                  onClick={() => setConfirmDelete(null)}
                  className="flex-1 px-4 py-3 rounded-xl border-2 border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700 transition-all duration-200 font-semibold"
                >
                  Cancel
                </button>
                <button
                  onClick={confirmAndDelete}
                  className="flex-1 px-4 py-3 rounded-xl bg-gradient-to-r from-red-600 to-red-700 hover:from-red-700 hover:to-red-800 text-white font-semibold transition-all duration-200 flex items-center justify-center gap-2 shadow-lg shadow-red-500/25"
                >
                  <Trash2 className="w-4 h-4" />
                  Delete
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default YieldReport
