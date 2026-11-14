import React, { createContext, useContext, useState, useEffect } from 'react';
import {
  VitalMetric,
  AstronautProfile,
  AnomalyAlert,
  DailyRecommendation,
  VisionTestResult,
  CognitiveTestResult,
  AnatomyZoneId,
  MetricStatus,
} from '../types/telemetry';
import { playWarningTone } from '../utils/audio';
import { getProfile, type MissionProfile, type MissionProfileId } from '../data/missionProfiles';

export type NavigationTab = 'dashboard' | 'anatomy' | 'tests' | 'behavior' | 'reports' | 'settings' | 'vision-test' | 'cognitive-test';

interface TelemetryContextType {
  currentTab: NavigationTab;
  setCurrentTab: (tab: NavigationTab) => void;
  astronaut: AstronautProfile;
  setAstronautId: (id: string) => void;
  availableAstronauts: AstronautProfile[];
  vitals: Record<string, VitalMetric>;
  simulationScenario: 'normal' | 'warning_iop' | 'eva_exertion' | 'hypoxia';
  setSimulationScenario: (scenario: 'normal' | 'warning_iop' | 'eva_exertion' | 'hypoxia') => void;
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
  systemTelemetery: {
    satelliteLatencyMs: number;
    signalStrengthPercent: number;
    activeSensors: number;
    totalSensors: number;
    cabinPressureKPa: number;
    cabinO2Percent: number;
    co2Percent: number;
    radiationDosimetryMSv: number;
    metTimeHours: number;
  };
  openActionPlanModal: boolean;
  setOpenActionPlanModal: (open: boolean) => void;
  /** Görev ortamı (ISS, Ay, Mars yolculuğu, Mars yüzeyi) */
  missionProfile: MissionProfile;
  setMissionProfileId: (id: MissionProfileId) => void;
}

const TelemetryContext = createContext<TelemetryContextType | undefined>(undefined);

/**
 * Demo astronotları — core.Astronauts ile uyumlu: iki profil görünür,
 * yalnız biri (A007) aktif test/veri girer; A008 yalnız gösterimdir (is_display_only).
 * Backend bağlanınca `astronautFromCore()` ile bu kayıtlar API'den gelir; foto/rol gibi
 * yalnız görsel alanlar burada kalır.
 */
const ASTRONAUTS: AstronautProfile[] = [
  {
    id: 'A007',
    astronautId: 'A007',
    missionId: 'M01',
    isDisplayOnly: false,
    sex: 'F',
    name: 'Dr. Selin Alper',
    role: { tr: 'Görev Komutanı / Biyomedikal Uzmanı', en: 'Mission Commander / Biomedical Specialist' },
    mission: 'M01',
    bloodType: 'A Rh+',
    age: 38,
    weightKg: 64,
    heightCm: 172,
    evaHours: 28.5,
    avatarUrl: 'https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?auto=format&fit=crop&q=80&w=300',
    solDay: 74, // demo: görev günü 74 (backend'den gelecek)
    spaceStationModule: 'Node 2 (Harmony) / Columbus',
  },
  {
    id: 'A008',
    astronautId: 'A008',
    missionId: 'M01',
    isDisplayOnly: true,
    sex: 'M',
    name: 'Dr. Mark Vance',
    role: { tr: 'Uçuş Mühendisi & Sistem Operatörü', en: 'Flight Engineer & Systems Operator' },
    mission: 'M01',
    bloodType: '0 Rh+',
    age: 42,
    weightKg: 78,
    heightCm: 184,
    evaHours: 44.0,
    avatarUrl: 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&q=80&w=300',
    solDay: 74, // demo: görev günü 74 (backend'den gelecek)
    spaceStationModule: 'Destiny US Lab',
  },
];

// Initial mock sparkline history (20 points)
const createInitialHistory = (base: number, variation: number, count = 20) => {
  const points: number[] = [];
  let current = base;
  for (let i = 0; i < count; i++) {
    current = +(current + (Math.random() - 0.48) * variation).toFixed(1);
    points.push(current);
  }
  return points;
};

const INITIAL_VITALS: Record<string, VitalMetric> = {
  pulse: {
    id: 'pulse',
    name: { tr: 'Nabız', en: 'Heart Rate' },
    shortName: 'HR',
    value: 74,
    unit: 'bpm',
    minNormal: 60,
    maxNormal: 90,
    status: 'normal',
    history: createInitialHistory(74, 2.5),
    trend: 'stable',
    changeRate: '+1 bpm',
    category: 'cardio',
    description: { tr: 'Kardiyovasküler ritim ve kalp debisi takibi', en: 'Cardiovascular rhythm and cardiac output tracking' },
  },
  glucose: {
    id: 'glucose',
    name: { tr: 'Kan Şekeri', en: 'Blood Glucose' },
    shortName: 'GLU',
    value: 94,
    unit: 'mg/dL',
    minNormal: 70,
    maxNormal: 110,
    status: 'normal',
    history: createInitialHistory(94, 2),
    trend: 'stable',
    changeRate: '-2 mg/dL',
    category: 'metabolic',
    description: { tr: 'Plazma glukoz konsantrasyonu ve hücresel enerji dengesi', en: 'Plasma glucose concentration and cellular energy balance' },
  },
  oxygen: {
    id: 'oxygen',
    name: { tr: 'Oksijen Seviyesi', en: 'Oxygen Saturation' },
    shortName: 'SpO2',
    value: 98.4,
    unit: '%',
    minNormal: 96,
    maxNormal: 100,
    status: 'normal',
    history: createInitialHistory(98.4, 0.4),
    trend: 'stable',
    changeRate: '+0.2%',
    category: 'respiratory',
    description: { tr: 'Arteriyel hemoglobin oksijen satürasyonu', en: 'Arterial hemoglobin oxygen saturation' },
  },
  temperature: {
    id: 'temperature',
    name: { tr: 'Vücut Sıcaklığı', en: 'Body Temperature' },
    shortName: 'TEMP',
    value: 36.8,
    unit: '°C',
    minNormal: 36.3,
    maxNormal: 37.2,
    status: 'normal',
    history: createInitialHistory(36.8, 0.1),
    trend: 'stable',
    changeRate: '0.0 °C',
    category: 'thermal',
    description: { tr: 'Mikroyerçekimi termoregülasyon ve çekirdek vücut ısısı', en: 'Microgravity thermoregulation and core body temperature' },
  },
  iop: {
    id: 'iop',
    name: { tr: 'Göz İçi Basıncı', en: 'Intraocular Pressure' },
    shortName: 'IOP',
    value: 15.8,
    unit: 'mmHg',
    minNormal: 10,
    maxNormal: 21,
    status: 'normal',
    history: createInitialHistory(15.8, 0.6),
    trend: 'up',
    changeRate: '+0.4 mmHg',
    category: 'ocular',
    description: { tr: 'SANS riski ve sefalik sıvı kayması takibi', en: 'SANS risk and headward fluid shift tracking' },
  },
  sleep: {
    id: 'sleep',
    name: { tr: 'Uyku Süresi', en: 'Sleep Duration' },
    shortName: 'SLP',
    value: 7.6,
    unit: 'h',
    minNormal: 7.0,
    maxNormal: 8.5,
    status: 'normal',
    history: [7.2, 7.5, 6.8, 7.8, 7.4, 7.1, 7.6],
    trend: 'stable',
    changeRate: '+0.3 h',
    category: 'neuro',
    description: { tr: 'Sirkadiyen uyku döngüsü ve dinlenme kalitesi', en: 'Circadian sleep cycle and rest quality' },
  },
};

export const TelemetryProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [currentTab, setCurrentTabState] = useState<NavigationTab>('dashboard');
  const [selectedAstronautId, setSelectedAstronautId] = useState<string>('A007');
  const [vitals, setVitals] = useState<Record<string, VitalMetric>>(INITIAL_VITALS);
  const [simulationScenario, setSimulationScenario] = useState<'normal' | 'warning_iop' | 'eva_exertion' | 'hypoxia'>('normal');
  const [isSimulating, setIsSimulating] = useState<boolean>(true);
  const [simulationIntervalMs, setSimulationIntervalMs] = useState<number>(2500);
  const [selectedAnatomyZone, setSelectedAnatomyZone] = useState<AnatomyZoneId | null>(null);
  const [openActionPlanModal, setOpenActionPlanModal] = useState<boolean>(false);
  const [missionProfileId, setMissionProfileIdState] = useState<MissionProfileId>(() => {
    try {
      return (localStorage.getItem('ahms-mission') as MissionProfileId) || 'iss';
    } catch {
      return 'iss';
    }
  });
  const setMissionProfileId = (id: MissionProfileId) => {
    setMissionProfileIdState(id);
    try {
      localStorage.setItem('ahms-mission', id);
    } catch {
      /* yok say */
    }
  };
  const missionProfile = getProfile(missionProfileId);

  const [currentAlert, setCurrentAlert] = useState<AnomalyAlert | null>({
    id: 'ALT-71-402',
    severity: 'warning',
    title: { tr: 'Göz İçi Basıncında Artış (SANS)', en: 'Intraocular Pressure Change Watch (SANS Protocol)' },
    description: { tr: 'Ağırlıksız ortamda vücut sıvısının kafaya doğru kayması nedeniyle göz arkasında hafif bir basınç artışı saptandı. Görme testi yapmanız önerilir.', en: 'A mild pressure fluctuation in the optic nerve sheath was detected due to microgravity-induced headward fluid shift. A visual acuity test is recommended.' },
    timestamp: '10:14 UTC',
    parameter: { tr: 'Göz İçi Basıncı (IOP: 18.2 mmHg)', en: 'Intraocular Pressure (IOP: 18.2 mmHg)' },
    protocolCode: 'NASA-ESA/ISS-MED-OPT-04',
    steps: [
      { tr: 'Sırt üstü dinlenme pozisyonuna geçin ve baş aşağı / zorlayıcı hareketleri bırakın.', en: 'Move to a supine rest position and stop head-down / straining maneuvers.' },
      { tr: 'Sıvıyı baştan uzaklaştırmak için 20 dakika alt vücut negatif basınç (LBNP, Chibis giysisi) uygulayın.', en: 'Apply 20 minutes of Lower Body Negative Pressure (LBNP, Chibis suit) to draw fluid away from the head.' },
      { tr: 'Görme testini ve retina (OCT) taramasını tekrarlayın.', en: 'Repeat the Snellen vision test and the OCT retinal scan.' },
      { tr: 'Uçuş cerrahıyla (Houston MCC) bir görüşme kaydı oluşturun.', en: 'Log a tele-consultation with the flight surgeon (Houston MCC).' }
    ],
    countermeasure: { tr: 'LBNP seansı (-25 mmHg) ve elektrolitli sıvı takviyesi.', en: 'LBNP session (-25 mmHg) & electrolyte-supported hydration protocol.' },
    notifiedGroundControl: true,
  });

  const [recommendations] = useState<DailyRecommendation[]>([
    {
      id: 'rec-1',
      category: 'sleep',
      title: { tr: 'Sirkadiyen Aydınlatma & Uyku', en: 'Circadian Lighting & Sleep' },
      target: { tr: '7.5 - 8.0 saat', en: '7.5 - 8.0 hours' },
      current: { tr: '7.6 saat', en: '7.6 hours' },
      recommendation: {
        tr: 'Uyku kabininde mavi ışık filtresi saat 21:00 UTC\'de devreye alınacak. Hedeflenen derin uyku oranı: %22.',
        en: 'The blue-light filter in the crew quarters turns on at 21:00 UTC. Target deep-sleep share: 22%.',
      },
      priority: 'low',
    },
    {
      id: 'rec-2',
      category: 'hydration',
      title: { tr: 'Sıvı & Elektrolit Dengeleme', en: 'Fluid & Electrolyte Balance' },
      target: { tr: '2.4 Litre', en: '2.4 liters' },
      current: { tr: '1.8 Litre', en: '1.8 liters' },
      recommendation: { tr: 'Sefalik sıvı birikimini dengelemek ve böbrek taşı riskini önlemek için potasyum sitrat katkılı 600 ml su tüketin.', en: 'Drink 600 ml of water with potassium citrate to balance fluid shift and lower kidney-stone risk.' },
      priority: 'high',
    },
    {
      id: 'rec-3',
      category: 'exercise',
      title: { tr: 'ARED ve T2 Egzersiz Protokolü', en: 'ARED & T2 Exercise Protocol' },
      target: { tr: '120 Dakika', en: '120 minutes' },
      current: { tr: '95 Dakika', en: '95 minutes' },
      recommendation: { tr: 'Kemik mineral kaybını önlemek için ARED direnç seansına 25 dk squat ve T2 koşu bandı ilave edin.', en: 'Add 25 min of squats on ARED and a T2 treadmill run to slow bone mineral loss.' },
      priority: 'medium',
    },
    {
      id: 'rec-4',
      category: 'rest',
      title: { tr: 'Vestibüler & Nöro-Bilişsel Dinlenme', en: 'Vestibular & Neuro-Cognitive Rest' },
      target: { tr: '30 Dakika', en: '30 minutes' },
      current: { tr: '20 Dakika', en: '20 minutes' },
      recommendation: { tr: 'Columbus laboratuvarındaki sessiz modda 10 dakikalık vestibüler göz-odaklama ve nefes egzersizi planlandı.', en: 'A 10-minute quiet vestibular eye-focus and breathing exercise is scheduled in the Columbus lab.' },
      priority: 'low',
    },
  ]);

  const [visionTestHistory, setVisionTestHistory] = useState<VisionTestResult[]>([
    { date: { tr: 'Gün 70 (4 gün önce)', en: 'Day 70 (4 days ago)' }, acuityScore: '20/20', eyePressureMmHg: 15.2, sansRisk: 'low', accuracyPercent: 100 },
    { date: { tr: 'Gün 72 (2 gün önce)', en: 'Day 72 (2 days ago)' }, acuityScore: '20/22', eyePressureMmHg: 16.1, sansRisk: 'low', accuracyPercent: 92 },
    { date: { tr: 'Gün 73 (dün)', en: 'Day 73 (yesterday)' }, acuityScore: '20/20', eyePressureMmHg: 15.8, sansRisk: 'low', accuracyPercent: 96 },
  ]);

  const [cognitiveTestHistory, setCognitiveTestHistory] = useState<CognitiveTestResult[]>([
    { date: { tr: 'Gün 70', en: 'Day 70' }, reactionTimeMs: 218, accuracyPercent: 98, memoryLevel: 7, fatigueIndexPercent: 11, readinessLevel: { tr: 'Göreve Tam Hazır', en: 'Fully mission-ready' } },
    { date: { tr: 'Gün 72', en: 'Day 72' }, reactionTimeMs: 232, accuracyPercent: 95, memoryLevel: 6, fatigueIndexPercent: 15, readinessLevel: { tr: 'Göreve Hazır', en: 'Mission-ready' } },
    { date: { tr: 'Gün 73', en: 'Day 73' }, reactionTimeMs: 224, accuracyPercent: 96, memoryLevel: 7, fatigueIndexPercent: 12, readinessLevel: { tr: 'Göreve Tam Hazır', en: 'Fully mission-ready' } },
  ]);

  const [systemTelemetery, setSystemTelemetry] = useState({
    satelliteLatencyMs: 42,
    signalStrengthPercent: 98.6,
    activeSensors: 12,
    totalSensors: 12,
    cabinPressureKPa: 101.3,
    cabinO2Percent: 21.1,
    co2Percent: 0.38,
    radiationDosimetryMSv: 0.42,
    metTimeHours: 3412.4,
  });

  // Sekme değişince seçili bölgeyi sıfırla (anatomi sayfası hariç),
  // böylece ana panele dönüşte detay penceresi kendiliğinden açılmaz.
  const setCurrentTab = (tab: NavigationTab) => {
    if (tab !== 'anatomy') setSelectedAnatomyZone(null);
    setCurrentTabState(tab);
  };

  const astronaut = ASTRONAUTS.find((a) => a.id === selectedAstronautId) || ASTRONAUTS[0];

  const addVisionTestResult = (res: VisionTestResult) => {
    setVisionTestHistory((prev) => [res, ...prev]);
  };

  const addCognitiveTestResult = (res: CognitiveTestResult) => {
    setCognitiveTestHistory((prev) => [res, ...prev]);
  };

  const resolveAlert = () => {
    setCurrentAlert(null);
  };

  const triggerManualAlert = (metricKey: string) => {
    playWarningTone();
    if (metricKey === 'pulse') {
      setCurrentAlert({
        id: 'ALT-71-CARDIO',
        severity: 'critical',
        title: { tr: 'Akut Taşikardi / Kalp Ritmi Uyarısı', en: 'Acute Tachycardia / Heart Rhythm Alert' },
        description: { tr: 'Astronotun nabzı 118 bpm değerine yükseldi. Egzersiz aşırı yüklenmesi veya kardiyak stres şüphesi.', en: 'Heart rate rose to 118 bpm. Possible exercise overload or cardiac stress.' },
        timestamp: { tr: 'Şimdi', en: 'Now' },
        parameter: { tr: 'Nabız (118 bpm > 90 bpm normal)', en: 'Heart rate (118 bpm > 90 bpm normal)' },
        protocolCode: 'NASA-ESA/ISS-MED-CRD-09',
        steps: [
          { tr: 'Astronotun fiziksel aktiviteyi derhal sonlandırması ve istirahate geçmesi.', en: 'Stop physical activity immediately and rest.' },
          { tr: 'Portatif 12-derivasyonlu EKG elektrotlarının takılması.', en: 'Attach the portable 12-lead ECG electrodes.' },
          { tr: 'Kabin O2 fraksiyonunun kontrol edilmesi ve %100 O2 maskesinin hazır tutulması.', en: 'Check cabin O2 fraction and keep the 100% O2 mask ready.' },
          { tr: 'Uçuş cerrahı ile sesli acil telemetri kanalının (Space-to-Ground 2) açılması.', en: 'Open the emergency voice channel (Space-to-Ground 2) with the flight surgeon.' }
        ],
        countermeasure: { tr: 'Vagal manevra, derin diyafram solunumu ve hidrasyon takviyesi.', en: 'Vagal maneuver, deep diaphragmatic breathing and extra hydration.' },
        notifiedGroundControl: true,
      });
      setVitals((prev) => ({
        ...prev,
        pulse: {
          ...prev.pulse,
          value: 118,
          status: 'critical',
          trend: 'up',
          changeRate: '+24 bpm',
          history: [...prev.pulse.history.slice(1), 118],
        },
      }));
    } else if (metricKey === 'iop') {
      setCurrentAlert({
        id: 'ALT-71-SANS-CRIT',
        severity: 'warning',
        title: { tr: 'SANS - Göz İçi Basınç Eşiği Aşıldı', en: 'SANS - Intraocular Pressure Threshold Exceeded' },
        description: { tr: 'Mikroyerçekimi intrakraniyal basınç artışı kaynaklı optik kılıf dilatasyonu gözlemlendi.', en: 'Optic nerve sheath dilation observed, linked to microgravity-induced intracranial pressure rise.' },
        timestamp: { tr: 'Şimdi', en: 'Now' },
        parameter: { tr: 'Göz İçi Basıncı (22.8 mmHg > 21 mmHg normal)', en: 'Intraocular pressure (22.8 mmHg > 21 mmHg normal)' },
        protocolCode: 'NASA-ESA/ISS-MED-SANS-02',
        steps: [
          { tr: 'Chibis Alt Vücut Negatif Basınç (LBNP) cihazında -30 mmHg seansı başlatılması.', en: 'Start a -30 mmHg session in the Chibis LBNP suit.' },
          { tr: 'Astronotun baş aşağı veya ağırlıklı çalışmalarının durdurulması.', en: 'Stop head-down or heavy-load work.' },
          { tr: 'Görme keskinliği Snellen ve kontrast duyarlılık testinin uygulanması.', en: 'Run the Snellen visual acuity and contrast sensitivity tests.' },
          { tr: 'Göz damlası (Timolol/Brinzolamide) medikal kit rezervinin kontrolü.', en: 'Check the medical kit stock of eye drops (Timolol/Brinzolamide).' }
        ],
        countermeasure: { tr: 'LBNP seansı ve karbonhidrat/sodyum kısıtlaması.', en: 'LBNP session and carbohydrate/sodium restriction.' },
        notifiedGroundControl: true,
      });
      setVitals((prev) => ({
        ...prev,
        iop: {
          ...prev.iop,
          value: 22.8,
          status: 'warning',
          trend: 'up',
          changeRate: '+3.5 mmHg',
          history: [...prev.iop.history.slice(1), 22.8],
        },
      }));
    } else if (metricKey === 'oxygen') {
      setCurrentAlert({
        id: 'ALT-71-HYPOXIA',
        severity: 'critical',
        title: { tr: 'Hafif Hipoksi / SpO2 Desatürasyonu', en: 'Mild Hypoxia / SpO2 Desaturation' },
        description: { tr: 'Astronot periferik oksijen satürasyonu %93.8 seviyesine geriledi.', en: 'Peripheral oxygen saturation dropped to 93.8%.' },
        timestamp: { tr: 'Şimdi', en: 'Now' },
        parameter: { tr: 'SpO2 (%93.8 < %96 normal)', en: 'SpO2 (93.8% < 96% normal)' },
        protocolCode: 'NASA-ESA/ISS-MED-PULM-01',
        steps: [
          { tr: 'Kabin gaz analizörü ile Columbus modülü kısmi pO2 basıncının ölçülmesi.', en: 'Measure partial O2 pressure in the module with the cabin gas analyzer.' },
          { tr: 'Astronota nazal kanül ile 2 L/dk takviye oksijen sağlanması.', en: 'Give 2 L/min supplemental oxygen via nasal cannula.' },
          { tr: 'Solunum sayısı ve ventilasyon döngüsünün izlenmesi.', en: 'Monitor breathing rate and ventilation.' },
          { tr: 'CO2 emici (CDRA) sistem filtelerinin re-generasyon durumunun denetlenmesi.', en: 'Check the regeneration status of the CO2 removal (CDRA) filters.' }
        ],
        countermeasure: { tr: 'Oksijen takviyesi ve kabin havalandırma debisinin artırılması.', en: 'Supplemental oxygen and increased cabin ventilation.' },
        notifiedGroundControl: true,
      });
      setVitals((prev) => ({
        ...prev,
        oxygen: {
          ...prev.oxygen,
          value: 93.8,
          status: 'critical',
          trend: 'down',
          changeRate: '-4.6%',
          history: [...prev.oxygen.history.slice(1), 93.8],
        },
      }));
    }
  };

  // Periodic Telemetry Simulation Hook
  useEffect(() => {
    if (!isSimulating) return;

    const timer = setInterval(() => {
      setVitals((prev) => {
        const next = { ...prev };

        // Pulse (HR)
        let basePulse = 74;
        let pFluct = (Math.random() - 0.49) * 2;
        if (simulationScenario === 'eva_exertion') {
          basePulse = 108;
          pFluct = (Math.random() - 0.45) * 4;
        }
        const newPulse = Math.round(
          Math.min(135, Math.max(55, (next.pulse?.value || 74) * 0.8 + basePulse * 0.2 + pFluct))
        );
        const pStatus: MetricStatus =
          newPulse > 105 ? 'critical' : newPulse > 90 || newPulse < 58 ? 'warning' : 'normal';

        // Glucose (GLU)
        const gFluct = (Math.random() - 0.48) * 1.5;
        const newGlucose = +(
          Math.min(130, Math.max(68, (next.glucose?.value || 94) + gFluct * 0.2))
        ).toFixed(0);
        const gStatus: MetricStatus =
          newGlucose > 120 || newGlucose < 65 ? 'critical' : newGlucose > 110 || newGlucose < 70 ? 'warning' : 'normal';

        // Oxygen (SpO2)
        let baseO2 = 98.4;
        if (simulationScenario === 'hypoxia') {
          baseO2 = 94.2;
        }
        const oFluct = (Math.random() - 0.49) * 0.3;
        const newO2 = +(
          Math.min(100, Math.max(90, (next.oxygen?.value || 98.4) * 0.85 + baseO2 * 0.15 + oFluct))
        ).toFixed(1);
        const oStatus: MetricStatus =
          newO2 < 94 ? 'critical' : newO2 < 96 ? 'warning' : 'normal';

        // Temperature (TEMP)
        const tFluct = (Math.random() - 0.49) * 0.08;
        const newTemp = +(
          Math.min(38.5, Math.max(35.8, (next.temperature?.value || 36.8) * 0.9 + 36.8 * 0.1 + tFluct))
        ).toFixed(1);
        const tStatus: MetricStatus =
          newTemp > 37.8 || newTemp < 35.8 ? 'critical' : newTemp > 37.2 || newTemp < 36.2 ? 'warning' : 'normal';

        // Intraocular Pressure (IOP)
        let baseIOP = 16.0;
        if (simulationScenario === 'warning_iop') {
          baseIOP = 22.4;
        }
        const iFluct = (Math.random() - 0.48) * 0.4;
        const newIOP = +(
          Math.min(26, Math.max(10, (next.iop?.value || 16.0) * 0.88 + baseIOP * 0.12 + iFluct))
        ).toFixed(1);
        const iStatus: MetricStatus =
          newIOP > 22.5 ? 'critical' : newIOP > 20.0 ? 'warning' : 'normal';

        // Sleep (SLP) remains stable or slight adjustment
        const newSleep = next.sleep?.value || 7.6;

        return {
          pulse: {
            ...next.pulse,
            value: newPulse,
            status: pStatus,
            trend: newPulse > (next.pulse?.value || 74) ? 'up' : 'down',
            changeRate: `${newPulse >= (next.pulse?.value || 74) ? '+' : ''}${newPulse - (next.pulse?.value || 74)} bpm`,
            history: [...next.pulse.history.slice(1), newPulse],
          },
          glucose: {
            ...next.glucose,
            value: newGlucose,
            status: gStatus,
            trend: newGlucose > (next.glucose?.value || 94) ? 'up' : 'down',
            changeRate: `${newGlucose >= (next.glucose?.value || 94) ? '+' : ''}${(newGlucose - (next.glucose?.value || 94)).toFixed(0)} mg/dL`,
            history: [...next.glucose.history.slice(1), newGlucose],
          },
          oxygen: {
            ...next.oxygen,
            value: newO2,
            status: oStatus,
            trend: newO2 >= (next.oxygen?.value || 98.4) ? 'up' : 'down',
            changeRate: `${newO2 >= (next.oxygen?.value || 98.4) ? '+' : ''}${(newO2 - (next.oxygen?.value || 98.4)).toFixed(1)}%`,
            history: [...next.oxygen.history.slice(1), newO2],
          },
          temperature: {
            ...next.temperature,
            value: newTemp,
            status: tStatus,
            trend: 'stable',
            changeRate: `${newTemp >= (next.temperature?.value || 36.8) ? '+' : ''}${(newTemp - (next.temperature?.value || 36.8)).toFixed(1)} °C`,
            history: [...next.temperature.history.slice(1), newTemp],
          },
          iop: {
            ...next.iop,
            value: newIOP,
            status: iStatus,
            trend: newIOP >= (next.iop?.value || 16.0) ? 'up' : 'down',
            changeRate: `${newIOP >= (next.iop?.value || 16.0) ? '+' : ''}${(newIOP - (next.iop?.value || 16.0)).toFixed(1)} mmHg`,
            history: [...next.iop.history.slice(1), newIOP],
          },
          sleep: {
            ...next.sleep,
            value: newSleep,
            status: 'normal',
          },
        };
      });

      // Fluctuate telemetry latency slightly
      setSystemTelemetry((prev) => ({
        ...prev,
        satelliteLatencyMs: Math.round(40 + Math.random() * 6),
        signalStrengthPercent: +(98 + Math.random() * 1.5).toFixed(1),
        metTimeHours: +(prev.metTimeHours + 0.001).toFixed(3),
      }));
    }, simulationIntervalMs);

    return () => clearInterval(timer);
  }, [isSimulating, simulationIntervalMs, simulationScenario]);

  return (
    <TelemetryContext.Provider
      value={{
        currentTab,
        setCurrentTab,
        astronaut,
        setAstronautId: setSelectedAstronautId,
        availableAstronauts: ASTRONAUTS,
        vitals,
        simulationScenario,
        setSimulationScenario,
        isSimulating,
        setIsSimulating,
        simulationIntervalMs,
        setSimulationIntervalMs,
        selectedAnatomyZone,
        setSelectedAnatomyZone,
        currentAlert,
        resolveAlert,
        triggerManualAlert,
        recommendations,
        visionTestHistory,
        addVisionTestResult,
        cognitiveTestHistory,
        addCognitiveTestResult,
        systemTelemetery,
        openActionPlanModal,
        setOpenActionPlanModal,
        missionProfile,
        setMissionProfileId,
      }}
    >
      {children}
    </TelemetryContext.Provider>
  );
};

export const useTelemetry = () => {
  const context = useContext(TelemetryContext);
  if (!context) {
    throw new Error('useTelemetry must be used within a TelemetryProvider');
  }
  return context;
};
