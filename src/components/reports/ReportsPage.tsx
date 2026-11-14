import React, { useState } from 'react';
import { Download, Heart, Wind, Thermometer, Moon, Eye, Brain, Printer } from 'lucide-react';
import { useTelemetry } from '../../context/TelemetryContext';
import { usePrefs } from '../../context/PreferencesContext';
import { playUiBeep } from '../../utils/audio';

type TimeRange = '24h' | '7d' | '30d';

interface ChartProps {
  labels: string[];
  data: number[];
  color: string;
  minY: number;
  maxY: number;
  normalMin: number;
  normalMax: number;
  ariaLabel: string;
}

/** Normal aralığı yeşil bant olarak gösteren çizgi grafik */
const LineChart: React.FC<ChartProps> = ({ labels, data, color, minY, maxY, normalMin, normalMax, ariaLabel }) => {
  const width = 560;
  const height = 180;
  const padL = 40;
  const padR = 16;
  const padT = 22;
  const padB = 28;
  const rangeY = maxY - minY || 1;

  const yOf = (v: number) => height - padB - ((Math.min(maxY, Math.max(minY, v)) - minY) / rangeY) * (height - padT - padB);
  const pts = data.map((v, i) => ({
    x: padL + (i / (data.length - 1 || 1)) * (width - padL - padR),
    y: yOf(v),
    v,
    out: v < normalMin || v > normalMax,
  }));
  const path = pts.map((p, i) => `${i ? 'L' : 'M'} ${p.x} ${p.y}`).join(' ');
  const bandTop = yOf(normalMax);
  const bandBottom = yOf(normalMin);

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto" role="img" aria-label={ariaLabel}>
      {/* Normal aralık bandı */}
      <rect x={padL} y={bandTop} width={width - padL - padR} height={Math.max(0, bandBottom - bandTop)} fill="#10B981" opacity="0.1" />
      <line x1={padL} x2={width - padR} y1={bandTop} y2={bandTop} stroke="#10B981" strokeOpacity="0.5" strokeDasharray="4 4" />
      <line x1={padL} x2={width - padR} y1={bandBottom} y2={bandBottom} stroke="#10B981" strokeOpacity="0.5" strokeDasharray="4 4" />
      <text x={padL - 6} y={bandTop + 4} textAnchor="end" fontSize="11" className="fill-slate-500 font-mono">
        {normalMax}
      </text>
      <text x={padL - 6} y={bandBottom + 4} textAnchor="end" fontSize="11" className="fill-slate-500 font-mono">
        {normalMin}
      </text>

      <path d={path} fill="none" stroke={color} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />

      {pts.map((p, i) => (
        <g key={i}>
          <circle cx={p.x} cy={p.y} r={p.out ? 5 : 4} fill={p.out ? '#F59E0B' : color} stroke="rgb(var(--c-surface))" strokeWidth="2" />
          <text x={p.x} y={p.y - 9} textAnchor="middle" fontSize="11" fontWeight="700" className="fill-slate-700 font-mono">
            {p.v}
          </text>
          <text x={p.x} y={height - 8} textAnchor="middle" fontSize="11" className="fill-slate-500">
            {labels[i]}
          </text>
        </g>
      ))}
    </svg>
  );
};

export const ReportsPage: React.FC = () => {
  const { astronaut, vitals, visionTestHistory, cognitiveTestHistory } = useTelemetry();
  const { t, pick } = usePrefs();
  const [timeRange, setTimeRange] = useState<TimeRange>('7d');

  // Örnek geçmiş veriler (backend bağlandığında API'den gelecek)
  const datasets = {
    '24h': {
      labels: ['00', '03', '06', '09', '12', '15', '18', '21'].map((h) => `${h}:00`),
      pulse: [64, 62, 60, 78, 86, 75, 72, 68],
      oxygen: [98.8, 98.6, 98.4, 98.1, 98.5, 98.7, 98.3, 98.5],
      temperature: [36.5, 36.4, 36.3, 36.7, 36.9, 36.8, 36.8, 36.7],
      sleep: [7.2, 7.5, 6.8, 7.8, 7.4, 7.1, 7.6, vitals.sleep.value],
    },
    '7d': {
      labels: [6, 5, 4, 3, 2, 1, 0].map((k) => (k ? `${t('Gün', 'Day')} ${astronaut.solDay - k}` : t('Bugün', 'Today'))),
      pulse: [71, 74, 68, 76, 73, 70, vitals.pulse.value],
      oxygen: [98.2, 98.5, 98.8, 98.1, 98.6, 98.4, vitals.oxygen.value],
      temperature: [36.7, 36.8, 36.7, 36.9, 36.8, 36.8, vitals.temperature.value],
      sleep: [7.2, 7.5, 6.8, 7.8, 7.4, 7.1, vitals.sleep.value],
    },
    '30d': {
      labels: [1, 2, 3, 4].map((w) => `${t('Hafta', 'Week')} ${w}`),
      pulse: [72, 73, 71, 74],
      oxygen: [98.3, 98.4, 98.6, vitals.oxygen.value],
      temperature: [36.7, 36.8, 36.8, vitals.temperature.value],
      sleep: [7.3, 7.4, 7.5, vitals.sleep.value],
    },
  };
  const ds = datasets[timeRange];
  const avg = (a: number[]) => +(a.reduce((s, v) => s + v, 0) / a.length).toFixed(1);

  const charts = [
    { key: 'pulse', icon: <Heart className="w-4 h-4 text-rose-500" />, title: t('Nabız', 'Heart rate'), unit: 'bpm', color: '#E11D48', minY: 50, maxY: 100, nMin: 60, nMax: 90, live: `${vitals.pulse.value} bpm` },
    { key: 'oxygen', icon: <Wind className="w-4 h-4 text-cyan-500" />, title: t('Oksijen (SpO₂)', 'Oxygen (SpO₂)'), unit: '%', color: '#0284C7', minY: 93, maxY: 100, nMin: 96, nMax: 100, live: `${vitals.oxygen.value}%` },
    { key: 'temperature', icon: <Thermometer className="w-4 h-4 text-amber-500" />, title: t('Vücut ısısı', 'Body temperature'), unit: '°C', color: '#D97706', minY: 36, maxY: 37.6, nMin: 36.3, nMax: 37.2, live: `${vitals.temperature.value} °C` },
    { key: 'sleep', icon: <Moon className="w-4 h-4 text-purple-500" />, title: t('Uyku süresi', 'Sleep duration'), unit: t('saat', 'h'), color: '#7C3AED', minY: 6, maxY: 9, nMin: 7, nMax: 8.5, live: `${vitals.sleep.value} ${t('sa', 'h')}` },
  ] as const;

  const riskLabel = (r: string) => (r === 'high' ? t('Yüksek', 'High') : r === 'medium' ? t('Orta', 'Medium') : t('Düşük', 'Low'));
  const riskCls = (r: string) =>
    r === 'high'
      ? 'bg-red-100 text-red-800 border-red-200'
      : r === 'medium'
        ? 'bg-amber-100 text-amber-800 border-amber-200'
        : 'bg-emerald-100 text-emerald-800 border-emerald-200';

  const exportCsv = () => {
    playUiBeep(880);
    const rows = [
      ['label', 'heart_rate_bpm', 'spo2_percent', 'body_temp_c', 'sleep_h'],
      ...ds.labels.map((l, i) => [l, ds.pulse[i], ds.oxygen[i], ds.temperature[i], ds.sleep[i] ?? '']),
    ];
    const csv = rows.map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(',')).join('\n');
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
    const a = document.createElement('a');
    a.href = url;
    a.download = `ahms-${astronaut.id}-${timeRange}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const ranges: { id: TimeRange; label: string }[] = [
    { id: '24h', label: t('24 saat', '24 hours') },
    { id: '7d', label: t('7 gün', '7 days') },
    { id: '30d', label: t('30 gün', '30 days') },
  ];

  return (
    <div className="w-full max-w-6xl mx-auto space-y-6 pb-12 animate-fadeIn">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{t('Sağlık Raporu', 'Health Report')}</h1>
          <p className="text-sm text-slate-500 mt-1">
            {astronaut.name} • {pick(astronaut.role)}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2 print:hidden">
          <div role="tablist" className="flex items-center bg-white p-1 rounded-xl border border-slate-200 shadow-sm">
            {ranges.map((r) => (
              <button
                key={r.id}
                role="tab"
                aria-selected={timeRange === r.id}
                onClick={() => {
                  playUiBeep(700);
                  setTimeRange(r.id);
                }}
                className={`px-3 py-1.5 rounded-lg text-sm font-semibold transition-all ${
                  timeRange === r.id ? 'bg-blue-600 text-white shadow-sm' : 'text-slate-600 hover:bg-slate-100'
                }`}
              >
                {r.label}
              </button>
            ))}
          </div>
          <button
            onClick={() => window.print()}
            className="flex items-center gap-1.5 px-3 py-2 bg-white hover:bg-slate-50 text-slate-700 rounded-xl border border-slate-200 text-sm font-semibold shadow-sm transition-colors"
          >
            <Printer className="w-4 h-4 text-blue-600" />
            {t('Yazdır / PDF', 'Print / PDF')}
          </button>
          <button
            onClick={exportCsv}
            className="flex items-center gap-1.5 px-3 py-2 bg-white hover:bg-slate-50 text-slate-700 rounded-xl border border-slate-200 text-sm font-semibold shadow-sm transition-colors"
          >
            <Download className="w-4 h-4 text-blue-600" />
            CSV
          </button>
        </div>
      </div>

      {/* Ortalamalar */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {charts.map((c) => {
          const a = avg(ds[c.key] as number[]);
          const ok = a >= c.nMin && a <= c.nMax;
          return (
            <div key={c.key} className="p-4 bg-white rounded-2xl border border-slate-200 shadow-sm">
              <div className="flex items-center justify-between text-sm text-slate-500">
                <span>
                  {c.title} <span className="text-slate-400">· {t('ort.', 'avg.')}</span>
                </span>
                {c.icon}
              </div>
              <div className="text-2xl font-bold font-mono text-slate-900 mt-1">
                {a} <span className="text-sm font-medium text-slate-500">{c.unit}</span>
              </div>
              <div className={`text-xs font-semibold mt-1 ${ok ? 'text-emerald-700' : 'text-amber-700'}`}>
                {ok ? t('Normal aralıkta', 'Within normal range') : t('Normal aralık dışında', 'Outside normal range')}
              </div>
            </div>
          );
        })}
      </div>

      {/* Grafikler */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {charts.map((c) => (
          <section key={c.key} className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm break-inside-avoid">
            <div className="flex items-start justify-between gap-2 mb-2">
              <div className="flex items-center gap-2">
                <div className="p-1.5 rounded-lg bg-slate-50 border border-slate-200">{c.icon}</div>
                <div>
                  <h2 className="text-base font-bold text-slate-900">{c.title}</h2>
                  <p className="text-xs text-slate-500">
                    {t('Normal', 'Normal')}: {c.nMin}–{c.nMax} {c.unit}
                  </p>
                </div>
              </div>
              <span className="text-xs font-mono font-semibold text-slate-600 bg-slate-100 px-2 py-1 rounded-md border border-slate-200 whitespace-nowrap">
                {t('Şimdi', 'Now')}: {c.live}
              </span>
            </div>
            <LineChart
              labels={ds.labels}
              data={ds[c.key] as number[]}
              color={c.color}
              minY={c.minY}
              maxY={c.maxY}
              normalMin={c.nMin}
              normalMax={c.nMax}
              ariaLabel={`${c.title} – ${ranges.find((r) => r.id === timeRange)?.label}`}
            />
          </section>
        ))}
      </div>

      <p className="flex items-center gap-3 text-xs text-slate-500">
        <span className="inline-flex items-center gap-1.5">
          <span className="w-4 h-2.5 rounded-sm bg-emerald-500/20 border border-emerald-500/50" />
          {t('Normal aralık', 'Normal range')}
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-amber-500" />
          {t('Aralık dışı ölçüm', 'Out-of-range reading')}
        </span>
      </p>

      {/* Test geçmişi */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <section className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <h2 className="flex items-center gap-2 text-base font-bold text-slate-900">
              <Eye className="w-4 h-4 text-blue-600" />
              {t('Görme testleri', 'Vision tests')}
            </h2>
            <span className="text-xs text-slate-500">
              {visionTestHistory.length} {t('kayıt', 'records')}
            </span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead className="text-xs text-slate-500 border-b border-slate-200">
                <tr>
                  <th className="py-2 pr-3 font-semibold">{t('Tarih', 'Date')}</th>
                  <th className="py-2 pr-3 font-semibold">{t('Skor', 'Score')}</th>
                  <th className="py-2 pr-3 font-semibold">{t('Göz basıncı', 'Eye pressure')}</th>
                  <th className="py-2 pr-3 font-semibold">{t('SANS riski', 'SANS risk')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {visionTestHistory.map((item, idx) => (
                  <tr key={idx}>
                    <td className="py-2.5 pr-3 text-slate-800">{pick(item.date)}</td>
                    <td className="py-2.5 pr-3 font-mono font-bold text-blue-700">{item.acuityScore}</td>
                    <td className="py-2.5 pr-3 font-mono text-slate-700">{item.eyePressureMmHg} mmHg</td>
                    <td className="py-2.5 pr-3">
                      <span className={`px-2 py-0.5 rounded-md text-xs font-semibold border ${riskCls(item.sansRisk)}`}>
                        {riskLabel(item.sansRisk)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <h2 className="flex items-center gap-2 text-base font-bold text-slate-900">
              <Brain className="w-4 h-4 text-indigo-600" />
              {t('Refleks & bilişsel testler', 'Reflex & cognitive tests')}
            </h2>
            <span className="text-xs text-slate-500">
              {cognitiveTestHistory.length} {t('kayıt', 'records')}
            </span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead className="text-xs text-slate-500 border-b border-slate-200">
                <tr>
                  <th className="py-2 pr-3 font-semibold">{t('Tarih', 'Date')}</th>
                  <th className="py-2 pr-3 font-semibold">{t('Tepki', 'Reaction')}</th>
                  <th className="py-2 pr-3 font-semibold">{t('Doğruluk', 'Accuracy')}</th>
                  <th className="py-2 pr-3 font-semibold">{t('Durum', 'Status')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {cognitiveTestHistory.map((item, idx) => (
                  <tr key={idx}>
                    <td className="py-2.5 pr-3 text-slate-800">{pick(item.date)}</td>
                    <td className="py-2.5 pr-3 font-mono font-bold text-indigo-700">{item.reactionTimeMs} ms</td>
                    <td className="py-2.5 pr-3 font-mono text-slate-700">{item.accuracyPercent}%</td>
                    <td className="py-2.5 pr-3">
                      <span className="px-2 py-0.5 rounded-md text-xs font-semibold border bg-emerald-100 text-emerald-800 border-emerald-200">
                        {pick(item.readinessLevel)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>
  );
};
