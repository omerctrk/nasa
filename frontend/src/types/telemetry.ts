/**
 * Metin alanları düz string (tek dil, ör. backend'den) veya { tr, en } olabilir.
 * Ekranda göstermek için: usePrefs().pick(alan)
 */
export type Text = string | { tr: string; en: string };

export type MetricStatus = 'normal' | 'warning' | 'critical';

export interface VitalMetric {
  id: string;
  name: Text;
  shortName: string;
  value: number;
  unit: string;
  minNormal: number;
  maxNormal: number;
  status: MetricStatus;
  history: number[]; // Last 20-30 data points for sparklines
  trend: 'up' | 'down' | 'stable';
  changeRate: string;
  category: 'cardio' | 'metabolic' | 'respiratory' | 'thermal' | 'ocular' | 'neuro';
  description: Text;
  /** Backend eşik politikasıyla karşılaştırıldı mı? false → eşik yok; durum "normal" SAYILMAZ */
  rangeKnown?: boolean;
  lowerLimit?: number | null;
  upperLimit?: number | null;
  /** Backend ölçüm kodu (ör. heart_rate) */
  code?: string;
  /** Son kayıt sentetik demo verisi mi (MeasurementRecords.source = synthetic) */
  synthetic?: boolean;
  /** Son kaydın tarihi (YYYY-MM-DD) */
  lastDate?: string;
}

export interface AstronautProfile {
  id: string;
  name: string;
  role: Text;
  mission: Text;
  bloodType: string;
  age: number;
  weightKg: number;
  heightCm: number;
  evaHours: number;
  avatarUrl: string;
  solDay: number;
  spaceStationModule: string;
  /** core.Astronauts.astronaut_id, ör. "A007" */
  astronautId?: string;
  /** core.Astronauts.mission_id, ör. "M01" */
  missionId?: string;
  /** İkinci profil yalnız gösterimdir: canlı test/veri girişi kapalı */
  isDisplayOnly?: boolean;
  sex?: 'M' | 'F' | null;
}

export type AnatomyZoneId = 'head' | 'chest' | 'abdomen' | 'musculoskeletal';

export interface AnatomyZoneInfo {
  id: AnatomyZoneId;
  title: string;
  subtitle: string;
  status: MetricStatus;
  metrics: { label: string; value: string; status: MetricStatus }[];
  description: string;
  recommendedActions: string[];
}

export interface AnomalyAlert {
  id: string;
  severity: MetricStatus;
  title: Text;
  description: Text;
  timestamp: Text;
  parameter: Text;
  protocolCode: string;
  steps: Text[];
  countermeasure: Text;
  notifiedGroundControl: boolean;
  /** Backend bağlantısı (ops.Alerts) — demo verisinde boş kalır */
  backend?: {
    alertId: string;
    module: 'anomaly' | 'sans';
    status: 'OPEN' | 'ACKNOWLEDGED' | 'RESOLVED';
    /** Anomali: normal/watch/review · SANS: green/yellow/red */
    level?: string;
    anomalyResultId?: string | null;
    sansAnalysisId?: number | null;
  };
}

export interface DailyRecommendation {
  id: string;
  category: 'sleep' | 'hydration' | 'exercise' | 'rest';
  title: Text;
  target: Text;
  current: Text;
  recommendation: Text;
  priority: 'high' | 'medium' | 'low';
}

export type RiskLevel = 'low' | 'medium' | 'high';

export interface VisionTestResult {
  date: Text;
  acuityScore: string;
  eyePressureMmHg: number;
  sansRisk: RiskLevel;
  accuracyPercent: number;
}

export interface CognitiveTestResult {
  date: Text;
  reactionTimeMs: number;
  accuracyPercent: number;
  memoryLevel: number;
  fatigueIndexPercent: number;
  readinessLevel: Text;
}
