import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Layers, Play, HelpCircle } from 'lucide-react'
import { rankForAnnotation } from '../api'
import { Empty, Failed, Loading, Wrap } from '../components/Shell'

const PLACEHOLDER = `samples/sonar_sector_04.jpg
samples/sonar_sector_12.jpg
samples/sonar_sector_19.jpg`

export default function Annotate() {
  const [topK, setTopK] = useState(12)

  const rank = useMutation({
    mutationFn: () => rankForAnnotation(undefined, topK),
  })

  const candidates = rank.data?.candidates ?? []

  return (
    <Wrap>
      {/* Header Info */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-line pb-5">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-wreck/30 bg-wreck/10 px-3 py-0.5 text-xs font-mono text-wreck mb-1">
            <Layers className="h-3.5 w-3.5 text-wreck" />
            ACTIVE LEARNING UNCERTAINTY QUEUE
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white">
            Active Annotation Queue
          </h1>
          <p className="mt-1 text-sm text-muted">
            Ranks all unlabelled side-scan sonar imagery currently saved in the database by model decision boundary uncertainty to maximize retraining efficiency.
          </p>
        </div>
      </div>

      {/* Input Card */}
      <div className="mt-6 rounded-2xl border border-line bg-panel/60 p-5 backdrop-blur-sm shadow-xl">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <label htmlFor="topk" className="text-xs font-mono text-muted">Show Top</label>
            <input
              id="topk"
              type="number"
              min={1}
              max={100}
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
              className="w-20 rounded-lg border border-line bg-marine-950 px-3 py-1 font-mono text-xs text-slate-200"
            />
          </div>
          <button
            onClick={() => rank.mutate()}
            disabled={rank.isPending}
            className="inline-flex items-center gap-2 rounded-xl border border-wreck/40 bg-wreck px-4 py-2 text-xs font-bold text-marine-950 hover:bg-wreck/90 transition-all disabled:opacity-40 shadow-glow-cyan"
          >
            <Play className="h-3.5 w-3.5 fill-current" />
            {rank.isPending ? 'Scoring Imagery...' : 'Rank Uncertainty'}
          </button>
        </div>
      </div>

      {rank.isPending && <div className="mt-4"><Loading what="Scoring imagery entropy..." /></div>}
      {rank.error && <div className="mt-4"><Failed error={rank.error} /></div>}

      {rank.data && (
        <>
          <p className="mt-6 text-xs font-mono text-wreck bg-wreck/10 p-3 rounded-xl border border-wreck/30">
            {rank.data.note}
          </p>

          {!candidates.length ? (
            <div className="mt-4"><Empty>Nothing scored — check paths resolve on server.</Empty></div>
          ) : (
            <>
              <h2 className="mt-6 text-xs font-mono font-bold uppercase tracking-wider text-wreck flex items-center gap-2">
                <HelpCircle className="h-4 w-4" /> High Priority — Label These First
              </h2>
              <ol className="mt-3 space-y-3">
                {candidates.slice(0, topK).map((c, i) => (
                  <li key={c.path} className="rounded-2xl border border-line bg-panel/40 p-4 text-xs">
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex items-center gap-3">
                        <span className="font-mono text-xs font-bold text-wreck">
                          #{String(i + 1).padStart(2, '0')}
                        </span>
                        <span className="truncate font-semibold text-slate-200">{basename(c.path)}</span>
                      </div>
                      <span className="font-mono font-bold text-wreck text-sm">
                        Score {c.score.toFixed(3)}
                      </span>
                    </div>
                    <div className="mt-2 text-muted font-mono">
                      {c.n_detections} detections · Max confidence {c.max_confidence.toFixed(2)}
                    </div>
                    <ul className="mt-2 space-y-1 text-muted font-mono">
                      {c.reasons.map((r) => (
                        <li key={r} className="flex items-center gap-1.5 text-[11px]">
                          <span className="h-1 w-1 rounded-full bg-wreck" />
                          {r}
                        </li>
                      ))}
                    </ul>
                  </li>
                ))}
              </ol>
            </>
          )}
        </>
      )}
    </Wrap>
  )
}

const basename = (p: string) => p.split(/[\/]/).pop() ?? p
