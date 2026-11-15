/** Typed client for the current FastAPI /api/v1 contract. */

const BASE = '/api/v1'

export class ApiError extends Error {
  constructor(public status: number, message: string, public code?: string) {
    super(message)
  }
}

export type User = {
  user_id: string
  email: string
  role: 'ASTRONAUT' | 'GROUND_CONTROL'
  astronaut_id: string | null
}
export type Profile = {
  astronaut_id: string
  display_name: string
  is_display_only: boolean
  mission_id: string
  mission_name: string
  mission_start_date: string
  mission_length_days: number
  scenario: string | null
}
export type Measurement = {
  record_id: string
  astronaut_id: string
  module: string
  measurement: string
  value_num: number | string | null
  value_text: string | null
  unit: string
  measured_date: string
  measured_at: string | null
  mission_day: number | null
  source: string
  valid: boolean
}
export type Checkin = {
  date: string
  mood: number
  energy: number
  stress: number
  loneliness: number
  crew: number
  mood_index: number
  bed_time: string
  wake_time: string
  sleep_hours: number
  sleep_quality: number
}
export type WeeklyAssessment = {
  id: number
  taken_at: string
  mission_day: number
  who5_score: number
  phq2_score: number
  gad2_score: number
  share_with_crew_medical: boolean
}
export type CognitiveTest = {
  id: number
  taken_at: string
  mission_day: number
  test_type: string
  mean_rt_ms: number | null
  accuracy: number | null
  valid: boolean
}
export type Alert = {
  alert_id: string
  astronaut_id: string
  severity: 'WARNING' | 'CRITICAL'
  status: 'OPEN' | 'ACKNOWLEDGED' | 'RESOLVED'
  created_at: string
  anomaly_result_id: string | null
  resolution_note: string | null
}
export type Job = {
  job_id: string
  state: 'QUEUED' | 'SYNCING' | 'ANALYZING' | 'COMPLETED' | 'FAILED'
  evaluation_status: 'evaluated' | 'insufficient_data' | 'invalid_data' | null
  error_code: string | null
  anomaly_result_id: string | null
}
export type Result = {
  id: string
  level: 'normal' | 'watch' | 'review'
  summary: string
  recommendation: string
  created_at: string
}
export type KnowledgeCard = {
  card_id: string
  type: string
  system: string
  metrics: string[]
  direction: string
  text: string
  source: string
  url: string
  locator: string
}
export type NotificationEvent = {
  event_id: string
  event_type: string
  created_at: string
  payload: Record<string, unknown>
}

type Options = { token?: string; method?: string; body?: unknown; query?: Record<string, string>;
  headers?: Record<string, string> }

export async function request<T>(path: string, options: Options = {}): Promise<{ data: T; etag: string | null }> {
  const query = options.query ? `?${new URLSearchParams(options.query)}` : ''
  const headers: Record<string, string> = { Accept: 'application/json', ...options.headers }
  if (options.token) headers.Authorization = `Bearer ${options.token}`
  if (options.body !== undefined) headers['Content-Type'] = 'application/json'
  const response = await fetch(`${BASE}${path}${query}`, {
    method: options.method ?? 'GET', headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
    signal: AbortSignal.timeout(15000),
  })
  const payload: unknown = response.status === 204 ? null : await response.json().catch(() => null)
  if (!response.ok) {
    const detail = (payload as { detail?: { message?: string; code?: string } } | null)?.detail
    throw new ApiError(response.status, detail?.message ?? `HTTP ${response.status}`, detail?.code)
  }
  return { data: payload as T, etag: response.headers.get('ETag') }
}

export const api = {
  devSession: async (role: User['role']) => {
    const response = await fetch('/__dev/session', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ role }), signal: AbortSignal.timeout(15000),
    })
    const payload = await response.json().catch(() => null) as { access_token?: string } | null
    if (!response.ok || !payload?.access_token) throw new ApiError(response.status, 'Yerel oturum açılamadı. API ve demo hesaplarını kontrol edin.')
    return payload.access_token
  },
  login: (email: string, password: string) => request<{ access_token: string }>('/auth/login', {
    method: 'POST', body: { email, password },
  }),
  me: (token: string) => request<User>('/auth/me', { token }),
  profile: (token: string) => request<Profile>('/me/profile', { token }),
  crew: (token: string) => request<Profile[]>('/ground/astronauts', { token }),
  measurements: (token: string, role: User['role'], astronautId: string, start: string, end: string) =>
    request<Measurement[]>(role === 'ASTRONAUT' ? '/me/measurements' : `/ground/astronauts/${encodeURIComponent(astronautId)}/measurements`,
      { token, query: { start, end } }),
  checkins: (token: string, start: string, end: string) =>
    request<Checkin[]>('/me/checkins', { token, query: { start, end } }),
  weekly: (token: string, start: string, end: string) =>
    request<WeeklyAssessment[]>('/me/weekly-assessments', { token, query: { start, end } }),
  cognitive: (token: string, start: string, end: string) =>
    request<CognitiveTest[]>('/me/cognitive-tests', { token, query: { start, end } }),
  checkin: (token: string, day: string) => request<Checkin>(`/me/checkins/${day}`, { token }),
  putCheckin: (token: string, day: string, body: Omit<Checkin, 'date' | 'sleep_hours'>, etag: string | null) =>
    request<Checkin>(`/me/checkins/${day}`, { token, method: 'PUT', body,
      ...(etag ? { headers: { 'If-Match': etag } } : {}) }),
  physiological: (token: string, body: { client_request_id: string; measurement: string; value_num: number;
    unit: string; measured_date: string }) => request<{ record_id: string }>('/me/physiological', { token, method: 'POST', body }),
  createJob: (token: string, idempotencyKey: string) => request<{ job_id: string }>('/analysis/jobs', {
    token, method: 'POST', body: { module: 'anomaly', module_scope: 'combined', idempotency_key: idempotencyKey },
  }),
  job: (token: string, id: string) => request<Job>(`/analysis/jobs/${id}`, { token }),
  result: (token: string, role: User['role'], id: string) =>
    request<Result>(role === 'ASTRONAUT' ? `/me/anomaly-results/${id}` : `/ground/anomaly-results/${id}`, { token }),
  alerts: (token: string, role: User['role']) => request<Alert[]>(role === 'ASTRONAUT' ? '/me/alerts' : '/ground/alerts', { token }),
  acknowledge: (token: string, id: string) => request<Alert>(`/ground/alerts/${id}/acknowledge`, { token, method: 'POST' }),
  resolve: (token: string, id: string, note: string) => request<Alert>(`/ground/alerts/${id}/resolve`, {
    token, method: 'POST', body: { resolution_note: note },
  }),
  cards: (token: string) => request<KnowledgeCard[]>('/knowledge-cards', { token }),
  createCard: (token: string, body: KnowledgeCard) => request<KnowledgeCard>('/knowledge-cards', { token, method: 'POST', body }),
  pending: (token: string) => request<NotificationEvent[]>('/notifications/pending', { token }),
  receipt: (token: string, id: string) => request(`/notifications/${id}/receipt`, { token, method: 'POST' }),
}
