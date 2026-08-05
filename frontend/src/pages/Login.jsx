import { motion } from 'framer-motion'
import { useMemo, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

const buttonBase =
  'min-h-[44px] px-6 py-3 rounded-xl font-semibold shadow-card transition-all duration-300 active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-pitaya-mint focus-visible:ring-offset-2 focus-visible:ring-offset-white'

function safeTrim(value) {
  return String(value ?? '').trim()
}

export default function Login() {
  const navigate = useNavigate()
  const location = useLocation()
  const logoUrl = useMemo(() => `${import.meta.env.BASE_URL}logoCaps.png`, [])

  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [touched, setTouched] = useState(false)

  const firstNameError = touched && !safeTrim(firstName) ? 'First name is required.' : ''
  const lastNameError = touched && !safeTrim(lastName) ? 'Last name is required.' : ''
  const canSubmit = safeTrim(firstName).length > 0 && safeTrim(lastName).length > 0

  const handleSubmit = (e) => {
    e.preventDefault()
    setTouched(true)
    if (!canSubmit) return

    const payload = {
      firstName: safeTrim(firstName),
      lastName: safeTrim(lastName),
      createdAt: Date.now(),
    }

    localStorage.setItem('pitayaUser', JSON.stringify(payload))

    const from = location.state?.from?.pathname
    navigate(from && from.startsWith('/app/') ? from : '/app/dashboard', { replace: true })
  }

  return (
    <div className="min-h-screen overflow-hidden relative bg-gradient-to-br from-pitaya-bg via-white to-pitaya-pale bg-gradient animate-gradient">
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
            className="bg-white/80 backdrop-blur-md border border-pitaya-leaf/20 rounded-2xl shadow-card px-6 sm:px-8 py-8"
          >
            <div className="text-center">
              <div className="mx-auto w-16 h-16 rounded-2xl bg-white/70 backdrop-blur-sm border border-pitaya-leaf/20 shadow-card flex items-center justify-center">
                <img src={logoUrl} alt="PITAYA" className="w-10 h-10 object-contain" draggable={false} />
              </div>

              <h1 className="mt-4 font-display font-bold text-2xl text-pitaya-deep dark:text-pitaya-light">Login to Continue</h1>
              <p className="mt-2 text-sm text-gray-600 dark:text-gray-300">Enter your details to access the system</p>
            </div>

            <div className="mt-6 space-y-4">
              <div>
                <label htmlFor="firstName" className="block text-sm font-semibold text-gray-700 dark:text-gray-300">
                  First Name
                </label>
                <input
                  id="firstName"
                  name="firstName"
                  type="text"
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                  onBlur={() => setTouched(true)}
                  autoComplete="given-name"
                  className={`mt-2 w-full min-h-[44px] rounded-xl border bg-white dark:bg-gray-800 px-4 py-3 text-gray-900 dark:text-gray-100 shadow-sm transition-colors focus:outline-none focus:ring-2 focus:ring-pitaya-mint ${
                    firstNameError ? 'border-red-300 focus:ring-red-300' : 'border-gray-200 focus:border-pitaya-mint'
                  }`}
                  placeholder="Juan"
                  aria-invalid={Boolean(firstNameError)}
                  aria-describedby={firstNameError ? 'firstName-error' : undefined}
                  required
                />
                {firstNameError && (
                  <p id="firstName-error" className="mt-2 text-sm text-red-600">
                    {firstNameError}
                  </p>
                )}
              </div>

              <div>
                <label htmlFor="lastName" className="block text-sm font-semibold text-gray-700 dark:text-gray-300">
                  Last Name
                </label>
                <input
                  id="lastName"
                  name="lastName"
                  type="text"
                  value={lastName}
                  onChange={(e) => setLastName(e.target.value)}
                  onBlur={() => setTouched(true)}
                  autoComplete="family-name"
                  className={`mt-2 w-full min-h-[44px] rounded-xl border bg-white dark:bg-gray-800 px-4 py-3 text-gray-900 dark:text-gray-100 shadow-sm transition-colors focus:outline-none focus:ring-2 focus:ring-pitaya-mint ${
                    lastNameError ? 'border-red-300 focus:ring-red-300' : 'border-gray-200 focus:border-pitaya-mint'
                  }`}
                  placeholder="Dela Cruz"
                  aria-invalid={Boolean(lastNameError)}
                  aria-describedby={lastNameError ? 'lastName-error' : undefined}
                  required
                />
                {lastNameError && (
                  <p id="lastName-error" className="mt-2 text-sm text-red-600">
                    {lastNameError}
                  </p>
                )}
              </div>
            </div>

            <motion.button
              type="submit"
              className={`${buttonBase} mt-6 w-full bg-pitaya-primary text-white hover:bg-pitaya-leaf hover:shadow-card-hover ${
                canSubmit ? '' : 'opacity-60'
              }`}
              whileHover={{ scale: 1.01 }}
              whileTap={{ scale: 0.99 }}
            >
              Login
            </motion.button>

            <button
              type="button"
              onClick={() => navigate('/get-started')}
              className="mt-3 w-full min-h-[44px] rounded-xl border border-pitaya-leaf/20 bg-white/60 px-6 py-3 text-sm font-semibold text-pitaya-deep transition-colors hover:bg-white"
            >
              Back
            </button>
          </form>
        </motion.section>
      </main>
    </div>
  )
}
