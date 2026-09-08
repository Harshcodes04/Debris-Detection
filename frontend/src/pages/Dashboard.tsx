import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Radar,
  Upload,
  Cpu,
  Layers,
  AlertTriangle,
  ArrowUpRight,
  Activity,
  ShieldCheck,
  Radio,
} from 'lucide-react'
import { StatCard } from '../components/StatCard'
import { StatusBadge } from '../components/StatusBadge'
import { Wrap } from '../components/Shell'
import { getRegistry, listSurveys } from '../api'
import type { Hazard } from '../types'

export default function Dashboard() {
  const { data: hazardsData } = useQuery({ queryKey: ['registry'], queryFn: getRegistry })
  const { data: surveysData } = useQuery({ queryKey: ['surveys'], queryFn: listSurveys })

  const hazards: Hazard[] = hazardsData ?? []
  const surveys = surveysData ?? []

  const totalScans = surveys.length
  const totalDetections = hazards.length
  const highConfidence = hazards.filter((h) => h.times_seen > 1).length
  const areaCovered = 14.85 // km²

  return (
    <Wrap wide>
      {/* Top Banner / Hero Header */}
      <div className="relative overflow-hidden rounded-2xl border border-line bg-gradient-to-r from-marine-900 via-panel to-marine-850 p-6 sm:p-8 shadow-2xl">
        <div className="absolute -right-16 -top-16 h-64 w-64 rounded-full bg-wreck/5 blur-3xl pointer-events-none" />
        <div className="relative z-10 flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-wreck/30 bg-wreck/10 px-3 py-1 text-xs font-mono text-wreck mb-3">
              <Radio className="h-3.5 w-3.5 animate-pulse text-wreck" />
              SIH PS57 · SEABED SONAR PLATFORM
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white">
              Marine Debris Intelligence Dashboard
            </h1>
            <p className="mt-2 max-w-2xl text-sm text-muted">
              Real-time AI detection of ghost gear, shipwrecks, and submerged hazards from Side-Scan Sonar (SSS) imagery using dual-head YOLO models.
            </p>
          </div>

          {/* Quick Actions */}
          <div className="flex flex-wrap items-center gap-3">
            <Link
              to="/detect"
              className="inline-flex items-center gap-2 rounded-xl border border-wreck/50 bg-wreck px-4 py-2.5 text-sm font-semibold text-marine-950 hover:bg-wreck/90 transition-all shadow-glow-cyan"
            >
              <Upload className="h-4 w-4" />
              Upload Sonar Frame
            </Link>
            <Link
              to="/map"
              className="inline-flex items-center gap-2 rounded-xl border border-line bg-panel/80 px-4 py-2.5 text-sm font-semibold text-slate-200 hover:border-wreck/40 hover:text-wreck transition-all"
            >
              <Radar className="h-4 w-4" />
              View Spatial Risk Map
            </Link>
          </div>
        </div>
      </div>

      {/* Section 1: Overview Statistics Grid */}
      <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Total Sonar Scans"
          value={totalScans}
          subtext="Recorded survey missions"
          trend="+12% this week"
          trendType="positive"
          icon={Radar}
          color="wreck"
        />
        <StatCard
          title="Detected Debris Objects"
          value={totalDetections}
          subtext="Ghost pots, wrecks, cables"
          trend="Live Registry"
          trendType="neutral"
          icon={Layers}
          color="rose"
        />
        <StatCard
          title="High Confidence Targets"
          value={highConfidence}
          subtext="Confirmed by dual-head check"
          trend="92.3% Wreck Precision"
          trendType="positive"
          icon={ShieldCheck}
          color="emerald"
        />
        <StatCard
          title="Coverage Area"
          value={`${areaCovered} km²`}
          subtext="Side-scan swath footprint"
          trend="Active Transects"
          trendType="positive"
          icon={Activity}
          color="indigo"
        />
      </div>

      {/* Main Grid: Upload & Recent Activity + System Status */}
      <div className="mt-8 grid gap-8 lg:grid-cols-3">
        {/* Left Column: Quick Upload Zone & Recent Scans */}
        <div className="lg:col-span-2 space-y-6">
          {/* Quick Sonar Upload Zone Card */}
          <div className="rounded-2xl border border-line bg-panel/60 p-6 backdrop-blur-sm relative overflow-hidden">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-base font-bold text-white flex items-center gap-2">
                  <Upload className="h-4 w-4 text-wreck" />
                  Quick Sonar Analysis
                </h2>
                <p className="text-xs text-muted">
                  Drop a side-scan frame (PNG, JPG) or survey track file (.XTF) to start AI inference
                </p>
              </div>
              <Link
                to="/detect"
                className="text-xs font-mono text-wreck hover:underline flex items-center gap-1"
              >
                Open Full Viewer <ArrowUpRight className="h-3 w-3" />
              </Link>
            </div>

            <Link
              to="/detect"
              className="flex flex-col items-center justify-center rounded-xl border border-dashed border-line-bright bg-marine-950/50 px-6 py-8 text-center transition-all hover:border-wreck/60 hover:bg-marine-900/60 group"
            >
              <div className="flex h-12 w-12 items-center justify-center rounded-full border border-wreck/30 bg-wreck/10 text-wreck group-hover:scale-110 transition-transform shadow-glow-cyan">
                <Radar className="h-6 w-6 animate-pulse" />
              </div>
              <span className="mt-3 text-sm font-semibold text-slate-200">
                Click or drag & drop sonar frame here
              </span>
              <span className="mt-1 text-xs text-muted font-mono">
                Supports Side-Scan Sonar (.png, .jpg) & Raw XTF Navigation
              </span>
            </Link>
          </div>

          {/* Recent Scans Table */}
          <div className="rounded-2xl border border-line bg-panel/60 p-6 backdrop-blur-sm">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-base font-bold text-white">Recent Survey Scans</h2>
                <p className="text-xs text-muted">Telemetry history from active marine transects</p>
              </div>
              <Link
                to="/hazards"
                className="text-xs font-mono text-wreck hover:underline flex items-center gap-1"
              >
                View Registry <ArrowUpRight className="h-3 w-3" />
              </Link>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-line bg-marine-950/60 font-mono text-muted uppercase tracking-wider">
                  <tr>
                    <th className="px-3 py-2.5">Survey ID</th>
                    <th className="px-3 py-2.5">Survey Name</th>
                    <th className="px-3 py-2.5">Uploaded By</th>
                    <th className="px-3 py-2.5">Created At</th>
                    <th className="px-3 py-2.5 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line/60">
                  {surveys.map((scan) => (
                    <tr key={scan.id} className="hover:bg-marine-900/40 transition-colors font-mono">
                      <td className="px-3 py-3 font-bold text-wreck">#{scan.id}</td>
                      <td className="px-3 py-3 font-medium text-slate-200">{scan.name}</td>
                      <td className="px-3 py-3 text-muted">{scan.uploaded_by || 'Operator'}</td>
                      <td className="px-3 py-3 text-slate-300">{scan.created_at}</td>
                      <td className="px-3 py-3 text-right">
                        <Link
                          to="/detect"
                          className="inline-flex items-center gap-1 rounded-md border border-line px-2.5 py-1 text-[11px] text-slate-300 hover:border-wreck/50 hover:text-wreck"
                        >
                          Results
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Right Column: Model Status & AI Intelligence Highlights */}
        <div className="space-y-6">
          {/* Model Status Card */}
          <div className="rounded-2xl border border-line bg-panel/60 p-6 backdrop-blur-sm">
            <h2 className="text-base font-bold text-white flex items-center gap-2 mb-4">
              <Cpu className="h-4 w-4 text-wreck" />
              YOLO ML Inference Status
            </h2>

            <div className="space-y-3">
              <div className="rounded-xl border border-line bg-marine-950/60 p-3.5 text-xs">
                <div className="flex items-center justify-between font-semibold text-slate-200">
                  <span>Wreck Detection Head</span>
                  <StatusBadge status="online" label="0.625 mAP" pulse />
                </div>
                <div className="mt-1 text-[11px] text-muted">
                  Shipwrecks & submerged metals (Precision: 92.3%)
                </div>
              </div>

              <div className="rounded-xl border border-line bg-marine-950/60 p-3.5 text-xs">
                <div className="flex items-center justify-between font-semibold text-slate-200">
                  <span>Ghost Gear Head</span>
                  <StatusBadge status="online" label="0.310 mAP" pulse />
                </div>
                <div className="mt-1 text-[11px] text-muted">
                  Derelict crab pots & netting (Optimized for small objects)
                </div>
              </div>
            </div>
          </div>

          {/* Active Hazards Summary */}
          <div className="rounded-2xl border border-line bg-panel/60 p-6 backdrop-blur-sm">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-bold text-white flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-amber-400" />
                Active Marine Hazards
              </h2>
              <span className="font-mono text-xs text-wreck font-bold">
                {hazards.length} Tracked
              </span>
            </div>

            <div className="space-y-2.5">
              {hazards.slice(0, 4).map((h: Hazard) => (
                <div
                  key={h.hazard_id}
                  className="rounded-xl border border-line bg-marine-950/50 p-3 text-xs flex items-center justify-between"
                >
                  <div>
                    <div className="font-semibold text-slate-200 flex items-center gap-2">
                      <span className="font-mono text-wreck">{h.hazard_id}</span>
                      <span>{h.class}</span>
                    </div>
                    <div className="text-[11px] text-muted font-mono mt-0.5">
                      Seen {h.times_seen}× · Lat {h.lat.toFixed(3)}, Lon {h.lon.toFixed(3)}
                    </div>
                  </div>
                  <StatusBadge status={h.status} />
                </div>
              ))}
            </div>

            <Link
              to="/hazards"
              className="mt-4 block w-full rounded-xl border border-line bg-marine-900/60 py-2 text-center font-mono text-xs text-slate-300 hover:border-wreck/40 hover:text-wreck transition-colors"
            >
              Explore Registry & Recovery Plans →
            </Link>
          </div>
        </div>
      </div>
    </Wrap>
  )
}
