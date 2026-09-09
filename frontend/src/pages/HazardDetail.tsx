import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Anchor, Waves, Fish, Clock, AlertTriangle, MapPin } from 'lucide-react'
import { getRecoveryPlan, getRegistry } from '../api'
import { StatusBadge } from '../components/StatusBadge'
import { Failed, Loading, Wrap } from '../components/Shell'

const BAND_CLASS: Record<string, string> = {
  HIGH: 'border-ghost/40 bg-ghost/10 text-rose-300',
  MEDIUM: 'border-hazard/40 bg-hazard/10 text-amber-300',
  LOW: 'border-safe/40 bg-safe/10 text-emerald-300',
}

function Field({ label, value, hint }: { label: string; value: React.ReactNode; hint?: string }) {
  return (
    <div className="border-t border-line/60 py-3">
      <div className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted">{label}</div>
      <div className="mt-1 font-mono text-sm text-slate-100">{value}</div>
      {hint && <div className="mt-0.5 text-[11px] text-muted">{hint}</div>}
    </div>
  )
}

function Card({
  icon,
  title,
  children,
}: {
  icon: React.ReactNode
  title: string
  children: React.ReactNode
}) {
  return (
    <section className="rounded-md border border-line bg-panel/60 p-5">
      <div className="mb-1 flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.12em] text-muted">
        {icon}
        {title}
      </div>
      {children}
    </section>
  )
}

export default function HazardDetail() {
  const { id = '' } = useParams()
  const registry = useQuery({ queryKey: ['registry'], queryFn: getRegistry })
  const plan = useQuery({
    queryKey: ['recovery-plan', id],
    queryFn: () => getRecoveryPlan(id),
    enabled: Boolean(id),
  })

  const hazard = registry.data?.find((h) => h.hazard_id === id)
  const ctx = plan.data?.context
  const risk = plan.data?.risk

  return (
    <Wrap>
      <Link
        to="/map"
        className="inline-flex items-center gap-1.5 font-mono text-xs text-muted hover:text-wreck"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        Back to map
      </Link>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-b border-line pb-5">
        <div>
          <h1 className="font-mono text-2xl font-bold tracking-tight text-white">{id}</h1>
          <p className="mt-1 text-sm text-muted">
            {hazard
              ? `${hazard.class} - seen ${hazard.times_seen}×, last on ${hazard.last_seen}`
              : 'Hazard record'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {hazard && <StatusBadge status={hazard.status} />}
          {risk && (
            <span
              className={`rounded-full border px-3 py-1 font-mono text-xs ${
                BAND_CLASS[risk.band] ?? BAND_CLASS.LOW
              }`}
            >
              RISK {risk.band} {risk.score.toFixed(2)}
            </span>
          )}
        </div>
      </div>

      {registry.error && <div className="mt-4"><Failed error={registry.error} /></div>}
      {plan.isLoading && <div className="mt-4"><Loading what="hazard detail" /></div>}
      {plan.error && <div className="mt-4"><Failed error={plan.error} /></div>}

      {!registry.isLoading && !hazard && (
        <p className="mt-6 text-sm text-muted">
          No hazard with this id is in the registry. It may have been recorded in a survey that has
          since been removed.
        </p>
      )}

      <div className="mt-6 grid gap-5 md:grid-cols-2">
        {hazard && (
          <Card icon={<MapPin className="h-3.5 w-3.5 text-wreck" />} title="Position">
            <Field label="Latitude" value={hazard.lat.toFixed(7)} />
            <Field label="Longitude" value={hazard.lon.toFixed(7)} />
            <Field label="Class" value={hazard.class} />
            <Field
              label="Sightings"
              value={`${hazard.times_seen}×`}
              hint={hazard.surveys.length ? `Surveys: ${hazard.surveys.join(', ')}` : undefined}
            />
            <Field label="Last seen" value={hazard.last_seen} />
          </Card>
        )}

        {ctx && (
          <Card icon={<Waves className="h-3.5 w-3.5 text-wreck" />} title="Site">
            <Field
              label="Water depth"
              value={ctx.depth_m === null ? 'unavailable' : `${ctx.depth_m} m`}
              hint="GEBCO 2020, ~450 m grid - the depth of the area, not the object"
            />
            <Field
              label="Diveable"
              value={ctx.diveable === null ? 'unknown' : ctx.diveable ? 'yes' : 'no - beyond dive limits'}
            />
            {ctx.nearest_port && (
              <Field
                label="Nearest port"
                value={`${ctx.nearest_port.port} - ${ctx.nearest_port.distance_km} km`}
                hint={ctx.nearest_port.note}
              />
            )}
            {ctx.biodiversity && (
              <Field
                label="Marine life nearby"
                value={
                  <span className="inline-flex items-center gap-1.5">
                    <Fish className="h-3.5 w-3.5 text-wreck" />
                    {ctx.biodiversity.species} species, {ctx.biodiversity.records} records
                  </span>
                }
                hint={`OBIS, within ${ctx.biodiversity.radius_km} km`}
              />
            )}
          </Card>
        )}

        {plan.data && (
          <Card icon={<Anchor className="h-3.5 w-3.5 text-wreck" />} title="Recovery">
            <Field
              label="Recoverable"
              value={plan.data.recoverable ? 'yes' : 'no - survey and mark only'}
            />
            <Field label="Method" value={plan.data.method} />
            {plan.data.transit_hours !== null && (
              <Field label="Transit" value={`${plan.data.transit_hours} h each way`} />
            )}
            <Field label="Setup" value={`${plan.data.setup_hours} h`} />
            <Field label="On site" value={`${plan.data.on_site_hours} h`} />
            <Field
              label="Total"
              value={
                <span className="inline-flex items-center gap-1.5">
                  <Clock className="h-3.5 w-3.5 text-wreck" />
                  {plan.data.total_hours === null ? 'needs a real position' : `${plan.data.total_hours} h`}
                </span>
              }
            />
            {plan.data.notes.length > 0 && (
              <ul className="mt-3 space-y-1.5 border-t border-line/60 pt-3 text-[11px] text-muted">
                {plan.data.notes.map((n) => (
                  <li key={n} className="flex gap-2">
                    <span className="text-wreck">-</span>
                    {n}
                  </li>
                ))}
              </ul>
            )}
          </Card>
        )}

        {risk && (
          <Card icon={<AlertTriangle className="h-3.5 w-3.5 text-wreck" />} title="Why this score">
            <div className="grid grid-cols-4 gap-2 pb-1 pt-2">
              {Object.entries(risk.components).map(([k, v]) => (
                <div key={k} className="rounded-lg border border-line/60 bg-marine-950/40 p-2 text-center">
                  <div className="font-mono text-sm text-slate-100">{v.toFixed(2)}</div>
                  <div className="mt-0.5 font-mono text-[9px] uppercase tracking-wider text-muted">
                    {k}
                  </div>
                </div>
              ))}
            </div>
            <ul className="mt-2 space-y-1.5 border-t border-line/60 pt-3 text-[11px] text-muted">
              {risk.reasons.map((r) => (
                <li key={r} className="flex gap-2">
                  <span className="text-wreck">-</span>
                  {r}
                </li>
              ))}
            </ul>
          </Card>
        )}
      </div>

      {ctx?.sources?.length ? (
        <p className="mt-6 font-mono text-[11px] text-muted">
          Sources: {ctx.sources.join(' · ')}
        </p>
      ) : null}
    </Wrap>
  )
}
