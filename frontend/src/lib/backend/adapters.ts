/**
 * Backend DTO → ekran modeli dönüştürücüleri.
 *
 * Kurallar (BACKEND_TABLO_SEMASI):
 * - Eşik karşılaştırması ve anomali seviyesi backend'dedir; frontend eşik uydurmaz.
 * - Anomali: normal → alarm yok; watch / review → WARNING.
 * - SANS (göz): green/yellow/red → NORMAL/WARNING/CRITICAL.
 * - Ortak sayısal "sağlık puanı" üretilmez.
 * - Eksik değer 0 yapılmaz; valid=false kayıtlar grafiğe girmez.
 */
import type { AnomalyAlert, AstronautProfile, MetricStatus, VitalMetric } from '../../types/telemetry';
import type {
  AlertSeverity,
  AnomalyLevel,
  AnomalyResult,
  BackendAlert,
  CoreAstronaut,
  CoreMission,
  MeasurementDTO,
  SansAnalysis,
  SansLevel,
} from './types';
import { mappingByCode } from './measurementCodes';
import type { MissionProfileId } from '../../data/missionProfiles';

// ---------------------------------------------------------------- seviye eşlemeleri

export const anomalyLevelToStatus = (level: AnomalyLevel): MetricStatus => (level === 'normal' ? 'normal' : 'warning');

export const sansLevelToStatus = (level: SansLevel): MetricStatus =>
  level === 'red' ? 'critical' : level === 'yellow' ? 'warning' : 'normal';

export const alertSeverityToStatus = (s: AlertSeverity): 'warning' | 'critical' => (s === 'CRITICAL' ? 'critical' : 'warning');

// ---------------------------------------------------------------- görev / astronot

/** core.Missions.scenario → ekrandaki görev ortamı */
export const scenarioToProfile = (scenario: string | null | undefined): MissionProfileId => {
  const s = (scenario ?? '').toLowerCase();
  if (s.includes('transit')) return 'mars_transit';
  if (s.includes('mars')) return 'mars_surface';
  if (s.includes('moon') || s.includes('lunar') || s.includes('ay')) return 'moon';
  return 'iss';
};

/** Görev günü (backend verir; bu yalnız yedek hesap) */
export const missionDayOf = (mission: CoreMission, dateUtc: string): number =>
  Math.round((Date.parse(`${dateUtc}T00:00:00Z`) - Date.parse(`${mission.start_date}T00:00:00Z`)) / 86400000);

/**
 * core.Astronauts → ekrandaki profil. Backend'de olmayan görsel alanlar (foto, rol metni)
 * `base` ile korunur.
 */
export const astronautFromCore = (
  a: CoreAstronaut,
  missionDay: number,
  base: Partial<AstronautProfile> = {}
): AstronautProfile => ({
  id: a.astronaut_id,
  astronautId: a.astronaut_id,
  missionId: a.mission_id,
  isDisplayOnly: a.is_display_only,
  sex: a.sex,
  name: a.display_name,
  role: base.role ?? '',
  mission: base.mission ?? a.mission_id,
  bloodType: base.bloodType ?? '—',
  age: a.age ?? base.age ?? 0,
  weightKg: a.weight_kg ?? base.weightKg ?? 0,
  heightCm: base.heightCm ?? 0,
  evaHours: base.evaHours ?? 0,
  avatarUrl: base.avatarUrl ?? '',
  solDay: missionDay,
  spaceStationModule: base.spaceStationModule ?? '',
});

// ---------------------------------------------------------------- ölçümler

/**
 * anomaly.v_measurements kayıtlarını ekrandaki gösterge kartlarına dönüştürür.
 * - `levels`: ölçüm koduna göre son anomali seviyesi (anomaly_results.level). Yoksa durum 'normal'
 *   kalır; frontend kendi eşiğini uygulamaz.
 * - Geçersiz (valid=false) kayıtlar ve eşlemesi olmayan kodlar atlanır.
 */
export const vitalsFromMeasurements = (
  dtos: MeasurementDTO[],
  current: Record<string, VitalMetric>,
  levels: Partial<Record<string, AnomalyLevel>> = {},
  historyLength = 20
): Record<string, VitalMetric> => {
  const next: Record<string, VitalMetric> = { ...current };
  const byKey = new Map<string, MeasurementDTO[]>();

  for (const d of dtos) {
    if (!d.valid || d.value_num === null) continue;
    const m = mappingByCode(d.measurement);
    if (!m || !next[m.vitalKey]) continue;
    const list = byKey.get(m.vitalKey) ?? [];
    list.push(d);
    byKey.set(m.vitalKey, list);
  }

  for (const [key, list] of byKey) {
    const at = (d: MeasurementDTO) => d.measured_at ?? d.measured_date;
    list.sort((a, b) => at(a).localeCompare(at(b)));
    const values = list.map((d) => d.value_num as number);
    const last = values[values.length - 1];
    const prev = values.length > 1 ? values[values.length - 2] : last;
    const code = list[list.length - 1].measurement;
    const lvl = levels[code];
    next[key] = {
      ...next[key],
      value: last,
      unit: list[list.length - 1].unit || next[key].unit,
      history: values.slice(-historyLength),
      trend: last > prev ? 'up' : last < prev ? 'down' : 'stable',
      changeRate: `${last >= prev ? '+' : ''}${Math.round((last - prev) * 10) / 10} ${next[key].unit}`,
      status: lvl ? anomalyLevelToStatus(lvl) : 'normal',
    };
  }
  return next;
};

// ---------------------------------------------------------------- uyarılar

const splitSteps = (text: string | null | undefined): string[] =>
  (text ?? '')
    .split(/\r?\n|(?<=\.)\s+(?=[A-ZÇĞİÖŞÜ0-9])/)
    .map((s) => s.replace(/^[-•\d.)\s]+/, '').trim())
    .filter(Boolean);

/**
 * ops.Alerts + kaynak sonucu (anomali veya SANS) → eylem planı penceresinin modeli.
 * Metinler backend'den tek dilde gelir; ekran `pick()` ile düz metni olduğu gibi gösterir.
 */
export const alertFromBackend = (alert: BackendAlert, source: AnomalyResult | SansAnalysis): AnomalyAlert => {
  const isSans = alert.module === 'sans';
  const sans = isSans ? (source as SansAnalysis) : null;
  const anom = !isSans ? (source as AnomalyResult) : null;
  const measurement = anom?.measurement ?? (isSans ? 'SANS' : '');
  const summary = (sans ? sans.summary : anom?.summary) ?? '';
  const recommendation = (sans ? sans.recommendation : anom?.recommendation) ?? '';

  return {
    id: alert.alert_id,
    severity: alertSeverityToStatus(alert.severity),
    title: isSans ? `SANS · ${sans?.state ?? ''}` : measurement,
    description: summary,
    timestamp: `${alert.created_at.slice(11, 16)} UTC`,
    parameter: measurement,
    protocolCode: `${alert.module.toUpperCase()}-${alert.alert_id.slice(0, 8)}`,
    steps: splitSteps(recommendation),
    countermeasure: recommendation,
    notifiedGroundControl: true, // Alerts kule iş akışındadır
    backend: {
      alertId: alert.alert_id,
      module: alert.module,
      status: alert.status,
      level: sans ? sans.level : anom?.level,
      anomalyResultId: alert.anomaly_result_id,
      sansAnalysisId: alert.sans_analysis_id,
    },
  };
};

// ---------------------------------------------------------------- göz testi birimleri

/** Snellen paydası → logMAR: 20/20 → 0.0, 20/40 → 0.3 */
export const snellenToLogMAR = (snellen: string): number | null => {
  const m = snellen.match(/(\d+)\s*\/\s*(\d+)/);
  if (!m) return null;
  return Math.round(Math.log10(Number(m[2]) / Number(m[1])) * 100) / 100;
};

/** logMAR → Snellen: 0.0 → "20/20", 0.3 → "20/40" */
export const logMARToSnellen = (logmar: number): string => `20/${Math.round(20 * Math.pow(10, logmar))}`;
