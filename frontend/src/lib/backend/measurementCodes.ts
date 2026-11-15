/**
 * Ekrandaki gösterge anahtarları ↔ backend ölçüm kodları (anomaly.MeasurementDefinitions).
 *
 * Kodlar ve kanonik birimler ASTRA backend seed sözlüğünden (bachand, scripts/seed.py).
 * Birim dönüşümü yapılmaz: backend'e sözlükteki birimle aynen gönderilir.
 * SpO₂ ve göz içi basıncı (IOP) backend sözlüğünde yok; arayüzden de kaldırıldı.
 */
import type { MeasurementModule } from './types';

export interface MeasurementMapping {
  /** Ekrandaki gösterge anahtarı (TelemetryContext.vitals) */
  vitalKey: string;
  measurement_code: string;
  module: MeasurementModule;
  /** Backend kanonik birimi (sözlükteki yazımıyla) */
  unit: string;
  /** Sözlükteki teyit durumu (seed: "unconfirmed") */
  confirmed: boolean;
}

export const MEASUREMENT_MAP: MeasurementMapping[] = [
  { vitalKey: 'pulse', measurement_code: 'heart_rate', module: 'physiological', unit: 'BPM', confirmed: false },
  { vitalKey: 'bp_systolic', measurement_code: 'systolic_bp', module: 'physiological', unit: 'mmHg', confirmed: false },
  { vitalKey: 'bp_diastolic', measurement_code: 'diastolic_bp', module: 'physiological', unit: 'mmHg', confirmed: false },
  { vitalKey: 'temperature', measurement_code: 'body_temperature', module: 'physiological', unit: '°C', confirmed: false },
  { vitalKey: 'glucose', measurement_code: 'blood_glucose', module: 'physiological', unit: 'mg/dL', confirmed: false },
  // Uyku fizyolojik değil, davranış modülünden gelir: check-in sleep_hours
  { vitalKey: 'sleep', measurement_code: 'sleep_hours', module: 'behavioral', unit: 'h', confirmed: false },
];

export const mappingByCode = (code: string): MeasurementMapping | undefined =>
  MEASUREMENT_MAP.find((m) => m.measurement_code === code);

export const mappingByVital = (key: string): MeasurementMapping | undefined =>
  MEASUREMENT_MAP.find((m) => m.vitalKey === key);
