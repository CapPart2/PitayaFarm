import { motion } from 'framer-motion'
import {
    Activity,
    Calendar,
    Download,
    Filter,
    Search,
    User
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { adminAuthApi, adminLogsApi } from '../api/adminApi'
import AdminPagination from '../components/AdminPagination'

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

export default function AdminLogs() {
  const navigate = useNavigate()
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState({
    action: '',
    user_id: '',
    start_date: '',
    end_date: '',
  })
  const [currentPage, setCurrentPage] = useState(1)
  const recordsPerPage = 10

  useEffect(() => {
    if (!adminAuthApi.isAuthenticated()) {
      navigate('/login')
      return
    }
    loadLogs()
  }, [navigate])

  useEffect(() => {
    setCurrentPage(1)
  }, [filters])

  const loadLogs = async () => {
    try {
      const response = await adminLogsApi.getLogs(filters)
      if (response.success) {
        setLogs(response.data || [])
      }
    } catch (error) {
      console.error('Failed to load logs:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleFilterChange = (e) => {
    setFilters({
      ...filters,
      [e.target.name]: e.target.value,
    })
  }

  const applyFilters = () => {
    setLoading(true)
    loadLogs()
  }

  const resetFilters = () => {
    setFilters({
      action: '',
      user_id: '',
      start_date: '',
      end_date: '',
    })
    setLoading(true)
    loadLogs()
  }

  const getActionBadgeColor = (action) => {
    const colors = {
      'LOGIN': 'bg-green-100 dark:bg-green-900/20 text-green-800 dark:text-green-400',
      'LOGOUT': 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-300',
      'CREATE_USER': 'bg-blue-100 dark:bg-blue-900/20 text-blue-800 dark:text-blue-400',
      'UPDATE_USER': 'bg-yellow-100 dark:bg-yellow-900/20 text-yellow-800 dark:text-yellow-400',
      'DELETE_USER': 'bg-red-100 dark:bg-red-900/20 text-red-800 dark:text-red-400',
      'UPDATE_SETTING': 'bg-purple-100 dark:bg-purple-900/20 text-purple-800 dark:text-purple-400',
      'DELETE_DETECTION': 'bg-orange-100 dark:bg-orange-900/20 text-orange-800 dark:text-orange-400',
      'DELETE_YIELD_PREDICTION': 'bg-pink-100 dark:bg-pink-900/20 text-pink-800 dark:text-pink-400',
    }
    return colors[action] || 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-300'
  }

  // Pagination logic
  const indexOfLastRecord = currentPage * recordsPerPage
  const indexOfFirstRecord = indexOfLastRecord - recordsPerPage
  const currentLogs = logs.slice(indexOfFirstRecord, indexOfLastRecord)
  const totalPages = Math.ceil(logs.length / recordsPerPage)

  const paginate = (pageNumber) => setCurrentPage(pageNumber)

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
          {/* Header with Export */}
          <motion.div variants={item} className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-2xl font-bold text-gray-900 dark:text-white">User Logs</h2>
              <p className="text-sm text-gray-500 dark:text-gray-400">View system activity and audit logs</p>
            </div>
            <button
              onClick={() => {
                const csvContent = [
                  ['Log ID', 'User', 'Action', 'Description', 'IP Address', 'Date'],
                  ...logs.map(log => [
                    log.LogID,
                    log.Username || 'N/A',
                    log.Action,
                    log.Description || '',
                    log.IPAddress || 'N/A',
                    log.CreatedAt
                  ])
                ].map(row => row.join(',')).join('\n')
                
                const blob = new Blob([csvContent], { type: 'text/csv' })
                const url = window.URL.createObjectURL(blob)
                const a = document.createElement('a')
                a.href = url
                a.download = `user_logs_${new Date().toISOString().split('T')[0]}.csv`
                a.click()
                window.URL.revokeObjectURL(url)
              }}
              className="flex min-h-[44px] w-full items-center justify-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors sm:w-auto"
            >
              <Download className="w-4 h-4" />
              Export CSV
            </button>
          </motion.div>

          {/* Filters */}
          <motion.div variants={item} className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700 shadow-sm">
            <div className="flex items-center gap-2 mb-4">
              <Filter className="w-5 h-5 text-gray-500" />
              <h3 className="font-semibold text-gray-900 dark:text-white">Filters</h3>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Action
                </label>
                <input
                  type="text"
                  name="action"
                  value={filters.action}
                  onChange={handleFilterChange}
                  placeholder="Search action..."
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-green-500 dark:bg-gray-700 dark:text-white"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  User ID
                </label>
                <input
                  type="text"
                  name="user_id"
                  value={filters.user_id}
                  onChange={handleFilterChange}
                  placeholder="Enter user ID..."
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-green-500 dark:bg-gray-700 dark:text-white"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Start Date
                </label>
                <input
                  type="date"
                  name="start_date"
                  value={filters.start_date}
                  onChange={handleFilterChange}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-green-500 dark:bg-gray-700 dark:text-white"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  End Date
                </label>
                <input
                  type="date"
                  name="end_date"
                  value={filters.end_date}
                  onChange={handleFilterChange}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-green-500 dark:bg-gray-700 dark:text-white"
                />
              </div>
            </div>
            <div className="flex gap-3 mt-4">
              <button
                onClick={applyFilters}
                className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
              >
                <Search className="w-4 h-4" />
                Apply Filters
              </button>
              <button
                onClick={resetFilters}
                className="px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
              >
                Reset
              </button>
            </div>
          </motion.div>

          {/* Logs Table */}
          <motion.div variants={item} className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm overflow-hidden">
            <div className="overflow-x-auto overscroll-x-contain" role="region" aria-label="Activity logs table" tabIndex="0">
              <table className="w-full min-w-[720px]">
                <thead className="bg-gray-50 dark:bg-gray-700">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      Date & Time
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      User
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      Action
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      Description
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      IP Address
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                  {currentLogs.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-6 py-12 text-center text-gray-500 dark:text-gray-400">
                        No logs found
                      </td>
                    </tr>
                  ) : (
                    currentLogs.map((log) => (
                      <tr key={log.LogID} className="hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors">
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="flex items-center text-sm text-gray-500 dark:text-gray-400">
                            <Calendar className="w-4 h-4 mr-2" />
                            {new Date(log.CreatedAt).toLocaleString()}
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="flex items-center text-sm text-gray-900 dark:text-white">
                            <User className="w-4 h-4 mr-2 text-gray-400" />
                            {log.Username || 'System'}
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getActionBadgeColor(log.Action)}`}>
                            <Activity className="w-3 h-3 mr-1" />
                            {log.Action}
                          </span>
                        </td>
                        <td className="px-6 py-4">
                          <div className="text-sm text-gray-900 dark:text-white max-w-xs truncate">
                            {log.Description || '-'}
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                          {log.IPAddress || 'N/A'}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
            <AdminPagination
              currentPage={currentPage}
              totalPages={totalPages}
              onPageChange={paginate}
              start={indexOfFirstRecord + 1}
              end={Math.min(indexOfLastRecord, logs.length)}
              total={logs.length}
              accent="green"
            />
          </motion.div>
        </motion.div>
    </div>
  )
}
