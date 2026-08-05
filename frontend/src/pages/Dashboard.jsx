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

  return (
    <motion.div
      variants={container}
      initial="hidden"
      animate="show"
      className="max-w-7xl mx-auto space-y-8"
    >
      <div>
        <h1 className="font-display font-bold text-2xl text-gray-900 dark:text-gray-100">Dashboard</h1>
        <p className="text-gray-600 dark:text-gray-300 mt-1">Overview of plant health and yield prediction</p>
      </div>

      {/* KPI Cards */}
      <motion.div variants={item} className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 sm:gap-4">
        {loading ? (
          // Loading skeleton
          kpiCards.map((card, index) => (
            <div key={index} className="bg-white dark:bg-gray-800 rounded-2xl p-5 border border-gray-100 dark:border-gray-700 shadow-card">
              <div className="animate-pulse">
                <div className="h-4 bg-gray-200 dark:bg-gray-600 rounded w-3/4 mb-3"></div>
                <div className="h-8 bg-gray-200 dark:bg-gray-600 rounded w-1/2"></div>
              </div>
            </div>
          ))
        ) : (
          kpiCards.map((card) => (
            <motion.div
              key={card.key}
              variants={item}
              whileHover={{ y: -4, boxShadow: '0 10px 25px -5px rgb(0 0 0 / 0.08)' }}
              whileTap={{ scale: 0.99 }}
              transition={{ duration: 0.2 }}
              onClick={() => {
                if (card.key === 'unreadAlerts') {
                  navigate('/app/alerts')
                } else if (card.key === 'highSeverityCases') {
                  navigate('/app/reports')
                } else if (card.key === 'totalYieldRecords' || card.key === 'totalFruits') {
                  navigate('/app/yield-report')
                }
              }}
              className={`bg-white dark:bg-gray-800 rounded-2xl p-4 sm:p-5 border border-gray-100 dark:border-gray-700 shadow-card transition-shadow touch-manipulation ${
                ['unreadAlerts', 'highSeverityCases', 'totalYieldRecords', 'totalFruits'].includes(card.key)
                  ? 'cursor-pointer hover:border-blue-300 dark:hover:border-blue-600' 
                  : ''
              }`}
            >
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0">
                  <p className="text-xs sm:text-sm font-medium text-gray-500 dark:text-gray-400 leading-tight">{card.label}</p>
                  <p className="mt-1 text-xl sm:text-2xl font-bold text-gray-900 dark:text-gray-100 truncate">
                    {(data?.[card.key] ?? 0).toLocaleString()}{card.suffix}
                  </p>
                </div>
                <div className="flex items-center gap-1">
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

      {/* Refresh Button */}
      <motion.div variants={item} className="flex justify-end">
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
            <h2 className="font-display font-semibold text-lg text-gray-900 dark:text-gray-100">Yield Total Fruit</h2>
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
          <h2 className="font-display font-semibold text-lg text-gray-900 dark:text-gray-100 mb-4">Disease Distribution</h2>
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
          <h2 className="font-display font-semibold text-lg text-gray-900 dark:text-gray-100 mb-4">Daily Disease Detections</h2>
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
          <h2 className="font-display font-semibold text-lg text-gray-900 dark:text-gray-100 mb-4">Severity Distribution</h2>
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
      <motion.div variants={item} className="bg-white dark:bg-gray-800 rounded-2xl p-6 border border-gray-100 dark:border-gray-700 shadow-card">
        <h2 className="font-display font-semibold text-lg text-gray-900 dark:text-gray-100 mb-4">Recent Alerts</h2>
        {dashboardAlerts.length === 0 ? (
          <p className="text-gray-500 dark:text-gray-400 text-center py-8">No new alerts</p>
        ) : (
          <div className="space-y-3">
            {dashboardAlerts.slice(0, 5).map((alert) => (
              <div key={alert.AlertID || alert.id} className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700 rounded-lg">
                <div className="flex items-center justify-between">
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
                  <span className="text-xs text-gray-500 dark:text-gray-400">
                    {alert.DateTime ? new Date(alert.DateTime).toLocaleString() : 'Unknown time'}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </motion.div>
    </motion.div>
  )
}
