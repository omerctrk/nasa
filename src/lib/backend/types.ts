/**
 * Backend sözleşme tipleri — "ASTRA HEALTH Sade Backend Tablo Şeması v5.0 MVP" ile birebir.
 *
 * Bu dosya yalnızca tip tanımlar; ekranlar bu tipleri doğrudan kullanmaz.
 * Dönüşüm `adapters.ts` içindedir (backend DTO → ekranın kullandığı model).
 * Alan adları tablo sütunlarıyla aynı bırakıldı (snake_case). Tüm zamanlar UTC ISO metindir.
 */

// ---------------------------------------------------------------- core
export type UserRole = 'ASTRONAUT' | 'GROUND_CONTROL';

/** core.Missions */
export interface CoreMission {
  mission_id: string; // "M01"
  name: string;
  start_date: string; // görev günü 0'ın tarihi (YYYY-MM-DD)
  length_days: number;
  scenario: string | null; // "ISS" / "Mars" (SANS uyumluluk)
}

/** core.Astronauts (gösterimde kullanılan alanlar; genetik/SANS alanları ekrana gelmez) */
export interface CoreAstronaut {
  astronaut_id: string; // "A007"
  display_name: string;
  mission_id: string;
  is_display_only: boolean; // ikinci profil: canlı test/veri girişi kapalı
  age: number | null;
  sex: 'M' | 'F' | null;
  weight_kg: number | null;
}

/** Oturum açmış kullanıcı (core.Users; parola alanları asla gelmez) */
export interface CurrentUser {
  user_id: string;
  email: string;
  role: UserRole;
  astronaut_id: string | null; // GROUND_CONTROL için null
}

// ---------------------------------------------------------------- ortak ölçüm DTO
export type MeasurementModule = 'physiological' | 'behavioral' | 'sans';
export type EyeCode = 'OD' | 'OS';
/** Dış sözleşmede seed → synthetic. Göz kaynağında ayrıca test_screen olabilir. */
export type RecordSource = 'manual' | 'synthetic' | 'test_screen' | (string & {});

/** anomaly.v_measurements ortak okuma DTO'su */
export interface MeasurementDTO {
  record_id: string; // "physiological:UUID", "checkin:12:stress", "cognitive:8:pvt_mean_rt", "eye:42"
  astronaut_id: string;
  mission_id: string;
  module: MeasurementModule;
  measurement: string; // measurement_code
  value_num: number | null;
  value_text: string | null;
  unit: string;
  /** Her zaman dolu (YYYY-MM-DD) */
  measured_date: string;
  /** Yalnız gerçek saat biliniyorsa UTC timestamp; yoksa null */
  measured_at: string | null;
  time_precision?: 'date' | 'timestamp';
  protocol_version?: string;
  mission_day: number | null;
  eye: EyeCode | null;
  source: RecordSource;
  valid: boolean;
  quality_score: number | null; // 0–1
  session_id: string | null;
  metadata_json: unknown | null;
}

/** Fizyolojik manuel ölçüm gönderimi (anomaly.MeasurementRecords) */
export interface PhysiologicalMeasurementInput {
  measurement_code: string;
  value_num: number | null;
  value_text?: string | null;
  measured_date: string; // YYYY-MM-DD
  measured_at?: string | null; // UTC timestamp varsa
  time_precision: 'date' | 'timestamp';
  mission_day?: number | null;
  client_request_id: string; // tekrar gönderimde aynı UUID
}

// ---------------------------------------------------------------- anomali
export type AnomalyLevel = 'normal' | 'watch' | 'review';

/** anomaly.anomaly_results (sayısal sağlık puanı yok; anomaly_score NULL) */
export interface AnomalyResult {
  id: string;
  astronaut_id: string;
  mission_day: number | null;
  created_at: string;
  module_scope: MeasurementModule | 'combined';
  measurement: string | null;
  eye: EyeCode | null;
  algorithm: string; // "threshold_rules_plus_llm"
  model_version: string | null;
  anomaly_score: null;
  is_anomaly: boolean;
  level: AnomalyLevel;
  summary: string;
  drivers_json: unknown[];
  baseline_status: 'insufficient_data' | 'provisional' | 'ready';
  data_quality_status: 'valid' | 'low_quality' | 'missing_data';
  recommendation: string;
  data_cutoff_at: string;
}

// ---------------------------------------------------------------- SANS (göz)
export type SansLevel = 'green' | 'yellow' | 'red';
export type SansState = 'normal' | 'suspect' | 'confirmed';

/** sans.analiz */
export interface SansAnalysis {
  analysis_id: number;
  astronaut_id: string;
  session_id: string | null;
  flight_day: number;
  created_at: string;
  module: 'sans';
  risk: number; // 0–1 (anomali skoru değildir)
  level: SansLevel;
  state: SansState;
  summary: string | null;
  recommendation: string | null;
  drivers_json: unknown[] | null;
  trend_json: unknown | null;
  model_version: string | null;
}

/** sans.test_kaydi — tam oturum: 3 test × 2 göz = 6 satır */
export interface SansTestRecord {
  id: number;
  session_id: string;
  astronaut_id: string;
  flight_day: number;
  eye: EyeCode;
  test: 'near_acuity' | 'contrast' | 'amsler';
  value: number;
  unit: 'logMAR' | 'logCS' | 'cells';
  amsler_cells: unknown[] | null;
  n_correct: number | null;
  n_presented: number | null;
  duration_s: number | null;
}

/** sans.durum */
export interface SansStatus {
  astronaut_id: string;
  state: SansState;
  since_flight_day: number;
  retest_due_day: number | null;
  last_analysis_id: number | null;
}

// ---------------------------------------------------------------- ops
export type JobState = 'QUEUED' | 'SYNCING' | 'ANALYZING' | 'COMPLETED' | 'FAILED';

/** ops.AnalysisJobs (istemciye dönen alanlar) */
export interface AnalysisJob {
  job_id: string;
  module: 'anomaly' | 'sans';
  state: JobState;
  evaluation_status: 'evaluated' | 'insufficient_data' | 'invalid_data' | null;
  error_code: string | null;
  created_at: string;
  updated_at: string;
  astronaut_id: string;
  anomaly_result_id: string | null;
  sans_analysis_id: number | null;
}

export type AlertStatus = 'OPEN' | 'ACKNOWLEDGED' | 'RESOLVED';
export type AlertSeverity = 'WARNING' | 'CRITICAL';

/** ops.Alerts */
export interface BackendAlert {
  alert_id: string;
  status: AlertStatus;
  acknowledged_by: string | null;
  acknowledged_at: string | null;
  resolved_by: string | null;
  resolved_at: string | null;
  resolution_note: string | null;
  created_at: string;
  astronaut_id: string;
  module: 'anomaly' | 'sans';
  anomaly_result_id: string | null;
  sans_analysis_id: number | null;
  severity: AlertSeverity;
}

/** ops.NotificationEvents (WebSocket /ws/v1/notifications üzerinden gelen olay) */
export interface NotificationEvent {
  event_id: string; // tekrarları ayıklamak için
  job_id: string | null;
  alert_id: string | null;
  event_type: 'analysis.completed' | 'risk.alert.created' | 'emergency.updated';
  audience: UserRole;
  payload_json: unknown;
  created_at: string;
}
