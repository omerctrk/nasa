import React from 'react';
import { Anatomy3D } from './Anatomy3D';
import { useTelemetry } from '../../context/TelemetryContext';
import { usePrefs } from '../../context/PreferencesContext';
import { AnatomyZoneId } from '../../types/telemetry';
import { playUiBeep } from '../../utils/audio';
import { statusMeta } from '../../utils/status';
import { getZoneContent } from './zoneContent';
import { ZoneDetails } from './ZoneDetails';

const ZONES: AnatomyZoneId[] = ['head', 'chest', 'abdomen', 'musculoskeletal'];

export const AnatomyPage: React.FC = () => {
  const { vitals, selectedAnatomyZone, setSelectedAnatomyZone } = useTelemetry();
  const { t } = usePrefs();
  const active: AnatomyZoneId = selectedAnatomyZone || 'head';
  const content = getZoneContent(active, vitals, t);
  const meta = statusMeta(content.status, t);

  const handleSelect = (zone: AnatomyZoneId) => {
    playUiBeep(750);
    setSelectedAnatomyZone(zone);
  };

  return (
    <div className="w-full max-w-7xl mx-auto space-y-5 pb-12 animate-fadeIn">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{t('Vücut Haritası', 'Body Map')}</h1>
          <p className="text-sm text-slate-500 mt-1">
            {t(
              'Uzay ortamının vücudunuzun her bölgesini nasıl etkilediğini ve neler yapabileceğinizi görün.',
              'See how spaceflight affects each part of your body and what you can do about it.'
            )}
          </p>
        </div>

        {/* Bölge seçici */}
        <div role="tablist" className="flex flex-wrap items-center gap-1 bg-white p-1 rounded-xl border border-slate-200 shadow-sm">
          {ZONES.map((z) => {
            const c = getZoneContent(z, vitals, t);
            const m = statusMeta(c.status, t);
            const isActive = active === z;
            return (
              <button
                key={z}
                role="tab"
                aria-selected={isActive}
                onClick={() => handleSelect(z)}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-semibold transition-all ${
                  isActive ? 'bg-blue-600 text-white' : 'text-slate-600 hover:bg-slate-100'
                }`}
              >
                <span className={`w-2 h-2 rounded-full ${m.dot}`} />
                {c.title}
              </button>
            );
          })}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        <div className="lg:col-span-7 h-[640px] lg:h-[720px] lg:sticky lg:top-6">
          <Anatomy3D fullPageView onSelectZone={(zone) => setSelectedAnatomyZone(zone)} />
        </div>

        <section className="lg:col-span-5 bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
          <div className="flex items-center gap-3 pb-4 mb-5 border-b border-slate-100">
            <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-200">{content.icon}</div>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-lg font-bold text-slate-900">{content.title}</h2>
                <span className={`px-2 py-0.5 rounded-md border text-xs font-semibold ${meta.badge}`}>{meta.label}</span>
              </div>
              <p className="text-sm text-slate-500">{content.subtitle}</p>
            </div>
          </div>
          <ZoneDetails content={content} />
        </section>
      </div>
    </div>
  );
};
