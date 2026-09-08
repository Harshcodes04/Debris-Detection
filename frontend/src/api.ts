/**
 * Backend client connecting directly to live FastAPI endpoints (`/api/...`).
 * Pure API integration without synthetic mock fallback data.
 */

import type {
  DayPlan,
  DetectionPage,
  Hazard,
  Job,
  JobSummary,
  RankResponse,
  RecoveryPlan,
  RegistryResponse,
  Survey,
  UploadResponse,
} from './types'

const BASE = '/api'

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${BASE}${path}`, init)
  if (!r.ok) {
    let detail = `${r.status} ${r.statusText}`
    try {
      const body = await r.json()
      if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : detail
    } catch {
      /* not JSON */
    }
    throw new Error(`${detail} (${BASE}${path})`)
  }
  return r.json() as Promise<T>
}

const json = (body: unknown): RequestInit => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

// --- surveys and upload ---------------------------------------------------

export const listSurveys = () => req<Survey[]>('/surveys')

export const createSurvey = (name: string, notes?: string) =>
  req<Survey>('/surveys', json({ name, notes: notes ?? null }))

/** Upload belongs to a survey, so one has to exist first. */
export async function uploadToSurvey(surveyId: number, file: File): Promise<UploadResponse> {
  const body = new FormData()
  body.append('file', file)
  const r = await fetch(`${BASE}/surveys/${surveyId}/upload`, { method: 'POST', body })
  if (!r.ok) throw new Error(`Upload failed: ${r.status} ${r.statusText}`)
  return r.json()
}

/** Convenience for the detect screen: one survey per uploaded frame. */
export async function uploadNewSurvey(file: File): Promise<{
  survey: Survey
  upload: UploadResponse
}> {
  const stamp = new Date().toISOString().replace('T', ' ').slice(0, 16)
  const survey = await createSurvey(`${file.name} — ${stamp}`)
  const upload = await uploadToSurvey(survey.id, file)
  return { survey, upload }
}

// --- jobs -----------------------------------------------------------------

export const getJob = (id: number) => req<Job>(`/jobs/${id}`)

export const getDetections = (id: number, limit = 200, offset = 0) =>
  req<DetectionPage>(`/jobs/${id}/detections?limit=${limit}&offset=${offset}`)

export const getSummary = (id: number) => req<JobSummary>(`/jobs/${id}/summary`)

/** Reports hang off the survey, not the job. */
export const reportUrl = (surveyId: number, format: 'json' | 'csv') =>
  `${BASE}/surveys/${surveyId}/report?format=${format}`

// --- registry -------------------------------------------------------------

export const getRegistry = async (): Promise<Hazard[]> => {
  const res = await req<RegistryResponse>('/registry')
  return res.entries || []
}

/** GeoJSON risk grid, built from present and unconfirmed hazards only. */
export const heatmapUrl = `${BASE}/registry/heatmap`

// --- recovery -------------------------------------------------------------

export const getRecoveryPlan = (hazardId: string) =>
  req<RecoveryPlan>(`/recovery/hazards/${hazardId}/plan`)

export const getDayPlan = (hazardIds: string[], hoursAvailable = 8) =>
  req<DayPlan>(
    '/recovery/day-plan',
    json({ hazard_ids: hazardIds, hours_available: hoursAvailable })
  )

// --- active learning ------------------------------------------------------

export const rankForAnnotation = (images: string[], topK = 20) =>
  req<RankResponse>('/active-learning/rank', json({ images, top_k: topK }))
