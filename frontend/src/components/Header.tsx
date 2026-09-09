import { NavLink } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { LogOut, Radio } from 'lucide-react'
import { getRegistry } from '../api'
import { useSession } from '../auth'

export function Header() {
  // The telemetry read a fixed North Sea position that nothing set. Show the
  // most recently recorded hazard instead, or say plainly that there is none.
  const { account, signOut, can } = useSession()
  const { data: hazards } = useQuery({ queryKey: ['registry'], queryFn: getRegistry })
  const latest = hazards?.length ? hazards[hazards.length - 1] : null
  const position = latest
    ? `${Math.abs(latest.lat).toFixed(4)}°${latest.lat >= 0 ? 'N' : 'S'} • ` +
      `${Math.abs(latest.lon).toFixed(4)}°${latest.lon >= 0 ? 'E' : 'W'}`
    : 'NO SURVEY LOADED'
  const navItems = [
    { label: 'Detect', path: '/detect' },
    { label: 'Registry', path: '/hazards' },
    { label: 'Map', path: '/map' },
    { label: 'Recovery', path: '/recovery' },
    { label: 'Annotate', path: '/annotate' },
    { label: 'Performance', path: '/about' },
      ...(can('admin') ? [{ label: 'Accounts', path: '/accounts' }] : []),
  ]

  return (
    <header className="sticky top-0 z-50 border-b border-[#26262a] bg-[#0c0c0d]/95 bg-clip-padding px-6 py-3 text-slate-100">
      <div className="flex flex-wrap items-center justify-between gap-4 max-w-[1600px] mx-auto">
        {/* Left Branding & Active Status */}
        <div className="flex items-center gap-3">
          {/* Sonar Icon */}
          <div className="flex h-9 w-9 items-center justify-center rounded border border-[#26262a] bg-[#141416] text-[#8a8a91]">
            <Radio className="h-4 w-4" />
          </div>

          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-base font-bold tracking-tight text-white font-sans">
                Seabed Anomaly Detection
              </h1>
            </div>
            <p className="text-[11px] text-[#6e6e75]">
              Side-scan sonar, ghost gear and wrecks — two heads loaded
            </p>
          </div>
        </div>

        {/* Center Navigation Links */}
        <nav className="flex items-center gap-1.5 bg-[#161617]/80 p-1 rounded-lg border border-[#26262a]">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `px-3.5 py-1 rounded text-xs font-mono transition-all ${
                  isActive
                    ? 'border border-[#6d8bab] bg-[#6d8bab]/15 text-[#6d8bab] font-semibold shadow-[0_0_10px_rgba(0,242,255,0.2)]'
                    : 'text-[#8a8a91] hover:text-white hover:bg-[#14223d]/50'
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        {/* Two boxed badges for one fact each was more chrome than the fact
            deserved. One line, and the model names moved to the tagline. */}
        <div className="flex items-center gap-4 text-xs">
          <div className="hidden lg:block text-right">
            <span className="text-[#6e6e75]">Last hazard </span>
            <span className="font-mono text-[#c9c9cd]">{position}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="hidden sm:inline text-[#6e6e75]">
              {account?.full_name || account?.email}
              <span className="ml-1.5 text-[#4a4a50]">({account?.role})</span>
            </span>
            <button
              type="button"
              onClick={signOut}
              title="Sign out"
              className="flex items-center gap-1.5 rounded border border-line px-2 py-1 text-[#8a8a91] transition-colors hover:border-line-bright hover:text-slate-200"
            >
              <LogOut className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Sign out</span>
            </button>
          </div>
        </div>
      </div>
    </header>
  )
}
