/**
 * Severity badge: Low / Medium / High with color and icon.
 */
const config = {
  low: {
    label: 'Low',
    className: 'bg-emerald-100 text-emerald-800 border-emerald-200',
    icon: '○',
  },
  medium: {
    label: 'Medium',
    className: 'bg-amber-100 text-amber-800 border-amber-200',
    icon: '◐',
  },
  high: {
    label: 'High',
    className: 'bg-red-100 text-red-800 border-red-200',
    icon: '●',
  },
}

export default function SeverityBadge({ severity = 'medium' }) {
  const s = config[severity] || config.medium
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border ${s.className}`}
      role="status"
    >
      <span aria-hidden>{s.icon}</span>
      {s.label}
    </span>
  )
}
