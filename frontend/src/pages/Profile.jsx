import { motion } from 'framer-motion'
import { AlertCircle, Bell, Camera, CheckCircle, Settings, User } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { getPitayaCurrentUser, getPitayaUserScopeHeaders, getScopedStorageKey } from '../api/userScope'

function getPitayaUser() {
  try {
    const raw = localStorage.getItem('pitayaUser')
    if (!raw) return null
    const parsed = JSON.parse(raw)
    const firstName = String(parsed?.firstName ?? '').trim()
    const lastName = String(parsed?.lastName ?? '').trim()
    if (!firstName && !lastName) return null
    return { firstName, lastName }
  } catch {
    return null
  }
}

function buildFullName(firstName, lastName) {
  return `${String(firstName ?? '').trim()} ${String(lastName ?? '').trim()}`.trim()
}

const DEFAULT_PROFILE = {
  fullName: '',
  email: '',
  farmName: '',
  location: '',
  bio: '',
}

export default function Profile() {
  const currentUser = getPitayaCurrentUser()
  const scopedProfileKey = getScopedStorageKey('userProfile', currentUser)
  const scopedPictureKey = getScopedStorageKey('profilePicture', currentUser)
  const scopedNotificationsKey = getScopedStorageKey('userNotifications', currentUser)
  const [activeTab, setActiveTab] = useState('profile')
  const [profilePicture, setProfilePicture] = useState(null)
  const [saveStatus, setSaveStatus] = useState({ type: '', message: '' })
  const fileInputRef = useRef(null)
  
  const [formData, setFormData] = useState({
    ...DEFAULT_PROFILE,
  })
  
  const [notifications, setNotifications] = useState({
    emailAlerts: true,
    pushNotifications: true,
    diseaseAlerts: true,
    yieldReports: false,
    systemUpdates: true
  })

  // Load saved data on component mount
  useEffect(() => {
    const loadProfileSettings = async () => {
      try {
        const response = await fetch('/api/user/preferences', {
          headers: {
            ...getPitayaUserScopeHeaders(),
          },
        })
        const data = await response.json()
        if (data?.success) {
          setFormData((prev) => ({
            ...prev,
            email: prev.email || data.data?.notification_email || '',
            farmName: data.data?.farm_name || prev.farmName,
          }))
        }
      } catch {
        // keep local fallback when the backend is unavailable
      }
    }

    const pitayaUser = getPitayaUser()
    const loggedInFullName = pitayaUser ? buildFullName(pitayaUser.firstName, pitayaUser.lastName) : ''
    const loggedInEmail = String(currentUser?.Email || '').trim()

    const savedProfile = localStorage.getItem(scopedProfileKey)
    const savedPicture = localStorage.getItem(scopedPictureKey)
    const savedNotifications = localStorage.getItem(scopedNotificationsKey)
    
    if (savedProfile) {
      const parsedProfile = JSON.parse(savedProfile)
      setFormData((prev) => ({
        ...prev,
        ...parsedProfile,
        farmName: parsedProfile?.farmName || parsedProfile?.phone || prev.farmName,
        fullName: loggedInFullName || parsedProfile?.fullName || prev.fullName,
        email: loggedInEmail || parsedProfile?.email || prev.email,
      }))
    } else if (loggedInFullName) {
      setFormData((prev) => ({
        ...prev,
        fullName: loggedInFullName,
        email: loggedInEmail || prev.email,
      }))
    } else if (loggedInEmail) {
      setFormData((prev) => ({
        ...prev,
        email: loggedInEmail,
      }))
    }

    loadProfileSettings()

    if (savedPicture) {
      setProfilePicture(savedPicture)
    }
    if (savedNotifications) {
      setNotifications(JSON.parse(savedNotifications))
    }
  }, [currentUser?.Email, scopedNotificationsKey, scopedPictureKey, scopedProfileKey])

  const handleInputChange = (e) => {
    const { name, value } = e.target
    setFormData(prev => ({
      ...prev,
      [name]: value
    }))
    // Clear save status when user starts typing
    setSaveStatus({ type: '', message: '' })
  }

  const handleNotificationChange = (key) => {
    const newNotifications = {
      ...notifications,
      [key]: !notifications[key]
    }
    setNotifications(newNotifications)
    
    // Save notifications to localStorage
    localStorage.setItem(scopedNotificationsKey, JSON.stringify(newNotifications))
    
    // Show success message
    setSaveStatus({ 
      type: 'success', 
      message: 'Notification preferences saved successfully!' 
    })
    
    // Clear message after 3 seconds
    setTimeout(() => setSaveStatus({ type: '', message: '' }), 3000)
  }

  const handleProfilePictureChange = (e) => {
    const file = e.target.files[0]
    if (file) {
      if (file.size > 5 * 1024 * 1024) {
        setSaveStatus({ 
          type: 'error', 
          message: 'Profile picture must be less than 5MB' 
        })
        setTimeout(() => setSaveStatus({ type: '', message: '' }), 3000)
        return
      }
      
      const reader = new FileReader()
      reader.onloadend = () => {
        const imageData = reader.result
        setProfilePicture(imageData)
        localStorage.setItem(scopedPictureKey, imageData)
        
        setSaveStatus({ 
          type: 'success', 
          message: 'Profile picture updated successfully!' 
        })
        setTimeout(() => setSaveStatus({ type: '', message: '' }), 3000)
      }
      reader.readAsDataURL(file)
    }
  }

  const handleProfileUpdate = async (e) => {
    e.preventDefault()
    
    // Validate required fields
    if (!formData.fullName.trim() || !formData.email.trim() || !formData.farmName.trim()) {
      setSaveStatus({ 
        type: 'error', 
        message: 'Name, email, and farm name are required fields' 
      })
      setTimeout(() => setSaveStatus({ type: '', message: '' }), 3000)
      return
    }
    
    // Validate email format
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    if (!emailRegex.test(formData.email)) {
      setSaveStatus({ 
        type: 'error', 
        message: 'Please enter a valid email address' 
      })
      setTimeout(() => setSaveStatus({ type: '', message: '' }), 3000)
      return
    }
    
    // Save to localStorage
    const profileData = {
      fullName: formData.fullName,
      email: formData.email,
      farmName: formData.farmName,
      location: formData.location,
      bio: formData.bio
    }
    
    localStorage.setItem(scopedProfileKey, JSON.stringify(profileData))

    // Also update pitayaUser firstName/lastName so the app won't overwrite
    // the displayed full name on reload (login info is used as authoritative)
    try {
      const raw = localStorage.getItem('pitayaUser')
      if (raw) {
        const pu = JSON.parse(raw)
        const parts = String(formData.fullName || '').trim().split(/\s+/)
        const first = parts.shift() || ''
        const last = parts.join(' ') || ''
        pu.firstName = first
        pu.lastName = last
        pu.Email = formData.email
        // keep existing Username/Role etc.
        localStorage.setItem('pitayaUser', JSON.stringify(pu))
      }
    } catch (e) {
      // non-fatal
      console.warn('Failed to update pitayaUser localStorage', e)
    }

    try {
      const response = await fetch('/api/user/preferences', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getPitayaUserScopeHeaders(),
        },
        body: JSON.stringify({
          preferred_language: 'en',
          notification_email: formData.email,
          farm_name: formData.farmName,
          email_notifications_enabled: true,
        }),
      })

      if (!response.ok) {
        throw new Error('Unable to save notification settings on the server')
      }
    } catch {
      setSaveStatus({
        type: 'error',
        message: 'Saved locally, but alert delivery settings could not be synced to the server.',
      })
      setTimeout(() => setSaveStatus({ type: '', message: '' }), 3000)
      return
    }
    
    setSaveStatus({ 
      type: 'success', 
      message: 'Alert delivery preferences saved successfully!' 
    })
    
    // Clear message after 3 seconds
    setTimeout(() => setSaveStatus({ type: '', message: '' }), 3000)
  }

  const tabs = [
    { id: 'profile', label: 'Profile Information', mobileLabel: 'Profile', icon: User },
    { id: 'notifications', label: 'Notifications', icon: Bell },
    { id: 'preferences', label: 'Preferences', icon: Settings }
  ]

  return (
    <div className="max-w-4xl mx-auto min-w-0">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden"
      >
        {/* Profile Header */}
        <div className="bg-gradient-to-r from-green-600 to-green-500 dark:from-green-700 dark:to-green-600 p-4 sm:p-6">
          <div className="flex flex-col items-center gap-3 text-center sm:flex-row sm:gap-4 sm:text-left">
            <div className="relative">
              {profilePicture ? (
                <img
                  src={profilePicture} 
                  alt="Profile" 
                  className="w-16 h-16 sm:w-20 sm:h-20 rounded-full object-cover border-2 border-white/30"
                />
              ) : (
                <div className="w-16 h-16 sm:w-20 sm:h-20 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center">
                  <User className="w-8 h-8 sm:w-10 sm:h-10 text-white" />
                </div>
              )}
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                onChange={handleProfilePictureChange}
                className="hidden"
                aria-label="Upload profile picture"
              />
              <button 
                onClick={() => fileInputRef.current?.click()}
                className="absolute bottom-0 right-0 w-6 h-6 bg-white dark:bg-gray-800 rounded-full flex items-center justify-center shadow-lg hover:scale-110 transition-transform"
                title="Change profile picture"
              >
                <Camera className="w-3 h-3 text-gray-600 dark:text-gray-300" />
              </button>
            </div>
            <div className="min-w-0 text-white">
              <h1 className="text-xl sm:text-2xl font-bold break-words">{formData.fullName}</h1>
              <p className="text-sm sm:text-base text-white/80 break-all sm:break-normal">{formData.email}</p>
              <p className="text-sm text-white/60 mt-1">{formData.farmName}</p>
            </div>
          </div>
        </div>

        {/* Save Status Messages */}
        {saveStatus.message && (
          <div className={`mx-4 sm:mx-6 mt-4 p-3 rounded-lg flex items-center gap-2 ${
            saveStatus.type === 'success' 
              ? 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400 border border-green-200 dark:border-green-800' 
              : 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400 border border-red-200 dark:border-red-800'
          }`}>
            {saveStatus.type === 'success' ? (
              <CheckCircle className="w-5 h-5" />
            ) : (
              <AlertCircle className="w-5 h-5" />
            )}
            <span className="text-sm font-medium">{saveStatus.message}</span>
          </div>
        )}

        {/* Tabs */}
        <div className="border-b border-gray-200 dark:border-gray-700">
          <nav className="grid grid-cols-3 px-1 sm:flex sm:space-x-8 sm:px-6" aria-label="Profile sections">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex min-w-0 justify-center py-3 px-1 border-b-2 font-medium text-xs sm:text-sm transition-colors ${
                  activeTab === tab.id
                    ? 'border-green-600 text-green-600 dark:text-green-400'
                    : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
                }`}
              >
                <div className="flex min-w-0 flex-col items-center gap-1 sm:flex-row sm:gap-2">
                  <tab.icon className="w-4 h-4 shrink-0" />
                  <span className="sm:hidden truncate">{tab.mobileLabel || tab.label}</span>
                  <span className="hidden sm:inline">{tab.label}</span>
                </div>
              </button>
            ))}
          </nav>
        </div>

        {/* Tab Content */}
        <div className="p-4 sm:p-6">
          {/* Profile Information Tab */}
          {activeTab === 'profile' && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.2 }}
            >
              <form onSubmit={handleProfileUpdate} className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Full Name
                    </label>
                    <input
                      type="text"
                      name="fullName"
                      value={formData.fullName}
                      onChange={handleInputChange}
                      className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-green-500 focus:border-transparent transition-colors"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Email Address
                    </label>
                    <input
                      type="email"
                      name="email"
                      value={formData.email}
                      onChange={handleInputChange}
                      className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-green-500 focus:border-transparent transition-colors"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Farm Name
                    </label>
                    <input
                      type="text"
                      name="farmName"
                      value={formData.farmName}
                      onChange={handleInputChange}
                      className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-green-500 focus:border-transparent transition-colors"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Location
                    </label>
                    <input
                      type="text"
                      name="location"
                      value={formData.location}
                      onChange={handleInputChange}
                      className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-green-500 focus:border-transparent transition-colors"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Bio
                  </label>
                  <textarea
                    name="bio"
                    value={formData.bio}
                    onChange={handleInputChange}
                    rows={4}
                    className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-green-500 focus:border-transparent transition-colors resize-none"
                  />
                </div>
                <div className="rounded-xl border border-green-200 dark:border-green-900/40 bg-green-50 dark:bg-green-900/10 p-4">
                  <p className="text-sm font-semibold text-green-900 dark:text-green-300">Alert delivery</p>
                  <p className="mt-1 text-sm text-green-800 dark:text-green-200/90">
                    High severity alerts will be sent to <span className="font-semibold">{formData.email}</span> for <span className="font-semibold">{formData.farmName}</span>.
                  </p>
                </div>
                <div className="flex justify-end">
                  <button
                    type="submit"
                    className="px-6 py-2 bg-green-600 hover:bg-green-700 text-white font-medium rounded-lg transition-colors"
                  >
                    Save Changes
                  </button>
                </div>
              </form>
            </motion.div>
          )}

          {/* Notifications Tab */}
          {activeTab === 'notifications' && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.2 }}
            >
              <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-6">Notification Preferences</h3>
              <div className="space-y-4">
                {Object.entries({
                  emailAlerts: { label: 'Email Alerts', description: 'Receive email notifications about disease detections' },
                  pushNotifications: { label: 'Push Notifications', description: 'Get browser notifications for important updates' },
                  diseaseAlerts: { label: 'Disease Alerts', description: 'Immediate alerts when diseases are detected' },
                  yieldReports: { label: 'Yield Reports', description: 'Weekly yield prediction reports' },
                  systemUpdates: { label: 'System Updates', description: 'Notifications about system maintenance and updates' }
                }).map(([key, config]) => (
                  <div key={key} className="flex items-center gap-4 justify-between py-3">
                    <div className="min-w-0 flex-1">
                      <h4 className="text-sm font-medium text-gray-900 dark:text-white">{config.label}</h4>
                      <p className="text-sm text-gray-500 dark:text-gray-400">{config.description}</p>
                    </div>
                    <button
                      onClick={() => handleNotificationChange(key)}
                      className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors ${
                        notifications[key] ? 'bg-green-600' : 'bg-gray-200 dark:bg-gray-600'
                      }`}
                    >
                      <span
                        className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                          notifications[key] ? 'translate-x-6' : 'translate-x-1'
                        }`}
                      />
                    </button>
                  </div>
                ))}
              </div>
            </motion.div>
          )}

          {/* Preferences Tab */}
          {activeTab === 'preferences' && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.2 }}
            >
              <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-6">Application Preferences</h3>
              <div className="space-y-6">
                <div>
                  <h4 className="text-sm font-medium text-gray-900 dark:text-white mb-3">Language & Region</h4>
                  <div className="space-y-3">
                    <div>
                      <label className="block text-sm text-gray-600 dark:text-gray-400 mb-1">Language</label>
                      <select className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-green-500 focus:border-transparent">
                        <option>English</option>
                        <option>Filipino</option>
                        <option>Cebuano</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-sm text-gray-600 dark:text-gray-400 mb-1">Time Zone</label>
                      <select className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-green-500 focus:border-transparent">
                        <option>Philippines Time (PST)</option>
                        <option>UTC+8</option>
                      </select>
                    </div>
                  </div>
                </div>
                <div>
                  <h4 className="text-sm font-medium text-gray-900 dark:text-white mb-3">Data & Privacy</h4>
                  <div className="space-y-3">
                    <button className="text-sm text-green-600 dark:text-green-400 hover:text-green-700 dark:hover:text-green-300">
                      Download My Data
                    </button>
                    <br />
                    <button className="text-sm text-red-600 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300">
                      Delete Account
                    </button>
                  </div>
                </div>
              </div>
            </motion.div>
          )}
        </div>
      </motion.div>
    </div>
  )
}
