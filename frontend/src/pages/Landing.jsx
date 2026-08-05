import { motion } from 'framer-motion'
import { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'

const buttonBase =
  'min-h-[44px] px-6 py-3 rounded-xl font-semibold shadow-card transition-all duration-300 active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-pitaya-mint focus-visible:ring-offset-2 focus-visible:ring-offset-white'

export default function Landing() {
  const navigate = useNavigate()
  const logoUrl = useMemo(() => `${import.meta.env.BASE_URL}logoCaps.png`, [])

  return (
    <div className="min-h-screen overflow-hidden relative bg-gradient-to-br from-pitaya-bg via-white to-pitaya-pale bg-gradient animate-gradient">
      <div aria-hidden className="absolute -top-24 -left-24 h-72 w-72 rounded-full bg-pitaya-mint/20 blur-3xl" />
      <div aria-hidden className="absolute -bottom-32 -right-20 h-80 w-80 rounded-full bg-pitaya-leaf/15 blur-3xl" />

      <header className="relative z-10 px-4 sm:px-6 pt-6">
        <div className="mx-auto max-w-6xl flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-white/70 backdrop-blur-md border border-pitaya-leaf/20 shadow-card flex items-center justify-center">
              <img src={logoUrl} alt="PITAYA" className="w-6 h-6 object-contain" draggable={false} />
            </div>
            <span className="font-display font-extrabold tracking-tight text-pitaya-deep">PITAYA</span>
          </div>

          <button
            type="button"
            onClick={() => navigate('/login')}
            className="hidden sm:inline-flex min-h-[44px] items-center rounded-xl border border-pitaya-leaf/20 bg-white/60 px-5 py-2.5 text-sm font-semibold text-pitaya-deep backdrop-blur-md transition-colors hover:bg-white"
          >
            Login
          </button>
        </div>
      </header>

      <main className="relative z-10 px-4 sm:px-6 pb-12 pt-10">
        <div className="mx-auto max-w-6xl grid grid-cols-1 lg:grid-cols-2 gap-10 items-center">
          <motion.section
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: 'easeOut' }}
            aria-label="Hero"
          >
            <p className="inline-flex items-center gap-2 rounded-full border border-pitaya-leaf/20 bg-white/60 px-4 py-2 text-xs font-semibold text-pitaya-deep backdrop-blur-md">
              <span className="h-2 w-2 rounded-full bg-pitaya-mint" aria-hidden />
              Agriculture + AI
            </p>

            <h1 className="mt-5 font-display font-extrabold text-4xl sm:text-5xl lg:text-6xl text-pitaya-deep dark:text-pitaya-light tracking-tight">
              Revolutionizing Dragon Fruit Farming
            </h1>
            <p className="mt-4 text-base sm:text-lg text-gray-700 dark:text-gray-200 leading-relaxed max-w-xl">
              Detect diseases and assess yield using AI-powered technology.
            </p>

            <div className="mt-8 flex flex-col sm:flex-row gap-3 sm:items-center">
              <motion.button
                type="button"
                onClick={() => navigate('/get-started')}
                className={`${buttonBase} bg-pitaya-primary text-white hover:bg-pitaya-leaf hover:shadow-card-hover`}
                whileHover={{ scale: 1.01 }}
                whileTap={{ scale: 0.99 }}
              >
                Get Started
              </motion.button>

              <button
                type="button"
                onClick={() => {
                  const el = document.getElementById('learn-more')
                  el?.scrollIntoView({ behavior: 'smooth', block: 'start' })
                }}
                className="min-h-[44px] px-6 py-3 rounded-xl font-semibold border border-pitaya-leaf/20 bg-white/60 backdrop-blur-md text-pitaya-deep transition-colors hover:bg-white"
              >
                Learn More
              </button>
            </div>

            <p className="mt-6 text-sm text-gray-600 dark:text-gray-300">
              Smart Farming Through AI and Precision Technology
            </p>
          </motion.section>

          <motion.section
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.55, ease: 'easeOut', delay: 0.05 }}
            aria-label="Visual"
            className="lg:justify-self-end"
          >
            <div className="rounded-3xl border border-pitaya-leaf/20 bg-white/60 backdrop-blur-md shadow-card p-6 sm:p-8">
              <div className="grid grid-cols-2 gap-4">
                <div className="rounded-2xl bg-white/70 border border-pitaya-leaf/15 p-4">
                  <p className="text-xs font-semibold text-gray-500 dark:text-gray-300">Disease Detection</p>
                  <p className="mt-2 font-display font-bold text-lg text-pitaya-deep">AI Vision</p>
                  <p className="mt-1 text-sm text-gray-600 dark:text-gray-300">Fast & consistent analysis</p>
                </div>
                <div className="rounded-2xl bg-white/70 border border-pitaya-leaf/15 p-4">
                  <p className="text-xs font-semibold text-gray-500 dark:text-gray-300">Yield Assessment</p>
                  <p className="mt-2 font-display font-bold text-lg text-pitaya-deep">Prediction</p>
                  <p className="mt-1 text-sm text-gray-600 dark:text-gray-300">Estimate fruit counts</p>
                </div>
                <div className="col-span-2 rounded-2xl bg-gradient-to-br from-pitaya-pale to-white border border-pitaya-leaf/15 p-4">
                  <p className="text-xs font-semibold text-gray-500 dark:text-gray-300">Field Insight</p>
                  <p className="mt-2 text-sm text-gray-700 dark:text-gray-200 leading-relaxed">
                    Turn field observations into actionable insights with AI-assisted detection, yield estimation, and clear reporting.
                  </p>
                  <div className="mt-4 h-2 rounded-full bg-white/70 overflow-hidden border border-pitaya-leaf/10" aria-hidden>
                    <div className="h-full w-2/3 bg-pitaya-mint" />
                  </div>
                </div>
              </div>
            </div>
          </motion.section>
        </div>

        <section id="learn-more" className="mx-auto max-w-6xl mt-14">
          <div className="rounded-3xl border border-pitaya-leaf/20 bg-white/60 backdrop-blur-md shadow-card p-6 sm:p-8">
            <h2 className="font-display font-bold text-2xl text-pitaya-deep dark:text-pitaya-light">Built for real-world farming</h2>
            <p className="mt-2 text-sm sm:text-base text-gray-700 dark:text-gray-200 leading-relaxed max-w-3xl">
              PITAYA helps you monitor plant health and improve yield decisions using AI-driven detection and reporting.
            </p>
          </div>
        </section>
      </main>
    </div>
  )
}
