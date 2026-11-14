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
  PvtTrial,
  RotationTrial,
  WeeklyAssessment,
  WeeklyAssessmentInput,
} from '../types';
import { daysBetween, todayUtc } from '../date';

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

const median = (a: number[]) => {
  if (!a.length) return null;
  const s = [...a].sort((x, y) => x - y);
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
};
const round1 = (n: number) => Math.round(n * 10) / 10;

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
      mood_index: round1(((input.mood + input.energy + (10 - input.stress)) / 3) * 10),
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

    let result: CognitiveTest;
    if (input.test_type === 'pvt') {
      const trials = input.trials as PvtTrial[];
      const rts = trials.filter((t) => !t.false_start && t.rt_ms !== null && t.rt_ms >= 100).map((t) => t.rt_ms as number);
      const falseStarts = trials.filter((t) => t.false_start || (t.rt_ms !== null && t.rt_ms < 100)).length;
      const valid = rts.length >= 5 && falseStarts <= Math.max(3, trials.length * 0.2);
      result = {
        ...base,
        mean_rt_ms: valid ? round1(rts.reduce((s, v) => s + v, 0) / rts.length) : null,
        median_rt_ms: valid ? round1(median(rts) ?? 0) : null,
        speed: valid ? Math.round((rts.reduce((s, v) => s + 1000 / v, 0) / rts.length) * 100) / 100 : null,
        lapses: valid ? rts.filter((r) => r > 500).length + trials.filter((t) => !t.false_start && t.rt_ms === null).length : null,
        false_starts: falseStarts,
        accuracy: null,
        correct_count: null,
        valid,
        invalid_reason: valid ? null : rts.length < 5 ? 'too_few_trials' : 'too_many_false_starts',
      };
    } else {
      const trials = input.trials as RotationTrial[];
      const correct = trials.filter((t) => t.answer !== null && (t.answer === 'mirror') === t.mirror);
      const rts = correct.map((t) => t.rt_ms as number);
      result = {
        ...base,
        mean_rt_ms: rts.length ? round1(rts.reduce((s, v) => s + v, 0) / rts.length) : null,
        median_rt_ms: null,
        speed: null,
        lapses: null,
        false_starts: null,
        accuracy: Math.round((correct.length / Math.max(1, trials.length)) * 10000) / 10000, // 0–1
        correct_count: null, // yalnız DSST
        valid: trials.length >= 8,
        invalid_reason: trials.length >= 8 ? null : 'too_few_trials',
      };
    }
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
    const a = input.answers;
    const result: WeeklyAssessment = {
      id: db.nextId++,
      taken_at: new Date().toISOString(),
      mission_day: missionDay(todayUtc()),
      who5_score: (a.who5_1 + a.who5_2 + a.who5_3 + a.who5_4 + a.who5_5) * 4,
      phq2_score: a.phq2_1 + a.phq2_2,
      gad2_score: a.gad2_1 + a.gad2_2,
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
