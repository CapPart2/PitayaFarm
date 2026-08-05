import { motion } from 'framer-motion'
import { useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'

export default function Loading() {
  const navigate = useNavigate()
  const logoUrl = useMemo(() => `${import.meta.env.BASE_URL}logoCaps.png`, [])

  useEffect(() => {
    const timer = window.setTimeout(() => {
      navigate('/landing', { replace: true })
    }, 10000)

    return () => window.clearTimeout(timer)
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
              >
                <motion.div
                  className="h-full bg-pitaya-mint"
                  initial={{ width: '0%' }}
                  animate={{ width: '100%' }}
                  transition={{ duration: 10, ease: 'linear' }}
                />
              </div>
              <div className="mt-4 flex items-center justify-center gap-2 text-sm text-gray-700 dark:text-gray-200">
                <span className="inline-flex h-4 w-4 rounded-full border-2 border-pitaya-leaf border-t-transparent animate-spin" aria-hidden />
                <span className="font-medium">Initializing PITAYA…</span>
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
