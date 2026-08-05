import { motion } from 'framer-motion'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

const HEALTH_URL = `${import.meta.env.VITE_API_BASE_URL || window.location.origin}/health`
const MIN_PROGRESS_WHEN_ONLINE = 15
const BASE_DURATION_MS = 5200
const OFFLINE_MESSAGE = 'Offline. Waiting for connection...'

export default function Loading() {
  const navigate = useNavigate()
  const logoUrl = useMemo(() => `${import.meta.env.BASE_URL}logoCaps.png`, [])
  const [progress, setProgress] = useState(0)
  const [connectionLabel, setConnectionLabel] = useState('Checking connection...')
  const [isOnline, setIsOnline] = useState(navigator.onLine)
  const [isBackendReachable, setIsBackendReachable] = useState(false)
  const onlineRef = useRef(navigator.onLine)
  const backendReachableRef = useRef(false)

  useEffect(() => {
    const handleOnline = () => setIsOnline(true)
    const handleOffline = () => setIsOnline(false)

    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)

    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
    }
  }, [])

  useEffect(() => {
    let animationFrameId = 0
    let pollTimer = 0
    let lastFrameTime = 0
    let accumulatedOnlineMs = 0
    let mounted = true

    const updateConnectionLabel = (online, backendReachable) => {
      if (!online) {
        setConnectionLabel(OFFLINE_MESSAGE)
        return
      }

      if (!backendReachable) {
        setConnectionLabel('Connection restored, verifying backend...')
        return
      }

      const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection
      const effectiveType = String(connection?.effectiveType || '').toLowerCase()

      if (effectiveType.includes('slow-2g')) {
        setConnectionLabel('Connected on a very slow network')
      } else if (effectiveType.includes('2g')) {
        setConnectionLabel('Connected on a slow network')
      } else if (effectiveType.includes('3g')) {
        setConnectionLabel('Connected on a moderate network')
      } else if (effectiveType.includes('4g')) {
        setConnectionLabel('Connected on a fast network')
      } else {
        setConnectionLabel('Connected. Loading your workspace...')
      }
    }

    const verifyBackend = async () => {
      if (!onlineRef.current) {
        if (mounted) {
          setIsBackendReachable(false)
          backendReachableRef.current = false
          updateConnectionLabel(false, false)
        }
        return false
      }

      try {
        const response = await fetch(HEALTH_URL, { cache: 'no-store' })
        const reachable = response.ok

        if (mounted) {
          setIsBackendReachable(reachable)
          backendReachableRef.current = reachable
          updateConnectionLabel(true, reachable)
        }

        return reachable
      } catch {
        if (mounted) {
          setIsBackendReachable(false)
          backendReachableRef.current = false
          updateConnectionLabel(true, false)
        }

        return false
      }
    }

    const tick = (now) => {
      if (!mounted) return

      if (!lastFrameTime) {
        lastFrameTime = now
      }

      const delta = now - lastFrameTime
      lastFrameTime = now
      const online = onlineRef.current
      const backendReachable = backendReachableRef.current

      if (online && backendReachable) {
        accumulatedOnlineMs += delta
      }

      const targetProgress = online && backendReachable
        ? Math.min(100, Math.max(MIN_PROGRESS_WHEN_ONLINE, (accumulatedOnlineMs / BASE_DURATION_MS) * 100))
        : 0

      setProgress((current) => (targetProgress > current ? targetProgress : current))

      if (online && backendReachable && accumulatedOnlineMs >= BASE_DURATION_MS) {
        navigate('/landing', { replace: true })
        return
      }

      animationFrameId = window.requestAnimationFrame(tick)
    }

    const runHealthPoll = async () => {
      await verifyBackend()
      if (mounted) {
        pollTimer = window.setTimeout(runHealthPoll, onlineRef.current ? 2000 : 1000)
      }
    }

    updateConnectionLabel(onlineRef.current, false)
    runHealthPoll()
    animationFrameId = window.requestAnimationFrame(tick)

    return () => {
      mounted = false
      window.cancelAnimationFrame(animationFrameId)
      window.clearTimeout(pollTimer)
    }
  }, [navigate])

  return (
    <div className="min-h-screen overflow-hidden relative bg-gradient-to-br from-pitaya-bg via-white to-pitaya-pale bg-gradient animate-gradient">
      {/* subtle glass blobs */}
      <div aria-hidden className="absolute -top-24 -left-24 h-72 w-72 rounded-full bg-pitaya-mint/20 blur-3xl" />
      <div aria-hidden className="absolute -bottom-32 -right-20 h-80 w-80 rounded-full bg-pitaya-leaf/15 blur-3xl" />

      <main className="relative min-h-screen flex items-center justify-center px-4 sm:px-6 py-10">
        <motion.section
          initial={{ opacity: 0, scale: 0.985 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.7, ease: 'easeOut' }}
          className="w-full max-w-md text-center"
          aria-label="PITAYA loading screen"
        >
          <div className="bg-white/70 backdrop-blur-md border border-pitaya-leaf/20 rounded-2xl shadow-card px-6 sm:px-8 py-10">
            <div className="mx-auto w-24 h-24 sm:w-28 sm:h-28 rounded-3xl bg-white/70 backdrop-blur-sm border border-pitaya-leaf/20 shadow-card flex items-center justify-center">
              <img
                src={logoUrl}
                alt="PITAYA logo"
                className="w-14 h-14 sm:w-16 sm:h-16 object-contain"
                draggable={false}
              />
            </div>

            <h1 className="mt-5 font-display font-extrabold text-4xl sm:text-5xl text-pitaya-deep tracking-tight">
              PITAYA
            </h1>
            <p className="mt-2 text-sm sm:text-base text-pitaya-primary font-medium">
              Smart Farming Through AI and Precision Technology
            </p>

            <div className="mt-8">
              <div
                className="w-full h-2 rounded-full bg-white/60 overflow-hidden border border-pitaya-leaf/15"
                role="progressbar"
                aria-label="Loading"
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={Math.round(progress)}
              >
                <motion.div
                  className="h-full bg-pitaya-mint"
                  initial={false}
                  animate={{ width: `${progress}%` }}
                  transition={{ duration: 0.12, ease: 'linear' }}
                />
              </div>
              <div className="mt-4 flex items-center justify-center gap-2 text-sm text-gray-700 dark:text-gray-200">
                <span className="inline-flex h-4 w-4 rounded-full border-2 border-pitaya-leaf border-t-transparent animate-spin" aria-hidden />
                <span className="font-medium">{connectionLabel}</span>
              </div>
            </div>
          </div>

          <p className="mt-4 text-xs text-gray-600 dark:text-gray-300">
            Loading the AI-powered farming workspace
          </p>
        </motion.section>
      </main>
    </div>
  )
}
