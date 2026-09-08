import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  Radar,
  Database,
  Map,
  Compass,
  Layers,
  BarChart3,
  Activity,
  Menu,
  X,
  ShieldCheck,
  Zap,
} from 'lucide-react'

const NAV_ITEMS = [
  { to: '/dashboard', label: 'Intelligence Hub', icon: LayoutDashboard },
  { to: '/detect', label: 'Sonar Upload & AI', icon: Radar },
  { to: '/hazards', label: 'Hazard Registry', icon: Database },
  { to: '/map', label: 'Spatial Risk Map', icon: Map },
  { to: '/recovery', label: 'Recovery Planner', icon: Compass },
  { to: '/annotate', label: 'Active Queue', icon: Layers },
  { to: '/about', label: 'Model Benchmarks', icon: BarChart3 },
]

export function Sidebar() {
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <>
      {/* Mobile Toggle Button */}
      <button
        onClick={() => setMobileOpen(!mobileOpen)}
        className="fixed bottom-4 right-4 z-50 flex h-12 w-12 items-center justify-center rounded-full border border-line bg-panel text-wreck shadow-glow-cyan md:hidden"
        aria-label="Toggle Navigation"
      >
        {mobileOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
      </button>

      {/* Mobile Overlay */}
      {mobileOpen && (
        <div
          onClick={() => setMobileOpen(false)}
          className="fixed inset-0 z-40 bg-ink/80 backdrop-blur-sm md:hidden"
        />
      )}

      {/* Sidebar Container */}
      <aside
        className={`fixed bottom-0 top-0 z-40 flex w-64 flex-col border-r border-line bg-marine-900/95 transition-transform duration-300 backdrop-blur-md md:static md:translate-x-0 ${
          mobileOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {/* Logo Brand Header */}
        <div className="flex items-center gap-3 border-b border-line px-5 py-4">
          <div className="relative flex h-10 w-10 items-center justify-center rounded-xl border border-wreck/40 bg-wreck/10 text-wreck shadow-glow-cyan">
            <Radar className="h-5 w-5" />
            <span className="absolute -right-0.5 -top-0.5 flex h-2.5 w-2.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-wreck opacity-75" />
              <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-wreck" />
            </span>
          </div>
          <div>
            <div className="flex items-center gap-1.5 font-bold tracking-wider text-white text-base">
              AQUASCAN <span className="text-wreck font-mono text-xs">AI</span>
            </div>
            <div className="text-[11px] text-muted tracking-tight">
              Seabed Sonar Intelligence
            </div>
          </div>
        </div>

        {/* Navigation Items */}
        <nav className="flex-1 space-y-1.5 px-3 py-4 overflow-y-auto">
          <div className="px-3 pb-2 text-[10px] font-mono font-semibold uppercase tracking-widest text-muted/70">
            Navigation Menu
          </div>
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon
            return (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={() => setMobileOpen(false)}
                className={({ isActive }) =>
                  `group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all ${
                    isActive
                      ? 'border border-wreck/30 bg-wreck/10 text-wreck shadow-glow-cyan'
                      : 'text-muted hover:border hover:border-line hover:bg-panel/60 hover:text-slate-100'
                  }`
                }
              >
                <Icon className="h-4 w-4 shrink-0 transition-transform group-hover:scale-110" />
                <span>{item.label}</span>
              </NavLink>
            )
          })}
        </nav>

        {/* Status System Card Footer */}
        <div className="border-t border-line p-4 bg-marine-950/60">
          <div className="rounded-xl border border-line-bright bg-panel/80 p-3 text-xs">
            <div className="flex items-center justify-between font-medium text-slate-200">
              <span className="flex items-center gap-1.5">
                <ShieldCheck className="h-3.5 w-3.5 text-safe" />
                YOLO Dual Head
              </span>
              <span className="inline-flex items-center gap-1 text-[10px] font-mono text-safe">
                <span className="h-1.5 w-1.5 rounded-full bg-safe animate-pulse" />
                ONLINE
              </span>
            </div>
            <div className="mt-2 flex items-center justify-between text-[11px] text-muted">
              <span className="flex items-center gap-1">
                <Zap className="h-3 w-3 text-amber-400" /> Latency
              </span>
              <span className="font-mono text-slate-300">~18.4 ms</span>
            </div>
            <div className="mt-1 flex items-center justify-between text-[11px] text-muted">
              <span className="flex items-center gap-1">
                <Activity className="h-3 w-3 text-wreck" /> Model Ver
              </span>
              <span className="font-mono text-slate-300">v2.4-Marine</span>
            </div>
          </div>
          <div className="mt-3 text-center text-[10px] text-muted/60 font-mono">
            SIH PS57 · PING Ecosystem CC-BY-4.0
          </div>
        </div>
      </aside>
    </>
  )
}
