/**
 * Test ve form özet hesapları — TEK YER.
 *
 * Backend (ASTRA, bachand dalı) şu an ham denemeleri değil, hesaplanmış değerleri bekliyor:
 *   bilişsel test → n_trials, mean_rt_ms, median_rt_ms, lapses, false_starts, accuracy, valid…
 *   haftalık ölçek → who5_score, phq2_score, gad2_score
 *   check-in      → mood_index (formül teyit edilene kadar istemciden)
 * Bu hesaplar yalnızca burada yapılır; sahte backend de aynı fonksiyonları kullanır.
 * Ekranlar puanı kendileri hesaplamaz, yalnız backend cevabını gösterir.
 * Formüller backend/modül sorumlusu tarafından teyit edilince yalnız bu dosya değişir.
 */
import type { CheckinInput, PvtTrial, RotationTrial, TestType, WeeklyAnswerKey } from './types';

const round1 = (n: number) => Math.round(n * 10) / 10;
const mean = (a: number[]) => (a.length ? a.reduce((s, v) => s + v, 0) / a.length : null);
const median = (a: number[]) => {
  if (!a.length) return null;
  const s = [...a].sort((x, y) => x - y);
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
};

export interface TestSummary {
  n_trials: number;
  mean_rt_ms: number | null;
  median_rt_ms: number | null;
  speed: number | null;
  lapses: number | null;
  false_starts: number | null;
  accuracy: number | null;
  correct_count: number | null;
  valid: boolean;
  invalid_reason: string | null;
}

/** PVT: 100 ms altı erken basma sayılır; 500 ms üstü ve cevapsız deneme dikkat kaybıdır. */
const summarizePvt = (trials: PvtTrial[]): TestSummary => {
  const rts = trials.filter((t) => !t.false_start && t.rt_ms !== null && t.rt_ms >= 100).map((t) => t.rt_ms as number);
  const falseStarts = trials.filter((t) => t.false_start || (t.rt_ms !== null && t.rt_ms < 100)).length;
  const valid = rts.length >= 5 && falseStarts <= Math.max(3, trials.length * 0.2);
  const m = mean(rts);
  const md = median(rts);
  return {
    n_trials: trials.length,
    mean_rt_ms: valid && m !== null ? round1(m) : null,
    median_rt_ms: valid && md !== null ? round1(md) : null,
    speed: valid ? Math.round((rts.reduce((s, v) => s + 1000 / v, 0) / rts.length) * 100) / 100 : null,
    lapses: valid ? rts.filter((r) => r > 500).length + trials.filter((t) => !t.false_start && t.rt_ms === null).length : null,
    false_starts: falseStarts,
    accuracy: null,
    correct_count: null,
    valid,
    invalid_reason: valid ? null : rts.length < 5 ? 'too_few_trials' : 'too_many_false_starts',
  };
};

/** Döndürme: doğruluk 0–1 oranı; ortalama süre yalnız doğru cevaplardan. */
const summarizeRotation = (trials: RotationTrial[]): TestSummary => {
  const correct = trials.filter((t) => t.answer !== null && (t.answer === 'mirror') === t.mirror);
  const m = mean(correct.map((t) => t.rt_ms as number));
  const valid = trials.length >= 8;
  return {
    n_trials: trials.length,
    mean_rt_ms: m !== null ? round1(m) : null,
    median_rt_ms: null,
    speed: null,
    lapses: null,
    false_starts: null,
    accuracy: Math.round((correct.length / Math.max(1, trials.length)) * 10000) / 10000,
    correct_count: null, // yalnız DSST
    valid,
    invalid_reason: valid ? null : 'too_few_trials',
  };
};

export const summarizeTest = (testType: TestType, trials: PvtTrial[] | RotationTrial[]): TestSummary =>
  testType === 'pvt' ? summarizePvt(trials as PvtTrial[]) : summarizeRotation(trials as RotationTrial[]);

/** WHO-5: ham toplam × 4 (0–100) · PHQ-2 ve GAD-2: ham toplam (0–6) */
export const weeklyScores = (a: Record<WeeklyAnswerKey, number>) => ({
  who5_score: (a.who5_1 + a.who5_2 + a.who5_3 + a.who5_4 + a.who5_5) * 4,
  phq2_score: a.phq2_1 + a.phq2_2,
  gad2_score: a.gad2_1 + a.gad2_2,
});

/** Ruh hali indeksi (0–100): ruh hali, enerji ve ters çevrilmiş stresin ortalaması. Formül teyit bekliyor. */
export const moodIndex = (c: Pick<CheckinInput, 'mood' | 'energy' | 'stress'>) => round1(((c.mood + c.energy + (10 - c.stress)) / 3) * 10);
