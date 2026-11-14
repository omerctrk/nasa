import React, { useId } from 'react';
import {
  Activity,
  Heart,
  Droplet,
  Wind,
  Thermometer,
  Eye,
  Moon,
  Gauge,
  Info,
  FlaskConical,
} from 'lucide-react';
import { useTelemetry } from '../../context/TelemetryContext';
import { usePrefs } from '../../context/PreferencesContext';
import { MetricStatus } from '../../types/telemetry';
import { AnalysisStatus } from './AnalysisStatus';
import { TodayGoals } from './TodayGoals';
import { playUiBeep } from '../../utils/audio';
import { statusMeta, vitalLabel } from '../../utils/status';
import { HAZARDS, METRIC_HAZARD } from '../../data/hazards';

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
        style={{ filter: `drop-shadow(0 0 3px ${color})` }}
      />
      <circle cx={lx} cy={ly} r="2.5" fill={color} vectorEffect="non-scaling-stroke" />
    </svg>
  );
};

// Normal aralıktaki gösterge oranı (ortak "sağlık puanı" değildir; backend böyle bir puan üretmez).
// Neon görünüm: parlayan halka, yavaş dönen yörünge, ışıldayan sayı.
const ScoreRing: React.FC<{ normal: number; total: number; color: string }> = ({ normal, total, color }) => {
  const gid = useId().replace(/:/g, '');
  const ratio = total ? normal / total : 0;
  const size = 148;
  const c = size / 2;
  const radius = 56;
  const stroke = 9;
  const circ = 2 * Math.PI * radius;
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      {/* Arka ışıma */}
      <div
        className="absolute inset-3 rounded-full neon-ring"
        style={{ background: `radial-gradient(circle, ${color}33 0%, transparent 70%)` }}
        aria-hidden
      />
      <svg width={size} height={size} className="relative" aria-hidden>
        <defs>
          <linearGradient id={`${gid}-g`} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.55" />
            <stop offset="100%" stopColor={color} />
          </linearGradient>
          <filter id={`${gid}-glow`} x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="3.5" result="b" />
            <feMerge>
              <feMergeNode in="b" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>
        {/* Yavaş dönen yörünge */}
        <g className="orbit-spin">
          <circle cx={c} cy={c} r={radius + 13} fill="none" stroke={color} strokeOpacity="0.35" strokeWidth="1" strokeDasharray="2 7" />
          <circle cx={c} cy={c - radius - 13} r="2.5" fill={color} filter={`url(#${gid}-glow)`} />
        </g>
        {/* İz */}
        <circle cx={c} cy={c} r={radius} stroke={color} strokeOpacity="0.14" strokeWidth={stroke} fill="none" />
        {/* İlerleme */}
        <g transform={`rotate(-90 ${c} ${c})`} className="neon-ring">
          <circle
            cx={c}
            cy={c}
            r={radius}
            stroke={`url(#${gid}-g)`}
            strokeWidth={stroke}
            strokeDasharray={circ}
            strokeDashoffset={circ - ratio * circ}
            strokeLinecap="round"
            fill="none"
            filter={`url(#${gid}-glow)`}
            className="transition-all duration-700 ease-out"
          />
        </g>
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-4xl font-black tracking-tight leading-none font-mono neon-text" style={{ color }}>
          {normal}
        </span>
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
  const { vitals, setSelectedAnatomyZone, triggerManualAlert, currentAlert } = useTelemetry();
  const { t, pick } = usePrefs();

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
  ];

  return (
    <div className="flex flex-col gap-5">
      {/* Üst: sağlık özeti (tam genişlik, yatay) */}
      <section className="bg-white rounded-2xl border border-slate-200 p-5">
          <div className="flex items-center justify-between">
            <h2 className="flex items-center gap-1.5 text-base font-bold text-slate-900">
              {t('Sağlık Özeti', 'Health Summary')}
              <span
                title={t(
                  'Halka, normal aralıktaki gösterge sayısını; durum metni en yüksek uyarı seviyesini gösterir.',
                  'The ring shows how many indicators are in range; the status reflects the highest alert level.'
                )}
              >
                <Info className="w-3.5 h-3.5 text-slate-400" />
              </span>
            </h2>
            <span className="flex items-center gap-1.5 text-xs font-semibold text-emerald-700">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              {t('Canlı', 'Live')}
            </span>
          </div>

          <div className="mt-3 flex flex-col md:flex-row md:items-center gap-5">
            <div className="flex items-center gap-5 shrink-0">
            <ScoreRing normal={counts.normal} total={all.length} color={verdict.color} />
            <div className="min-w-0">
              <div className={`text-lg font-bold leading-snug ${verdict.cls}`}>{verdict.text}</div>
              <ul className="mt-2 space-y-1 text-sm text-slate-600">
                <li className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-emerald-500" />
                  <span className="font-mono font-bold text-slate-800">{counts.normal}</span> {t('normal', 'normal')}
                </li>
                <li className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-amber-500" />
                  <span className="font-mono font-bold text-slate-800">{counts.warning}</span> {t('dikkat', 'caution')}
                </li>
                <li className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-red-500" />
                  <span className="font-mono font-bold text-slate-800">{counts.critical}</span> {t('kritik', 'critical')}
                </li>
              </ul>
            </div>
            </div>

            {/* Anomali analizi: geniş ekranda sağda */}
            <div className="flex-1 min-w-0 md:pl-6 md:border-l md:border-slate-200/70 md:[&>div]:mt-0 md:[&>div]:pt-0 md:[&>div]:border-t-0">
              <AnalysisStatus />
            </div>
          </div>
        </section>

      {/* Yaşamsal bulgular: sade kartlar */}
      <section aria-labelledby="vitals-heading">
        <h2 id="vitals-heading" className="text-sm font-bold text-slate-800 mb-2.5 px-1">
          {t('Yaşamsal Bulgular', 'Vital Signs')}
        </h2>

        <div className="grid grid-cols-2 xl:grid-cols-3 gap-3">
          {cards.map((c) => {
            const meta = statusMeta(c.status, t);
            const hazard = METRIC_HAZARD[c.id];
            return (
              <button
                type="button"
                key={c.id}
                onClick={() => handleCardClick(c.id)}
                title={hazard ? `${t('İlişkili tehlike', 'Related hazard')}: ${pick(HAZARDS[hazard].name)}` : undefined}
                className={`text-left rounded-xl border p-3.5 transition-all hover:-translate-y-0.5 ${meta.card}`}
              >
                <div className="flex items-center justify-between gap-1">
                  <span className="flex items-center gap-1.5 min-w-0">
                    {METRIC_ICONS[c.id] ?? <Activity className="w-4 h-4 text-slate-500" />}
                    <span className="text-xs font-semibold text-slate-600 truncate">{vitalLabel(c.id, t)}</span>
                  </span>
                  <span className={`w-2 h-2 rounded-full shrink-0 ${meta.dot}`} title={meta.label} />
                </div>

                <div className="mt-2 flex items-baseline gap-1 whitespace-nowrap">
                  <span className={`text-2xl font-bold font-mono tracking-tight ${meta.text}`}>{c.value}</span>
                  <span className="text-xs text-slate-500">{c.unit}</span>
                </div>

                <div className="mt-1 h-8">
                  {c.history ? (
                    <Sparkline data={c.history} color={meta.hex === '#10B981' ? '#0EA5E9' : meta.hex} />
                  ) : (
                    <div className="h-full flex items-center text-xs text-slate-400">{t('Manuel ölçüm', 'Manual reading')}</div>
                  )}
                </div>

                <div className="mt-1 flex items-center justify-between gap-1 text-[11px]">
                  <span className="text-slate-400 font-mono truncate">{ranges[c.id]}</span>
                  {c.status !== 'normal' && (
                    <span className={`px-1.5 py-0.5 rounded-md border font-semibold shrink-0 ${meta.badge}`}>{meta.label}</span>
                  )}
                </div>
              </button>
            );
          })}
        </div>
      </section>

      {/* Bugünkü hedefler: yatay */}
      <TodayGoals horizontal />

      {/* Demo: sunumda uyarı akışını göstermek için (sade) */}
      <div className="flex flex-wrap items-center gap-2 px-1 text-xs text-slate-400">
        <FlaskConical className="w-3.5 h-3.5" />
        <span>{t('Demo uyarısı:', 'Demo alert:')}</span>
        {[
          { k: 'iop', l: t('Göz basıncı', 'Eye pressure') },
          { k: 'pulse', l: t('Nabız', 'Heart rate') },
          { k: 'oxygen', l: t('Oksijen', 'Oxygen') },
        ].map((d) => (
          <button
            key={d.k}
            onClick={() => triggerManualAlert(d.k)}
            className="px-2 py-0.5 rounded-md border border-slate-200 text-slate-500 hover:text-slate-800 hover:border-slate-400 transition-colors"
          >
            {d.l}
          </button>
        ))}
      </div>
    </div>
  );
};
