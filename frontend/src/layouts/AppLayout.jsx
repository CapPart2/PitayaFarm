import { motion } from 'framer-motion'
import {
    Bell,
    BookOpen,
    FileText,
    LayoutDashboard,
    LogOut,
    Menu,
    Moon,
    Search,
    Sun,
    TrendingUp,
    User,
    X
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'

const navItems = [
  { to: '/app/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/app/identify', label: 'Disease Detection', icon: Search },
  { to: '/app/library', label: 'Library', icon: BookOpen },
  { to: '/app/alerts', label: 'Alerts', icon: Bell },
  { to: '/app/yield', label: 'Assessing Yield', icon: TrendingUp },
  { to: '/app/reports', label: 'Reports', icon: FileText },
  { to: '/app/profile', label: 'Profile', icon: User },
]

const pathToTitle = {
  '/app/dashboard': 'Dashboard',
  '/app/identify': 'Disease Detection',
  '/app/library': 'Library',
  '/app/alerts': 'Alerts',
  '/app/yield': 'Assessing Yield',
  '/app/reports': 'Reports',
  '/app/yield-report': 'Reports',
  '/app/profile': 'Profile',
}

function getPageTitle(pathname) {
  if (pathToTitle[pathname]) return pathToTitle[pathname]
  if (pathname.startsWith('/app/')) return 'Dashboard'
  return 'PITAYA'
}

export default function AppLayout() {
  const location = useLocation()
  const navigate = useNavigate()
  const [darkMode, setDarkMode] = useState(false)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const pageTitle = getPageTitle(location.pathname)

  const logoUrl = `${import.meta.env.BASE_URL}logoCaps.png`

  const handleBrandClick = () => {
    setMobileMenuOpen(false)
    window.location.assign('/app/dashboard')
  }

  const handleLogout = () => {
    setMobileMenuOpen(false)
    localStorage.removeItem('pitayaUser')
    navigate('/landing', { replace: true })
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
        aria-label="Main navigation"
      >
        {/* Header */}
        <div className="p-4 flex items-center border-b border-gray-200 dark:border-gray-700">
          <button
            type="button"
            onClick={handleBrandClick}
            className="flex items-center gap-3 text-left"
            aria-label="Go to Dashboard"
          >
            <img
              src="/logoCaps.png"
              alt="PITAYA"
              className="w-10 h-10 rounded-xl object-contain"
            />
            <span className="font-display font-bold text-lg">PITAYA</span>
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              onClick={() => setMobileMenuOpen(false)}
              className={({ isActive }) =>
                `group flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 min-h-[44px] ${
                  isActive 
                    ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 border-l-4 border-green-600 dark:border-green-400' 
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
        <header className="h-14 px-4 lg:px-6 flex items-center gap-3 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 shadow-sm shrink-0 transition-colors duration-300">
          {/* Mobile Menu Button */}
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="lg:hidden p-2 rounded-lg text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
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
    </div>
  )
}
