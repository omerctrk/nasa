import React from 'react';
import { ArrowDownToLine, Radiation, Satellite, Users, Wind } from 'lucide-react';
import { useTelemetry } from '../../context/TelemetryContext';
import { usePrefs } from '../../context/PreferencesContext';

const entries = [
  { id: 'radiation', Icon: Radiation, tr: 'Radyasyon', en: 'Radiation', source: 'Doz kaynağı bağlı değil' },
  { id: 'isolation', Icon: Users, tr: 'İzolasyon', en: 'Isolation', source: 'Davranış kaynağı bağlı değil' },
  { id: 'distance', Icon: Satellite, tr: 'Uzaklık', en: 'Distance', source: 'Gecikme kaynağı bağlı değil' },
  { id: 'gravity', Icon: ArrowDownToLine, tr: 'Yerçekimi', en: 'Gravity', source: 'Yalnızca kayıtlı ölçümler gösterilir' },
  { id: 'environment', Icon: Wind, tr: 'Kapalı ortam', en: 'Closed environment', source: 'Kabin sensörü bağlı değil' },
] as const;

export const HazardsPanel: React.FC = () => {
  const { vitals } = useTelemetry();
  const { t } = usePrefs();
  const heartRate = Number.isFinite(vitals.pulse.value) ? `${vitals.pulse.value} ${vitals.pulse.unit}` : null;
  return <section aria-labelledby="hazards-heading">
    <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2 px-1"><h2 id="hazards-heading" className="text-sm font-bold text-slate-800">{t('Görev Ortam Koşulları', 'Mission Environment Conditions')}</h2>
      <span className="text-xs text-slate-500">{t('Yalnızca bağlı veri kaynakları gösterilir', 'Only connected data sources are shown')}</span></div>
    <div className="grid grid-cols-2 gap-2.5 md:grid-cols-3 xl:grid-cols-5">{entries.map(({ id, Icon, tr, en, source }) => {
      const value = id === 'gravity' && heartRate ? heartRate : t('Kayıt yok', 'No record');
      const sub = id === 'gravity' && heartRate ? t('Son kayıtlı nabız', 'Latest stored heart rate') : t(source, source);
      return <div key={id} className="flex min-w-0 flex-col gap-1 rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
        <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-600"><Icon className="h-4 w-4 text-slate-500" />{t(tr, en)}</div>
        <div className="truncate font-mono text-base font-bold text-slate-900">{value}</div><div className="text-xs text-slate-500">{sub}</div>
      </div>;
    })}</div>
  </section>;
};
