import React from 'react';
import { Download, Heart, Moon, Thermometer, Wind } from 'lucide-react';
import { useTelemetry } from '../../context/TelemetryContext';
import { usePrefs } from '../../context/PreferencesContext';

const icons: Record<string, React.ReactNode> = {
  pulse: <Heart className="h-4 w-4 text-rose-500" />, oxygen: <Wind className="h-4 w-4 text-cyan-500" />,
  temperature: <Thermometer className="h-4 w-4 text-amber-500" />, sleep: <Moon className="h-4 w-4 text-purple-500" />,
};

const Graph: React.FC<{ values: number[] }> = ({ values }) => {
  if (!values.length) return <div className="grid h-36 place-items-center text-sm text-slate-500">Grafik oluşturacak kayıt yok.</div>;
  const low = Math.min(...values), high = Math.max(...values), span = Math.max(1, high - low);
  const points = values.map((value, index) => `${18 + index * 364 / Math.max(1, values.length - 1)},${120 - (value - low) / span * 88}`).join(' ');
  return <svg viewBox="0 0 400 140" className="h-40 w-full" aria-label="Ölçüm geçmişi"><line x1="18" y1="120" x2="382" y2="120" stroke="#cbd5e1" />
    {values.length > 1 ? <polyline points={points} fill="none" stroke="#0284c7" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" /> : <circle cx="18" cy="120" r="5" fill="#0284c7" />}</svg>;
};

export const ReportsPage: React.FC = () => {
  const { vitals, cognitiveTestHistory } = useTelemetry();
  const { t } = usePrefs();
  const rows = ['pulse', 'oxygen', 'temperature', 'sleep'].map((key) => [key, vitals[key]] as const);
  return <div className="mx-auto max-w-6xl space-y-5 pb-12 animate-fadeIn">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><h1 className="text-2xl font-bold text-slate-900">{t('Raporlar', 'Reports')}</h1>
      <p className="text-sm text-slate-500">{t('Yalnızca merkezi veritabanındaki ölçüm geçmişi', 'Only measurement history from the central database')}</p></div>
      <button disabled className="flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-400"><Download className="h-4 w-4" />{t('Dışa aktarım yakında', 'Export coming soon')}</button></div>
    <div className="grid gap-4 md:grid-cols-2">{rows.map(([key, metric]) => <section key={key} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
       <div className="flex items-center justify-between"><h2 className="flex items-center gap-2 font-bold text-slate-900">{icons[key]}{typeof metric.name === 'string' ? metric.name : t(metric.name.tr, metric.name.en)}</h2>
        <span className="font-mono text-sm text-sky-800">{Number.isFinite(metric.value) ? `${metric.value} ${metric.unit}` : 'Kayıt yok'}</span></div>
      <Graph values={metric.history} /><p className="text-xs text-slate-500">{metric.history.length} {t('kayıt', 'records')} · {t('Sağlık eşiği uygulanmaz', 'No health threshold applied')}</p>
    </section>)}</div>
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><h2 className="font-bold text-slate-900">{t('Bilişsel test geçmişi', 'Cognitive test history')}</h2>
      {cognitiveTestHistory.length ? <div className="mt-3 divide-y">{cognitiveTestHistory.map((row, index) => <div key={index} className="flex justify-between py-2 text-sm"><span>{typeof row.date === 'string' ? row.date.slice(0, 16) : row.date.tr}</span><span>{typeof row.readinessLevel === 'string' ? row.readinessLevel : row.readinessLevel.tr}</span></div>)}</div>
        : <p className="mt-3 text-sm text-slate-500">{t('Kayıt yok.', 'No record.')}</p>}</section>
  </div>;
};
