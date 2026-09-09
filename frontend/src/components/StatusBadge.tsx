

interface StatusBadgeProps {
  status: string
  label?: string
  pulse?: boolean
}

export function StatusBadge({ status, label, pulse = false }: StatusBadgeProps) {
  const s = status.toLowerCase()
  const displayLabel = label || status

  let classes = 'bg-slate-500/10 text-slate-400 border-slate-500/30'
  let dotColor = 'bg-slate-400'

  if (s === 'present' || s === 'completed' || s === 'online' || s === 'active' || s === 'high') {
    classes = 'bg-wreck/10 text-wreck border-wreck/30'
    dotColor = 'bg-wreck'
  } else if (s === 'unconfirmed' || s === 'flagged' || s === 'processing' || s === 'queued' || s === 'medium') {
    classes = 'bg-hazard/10 text-hazard border-hazard/30'
    dotColor = 'bg-hazard'
  } else if (s === 'recovered' || s === 'safe' || s === 'resolved' || s === 'low') {
    classes = 'bg-safe/10 text-safe border-safe/30'
    dotColor = 'bg-safe'
  } else if (s === 'failed' || s === 'critical' || s === 'offline' || s === 'gone') {
    classes = 'bg-ghost/10 text-ghost border-ghost/30'
    dotColor = 'bg-ghost'
  }

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-mono font-medium transition-colors ${classes}`}
    >
      <span className="relative flex h-1.5 w-1.5">
        {pulse && (
          <span
            className={`absolute inline-flex h-full w-full opacity-0 rounded-full ${dotColor} opacity-75`}
          />
        )}
        <span className={`relative inline-flex h-1.5 w-1.5 rounded-full ${dotColor}`} />
      </span>
      {displayLabel}
    </span>
  )
}
