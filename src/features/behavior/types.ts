/**
 * Davranışsal ve Refleks modülü — API tipleri.
 * Cevap şekilleri backend netleşene kadar "önerilen" şekillerdir (bkz. arayüz belgesi).
 */

/**
 * Veri kökeni. Tabloda 'manual' | 'seed'; dış sözleşmede (API) seed → 'synthetic' olarak döner.
 * Bkz. BACKEND_TABLO_SEMASI §2 ve behavioral.* tabloları.
 */
export type DataSource = 'manual' | 'seed' | 'synthetic' | (string & {});

/** Simüle/sentetik kayıt mı? ("simüle veri" etiketi için) */
export const isSynthetic = (source: DataSource | undefined | null): boolean => source === 'seed' || source === 'synthetic';

export interface ListResponse<T> {
  items: T[];
  next_cursor: string | null;
}

// --- Check-in ---
export type SymptomCode =
  | 'bas_agrisi'
  | 'halsizlik'
  | 'bulanti'
  | 'bas_donmesi'
  | 'bulanik_gorme'
  | 'goz_baskisi'
  | 'sirt_agrisi'
  | 'oksuruk'
  | 'nefes_darligi'
  | 'bogaz_agrisi'
  | 'doku_lezyon'
  | 'sindirim';

export interface CheckinInput {
  mood: number; // 0–10
  energy: number; // 0–10
  stress: number; // 0–10
  loneliness: number; // 0–4
  crew: number; // 0–4
  bed_time: string; // "23:40"
  wake_time: string; // "06:10"
  sleep_quality: number; // 1–5
  symptoms: SymptomCode[];
}

export interface Checkin extends Omit<CheckinInput, 'bed_time' | 'wake_time' | 'symptoms'> {
  id: number;
  date: string; // UTC, "2026-11-14"
  mission_day: number;
  mood_index: number; // 0–100
  bed_time: string; // "23:40:00"
  wake_time: string;
  sleep_hours: number;
  /** behavioral.checkins.symptoms NULL olabilir */
  symptoms: SymptomCode[] | null;
  source: DataSource;
  created_at?: string;
  updated_at: string;
}

// --- Bilişsel testler ---
/** 'dsst' backend'de var; bu arayüzde henüz testi yok (kapsam dışı), gelirse yok sayılır. */
export type TestType = 'pvt' | 'rotation' | 'dsst';

export interface PvtTrial {
  i: number;
  delay_ms: number;
  rt_ms: number | null;
  false_start: boolean;
}

export type ShapeId = 's1' | 's2' | 's3' | 's4';
export type RotationAngle = 0 | 60 | 120 | 180;

export interface RotationTrial {
  i: number;
  shape: ShapeId;
  angle: RotationAngle;
  mirror: boolean;
  answer: 'same' | 'mirror' | null;
  rt_ms: number | null;
}

export interface CognitiveTestInput {
  test_type: TestType;
  duration_s: number;
  device: string;
  trials: PvtTrial[] | RotationTrial[];
  /** behavioral.cognitive_tests.client_request_id: Idempotency-Key ile aynı UUID */
  client_request_id?: string;
}

export interface CognitiveTest {
  id: number;
  taken_at: string;
  mission_day: number;
  test_type: TestType;
  n_trials: number;
  mean_rt_ms: number | null;
  median_rt_ms: number | null;
  speed: number | null;
  lapses: number | null;
  false_starts: number | null;
  /** Rotation/DSST doğruluk ORANI: 0–1 (yüzde değil). PVT'de null. */
  accuracy: number | null;
  /** Yalnız DSST; PVT ve rotation'da null */
  correct_count: number | null;
  valid: boolean;
  invalid_reason: string | null;
  device?: string;
  source: DataSource;
}

/** 0–1 oranı ekranda yüzdeye çevirir: 0.9375 → 93.8 */
export const accuracyPct = (a: number | null | undefined): number | null => (a == null ? null : Math.round(a * 1000) / 10);

// --- Haftalık ölçekler ---
export type WeeklyAnswerKey =
  | 'who5_1'
  | 'who5_2'
  | 'who5_3'
  | 'who5_4'
  | 'who5_5'
  | 'phq2_1'
  | 'phq2_2'
  | 'gad2_1'
  | 'gad2_2';

export interface WeeklyAssessmentInput {
  answers: Record<WeeklyAnswerKey, number>;
  share_with_crew_medical: boolean;
  /** behavioral.weekly_assessments.client_request_id: Idempotency-Key ile aynı UUID */
  client_request_id?: string;
}

export interface WeeklyAssessment {
  id: number;
  taken_at: string;
  mission_day: number;
  who5_score: number;
  phq2_score: number;
  gad2_score: number;
  share_with_crew_medical: boolean;
  source?: DataSource;
}

/** Görev günü bilgisi. core.Missions alanları varsa birlikte gelir. */
export interface MissionInfo {
  mission_day: number;
  date: string; // UTC
  mission_id?: string; // core.Missions.mission_id, ör. "M01"
  name?: string;
  start_date?: string; // görev günü 0'ın tarihi
  length_days?: number;
  scenario?: string | null; // "ISS" / "Mars" ...
}
