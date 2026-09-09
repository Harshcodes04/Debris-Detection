import { BarChart3, AlertTriangle, Cpu } from 'lucide-react'

interface Metric {
  value: string
  label: string
  detail: string
  caveat?: string
}

const DETECTION: Metric[] = [
  {
    value: '0.625',
    label: 'mAP@0.5 — Shipwrecks',
    detail: 'Shipwrecks & submerged aircraft on held-out SCTD test split',
    caveat: 'Evaluated on 39 held-out sonar images',
  },
  {
    value: '0.923',
    label: 'Precision — Wrecks',
    detail: 'When flagging a large metal anomaly, precision is 92.3%',
  },
  {
    value: '0.310',
    label: 'mAP@0.5 — Ghost Gear',
    detail: 'Derelict crab pots on survey recordings never seen in training',
    caveat: 'Ghost pots are ~23px against rippled seabed',
  },
  {
    value: '0.420',
    label: 'Precision — Ghost Gear',
    detail: 'Measured at 0.20 threshold where F1 score peaks at 0.368',
    caveat: 'Tunable: 0.10 threshold increases recall to 67%',
  },
]

const SYSTEM: Metric[] = [
  { value: '~184 ms', label: 'CPU Inference Latency', detail: 'Measured per frame on CPU without GPU acceleration' },
  { value: '7,276', label: 'Training Images', detail: 'Staged fine-tunes with 9,365 annotated target objects' },
  { value: '6,674', label: 'Ghost Gear Dataset', detail: 'Ghost Pot SSS dataset from PING Ecosystem (CC-BY-4.0)' },
  { value: '3', label: 'Public Datasets', detail: 'Fully open & cited — zero synthetic or scraped data' },
]

function Card({ m }: { m: Metric }) {
  return (
    <div className="rounded-md border border-line bg-panel/60 p-5 bg-clip-padding shadow-md hover:border-wreck/40 transition-all group">
      <div className="font-mono text-3xl font-extrabold text-wreck group-hover:scale-105 transition-transform origin-left">
        {m.value}
      </div>
      <div className="mt-2 text-xs font-medium text-slate-300">{m.label}</div>
      <div className="mt-1 text-[11px] text-muted leading-snug">{m.detail}</div>
      {m.caveat && (
        <div className="mt-3 border-t border-line/60 pt-2 text-[10px] font-mono text-hazard flex items-center gap-1">
          <AlertTriangle className="h-3 w-3 shrink-0" />
          {m.caveat}
        </div>
      )}
    </div>
  )
}

export function Metrics() {
  return (
    <section className="border-t border-line py-10">
      <div className="mx-auto max-w-7xl px-4 sm:px-6">
        <div className="inline-flex items-center gap-2 rounded-full border border-wreck/30 bg-wreck/10 px-3 py-0.5 text-xs font-mono text-wreck mb-2">
          <BarChart3 className="h-3.5 w-3.5" /> EMPIRICAL BENCHMARKS
        </div>
        <h2 className="text-2xl font-bold tracking-tight text-white">
          Held-Out Held Test Split Metrics
        </h2>
        <p className="mt-1 max-w-2xl text-sm text-muted">
          Evaluated by survey recording split rather than random split to avoid data leakage between adjacent sonar pings.
        </p>

        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {DETECTION.map((m) => (
            <Card key={m.label} m={m} />
          ))}
        </div>

        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {SYSTEM.map((m) => (
            <Card key={m.label} m={m} />
          ))}
        </div>

        <div className="mt-6 rounded-md border border-line bg-panel/40 p-5 text-xs text-muted bg-clip-padding">
          <div className="font-bold text-slate-200 text-sm flex items-center gap-2 mb-1">
            <Cpu className="h-4 w-4 text-wreck" /> Resolution Bottleneck Insight
          </div>
          <p className="leading-relaxed">
            Retraining ghost gear head at 1280px scored <span className="font-mono text-wreck">0.248 mAP</span> (worse than 640px). Source images are 640×640, so upscaling added interpolation blur without detail. Object physical size in sonar swath is the true bottleneck.
          </p>
        </div>
      </div>
    </section>
  )
}
