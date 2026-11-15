import React from 'react';
import { ArrowLeft, Info } from 'lucide-react';
import { useTelemetry } from '../../context/TelemetryContext';
import { usePrefs } from '../../context/PreferencesContext';
import { DisplayOnlyNotice } from '../common/DisplayOnlyNotice';
import { PageHeader } from '../ui';
import { CognitiveTestCards } from '../../features/behavior/components/CognitiveTestCards';
import { useBehaviorData } from '../../features/behavior/useBehaviorData';
import { formatDayMonth } from '../../features/behavior/date';

/**
 * Sol menü → Testler → "Refleks testleri".
 * Davranışsal ve Refleks Modülü belgesine göre: tepki testi (PVT) ve zihinsel döndürme.
 * Testler Davranış modülüyle aynı bileşenlerden oynatılır ve aynı uca kaydedilir;
 * ekranda puan hesaplanmaz, renk/durum rozeti gösterilmez.
 */
export const CognitiveTestPage: React.FC = () => {
  const { setCurrentTab, astronaut } = useTelemetry();
  const { t, lang } = usePrefs();
  const { data, reload } = useBehaviorData();

  const missionLine = data.mission
    ? `${t('Görev günü', 'Mission day')} ${data.mission.mission_day} · ${formatDayMonth(data.mission.date, lang)} (UTC)`
    : undefined;

  return (
    <div className="w-full max-w-5xl mx-auto space-y-5 pb-12 animate-fadeIn">
      <button
        type="button"
        onClick={() => setCurrentTab('tests')}
        className="flex items-center gap-1.5 min-h-11 text-sm font-semibold text-slate-600 hover:text-slate-900"
      >
        <ArrowLeft className="w-4 h-4" />
        {t('Testlere dön', 'Back to tests')}
      </button>

      <PageHeader title={t('Refleks testleri', 'Reflex tests')} subtitle={missionLine} />

      {astronaut.isDisplayOnly ? (
        <DisplayOnlyNotice />
      ) : (
        <CognitiveTestCards tests={data.tests} onFinished={reload} />
      )}

      <p className="flex items-start gap-2 text-sm text-slate-500">
        <Info className="w-4 h-4 mt-0.5 shrink-0" />
        <span>
          {t('Sonuçlar Davranış modülüne kaydedilir; tüm geçmişi ', 'Results are saved to the Behavior module; see the full history in ')}
          <button type="button" onClick={() => setCurrentTab('behavior')} className="font-semibold text-blue-700 hover:underline">
            {t('Davranış → Geçmiş', 'Behavior → History')}
          </button>
          {t(' sekmesinde görebilirsin.', '.')}
        </span>
      </p>
    </div>
  );
};
