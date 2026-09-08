import { NavLink } from 'react-router-dom'
import { Radio } from 'lucide-react'

export function Header() {
  const navItems = [
    { label: 'Detect', path: '/detect' },
    { label: 'Registry', path: '/hazards' },
    { label: 'Map', path: '/map' },
    { label: 'Recovery', path: '/recovery' },
    { label: 'Annotate', path: '/annotate' },
    { label: 'Performance', path: '/about' },
  ]

  return (
    <header className="sticky top-0 z-50 border-b border-[#141f36] bg-[#050914]/95 backdrop-blur-md px-6 py-3 text-slate-100">
      <div className="flex flex-wrap items-center justify-between gap-4 max-w-[1600px] mx-auto">
        {/* Left Branding & Active Status */}
        <div className="flex items-center gap-3">
          {/* Sonar Icon */}
          <div className="relative flex h-9 w-9 items-center justify-center rounded-lg border border-[#00f2ff]/40 bg-[#00f2ff]/10 text-[#00f2ff] shadow-[0_0_15px_rgba(0,242,255,0.2)]">
            <Radio className="h-5 w-5 animate-pulse text-[#00f2ff]" />
            <span className="absolute inset-0 rounded-lg border border-[#00f2ff]/60 animate-ping opacity-25" />
          </div>

          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-base font-bold tracking-tight text-white font-sans">
                Seabed Anomaly Detection
              </h1>
              {/* Active Badge */}
              <span className="hidden sm:inline-flex items-center gap-1.5 rounded-full border border-[#00f2ff]/40 bg-[#00f2ff]/10 px-2.5 py-0.5 text-[10px] font-mono text-[#00f2ff] shadow-[0_0_10px_rgba(0,242,255,0.15)]">
                <span className="h-1.5 w-1.5 rounded-full bg-[#10b981] animate-pulse" />
                DUAL HEAD INFERENCE ACTIVE
              </span>
            </div>
            <p className="text-[11px] text-[#64748b] font-mono tracking-tight">
              Side-scan sonar • ghost gear and wrecks • SIH PS57
            </p>
          </div>
        </div>

        {/* Center Navigation Links */}
        <nav className="flex items-center gap-1.5 bg-[#0a1122]/80 p-1 rounded-lg border border-[#141f36]">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `px-3.5 py-1 rounded text-xs font-mono transition-all ${
                  isActive
                    ? 'border border-[#00f2ff] bg-[#00f2ff]/15 text-[#00f2ff] font-semibold shadow-[0_0_10px_rgba(0,242,255,0.2)]'
                    : 'text-[#8094b8] hover:text-white hover:bg-[#14223d]/50'
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        {/* Right Telemetry & Frequency Badges */}
        <div className="hidden lg:flex items-center gap-3 font-mono text-xs">
          {/* Survey Telemetry */}
          <div className="rounded-lg border border-[#141f36] bg-[#0a1122] px-3.5 py-1.5 text-right">
            <div className="text-[9px] uppercase tracking-wider text-[#64748b] font-semibold">
              SURVEY TELEMETRY
            </div>
            <div className="text-[#00f2ff] font-bold text-xs tracking-tight">
              LAT 54°22'N • LON 03°18'E
            </div>
          </div>

          {/* SSS Frequency Badge */}
          <div className="rounded-lg border border-[#141f36] bg-[#0a1122] px-3.5 py-2 text-[#00f2ff] font-bold text-xs tracking-wider">
            120 kHz SSS
          </div>
        </div>
      </div>
    </header>
  )
}
