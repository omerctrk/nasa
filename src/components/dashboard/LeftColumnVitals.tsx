import React, { useId } from 'react';
import {
  Activity,
  Heart,
  Droplet,
  Wind,
  Thermometer,
  Eye,
  Moon,
  Radio,
  Wifi,
  Cpu,
  Gauge,
  Info,
  FlaskConical,
} from 'lucide-react';
import { useTelemetry } from '../../context/TelemetryContext';
import { usePrefs } from '../../context/PreferencesContext';
import { MetricStatus } from '../../types/telemetry';
import { AnalysisStatus } from './AnalysisStatus';
import { playUiBeep } from '../../utils/audio';
import { statusMeta, vitalLabel, unitLabel } from '../../utils/status';
import { HAZARDS, METRIC_HAZARD } from '../../data/hazards';
import { CAREER_LIMIT_MSV, cumulativeDose, formatDelay } from '../../data/missionProfiles';

// Mini trend grafiği
const Sparkline: React.FC<{ data: number[]; color: string }> = ({ data, color }) => {
  const gid = useId().replace(/:/g, '');
  if (!data || data.length < 2) return null;

  const width = 120;
  const height = 30;
  const pad = 3;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;

  const pts = data.map((d, i) => [
    pad + (i / (data.length - 1)) * (width - 2 * pad),
    height - pad - ((d - min) / range) * (height - 2 * pad),
  ]);
  const line = pts.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' ');
  const [lx, ly] = pts[pts.length - 1];

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-8" preserveAspectRatio="none" aria-hidden>
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.25" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon points={`${line} ${width - pad},${height} ${pad},${height}`} fill={`url(#${gid})`} />
      <polyline
        fill="none"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        vectorEffect="non-scaling-stroke"
        points={line}
      />
      <circle cx={lx} cy={ly} r="2.5" fill={color} vectorEffect="non-scaling-stroke" />
    </svg>
  );
};

// Normal aralıktaki gösterge oranı (ortak "sağlık puanı" değildir; backend böyle bir puan üretmez)
const ScoreRing: React.FC<{ normal: number; total: number; color: string }> = ({ normal, total, color }) => {
  const ratio = total ? normal / total : 0;
  const radius = 52;
  const stroke = 10;
  const circ = 2 * Math.PI * radius;
  return (
    <div className="relative w-[132px] h-[132px] shrink-0">
      <svg width="132" height="132" className="-rotate-90" aria-hidden>
        <circle cx="66" cy="66" r={radius} stroke="rgb(var(--c-bg-slate-100))" strokeWidth={stroke} fill="none" />
        <circle
          cx="66"
          cy="66"
          r={radius}
          stroke={color}
          strokeWidth={stroke}
          strokeDasharray={circ}
          strokeDashoffset={circ - ratio * circ}
          strokeLinecap="round"
          fill="none"
          className="transition-all duration-700 ease-out"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-4xl font-black tracking-tight text-slate-900 leading-none font-mono">{normal}</span>
        <span className="text-xs font-semibold text-slate-500 mt-1">/ {total}</span>
      </div>
    </div>
  );
};

const METRIC_ICONS: Record<string, React.ReactNode> = {
  pulse: <Heart className="w-4 h-4 text-rose-500" />,
  bp: <Gauge className="w-4 h-4 text-blue-500" />,
  glucose: <Droplet className="w-4 h-4 text-sky-500" />,
  oxygen: <Wind className="w-4 h-4 text-cyan-500" />,
  temperature: <Thermometer className="w-4 h-4 text-amber-500" />,
  iop: <Eye className="w-4 h-4 text-indigo-500" />,
  sleep: <Moon className="w-4 h-4 text-purple-500" />,
};

export const LeftColumnVitals: React.FC = () => {
  const { vitals, systemTelemetery, setSelectedAnatomyZone, triggerManualAlert, currentAlert, missionProfile, astronaut } = useTelemetry();
  const { t, pick, lang } = usePrefs();

  const all = Object.values(vitals);
  const counts = {
    normal: all.filter((m) => m.status === 'normal').length,
    warning: all.filter((m) => m.status === 'warning').length,
    critical: all.filter((m) => m.status === 'critical').length,
  };

  // Genel durum: göstergelerin ve açık uyarının EN KÖTÜ seviyesi (sayısal puan yok).
  // Backend'de seviyeler: anomali watch/review → WARNING, SANS red → CRITICAL.
  const worst =
    counts.critical > 0 || currentAlert?.severity === 'critical'
      ? 'critical'
      : counts.warning > 0 || currentAlert?.severity === 'warning'
        ? 'warning'
        : 'normal';
  const verdict =
    worst === 'normal'
      ? { text: t('Görev için uygun', 'Fit for duty'), color: '#10B981', cls: 'text-emerald-700' }
      : worst === 'warning'
        ? { text: t('Yakından izleniyor', 'Under close watch'), color: '#F59E0B', cls: 'text-amber-700' }
        : { text: t('Müdahale gerekli', 'Action required'), color: '#EF4444', cls: 'text-red-700' };

  const zoneFor = (id: string) =>
    id === 'pulse' || id === 'oxygen' || id === 'bp'
      ? 'chest'
      : id === 'glucose' || id === 'temperature'
        ? 'abdomen'
        : 'head';

  const handleCardClick = (metricId: string) => {
    playUiBeep(750);
    setSelectedAnatomyZone(zoneFor(metricId));
  };

  const ranges: Record<string, string> = {
    pulse: '60–90 bpm',
    bp: '90–120 / 60–80',
    glucose: '70–110 mg/dL',
    oxygen: '96–100 %',
    temperature: '36.3–37.2 °C',
    iop: '10–21 mmHg',
    sleep: t('7–8.5 saat', '7–8.5 h'),
  };

  // Tansiyon şimdilik sabit (backend bağlanınca gerçek veri gelecek)
  const cards: {
    id: string;
    value: string | number;
    unit: string;
    status: MetricStatus;
    history?: number[];
  }[] = [
    { id: 'pulse', value: vitals.pulse.value, unit: vitals.pulse.unit, status: vitals.pulse.status, history: vitals.pulse.history },
    { id: 'bp', value: '118/76', unit: 'mmHg', status: 'normal' },
    { id: 'oxygen', value: vitals.oxygen.value, unit: vitals.oxygen.unit, status: vitals.oxygen.status, history: vitals.oxygen.history },
    { id: 'glucose', value: vitals.glucose.value, unit: vitals.glucose.unit, status: vitals.glucose.status, history: vitals.glucose.history },
    { id: 'temperature', value: vitals.temperature.value, unit: vitals.temperature.unit, status: vitals.temperature.status, history: vitals.temperature.history },
    { id: 'iop', value: vitals.iop.value, unit: vitals.iop.unit, status: vitals.iop.status, history: vitals.iop.history },
    { id: 'sleep', value: vitals.sleep.value, unit: unitLabel(vitals.sleep.unit, t), status: vitals.sleep.status, history: vitals.sleep.history },
  ];

  return (
    <div className="flex flex-col gap-4">
      {/* 1. Genel sağlık özeti */}
      <section className="bg-white rounded-2xl border border-slate-200 p-5 shadow-card">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-bold text-slate-900">{t('Sağlık Özeti', 'Health Summary')}</h2>
          <span className="flex items-center gap-1.5 text-xs font-semibold text-emerald-700">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            {t('Canlı', 'Live')}
          </span>
        </div>

        <div className="mt-4 flex items-center gap-4">
          <ScoreRing normal={counts.normal} total={all.length} color={verdict.color} />
          <div className="min-w-0">
            <div className={`text-lg font-bold leading-snug ${verdict.cls}`}>{verdict.text}</div>
            <ul className="mt-2 space-y-1 text-sm">
              <li className="flex items-center gap-2 text-slate-700">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
                <span className="font-mono font-bold">{counts.normal}</span> {t('normal', 'normal')}
              </li>
              <li className="flex items-center gap-2 text-slate-700">
                <span className="w-2.5 h-2.5 rounded-full bg-amber-500" />
                <span className="font-mono font-bold">{counts.warning}</span> {t('dikkat', 'caution')}
              </li>
              <li className="flex items-center gap-2 text-slate-700">
                <span className="w-2.5 h-2.5 rounded-full bg-red-500" />
                <span className="font-mono font-bold">{counts.critical}</span> {t('kritik', 'critical')}
              </li>
            </ul>
          </div>
        </div>

        <AnalysisStatus />

        <p className="mt-3 flex items-start gap-2 text-xs text-slate-500 leading-relaxed">
          <Info className="w-3.5 h-3.5 mt-0.5 shrink-0" />
          {t(
            'Halka, normal aralıktaki gösterge sayısını; durum metni en yüksek uyarı seviyesini gösterir. Bir karta tıklayarak ilgili vücut bölgesini açabilirsiniz.',
            'The ring shows how many indicators are in their normal range; the status reflects the highest alert level. Click a card to open the related body area.'
          )}
        </p>
      </section>

      {/* 2. Yaşamsal bulgular */}
      <section aria-labelledby="vitals-heading">
        <div className="flex items-center justify-between mb-2 px-1">
          <h2 id="vitals-heading" className="text-sm font-bold text-slate-800">
            {t('Yaşamsal Bulgular', 'Vital Signs')}
          </h2>
          <span className="text-xs text-slate-500">{t('Normal aralık altta', 'Normal range below')}</span>
        </div>

        <div className="grid grid-cols-2 gap-2.5">
          {cards.map((c, idx) => {
            const meta = statusMeta(c.status, t);
            const isLast = idx === cards.length - 1 && cards.length % 2 === 1;
            return (
              <button
                type="button"
                key={c.id}
                onClick={() => handleCardClick(c.id)}
                className={`text-left rounded-xl border p-3 transition-all shadow-sm hover:shadow-md ${meta.card} ${
                  isLast ? 'col-span-2' : ''
                }`}
              >
                <div className="flex items-center justify-between gap-1">
                  <span className="flex items-center gap-1.5 min-w-0">
                    {METRIC_ICONS[c.id] ?? <Activity className="w-4 h-4 text-slate-500" />}
                    <span className="text-xs font-semibold text-slate-700 truncate">{vitalLabel(c.id, t)}</span>
                  </span>
                  {METRIC_HAZARD[c.id] && (
                    <span
                      className="px-1.5 py-0.5 rounded bg-slate-100 text-[10px] font-semibold text-slate-500 shrink-0 whitespace-nowrap"
                      title={`${t('İlişkili tehlike', 'Related hazard')}: ${pick(HAZARDS[METRIC_HAZARD[c.id]].name)}`}
                    >
                      {pick(HAZARDS[METRIC_HAZARD[c.id]].short)}
                    </span>
                  )}
                </div>

                <div className="mt-1.5 flex items-baseline gap-1 whitespace-nowrap">
                  <span className={`text-xl font-bold font-mono tracking-tight ${meta.text}`}>{c.value}</span>
                  <span className="text-xs text-slate-500">{c.unit}</span>
                </div>

                <div className="mt-1 h-8">
                  {c.history ? (
                    <Sparkline data={c.history} color={meta.hex === '#10B981' ? '#0EA5E9' : meta.hex} />
                  ) : (
                    <div className="h-full flex items-center text-xs text-slate-400 italic">
                      {t('Manuel ölçüm', 'Manual reading')}
                    </div>
                  )}
                </div>

                <div className="mt-1 flex items-center justify-between gap-1 text-xs">
                  <span className="text-slate-500 font-mono truncate">{ranges[c.id]}</span>
                  <span className={`px-1.5 py-0.5 rounded-md border font-semibold shrink-0 ${meta.badge}`}>
                    {meta.label}
                  </span>
                </div>
              </button>
            );
          })}
        </div>
      </section>

      {/* 3. Kabin ve bağlantı durumu */}
      <section className="bg-white rounded-2xl border border-slate-200 p-4 shadow-sm">
        <div className="flex items-center gap-2 mb-3">
          <Radio className="w-4 h-4 text-blue-600" />
          <h2 className="text-sm font-bold text-slate-800">{t('Kabin & Bağlantı', 'Cabin & Link')}</h2>
        </div>

        <dl className="grid grid-cols-2 gap-2 text-sm">
          <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-100">
            <dt className="text-xs text-slate-500">{t('Dünya gecikmesi', 'Earth delay')}</dt>
            <dd className="flex items-center gap-1 text-slate-800 font-bold font-mono mt-0.5">
              <Wifi className="w-3.5 h-3.5 text-slate-400" />
              {formatDelay(missionProfile.oneWayDelaySec, lang)}
            </dd>
          </div>
          <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-100">
            <dt className="text-xs text-slate-500">{t('Sensörler', 'Sensors')}</dt>
            <dd className="flex items-center gap-1 text-slate-800 font-bold font-mono mt-0.5">
              <Cpu className="w-3.5 h-3.5 text-blue-500" />
              {systemTelemetery.activeSensors}/{systemTelemetery.totalSensors}
            </dd>
          </div>
          <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-100">
            <dt className="text-xs text-slate-500">{t('Kabin O₂ / CO₂', 'Cabin O₂ / CO₂')}</dt>
            <dd className="text-slate-800 font-bold font-mono mt-0.5">
              {systemTelemetery.cabinO2Percent}% / {systemTelemetery.co2Percent}%
            </dd>
          </div>
          <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-100">
            <dt className="text-xs text-slate-500">{t('Radyasyon (toplam)', 'Radiation (total)')}</dt>
            <dd className="text-slate-800 font-bold font-mono mt-0.5">
              {cumulativeDose(missionProfile, astronaut.solDay)} / {CAREER_LIMIT_MSV} mSv
            </dd>
          </div>
        </dl>

        {/* Demo senaryoları: jüri sunumunda uyarı akışını göstermek için */}
        <div className="mt-3 pt-3 border-t border-slate-100">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-500 mb-2">
            <FlaskConical className="w-3.5 h-3.5" />
            {t('Demo: uyarı tetikle', 'Demo: trigger an alert')}
          </div>
          <div className="flex flex-wrap gap-1.5">
            <button
              onClick={() => triggerManualAlert('iop')}
              className="px-2.5 py-1 bg-amber-50 hover:bg-amber-100 text-amber-800 border border-amber-200 font-semibold rounded-lg text-xs transition-colors"
            >
              {t('Göz basıncı', 'Eye pressure')}
            </button>
            <button
              onClick={() => triggerManualAlert('pulse')}
              className="px-2.5 py-1 bg-red-50 hover:bg-red-100 text-red-800 border border-red-200 font-semibold rounded-lg text-xs transition-colors"
            >
              {t('Nabız', 'Heart rate')}
            </button>
            <button
              onClick={() => triggerManualAlert('oxygen')}
              className="px-2.5 py-1 bg-red-50 hover:bg-red-100 text-red-800 border border-red-200 font-semibold rounded-lg text-xs transition-colors"
            >
              {t('Oksijen', 'Oxygen')}
            </button>
          </div>
        </div>
      </section>
    </div>
  );
};
