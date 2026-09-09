/**
 * Types mirroring the backend's Pydantic schemas, endpoint by endpoint.
 * Extended with Dashboard, Scan History, and System Health models.
 */

export type JobStatus = 'queued' | 'processing' | 'done' | 'failed'

/** POST /api/surveys */
export interface Survey {
  id: number
  name: string
  uploaded_by: string | null
  notes: string | null
  created_at: string
}

/** POST /api/surveys/{id}/upload */
export interface UploadResponse {
  file_id: number
  job_id: number
  status: JobStatus
}

/** GET /api/jobs/{id} */
export interface Job {
  id: number
  file_id: number
  status: JobStatus
  progress: number
  error: string | null
  started_at: string | null
  finished_at: string | null
}

/** One row from GET /api/jobs/{id}/detections */
export interface Detection {
  id: number
  class: string
  confidence: number
  /** [x, y, w, h] in full-image pixels, top-left origin. */
  bbox: number[]
  lat: number | null
  lon: number | null
  size_m: number | null
  frame_index: number | null
  created_at: string
}

/** GET /api/jobs/{id}/detections - paginated, not a bare array. */
export interface DetectionPage {
  items: Detection[]
  total: number
  limit: number
  offset: number
}

/** GET /api/jobs/{id}/summary */
export interface JobSummary {
  job_id: number
  total: number
  by_class: Record<string, number>
  area_covered: number
  processing_ms: number | null
}

/** One entry from GET /api/registry. */
export interface Hazard {
  hazard_id: string
  class: string
  lat: number
  lon: number
  status: HazardStatus
  times_seen: number
  last_seen: string
  surveys: string[]
  note: string
}

export type HazardStatus = 'present' | 'unconfirmed' | 'gone' | 'recovered'

/** GET /api/registry */
export interface RegistryResponse {
  entries: Hazard[]
}

/** GET /api/recovery/hazards/{id}/plan */
export interface RecoveryPlan {
  hazard_id: string
  cls: string
  recoverable: boolean
  method: string
  transit_hours: number | null
  setup_hours: number
  on_site_hours: number
  total_hours: number | null
  notes: string[]
  /** Present from /hazards/{id}/plan; the day-plan response omits them. */
  risk?: HazardRisk | null
  context?: HazardContext | null
}

/** Why this hazard scored what it did, not just the number. */
export interface HazardRisk {
  score: number
  band: 'HIGH' | 'MEDIUM' | 'LOW'
  reasons: string[]
  components: { harm: number; ecology: number; access: number; certainty: number }
}

/** Looked up from the coordinate: GEBCO depth, OBIS records, nearest port. */
export interface HazardContext {
  depth_m: number | null
  diveable: boolean | null
  biodiversity: { species: number; records: number; datasets: number; radius_km: number } | null
  nearest_port: {
    port: string
    distance_km: number
    transit_hours: number
    assumed_speed_knots: number
    note: string
  } | null
  sources: string[]
}

/** POST /api/recovery/day-plan */
export interface DayPlan {
  hours_available: number
  hours_planned: number
  items: Array<{
    hazard_id: string
    class: string
    method: string
    hours: number
    risk: number
  }>
  deferred: number
  note: string
}

/** POST /api/active-learning/rank */
export interface RankResponse {
  note: string
  candidates: Array<{
    path: string
    score: number
    n_detections: number
    max_confidence: number
    reasons: string[]
  }>
}

/** Scan History entry for Dashboard and ScanHistory views */
export interface ScanItem {
  id: string
  filename: string
  timestamp: string
  sector: string
  detectionsCount: number
  highConfidenceCount: number
  status: 'completed' | 'processing' | 'flagged' | 'failed'
  previewUrl?: string
  detections?: Detection[]
}

/** System & Model Status */
export interface ModelStatusInfo {
  name: string
  version: string
  status: 'online' | 'degraded' | 'offline'
  latencyMs: number
  accuracy: string
  lastInference: string
}

export const STATUS_COLOUR: Record<HazardStatus, string> = {
  present: '#6d8bab',      // the accent - confirmed, still there
  unconfirmed: '#9a9aa2',  // seen once; grey until a second survey agrees
  gone: '#4a4a50',         // missed repeatedly, presumed removed
  recovered: '#6f9270',    // lifted
}

/** Colour a detection by class family */
export function classColour(cls: string): string {
  const c = cls.toLowerCase()
  if (c.includes('pot') || c.includes('net') || c.includes('gear') || c.includes('ghost')) return '#fb7185'
  if (c.includes('ship') || c.includes('wreck') || c.includes('aircraft') || c.includes('metal')) return '#6d8bab'
  if (c.includes('pipe') || c.includes('container') || c.includes('debris')) return '#b8904a'
  return '#34d399'
}

/** Return Tailwind classes for hazard chips */
export function statusBadgeStyle(status: string): string {
  const s = status.toLowerCase()
  if (s === 'present' || s === 'completed' || s === 'online') {
    return 'bg-wreck/10 text-wreck border-wreck/30'
  }
  if (s === 'unconfirmed' || s === 'flagged' || s === 'processing') {
    return 'bg-amber-500/10 text-amber-400 border-amber-500/30'
  }
  if (s === 'recovered' || s === 'safe') {
    return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
  }
  return 'bg-rose-500/10 text-rose-400 border-rose-500/30'
}

