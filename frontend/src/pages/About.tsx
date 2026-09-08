import { Metrics } from '../components/Metrics'
import { Wrap } from '../components/Shell'
import { ShieldAlert, BookOpen, Cpu } from 'lucide-react'

const LIMITS = [
  'Ghost gear detection is uncertain everywhere — no test detection exceeds 0.5 confidence. It is a screening tool that gives an analyst a shortlist, not an authority.',
  'Positions are real when the input is an XTF survey file, read from the ping headers. An image file carries no navigation, so a synthetic track is attached and the report says so.',
  'Coordinates inherit layback error — the towfish trails the vessel by an unmeasured distance, so six decimal places overstates what the sensor knows.',
  'Neither model has been tested on Indian coastal waters. Ghost Pot is Delaware bays; SCTD is mixed provenance.',
  'Nets, pipes and cylinders are not detected. No annotated side-scan dataset exists for them — the same wall that made ghost pots the only trainable target.',
]

export default function About() {
  return (
    <div>
      <Wrap wide>
        <div className="border-b border-line pb-5">
          <div className="inline-flex items-center gap-2 rounded-full border border-wreck/30 bg-wreck/10 px-3 py-0.5 text-xs font-mono text-wreck mb-1">
            <Cpu className="h-3.5 w-3.5 text-wreck" />
            MODEL EVALUATION & BENCHMARKS
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white">
            Performance Benchmarks & Limitations
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-muted">
            Dual side-scan detection heads fine-tuned across 3 staged training runs to handle acoustic sonar shadows.
          </p>
        </div>
      </Wrap>

      <Metrics />

      <Wrap wide>
        <section className="py-6">
          <div className="flex items-center gap-2 font-bold text-lg text-white mb-4">
            <ShieldAlert className="h-5 w-5 text-amber-400" />
            Documented Technical Limitations
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {LIMITS.map((l, idx) => (
              <div
                key={idx}
                className="rounded-2xl border border-line bg-panel/40 p-4 text-xs text-muted leading-relaxed backdrop-blur-sm"
              >
                <div className="font-mono text-wreck font-bold mb-1 text-[11px]">
                  LIMITATION #{idx + 1}
                </div>
                {l}
              </div>
            ))}
          </div>

          <div className="mt-10 rounded-2xl border border-line bg-panel/60 p-6 backdrop-blur-sm">
            <div className="flex items-center gap-2 font-bold text-base text-white mb-2">
              <BookOpen className="h-5 w-5 text-wreck" />
              Prior Work & Academic Comparison
            </div>
            <p className="text-xs text-muted leading-relaxed">
              <strong className="text-slate-200">GhostVision (University of Delaware, JMSE 2026)</strong> trained on the same dataset and reports higher F1 on crab pots (0.51 untuned, 0.71–0.73 with post-processing that aggregates detections across overlapping pings). This system covers more target types and adds recovery prioritisation; the ping aggregation step is the documented path to closing the gap.
            </p>
          </div>
        </section>
      </Wrap>
    </div>
  )
}
