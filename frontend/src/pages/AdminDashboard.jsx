import { motion } from 'framer-motion'
import {
    Activity,
    AlertTriangle,
    Apple,
    Database,
    FileText,
    Leaf,
    Settings,
    Shield,
    TrendingUp,
    Users
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { adminAuthApi, adminDashboardApi } from '../api/adminApi'

const container = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.1 },
  },
}

const item = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0 },
}

export default function AdminDashboard() {
  const navigate = useNavigate()
  const [metrics, setMetrics] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!adminAuthApi.isAuthenticated()) {
      navigate('/login')
      return
    }

    loadMetrics()
  }, [navigate])

  const loadMetrics = async () => {
    try {
      const response = await adminDashboardApi.getMetrics()
      if (response.success) {
        setMetrics(response.data)
      }
    } catch (error) {
      console.error('Failed to load metrics:', error)
    } finally {
      setLoading(false)
    }
  }

  const metricCards = [
    {
      title: 'Total Users',
      value: metrics?.users?.total || 0,
      icon: Users,
      color: 'from-blue-500 to-blue-600',
      bgColor: 'bg-blue-50 dark:bg-blue-900/20',
      textColor: 'text-blue-600 dark:text-blue-400',
    },
    {
      title: 'Active Users',
      value: metrics?.users?.active || 0,
      icon: Activity,
      color: 'from-green-500 to-green-600',
      bgColor: 'bg-green-50 dark:bg-green-900/20',
      textColor: 'text-green-600 dark:text-green-400',
    },
    {
      title: 'Admin Users',
      value: metrics?.users?.admins || 0,
      icon: Shield,
      color: 'from-purple-500 to-purple-600',
      bgColor: 'bg-purple-50 dark:bg-purple-900/20',
      textColor: 'text-purple-600 dark:text-purple-400',
    },
    {
      title: 'Total Detections',
      value: metrics?.detections?.total || 0,
      icon: Leaf,
      color: 'from-red-500 to-red-600',
      bgColor: 'bg-red-50 dark:bg-red-900/20',
      textColor: 'text-red-600 dark:text-red-400',
    },
    {
      title: 'Weekly Detections',
      value: metrics?.detections?.weekly || 0,
      icon: TrendingUp,
      color: 'from-orange-500 to-orange-600',
      bgColor: 'bg-orange-50 dark:bg-orange-900/20',
      textColor: 'text-orange-600 dark:text-orange-400',
    },
    {
      title: 'Yield Predictions',
      value: metrics?.yield?.total_predictions || 0,
      icon: Apple,
      color: 'from-teal-500 to-teal-600',
      bgColor: 'bg-teal-50 dark:bg-teal-900/20',
      textColor: 'text-teal-600 dark:text-teal-400',
    },
    {
      title: 'Total Fruits',
      value: metrics?.yield?.total_fruits || 0,
      icon: Database,
      color: 'from-pink-500 to-pink-600',
      bgColor: 'bg-pink-50 dark:bg-pink-900/20',
      textColor: 'text-pink-600 dark:text-pink-400',
    },
    {
      title: 'Unread Alerts',
      value: metrics?.alerts?.unread || 0,
      icon: AlertTriangle,
      color: 'from-amber-500 to-amber-600',
      bgColor: 'bg-amber-50 dark:bg-amber-900/20',
      textColor: 'text-amber-600 dark:text-amber-400',
    },
  ]

  const quickActions = [
    {
      title: 'User Management',
      description: 'Manage system users and permissions',
      icon: Users,
      path: '/admin/users',
      color: 'bg-blue-500',
    },
    {
      title: 'User Logs',
      description: 'View system activity and audit logs',
      icon: FileText,
      path: '/admin/logs',
      color: 'bg-green-500',
    },
    {
      title: 'Site Settings',
      description: 'Configure system preferences',
      icon: Settings,
      path: '/admin/settings',
      color: 'bg-purple-500',
    },
    {
      title: 'Disease Reports',
      description: 'View stem disease detection reports',
      icon: Leaf,
      path: '/admin/reports',
      color: 'bg-red-500',
    },
  ]

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-green-600"></div>
      </div>
    )
  }

  return (
    <div className="max-w-7xl mx-auto">
        <motion.div
          variants={container}
          initial="hidden"
          animate="show"
          className="space-y-8"
        >
          {/* Metrics Grid */}
          <motion.div variants={item}>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
              System Overview
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {metricCards.map((card, index) => (
                <motion.div
                  key={card.title}
                  variants={item}
                  whileHover={{ y: -4, transition: { duration: 0.2 } }}
                  className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700 shadow-sm hover:shadow-md transition-shadow"
                >
                  <div className="flex items-center justify-between mb-4">
                    <div className={`p-3 rounded-lg ${card.bgColor}`}>
                      <card.icon className={`w-6 h-6 ${card.textColor}`} />
                    </div>
                  </div>
                  <p className="text-2xl font-bold text-gray-900 dark:text-white">
                    {card.value.toLocaleString()}
                  </p>
                  <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                    {card.title}
                  </p>
                </motion.div>
              ))}
            </div>
          </motion.div>

          {/* Quick Actions */}
          <motion.div variants={item}>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
              Quick Actions
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {quickActions.map((action) => (
                <motion.button
                  key={action.title}
                  variants={item}
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={() => navigate(action.path)}
                  className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700 shadow-sm hover:shadow-md transition-all text-left group"
                >
                  <div className={`p-3 rounded-lg ${action.color} mb-4 group-hover:opacity-90 transition-opacity`}>
                    <action.icon className="w-6 h-6 text-white" />
                  </div>
                  <h3 className="font-semibold text-gray-900 dark:text-white mb-1">
                    {action.title}
                  </h3>
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    {action.description}
                  </p>
                </motion.button>
              ))}
            </div>
          </motion.div>

          {/* Recent Activity Summary */}
          <motion.div variants={item} className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700 shadow-sm">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
              Weekly Activity
            </h2>
            <div className="flex items-center gap-4">
              <div className="flex-1">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-gray-500 dark:text-gray-400">
                    Activity Logs (Last 7 Days)
                  </span>
                  <span className="text-2xl font-bold text-gray-900 dark:text-white">
                    {metrics?.activity?.weekly_logs || 0}
                  </span>
                </div>
                <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                  <div
                    className="bg-gradient-to-r from-green-500 to-emerald-600 h-2 rounded-full"
                    style={{ width: '75%' }}
                  ></div>
                </div>
              </div>
              <Activity className="w-12 h-12 text-green-500" />
            </div>
          </motion.div>
        </motion.div>
    </div>
  )
}
