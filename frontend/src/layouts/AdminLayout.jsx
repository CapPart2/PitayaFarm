import { motion } from 'framer-motion'
import {
    Activity,
    AlertTriangle,
  BookOpen,
    Database,
    FileText,
    LayoutDashboard,
    LogOut,
    Menu,
    Moon,
    Settings,
    Shield,
    Sun,
    User,
    X
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { adminAuthApi } from '../api/adminApi'

const adminNavItems = [
  { to: '/admin/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/admin/library', label: 'Disease Library', icon: BookOpen },
  { to: '/admin/users', label: 'User Management', icon: User },
  { to: '/admin/logs', label: 'User Logs', icon: Activity },
  { to: '/admin/records', label: 'Data Records', icon: Database },
  { to: '/admin/reports', label: 'Reports', icon: FileText },
  { to: '/admin/settings', label: 'Settings', icon: Settings },
]

const pathToTitle = {
  '/admin/dashboard': 'Admin Dashboard',
  '/admin/library': 'Disease Library',
  '/admin/users': 'User Management',
  '/admin/logs': 'User Logs',
  '/admin/records': 'Data Records',
  '/admin/reports': 'Reports',
  '/admin/settings': 'Settings',
}

function getPageTitle(pathname) {
  if (pathToTitle[pathname]) return pathToTitle[pathname]
  if (pathname.startsWith('/admin/')) return 'Admin Dashboard'
  return 'PITAYA Admin'
}

export default function AdminLayout() {
  const location = useLocation()
  const navigate = useNavigate()
  const [darkMode, setDarkMode] = useState(false)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [confirmLogout, setConfirmLogout] = useState(false)
  const pageTitle = getPageTitle(location.pathname)

  const logoUrl = `${import.meta.env.BASE_URL}logoCaps.png`

  const handleBrandClick = () => {
    setMobileMenuOpen(false)
    navigate('/admin/dashboard')
  }

  const handleLogout = () => {
    setMobileMenuOpen(false)
    setConfirmLogout(true)
  }

  const confirmLogoutAction = () => {
    adminAuthApi.logout()
    setConfirmLogout(false)
    navigate('/login', { replace: true })
  }

  // Load theme preference from localStorage
  useEffect(() => {
    const savedTheme = localStorage.getItem('theme')
    if (savedTheme === 'dark') {
      setDarkMode(true)
      document.documentElement.classList.add('dark')
    }
  }, [])

  // Toggle theme and save preference
  const toggleTheme = () => {
    const newTheme = !darkMode
    setDarkMode(newTheme)
    if (newTheme) {
      document.documentElement.classList.add('dark')
      localStorage.setItem('theme', 'dark')
    } else {
      document.documentElement.classList.remove('dark')
      localStorage.setItem('theme', 'light')
    }
  }

  return (
    <div className="min-h-screen flex bg-gray-50 dark:bg-gray-900 transition-colors duration-300">
     
      {mobileMenuOpen && (
        <div 
          className="fixed inset-0 bg-black bg-opacity-50 z-40 lg:hidden"
          onClick={() => setMobileMenuOpen(false)}
        />
      )}

      {/* Sidebar - Fixed on desktop, sliding on mobile */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 w-64 bg-white dark:bg-gray-800 text-gray-800 dark:text-white flex flex-col shadow-lg border-r border-gray-200 dark:border-gray-700 transform transition-transform duration-300 ease-in-out lg:translate-x-0 ${
          mobileMenuOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
        aria-label="Admin navigation"
      >
        {/* Header */}
        <div className="p-4 flex items-center border-b border-gray-200 dark:border-gray-700">
          <button
            type="button"
            onClick={handleBrandClick}
            className="flex items-center gap-3 text-left"
            aria-label="Go to Admin Dashboard"
          >
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-500 to-purple-600 flex items-center justify-center">
              <Shield className="w-6 h-6 text-white" />
            </div>
            <div>
              <span className="font-display font-bold text-lg">PITAYA</span>
              <span className="block text-xs text-gray-500 dark:text-gray-400">Admin Panel</span>
            </div>
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          {adminNavItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              onClick={() => setMobileMenuOpen(false)}
              className={({ isActive }) =>
                `group flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 min-h-[44px] ${
                  isActive 
                    ? 'bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-400 border-l-4 border-purple-600 dark:border-purple-400' 
                    : 'text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 hover:text-gray-900 dark:hover:text-white'
                }`
              }
            >
              {/* Icon */}
              <item.icon 
                className="w-5 h-5 shrink-0 transition-transform duration-200 group-hover:scale-110" 
                aria-hidden 
              />
              
              {/* Label - Always visible */}
              <span className="truncate">
                {item.label}
              </span>
            </NavLink>
          ))}
        </nav>

        {/* Footer */}
        <div className="p-3 border-t border-gray-200 dark:border-gray-700 space-y-2">
          {/* Theme Toggle */}
          <button
            type="button"
            onClick={toggleTheme}
            className="group w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-all duration-200 min-h-[44px]"
          >
            {darkMode ? (
              <Sun className="w-5 h-5 shrink-0 transition-transform duration-200 group-hover:scale-110" />
            ) : (
              <Moon className="w-5 h-5 shrink-0 transition-transform duration-200 group-hover:scale-110" />
            )}
            <span>
              {darkMode ? 'Light Mode' : 'Dark Mode'}
            </span>
          </button>

          {/* Back to App */}
          <button
            type="button"
            onClick={() => navigate('/landing')}
            className="group w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-all duration-200 min-h-[44px]"
          >
            <LayoutDashboard className="w-5 h-5 shrink-0 transition-transform duration-200 group-hover:scale-110" />
            <span>
              Back to App
            </span>
          </button>

          {/* Logout */}
          <button
            type="button"
            onClick={handleLogout}
            className="group w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition-all duration-200 min-h-[44px]"
          >
            <LogOut className="w-5 h-5 shrink-0 transition-transform duration-200 group-hover:scale-110" />
            <span>
              Logout
            </span>
          </button>
        </div>
      </aside>

      <div className="flex-1 flex flex-col min-w-0 lg:ml-64">
        <header className="min-h-14 px-3 py-2 sm:px-4 lg:px-6 flex items-center gap-3 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 shadow-sm shrink-0 transition-colors duration-300">
          {/* Mobile Menu Button */}
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="lg:hidden min-h-[44px] min-w-[44px] p-2 rounded-lg text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
            aria-label="Toggle menu"
          >
            {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
          
          <h1 className="font-display font-semibold text-lg text-gray-800 dark:text-white truncate transition-colors duration-300 flex-1">{pageTitle}</h1>
        </header>

        <main className="flex-1 p-3 sm:p-4 lg:p-6 bg-gray-50 dark:bg-gray-900 transition-colors duration-300">
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, ease: 'easeOut' }}
            className="h-full overflow-auto"
          >
            <Outlet />
          </motion.div>
        </main>
      </div>

      {/* Logout Confirmation Modal */}
      {confirmLogout && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 z-[60] animate-in fade-in duration-200">
          <div className="bg-white dark:bg-gray-800 rounded-2xl max-w-md w-full shadow-2xl animate-in slide-in-from-bottom-4 duration-300">
            <div className="p-6">
              {/* Header */}
              <div className="flex items-center gap-4 mb-6">
                <div className="w-14 h-14 rounded-full bg-gradient-to-br from-amber-100 to-amber-200 dark:from-amber-900/40 dark:to-amber-800/30 flex items-center justify-center shrink-0 shadow-sm">
                  <LogOut className="w-7 h-7 text-amber-600 dark:text-amber-400" />
                </div>
                <div>
                  <h3 className="text-xl font-bold text-gray-900 dark:text-gray-100">Logout</h3>
                  <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">Are you sure you want to logout?</p>
                </div>
              </div>

              {/* Warning Message */}
              <div className="flex items-start gap-3 mb-6 p-4 bg-amber-50 dark:bg-amber-900/20 rounded-lg border border-amber-200 dark:border-amber-800">
                <AlertTriangle className="w-5 h-5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
                <p className="text-sm text-amber-800 dark:text-amber-200">
                  You will be logged out of the admin panel and redirected to the login page.
                </p>
              </div>

              {/* Action Buttons */}
              <div className="flex gap-3">
                <button
                  onClick={() => setConfirmLogout(false)}
                  className="flex-1 px-4 py-3 rounded-xl border-2 border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700 transition-all duration-200 font-semibold"
                >
                  Cancel
                </button>
                <button
                  onClick={confirmLogoutAction}
                  className="flex-1 px-4 py-3 rounded-xl bg-gradient-to-r from-amber-600 to-amber-700 hover:from-amber-700 hover:to-amber-800 text-white font-semibold transition-all duration-200 flex items-center justify-center gap-2 shadow-lg shadow-amber-500/25"
                >
                  <LogOut className="w-4 h-4" />
                  Logout
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
