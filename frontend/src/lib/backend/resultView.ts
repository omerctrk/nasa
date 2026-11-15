/** Anomali sonucunu ekranda okumak için yardımcılar (değer üretmez; sonucun kendi alanları). */
import type { AdviceDriver, BaselineDriver, BreachDriver, Result } from '../../live/api';
import { MEASUREMENT_LABELS, unitText } from './thresholdStatus';

type Driver = BreachDriver | BaselineDriver | AdviceDriver;

/** Sabit güvenlik eşiği ihlali (eski sonuçlarda kind alanı yoktur) */
export const isBreach = (d: Driver): d is BreachDriver =>
  (d as AdviceDriver).type !== 'advice' && (d as BaselineDriver).kind !== 'baseline';
/** Bugün ↔ önceki günler sapması */
export const isBaseline = (d: Driver): d is BaselineDriver => (d as BaselineDriver).kind === 'baseline';
export const adviceOf = (r: Result | null): AdviceDriver | null =>
  (r?.drivers.find((d) => (d as AdviceDriver).type === 'advice') as AdviceDriver | undefined) ?? null;

/** "Nabız 87 BPM (üst sınır 80)" — sürücünün kendi ondalık değerleri, yuvarlama yok */
export const breachText = (d: BreachDriver, lang: 'tr' | 'en'): string => {
  const label = MEASUREMENT_LABELS[d.measurement]?.[lang] ?? d.measurement;
  const value = String(Number(d.value));
  const bound = d.direction === 'up' ? d.upper : d.lower;
  const side = d.direction === 'up' ? (lang === 'tr' ? 'üst sınır' : 'upper limit') : (lang === 'tr' ? 'alt sınır' : 'lower limit');
  return `${label} ${value} ${unitText(d.unit, lang)} (${side} ${bound === null ? '—' : String(Number(bound))})`;
};

/** "Uyku süresi 5.55 saat · önceki 73 gün ort. 7.64 (z −4.08)" */
export const baselineText = (d: BaselineDriver, lang: 'tr' | 'en'): string => {
  const label = MEASUREMENT_LABELS[d.measurement]?.[lang] ?? d.measurement;
  const z = Number(d.z);
  const zText = `${z > 0 ? '+' : z < 0 ? '−' : ''}${Math.abs(z).toFixed(2)}`;
  return lang === 'tr'
    ? `${label} ${String(Number(d.value))} ${unitText(d.unit, lang)} · önceki ${d.baseline_days} gün ort. ${String(Number(d.baseline_mean))} (z ${zText})`
    : `${label} ${String(Number(d.value))} ${unitText(d.unit, lang)} · previous ${d.baseline_days} days avg. ${String(Number(d.baseline_mean))} (z ${zText})`;
};

