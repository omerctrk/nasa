import React, { useEffect, useRef, useState } from 'react';
import { RefreshCw, CheckCircle2 } from 'lucide-react';
import { Button, Card, InfoBox, PageHeader } from '../../components/ui';
import { usePrefs } from '../../context/PreferencesContext';
import { useTelemetry } from '../../context/TelemetryContext';
import { DisplayOnlyNotice } from '../../components/common/DisplayOnlyNotice';
import { ApiError } from '../../lib/apiClient';
import { errorMessage } from './api';
import { formatDayMonth } from './date';
import { useBehaviorData } from './useBehaviorData';
import { TodayTab, type BehaviorAction } from './components/TodayTab';
import { CheckinForm } from './components/CheckinForm';
import { WeeklyForm } from './components/WeeklyForm';
import { HistoryTab } from './components/HistoryTab';
import { CognitiveTestCards } from './components/CognitiveTestCards';
import { PvtTest } from './tests/PvtTest';
import { RotationTest } from './tests/RotationTest';

type Tab = 'today' | 'checkin' | 'tests' | 'history';

/**
 * Davranışsal ve Refleks modülü.
 * Puan hesaplamaz, renk üretmez, veri saklamaz: soruları gösterir, testleri oynatır,
 * ham sonuçları backend'e gönderir ve dönen değerleri gösterir.
 */
export const BehaviorPage: React.FC = () => {
  const { t, lang } = usePrefs();
  const { astronaut } = useTelemetry();
  const { data, loading, error, reload } = useBehaviorData();
  const [tab, setTab] = useState<Tab>('today');
  const [activeTest, setActiveTest] = useState<'pvt' | 'rotation' | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const weeklyRef = useRef<HTMLDivElement>(null);
  const [scrollToWeekly, setScrollToWeekly] = useState(false);

  useEffect(() => {
    if (!toast) return;
    const id = window.setTimeout(() => setToast(null), 4000);
    return () => window.clearTimeout(id);
  }, [toast]);

  useEffect(() => {
    if (tab === 'checkin' && scrollToWeekly) {
      weeklyRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      setScrollToWeekly(false);
    }
  }, [tab, scrollToWeekly]);

  const onAction = (a: BehaviorAction) => {
    if (a === 'pvt' || a === 'rotation') setActiveTest(a);
    else {
      setTab('checkin');
      if (a === 'weekly') setScrollToWeekly(true);
      else window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  const finishTest = async () => {
    setActiveTest(null);
    setTab('today');
    await reload();
  };

  const missionLine = data.mission
    ? `${t('Görev günü', 'Mission day')} ${data.mission.mission_day} · ${formatDayMonth(data.mission.date, lang)} (UTC)`
    : '';

  const tabs: { id: Tab; label: string }[] = [
    { id: 'today', label: t('Bugün', 'Today') },
    { id: 'checkin', label: t('Check-in', 'Check-in') },
    { id: 'tests', label: t('Testler', 'Tests') },
    { id: 'history', label: t('Geçmiş', 'History') },
  ];

  return (
    <div className="w-full max-w-6xl mx-auto space-y-5 pb-12 animate-fadeIn">
      <PageHeader
        title={`${t('Davranış ve Refleks', 'Behavior & Reflex')}${data.mission ? ` · ${t('Görev günü', 'Mission day')} ${data.mission.mission_day}` : ''}`}
        subtitle={missionLine}
      />

      <div role="tablist" aria-label={t('Modül sekmeleri', 'Module tabs')} className="flex gap-1 p-1 bg-white rounded-xl border border-slate-200 shadow-sm w-full sm:w-fit overflow-x-auto">
        {tabs.map((x) => (
          <button
            key={x.id}
            role="tab"
            aria-selected={tab === x.id}
            onClick={() => setTab(x.id)}
            className={`flex-1 sm:flex-none min-h-11 px-4 rounded-lg text-sm font-semibold whitespace-nowrap transition-colors ${
              tab === x.id ? 'bg-slate-800 text-white' : 'text-slate-600 hover:bg-slate-100'
            }`}
          >
            {x.label}
          </button>
        ))}
      </div>

      {toast && (
        <div role="status" className="flex items-center gap-2 px-4 py-3 rounded-xl bg-slate-800 text-white text-sm w-fit">
          <CheckCircle2 className="w-4 h-4" />
          {toast}
        </div>
      )}

      {astronaut.isDisplayOnly ? (
        <DisplayOnlyNotice />
      ) : error ? (
        <InfoBox>
          <div className="flex flex-wrap items-center gap-3">
            <span>{errorMessage(error, t)}</span>
            {!(error instanceof ApiError && error.status === 401) && (
              <Button variant="secondary" onClick={() => void reload()}>
                <RefreshCw className="w-4 h-4" />
                {t('Tekrar dene', 'Try again')}
              </Button>
            )}
          </div>
        </InfoBox>
      ) : (
        <>
          {tab === 'today' && <TodayTab data={data} loading={loading} onAction={onAction} />}

          {tab === 'checkin' && (
            <div className="grid grid-cols-1 gap-5 max-w-3xl">
              {loading ? (
                <Card className="p-6 text-sm text-slate-500">{t('Yükleniyor…', 'Loading…')}</Card>
              ) : (
                <CheckinForm
                  today={data.today}
                  existing={data.todayCheckin}
                  etag={data.todayEtag}
                  onReloadNeeded={reload}
                  onSaved={async () => {
                    setToast(t('Check-in kaydedildi', 'Check-in saved'));
                    await reload();
                    setTab('today');
                    window.scrollTo({ top: 0, behavior: 'smooth' });
                  }}
                />
              )}
              <div ref={weeklyRef} className="scroll-mt-24">
                <WeeklyForm onSaved={() => void reload()} />
              </div>
            </div>
          )}

          {tab === 'tests' && (
            <CognitiveTestCards
              tests={data.tests}
              onFinished={async () => {
                setTab('today');
                await reload();
              }}
            />
          )}

          {tab === 'history' && <HistoryTab data={data} loading={loading} onCheckin={() => onAction('checkin')} onReload={reload} />}
        </>
      )}

      {activeTest === 'pvt' && <PvtTest onClose={() => setActiveTest(null)} onFinished={() => void finishTest()} />}
      {activeTest === 'rotation' && <RotationTest onClose={() => setActiveTest(null)} onFinished={() => void finishTest()} />}
    </div>
  );
};
