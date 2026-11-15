/** Anomali sonucunu ekranda okumak için yardımcılar (değer üretmez; sonucun kendi alanları). */
import type { AdviceDriver, BreachDriver, Result } from '../../live/api';
import { MEASUREMENT_LABELS } from './thresholdStatus';

export const isBreach = (d: BreachDriver | AdviceDriver): d is BreachDriver => (d as AdviceDriver).type !== 'advice';
export const adviceOf = (r: Result | null): AdviceDriver | null =>
  (r?.drivers.find((d) => (d as AdviceDriver).type === 'advice') as AdviceDriver | undefined) ?? null;

/** "Nabız 87 BPM (üst sınır 80)" — sürücünün kendi ondalık değerleri, yuvarlama yok */
export const breachText = (d: BreachDriver, lang: 'tr' | 'en'): string => {
  const label = MEASUREMENT_LABELS[d.measurement]?.[lang] ?? d.measurement;
  const value = String(Number(d.value));
  const bound = d.direction === 'up' ? d.upper : d.lower;
  const side = d.direction === 'up' ? (lang === 'tr' ? 'üst sınır' : 'upper limit') : (lang === 'tr' ? 'alt sınır' : 'lower limit');
  return `${label} ${value} ${d.unit} (${side} ${bound === null ? '—' : String(Number(bound))})`;
};

