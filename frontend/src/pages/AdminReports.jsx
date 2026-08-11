import { motion } from 'framer-motion'
import jsPDF from 'jspdf'
import {
    AlertTriangle,
    Apple,
    BarChart3,
    Calendar,
    Download,
    Eye,
    Leaf,
    PieChart,
    TrendingUp,
    X
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
    Bar,
    BarChart,
    CartesianGrid,
    Cell,
    Legend,
    Pie,
    PieChart as RechartsPieChart,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis
} from 'recharts'
import { adminAuthApi, adminDetectionsApi, adminYieldApi } from '../api/adminApi'

const container = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.05 },
  },
}

const item = {
  hidden: { opacity: 0, y: 10 },
  show: { opacity: 1, y: 0 },
}

const DISEASE_COLORS = [
  '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF',
  '#FF9F40', '#FF6B6B', '#4ECDC4', '#95E1D3'
]

export default function AdminReports() {
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState('disease')
  const [detections, setDetections] = useState([])
  const [yieldPredictions, setYieldPredictions] = useState([])
  const [loading, setLoading] = useState(true)
  const [currentPage, setCurrentPage] = useState(1)
  const recordsPerPage = 10
  const [showPreviewModal, setShowPreviewModal] = useState(false)
  const [previewData, setPreviewData] = useState(null)
  const reportRef = useRef(null)

  useEffect(() => {
    if (!adminAuthApi.isAuthenticated()) {
      navigate('/login')
      return
    }
    loadData()
  }, [navigate])

  useEffect(() => {
    setCurrentPage(1)
  }, [activeTab])

  const loadData = async () => {
    try {
      setLoading(true)
      const [detectionsResponse, yieldResponse] = await Promise.all([
        adminDetectionsApi.getAllDetections(),
        adminYieldApi.getAllPredictions()
      ])

      if (detectionsResponse.success) {
        setDetections(detectionsResponse.data || [])
      }
      if (yieldResponse.success) {
        setYieldPredictions(yieldResponse.data || [])
      }
    } catch (error) {
      console.error('Failed to load report data:', error)
    } finally {
      setLoading(false)
    }
  }

  // Disease Statistics
  const diseaseStats = detections.reduce((acc, detection) => {
    const disease = detection.DiseaseType || 'Unknown'
    acc[disease] = (acc[disease] || 0) + 1
    return acc
  }, {})

  const diseaseChartData = Object.entries(diseaseStats).map(([name, value]) => ({
    name,
    value
  })).sort((a, b) => b.value - a.value)

  const severityStats = detections.reduce((acc, detection) => {
    const severity = detection.Severity || 'unknown'
    acc[severity] = (acc[severity] || 0) + 1
    return acc
  }, {})

  const severityChartData = Object.entries(severityStats).map(([name, value]) => ({
    name: name.charAt(0).toUpperCase() + name.slice(1),
    value
  }))

  // Yield Statistics
  const yieldByLocation = yieldPredictions.reduce((acc, prediction) => {
    const location = prediction.location || 'Unknown'
    acc[location] = (acc[location] || 0) + prediction.predicted_yield
    return acc
  }, {})

  const yieldByLocationData = Object.entries(yieldByLocation).map(([name, value]) => ({
    name,
    value: Math.round(value)
  })).sort((a, b) => b.value - a.value)

  const yieldBySeason = yieldPredictions.reduce((acc, prediction) => {
    const season = prediction.season || 'Unknown'
    acc[season] = (acc[season] || 0) + prediction.predicted_yield
    return acc
  }, {})

  const yieldBySeasonData = Object.entries(yieldBySeason).map(([name, value]) => ({
    name,
    value: Math.round(value)
  }))

  const totalYield = yieldPredictions.reduce((sum, pred) => sum + pred.predicted_yield, 0)
  const avgYield = yieldPredictions.length > 0 ? totalYield / yieldPredictions.length : 0

  // Pagination logic
  const indexOfLastRecord = currentPage * recordsPerPage
  const indexOfFirstRecord = indexOfLastRecord - recordsPerPage
  const currentDetections = detections.slice(indexOfFirstRecord, indexOfLastRecord)
  const currentYieldPredictions = yieldPredictions.slice(indexOfFirstRecord, indexOfLastRecord)
  const totalPages = Math.ceil((activeTab === 'disease' ? detections.length : yieldPredictions.length) / recordsPerPage)

  const paginate = (pageNumber) => setCurrentPage(pageNumber)

  const handlePreview = (item) => {
    setPreviewData(item)
    setShowPreviewModal(true)
  }

  const handleDownloadPDF = async () => {
    try {
      const pdf = new jsPDF('p', 'mm', 'a4')
      const pageWidth = pdf.internal.pageSize.getWidth()
      const pageHeight = pdf.internal.pageSize.getHeight()
      const margin = 20
      let yPosition = margin

      // Helper function to add page if needed
      const checkPageBreak = (requiredSpace) => {
        if (yPosition + requiredSpace > pageHeight - margin) {
          pdf.addPage()
          yPosition = margin
        }
      }

      // Header
      pdf.setFontSize(24)
      pdf.setFont('helvetica', 'bold')
      pdf.setTextColor(51, 51, 51)
      pdf.text('PITAYA FARM REPORT', margin, yPosition)
      yPosition += 10

      pdf.setFontSize(10)
      pdf.setFont('helvetica', 'normal')
      pdf.setTextColor(128, 128, 128)
      pdf.text(`Generated: ${new Date().toLocaleDateString()}`, margin, yPosition)
      pdf.text(`Report Type: ${activeTab === 'disease' ? 'Disease Analysis' : 'Yield Analysis'}`, margin, yPosition + 5)
      yPosition += 15

      // Divider line
      pdf.setDrawColor(200, 200, 200)
      pdf.setLineWidth(0.5)
      pdf.line(margin, yPosition, pageWidth - margin, yPosition)
      yPosition += 10

      // Summary Section
      pdf.setFontSize(14)
      pdf.setFont('helvetica', 'bold')
      pdf.setTextColor(51, 51, 51)
      pdf.text('SUMMARY', margin, yPosition)
      yPosition += 8

      pdf.setFontSize(10)
      pdf.setFont('helvetica', 'normal')
      pdf.setTextColor(51, 51, 51)

      if (activeTab === 'disease') {
        const summaryData = [
          ['Total Detections', detections.length.toString()],
          ['Disease Types', Object.keys(diseaseStats).length.toString()],
          ['High Severity', (severityStats.high || 0).toString()]
        ]
        
        summaryData.forEach(([label, value]) => {
          pdf.text(`${label}:`, margin, yPosition)
          pdf.text(value, pageWidth - margin - 20, yPosition, { align: 'right' })
          yPosition += 6
        })
      } else {
        const summaryData = [
          ['Total Predictions', yieldPredictions.length.toString()],
          ['Total Fruits', Math.round(totalYield).toLocaleString()],
          ['Average Yield', avgYield.toFixed(1)]
        ]
        
        summaryData.forEach(([label, value]) => {
          pdf.text(`${label}:`, margin, yPosition)
          pdf.text(value, pageWidth - margin - 20, yPosition, { align: 'right' })
          yPosition += 6
        })
      }
      yPosition += 10

      // Divider line
      pdf.setDrawColor(200, 200, 200)
      pdf.line(margin, yPosition, pageWidth - margin, yPosition)
      yPosition += 10

      // Charts/Statistics Section
      checkPageBreak(30)
      pdf.setFontSize(14)
      pdf.setFont('helvetica', 'bold')
      pdf.setTextColor(51, 51, 51)
      pdf.text('STATISTICS', margin, yPosition)
      yPosition += 8

      pdf.setFontSize(10)
      pdf.setFont('helvetica', 'normal')
      pdf.setTextColor(51, 51, 51)

      if (activeTab === 'disease') {
        // Disease Distribution
        yPosition += 5
        pdf.setFont('helvetica', 'bold')
        pdf.text('Disease Distribution', margin, yPosition)
        yPosition += 6
        pdf.setFont('helvetica', 'normal')
        
        diseaseChartData.slice(0, 5).forEach((item, index) => {
          checkPageBreak(6)
          const percentage = ((item.value / detections.length) * 100).toFixed(1)
          pdf.text(`${item.name}:`, margin, yPosition)
          pdf.text(`${item.value} (${percentage}%)`, pageWidth - margin - 20, yPosition, { align: 'right' })
          yPosition += 6
        })

        // Severity Distribution
        checkPageBreak(20)
        yPosition += 5
        pdf.setFont('helvetica', 'bold')
        pdf.text('Severity Distribution', margin, yPosition)
        yPosition += 6
        pdf.setFont('helvetica', 'normal')
        
        severityChartData.forEach((item) => {
          checkPageBreak(6)
          pdf.text(`${item.name}:`, margin, yPosition)
          pdf.text(item.value.toString(), pageWidth - margin - 20, yPosition, { align: 'right' })
          yPosition += 6
        })
      } else {
        // Yield by Location
        yPosition += 5
        pdf.setFont('helvetica', 'bold')
        pdf.text('Yield by Location', margin, yPosition)
        yPosition += 6
        pdf.setFont('helvetica', 'normal')
        
        yieldByLocationData.slice(0, 5).forEach((item) => {
          checkPageBreak(6)
          pdf.text(`${item.name}:`, margin, yPosition)
          pdf.text(`${item.value.toLocaleString()} fruits`, pageWidth - margin - 20, yPosition, { align: 'right' })
          yPosition += 6
        })

        // Yield by Season
        checkPageBreak(20)
        yPosition += 5
        pdf.setFont('helvetica', 'bold')
        pdf.text('Yield by Season', margin, yPosition)
        yPosition += 6
        pdf.setFont('helvetica', 'normal')
        
        yieldBySeasonData.forEach((item) => {
          checkPageBreak(6)
          pdf.text(`${item.name}:`, margin, yPosition)
          pdf.text(`${item.value.toLocaleString()} fruits`, pageWidth - margin - 20, yPosition, { align: 'right' })
          yPosition += 6
        })
      }
      yPosition += 10

      // Divider line
      pdf.setDrawColor(200, 200, 200)
      pdf.line(margin, yPosition, pageWidth - margin, yPosition)
      yPosition += 10

      // Data Table Section
      checkPageBreak(30)
      pdf.setFontSize(14)
      pdf.setFont('helvetica', 'bold')
      pdf.setTextColor(51, 51, 51)
      pdf.text(activeTab === 'disease' ? 'DETECTION RECORDS' : 'PREDICTION RECORDS', margin, yPosition)
      yPosition += 8

      // Table headers
      const tableData = (activeTab === 'disease' ? detections : yieldPredictions).slice(0, 20)
      const headers = activeTab === 'disease' 
        ? ['Date', 'Disease', 'Severity', 'Confidence']
        : ['Date', 'Yield', 'Season', 'Location']
      
      const colWidths = activeTab === 'disease'
        ? [40, 50, 30, 30]
        : [40, 40, 30, 40]

      // Draw header row
      pdf.setFillColor(245, 245, 245)
      pdf.rect(margin, yPosition - 5, pageWidth - (margin * 2), 8, 'F')
      pdf.setFont('helvetica', 'bold')
      pdf.setFontSize(9)
      pdf.setTextColor(51, 51, 51)
      
      let xPos = margin
      headers.forEach((header, index) => {
        pdf.text(header, xPos, yPosition)
        xPos += colWidths[index]
      })
      yPosition += 8

      // Draw data rows
      pdf.setFont('helvetica', 'normal')
      pdf.setFontSize(8)
      pdf.setTextColor(68, 68, 68)
      
      tableData.forEach((item) => {
        checkPageBreak(8)
        xPos = margin
        
        if (activeTab === 'disease') {
          pdf.text(new Date(item.DateTime).toLocaleDateString(), xPos, yPosition)
          xPos += colWidths[0]
          pdf.text(item.DiseaseType.substring(0, 20), xPos, yPosition)
          xPos += colWidths[1]
          pdf.text(item.Severity?.toUpperCase(), xPos, yPosition)
          xPos += colWidths[2]
          pdf.text(`${Number(item.Confidence).toFixed(1)}%`, xPos, yPosition)
        } else {
          pdf.text(new Date(item.prediction_date).toLocaleDateString(), xPos, yPosition)
          xPos += colWidths[0]
          pdf.text(Math.round(item.predicted_yield).toLocaleString(), xPos, yPosition)
          xPos += colWidths[1]
          pdf.text((item.season || 'N/A').substring(0, 10), xPos, yPosition)
          xPos += colWidths[2]
          pdf.text((item.location || 'N/A').substring(0, 15), xPos, yPosition)
        }
        
        yPosition += 6
        
        // Row divider
        pdf.setDrawColor(240, 240, 240)
        pdf.line(margin, yPosition - 3, pageWidth - margin, yPosition - 3)
      })

      // Footer
      const totalPages = pdf.internal.getNumberOfPages()
      for (let i = 1; i <= totalPages; i++) {
        pdf.setPage(i)
        pdf.setFontSize(8)
        pdf.setFont('helvetica', 'normal')
        pdf.setTextColor(153, 153, 153)
        pdf.text(`Page ${i} of ${totalPages}`, pageWidth / 2, pageHeight - 10, { align: 'center' })
        pdf.text('Pitaya Farm Management System', margin, pageHeight - 10)
        pdf.text(`Generated on ${new Date().toLocaleDateString()}`, pageWidth - margin - 20, pageHeight - 10, { align: 'right' })
      }

      pdf.save(`pitaya-report-${activeTab}-${new Date().toISOString().split('T')[0]}.pdf`)
    } catch (error) {
      console.error('Failed to generate PDF:', error)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-green-600"></div>
      </div>
    )
  }

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <motion.div
        variants={container}
        initial="hidden"
        animate="show"
        className="space-y-6"
      >
        {/* Header */}
        <motion.div variants={item} className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white">Reports</h2>
            <p className="text-sm text-gray-500 dark:text-gray-400">Stem Disease & Yield Analysis</p>
          </div>
          <button
            onClick={() => setShowPreviewModal(true)}
            className="flex items-center gap-2 px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700 transition-colors"
          >
            <Download className="w-4 h-4" />
            Download PDF
          </button>
        </motion.div>

        {/* Tabs */}
        <motion.div variants={item} className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm">
          <div className="flex border-b border-gray-200 dark:border-gray-700">
            <button
              onClick={() => setActiveTab('disease')}
              className={`flex items-center gap-2 px-6 py-4 font-medium transition-colors ${
                activeTab === 'disease'
                  ? 'text-orange-600 dark:text-orange-400 border-b-2 border-orange-600'
                  : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
              }`}
            >
              <Leaf className="w-4 h-4" />
              Disease Reports
            </button>
            <button
              onClick={() => setActiveTab('yield')}
              className={`flex items-center gap-2 px-6 py-4 font-medium transition-colors ${
                activeTab === 'yield'
                  ? 'text-orange-600 dark:text-orange-400 border-b-2 border-orange-600'
                  : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
              }`}
            >
              <Apple className="w-4 h-4" />
              Yield Reports
            </button>
          </div>
        </motion.div>

        {/* Report Content - Wrapped for PDF */}
        <div ref={reportRef} className="space-y-6">

        {/* Disease Reports */}
        {activeTab === 'disease' && (
          <motion.div variants={item} className="space-y-6">
            {/* Summary Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700 shadow-sm">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-500 dark:text-gray-400">Total Detections</p>
                    <p className="text-2xl font-bold text-gray-900 dark:text-white mt-1">
                      {detections.length}
                    </p>
                  </div>
                  <div className="bg-red-100 dark:bg-red-900/20 p-3 rounded-lg">
                    <AlertTriangle className="w-6 h-6 text-red-600 dark:text-red-400" />
                  </div>
                </div>
              </div>
              <div className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700 shadow-sm">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-500 dark:text-gray-400">Disease Types</p>
                    <p className="text-2xl font-bold text-gray-900 dark:text-white mt-1">
                      {Object.keys(diseaseStats).length}
                    </p>
                  </div>
                  <div className="bg-blue-100 dark:bg-blue-900/20 p-3 rounded-lg">
                    <Leaf className="w-6 h-6 text-blue-600 dark:text-blue-400" />
                  </div>
                </div>
              </div>
              <div className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700 shadow-sm">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-500 dark:text-gray-400">High Severity</p>
                    <p className="text-2xl font-bold text-gray-900 dark:text-white mt-1">
                      {severityStats.high || 0}
                    </p>
                  </div>
                  <div className="bg-orange-100 dark:bg-orange-900/20 p-3 rounded-lg">
                    <TrendingUp className="w-6 h-6 text-orange-600 dark:text-orange-400" />
                  </div>
                </div>
              </div>
            </div>

            {/* Charts */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Disease Distribution */}
              <div className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700 shadow-sm">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
                  <PieChart className="w-5 h-5" />
                  Disease Distribution
                </h3>
                <ResponsiveContainer width="100%" height={300}>
                  <RechartsPieChart>
                    <Pie
                      data={diseaseChartData.slice(0, 5)}
                      cx="50%"
                      cy="50%"
                      labelLine={false}
                      label={({ name, percent }) => percent > 5 ? `${name} ${(percent * 100).toFixed(0)}%` : ''}
                      outerRadius={80}
                      fill="#8884d8"
                      dataKey="value"
                    >
                      {diseaseChartData.slice(0, 5).map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={DISEASE_COLORS[index % DISEASE_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip />
                    <Legend />
                  </RechartsPieChart>
                </ResponsiveContainer>
              </div>

              {/* Severity Distribution */}
              <div className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700 shadow-sm">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
                  <BarChart3 className="w-5 h-5" />
                  Severity Distribution
                </h3>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={severityChartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="value" fill="#FF6384" radius={[8, 8, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Recent Detections Table */}
            <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm overflow-hidden">
              <div className="p-6 border-b border-gray-200 dark:border-gray-700">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Recent Detections</h3>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50 dark:bg-gray-700">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Date</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Disease</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Severity</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Confidence</th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                    {currentDetections.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="px-6 py-12 text-center text-gray-500 dark:text-gray-400">
                          No disease detections found
                        </td>
                      </tr>
                    ) : (
                      currentDetections.map((detection) => (
                        <tr key={detection.DetectionID} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                            {new Date(detection.DateTime).toLocaleDateString()}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-white">
                            {detection.DiseaseType}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                              detection.Severity === 'high' ? 'bg-red-100 dark:bg-red-900/20 text-red-800 dark:text-red-400' :
                              detection.Severity === 'medium' ? 'bg-yellow-100 dark:bg-yellow-900/20 text-yellow-800 dark:text-yellow-400' :
                              'bg-green-100 dark:bg-green-900/20 text-green-800 dark:text-green-400'
                            }`}>
                              {detection.Severity?.toUpperCase()}
                            </span>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-white">
                            {Number(detection.Confidence).toFixed(1)}%
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-right">
                            <button
                              onClick={() => handlePreview(detection)}
                              className="p-2 text-orange-600 hover:text-orange-900 dark:text-orange-400 dark:hover:text-orange-300 transition-colors"
                              title="Preview"
                            >
                              <Eye className="w-4 h-4" />
                            </button>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex items-center justify-between px-6 py-4 border-t border-gray-200 dark:border-gray-700">
                  <div className="text-sm text-gray-500 dark:text-gray-400">
                    Showing {indexOfFirstRecord + 1} to {Math.min(indexOfLastRecord, detections.length)} of {detections.length} entries
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => paginate(currentPage - 1)}
                      disabled={currentPage === 1}
                      className="px-3 py-1 rounded border border-gray-300 dark:border-gray-600 text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-100 dark:hover:bg-gray-700 dark:text-white"
                    >
                      Previous
                    </button>
                    {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => (
                      <button
                        key={page}
                        onClick={() => paginate(page)}
                        className={`px-3 py-1 rounded border text-sm ${
                          currentPage === page
                            ? 'bg-orange-600 text-white border-orange-600'
                            : 'border-gray-300 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700 dark:text-white'
                        }`}
                      >
                        {page}
                      </button>
                    ))}
                    <button
                      onClick={() => paginate(currentPage + 1)}
                      disabled={currentPage === totalPages}
                      className="px-3 py-1 rounded border border-gray-300 dark:border-gray-600 text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-100 dark:hover:bg-gray-700 dark:text-white"
                    >
                      Next
                    </button>
                  </div>
                </div>
              )}
            </div>
          </motion.div>
        )}

        {/* Yield Reports */}
        {activeTab === 'yield' && (
          <motion.div variants={item} className="space-y-6">
            {/* Summary Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700 shadow-sm">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-500 dark:text-gray-400">Total Predictions</p>
                    <p className="text-2xl font-bold text-gray-900 dark:text-white mt-1">
                      {yieldPredictions.length}
                    </p>
                  </div>
                  <div className="bg-green-100 dark:bg-green-900/20 p-3 rounded-lg">
                    <Apple className="w-6 h-6 text-green-600 dark:text-green-400" />
                  </div>
                </div>
              </div>
              <div className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700 shadow-sm">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-500 dark:text-gray-400">Total Fruits</p>
                    <p className="text-2xl font-bold text-gray-900 dark:text-white mt-1">
                      {Math.round(totalYield).toLocaleString()}
                    </p>
                  </div>
                  <div className="bg-blue-100 dark:bg-blue-900/20 p-3 rounded-lg">
                    <TrendingUp className="w-6 h-6 text-blue-600 dark:text-blue-400" />
                  </div>
                </div>
              </div>
              <div className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700 shadow-sm">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-500 dark:text-gray-400">Avg Yield</p>
                    <p className="text-2xl font-bold text-gray-900 dark:text-white mt-1">
                      {avgYield.toFixed(1)}
                    </p>
                  </div>
                  <div className="bg-purple-100 dark:bg-purple-900/20 p-3 rounded-lg">
                    <BarChart3 className="w-6 h-6 text-purple-600 dark:text-purple-400" />
                  </div>
                </div>
              </div>
            </div>

            {/* Charts */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Yield by Location */}
              <div className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700 shadow-sm">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
                  <BarChart3 className="w-5 h-5" />
                  Yield by Location
                </h3>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={yieldByLocationData.slice(0, 5)}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="value" fill="#4BC0C0" radius={[8, 8, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>

              {/* Yield by Season */}
              <div className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700 shadow-sm">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
                  <Calendar className="w-5 h-5" />
                  Yield by Season
                </h3>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={yieldBySeasonData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="value" fill="#9966FF" radius={[8, 8, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Recent Predictions Table */}
            <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm overflow-hidden">
              <div className="p-6 border-b border-gray-200 dark:border-gray-700">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Recent Predictions</h3>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50 dark:bg-gray-700">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Date</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Predicted Yield</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Season</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Location</th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                    {currentYieldPredictions.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="px-6 py-12 text-center text-gray-500 dark:text-gray-400">
                          No yield predictions found
                        </td>
                      </tr>
                    ) : (
                      currentYieldPredictions.map((prediction) => (
                        <tr key={prediction.id} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                            {new Date(prediction.prediction_date).toLocaleDateString()}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-white">
                            {Math.round(prediction.predicted_yield).toLocaleString()}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                            {prediction.season || 'N/A'}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                            {prediction.location || 'N/A'}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-right">
                            <button
                              onClick={() => handlePreview(prediction)}
                              className="p-2 text-orange-600 hover:text-orange-900 dark:text-orange-400 dark:hover:text-orange-300 transition-colors"
                              title="Preview"
                            >
                              <Eye className="w-4 h-4" />
                            </button>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex items-center justify-between px-6 py-4 border-t border-gray-200 dark:border-gray-700">
                  <div className="text-sm text-gray-500 dark:text-gray-400">
                    Showing {indexOfFirstRecord + 1} to {Math.min(indexOfLastRecord, yieldPredictions.length)} of {yieldPredictions.length} entries
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => paginate(currentPage - 1)}
                      disabled={currentPage === 1}
                      className="px-3 py-1 rounded border border-gray-300 dark:border-gray-600 text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-100 dark:hover:bg-gray-700 dark:text-white"
                    >
                      Previous
                    </button>
                    {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => (
                      <button
                        key={page}
                        onClick={() => paginate(page)}
                        className={`px-3 py-1 rounded border text-sm ${
                          currentPage === page
                            ? 'bg-orange-600 text-white border-orange-600'
                            : 'border-gray-300 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700 dark:text-white'
                        }`}
                      >
                        {page}
                      </button>
                    ))}
                    <button
                      onClick={() => paginate(currentPage + 1)}
                      disabled={currentPage === totalPages}
                      className="px-3 py-1 rounded border border-gray-300 dark:border-gray-600 text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-100 dark:hover:bg-gray-700 dark:text-white"
                    >
                      Next
                    </button>
                  </div>
                </div>
              )}
            </div>
          </motion.div>
        )}
        </div>
      </motion.div>

      {/* Preview Modal */}
      {showPreviewModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl w-full max-w-4xl max-h-[90vh] overflow-y-auto"
          >
            <div className="sticky top-0 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 p-6 flex items-center justify-between">
              <h2 className="text-xl font-bold text-gray-900 dark:text-white">
                Report Preview - {activeTab === 'disease' ? 'Disease Analysis' : 'Yield Analysis'}
              </h2>
              <button
                onClick={() => {
                  setShowPreviewModal(false)
                  setPreviewData(null)
                }}
                className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
              >
                <X className="w-5 h-5 text-gray-500 dark:text-gray-400" />
              </button>
            </div>

            <div className="p-6 space-y-6">
              {/* Summary Cards */}
              {activeTab === 'disease' ? (
                <div className="grid grid-cols-3 gap-4">
                  <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
                    <p className="text-sm text-gray-500 dark:text-gray-400">Total Detections</p>
                    <p className="text-2xl font-bold text-gray-900 dark:text-white">{detections.length}</p>
                  </div>
                  <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
                    <p className="text-sm text-gray-500 dark:text-gray-400">Disease Types</p>
                    <p className="text-2xl font-bold text-gray-900 dark:text-white">{Object.keys(diseaseStats).length}</p>
                  </div>
                  <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
                    <p className="text-sm text-gray-500 dark:text-gray-400">High Severity</p>
                    <p className="text-2xl font-bold text-gray-900 dark:text-white">{severityStats.high || 0}</p>
                  </div>
                </div>
              ) : (
                <div className="grid grid-cols-3 gap-4">
                  <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
                    <p className="text-sm text-gray-500 dark:text-gray-400">Total Predictions</p>
                    <p className="text-2xl font-bold text-gray-900 dark:text-white">{yieldPredictions.length}</p>
                  </div>
                  <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
                    <p className="text-sm text-gray-500 dark:text-gray-400">Total Fruits</p>
                    <p className="text-2xl font-bold text-gray-900 dark:text-white">{Math.round(totalYield).toLocaleString()}</p>
                  </div>
                  <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
                    <p className="text-sm text-gray-500 dark:text-gray-400">Avg Yield</p>
                    <p className="text-2xl font-bold text-gray-900 dark:text-white">{avgYield.toFixed(1)}</p>
                  </div>
                </div>
              )}

              {activeTab === 'disease' && previewData && (previewData.image_url || previewData.image_path) && (
                <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
                  <h3 className="font-semibold text-gray-900 dark:text-white mb-2">Uploaded Image</h3>
                  <img
                    src={previewData.image_url || previewData.image_path}
                    alt="Uploaded disease detection"
                    className="w-full max-h-[420px] object-contain rounded-lg border border-gray-200 dark:border-gray-600 bg-white"
                  />
                </div>
              )}

              {/* Charts Preview */}
              <div className="grid grid-cols-2 gap-4">
                {activeTab === 'disease' ? (
                  <>
                    <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
                      <h3 className="font-semibold text-gray-900 dark:text-white mb-2">Disease Distribution</h3>
                      <div className="space-y-2">
                        {diseaseChartData.slice(0, 5).map((item, index) => (
                          <div key={item.name} className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: DISEASE_COLORS[index % DISEASE_COLORS.length] }} />
                              <span className="text-sm text-gray-700 dark:text-gray-300">{item.name}</span>
                            </div>
                            <span className="text-sm font-medium text-gray-900 dark:text-white">{item.value}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                    <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
                      <h3 className="font-semibold text-gray-900 dark:text-white mb-2">Severity Distribution</h3>
                      <div className="space-y-2">
                        {severityChartData.map((item) => (
                          <div key={item.name} className="flex items-center justify-between">
                            <span className="text-sm text-gray-700 dark:text-gray-300">{item.name}</span>
                            <span className="text-sm font-medium text-gray-900 dark:text-white">{item.value}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </>
                ) : (
                  <>
                    <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
                      <h3 className="font-semibold text-gray-900 dark:text-white mb-2">Yield by Location</h3>
                      <div className="space-y-2">
                        {yieldByLocationData.slice(0, 5).map((item) => (
                          <div key={item.name} className="flex items-center justify-between">
                            <span className="text-sm text-gray-700 dark:text-gray-300">{item.name}</span>
                            <span className="text-sm font-medium text-gray-900 dark:text-white">{item.value}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                    <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
                      <h3 className="font-semibold text-gray-900 dark:text-white mb-2">Yield by Season</h3>
                      <div className="space-y-2">
                        {yieldBySeasonData.map((item) => (
                          <div key={item.name} className="flex items-center justify-between">
                            <span className="text-sm text-gray-700 dark:text-gray-300">{item.name}</span>
                            <span className="text-sm font-medium text-gray-900 dark:text-white">{item.value}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </>
                )}
              </div>

              {/* Data Table Preview */}
              <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
                <h3 className="font-semibold text-gray-900 dark:text-white mb-2">
                  {activeTab === 'disease' ? 'Recent Detections' : 'Recent Predictions'}
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-200 dark:border-gray-600">
                        {activeTab === 'disease' ? (
                          <>
                            <th className="text-left py-2 text-gray-500 dark:text-gray-400">Date</th>
                            <th className="text-left py-2 text-gray-500 dark:text-gray-400">Disease</th>
                            <th className="text-left py-2 text-gray-500 dark:text-gray-400">Severity</th>
                            <th className="text-left py-2 text-gray-500 dark:text-gray-400">Confidence</th>
                          </>
                        ) : (
                          <>
                            <th className="text-left py-2 text-gray-500 dark:text-gray-400">Date</th>
                            <th className="text-left py-2 text-gray-500 dark:text-gray-400">Yield</th>
                            <th className="text-left py-2 text-gray-500 dark:text-gray-400">Season</th>
                            <th className="text-left py-2 text-gray-500 dark:text-gray-400">Location</th>
                          </>
                        )}
                      </tr>
                    </thead>
                    <tbody>
                      {(activeTab === 'disease' ? detections : yieldPredictions).slice(0, 10).map((item, index) => (
                        <tr key={index} className="border-b border-gray-200 dark:border-gray-600">
                          {activeTab === 'disease' ? (
                            <>
                              <td className="py-2 text-gray-700 dark:text-gray-300">{new Date(item.DateTime).toLocaleDateString()}</td>
                              <td className="py-2 text-gray-900 dark:text-white">{item.DiseaseType}</td>
                              <td className="py-2">
                                <span className={`px-2 py-0.5 rounded text-xs ${
                                  item.Severity === 'high' ? 'bg-red-100 text-red-800' :
                                  item.Severity === 'medium' ? 'bg-yellow-100 text-yellow-800' :
                                  'bg-green-100 text-green-800'
                                }`}>
                                  {item.Severity?.toUpperCase()}
                                </span>
                              </td>
                              <td className="py-2 text-gray-900 dark:text-white">{Number(item.Confidence).toFixed(1)}%</td>
                            </>
                          ) : (
                            <>
                              <td className="py-2 text-gray-700 dark:text-gray-300">{new Date(item.prediction_date).toLocaleDateString()}</td>
                              <td className="py-2 text-gray-900 dark:text-white">{Math.round(item.predicted_yield).toLocaleString()}</td>
                              <td className="py-2 text-gray-700 dark:text-gray-300">{item.season || 'N/A'}</td>
                              <td className="py-2 text-gray-700 dark:text-gray-300">{item.location || 'N/A'}</td>
                            </>
                          )}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>

            <div className="sticky bottom-0 bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 p-6">
              <div className="flex gap-3">
                <button
                  onClick={() => {
                    setShowPreviewModal(false)
                    setPreviewData(null)
                  }}
                  className="flex-1 px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleDownloadPDF}
                  className="flex-1 px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700 transition-colors flex items-center justify-center gap-2"
                >
                  <Download className="w-4 h-4" />
                  Download PDF
                </button>
              </div>
            </div>
          </motion.div>
        </div>
      )}
    </div>
  )
}
