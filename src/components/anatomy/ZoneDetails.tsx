import React from 'react';
import { ArrowRight, Orbit, ListChecks } from 'lucide-react';
import { usePrefs } from '../../context/PreferencesContext';
import { useTelemetry } from '../../context/TelemetryContext';
import { statusMeta } from '../../utils/status';
import { playUiBeep } from '../../utils/audio';
import { ZoneContent } from './zoneContent';

/** Bölge ölçümleri + uzay etkisi + yapılacaklar (modal ve anatomi sayfası ortak) */
export const ZoneDetails: React.FC<{ content: ZoneContent; onNavigate?: () => void }> = ({ content, onNavigate }) => {
  const { t } = usePrefs();
  const { setCurrentTab } = useTelemetry();

  return (
    <div className="space-y-5">
      {/* Ölçümler */}
      <section>
        <h3 className="text-sm font-bold text-slate-800 mb-2">{t('Güncel değerler', 'Current values')}</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
          {content.metrics.map((m) => {
            const meta = statusMeta(m.status, t);
            return (
              <div key={m.label} className="p-3 bg-slate-50 rounded-xl border border-slate-100">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm text-slate-600">{m.label}</span>
                  <span className={`px-1.5 py-0.5 rounded-md border text-xs font-semibold ${meta.badge}`}>{meta.label}</span>
                </div>
                <div className={`text-xl font-bold font-mono mt-1 ${meta.text}`}>{m.value}</div>
                <div className="text-xs text-slate-500 mt-0.5">
                  {t('Normal', 'Normal')}: {m.normal}
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* Uzayda ne oluyor? */}
      <section className="p-4 bg-sky-50 rounded-xl border border-sky-200">
        <h3 className="flex items-center gap-1.5 text-sm font-bold text-sky-800">
          <Orbit className="w-4 h-4" />
          {t('Uzayda ne oluyor?', 'What happens in space?')}
        </h3>
        <p className="text-sm text-slate-700 leading-relaxed mt-1.5">{content.spaceEffect}</p>
      </section>

      {/* Ne yapabilirim? */}
      <section>
        <h3 className="flex items-center gap-1.5 text-sm font-bold text-slate-800 mb-2">
          <ListChecks className="w-4 h-4 text-emerald-600" />
          {t('Ne yapabilirsiniz?', 'What you can do')}
        </h3>
        <ul className="space-y-1.5">
          {content.actions.map((a) => (
            <li key={a} className="flex items-start gap-2 text-sm text-slate-700">
              <span className="mt-2 w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" />
              {a}
            </li>
          ))}
        </ul>
      </section>

      {/* İlgili testler */}
      <div className="flex flex-wrap gap-2">
        {content.links.map((l) => (
          <button
            key={l.tab}
            onClick={() => {
              playUiBeep(880);
              setCurrentTab(l.tab);
              window.scrollTo({ top: 0, behavior: 'smooth' });
              onNavigate?.();
            }}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm font-semibold shadow-sm transition-colors"
          >
            {l.icon}
            {l.label}
            <ArrowRight className="w-4 h-4" />
          </button>
        ))}
      </div>
    </div>
  );
};
