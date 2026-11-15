import React from 'react';
import { useTelemetry } from '../../context/TelemetryContext';
import { usePrefs } from '../../context/PreferencesContext';

/** Alt durum çubuğu: bağlantı ve simülasyon bilgisi (menü header'da). */
export const FooterNav: React.FC = () => {
  const { systemTelemetery, missionProfile } = useTelemetry();
  const { t, pick } = usePrefs();

  return (
    <footer className="mt-auto mx-4 sm:mx-6 mb-4 glass-bar rounded-2xl py-3 px-4">
      <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-3 text-xs text-slate-500">
        <div className="flex items-center gap-2">
          <span className="flex h-2 w-2 relative">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
          </span>
          <span className="font-semibold text-slate-700">{t('Merkezi API bağlantısı', 'Central API connection')}</span>
          <span aria-hidden>•</span>
          <span className="font-mono">
            {t('Görev profili', 'Mission profile')} {pick(missionProfile.name)}
          </span>
          <span aria-hidden className="hidden sm:inline">•</span>
          <span className="hidden sm:inline font-mono">
            {t('Alınan ölçüm', 'Received measurements')} {systemTelemetery.activeSensors}
          </span>
        </div>

        <div className="flex items-center gap-2">
          <span>{pick(missionProfile.name)} • NASA Space Apps 2026</span>
        </div>
      </div>
    </footer>
  );
};
