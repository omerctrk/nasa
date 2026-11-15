/**
 * Anomali analiz işi (ops.AnalysisJobs) istemcisi.
 *
 * Şema kuralları:
 * - İstek idempotency_key ile yazılır, 202 + iş döner. Aynı anahtar farklı içerikle → 409.
 * - Yaşam döngüsü: QUEUED → SYNCING → ANALYZING → COMPLETED / FAILED.
 * - Geçici hatada backend bir kez kendisi tekrar dener; yine başarısızsa FAILED + elle tekrar.
 * - Başarısızlıkta sahte "normal" sonucu gösterilmez.
 * - Yetersiz/geçersiz veride iş COMPLETED olabilir ama sonuç yoktur (evaluation_status).
 *
 * UÇ NOKTALAR (ASTRA backend, contracts/backend-contract.md §8):
 *   POST /analysis/jobs              { module: 'anomaly', idempotency_key, module_scope } → 202 {job_id, module, state, status_url}
 *   GET  /analysis/jobs/{job_id}     → iş durumu
 *   POST /analysis/jobs/{job_id}/retry → 202 {job_id, module, state, status_url}
 *   GET  /me/anomaly-results/{id}    → sonuç ayrıntısı (özet, sürücüler, öneri, seviye)
 */
import { USE_MOCK, apiRequest, ApiError } from '../apiClient';
import type { AnalysisJob, AnomalyResult, JobState } from './types';

// ---------------------------------------------------------------- sahte iş akışı (yalnız demo)

type MockJob = AnalysisJob & { startedAt: number; fail: boolean; result?: AnomalyResult };
const mockJobs = new Map<string, MockJob>();
const mockByKey = new Map<string, string>();

const isMockOffline = () => {
  try {
    return localStorage.getItem('ahms-mock-offline') === '1' || navigator.onLine === false;
  } catch {
    return false;
  }
};

const uuid = () =>
  typeof crypto !== 'undefined' && 'randomUUID' in crypto ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`;

/** Geçen süreye göre iş durumunu ilerletir */
const advance = (j: MockJob): MockJob => {
  if (j.state === 'COMPLETED' || j.state === 'FAILED') return j;
  const el = Date.now() - j.startedAt;
  const now = new Date().toISOString();
  let state: JobState = 'QUEUED';
  if (el > 800) state = 'SYNCING';
  if (el > 2000) state = 'ANALYZING';
  if (el > 4200) state = j.fail ? 'FAILED' : 'COMPLETED';
  j.state = state;
  j.updated_at = now;
  if (state === 'FAILED') {
    j.error_code = 'PROVIDER_TIMEOUT'; // bir otomatik tekrardan sonra
  }
  if (state === 'COMPLETED' && !j.result) {
    const id = uuid();
    j.result = {
      id,
      astronaut_id: j.astronaut_id,
      mission_day: null,
      created_at: now,
      module_scope: 'combined',
      measurement: null,
      eye: null,
      algorithm: 'threshold_rules_plus_llm',
      model_version: 'mock',
      anomaly_score: null,
      is_anomaly: false,
      level: 'normal',
      summary:
        'Güncel değerler son 7 günün ve 74 günlük geçmişin olağan aralığında. (Demo: sahte backend sonucu)',
      drivers_json: [],
      baseline_status: 'provisional',
      data_quality_status: 'valid',
      recommendation: 'Planlı ölçümlere devam edin.',
      data_cutoff_at: now,
    };
    j.evaluation_status = 'evaluated';
    j.anomaly_result_id = id;
  }
  return j;
};

const mock = {
  async create(key: string, astronautId: string): Promise<AnalysisJob> {
    await new Promise((r) => setTimeout(r, 300));
    const existing = mockByKey.get(key);
    if (existing) return publicJob(mockJobs.get(existing)!);
    const now = new Date().toISOString();
    const job: MockJob = {
      job_id: uuid(),
      module: 'anomaly',
      state: 'QUEUED',
      evaluation_status: null,
      error_code: null,
      created_at: now,
      updated_at: now,
      astronaut_id: astronautId,
      anomaly_result_id: null,
      sans_analysis_id: null,
      startedAt: Date.now(),
      fail: isMockOffline(),
    };
    mockJobs.set(job.job_id, job);
    mockByKey.set(key, job.job_id);
    return publicJob(job);
  },
  async get(id: string): Promise<AnalysisJob> {
    const j = mockJobs.get(id);
    if (!j) throw new ApiError(404, 'NOT_FOUND', 'Bu kayda erişemiyorsun.');
    return publicJob(advance(j));
  },
  async retry(id: string): Promise<AnalysisJob> {
    const j = mockJobs.get(id);
    if (!j) throw new ApiError(404, 'NOT_FOUND', 'Bu kayda erişemiyorsun.');
    // Elle tekrar: aynı dondurulmuş girdiyle yeniden dener
    Object.assign(j, { state: 'QUEUED', error_code: null, startedAt: Date.now(), fail: isMockOffline() });
    return publicJob(j);
  },
  async result(id: string): Promise<AnomalyResult> {
    for (const j of mockJobs.values()) if (j.result?.id === id) return j.result;
    throw new ApiError(404, 'NOT_FOUND', 'Bu kayda erişemiyorsun.');
  },
};

// eslint-disable-next-line @typescript-eslint/no-unused-vars
const publicJob = ({ startedAt, fail, result, ...job }: MockJob): AnalysisJob => ({ ...job });

// ---------------------------------------------------------------- dışa açık API

/** 202 cevabı: yalnız kimlik ve durum gelir; ekranın beklediği iş şekline tamamlanır */
interface JobAccepted {
  job_id: string;
  module: 'anomaly' | 'sans';
  state: JobState;
  status_url: string;
}
const fromAccepted = (a: JobAccepted, astronautId = ''): AnalysisJob => {
  const now = new Date().toISOString();
  return {
    job_id: a.job_id,
    module: a.module,
    state: a.state,
    evaluation_status: null,
    error_code: null,
    created_at: now,
    updated_at: now,
    astronaut_id: astronautId,
    anomaly_result_id: null,
    sans_analysis_id: null,
  };
};

/** Sonuç ayrıntısı: GET /me/anomaly-results/{id} (backend app/routers/alerts.py) */
export const RESULT_DETAILS_AVAILABLE = true;

/** Backend sonucu (drivers) → ekran tipi (drivers_json) */
interface BackendResult extends Omit<AnomalyResult, 'drivers_json' | 'measurement' | 'eye' | 'anomaly_score'> {
  drivers: unknown[];
}

export const analysisApi = {
  async createJob(idempotencyKey: string, astronautId: string): Promise<AnalysisJob> {
    if (USE_MOCK) return mock.create(idempotencyKey, astronautId);
    const r = await apiRequest<JobAccepted>('POST', '/analysis/jobs', {
      // SANS kapsamı backend'de kapatıldı; birleşik (fizyolojik + davranış) analiz istenir
      body: { module: 'anomaly', idempotency_key: idempotencyKey, module_scope: 'combined' },
    });
    return fromAccepted(r.data, astronautId);
  },
  async getJob(jobId: string): Promise<AnalysisJob> {
    if (USE_MOCK) return mock.get(jobId);
    return (await apiRequest<AnalysisJob>('GET', `/analysis/jobs/${jobId}`)).data;
  },
  async retryJob(jobId: string): Promise<AnalysisJob> {
    if (USE_MOCK) return mock.retry(jobId);
    return fromAccepted((await apiRequest<JobAccepted>('POST', `/analysis/jobs/${jobId}/retry`)).data);
  },
  async getResult(resultId: string): Promise<AnomalyResult> {
    if (USE_MOCK) return mock.result(resultId);
    const r = (await apiRequest<BackendResult>('GET', `/me/anomaly-results/${resultId}`)).data;
    const { drivers, ...rest } = r;
    return { ...rest, drivers_json: drivers, measurement: null, eye: null, anomaly_score: null };
  },
};

export const isTerminal = (s: JobState) => s === 'COMPLETED' || s === 'FAILED';
