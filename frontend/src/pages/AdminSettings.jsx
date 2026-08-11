import { motion } from 'framer-motion'
import {
    Bell,
    CheckCircle,
    Globe,
    Info,
    Settings,
    XCircle
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { adminAuthApi, adminSettingsApi } from '../api/adminApi'

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

export default function AdminSettings() {
  const navigate = useNavigate()
  const [settings, setSettings] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [success, setSuccess] = useState('')
  const [error, setError] = useState('')
  const [activeCategory, setActiveCategory] = useState('general')
  const [confirmUpdate, setConfirmUpdate] = useState(null)

  useEffect(() => {
    if (!adminAuthApi.isAuthenticated()) {
      navigate('/login')
      return
    }
    loadSettings()
  }, [navigate])

  const loadSettings = async () => {
    try {
      const response = await adminSettingsApi.getSettings()
      if (response.success) {
        setSettings(response.data || [])
      }
    } catch (err) {
      console.error('Failed to load settings:', err)
      setError('Failed to load settings')
    } finally {
      setLoading(false)
    }
  }

  const handleUpdateSetting = async (settingKey, value) => {
    const setting = settings.find(s => s.SettingKey === settingKey)
    setConfirmUpdate({ key: settingKey, value, label: setting.SettingKey.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()) })
  }

  const confirmAndUpdate = async () => {
    if (!confirmUpdate) return
    
    try {
      setSaving(true)
      setError('')
      setSuccess('')

      const response = await adminSettingsApi.updateSetting(confirmUpdate.key, confirmUpdate.value)
      
      if (response.success) {
        setSuccess('Setting updated successfully')
        // Update local state
        setSettings(settings.map(s => 
          s.SettingKey === confirmUpdate.key ? { ...s, SettingValue: confirmUpdate.value } : s
        ))
      } else {
        setError(response.error || 'Failed to update setting')
      }
    } catch (err) {
      setError(err.message || 'Failed to update setting')
    } finally {
      setSaving(false)
      setConfirmUpdate(null)
    }
  }

  const categories = ['general', 'notifications']

  const filteredSettings = settings.filter(s => s.Category === activeCategory)

  const renderSettingInput = (setting) => {
    const value = setting.SettingValue

    if (setting.SettingType === 'boolean') {
      return (
        <div className="flex items-center">
          <button
            onClick={() => handleUpdateSetting(setting.SettingKey, value === 'true' ? 'false' : 'true')}
            disabled={saving}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
              value === 'true' ? 'bg-green-600' : 'bg-gray-300 dark:bg-gray-600'
            }`}
          >
            <span
              className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                value === 'true' ? 'translate-x-6' : 'translate-x-1'
              }`}
            />
          </button>
          <span className="ml-3 text-sm text-gray-600 dark:text-gray-400">
            {value === 'true' ? 'Enabled' : 'Disabled'}
          </span>
        </div>
      )
    }

    if (setting.SettingType === 'number') {
      return (
        <input
          type="number"
          value={value}
          onChange={(e) => handleUpdateSetting(setting.SettingKey, e.target.value)}
          disabled={saving}
          className="w-32 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-green-500 dark:bg-gray-700 dark:text-white"
        />
      )
    }

    return (
      <input
        type="text"
        value={value}
        onChange={(e) => handleUpdateSetting(setting.SettingKey, e.target.value)}
        disabled={saving}
        className="w-full max-w-md px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-green-500 dark:bg-gray-700 dark:text-white"
      />
    )
  }

  const getCategoryIcon = (category) => {
    switch (category) {
      case 'general':
        return <Globe className="w-5 h-5" />
      case 'notifications':
        return <Bell className="w-5 h-5" />
      default:
        return <Settings className="w-5 h-5" />
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
          {/* Success/Error Messages */}
          {success && (
            <motion.div variants={item} className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 text-green-700 dark:text-green-400 px-4 py-3 rounded-lg flex items-center gap-2">
              <CheckCircle className="w-5 h-5" />
              {success}
            </motion.div>
          )}
          {error && (
            <motion.div variants={item} className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400 px-4 py-3 rounded-lg flex items-center gap-2">
              <XCircle className="w-5 h-5" />
              {error}
            </motion.div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
            {/* Sidebar */}
            <motion.div variants={item} className="lg:col-span-1">
              <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm p-4">
                <h3 className="font-semibold text-gray-900 dark:text-white mb-4">Categories</h3>
                <nav className="space-y-2">
                  {categories.map((category) => (
                    <button
                      key={category}
                      onClick={() => setActiveCategory(category)}
                      className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                        activeCategory === category
                          ? 'bg-purple-100 dark:bg-purple-900/20 text-purple-700 dark:text-purple-400'
                          : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700'
                      }`}
                    >
                      {getCategoryIcon(category)}
                      <span className="capitalize">{category}</span>
                    </button>
                  ))}
                </nav>
              </div>
            </motion.div>

            {/* Settings Content */}
            <motion.div variants={item} className="lg:col-span-3">
              <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm">
                <div className="p-6 border-b border-gray-200 dark:border-gray-700">
                  <div className="flex items-center gap-3">
                    {getCategoryIcon(activeCategory)}
                    <h2 className="text-xl font-semibold text-gray-900 dark:text-white capitalize">
                      {activeCategory} Settings
                    </h2>
                  </div>
                </div>
                <div className="p-6 space-y-6">
                  {filteredSettings.length === 0 ? (
                    <div className="text-center py-12 text-gray-500 dark:text-gray-400">
                      <Info className="w-12 h-12 mx-auto mb-4 opacity-50" />
                      <p>No settings found for this category</p>
                    </div>
                  ) : (
                    filteredSettings.map((setting) => (
                      <div key={setting.SettingID} className="space-y-2">
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <label className="block text-sm font-medium text-gray-900 dark:text-white mb-1">
                              {setting.SettingKey.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                            </label>
                            {setting.Description && (
                              <p className="text-sm text-gray-500 dark:text-gray-400">
                                {setting.Description}
                              </p>
                            )}
                          </div>
                          <div className="ml-6">
                            {renderSettingInput(setting)}
                          </div>
                        </div>
                        <div className="border-b border-gray-200 dark:border-gray-700 pt-4"></div>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Info Box */}
              <motion.div variants={item} className="mt-6 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-xl p-4">
                <div className="flex items-start gap-3">
                  <Info className="w-5 h-5 text-blue-600 dark:text-blue-400 mt-0.5" />
                  <div className="flex-1">
                    <h4 className="font-medium text-blue-900 dark:text-blue-100 mb-1">
                      Settings Information
                    </h4>
                    <p className="text-sm text-blue-700 dark:text-blue-300">
                      Changes to site settings are applied immediately. Some settings may require a page refresh to take effect. 
                      Be careful when modifying critical system settings.
                    </p>
                  </div>
                </div>
              </motion.div>
            </motion.div>
          </div>
        </motion.div>

      {/* Settings Update Confirmation Modal */}
      {confirmUpdate && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 z-[60] animate-in fade-in duration-200">
          <div className="bg-white dark:bg-gray-800 rounded-2xl max-w-md w-full shadow-2xl animate-in slide-in-from-bottom-4 duration-300">
            <div className="p-6">
              {/* Header */}
              <div className="flex items-center gap-4 mb-6">
                <div className="w-14 h-14 rounded-full bg-gradient-to-br from-purple-100 to-purple-200 dark:from-purple-900/40 dark:to-purple-800/30 flex items-center justify-center shrink-0 shadow-sm">
                  <Settings className="w-7 h-7 text-purple-600 dark:text-purple-400" />
                </div>
                <div>
                  <h3 className="text-xl font-bold text-gray-900 dark:text-gray-100">Update Setting</h3>
                  <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">Are you sure you want to change this setting?</p>
                </div>
              </div>

              {/* Content Box */}
              <div className="bg-gradient-to-r from-gray-50 to-gray-100 dark:from-gray-700/50 dark:to-gray-800/50 rounded-xl px-5 py-4 mb-6 border border-gray-200 dark:border-gray-700">
                <div className="flex items-center gap-3">
                  <div className="w-2 h-2 rounded-full bg-purple-500"></div>
                  <p className="text-sm text-gray-700 dark:text-gray-300 font-medium">{confirmUpdate.label}</p>
                </div>
              </div>

              {/* Warning Message */}
              <div className="flex items-start gap-3 mb-6 p-4 bg-amber-50 dark:bg-amber-900/20 rounded-lg border border-amber-200 dark:border-amber-800">
                <AlertTriangle className="w-5 h-5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
                <p className="text-sm text-amber-800 dark:text-amber-200">
                  Changes to system settings are applied immediately and may affect the application behavior.
                </p>
              </div>

              {/* Action Buttons */}
              <div className="flex gap-3">
                <button
                  onClick={() => setConfirmUpdate(null)}
                  className="flex-1 px-4 py-3 rounded-xl border-2 border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700 transition-all duration-200 font-semibold"
                >
                  Cancel
                </button>
                <button
                  onClick={confirmAndUpdate}
                  className="flex-1 px-4 py-3 rounded-xl bg-gradient-to-r from-purple-600 to-purple-700 hover:from-purple-700 hover:to-purple-800 text-white font-semibold transition-all duration-200 flex items-center justify-center gap-2 shadow-lg shadow-purple-500/25"
                >
                  <Settings className="w-4 h-4" />
                  Update
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
