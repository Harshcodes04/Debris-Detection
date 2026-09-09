import { useMemo, useState } from 'react'
import { useMutation, useQueries, useQuery } from '@tanstack/react-query'
import { Compass, Clock, CheckCircle2, Play } from 'lucide-react'
import { getDayPlan, getRecoveryPlan, getRegistry } from '../api'
import type { RecoveryPlan } from '../types'
import { Empty, Failed, Loading, Wrap } from '../components/Shell'

export default function Recovery() {
  const [hours, setHours] = useState(8)

  const { data: hazards, isLoading, error } = useQuery({
    queryKey: ['registry'],
    queryFn: getRegistry,
  })

  // Filter hazards requiring recovery
  const live = useMemo(
    () => (hazards ?? []).filter((h) => h.status === 'present' || h.status === 'unconfirmed'),
    [hazards],
  )

  const plans = useQueries({
    queries: live.map((h) => ({
      queryKey: ['recovery', h.hazard_id],
      queryFn: () => getRecoveryPlan(h.hazard_id),
      staleTime: 5 * 60_000,
    })),
  })

  const day = useMutation({
    mutationFn: () => getDayPlan(live.map((h) => h.hazard_id), hours),
  })

  if (isLoading) return <Wrap><Loading what="Loading Recovery Target Hazards..." /></Wrap>
  if (error) return <Wrap><Failed error={error} /></Wrap>

  const ready = plans.filter((p) => p.data).map((p) => p.data as RecoveryPlan)
  const pending = plans.filter((p) => p.isLoading).length
  const chosen = new Set(day.data?.items.map((i) => i.hazard_id) ?? [])

  return (
    <Wrap>
      {/* Header Info */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-line pb-5">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-wreck/30 bg-wreck/10 px-3 py-0.5 text-xs font-mono text-wreck mb-1">
            <Compass className="h-3.5 w-3.5 text-wreck" />
            SALVAGE & RECOVERY OPTIMIZER
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white">
            Operational Recovery Planner
          </h1>
          <p className="mt-1 text-sm text-muted">
            Depth-based mission planning ordering hazards by risk per operational hour and vessel transit constraints.
          </p>
        </div>
      </div>

      {/* Operational Working Day Scheduler Controls */}
      <div className="mt-6 flex flex-wrap items-center justify-between gap-4 rounded-md border border-line bg-panel/60 p-5 bg-clip-padding shadow-lg">
        <div className="flex items-center gap-4">
          <Clock className="h-5 w-5 text-wreck" />
          <div>
            <label htmlFor="hours" className="text-xs font-bold text-white uppercase font-mono">
              Working Day Window
            </label>
            <div className="flex items-center gap-3 mt-1">
              <input
                id="hours"
                type="range"
                min={4}
                max={12}
                step={0.5}
                value={hours}
                onChange={(e) => setHours(Number(e.target.value))}
                className="w-36 lg:w-48 accent-wreck cursor-pointer"
              />
              <span className="font-mono text-base font-bold text-wreck">{hours} Hours</span>
            </div>
          </div>
        </div>

        <button
          onClick={() => day.mutate()}
          disabled={!live.length || day.isPending}
          className="inline-flex items-center gap-2 rounded-md border border-wreck/40 bg-wreck px-5 py-2.5 text-xs font-bold text-marine-950 hover:bg-wreck/90 transition-all disabled:opacity-40 shadow-none"
        >
          <Play className="h-3.5 w-3.5 fill-current" />
          {day.isPending ? 'Optimizing Plan...' : 'Generate Day Mission Plan'}
        </button>
      </div>

      {day.error && <div className="mt-4"><Failed error={day.error} /></div>}

      {/* Generated Day Plan Summary */}
      {day.data && (
        <div className="mt-6 rounded-md border border-wreck/40 bg-wreck/10 p-5 text-xs bg-clip-padding shadow-none">
          <div className="font-bold text-slate-100 text-sm flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-wreck" />
            {day.data.hours_planned.toFixed(1)} h planned of {day.data.hours_available} h available ·{' '}
            {day.data.items.length} hazards scheduled · {day.data.deferred} deferred
          </div>
          <p className="mt-1 text-muted font-mono">{day.data.note}</p>
        </div>
      )}

      {pending > 0 && (
        <div className="mt-4"><Loading what={`Costing ${pending} hazard(s)...`} /></div>
      )}

      {/* Hazard Recovery Cards List */}
      {!live.length ? (
        <div className="mt-6"><Empty>Nothing in the registry needs recovering.</Empty></div>
      ) : (
        <div className="mt-6 space-y-4">
          {ready.map((plan) => {
            const inDay = chosen.has(plan.hazard_id)
            return (
              <div
                key={plan.hazard_id}
                className={`rounded-md border p-5 transition-all bg-clip-padding ${
                  inDay
                    ? 'border-wreck/50 bg-wreck/10 shadow-none'
                    : 'border-line bg-panel/40 hover:border-line-bright'
                }`}
              >
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-sm font-bold text-wreck">{plan.hazard_id}</span>
                    <span className="text-sm font-semibold text-white">{plan.cls}</span>
                    {inDay && (
                      <span className="rounded-full bg-wreck/20 px-2.5 py-0.5 font-mono text-[10px] text-wreck font-bold border border-wreck/40">
                        SCHEDULED TODAY
                      </span>
                    )}
                    {!plan.recoverable && (
                      <span className="rounded-full bg-slate-500/20 px-2.5 py-0.5 font-mono text-[10px] text-muted border border-slate-500/30">
                        NOT RECOVERABLE
                      </span>
                    )}
                  </div>
                  <span className="font-mono text-sm font-bold text-slate-200">
                    Est. {plan.total_hours ? `${plan.total_hours} h` : '—'}
                  </span>
                </div>

                <div className="mt-3 text-xs text-muted flex items-center gap-2">
                  <span className="text-slate-200 font-medium">{plan.method}</span>
                  {plan.transit_hours != null && (
                    <>
                      <span>·</span>
                      <span className="font-mono">{plan.transit_hours} h transit each way</span>
                    </>
                  )}
                </div>

                {plan.notes.length > 0 && (
                  <ul className="mt-3 space-y-1 text-xs text-muted border-t border-line/50 pt-2 font-mono">
                    {plan.notes.map((n) => (
                      <li key={n} className="flex items-center gap-1.5">
                        <span className="h-1 w-1 rounded-full bg-wreck" />
                        {n}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )
          })}
        </div>
      )}
    </Wrap>
  )
}
