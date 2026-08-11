import { motion } from 'framer-motion'
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

const buttonBase =
  'min-h-[44px] px-6 py-3 rounded-xl font-semibold shadow-card transition-all duration-300 active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-pitaya-mint focus-visible:ring-offset-2 focus-visible:ring-offset-white'

function safeTrim(value) {
  return String(value ?? '').trim()
}

export default function Signup() {
  const navigate = useNavigate()
  const logoUrl = useMemo(() => `${import.meta.env.BASE_URL}logoCaps.png`, [])
  const [email, setEmail] = useState('')
  const [username, setUsername] = useState('')
  const [name, setName] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [emailTouched, setEmailTouched] = useState(false)
  const [usernameTouched, setUsernameTouched] = useState(false)
  const [nameTouched, setNameTouched] = useState(false)
  const [passwordTouched, setPasswordTouched] = useState(false)
  const [submitAttempted, setSubmitAttempted] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const nameError = (submitAttempted || nameTouched) && !safeTrim(name) ? 'Full name is required.' : ''
  const emailError = (submitAttempted || emailTouched) && !safeTrim(email) ? 'Email is required.' : ''
  const usernameError = (submitAttempted || usernameTouched) && !safeTrim(username) ? 'Username is required.' : ''
  const passwordError = (submitAttempted || passwordTouched) && !safeTrim(password)
    ? 'Password is required.'
    : password.length > 8
      ? 'Password must not exceed 8 characters.'
      : ''

  const canSubmit = [name, email, username, password].every((value) => safeTrim(value).length > 0) && password.length <= 8

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSubmitAttempted(true)
    setNameTouched(true)
    setEmailTouched(true)
    setUsernameTouched(true)
    setPasswordTouched(true)
    setError('')

    if (!canSubmit) return

    setLoading(true)
    try {
      const API_BASE = import.meta.env.VITE_API_BASE || ''
      const res = await fetch(`${API_BASE}/api/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: safeTrim(email),
          username: safeTrim(username),
          name: safeTrim(name),
          password,
        }),
      })
      const data = await res.json()
      if (res.ok && data.success) {
        alert(data.message || 'Account created — please wait for admin verification')
        localStorage.setItem('pitayaLastSignupEmail', safeTrim(email))
        // Clear any existing local user data so the new account starts empty
        try {
          localStorage.removeItem('pitayaUser')
          localStorage.removeItem('userProfile')
          localStorage.removeItem('profilePicture')
          localStorage.removeItem('userNotifications')
        } catch (e) {
          console.warn('Failed clearing local storage on signup', e)
        }
        navigate('/login')
      } else {
        setError(data.error || 'Signup failed')
      }
    } catch (err) {
      setError(err.message || 'Signup failed')
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
          aria-label="Sign up"
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

              <h1 className="mt-4 font-display font-bold text-2xl text-pitaya-deep">Create Account</h1>
              <p className="mt-2 text-sm text-gray-700">
                Fill up your details to create your PITAYA account
              </p>
            </div>

            <div className="mt-6 space-y-4">
              <div>
                <label htmlFor="name" className="block text-sm font-semibold text-gray-700">
                  Full Name
                </label>
                <input
                  id="name"
                  name="name"
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  onBlur={() => setNameTouched(true)}
                  autoComplete="name"
                  className={`mt-2 w-full min-h-[44px] rounded-xl border bg-white px-4 py-3 text-gray-900 shadow-sm transition-colors focus:outline-none focus:ring-2 focus:ring-pitaya-mint placeholder:text-gray-400 ${
                    nameError ? 'border-red-300 focus:ring-red-300' : 'border-gray-200 focus:border-pitaya-mint'
                  }`}
                  placeholder="Enter your full name"
                  aria-invalid={Boolean(nameError)}
                  aria-describedby={nameError ? 'name-error' : undefined}
                />
                {nameError && (
                  <p id="name-error" className="mt-2 text-sm text-red-600">
                    {nameError}
                  </p>
                )}
              </div>

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
                <label htmlFor="username" className="block text-sm font-semibold text-gray-700">
                  Username
                </label>
                <input
                  id="username"
                  name="username"
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  onBlur={() => setUsernameTouched(true)}
                  autoComplete="username"
                  className={`mt-2 w-full min-h-[44px] rounded-xl border bg-white px-4 py-3 text-gray-900 shadow-sm transition-colors focus:outline-none focus:ring-2 focus:ring-pitaya-mint placeholder:text-gray-400 ${
                    usernameError ? 'border-red-300 focus:ring-red-300' : 'border-gray-200 focus:border-pitaya-mint'
                  }`}
                  placeholder="Enter your username"
                  aria-invalid={Boolean(usernameError)}
                  aria-describedby={usernameError ? 'username-error' : undefined}
                />
                {usernameError && (
                  <p id="username-error" className="mt-2 text-sm text-red-600">
                    {usernameError}
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
                    autoComplete="new-password"
                    maxLength={8}
                    className={`w-full min-h-[44px] rounded-xl border bg-white px-4 py-3 pr-12 text-gray-900 shadow-sm transition-colors focus:outline-none focus:ring-2 focus:ring-pitaya-mint placeholder:text-gray-400 ${
                      passwordError ? 'border-red-300 focus:ring-red-300' : 'border-gray-200 focus:border-pitaya-mint'
                    }`}
                    placeholder="Enter your password"
                    aria-invalid={Boolean(passwordError)}
                    aria-describedby={passwordError ? 'password-error password-help' : 'password-help'}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((visible) => !visible)}
                    className="absolute inset-y-0 right-0 flex w-12 items-center justify-center text-gray-500 hover:text-pitaya-deep focus:outline-none focus:ring-2 focus:ring-pitaya-mint focus:ring-inset"
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                  >
                    {showPassword ? (
                      <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-5 w-5"><path d="m3 3 18 18" /><path d="M10.6 10.6a3 3 0 0 0 4.2 4.2" /><path d="M9.9 4.2A10.7 10.7 0 0 1 12 4c5.5 0 9.3 5.4 9.5 5.7a1 1 0 0 1 0 1.1 18.1 18.1 0 0 1-3 3.7" /><path d="M6.6 6.6A18.4 18.4 0 0 0 2.5 9.7a1 1 0 0 0 0 1.1C2.7 11.1 6.5 16.5 12 16.5c.7 0 1.4-.1 2-.2" /></svg>
                    ) : (
                      <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-5 w-5"><path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z" /><circle cx="12" cy="12" r="3" /></svg>
                    )}
                  </button>
                </div>
                <p id="password-help" className="mt-2 text-xs text-gray-600">Maximum 8 characters.</p>
                {passwordError && (
                  <p id="password-error" className="mt-2 text-sm text-red-600">
                    {passwordError}
                  </p>
                )}
              </div>

              <div className="text-center mt-2">
                <a href="/login" className="text-sm font-semibold text-pitaya-deep hover:underline">Already have an account? Login</a>
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
              disabled={loading || !canSubmit}
            >
              {loading ? 'Creating...' : 'Create account'}
            </motion.button>

            <button
              type="button"
              onClick={() => navigate('/login')}
              className="mt-3 w-full min-h-[44px] rounded-xl border border-pitaya-leaf/20 bg-white/80 px-6 py-3 text-sm font-semibold text-pitaya-deep transition-colors hover:bg-white"
            >
              Back to Login
            </button>
          </form>
        </motion.section>
      </main>
    </div>
  )
}
