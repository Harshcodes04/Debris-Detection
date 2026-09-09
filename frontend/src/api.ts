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
const TOKEN_KEY = 'sih.token'

/** Kept in sessionStorage rather than localStorage: closing the tab ends the
 *  session, which is the behaviour you want on a shared survey machine. */
export const getToken = () => sessionStorage.getItem(TOKEN_KEY)
export const setToken = (t: string) => sessionStorage.setItem(TOKEN_KEY, t)
export const clearToken = () => sessionStorage.removeItem(TOKEN_KEY)

/** Raised on 401 so the app can send the user back to sign in rather than
 *  showing an error nobody can act on. */
export class NotSignedIn extends Error {
  constructor() {
    super('Your session has ended. Sign in again.')
    this.name = 'NotSignedIn'
  }
}

function withAuth(init?: RequestInit): RequestInit {
  const token = getToken()
  if (!token) return init ?? {}
  return {
    ...init,
    headers: { ...(init?.headers ?? {}), Authorization: `Bearer ${token}` },
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${BASE}${path}`, withAuth(init))
  if (r.status === 401) {
    clearToken()
    window.dispatchEvent(new Event('sih:signed-out'))
    throw new NotSignedIn()
  }
  if (!r.ok) {
    let detail = `${r.status} ${r.statusText}`
    try {
      const body = await r.json()
      const d = body?.detail ?? body?.message
      if (d) detail = typeof d === 'string' ? d : detail
    } catch {
      /* not JSON */
    }
    throw new Error(`${detail} (${BASE}${path})`)
  }
  if (r.status === 204) return undefined as T
  return r.json() as Promise<T>
}

// --- auth -----------------------------------------------------------------

export interface Session {
  access_token: string
  token_type: string
  expires_in_minutes: number
  email: string
  role: 'viewer' | 'analyst' | 'admin'
  full_name: string | null
}

export const signIn = async (email: string, password: string): Promise<Session> => {
  const session = await req<Session>('/auth/login', json({ email, password }))
  setToken(session.access_token)
  return session
}

export const whoAmI = () =>
  req<{ id: number; email: string; full_name: string | null; role: Session['role']; is_active: boolean }>(
    '/auth/me',
  )

// --- accounts, admin only -------------------------------------------------

export interface Account {
  id: number
  email: string
  full_name: string | null
  role: 'viewer' | 'analyst' | 'admin'
  is_active: boolean
  last_login_at: string | null
}

export const listAccounts = () => req<Account[]>('/auth/users')

export const createAccount = (body: {
  email: string
  password: string
  full_name?: string
  role: string
}) => req<Account>('/auth/users', json(body))

export const setAccountActive = (id: number, active: boolean) =>
  req<Account>(`/auth/users/${id}/${active ? 'enable' : 'disable'}`, json({}))

export const setAccountRole = (id: number, role: string) =>
  req<Account>(`/auth/users/${id}/role`, json({ role }))

/** No email in this system, so there is no reset link - an admin sets the
 *  password and tells the person out of band. */
export const resetAccountPassword = (id: number, new_password: string) =>
  req<void>(`/auth/users/${id}/reset-password`, json({ new_password }))

export const changeMyPassword = (current_password: string, new_password: string) =>
  req<void>('/auth/change-password', json({ current_password, new_password }))

export const signOut = () => {
  clearToken()
  window.dispatchEvent(new Event('sih:signed-out'))
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

/** Fetch a protected file and hand back an object URL.
 *
 *  A browser will not attach an Authorization header to <img src> or <a href>,
 *  so anything behind the token has to be fetched and turned into a blob. Call
 *  URL.revokeObjectURL on the result when the component unmounts. */
export async function fetchBlobUrl(path: string): Promise<string> {
  const r = await fetch(`${BASE}${path}`, withAuth())
  if (r.status === 401) {
    clearToken()
    window.dispatchEvent(new Event('sih:signed-out'))
    throw new NotSignedIn()
  }
  if (!r.ok) throw new Error(`${r.status} ${r.statusText} (${BASE}${path})`)
  return URL.createObjectURL(await r.blob())
}

/** Reports hang off the survey, not the job. */
export const reportPath = (surveyId: number, format: 'json' | 'csv') =>
  `/surveys/${surveyId}/report?format=${format}`

/** Pull a report down as a file, since a plain link cannot carry the token. */
export async function downloadReport(surveyId: number, format: 'json' | 'csv') {
  const url = await fetchBlobUrl(reportPath(surveyId, format))
  const a = document.createElement('a')
  a.href = url
  a.download = `survey-${surveyId}-report.${format}`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

export const jobImagePath = (jobId: number) => `/jobs/${jobId}/image`

// --- registry -------------------------------------------------------------

export const getRegistry = async (): Promise<Hazard[]> => {
  const res = await req<RegistryResponse>('/registry')
  return res.entries || []
}

/** GeoJSON risk grid, built from present and unconfirmed hazards only. */
export const getHeatmap = () => req<{ type: string; features: unknown[] }>('/registry/heatmap')

// --- recovery -------------------------------------------------------------

export const getRecoveryPlan = (hazardId: string) =>
  req<RecoveryPlan>(`/recovery/hazards/${hazardId}/plan`)

export const getDayPlan = (hazardIds: string[], hoursAvailable = 8) =>
  req<DayPlan>(
    '/recovery/day-plan',
    json({ hazard_ids: hazardIds, hours_available: hoursAvailable })
  )

// --- active learning ------------------------------------------------------

export const rankForAnnotation = (images?: string[], topK = 50) =>
  req<RankResponse>('/active-learning/rank', json({ images, top_k: topK }))
