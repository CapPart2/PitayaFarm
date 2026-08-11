import { motion } from 'framer-motion'
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { setAdminToken } from '../api/adminApi'
import { getPitayaUserScopeId, getScopedStorageKey } from '../api/userScope'

const buttonBase =
  'min-h-[44px] px-6 py-3 rounded-xl font-semibold shadow-card transition-all duration-300 active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-pitaya-mint focus-visible:ring-offset-2 focus-visible:ring-offset-white'

function safeTrim(value) {
  return String(value ?? '').trim()
}

export default function Login() {
  const navigate = useNavigate()
  const logoUrl = useMemo(() => `${import.meta.env.BASE_URL}logoCaps.png`, [])

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [emailTouched, setEmailTouched] = useState(false)
  const [passwordTouched, setPasswordTouched] = useState(false)
  const [submitAttempted, setSubmitAttempted] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const emailError = (submitAttempted || emailTouched) && !safeTrim(email) ? 'Email is required.' : ''
  const passwordError = (submitAttempted || passwordTouched) && !safeTrim(password) ? 'Password is required.' : ''

  const canSubmit = safeTrim(email).length > 0 && safeTrim(password).length > 0

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSubmitAttempted(true)
    setEmailTouched(true)
    setPasswordTouched(true)
    setError('')

    if (!canSubmit) return

    setLoading(true)
    try {
      const API_BASE = import.meta.env.VITE_API_BASE || ''

      const res = await fetch(`${API_BASE}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: safeTrim(email), password }),
      })
      const data = await res.json()
      if (res.ok && data.success) {
        const user = data.user || {}
        // Normalize backend PascalCase keys to camelCase expected by the SPA
        const normalized = {
          UserID: user.UserID,
          Username: user.Username,
          Email: user.Email,
          firstName: user.FirstName || user.firstName || '',
          lastName: user.LastName || user.lastName || '',
          Role: user.Role,
          Status: user.Status,
        }

        let userPayload = {
          ...normalized,
          // keep Username (capitalized) for admin checks elsewhere
          Username: user.Username,
          isAdmin: (user.Role || '').toLowerCase() === 'admin',
          createdAt: Date.now(),
        }

        const scopedId = getPitayaUserScopeId(userPayload)
        if (scopedId) {
          userPayload.scopeId = scopedId
        }

        // Merge locally-saved profile fields so user edits persist across logout/login
        try {
          const profileKey = getScopedStorageKey('userProfile', userPayload)
          const savedProfile = localStorage.getItem(profileKey)
          if (savedProfile) {
            const parsed = JSON.parse(savedProfile)
            // prefer local fullName -> split into first/last
            if (parsed.fullName) {
              const parts = String(parsed.fullName || '').trim().split(/\s+/)
              const first = parts.shift() || ''
              const last = parts.join(' ') || ''
              userPayload.firstName = first
              userPayload.lastName = last
            }
            if (parsed.farmName) {
              userPayload.farmName = parsed.farmName
            }
          }
        } catch (e) {
          // ignore merge failures
          console.warn('Failed to merge local userProfile into login payload', e)
        }

        localStorage.setItem('pitayaUser', JSON.stringify(userPayload))
        localStorage.removeItem('pitayaLastSignupEmail')

        if (userPayload.isAdmin) {
          setAdminToken(data.adminToken || import.meta.env.VITE_ADMIN_TOKEN || 'admin-secret-token-12345')
        }

        if (userPayload.isAdmin) navigate('/admin/dashboard', { replace: true })
        else navigate('/app/dashboard', { replace: true })
      } else {
        setError(data.error || 'Invalid email or password')
      }
    } catch (err) {
      setError(err.message || 'Login failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen overflow-hidden relative bg-gradient-to-br from-pitaya-bg via-white to-pitaya-pale bg-gradient animate-gradient text-gray-900">
      <div aria-hidden className="absolute -top-24 -left-24 h-72 w-72 rounded-full bg-pitaya-mint/20 blur-3xl" />
      <div aria-hidden className="absolute -bottom-32 -right-20 h-80 w-80 rounded-full bg-pitaya-leaf/15 blur-3xl" />

      <main className="relative min-h-screen flex items-center justify-center px-4 sm:px-6 py-10">
        <motion.section
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45, ease: 'easeOut' }}
          className="w-full max-w-md"
          aria-label="Login"
        >
          <form
            onSubmit={handleSubmit}
            noValidate
            className="bg-white/85 backdrop-blur-md border border-pitaya-leaf/20 rounded-2xl shadow-card px-6 sm:px-8 py-8"
          >
            <div className="text-center">
              <div className="mx-auto w-16 h-16 rounded-2xl bg-white/80 backdrop-blur-sm border border-pitaya-leaf/20 shadow-card flex items-center justify-center">
                <img src={logoUrl} alt="PITAYA" className="w-10 h-10 object-contain" draggable={false} />
              </div>

              <h1 className="mt-4 font-display font-bold text-2xl text-pitaya-deep">Login to Continue</h1>
              <p className="mt-2 text-sm text-gray-700">
                Enter your details to access the system
              </p>
            </div>

            <div className="mt-6 space-y-4">
              <div>
                <label htmlFor="email" className="block text-sm font-semibold text-gray-700">
                  Email
                </label>
                <input
                  id="email"
                  name="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  onBlur={() => setEmailTouched(true)}
                  autoComplete="email"
                  className={`mt-2 w-full min-h-[44px] rounded-xl border bg-white px-4 py-3 text-gray-900 shadow-sm transition-colors focus:outline-none focus:ring-2 focus:ring-pitaya-mint placeholder:text-gray-400 ${
                    emailError ? 'border-red-300 focus:ring-red-300' : 'border-gray-200 focus:border-pitaya-mint'
                  }`}
                  placeholder="Enter your email"
                  aria-invalid={Boolean(emailError)}
                  aria-describedby={emailError ? 'email-error' : undefined}
                />
                {emailError && (
                  <p id="email-error" className="mt-2 text-sm text-red-600">
                    {emailError}
                  </p>
                )}
              </div>

              <div>
                <label htmlFor="password" className="block text-sm font-semibold text-gray-700">
                  Password
                </label>
                <div className="relative mt-2">
                  <input
                    id="password"
                    name="password"
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    onBlur={() => setPasswordTouched(true)}
                    autoComplete="current-password"
                    className={`w-full min-h-[44px] rounded-xl border bg-white px-4 py-3 pr-12 text-gray-900 shadow-sm transition-colors focus:outline-none focus:ring-2 focus:ring-pitaya-mint placeholder:text-gray-400 ${
                      passwordError ? 'border-red-300 focus:ring-red-300' : 'border-gray-200 focus:border-pitaya-mint'
                    }`}
                    placeholder="Enter your password"
                    aria-invalid={Boolean(passwordError)}
                    aria-describedby={passwordError ? 'password-error' : undefined}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((visible) => !visible)}
                    className="absolute inset-y-0 right-0 flex w-12 items-center justify-center text-gray-500 hover:text-pitaya-deep focus:outline-none focus:ring-2 focus:ring-pitaya-mint focus:ring-inset disabled:cursor-not-allowed disabled:opacity-50"
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                  >
                    {showPassword ? (
                      <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-5 w-5"><path d="m3 3 18 18" /><path d="M10.6 10.6a3 3 0 0 0 4.2 4.2" /><path d="M9.9 4.2A10.7 10.7 0 0 1 12 4c5.5 0 9.3 5.4 9.5 5.7a1 1 0 0 1 0 1.1 18.1 18.1 0 0 1-3 3.7" /><path d="M6.6 6.6A18.4 18.4 0 0 0 2.5 9.7a1 1 0 0 0 0 1.1C2.7 11.1 6.5 16.5 12 16.5c.7 0 1.4-.1 2-.2" /></svg>
                    ) : (
                      <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-5 w-5"><path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z" /><circle cx="12" cy="12" r="3" /></svg>
                    )}
                  </button>
                </div>
                {passwordError && (
                  <p id="password-error" className="mt-2 text-sm text-red-600">
                    {passwordError}
                  </p>
                )}
              </div>

              <div className="text-center mt-2">
                <a href="/signup" className="text-sm font-semibold text-pitaya-deep hover:underline">Create Account / Sign Up</a>
              </div>
            </div>

            {error && (
              <div className="mt-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
                {error}
              </div>
            )}

            <motion.button
              type="submit"
              className={`${buttonBase} mt-6 w-full bg-pitaya-primary text-white shadow-card hover:bg-pitaya-leaf hover:shadow-card-hover disabled:bg-pitaya-primary disabled:opacity-100 disabled:cursor-not-allowed`}
              whileHover={{ scale: 1.01 }}
              whileTap={{ scale: 0.99 }}
              disabled={loading}
            >
              {loading ? (
                <span className="flex items-center justify-center">
                  <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Signing in...
                </span>
              ) : (
                'Login'
              )}
            </motion.button>

            <button
              type="button"
              onClick={() => navigate('/get-started')}
              className="mt-3 w-full min-h-[44px] rounded-xl border border-pitaya-leaf/20 bg-white/80 px-6 py-3 text-sm font-semibold text-pitaya-deep transition-colors hover:bg-white"
            >
              Back
            </button>
          </form>
        </motion.section>
      </main>
    </div>
  )
}
