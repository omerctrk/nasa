/**
 * Davranışsal modül API katmanı. Ekranlar yalnızca bu fonksiyonları kullanır.
 * USE_MOCK açıkken sahte backend'e, kapalıyken /api/v1/behavioral/... uç noktalarına gider.
 */
import { USE_MOCK, apiRequest, ApiError } from '../../lib/apiClient';
import { mockServer } from './mock/mockServer';
import type {
  Checkin,
  CheckinInput,
  CognitiveTest,
  CognitiveTestInput,
  ListResponse,
  MissionInfo,
  WeeklyAssessment,
  WeeklyAssessmentInput,
} from './types';

const B = '/behavioral';

export const behavioralApi = {
  /** Görev günü: ortak üst barın kullandığı kaynak (varsayım: /dashboard/me). Frontend hesaplamaz. */
  async getMission(): Promise<MissionInfo> {
    if (USE_MOCK) return (await mockServer.getMission()).data;
    const r = await apiRequest<MissionInfo>('GET', '/dashboard/me');
    return r.data;
  },

  /** from dahil, to hariç (UTC tarihleri) */
  async listCheckins(q: { from?: string; to?: string; limit?: number; cursor?: string | null }) {
    if (USE_MOCK) return mockServer.listCheckins(q);
    return apiRequest<ListResponse<Checkin>>('GET', `${B}/checkins`, { query: q });
  },

  /** Yeni kayıt: If-None-Match: *  ·  Güncelleme: If-Match: <ETag> */
  async putCheckin(date: string, input: CheckinInput, etag: string | null) {
    const headers: Record<string, string> = etag ? { 'If-Match': etag } : { 'If-None-Match': '*' };
    if (USE_MOCK) return mockServer.putCheckin(date, input, { ifMatch: etag ?? undefined, ifNoneMatch: etag ? undefined : '*' });
    return apiRequest<Checkin>('PUT', `${B}/checkins/${date}`, { body: input, headers });
  },

  async listTests(q: { limit?: number; cursor?: string | null } = {}) {
    if (USE_MOCK) return mockServer.listTests(q);
    return apiRequest<ListResponse<CognitiveTest>>('GET', `${B}/cognitive-tests`, { query: q });
  },

  async postTest(input: CognitiveTestInput, idempotencyKey: string) {
    const body = { ...input, client_request_id: idempotencyKey };
    if (USE_MOCK) return mockServer.postTest(body, idempotencyKey);
    return apiRequest<CognitiveTest>('POST', `${B}/cognitive-tests`, {
      body,
      headers: { 'Idempotency-Key': idempotencyKey },
    });
  },

  async listWeekly(q: { limit?: number; cursor?: string | null } = {}) {
    if (USE_MOCK) return mockServer.listWeekly(q);
    return apiRequest<ListResponse<WeeklyAssessment>>('GET', `${B}/weekly-assessments`, { query: q });
  },

  async postWeekly(input: WeeklyAssessmentInput, idempotencyKey: string) {
    const body = { ...input, client_request_id: idempotencyKey };
    if (USE_MOCK) return mockServer.postWeekly(body, idempotencyKey);
    return apiRequest<WeeklyAssessment>('POST', `${B}/weekly-assessments`, {
      body,
      headers: { 'Idempotency-Key': idempotencyKey },
    });
  },

  async putWeeklySharing(id: number, share: boolean) {
    if (USE_MOCK) return mockServer.putWeeklySharing(id, share);
    return apiRequest<WeeklyAssessment>('PUT', `${B}/weekly-assessments/${id}/sharing`, {
      body: { share_with_crew_medical: share },
    });
  },
};

/**
 * Liste uç noktası sayfalıdır (limit ≤ 100). Gerekirse tüm sayfaları çeker.
 * `stop` true dönerse (ör. 30 günden eskiye inildiyse) durur.
 */
export const fetchAllPages = async <T>(
  fetchPage: (cursor: string | null) => Promise<{ data: ListResponse<T> }>,
  stop?: (items: T[]) => boolean,
  maxPages = 10
): Promise<T[]> => {
  const all: T[] = [];
  let cursor: string | null = null;
  for (let p = 0; p < maxPages; p++) {
    const { data } = await fetchPage(cursor);
    all.push(...data.items);
    if (!data.next_cursor || (stop && stop(data.items))) break;
    cursor = data.next_cursor;
  }
  return all;
};

/** Hata koduna göre kullanıcıya gösterilecek mesaj (belgedeki tablo) */
export const errorMessage = (e: unknown, t: (tr: string, en: string) => string): string => {
  if (!(e instanceof ApiError)) return t('Beklenmeyen bir hata oluştu.', 'An unexpected error occurred.');
  switch (e.status) {
    case 401:
      return t('Oturumun sona erdi, lütfen tekrar giriş yap.', 'Your session has expired, please sign in again.');
    case 403:
    case 404:
      return t('Bu kayda erişemiyorsun.', "You can't access this record.");
    case 409:
      return t('Bu işlem zaten kaydedildi.', 'This has already been saved.');
    case 412:
      return t(
        'Bu check-in başka bir yerde güncellendi. Sayfayı yenileyip tekrar dene.',
        'This check-in was updated elsewhere. Refresh and try again.'
      );
    case 422:
      return e.message;
    case 0:
    case 503:
      return t('Şu anda kaydedilemiyor. Tekrar dene.', "Can't save right now. Try again.");
    default:
      return e.message || t('Beklenmeyen bir hata oluştu.', 'An unexpected error occurred.');
  }
};
