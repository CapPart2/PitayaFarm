import { motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from 'recharts'
import {
  deleteDetection,
  fetchAlerts,
  fetchDailyDetectionsChart,
  fetchDashboard,
  fetchDiseaseDistributionChart,
  fetchSeverityDistributionChart,
  markAlertRead
} from '../api/dashboard'
import { fetchYield } from '../api/yieldApi'
import LoadingSpinner from '../components/LoadingSpinner'

const container = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.06 },
  },
}

const item = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0 },
}

const kpiCards = [
  { key: 'totalDetections',  label: 'Total Disease Detections', icon: '🔍',  suffix: '' },
  { key: 'highSeverityCases', label: 'High Severity Cases',       icon: '⚠️', suffix: '' },
  { key: 'unreadAlerts',     label: 'Unread Alerts',              icon: '🔔', suffix: '' },
  { key: 'avgConfidence',    label: 'Avg. Disease Confidence',    icon: '🎯', suffix: '%' },
  { key: 'totalYieldRecords', label: 'Total Yield Records',       icon: '📊', suffix: '' },
  { key: 'totalFruits',      label: 'Total Fruits Detected',      icon: '🍈', suffix: '' },
]

const severityColors = { high: 'bg-red-100 text-red-800', medium: 'bg-amber-100 text-amber-800', low: 'bg-gray-100 text-gray-700' }

const professionalMetrics = [
  { key: 'totalDetections', label: 'Disease detections', detail: 'All recorded plant-health scans', action: 'View reports', target: '/app/reports', suffix: '', tone: 'border-pitaya-primary' },
  { key: 'highSeverityCases', label: 'High-priority cases', detail: 'Cases requiring immediate review', action: 'Review cases', target: '/app/reports', suffix: '', tone: 'border-red-500' },
  { key: 'unreadAlerts', label: 'Alerts to review', detail: 'Unread farm-health notifications', action: 'Open alerts', target: '/app/alerts', suffix: '', tone: 'border-amber-500' },
  { key: 'avgConfidence', label: 'Average scan confidence', detail: 'Confidence across disease detections', action: 'Run new scan', target: '/app/identify', suffix: '%', tone: 'border-sky-500' },
]

const CHART_COLORS = [
  '#FF6384', // Red - Anthracnose
  '#36A2EB', // Blue - Black Spot  
  '#FFCE56', // Yellow - Brown Spot
  '#4BC0C0', // Teal - Root Rot
  '#9966FF', // Purple - Soft Rot
  '#FF9F40', // Orange - Stem Rot
  '#FF6B6B', // Light Red - Stem Canker
  '#4ECDC4', // Light Teal - Twig Blight
  '#95E1D3'  // Mint Green - White Spot
]

export default function Dashboard() {
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [yieldEstimation, setYieldEstimation] = useState([])
  const [yieldFilter, setYieldFilter] = useState('monthly')
  const [chartData, setChartData] = useState({
    diseaseDistribution: null,
    dailyDetections: null,
    severityDistribution: null
  })
  const [dashboardAlerts, setDashboardAlerts] = useState([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [lastUpdated, setLastUpdated] = useState(null)

  const loadDashboardData = async () => {
    try {
      setLoading(true)
      
      // Load all data in parallel
      const [dashboardData, diseaseDist, dailyDet, severityDist, alertsData, yieldData] = await Promise.all([
        fetchDashboard(),
        fetchDiseaseDistributionChart(),
        fetchDailyDetectionsChart(),
        fetchSeverityDistributionChart(),
        fetchAlerts(true), // Get unread alerts
        fetchYield()
      ])
      
      setData(dashboardData || {})
      setYieldEstimation(yieldData?.yieldEstimation || [])
      setChartData({
        diseaseDistribution: diseaseDist || null,
        dailyDetections: dailyDet || null,
        severityDistribution: severityDist || null
      })
      setDashboardAlerts(alertsData || [])
      setLastUpdated(new Date())
    } catch (error) {
      console.error('Failed to load dashboard data:', error)
      // Set fallback data to prevent crashes
      setData({
        totalDetections: 0,
        highSeverityCases: 0,
        unreadAlerts: 0,
        avgConfidence: 0,
        totalYieldRecords: 0,
        totalFruits: 0
      })
      setDashboardAlerts([])
    } finally {
      setLoading(false)
    }
  }

  const refreshData = async () => {
    setRefreshing(true)
    await loadDashboardData()
    setRefreshing(false)
  }

  const handleMarkAlertRead = async (alertId) => {
    try {
      await markAlertRead(alertId)
      setDashboardAlerts(dashboardAlerts.filter(alert => 
        (alert.AlertID || alert.id) !== alertId
      ))
    } catch (error) {
      console.error('Failed to mark alert as read:', error)
    }
  }

  const handleDeleteDetection = async (detectionId) => {
    try {
      const result = await deleteDetection(detectionId)
      if (result.success) {
        // Refresh dashboard data to reflect the deletion
        await loadDashboardData()
      } else {
        console.error('Failed to delete detection:', result.error)
      }
    } catch (error) {
      console.error('Error deleting detection:', error)
    }
  }

  useEffect(() => {
    loadDashboardData()
    
    // Set up auto-refresh every 30 seconds
    const interval = setInterval(loadDashboardData, 30000)
    
    // Listen for real-time refresh events from other components
    const handleRealTimeRefresh = () => {
      console.log('📊 Dashboard received real-time refresh event')
      loadDashboardData()
    }
    
    window.addEventListener('pitaya:refresh', handleRealTimeRefresh)
    
    return () => {
      clearInterval(interval)
      window.removeEventListener('pitaya:refresh', handleRealTimeRefresh)
    }
  }, [])

  if (loading) return <LoadingSpinner className="min-h-[60vh]" />

  const { kpis, monthlyYield, diseaseOccurrence, diseaseDistribution, alerts: legacyAlerts } = data

  const aggregateYield = (records, mode) => {
    const grouped = {}
    records.forEach((item) => {
      const raw = String(item?.period || '')
      if (!raw) return
      let key = raw
      if (mode === 'monthly') {
        key = raw.slice(0, 7)
      } else if (mode === 'yearly') {
        key = raw.slice(0, 4)
      }
      grouped[key] = (grouped[key] || 0) + (item?.yieldKg || 0)
    })
    return Object.entries(grouped)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([period, fruits]) => ({ period, yieldKg: fruits }))
  }

  const yieldChartData = aggregateYield(yieldEstimation, yieldFilter)
  const needsAttention = (data?.highSeverityCases || 0) > 0 || (data?.unreadAlerts || 0) > 0

  return (
    <motion.div
      variants={container}
      initial="hidden"
      animate="show"
      className="max-w-7xl mx-auto space-y-8"
    >
      <div className="flex flex-col gap-5 border-b border-gray-200 pb-6 dark:border-gray-700 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-pitaya-primary dark:text-pitaya-mint">Farm intelligence</p>
          <h1 className="mt-2 font-display text-3xl font-bold tracking-tight text-gray-900 dark:text-gray-100">Farm health overview</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-gray-600 dark:text-gray-300">Monitor disease activity, prioritise urgent cases, and track yield records from one workspace.</p>
        </div>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <p className="text-xs text-gray-500 dark:text-gray-400">{lastUpdated ? `Last updated ${lastUpdated.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}` : 'Loading latest data'}</p>
          <button onClick={refreshData} disabled={refreshing} className="min-h-[44px] rounded-lg bg-pitaya-primary px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-pitaya-leaf disabled:cursor-not-allowed disabled:opacity-50">
            {refreshing ? 'Refreshing data…' : 'Refresh data'}
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <motion.div variants={item} className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {loading ? (
          // Loading skeleton
          professionalMetrics.map((card, index) => (
            <div key={index} className="rounded-xl border border-gray-200 border-t-4 border-t-gray-300 bg-white p-5 shadow-sm dark:border-gray-700 dark:border-t-gray-600 dark:bg-gray-800">
              <div className="animate-pulse">
                <div className="h-4 bg-gray-200 dark:bg-gray-600 rounded w-3/4 mb-3"></div>
                <div className="h-8 bg-gray-200 dark:bg-gray-600 rounded w-1/2"></div>
              </div>
            </div>
          ))
        ) : (
          professionalMetrics.map((card) => (
            <motion.div
              key={card.key}
              variants={item}
              whileHover={{ y: -2, boxShadow: '0 10px 25px -12px rgb(0 0 0 / 0.22)' }}
              whileTap={{ scale: 0.99 }}
              transition={{ duration: 0.2 }}
              onClick={() => navigate(card.target)}
              className={`cursor-pointer rounded-xl border border-gray-200 border-t-4 bg-white p-5 shadow-sm transition-shadow touch-manipulation dark:border-gray-700 dark:bg-gray-800 ${card.tone}`}
            >
              <div className="min-w-0">
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-gray-700 dark:text-gray-200">{card.label}</p>
                  <p className="mt-4 text-3xl font-bold tracking-tight text-gray-900 dark:text-gray-100">
                    {(data?.[card.key] ?? 0).toLocaleString()}{card.suffix}
                  </p>
                  <p className="mt-2 text-xs leading-5 text-gray-500 dark:text-gray-400">{card.detail}</p>
                  <p className="mt-4 text-xs font-semibold text-pitaya-primary dark:text-pitaya-mint">{card.action} <span aria-hidden>→</span></p>
                </div>
                <div className="hidden">
                  <span className="text-2xl sm:text-3xl">{card.icon}</span>
                  {(card.key === 'unreadAlerts' || card.key === 'highSeverityCases') && (
                    <span className="text-xs text-gray-400 dark:text-gray-500">→</span>
                  )}
                </div>
              </div>
            </motion.div>
          ))
        )}
      </motion.div>

      <motion.section variants={item} className={`grid overflow-hidden rounded-xl border shadow-sm lg:grid-cols-[1.4fr_1fr] ${needsAttention ? 'border-amber-200 dark:border-amber-900' : 'border-pitaya-leaf/30 dark:border-gray-700'}`}>
        <div className="bg-white p-5 dark:bg-gray-800 sm:p-6">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-gray-500 dark:text-gray-400">Current priority</p>
          <h2 className="mt-2 text-xl font-bold text-gray-900 dark:text-gray-100">{needsAttention ? 'Farm health needs review' : 'No urgent farm-health issues'}</h2>
          <p className="mt-2 text-sm leading-6 text-gray-600 dark:text-gray-300">{needsAttention ? `${data?.highSeverityCases || 0} high-priority case(s) and ${data?.unreadAlerts || 0} unread alert(s) need your attention.` : 'There are no high-priority cases or unread alerts at this time.'}</p>
        </div>
        <div className="border-t border-gray-200 bg-gray-50 p-5 dark:border-gray-700 dark:bg-gray-800/70 sm:p-6 lg:border-l lg:border-t-0">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-gray-500 dark:text-gray-400">Yield tracking</p>
          <div className="mt-3 flex items-end gap-8">
            <div><p className="text-2xl font-bold text-gray-900 dark:text-gray-100">{(data?.totalYieldRecords ?? 0).toLocaleString()}</p><p className="mt-1 text-xs text-gray-500 dark:text-gray-400">Yield records</p></div>
            <div><p className="text-2xl font-bold text-gray-900 dark:text-gray-100">{(data?.totalFruits ?? 0).toLocaleString()}</p><p className="mt-1 text-xs text-gray-500 dark:text-gray-400">Fruits logged</p></div>
          </div>
        </div>
      </motion.section>

      {/* Refresh Button */}
      <motion.div variants={item} className="hidden">
        <button
          onClick={refreshData}
          disabled={refreshing}
          className="px-4 py-2 bg-pitaya-primary text-white rounded-lg hover:bg-pitaya-leaf disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
        >
          {refreshing ? (
            <>
              <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
              Refreshing...
            </>
          ) : (
            <>
              🔄 Refresh Data
            </>
          )}
        </button>
      </motion.div>

      {/* Charts row 1: Yield Trend + Disease Distribution */}
      <motion.div variants={item} className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white dark:bg-gray-800 rounded-2xl p-6 border border-gray-100 dark:border-gray-700 shadow-card">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between mb-4">
            <div><p className="text-xs font-semibold uppercase tracking-[0.14em] text-gray-500 dark:text-gray-400">Yield</p><h2 className="mt-1 font-display font-semibold text-lg text-gray-900 dark:text-gray-100">Fruit detection trend</h2></div>
            <div className="inline-flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
              <span>View</span>
              <select
                value={yieldFilter}
                onChange={(e) => setYieldFilter(e.target.value)}
                className="px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-200"
              >
                <option value="monthly">Monthly</option>
                <option value="yearly">Yearly</option>
              </select>
            </div>
          </div>
          {yieldChartData.length === 0 ? (
            <div className="flex items-center justify-center h-[320px] text-gray-400 dark:text-gray-500 text-sm">
              No yield data yet. Run a yield detection to see results here.
            </div>
          ) : (
          <ResponsiveContainer width="100%" height={320}>
            <BarChart data={yieldChartData} margin={{ top: 10, right: 20, left: 5, bottom: 60 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" vertical={false} />
              <XAxis
                dataKey="period"
                tick={{ fontSize: 11 }}
                stroke="#6b7280"
                angle={-35}
                textAnchor="end"
                height={70}
                tickFormatter={(v) => {
                  if (typeof v !== 'string') return v
                  if (yieldFilter === 'yearly') return v
                  if (yieldFilter === 'monthly') {
                    try {
                      return new Date(`${v}-01`).toLocaleDateString(undefined, { month: 'short', year: 'numeric' })
                    } catch {
                      return v
                    }
                  }
                  try { return new Date(v).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) } catch { return v }
                }}
              />
              <YAxis
                tick={{ fontSize: 12 }}
                stroke="#6b7280"
                unit=" fruits"
                width={65}
              />
              <Tooltip
                contentStyle={{ borderRadius: 12, border: '1px solid #e5e7eb' }}
                formatter={(value) => [`${value} fruits`, 'Total Detected']}
                labelFormatter={(v) => {
                  if (yieldFilter === 'yearly') return v
                  if (yieldFilter === 'monthly') {
                    try {
                      return new Date(`${v}-01`).toLocaleDateString(undefined, { year: 'numeric', month: 'long' })
                    } catch {
                      return v
                    }
                  }
                  try { return new Date(v).toLocaleDateString(undefined, { weekday: 'short', year: 'numeric', month: 'short', day: 'numeric' }) } catch { return v }
                }}
                labelStyle={{ fontWeight: 600 }}
              />
              <Legend />
              <Bar
                dataKey="yieldKg"
                name="Fruits Detected"
                fill="#2f6a21"
                radius={[6, 6, 0, 0]}
                maxBarSize={60}
              />
            </BarChart>
          </ResponsiveContainer>
          )}
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-2xl p-6 border border-gray-100 dark:border-gray-700 shadow-card">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-gray-500 dark:text-gray-400">Plant health</p><h2 className="mt-1 font-display font-semibold text-lg text-gray-900 dark:text-gray-100 mb-4">Disease distribution</h2>
          <ResponsiveContainer width="100%" height={350}>
            <PieChart>
              <Pie
                data={(() => {
                  const rawData = chartData.diseaseDistribution?.labels?.map((label, index) => ({
                    name: label,
                    value: chartData.diseaseDistribution?.datasets?.[0]?.data?.[index] || 0
                  })) || [];
                  
                  // Sort by value and take top 5, group others
                  const sorted = rawData.sort((a, b) => b.value - a.value);
                  const top5 = sorted.slice(0, 5);
                  const others = sorted.slice(5);
                  
                  if (others.length > 0) {
                    const othersSum = others.reduce((sum, item) => sum + item.value, 0);
                    top5.push({ name: 'Others', value: othersSum });
                  }
                  
                  return top5.filter(item => item.value > 0);
                })()}
                cx="50%"
                cy="45%"
                labelLine={false}
                label={({ name, percent }) => percent > 5 ? `${name} ${(percent * 100).toFixed(0)}%` : ''}
                outerRadius={90}
                fill="#8884d8"
                dataKey="value"
                minAngle={10}
              >
                {(() => {
                  const data = (() => {
                    const rawData = chartData.diseaseDistribution?.labels?.map((label, index) => ({
                      name: label,
                      value: chartData.diseaseDistribution?.datasets?.[0]?.data?.[index] || 0
                    })) || [];
                    
                    const sorted = rawData.sort((a, b) => b.value - a.value);
                    const top5 = sorted.slice(0, 5);
                    const others = sorted.slice(5);
                    
                    if (others.length > 0) {
                      const othersSum = others.reduce((sum, item) => sum + item.value, 0);
                      top5.push({ name: 'Others', value: othersSum });
                    }
                    
                    return top5.filter(item => item.value > 0);
                  })();
                  
                  return data.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                  ));
                })()}
              </Pie>
              <Tooltip 
                formatter={(value) => [value, 'Cases']} 
                contentStyle={{ borderRadius: 8, border: '1px solid #e5e7eb' }}
              />
              <Legend 
                verticalAlign="bottom" 
                height={80}
                align="center"
                layout="horizontal"
                wrapperStyle={{ paddingTop: '20px' }}
                formatter={(value, entry) => (
                  <span style={{ color: entry.color, fontSize: '12px' }}>
                    {value.length > 12 ? `${value.substring(0, 12)}...` : value}
                  </span>
                )}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </motion.div>

      {/* Charts row 2: Daily Detections + Severity Distribution */}
      <motion.div variants={item} className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white dark:bg-gray-800 rounded-2xl p-6 border border-gray-100 dark:border-gray-700 shadow-card">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-gray-500 dark:text-gray-400">Activity</p><h2 className="mt-1 font-display font-semibold text-lg text-gray-900 dark:text-gray-100 mb-4">Daily disease detections</h2>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart 
              data={chartData.dailyDetections?.labels?.map((label, index) => ({
                date: label,
                count: chartData.dailyDetections?.datasets?.[0]?.data?.[index] || 0
              })) || []} 
              margin={{ top: 10, right: 30, left: 20, bottom: 60 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis 
                dataKey="date" 
                tick={{ fontSize: 11 }} 
                stroke="#6b7280"
                angle={-45}
                textAnchor="end"
                height={80}
              />
              <YAxis 
                tick={{ fontSize: 12 }} 
                stroke="#6b7280"
                label={{ value: 'Detections', angle: -90, position: 'insideLeft' }}
              />
              <Tooltip
                contentStyle={{ borderRadius: 12, border: '1px solid #e5e7eb' }}
                formatter={(value) => [value, 'Detections']}
                labelStyle={{ fontWeight: 600 }}
              />
              <Legend />
              <Bar 
                dataKey="count" 
                fill="#FF6384" 
                radius={[8, 8, 0, 0]}
                name="Disease Detections"
                animationDuration={1000}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-2xl p-6 border border-gray-100 dark:border-gray-700 shadow-card">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-gray-500 dark:text-gray-400">Risk profile</p><h2 className="mt-1 font-display font-semibold text-lg text-gray-900 dark:text-gray-100 mb-4">Severity distribution</h2>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={chartData.severityDistribution?.labels?.map((label, index) => ({
                  name: label,
                  value: chartData.severityDistribution?.datasets?.[0]?.data?.[index] || 0
                })) || []}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                outerRadius={90}
                fill="#8884d8"
                dataKey="value"
              >
                {chartData.severityDistribution?.labels?.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={['#FF6384', '#FFCE56', '#4BC0C0'][index]} />
                ))}
              </Pie>
              <Tooltip 
                formatter={(value) => [value, 'Cases']} 
                contentStyle={{ borderRadius: 8, border: '1px solid #e5e7eb' }}
              />
              <Legend 
                verticalAlign="bottom" 
                height={36}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </motion.div>

      {/* Alerts Section */}
      <motion.div variants={item} className="bg-white dark:bg-gray-800 rounded-2xl p-5 sm:p-6 border border-gray-100 dark:border-gray-700 shadow-card">
        <div className="mb-4 flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between"><div><p className="text-xs font-semibold uppercase tracking-[0.14em] text-gray-500 dark:text-gray-400">Notifications</p><h2 className="mt-1 font-display font-semibold text-lg text-gray-900 dark:text-gray-100">Recent alerts</h2></div><button type="button" onClick={() => navigate('/app/alerts')} className="text-left text-sm font-semibold text-pitaya-primary hover:underline dark:text-pitaya-mint">View all alerts</button></div>
        {dashboardAlerts.length === 0 ? (
          <p className="text-gray-500 dark:text-gray-400 text-center py-8">No new alerts</p>
        ) : (
          <div className="space-y-3">
            {dashboardAlerts.slice(0, 5).map((alert) => (
              <div key={alert.AlertID || alert.id} className="flex flex-col gap-2 rounded-lg bg-gray-50 p-3 dark:bg-gray-700 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0">
                  <div>
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                      (alert.Severity || alert.severity) === 'high' ? 'bg-red-100 dark:bg-red-900/20 text-red-800 dark:text-red-300' :
                      (alert.Severity || alert.severity) === 'medium' ? 'bg-yellow-100 dark:bg-yellow-900/20 text-yellow-800 dark:text-yellow-300' :
                      'bg-blue-100 dark:bg-blue-900/20 text-blue-800 dark:text-blue-300'
                    }`}>
                      {(alert.Severity || alert.severity)?.toUpperCase() || 'MEDIUM'}
                    </span>
                    <span className="ml-2 text-sm text-gray-600 dark:text-gray-300">
                      {alert.DiseaseType || alert.disease_name || 'Unknown Disease'}
                    </span>
                  </div>
                </div>
                <span className="shrink-0 text-xs text-gray-500 dark:text-gray-400">{alert.DateTime ? new Date(alert.DateTime).toLocaleString() : 'Unknown time'}</span>
              </div>
            ))}
          </div>
        )}
      </motion.div>
    </motion.div>
  )
}
