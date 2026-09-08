import { Link } from 'react-router-dom'
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Database, Search, ShieldAlert, MapPin } from 'lucide-react'
import { getRegistry } from '../api'
import { Empty, Failed, Loading, Wrap } from '../components/Shell'
import { StatusBadge } from '../components/StatusBadge'

export default function Hazards() {
  const [filter, setFilter] = useState<'all' | 'present' | 'unconfirmed' | 'recovered'>('all')
  const [search, setSearch] = useState('')

  const { data, isLoading, error } = useQuery({
    queryKey: ['registry'],
    queryFn: getRegistry,
  })

  if (isLoading) return <Wrap wide><Loading what="Fetching Seabed Hazard Registry..." /></Wrap>
  if (error) return <Wrap wide><Failed error={error} /></Wrap>

  const hazards = data ?? []

  // Filtering & search
  const filtered = hazards.filter((h) => {
    const matchesFilter = filter === 'all' || h.status === filter
    const matchesSearch =
      search === '' ||
      h.hazard_id.toLowerCase().includes(search.toLowerCase()) ||
      h.class.toLowerCase().includes(search.toLowerCase()) ||
      (h.note && h.note.toLowerCase().includes(search.toLowerCase()))
    return matchesFilter && matchesSearch
  })

  const confirmedCount = hazards.filter((h) => h.times_seen > 1 && h.status !== 'recovered').length

  return (
    <Wrap wide>
      {/* Header Info */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-line pb-5">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-wreck/30 bg-wreck/10 px-3 py-0.5 text-xs font-mono text-wreck mb-1">
            <Database className="h-3.5 w-3.5 text-wreck" />
            CROSS-SURVEY REGISTRY
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white">
            Seabed Debris Hazard Registry
          </h1>
          <p className="mt-1 text-sm text-muted">
            Aggregated target registry matched across multiple side-scan sonar passes using geospatial tolerance algorithms.
          </p>
        </div>

        <div className="flex items-center gap-2 rounded-xl border border-line bg-panel/70 p-1">
          {(['all', 'present', 'unconfirmed', 'recovered'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setFilter(tab)}
              className={`rounded-lg px-3 py-1.5 text-xs font-mono capitalize transition-all ${
                filter === tab
                  ? 'bg-wreck/20 text-wreck font-semibold border border-wreck/30'
                  : 'text-muted hover:text-slate-200'
              }`}
            >
              {tab}
            </button>
          ))}
        </div>
      </div>

      {/* Confirmed Alert Banner */}
      {confirmedCount > 0 && (
        <div className="mt-6 flex items-center justify-between rounded-xl border border-wreck/40 bg-wreck/10 p-4 text-xs backdrop-blur-sm shadow-glow-cyan">
          <div className="flex items-center gap-3">
            <ShieldAlert className="h-5 w-5 text-wreck shrink-0" />
            <div>
              <strong className="font-bold text-white text-sm">
                {confirmedCount} Confirmed & Uncollected Targets
              </strong>
              <div className="text-muted mt-0.5">
                Sighted across multiple independent sonar transects with high spatial correlation.
              </div>
            </div>
          </div>
          <span className="hidden md:inline-block font-mono text-[11px] text-wreck bg-marine-950 px-3 py-1 rounded-lg border border-wreck/30">
            HIGH RECOVERY PRIORITY
          </span>
        </div>
      )}

      {/* Search & Stats Filter */}
      <div className="mt-6 flex flex-wrap items-center justify-between gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted" />
          <input
            type="text"
            placeholder="Filter by Hazard ID, Class, or Note..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-xl border border-line bg-panel/70 pl-9 pr-4 py-2 text-xs text-slate-200 placeholder-muted/60 focus:border-wreck/50 focus:outline-none"
          />
        </div>
        <div className="text-xs font-mono text-muted">
          Showing <span className="text-slate-200 font-bold">{filtered.length}</span> of {hazards.length} hazards
        </div>
      </div>

      {/* Registry Table */}
      {!filtered.length ? (
        <div className="mt-6">
          <Empty>No hazards found matching current filters.</Empty>
        </div>
      ) : (
        <div className="mt-6 overflow-x-auto rounded-2xl border border-line bg-panel/60 backdrop-blur-sm">
          <table className="w-full text-xs text-left">
            <thead className="bg-marine-950 font-mono text-muted uppercase tracking-wider border-b border-line">
              <tr>
                <th className="px-4 py-3">Hazard ID</th>
                <th className="px-4 py-3">Debris Class</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Sightings</th>
                <th className="px-4 py-3">Last Sighted</th>
                <th className="px-4 py-3">Geographic Coordinates</th>
                <th className="px-4 py-3">Field Notes</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line/60">
              {filtered.map((h) => (
                <tr key={h.hazard_id} className="hover:bg-marine-900/40 transition-colors">
                  <td className="px-4 py-3 font-mono font-bold">
                    <Link to={`/hazards/${h.hazard_id}`} className="text-wreck hover:underline">
                      {h.hazard_id}
                    </Link>
                  </td>
                  <td className="px-4 py-3 font-semibold text-slate-200">{h.class}</td>
                  <td className="px-4 py-3">
                    <StatusBadge status={h.status} />
                  </td>
                  <td className="px-4 py-3 font-mono">
                    <span className="font-bold text-slate-200">{h.times_seen}×</span>
                    {h.times_seen > 1 && (
                      <span className="ml-1.5 rounded bg-wreck/10 px-1.5 py-0.5 text-[10px] text-wreck font-bold border border-wreck/20">
                        CONFIRMED
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 font-mono text-muted">{h.last_seen}</td>
                  <td className="px-4 py-3 font-mono text-slate-300">
                    <span className="flex items-center gap-1">
                      <MapPin className="h-3 w-3 text-wreck" />
                      {h.lat.toFixed(5)}, {h.lon.toFixed(5)}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-muted max-w-xs truncate" title={h.note}>
                    {h.note || '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Wrap>
  )
}
