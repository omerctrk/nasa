/**
 * Ekrandaki gösterge anahtarları ↔ backend ölçüm kodları (anomaly.MeasurementDefinitions).
 *
 * ÖNEMLİ: Şemada fizyolojik ölçüm sözlüğünün kodları henüz verilmedi.
 * Aşağıdaki `measurement_code` değerleri ÖNERİDİR; backend sözlüğü gelince yalnızca
 * bu dosya güncellenir, ekranlar değişmez.
 */
import type { MeasurementModule } from './types';

export interface MeasurementMapping {
  /** Ekrandaki gösterge anahtarı (TelemetryContext.vitals) */
  vitalKey: string;
  measurement_code: string;
  module: MeasurementModule;
  /** Backend kanonik birimi */
  unit: string;
  /** Teyit durumu */
  confirmed: boolean;
}

export const MEASUREMENT_MAP: MeasurementMapping[] = [
  { vitalKey: 'pulse', measurement_code: 'heart_rate', module: 'physiological', unit: 'bpm', confirmed: false },
  { vitalKey: 'bp_systolic', measurement_code: 'blood_pressure_systolic', module: 'physiological', unit: 'mmHg', confirmed: false },
  { vitalKey: 'bp_diastolic', measurement_code: 'blood_pressure_diastolic', module: 'physiological', unit: 'mmHg', confirmed: false },
  { vitalKey: 'oxygen', measurement_code: 'spo2', module: 'physiological', unit: '%', confirmed: false },
  { vitalKey: 'temperature', measurement_code: 'body_temperature', module: 'physiological', unit: '°C', confirmed: false },
  { vitalKey: 'glucose', measurement_code: 'blood_glucose', module: 'physiological', unit: 'mg/dL', confirmed: false },
  // Göz içi basıncı şemadaki SANS testlerinde yok (near_acuity/contrast/amsler). Backend'e sorulacak.
  { vitalKey: 'iop', measurement_code: 'intraocular_pressure', module: 'physiological', unit: 'mmHg', confirmed: false },
  // Uyku fizyolojik değil, davranış modülünden gelir: behavioral.checkins.sleep_hours
  { vitalKey: 'sleep', measurement_code: 'sleep_hours', module: 'behavioral', unit: 'h', confirmed: false },
];

export const mappingByCode = (code: string): MeasurementMapping | undefined =>
  MEASUREMENT_MAP.find((m) => m.measurement_code === code);

export const mappingByVital = (key: string): MeasurementMapping | undefined =>
  MEASUREMENT_MAP.find((m) => m.vitalKey === key);
