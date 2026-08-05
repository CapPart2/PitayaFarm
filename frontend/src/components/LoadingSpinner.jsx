import { motion } from 'framer-motion'

export default function LoadingSpinner({ className = '' }) {
  return (
    <div className={`flex items-center justify-center min-h-[200px] ${className}`}>
      <motion.div
        animate={{ rotate: 360 }}
        transition={{ repeat: Infinity, duration: 0.8, ease: 'linear' }}
        className="w-10 h-10 border-2 border-pitaya-primary border-t-transparent rounded-full"
      />
    </div>
  )
}
