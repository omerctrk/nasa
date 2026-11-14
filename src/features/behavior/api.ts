/**
 * Davranışsal modül API katmanı. Ekranlar yalnızca bu fonksiyonları kullanır.
 *
 * USE_MOCK açıkken sahte backend'e gider. Kapalıyken ASTRA backend'ine (bachand dalı,
 * contracts/backend-contract.md) gider ve cevapları ekranların beklediği şekle çevirir:
 *   - Uçlar /api/v1/me/... altında (eski öneri: /behavioral/...)
 *   - Listeler düz dizi döner, ?start=&end= ile çekilir ([start, end), en fazla 120 gün)
 *   - Test ve haftalık form hesaplanmış değerlerle gönderilir (bkz. scoring.ts)
 *   - Check-in: yeni kayıtta başlık yok, güncellemede If-Match; mood_index istemciden
 */
import { USE_MOCK, apiRequest, ApiError, type ApiResponse } from '../../lib/apiClient';
import { mockServer } from './mock/mockServer';
import { addDaysUtc, daysBetween, todayUtc } from './date';
import { moodIndex, summarizeTest, weeklyScores } from './scoring';
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

const ME = '/me';
/** Backend'in tek istekte izin verdiği en uzun aralık */
const MAX_RANGE_DAYS = 120;

/** Haftalık paylaşım ayarı backend'de henüz yok; yalnız sahte modda değiştirilebilir. */
export const SHARING_EDITABLE = USE_MOCK;

/** Son N günün aralığı: [bugün-(N-1), yarın) */
const recentRange = (days = MAX_RANGE_DAYS) => {
  const today = todayUtc();
  return { start: addDaysUtc(today, -(days - 1)), end: addDaysUtc(today, 1) };
};

/** Düz diziyi ekranların kullandığı liste biçimine çevirir (yeniden eskiye) */
const asList = <T>(r: ApiResponse<T[]>, key: (x: T) => string): ApiResponse<ListResponse<T>> => ({
  ...r,
  data: { items: [...(r.data ?? [])].sort((a, b) => key(b).localeCompare(key(a))), next_cursor: null },
});

/** /me/profile cevabı */
interface ProfileOut {
  astronaut_id: string;
  display_name: string;
  is_display_only: boolean;
  mission_id: string;
  mission_name: string;
  mission_start_date: string; // görev günü 0
  mission_length_days: number;
  scenario: string | null;
}

/** Aynı gönderimin tekrarında taken_at değişmesin (aynı istek → aynı kayıt) */
const takenAtByKey = new Map<string, string>();
const takenAtFor = (key: string) => {
  if (!takenAtByKey.has(key)) takenAtByKey.set(key, new Date().toISOString());
  return takenAtByKey.get(key)!;
};

export const behavioralApi = {
  /** Görev günü: /me/profile'daki görev başlangıcından (gün 0) bugünün UTC tarihine */
  async getMission(): Promise<MissionInfo> {
    if (USE_MOCK) return (await mockServer.getMission()).data;
    const { data: p } = await apiRequest<ProfileOut>('GET', `${ME}/profile`);
    const date = todayUtc();
    return {
      mission_day: daysBetween(p.mission_start_date, date),
      date,
      mission_id: p.mission_id,
      name: p.mission_name,
      start_date: p.mission_start_date,
      length_days: p.mission_length_days,
      scenario: p.scenario,
    };
  },

  /** from dahil, to hariç (UTC tarihleri) */
  async listCheckins(q: { from?: string; to?: string; limit?: number; cursor?: string | null }) {
    if (USE_MOCK) return mockServer.listCheckins(q);
    const def = recentRange();
    const r = await apiRequest<Checkin[]>('GET', `${ME}/checkins`, { query: { start: q.from ?? def.start, end: q.to ?? def.end } });
    return asList(r, (x) => x.date);
  },

  /** Bugünün kaydı ve ETag'i (güncellemede If-Match için). Kayıt yoksa null. */
  async getCheckin(date: string): Promise<{ item: Checkin | null; etag: string | null }> {
    if (USE_MOCK) {
      const r = await mockServer.listCheckins({ from: date, to: addDaysUtc(date, 1), limit: 1 });
      const item = r.data.items[0] ?? null;
      return { item, etag: item ? r.etag : null };
    }
    try {
      const r = await apiRequest<Checkin>('GET', `${ME}/checkins/${date}`);
      return { item: r.data, etag: r.etag };
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) return { item: null, etag: null };
      throw e;
    }
  },

  /** Yeni kayıt: başlık yok (sahte modda If-None-Match: *)  ·  Güncelleme: If-Match: <ETag> */
  async putCheckin(date: string, input: CheckinInput, etag: string | null) {
    if (USE_MOCK) return mockServer.putCheckin(date, input, { ifMatch: etag ?? undefined, ifNoneMatch: etag ? undefined : '*' });
    return apiRequest<Checkin>('PUT', `${ME}/checkins/${date}`, {
      body: { ...input, mood_index: moodIndex(input) },
      headers: etag ? { 'If-Match': etag } : {},
    });
  },

  async listTests(q: { limit?: number; cursor?: string | null } = {}) {
    if (USE_MOCK) return mockServer.listTests(q);
    const r = await apiRequest<CognitiveTest[]>('GET', `${ME}/cognitive-tests`, { query: recentRange() });
    const out = asList(r, (x) => x.taken_at);
    out.data.items = out.data.items.map((x) => ({ ...x, speed: x.speed ?? null }));
    return out;
  },

  async postTest(input: CognitiveTestInput, idempotencyKey: string) {
    if (USE_MOCK) return mockServer.postTest({ ...input, client_request_id: idempotencyKey }, idempotencyKey);
    const summary = summarizeTest(input.test_type, input.trials);
    const r = await apiRequest<Pick<CognitiveTest, 'id' | 'taken_at' | 'mission_day' | 'test_type' | 'valid'>>(
      'POST',
      `${ME}/cognitive-tests`,
      {
        body: {
          client_request_id: idempotencyKey,
          taken_at: takenAtFor(idempotencyKey),
          test_type: input.test_type,
          duration_s: Math.max(1, input.duration_s),
          ...summary,
          device: input.device,
          raw: input.trials, // ham denemeler de saklanır
        },
        headers: { 'Idempotency-Key': idempotencyKey },
      }
    );
    // Backend kısa özet döner; sonuç ekranı için gönderilen değerlerle birleştirilir
    return { ...r, data: { ...summary, ...r.data, device: input.device, source: 'manual' } as CognitiveTest };
  },

  async listWeekly(q: { limit?: number; cursor?: string | null } = {}) {
    if (USE_MOCK) return mockServer.listWeekly(q);
    const r = await apiRequest<WeeklyAssessment[]>('GET', `${ME}/weekly-assessments`, { query: recentRange() });
    return asList(r, (x) => x.taken_at);
  },

  async postWeekly(input: WeeklyAssessmentInput, idempotencyKey: string) {
    if (USE_MOCK) return mockServer.postWeekly({ ...input, client_request_id: idempotencyKey }, idempotencyKey);
    return apiRequest<WeeklyAssessment>('POST', `${ME}/weekly-assessments`, {
      body: {
        client_request_id: idempotencyKey,
        taken_at: takenAtFor(idempotencyKey),
        answers: input.answers,
        ...weeklyScores(input.answers),
        share_with_crew_medical: input.share_with_crew_medical,
      },
      headers: { 'Idempotency-Key': idempotencyKey },
    });
  },

  /** Backend'de henüz yok (PUT …/sharing). Gerçek modda ekranda anahtar gizlenir. */
  async putWeeklySharing(id: number, share: boolean) {
    if (USE_MOCK) return mockServer.putWeeklySharing(id, share);
    throw new ApiError(501, 'NOT_SUPPORTED', 'Paylaşım ayarı henüz değiştirilemiyor.');
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
