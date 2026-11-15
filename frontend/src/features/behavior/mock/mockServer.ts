/**
 * SAHTE BACKEND — yalnızca geliştirme/demo içindir.
 *
 * Buradaki puan hesapları backend'i taklit eder; gerçek kurallar backend'dedir.
 * Ekranlar (frontend) hiçbir puanı kendisi hesaplamaz, her zaman bu katmanın
 * ya da gerçek API'nin döndürdüğü değeri gösterir.
 *
 * Ağ hatasını denemek için: tarayıcıyı çevrimdışı yapın (DevTools > Network > Offline)
 * veya konsolda localStorage.setItem('ahms-mock-offline', '1').
 */
import checkinsFx from '../../../data/fixtures/behavioral/checkins.json';
import testsFx from '../../../data/fixtures/behavioral/cognitive-tests.json';
import weeklyFx from '../../../data/fixtures/behavioral/weekly-assessments.json';
import { ApiError, type ApiResponse } from '../../../lib/apiClient';
import type {
  Checkin,
  CheckinInput,
  CognitiveTest,
  CognitiveTestInput,
  ListResponse,
  MissionInfo,
  WeeklyAssessment,
  WeeklyAssessmentInput,
} from '../types';
import { daysBetween, todayUtc } from '../date';
import { moodIndex, summarizeTest, weeklyScores } from '../scoring';

const LAUNCH_DATE = '2026-09-01'; // görev günü 0

const db = {
  checkins: [...(checkinsFx.items as Checkin[])],
  checkinVersion: new Map<string, number>(),
  tests: [...(testsFx.items as CognitiveTest[])],
  weekly: [...(weeklyFx.items as WeeklyAssessment[])],
  idempotency: new Map<string, unknown>(),
  nextId: 1000,
};

const delay = (ms = 350) => new Promise((r) => setTimeout(r, ms));

const assertOnline = () => {
  let forced = false;
  try {
    forced = localStorage.getItem('ahms-mock-offline') === '1';
  } catch {
    /* yok say */
  }
  if (forced || (typeof navigator !== 'undefined' && navigator.onLine === false)) {
    throw new ApiError(0, 'NETWORK_ERROR', 'Network error');
  }
};

const ok = <T>(data: T, status = 200, etag: string | null = null): ApiResponse<T> => ({ data, status, etag });

const paginate = <T>(items: T[], limit = 20, cursor?: string | null): ListResponse<T> => {
  const l = Math.min(100, Math.max(1, limit));
  const start = cursor ? parseInt(cursor, 10) || 0 : 0;
  const page = items.slice(start, start + l);
  return { items: page, next_cursor: start + l < items.length ? String(start + l) : null };
};

const missionDay = (date: string) => daysBetween(LAUNCH_DATE, date);
const etagFor = (date: string) => `"checkin-${date}-v${db.checkinVersion.get(date) ?? 1}"`;

export const mockServer = {
  async getMission(): Promise<ApiResponse<MissionInfo>> {
    await delay(150);
    const date = todayUtc();
    // core.Missions alanları (demo varsayımı: M01, görev günü 0 = 1 Eylül 2026)
    return ok({
      mission_day: missionDay(date),
      date,
      mission_id: 'M01',
      name: 'AHMS Demo',
      start_date: LAUNCH_DATE,
      length_days: 180,
      scenario: 'ISS',
    });
  },

  // ---------------- Check-in ----------------
  async listCheckins(q: { from?: string; to?: string; limit?: number; cursor?: string | null }) {
    await delay();
    assertOnline();
    const items = db.checkins
      .filter((c) => (!q.from || c.date >= q.from) && (!q.to || c.date < q.to))
      .sort((a, b) => b.date.localeCompare(a.date));
    const page = paginate(items, q.limit, q.cursor);
    // Tek günlük sorguda o kaydın ETag'i döner
    const etag = page.items.length === 1 ? etagFor(page.items[0].date) : null;
    return ok(page, 200, etag);
  },

  async putCheckin(date: string, input: CheckinInput, h: { ifMatch?: string; ifNoneMatch?: string }) {
    await delay(450);
    assertOnline();
    const existing = db.checkins.find((c) => c.date === date);
    if (existing && h.ifNoneMatch === '*') {
      throw new ApiError(412, 'PRECONDITION_FAILED', 'Bu check-in başka bir yerde güncellendi.');
    }
    if (existing && h.ifMatch && h.ifMatch !== etagFor(date)) {
      throw new ApiError(412, 'PRECONDITION_FAILED', 'Bu check-in başka bir yerde güncellendi.');
    }

    const bed = input.bed_time.split(':').map(Number);
    const wake = input.wake_time.split(':').map(Number);
    let mins = wake[0] * 60 + wake[1] - (bed[0] * 60 + bed[1]);
    if (mins <= 0) mins += 1440;

    const record: Checkin = {
      id: existing?.id ?? db.nextId++,
      date,
      mission_day: missionDay(date),
      ...input,
      bed_time: `${input.bed_time}:00`,
      wake_time: `${input.wake_time}:00`,
      mood_index: moodIndex(input),
      sleep_hours: Math.round((mins / 60) * 100) / 100,
      source: 'manual',
      created_at: existing?.created_at ?? new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    db.checkins = [record, ...db.checkins.filter((c) => c.date !== date)];
    db.checkinVersion.set(date, (db.checkinVersion.get(date) ?? 1) + (existing ? 1 : 0));
    return ok(record, existing ? 200 : 201, etagFor(date));
  },

  // ---------------- Bilişsel testler ----------------
  async listTests(q: { limit?: number; cursor?: string | null }) {
    await delay();
    assertOnline();
    const items = [...db.tests].sort((a, b) => b.taken_at.localeCompare(a.taken_at));
    return ok(paginate(items, q.limit, q.cursor));
  },

  async postTest(input: CognitiveTestInput, idempotencyKey: string) {
    await delay(600);
    assertOnline();
    const prev = db.idempotency.get(idempotencyKey);
    if (prev) return ok(prev as CognitiveTest, 201);

    const date = todayUtc();
    const base = {
      id: db.nextId++,
      taken_at: new Date().toISOString(),
      mission_day: missionDay(date),
      test_type: input.test_type,
      n_trials: input.trials.length,
      source: 'manual',
    };

    // Özet hesap ortak dosyada (scoring.ts): gerçek backend'e de aynı değerler gider
    const result: CognitiveTest = { ...base, ...summarizeTest(input.test_type, input.trials) };
    db.tests = [result, ...db.tests];
    db.idempotency.set(idempotencyKey, result);
    return ok(result, 201);
  },

  // ---------------- Haftalık ----------------
  async listWeekly(q: { limit?: number; cursor?: string | null }) {
    await delay();
    assertOnline();
    const items = [...db.weekly].sort((a, b) => b.taken_at.localeCompare(a.taken_at));
    return ok(paginate(items, q.limit, q.cursor));
  },

  async postWeekly(input: WeeklyAssessmentInput, idempotencyKey: string) {
    await delay(500);
    assertOnline();
    const prev = db.idempotency.get(idempotencyKey);
    if (prev) return ok(prev as WeeklyAssessment, 201);
    const result: WeeklyAssessment = {
      id: db.nextId++,
      taken_at: new Date().toISOString(),
      mission_day: missionDay(todayUtc()),
      ...weeklyScores(input.answers),
      share_with_crew_medical: input.share_with_crew_medical,
      source: 'manual',
    };
    db.weekly = [result, ...db.weekly];
    db.idempotency.set(idempotencyKey, result);
    return ok(result, 201);
  },

  async putWeeklySharing(id: number, share: boolean) {
    await delay(250);
    assertOnline();
    const w = db.weekly.find((x) => x.id === id);
    if (!w) throw new ApiError(404, 'NOT_FOUND', 'Bu kayda erişemiyorsun.');
    w.share_with_crew_medical = share;
    return ok({ ...w });
  },
};
