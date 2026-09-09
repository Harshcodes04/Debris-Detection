import { useCallback, useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Upload,
  Eye,
  Layers,
  Sliders,
  Download,
  FileCode,
  FileSpreadsheet,
  CheckCircle2,
  RefreshCw,
} from 'lucide-react'
import * as api from '../api'
import type { Detection, JobSummary, Survey } from '../types'
import { classColour } from '../types'
import { Empty, Failed, Loading } from '../components/Shell'

type Phase = 'idle' | 'uploading' | 'processing' | 'done' | 'failed'

export default function Detect() {
  const [phase, setPhase] = useState<Phase>('idle')
  const [error, setError] = useState<unknown>(null)
  const [survey, setSurvey] = useState<Survey | null>(null)
  const [jobId, setJobId] = useState<number | null>(null)
  const [progress, setProgress] = useState(0)
  const [preview, setPreview] = useState<string | null>(null)
  const [fileName, setFileName] = useState<string>('')
  const [detections, setDetections] = useState<Detection[]>([])
  const [summary, setSummary] = useState<JobSummary | null>(null)
  const [minConf, setMinConf] = useState(0.2)
  const [selected, setSelected] = useState<number | null>(null)

  // Fetch real recent surveys from backend
  const { data: surveysData, refetch: refetchSurveys } = useQuery({
    queryKey: ['surveys'],
    queryFn: api.listSurveys,
  })

  const submit = useCallback(async (file: File) => {
    setError(null)
    setDetections([])
    setSummary(null)
    setSelected(null)
    setProgress(0)
    setFileName(file.name)
    setPreview((old) => {
      if (old) URL.revokeObjectURL(old)
      return URL.createObjectURL(file)
    })
    setPhase('uploading')
    try {
      const { survey: s, upload } = await api.uploadNewSurvey(file)
      setSurvey(s)
      setJobId(upload.job_id)
      setPhase('processing')
      void refetchSurveys()
    } catch (e) {
      setError(e)
      setPhase('failed')
    }
  }, [refetchSurveys])

  // Poll while job is processing
  useEffect(() => {
    if (phase !== 'processing' || jobId == null) return

    let cancelled = false
    const tick = async () => {
      try {
        const job = await api.getJob(jobId)
        if (cancelled) return
        setProgress(job.progress ?? 0)
        if (job.status === 'done') {
          const [page, sum] = await Promise.all([
            api.getDetections(jobId),
            api.getSummary(jobId).catch(() => null),
          ])
          if (cancelled) return
          setDetections(page.items)
          setSummary(sum)
          setPreview(`/api/jobs/${jobId}/image`)
          setPhase('done')
        } else if (job.status === 'failed') {
          setError(new Error(job.error || 'Job processing failed'))
          setPhase('failed')
        }
      } catch (e) {
        if (!cancelled) {
          setError(e)
          setPhase('failed')
        }
      }
    }

    const id = setInterval(tick, 1200)
    void tick()
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [phase, jobId])

  const shown = detections.filter((d) => d.confidence >= minConf)
  const geotagged = shown.filter((d) => d.lat != null).length
  const surveysList = surveysData ?? []

  return (
    <div className="max-w-[1600px] mx-auto px-6 py-6 space-y-6">
      {/* Subheader Title & Pipeline Context */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold tracking-tight text-white font-sans">
              Detect
            </h1>
            <span className="rounded-full border border-[#00f2ff]/40 bg-[#00f2ff]/10 text-[#00f2ff] font-mono text-xs px-3 py-0.5 font-semibold">
              Contract v1.0.0
            </span>
          </div>
          <p className="mt-1 text-xs sm:text-sm text-[#8094b8]">
            Upload a side-scan sonar frame. Both detection heads run and their results merge.
          </p>
        </div>

        {/* Top-Right Mode Selector */}
        <div className="flex items-center gap-2">
          <div className="rounded-full border border-[#141f36] bg-[#0a1122] p-1 flex items-center gap-1 font-mono text-xs text-[#8094b8]">
            <button
              onClick={() => setPhase('idle')}
              className={`px-3.5 py-1 rounded-full font-bold transition-all ${
                phase === 'idle'
                  ? 'bg-[#00f2ff] text-[#050914] shadow-[0_0_10px_rgba(0,242,255,0.3)]'
                  : 'hover:text-white'
              }`}
            >
              Upload Inference
            </button>
            <button
              className={`px-3.5 py-1 rounded-full transition-all ${
                phase === 'done'
                  ? 'bg-[#00f2ff] text-[#050914] font-bold shadow-[0_0_10px_rgba(0,242,255,0.3)]'
                  : 'hover:text-white'
              }`}
            >
              Analyzed Frame ({shown.length})
            </button>
          </div>
        </div>
      </div>

      {/* Hero Upload Dropzone Section */}
      {phase === 'idle' && (
        <div
          className="relative rounded-2xl border border-dashed border-[#1e2d4a] bg-[#070c18] p-10 sm:p-14 text-center overflow-hidden flex flex-col items-center justify-center min-h-[380px] shadow-2xl group cursor-pointer hover:border-[#00f2ff]/60 transition-all"
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault()
            const f = e.dataTransfer.files?.[0]
            if (f) void submit(f)
          }}
        >
          {/* Background Concentric Radar Rings */}
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center opacity-15">
            <div className="h-[450px] w-[450px] rounded-full border border-[#00f2ff]" />
            <div className="absolute h-[320px] w-[320px] rounded-full border border-[#00f2ff] border-dashed" />
            <div className="absolute h-[180px] w-[180px] rounded-full border border-[#00f2ff]" />
          </div>

          {/* Central Glowing Upload Icon */}
          <label className="relative z-10 cursor-pointer flex flex-col items-center">
            <input
              type="file"
              accept="image/*,.xtf"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0]
                if (f) void submit(f)
              }}
            />
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl border border-[#00f2ff]/60 bg-[#00f2ff]/10 text-[#00f2ff] group-hover:scale-110 shadow-[0_0_25px_rgba(0,242,255,0.3)] transition-all">
              <Upload className="h-8 w-8 text-[#00f2ff]" />
            </div>

            <h2 className="mt-4 text-xl font-bold tracking-tight text-white font-sans">
              Drop a sonar image, or click to choose
            </h2>
            <p className="mt-1 text-xs font-mono text-[#64748b]">
              PNG, JPG, TIFF or raw .XTF survey files, up to 100 MB
            </p>
          </label>

          {/* Dual Model Tags */}
          <div className="relative z-10 mt-6 flex flex-wrap items-center justify-center gap-2 font-mono text-xs">
            <div className="rounded-full border border-[#1e2d4a] bg-[#0a1122] px-3.5 py-1 text-[#00f2ff]">
              Wreck head: <span className="font-bold text-white">sidescan_v1</span>
            </div>
            <span className="text-[#64748b] font-bold">+</span>
            <div className="rounded-full border border-[#1e2d4a] bg-[#0a1122] px-3.5 py-1 text-[#00f2ff]">
              Ghost gear head: <span className="font-bold text-white">ghostgear_v1</span>
            </div>
          </div>
        </div>
      )}

      {/* Progress / Loading Indicator */}
      {phase === 'uploading' && (
        <div className="py-12">
          <Loading what="Uploading Sonar Waterfall Telemetry…" />
        </div>
      )}
      {phase === 'processing' && (
        <div className="py-12 space-y-4 max-w-md mx-auto text-center">
          <Loading what={`Running Model Inference… ${progress ? `${progress}%` : ''}`} />
          <div className="h-2 w-full overflow-hidden rounded-full bg-[#0a1122] border border-[#141f36]">
            <div
              className="h-full bg-gradient-to-r from-[#00c6ff] to-[#00f2ff] transition-all duration-300 shadow-[0_0_10px_rgba(0,242,255,0.5)]"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      )}
      {phase === 'failed' && <div className="py-12"><Failed error={error} /></div>}

      {/* Main Analysis & Visualizer View when done */}
      {phase === 'done' && (
        <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
          {/* Main Sonar Image & Overlay Canvas */}
          <div className="space-y-6">
            <div className="rounded-2xl border border-[#141f36] bg-[#070d1a] p-5 shadow-2xl">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <Eye className="h-4 w-4 text-[#00f2ff]" />
                  <span className="text-xs font-mono font-bold uppercase text-white tracking-wider">
                    Acoustic Sonar Visualizer
                  </span>
                </div>
                <span className="font-mono text-xs text-[#64748b]">
                  {fileName || 'Sonar Frame'}
                </span>
              </div>

              {preview && (
                <BoxOverlay
                  src={preview}
                  detections={shown}
                  selected={selected}
                  onSelect={setSelected}
                />
              )}
            </div>

            {/* Detections Table */}
            <div className="rounded-2xl border border-[#141f36] bg-[#070d1a] p-5 shadow-2xl">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-bold text-white flex items-center gap-2 font-mono">
                  <Layers className="h-4 w-4 text-[#00f2ff]" />
                  Detected Anomalies ({shown.length})
                </h3>
                <span className="text-xs font-mono text-[#64748b]">
                  Confidence Cutoff: {(minConf * 100).toFixed(0)}%
                </span>
              </div>

              {shown.length ? (
                <DetectionTable
                  detections={shown}
                  selected={selected}
                  onSelect={setSelected}
                />
              ) : (
                <Empty>
                  No objects detected above {(minConf * 100).toFixed(0)}% confidence threshold.
                </Empty>
              )}
            </div>
          </div>

          {/* Right Sidebar: Controls & Metrics */}
          <aside className="space-y-6">
            {/* Quick Metrics Panel */}
            <div className="rounded-2xl border border-[#141f36] bg-[#070d1a] p-5 text-xs shadow-2xl">
              <div className="font-mono font-bold uppercase text-[#00f2ff] mb-3 pb-2 border-b border-[#141f36] flex items-center justify-between">
                <span>Scan Telemetry</span>
                <CheckCircle2 className="h-3.5 w-3.5 text-[#10b981]" />
              </div>
              <div className="space-y-2.5">
                <Row label="Objects Shown" value={String(shown.length)} />
                <Row label="Total Detected" value={String(detections.length)} />
                <Row label="Geotagged" value={String(geotagged)} />
                {summary?.processing_ms != null && (
                  <Row label="Inference Speed" value={`${summary.processing_ms} ms`} />
                )}
                {summary && summary.area_covered > 0 && (
                  <Row label="Coverage Area" value={`${summary.area_covered.toFixed(3)} km²`} />
                )}
              </div>
            </div>

            {/* Confidence Slider Control */}
            <div className="rounded-2xl border border-[#141f36] bg-[#070d1a] p-5 shadow-2xl">
              <div className="flex items-center justify-between mb-2">
                <label htmlFor="conf" className="text-xs font-bold text-white flex items-center gap-1.5 font-mono">
                  <Sliders className="h-3.5 w-3.5 text-[#00f2ff]" />
                  Confidence Threshold
                </label>
                <span className="font-mono text-xs font-bold text-[#00f2ff]">
                  {(minConf * 100).toFixed(0)}%
                </span>
              </div>
              <input
                id="conf"
                type="range"
                min={0.05}
                max={0.6}
                step={0.01}
                value={minConf}
                onChange={(e) => setMinConf(Number(e.target.value))}
                className="mt-3 w-full accent-[#00f2ff] cursor-pointer"
              />
            </div>

            {/* Export Reports */}
            <div className="rounded-2xl border border-[#141f36] bg-[#070d1a] p-5 shadow-2xl">
              <div className="text-xs font-bold text-white flex items-center gap-1.5 mb-3 font-mono">
                <Download className="h-3.5 w-3.5 text-[#00f2ff]" />
                Export Intelligence Report
              </div>
              <div className="grid grid-cols-2 gap-2">
                <a
                  className="flex items-center justify-center gap-1.5 rounded-xl border border-[#141f36] bg-[#0a1122] px-3 py-2 text-center text-xs font-mono text-slate-200 hover:border-[#00f2ff]/50 hover:text-[#00f2ff] transition-colors"
                  href={survey ? api.reportUrl(survey.id, 'json') : '#'}
                  download="sonar_report.json"
                >
                  <FileCode className="h-3.5 w-3.5 text-[#00f2ff]" /> JSON
                </a>
                <a
                  className="flex items-center justify-center gap-1.5 rounded-xl border border-[#141f36] bg-[#0a1122] px-3 py-2 text-center text-xs font-mono text-slate-200 hover:border-[#00f2ff]/50 hover:text-[#00f2ff] transition-colors"
                  href={survey ? api.reportUrl(survey.id, 'csv') : '#'}
                  download="sonar_report.csv"
                >
                  <FileSpreadsheet className="h-3.5 w-3.5 text-[#00f2ff]" /> CSV
                </a>
              </div>
              <button
                onClick={() => setPhase('idle')}
                className="mt-4 w-full flex items-center justify-center gap-2 rounded-xl border border-[#141f36] bg-[#0a1122] py-2 text-xs font-mono text-slate-200 hover:border-[#00f2ff]/40 hover:text-[#00f2ff] transition-colors"
              >
                <RefreshCw className="h-3.5 w-3.5" /> Analyze Another Frame
              </button>
            </div>
          </aside>
        </div>
      )}

      {/* RECENT SURVEY SWATHS (Live Data from API) */}
      <div className="mt-8 rounded-2xl border border-[#141f36] bg-[#070d1a] p-6 shadow-2xl space-y-4">
        {/* Title */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-[#141f36] pb-4">
          <div>
            <h2 className="text-sm font-bold uppercase font-mono tracking-wider text-slate-100">
              RECENT SURVEY SWATHS
            </h2>
            <p className="text-xs text-[#64748b] mt-0.5">
              Surveys recorded by this system, newest last
            </p>
          </div>
        </div>

        {/* Table */}
        {!surveysList.length ? (
          <Empty>No survey swaths recorded yet. Upload a sonar image to run inference.</Empty>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead className="bg-[#050914] font-mono text-[#64748b] uppercase tracking-wider text-[11px] border-b border-[#141f36]">
                <tr>
                  <th className="px-4 py-3">SURVEY ID</th>
                  <th className="px-4 py-3">NAME / FILE</th>
                  <th className="px-4 py-3">UPLOADED BY</th>
                  <th className="px-4 py-3">CREATED AT</th>
                  <th className="px-4 py-3 text-right">ACTION</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#141f36]">
                {surveysList.map((s) => (
                  <tr key={s.id} className="hover:bg-[#0a1122]/60 transition-colors font-mono">
                    <td className="px-4 py-4 font-bold text-[#00f2ff]">#{s.id}</td>
                    <td className="px-4 py-4 text-slate-200">{s.name}</td>
                    <td className="px-4 py-4 text-slate-300">{s.uploaded_by || '—'}</td>
                    <td className="px-4 py-4 text-[#8094b8]">{s.created_at}</td>
                    <td className="px-4 py-4 text-right">
                      <a
                        href={api.reportUrl(s.id, 'json')}
                        className="rounded-lg border border-[#00f2ff]/60 text-[#00f2ff] hover:bg-[#00f2ff]/10 px-3 py-1.5 text-xs font-mono font-semibold transition-all inline-block"
                      >
                        Download Report
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between border-b border-[#141f36] py-1.5 last:border-0 font-mono">
      <span className="text-[#64748b]">{label}</span>
      <span className="text-slate-200 font-semibold">{value}</span>
    </div>
  )
}

function BoxOverlay({
  src,
  detections,
  selected,
  onSelect,
}: {
  src: string
  detections: Detection[]
  selected: number | null
  onSelect: (i: number | null) => void
}) {
  const imgRef = useRef<HTMLImageElement>(null)
  const [natural, setNatural] = useState<{ w: number; h: number } | null>(null)
  const [shown, setShown] = useState<{ w: number; h: number } | null>(null)

  useEffect(() => {
    const el = imgRef.current
    if (!el) return
    const ro = new ResizeObserver(() => setShown({ w: el.clientWidth, h: el.clientHeight }))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  // object-contain scales the image to fit the element box while preserving
  // aspect ratio. We must compute the *rendered* image rect inside the element
  // so that bbox coordinates (which are in natural pixels) map to the right
  // screen pixels and don't drift into the letterbox / pillarbox area.
  const renderRect = natural && shown
    ? (() => {
        const scaleX = shown.w / natural.w
        const scaleY = shown.h / natural.h
        const scale = Math.min(scaleX, scaleY)          // object-contain picks the smaller
        const rw = natural.w * scale
        const rh = natural.h * scale
        const ox = (shown.w - rw) / 2                    // pillarbox offset
        const oy = (shown.h - rh) / 2                    // letterbox offset
        return { ox, oy, scale }
      })()
    : null

  return (
    <div className="relative inline-block w-full overflow-hidden rounded-xl border border-[#141f36] bg-black">
      <img
        ref={imgRef}
        src={src}
        alt="Sonar frame recording"
        className="block w-full object-contain max-h-[550px]"
        onLoad={(e) => {
          const el = e.currentTarget
          setNatural({ w: el.naturalWidth, h: el.naturalHeight })
          setShown({ w: el.clientWidth, h: el.clientHeight })
        }}
      />
      {renderRect && shown && (
        <svg
          className="pointer-events-none absolute inset-0 h-full w-full"
          viewBox={`0 0 ${shown.w} ${shown.h}`}
        >
          {detections.map((d, i) => {
            const [x, y, w, h] = d.bbox
            const colour = classColour(d.class)
            const on = selected === d.id
            const rx = x * renderRect.scale + renderRect.ox
            const ry = y * renderRect.scale + renderRect.oy
            const rw = w * renderRect.scale
            const rh = h * renderRect.scale
            return (
              <g
                key={d.id ?? i}
                className="pointer-events-auto cursor-pointer"
                onClick={() => onSelect(on ? null : d.id)}
              >
                <rect
                  x={rx}
                  y={ry}
                  width={rw}
                  height={rh}
                  fill={on ? colour : 'none'}
                  fillOpacity={on ? 0.25 : 0.08}
                  stroke={colour}
                  strokeWidth={on ? 3 : 2}
                  strokeDasharray={on ? 'none' : '4 2'}
                />
                <rect
                  x={rx}
                  y={Math.max(0, ry - 22)}
                  width={Math.max(130, d.class.length * 8 + 45)}
                  height={22}
                  fill="#050914"
                  fillOpacity={0.95}
                  stroke={colour}
                  strokeWidth={1}
                  rx={4}
                />
                <text
                  x={rx + 6}
                  y={Math.max(15, ry - 7)}
                  fill={colour}
                  fontSize={11}
                  fontWeight={600}
                  fontFamily="'JetBrains Mono', monospace"
                >
                  {d.class} {(d.confidence * 100).toFixed(1)}%
                </text>
              </g>
            )
          })}
        </svg>
      )}
    </div>
  )
}

function DetectionTable({
  detections,
  selected,
  onSelect,
}: {
  detections: Detection[]
  selected: number | null
  onSelect: (i: number | null) => void
}) {
  return (
    <div className="overflow-x-auto rounded-xl border border-[#141f36]">
      <table className="w-full text-xs text-left font-mono">
        <thead className="bg-[#050914] text-[#64748b] uppercase tracking-wider text-[11px] border-b border-[#141f36]">
          <tr>
            <th className="px-4 py-3">Class / Target</th>
            <th className="px-4 py-3">Confidence</th>
            <th className="px-4 py-3">Coordinates (Lat, Lon)</th>
            <th className="px-4 py-3">Est. Size</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[#141f36]">
          {[...detections]
            .sort((a, b) => b.confidence - a.confidence)
            .map((d) => {
              const color = classColour(d.class)
              const isSelected = selected === d.id
              return (
                <tr
                  key={d.id}
                  onClick={() => onSelect(isSelected ? null : d.id)}
                  className={`cursor-pointer transition-colors ${
                    isSelected ? 'bg-[#00f2ff]/15 font-medium' : 'hover:bg-[#0a1122]/60'
                  }`}
                >
                  <td className="px-4 py-3">
                    <span
                      className="mr-2 inline-block h-2.5 w-2.5 rounded-full align-middle"
                      style={{ background: color }}
                    />
                    <span className="font-semibold text-slate-200">{d.class}</span>
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className="inline-block rounded px-2 py-0.5 text-xs font-bold"
                      style={{ color: color, backgroundColor: `${color}18` }}
                    >
                      {(d.confidence * 100).toFixed(1)}%
                    </span>
                  </td>
                  <td className="px-4 py-3 text-[#8094b8]">
                    {d.lat != null && d.lon != null ? (
                      `${d.lat.toFixed(4)}°N, ${d.lon.toFixed(4)}°E`
                    ) : (
                      <span className="text-[#64748b] italic">Telemetry track</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-slate-300">
                    {d.size_m != null ? `${d.size_m.toFixed(2)} m` : (
                      <span
                        className="text-[#64748b] italic cursor-help"
                        title="Size estimation requires an XTF survey file with navigation headers. JPEG/PNG uploads have no spatial calibration."
                      >
                        No nav data
                      </span>
                    )}
                  </td>
                </tr>
              )
            })}
        </tbody>
      </table>
    </div>
  )
}
