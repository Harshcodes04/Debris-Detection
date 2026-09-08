

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
    classes = 'bg-amber-500/10 text-amber-400 border-amber-500/30'
    dotColor = 'bg-amber-400'
  } else if (s === 'recovered' || s === 'safe' || s === 'resolved' || s === 'low') {
    classes = 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
    dotColor = 'bg-emerald-400'
  } else if (s === 'failed' || s === 'critical' || s === 'offline' || s === 'gone') {
    classes = 'bg-rose-500/10 text-rose-400 border-rose-500/30'
    dotColor = 'bg-rose-400'
  }

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-mono font-medium transition-colors ${classes}`}
    >
      <span className="relative flex h-1.5 w-1.5">
        {pulse && (
          <span
            className={`absolute inline-flex h-full w-full animate-ping rounded-full ${dotColor} opacity-75`}
          />
        )}
        <span className={`relative inline-flex h-1.5 w-1.5 rounded-full ${dotColor}`} />
      </span>
      {displayLabel}
    </span>
  )
}
