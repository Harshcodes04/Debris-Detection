import { LucideIcon } from 'lucide-react'

interface StatCardProps {
  title: string
  value: string | number
  subtext?: string
  trend?: string
  trendType?: 'positive' | 'negative' | 'neutral'
  icon: LucideIcon
  color?: 'wreck' | 'rose' | 'amber' | 'emerald' | 'indigo'
}

export function StatCard({
  title,
  value,
  subtext,
  trend,
  trendType = 'positive',
  icon: Icon,
  color = 'wreck',
}: StatCardProps) {
  const colorMap = {
    wreck: {
      border: 'border-wreck/30',
      bg: 'bg-wreck/10',
      text: 'text-wreck',
      glow: 'hover:border-line-bright',
    },
    rose: {
      border: 'border-ghost/30',
      bg: 'bg-ghost/10',
      text: 'text-ghost',
      glow: 'hover:border-line-bright',
    },
    amber: {
      border: 'border-hazard/30',
      bg: 'bg-hazard/10',
      text: 'text-hazard',
      glow: 'hover:shadow-glow-amber',
    },
    emerald: {
      border: 'border-safe/30',
      bg: 'bg-safe/10',
      text: 'text-safe',
      glow: 'hover:border-line-bright',
    },
    indigo: {
      border: 'border-indigo-500/30',
      bg: 'bg-indigo-500/10',
      text: 'text-indigo-400',
      glow: 'hover:shadow-indigo-500/20',
    },
  }

  const activeColor = colorMap[color]

  return (
    <div
      className={`group relative overflow-hidden rounded-md border border-line bg-panel/70 p-5 bg-clip-padding transition-all duration-300 hover:border-line-bright ${activeColor.glow}`}
    >
      {/* Top row: Icon & Trend */}
      <div className="flex items-center justify-between">
        <div className={`flex h-10 w-10 items-center justify-center rounded-lg border ${activeColor.border} ${activeColor.bg} ${activeColor.text}`}>
          <Icon className="h-5 w-5 transition-transform group-hover:scale-110" />
        </div>
        {trend && (
          <span
            className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-mono font-medium ${
              trendType === 'positive'
                ? 'bg-safe/10 text-safe border border-safe/30'
                : trendType === 'negative'
                ? 'bg-ghost/10 text-ghost border border-ghost/30'
                : 'bg-slate-500/10 text-slate-400 border border-slate-500/30'
            }`}
          >
            {trend}
          </span>
        )}
      </div>

      {/* Main Value */}
      <div className="mt-4">
        <div className="font-mono text-2xl lg:text-3xl font-bold tracking-tight text-white">
          {value}
        </div>
        <div className="mt-1 text-xs font-medium text-slate-300">
          {title}
        </div>
      </div>

      {/* Subtext */}
      {subtext && (
        <div className="mt-2 text-[11px] text-muted leading-tight border-t border-line/50 pt-2">
          {subtext}
        </div>
      )}
    </div>
  )
}
