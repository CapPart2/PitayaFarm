import { motion } from 'framer-motion'
import { useEffect, useMemo, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

function getStoredDetails() {
  try {
    return JSON.parse(sessionStorage.getItem('pitayaSignupVerification') || '{}')
  } catch {
    return {}
  }
}

export default function VerifyEmail() {
  const navigate = useNavigate()
  const location = useLocation()
  const logoUrl = useMemo(() => `${import.meta.env.BASE_URL}logoCaps.png`, [])
  const initial = location.state?.challengeId ? location.state : getStoredDetails()
  const [details, setDetails] = useState(initial)
  const [code, setCode] = useState('')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)
  const [resending, setResending] = useState(false)
  const [confirmed, setConfirmed] = useState(false)

  useEffect(() => {
    if (initial?.challengeId) {
      sessionStorage.setItem('pitayaSignupVerification', JSON.stringify(initial))
    }
  }, [])

  const handleVerify = async (event) => {
    event.preventDefault()
    setError('')
    if (!details?.challengeId) {
      setError('Start by creating your account so we can send a confirmation code.')
      return
    }
    if (!/^\d{6}$/.test(code)) {
      setError('Enter the 6-digit code from your email.')
      return
    }

    setLoading(true)
    try {
      const API_BASE = import.meta.env.VITE_API_BASE || ''
      const response = await fetch(`${API_BASE}/api/auth/verify-signup-email`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ challenge_id: details.challengeId, code }),
      })
      const data = await response.json()
      if (!(response.ok && data.success)) {
        setError(data.error || 'We could not confirm that code.')
        return
      }
      sessionStorage.removeItem('pitayaSignupVerification')
      setConfirmed(true)
    } catch {
      setError('We could not connect. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const handleResend = async () => {
    setError('')
    setMessage('')
    if (!details?.email) {
      setError('We need your email address to send another code.')
      return
    }
    setResending(true)
    try {
      const API_BASE = import.meta.env.VITE_API_BASE || ''
      const response = await fetch(`${API_BASE}/api/auth/resend-signup-code`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: details.email }),
      })
      const data = await response.json()
      if (!(response.ok && data.success)) {
        setError(data.error || 'We could not resend the code.')
        return
      }
      const updated = {
        ...details,
        challengeId: data.verification?.challenge_id || details.challengeId,
        maskedEmail: data.verification?.masked_email || details.maskedEmail,
      }
      setDetails(updated)
      sessionStorage.setItem('pitayaSignupVerification', JSON.stringify(updated))
      setCode('')
      setMessage('A new code has been sent. Check your inbox.')
    } catch {
      setError('We could not connect. Please try again.')
    } finally {
      setResending(false)
    }
  }

  return (
    <div className="relative min-h-screen overflow-hidden bg-gradient-to-br from-pitaya-bg via-white to-pitaya-pale text-gray-900">
      <div aria-hidden className="absolute -top-24 -left-24 h-72 w-72 rounded-full bg-pitaya-mint/20 blur-3xl" />
      <div aria-hidden className="absolute -bottom-32 -right-20 h-80 w-80 rounded-full bg-pitaya-leaf/15 blur-3xl" />
      <main className="relative flex min-h-screen items-center justify-center px-4 py-10">
        <motion.section initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }} className="w-full max-w-md rounded-3xl border border-pitaya-leaf/20 bg-white/90 p-6 shadow-card backdrop-blur-md sm:p-8">
          <div className="text-center">
            <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl border border-pitaya-leaf/20 bg-white shadow-card">
              <img src={logoUrl} alt="PITAYA" className="h-10 w-10 object-contain" draggable={false} />
            </div>
            <div className="mx-auto mt-5 flex h-12 w-12 items-center justify-center rounded-full bg-pitaya-mint/25 text-pitaya-deep">
              <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-6 w-6"><rect x="3" y="5" width="18" height="14" rx="2" /><path d="m4 7 8 6 8-6" /></svg>
            </div>
            <h1 className="mt-4 font-display text-2xl font-bold text-pitaya-deep">Confirm your email</h1>
            <p className="mt-2 text-sm leading-6 text-gray-700">One last step: enter the 6-digit code we sent to confirm you own this email address.</p>
          </div>

          <ol className="mt-6 grid grid-cols-3 gap-2 text-center text-[11px] font-semibold text-pitaya-deep/70" aria-label="Sign-up progress">
            <li><span className="mx-auto mb-1 flex h-6 w-6 items-center justify-center rounded-full bg-pitaya-primary text-white">1</span>Details</li>
            <li><span className="mx-auto mb-1 flex h-6 w-6 items-center justify-center rounded-full bg-pitaya-primary text-white">2</span>Confirm email</li>
            <li><span className="mx-auto mb-1 flex h-6 w-6 items-center justify-center rounded-full border border-pitaya-leaf/30 bg-white">3</span>Sign in</li>
          </ol>

          <div className="mt-6 rounded-2xl border border-pitaya-leaf/15 bg-pitaya-pale/55 px-4 py-3 text-center">
            <p className="text-xs font-semibold uppercase tracking-wide text-pitaya-deep/70">Confirmation code sent to</p>
            <p className="mt-1 font-semibold text-pitaya-deep">{details?.maskedEmail || details?.email || 'your email address'}</p>
          </div>

          {confirmed ? (
            <div className="mt-6 text-center" role="status">
              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-green-100 text-green-700">
                <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" className="h-8 w-8"><path d="m5 12 4.5 4.5L19 7" /></svg>
              </div>
              <h2 className="mt-4 font-display text-xl font-bold text-pitaya-deep">Email confirmed!</h2>
              <p className="mt-2 text-sm leading-6 text-gray-700">Your account is ready. You can now sign in with your email and password.</p>
              <button type="button" onClick={() => navigate('/login', { replace: true })} className="mt-6 min-h-[48px] w-full rounded-xl bg-pitaya-primary px-6 py-3 font-semibold text-white shadow-card transition hover:bg-pitaya-leaf">Continue to login</button>
            </div>
          ) : (
            <>
              <form onSubmit={handleVerify} noValidate className="mt-6">
                <label htmlFor="confirmationCode" className="block text-sm font-semibold text-gray-700">Confirmation code</label>
                <input id="confirmationCode" type="text" inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={code} onChange={(event) => setCode(event.target.value.replace(/\D/g, ''))} className="mt-2 w-full rounded-xl border border-gray-200 bg-white px-4 py-3 text-center text-xl font-bold tracking-[0.45em] text-pitaya-deep outline-none transition focus:border-pitaya-mint focus:ring-2 focus:ring-pitaya-mint" placeholder="000000" aria-invalid={Boolean(error)} aria-describedby={error ? 'confirmation-error' : undefined} />
                {error && <p id="confirmation-error" className="mt-3 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
                {message && <p className="mt-3 rounded-xl border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-700">{message}</p>}
                <button type="submit" disabled={loading} className="mt-5 min-h-[48px] w-full rounded-xl bg-pitaya-primary px-6 py-3 font-semibold text-white shadow-card transition hover:bg-pitaya-leaf disabled:cursor-not-allowed disabled:opacity-60">{loading ? 'Confirming email...' : 'Confirm email address'}</button>
              </form>

              <p className="mt-5 text-center text-sm text-gray-600">Didn't receive a code? <button type="button" onClick={handleResend} disabled={resending} className="font-semibold text-pitaya-deep hover:underline disabled:opacity-60">{resending ? 'Sending...' : 'Resend code'}</button></p>
              <button type="button" onClick={() => navigate('/signup')} className="mt-4 w-full text-sm font-semibold text-pitaya-deep hover:underline">Use a different email</button>
            </>
          )}
        </motion.section>
      </main>
    </div>
  )
}
