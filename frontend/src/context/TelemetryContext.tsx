import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type {
  AnatomyZoneId, AnomalyAlert, AstronautProfile, CognitiveTestResult, DailyRecommendation,
  MetricStatus, VitalMetric, VisionTestResult,
} from '../types/telemetry';
import { getProfile, type MissionProfile, type MissionProfileId } from '../data/missionProfiles';
import { api, ApiError, type Alert, type Measurement, type Profile, type Result, type ThresholdPolicy } from '../live/api';
import { checkRange } from '../lib/backend/thresholdStatus';
import { adviceOf, baselineText, breachText, isBaseline, isBreach } from '../lib/backend/resultView';

export type NavigationTab = 'dashboard' | 'anatomy' | 'tests' | 'behavior' | 'reports' | 'settings' | 'vision-test' | 'cognitive-test';

interface TelemetryContextType {
  currentTab: NavigationTab;
  setCurrentTab: (tab: NavigationTab) => void;
  astronaut: AstronautProfile;
  setAstronautId: (id: string) => void;
  availableAstronauts: AstronautProfile[];
  vitals: Record<string, VitalMetric>;
  simulationScenario: 'normal' | 'hypertension' | 'eva_exertion' | 'fever';
  setSimulationScenario: (scenario: 'normal' | 'hypertension' | 'eva_exertion' | 'fever') => void;
  isSimulating: boolean;
  setIsSimulating: (active: boolean) => void;
  simulationIntervalMs: number;
  setSimulationIntervalMs: (ms: number) => void;
  selectedAnatomyZone: AnatomyZoneId | null;
  setSelectedAnatomyZone: (zone: AnatomyZoneId | null) => void;
  currentAlert: AnomalyAlert | null;
  resolveAlert: () => void;
  triggerManualAlert: (metricKey: string) => void;
  recommendations: DailyRecommendation[];
  visionTestHistory: VisionTestResult[];
  addVisionTestResult: (res: VisionTestResult) => void;
  cognitiveTestHistory: CognitiveTestResult[];
  addCognitiveTestResult: (res: CognitiveTestResult) => void;
  systemTelemetery: { satelliteLatencyMs: number; signalStrengthPercent: number; activeSensors: number; totalSensors: number; cabinPressureKPa: number; cabinO2Percent: number; co2Percent: number; radiationDosimetryMSv: number; metTimeHours: number };
  openActionPlanModal: boolean;
  setOpenActionPlanModal: (open: boolean) => void;
  missionProfile: MissionProfile;
  setMissionProfileId: (id: MissionProfileId) => void;
  loading: boolean;
  error: string | null;
  /** Son anomali analizi sonucu (backend anomaly_results) — AI paneli bunu gösterir */
  latestResult: Result | null;
  /** Analizin kullandığı eşik politikası (GET /thresholds) */
  thresholdPolicy: ThresholdPolicy | null;
  reload: () => void;
}

const TelemetryContext = createContext<TelemetryContextType | undefined>(undefined);
const TOKEN_KEY = 'astra-live-token';

const emptyVital = (id: string, shortName: string, unit: string, category: VitalMetric['category']): VitalMetric => ({
  id, name: shortName, shortName, value: Number.NaN, unit, minNormal: 0, maxNormal: 0,
  status: 'normal', history: [], trend: 'stable', changeRate: 'Kayıt yok', category,
  description: 'Veritabanında kayıt yok.',
});

const EMPTY_VITALS: Record<string, VitalMetric> = {
  pulse: emptyVital('pulse', 'Nabız', 'BPM', 'cardio'),
  glucose: emptyVital('glucose', 'Kan şekeri', 'mg/dL', 'metabolic'),
  oxygen: emptyVital('oxygen', 'SpO₂', '%', 'respiratory'),
  temperature: emptyVital('temperature', 'Vücut ısısı', '°C', 'thermal'),
  iop: emptyVital('iop', 'Göz içi basıncı', 'mmHg', 'ocular'),
  sleep: emptyVital('sleep', 'Uyku', 'saat', 'neuro'),
  // Sude'nin anatomi panelleri tansiyonu ayrı okur; backend kodları systolic_bp / diastolic_bp.
  bp_systolic: emptyVital('bp_systolic', 'Sistolik', 'mmHg', 'cardio'),
  bp_diastolic: emptyVital('bp_diastolic', 'Diyastolik', 'mmHg', 'cardio'),
  // Görev ortamı (sentetik demo kaynakları: kişisel dozimetre, kabin CO2 sensörü)
  radiation: emptyVital('radiation', 'Radyasyon dozu', 'mSv/d', 'respiratory'),
  co2: emptyVital('co2', 'Kabin CO₂', 'mmHg', 'respiratory'),
  // İzolasyon: günlük check-in (gerçek giriş)
  loneliness: emptyVital('loneliness', 'Yalnızlık', 'score_0_4', 'neuro'),
  crew: emptyVital('crew', 'Mürettebat ilişkisi', 'score_0_4', 'neuro'),
};

const emptyAstronaut: AstronautProfile = {
  id: '—', astronautId: '—', missionId: '—', name: 'Profil yükleniyor', role: '—', mission: '—',
  bloodType: '—', age: 0, weightKg: 0, heightCm: 0, evaHours: 0, avatarUrl: '', solDay: 0,
  spaceStationModule: '—', isDisplayOnly: false, sex: null,
};

const profileToAstronaut = (profile: Profile): AstronautProfile => ({
  ...emptyAstronaut, id: profile.astronaut_id, astronautId: profile.astronaut_id,
  missionId: profile.mission_id, name: profile.display_name, mission: profile.mission_name,
  isDisplayOnly: profile.is_display_only,
  // Backend ile aynı kural: görev günü = bugün(UTC) − gün 0, tam gün (round öğleden sonra +1 gösterirdi).
  solDay: Math.max(0, Math.floor((Date.now() - Date.parse(`${profile.mission_start_date}T00:00:00Z`)) / 86400000)),
});

const scenarioProfile = (scenario: string | null): MissionProfileId => {
  const name = (scenario ?? '').toLowerCase();
  return name.includes('transit') ? 'mars_transit' : name.includes('mars') ? 'mars_surface' : name.includes('moon') || name.includes('ay') ? 'moon' : 'iss';
};

/** Alarm kartı ve aksiyon planı, alarmın bağlı olduğu analiz sonucundan doldurulur. */
const asAlert = (alert: Alert, result: Result | null): AnomalyAlert => {
  const linked = result && result.id === alert.anomaly_result_id ? result : null;
  const breaches = linked ? linked.drivers.filter(isBreach) : [];
  const personal = linked ? linked.drivers.filter(isBaseline) : [];
  const advice = adviceOf(linked);
  const steps = linked ? linked.recommendation.split('\n').map((s) => s.trim()).filter(Boolean) : [];
  const actions = advice?.recommendations.map((r) => r.action).filter(Boolean) ?? [];
  const review = linked?.level === 'review';
  return {
    id: alert.alert_id, severity: alert.severity === 'CRITICAL' ? 'critical' : 'warning',
    title: linked
      ? (review ? { tr: 'İncele: uçuş hekimine yükseltildi', en: 'Review: escalated to flight surgeon' }
        : { tr: 'İzle: önceki günlerden sapma', en: 'Watch: deviation from previous days' })
      : `${alert.severity} alarm`,
    description: linked ? linked.summary
      : { tr: 'Bu alarmın analiz sonucu okunamadı.', en: 'The analysis result for this alert could not be read.' },
    timestamp: `${alert.created_at.slice(0, 10)} ${alert.created_at.slice(11, 16)} UTC`,
    parameter: personal.length || breaches.length
      ? { tr: [...personal.map((d) => baselineText(d, 'tr')), ...breaches.map((d) => breachText(d, 'tr'))].join('; '),
          en: [...personal.map((d) => baselineText(d, 'en')), ...breaches.map((d) => breachText(d, 'en'))].join('; ') }
      : alert.astronaut_id,
    protocolCode: alert.alert_id.slice(0, 12),
    steps,
    countermeasure: actions.length ? actions.join(' ')
      : { tr: 'Kart destesinde bu bulgu için onaylı önlem yok; karar uçuş hekimindedir.',
          en: 'No approved countermeasure card for this finding; the flight surgeon decides.' },
    notifiedGroundControl: true,
    backend: { alertId: alert.alert_id, module: 'anomaly', status: alert.status, level: linked?.level,
      anomalyResultId: alert.anomaly_result_id },
  };
};

const dateAdd = (date: string, days: number) => {
  const value = new Date(`${date}T00:00:00Z`);
  value.setUTCDate(value.getUTCDate() + days);
  return value.toISOString().slice(0, 10);
};

function vitalFromMeasurements(rows: Measurement[], policy: ThresholdPolicy | null): Record<string, VitalMetric> {
  const mappings: Record<string, string> = {
    heart_rate: 'pulse', blood_glucose: 'glucose', body_temperature: 'temperature',
    systolic_bp: 'bp_systolic', diastolic_bp: 'bp_diastolic',
    spo2: 'oxygen', intraocular_pressure: 'iop', radiation_dose: 'radiation', cabin_co2: 'co2',
    loneliness: 'loneliness', crew: 'crew',
  };
  const next = Object.fromEntries(Object.entries(EMPTY_VITALS).map(([key, value]) => [key, { ...value, history: [] }])) as Record<string, VitalMetric>;
  const codeOf = Object.fromEntries(Object.entries(mappings).map(([code, key]) => [key, code]));
  const grouped = new Map<string, Measurement[]>();
  for (const row of rows) {
    const key = mappings[row.measurement];
    if (!key || !row.valid || row.value_num === null || !Number.isFinite(Number(row.value_num))) continue;
    grouped.set(key, [...(grouped.get(key) ?? []), row]);
  }
  for (const [key, values] of grouped) {
    values.sort((a, b) => (a.measured_at ?? a.measured_date).localeCompare(b.measured_at ?? b.measured_date));
    const history = values.map((row) => Number(row.value_num));
    const last = history.at(-1)!;
    const previous = history.at(-2) ?? last;
    const unit = values.at(-1)!.unit;
    // Durum backend eşiğinden: aralık dışı → "dikkat"; eşik yoksa bilinmiyor (normal sayılmaz)
    const range = checkRange(policy, codeOf[key], unit, last);
    next[key] = { ...next[key], value: last, unit, history, trend: last > previous ? 'up' : last < previous ? 'down' : 'stable', changeRate: history.length > 1 ? `${last >= previous ? '+' : ''}${Math.round((last - previous) * 100) / 100} ${unit}` : 'Tek kayıt',
      status: range.status, rangeKnown: range.known, lowerLimit: range.lower, upperLimit: range.upper, code: codeOf[key],
      synthetic: values.at(-1)!.source === 'synthetic', lastDate: values.at(-1)!.measured_date,
      minNormal: range.lower ?? Number.NaN, maxNormal: range.upper ?? Number.NaN };
  }
  return next;
}

export const TelemetryProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [currentTab, setCurrentTabState] = useState<NavigationTab>('dashboard');
  const [astronaut, setAstronaut] = useState<AstronautProfile>(emptyAstronaut);
  const [availableAstronauts, setAvailableAstronauts] = useState<AstronautProfile[]>([]);
  const [vitals, setVitals] = useState<Record<string, VitalMetric>>(EMPTY_VITALS);
  const [currentAlert, setCurrentAlert] = useState<AnomalyAlert | null>(null);
  const [cognitiveTestHistory, setCognitiveTestHistory] = useState<CognitiveTestResult[]>([]);
  const [selectedAnatomyZone, setSelectedAnatomyZone] = useState<AnatomyZoneId | null>(null);
  const [openActionPlanModal, setOpenActionPlanModal] = useState(false);
  const [missionProfileId, setMissionProfileId] = useState<MissionProfileId>('iss');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [latestResult, setLatestResult] = useState<Result | null>(null);
  const [thresholdPolicy, setThresholdPolicy] = useState<ThresholdPolicy | null>(null);

  const reload = useCallback(() => {
    let active = true;
    const load = async () => {
      setLoading(true); setError(null);
      try {
        let token = sessionStorage.getItem(TOKEN_KEY);
        if (!token && import.meta.env.DEV) {
          token = await api.devSession('ASTRONAUT');
          sessionStorage.setItem(TOKEN_KEY, token);
        }
        if (!token) throw new Error('Oturum bulunamadı.');
        const me = (await api.me(token)).data;
        if (me.role !== 'ASTRONAUT') throw new Error('Bu tasarım astronot hesabıyla açılmalıdır.');
        const profile = (await api.profile(token)).data;
        const end = dateAdd(profile.mission_start_date, profile.mission_length_days);
        const ranges: { start: string; end: string }[] = [];
        for (let start = profile.mission_start_date; start < end; start = dateAdd(start, 120)) ranges.push({ start, end: dateAdd(start, 120) < end ? dateAdd(start, 120) : end });
        const pages = await Promise.all(ranges.map((range) => api.measurements(token!, me.role, profile.astronaut_id, range.start, range.end)));
        const rows = pages.flatMap((page) => page.data);
        const lastDate = rows.map((row) => row.measured_date).sort().at(-1) ?? profile.mission_start_date;
        const start = dateAdd(lastDate, -29);
        const todayUtc = new Date().toISOString().slice(0, 10);
        const [alerts, cognitive, policy, results] = await Promise.all([
          api.alerts(token, me.role), api.cognitive(token, start, dateAdd(lastDate, 1)),
          api.thresholds(token),
          api.results(token, me.role, profile.astronaut_id, dateAdd(todayUtc, -29), dateAdd(todayUtc, 1)),
        ]);
        const newest = [...results.data].sort((a, b) => b.created_at.localeCompare(a.created_at))[0] ?? null;
        if (!active) return;
        const current = profileToAstronaut(profile);
        setAstronaut(current); setAvailableAstronauts([current]); setMissionProfileId(scenarioProfile(profile.scenario));
        setThresholdPolicy(policy.data);
        setVitals(vitalFromMeasurements(rows, policy.data));
        setLatestResult(newest);
        const alert = [...alerts.data].sort((a, b) => b.created_at.localeCompare(a.created_at)).find((row) => row.status !== 'RESOLVED');
        let linked: Result | null = null;
        if (alert?.anomaly_result_id) {
          linked = results.data.find((r) => r.id === alert.anomaly_result_id) ?? null;
          if (!linked) linked = (await api.result(token, me.role, alert.anomaly_result_id).catch(() => null))?.data ?? null;
        }
        if (!active) return;
        setCurrentAlert(alert ? asAlert(alert, linked) : null);
        setCognitiveTestHistory(cognitive.data.map((row) => ({ date: row.taken_at, reactionTimeMs: row.mean_rt_ms ?? 0, accuracyPercent: row.accuracy === null ? 0 : Math.round(row.accuracy * 100), memoryLevel: 0, fatigueIndexPercent: 0, readinessLevel: row.valid ? 'Geçerli kayıt' : 'Geçersiz kayıt' })));
      } catch (cause) {
        if (active) setError(cause instanceof ApiError ? cause.message : cause instanceof Error ? cause.message : 'Veri yüklenemedi.');
      } finally { if (active) setLoading(false); }
    };
    void load();
    return () => { active = false; };
  }, []);

  useEffect(() => reload(), [reload]);
  const setCurrentTab = (tab: NavigationTab) => { if (tab !== 'anatomy') setSelectedAnatomyZone(null); setCurrentTabState(tab); };
  const missionProfile = getProfile(missionProfileId);
  const value = useMemo(() => ({
    currentTab, setCurrentTab, astronaut, setAstronautId: () => undefined, availableAstronauts, vitals,
    simulationScenario: 'normal' as const, setSimulationScenario: () => undefined, isSimulating: false, setIsSimulating: () => undefined,
    simulationIntervalMs: 0, setSimulationIntervalMs: () => undefined, selectedAnatomyZone, setSelectedAnatomyZone,
    currentAlert, resolveAlert: () => setCurrentAlert(null), triggerManualAlert: () => undefined,
    recommendations: [] as DailyRecommendation[], visionTestHistory: [] as VisionTestResult[], addVisionTestResult: () => undefined,
    cognitiveTestHistory, addCognitiveTestResult: () => undefined,
    systemTelemetery: { satelliteLatencyMs: 0, signalStrengthPercent: 0, activeSensors: 0, totalSensors: 0, cabinPressureKPa: 0, cabinO2Percent: 0, co2Percent: 0, radiationDosimetryMSv: 0, metTimeHours: 0 },
    openActionPlanModal, setOpenActionPlanModal, missionProfile, setMissionProfileId, loading, error, reload,
    latestResult, thresholdPolicy,
  }), [currentTab, astronaut, availableAstronauts, vitals, selectedAnatomyZone, currentAlert, cognitiveTestHistory, openActionPlanModal, missionProfile, loading, error, reload, latestResult, thresholdPolicy]);
  return <TelemetryContext.Provider value={value}>{children}</TelemetryContext.Provider>;
};

export const useTelemetry = () => {
  const context = useContext(TelemetryContext);
  if (!context) throw new Error('useTelemetry must be used within a TelemetryProvider');
  return context;
};
