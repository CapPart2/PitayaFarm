import { motion } from 'framer-motion'
import { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'

const buttonBase =
  'min-h-[44px] px-6 py-3 rounded-xl font-semibold shadow-card transition-all duration-300 active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-pitaya-mint focus-visible:ring-offset-2 focus-visible:ring-offset-white'

export default function GetStarted() {
  const navigate = useNavigate()
  const logoUrl = useMemo(() => `${import.meta.env.BASE_URL}pitaya-logo.png`, [])

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
          aria-label="Get started"
        >
          <div className="bg-white/75 backdrop-blur-md border border-pitaya-leaf/20 rounded-2xl shadow-card px-6 sm:px-8 py-8 text-center">
            <div className="flex items-center justify-center">
              <div className="w-16 h-16 rounded-2xl bg-pitaya-pale border border-pitaya-leaf/20 flex items-center justify-center">
                <img src={logoUrl} alt="" className="w-10 h-10 object-contain" draggable={false} />
              </div>
            </div>

            <h1 className="mt-4 font-display font-bold text-2xl text-pitaya-deep dark:text-pitaya-light">Welcome to PITAYA</h1>
            <p className="mt-2 text-sm sm:text-base text-gray-600 dark:text-gray-300 leading-relaxed">
              Detect diseases and assess yield using AI-powered technology — built for dragon fruit farming.
            </p>

            <motion.button
              type="button"
              onClick={() => navigate('/login')}
              className={`${buttonBase} mt-6 w-full bg-pitaya-primary text-white hover:bg-pitaya-leaf hover:shadow-card-hover`}
              whileHover={{ scale: 1.01 }}
              whileTap={{ scale: 0.99 }}
            >
              Continue
            </motion.button>

            <button
              type="button"
              onClick={() => navigate('/landing')}
              className="mt-3 w-full min-h-[44px] rounded-xl border border-pitaya-leaf/20 bg-white/60 px-6 py-3 text-sm font-semibold text-pitaya-deep transition-colors hover:bg-white"
            >
              Back to Landing
            </button>
          </div>
        </motion.section>
      </main>
    </div>
  )
}
