/**
 * Ölçüm durumu = backend eşik politikası (GET /api/v1/thresholds, config/thresholds.json).
 *
 * Analizle AYNI kural (backend services/thresholds.py compare_threshold):
 * - Kural ölçüm kodu + modül + BİRİM ile eşleşir; birim farklıysa karşılaştırılmaz (dönüşüm yok).
 * - Sınır dahildir (boundary "inclusive"): değer > üst sınır veya < alt sınır → aralık dışı.
 * - Kural yoksa durum BİLİNMEZ; "normal" sayılmaz (bilinmeyen normal değildir).
 * - Politikada kritik sınır yoktur: aralık dışı = "dikkat" (backend alarmı da WARNING).
 */
import type { ThresholdPolicy, ThresholdRule } from '../../live/api';
import type { MetricStatus } from '../../types/telemetry';

export type RangeCheck = {
  /** false → bu ölçüm için tanımlı eşik yok (veya birim uyuşmuyor) */
  known: boolean;
  status: MetricStatus;
  lower: number | null;
  upper: number | null;
  /** 'above' | 'below' | 'within' | 'unknown' */
  position: 'above' | 'below' | 'within' | 'unknown';
  rule: ThresholdRule | null;
};

const num = (v: string | null): number | null => (v === null || v === '' ? null : Number(v));

export function findRule(policy: ThresholdPolicy | null, code: string, unit: string): ThresholdRule | null {
  if (!policy) return null;
  return policy.rules.find((r) => r.module === 'physiological' && r.measurement === code && r.unit === unit) ?? null;
}

export function checkRange(policy: ThresholdPolicy | null, code: string, unit: string, value: number): RangeCheck {
  const rule = findRule(policy, code, unit);
  if (!rule || !Number.isFinite(value)) {
    return { known: false, status: 'normal', lower: null, upper: null, position: 'unknown', rule: null };
  }
  const lower = num(rule.lower);
  const upper = num(rule.upper);
  if (upper !== null && value > upper) return { known: true, status: 'warning', lower, upper, position: 'above', rule };
  if (lower !== null && value < lower) return { known: true, status: 'warning', lower, upper, position: 'below', rule };
  return { known: true, status: 'normal', lower, upper, position: 'within', rule };
}

/** "Üst sınır 80 BPM" / "Alt sınır 50 · üst sınır 100 mmHg" */
export function limitText(check: RangeCheck, unit: string, t: (tr: string, en: string) => string): string {
  if (!check.known) return t('Eşik tanımlı değil', 'No threshold defined');
  const parts: string[] = [];
  if (check.lower !== null) parts.push(`${t('alt sınır', 'lower limit')} ${check.lower}`);
  if (check.upper !== null) parts.push(`${t('üst sınır', 'upper limit')} ${check.upper}`);
  const text = `${parts.join(' · ')} ${unit}`;
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** Ölçüm kodu → ekranda okunan ad */
export const MEASUREMENT_LABELS: Record<string, { tr: string; en: string }> = {
  heart_rate: { tr: 'Nabız', en: 'Heart rate' },
  systolic_bp: { tr: 'Büyük tansiyon', en: 'Systolic BP' },
  diastolic_bp: { tr: 'Küçük tansiyon', en: 'Diastolic BP' },
  blood_glucose: { tr: 'Kan şekeri', en: 'Blood glucose' },
  body_temperature: { tr: 'Vücut ısısı', en: 'Body temperature' },
};
