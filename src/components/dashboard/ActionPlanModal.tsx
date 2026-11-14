import React, { useEffect, useState } from 'react';
import { X, CheckCircle, Radio, ShieldAlert, HeartPulse, Check, Timer, Satellite } from 'lucide-react';
import { formatDelay } from '../../data/missionProfiles';
import { useTelemetry } from '../../context/TelemetryContext';
import { usePrefs } from '../../context/PreferencesContext';
import { playUiBeep, playSuccessChime } from '../../utils/audio';

export const ActionPlanModal: React.FC = () => {
  const { currentAlert, resolveAlert, openActionPlanModal, setOpenActionPlanModal, astronaut, missionProfile } = useTelemetry();
  const { t, pick, lang } = usePrefs();
  const [completedSteps, setCompletedSteps] = useState<number[]>([]);
  const [isTransmitting, setIsTransmitting] = useState(false);
  const [sentAt, setSentAt] = useState<Date | null>(null);

  const close = () => {
    playUiBeep(600);
    setOpenActionPlanModal(false);
  };

  // Esc ile kapat
  useEffect(() => {
    if (!openActionPlanModal) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpenActionPlanModal(false);
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [openActionPlanModal, setOpenActionPlanModal]);

  // Yeni uyarıda işaretli adımları ve gönderim durumunu sıfırla
  useEffect(() => {
    setCompletedSteps([]);
    setSentAt(null);
  }, [currentAlert?.id]);

  if (!openActionPlanModal || !currentAlert) return null;

  const critical = currentAlert.severity === 'critical';
  const total = currentAlert.steps.length;
  const done = completedSteps.length;
  const pct = total ? Math.round((done / total) * 100) : 0;

  const toggleStep = (idx: number) => {
    playUiBeep(700);
    setCompletedSteps((prev) => (prev.includes(idx) ? prev.filter((i) => i !== idx) : [...prev, idx]));
  };

  // Kendi başına karar akışı: önce müdahale, sonra izleme, sonra yer ekibi
  const recheckMin = critical ? 5 : 30;
  const delaySec = missionProfile.oneWayDelaySec;
  const longDelay = delaySec >= 60;
  const utc = (d: Date) => d.toISOString().slice(11, 16);

  const handleTransmitReport = () => {
    playUiBeep(880);
    setIsTransmitting(true);
    setTimeout(() => {
      setIsTransmitting(false);
      setSentAt(new Date());
      playSuccessChime();
    }, 900);
  };

  const handleCompleteProtocol = () => {
    playSuccessChime();
    resolveAlert();
    setOpenActionPlanModal(false);
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/50 backdrop-blur-sm animate-fadeIn"
      onClick={close}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="action-plan-title"
        onClick={(e) => e.stopPropagation()}
        className="relative w-full max-w-2xl bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden flex flex-col max-h-[90vh]"
      >
        {/* Başlık */}
        <div
          className={`p-5 border-b flex items-start justify-between gap-3 ${
            critical ? 'bg-red-50 border-red-200' : 'bg-amber-50 border-amber-200'
          }`}
        >
          <div className="flex items-start gap-3">
            <div className={`p-2.5 rounded-xl text-white shrink-0 ${critical ? 'bg-red-600' : 'bg-amber-500'}`}>
              <ShieldAlert className="w-6 h-6" />
            </div>
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <span
                  className={`px-2 py-0.5 rounded-md text-xs font-bold uppercase text-white ${
                    critical ? 'bg-red-600' : 'bg-amber-600'
                  }`}
                >
                  {critical ? t('Kritik', 'Critical') : t('Dikkat', 'Caution')}
                </span>
                <span className="text-xs font-mono text-slate-500">{currentAlert.protocolCode}</span>
                {currentAlert.backend && (
                  <span className="px-2 py-0.5 rounded-md border border-slate-300 bg-white text-xs font-semibold text-slate-600">
                    {
                      {
                        OPEN: t('Açık', 'Open'),
                        ACKNOWLEDGED: t('Yer ekibi gördü', 'Acknowledged'),
                        RESOLVED: t('Kapatıldı', 'Resolved'),
                      }[currentAlert.backend.status]
                    }
                  </span>
                )}
              </div>
              <h2 id="action-plan-title" className="text-lg font-bold text-slate-900 mt-1 leading-snug">
                {pick(currentAlert.title)}
              </h2>
            </div>
          </div>
          <button
            onClick={close}
            aria-label={t('Kapat', 'Close')}
            className="p-2 rounded-xl text-slate-500 hover:text-slate-800 hover:bg-white/80 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-5 overflow-y-auto flex-1">
          {/* Ne oldu? */}
          <section className="space-y-3">
            <p className="text-base text-slate-700 leading-relaxed">{pick(currentAlert.description)}</p>
            <dl className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm">
              <div className="p-3 rounded-xl bg-slate-50 border border-slate-100">
                <dt className="text-xs text-slate-500">{t('Etkilenen değer', 'Affected value')}</dt>
                <dd className={`font-bold mt-0.5 ${critical ? 'text-red-700' : 'text-amber-700'}`}>
                  {pick(currentAlert.parameter)}
                </dd>
              </div>
              <div className="p-3 rounded-xl bg-slate-50 border border-slate-100">
                <dt className="text-xs text-slate-500">{t('Algılanma', 'Detected')}</dt>
                <dd className="font-semibold text-slate-800 mt-0.5">
                  {pick(currentAlert.timestamp)} • {t('Görev günü', 'Mission day')} {astronaut.solDay}
                </dd>
              </div>
            </dl>
          </section>

          {/* Adımlar */}
          <section>
            <div className="flex items-center justify-between mb-2">
              <h3 className="flex items-center gap-2 text-base font-bold text-slate-900">
                <span className="w-6 h-6 rounded-full bg-slate-800 text-white text-xs flex items-center justify-center">1</span>
                {t('Kendin yap — şimdi', 'Act yourself — now')}
              </h3>
              <span className="text-sm font-mono text-slate-500">
                {done}/{total}
              </span>
            </div>
            <div className="h-1.5 rounded-full bg-slate-200 overflow-hidden mb-3">
              <div className="h-full bg-emerald-500 rounded-full transition-all" style={{ width: `${pct}%` }} />
            </div>

            <ol className="space-y-2">
              {currentAlert.steps.map((step, idx) => {
                const isChecked = completedSteps.includes(idx);
                return (
                  <li key={idx}>
                    <button
                      type="button"
                      onClick={() => toggleStep(idx)}
                      aria-pressed={isChecked}
                      className={`w-full text-left flex items-start gap-3 p-3 rounded-xl border transition-all ${
                        isChecked
                          ? 'bg-emerald-50 border-emerald-300'
                          : 'bg-white border-slate-200 hover:border-sky-300 hover:bg-sky-50'
                      }`}
                    >
                      <span
                        className={`mt-0.5 w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold shrink-0 border-2 transition-colors ${
                          isChecked ? 'bg-emerald-600 border-emerald-600 text-white' : 'border-slate-300 text-slate-500'
                        }`}
                      >
                        {isChecked ? <Check className="w-3.5 h-3.5" /> : idx + 1}
                      </span>
                      <span className={`text-sm leading-relaxed ${isChecked ? 'line-through text-slate-500' : 'text-slate-800'}`}>
                        {pick(step)}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ol>
          </section>

          {/* Önleyici tedbir */}
          <section className="p-4 bg-blue-50 rounded-xl border border-blue-200">
            <h3 className="text-sm font-bold text-blue-800 flex items-center gap-1.5">
              <HeartPulse className="w-4 h-4" />
              {t('Önerilen tedbir', 'Recommended countermeasure')}
            </h3>
            <p className="text-sm text-slate-700 mt-1">{pick(currentAlert.countermeasure)}</p>
          </section>

          {/* 2. aşama: izle */}
          <section className="p-4 rounded-xl border border-slate-200">
            <h3 className="flex items-center gap-2 text-base font-bold text-slate-900">
              <span className="w-6 h-6 rounded-full bg-slate-800 text-white text-xs flex items-center justify-center">2</span>
              {t('İzle', 'Monitor')}
            </h3>
            <p className="flex items-start gap-2 text-sm text-slate-700 mt-2">
              <Timer className="w-4 h-4 mt-0.5 shrink-0 text-slate-500" />
              {t(
                `${recheckMin} dakika sonra değeri tekrar ölç. Düzelmediyse veya kötüleştiyse 3. adıma geç.`,
                `Measure again in ${recheckMin} minutes. If it hasn't improved or got worse, go to step 3.`
              )}
            </p>
          </section>

          {/* 3. aşama: yer ekibi (gecikme görev ortamına göre) */}
          <section className={`p-4 rounded-xl border ${longDelay ? 'border-amber-300 bg-amber-50' : 'border-slate-200 bg-slate-50'}`}>
            <h3 className="flex items-center gap-2 text-base font-bold text-slate-900">
              <span className="w-6 h-6 rounded-full bg-slate-800 text-white text-xs flex items-center justify-center">3</span>
              {t('Yer ekibine haber ver', 'Notify the ground team')}
            </h3>
            <p className="flex items-start gap-2 text-sm text-slate-700 mt-2">
              <Satellite className="w-4 h-4 mt-0.5 shrink-0 text-slate-500" />
              <span>
                <strong>{pick(missionProfile.name)}:</strong>{' '}
                {t(
                  `mesajın ${formatDelay(delaySec, 'tr')} sonra ulaşır, cevap en erken ${formatDelay(delaySec * 2, 'tr')} sonra gelir.`,
                  `your message arrives in ${formatDelay(delaySec, 'en')}; the earliest reply comes in ${formatDelay(delaySec * 2, 'en')}.`
                )}{' '}
                {pick(missionProfile.autonomy)}
              </span>
            </p>
            {longDelay && (
              <p className="text-sm font-semibold text-amber-800 mt-2">
                {t('Cevabı beklerken 1. ve 2. adımlara devam et; karar senin.', 'Keep doing steps 1 and 2 while you wait; the decision is yours.')}
              </p>
            )}
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <button
                onClick={handleTransmitReport}
                disabled={isTransmitting || !!sentAt}
                className="flex items-center gap-2 px-4 py-2 bg-white hover:bg-slate-100 disabled:opacity-60 text-slate-700 text-sm font-semibold rounded-xl border border-slate-300 shadow-sm transition-colors"
              >
                <Radio className={`w-4 h-4 text-blue-600 ${isTransmitting ? 'animate-spin' : ''}`} />
                {isTransmitting ? t('Gönderiliyor...', 'Sending...') : sentAt ? t('Gönderildi', 'Sent') : t('Raporu gönder', 'Send report')}
              </button>
              {sentAt && (
                <span className="text-sm text-slate-600 font-mono" role="status">
                  {t('Varış', 'Arrives')} {utc(new Date(sentAt.getTime() + delaySec * 1000))} UTC · {t('en erken cevap', 'earliest reply')}{' '}
                  {utc(new Date(sentAt.getTime() + delaySec * 2000))} UTC
                </span>
              )}
            </div>
          </section>
        </div>

        {/* Alt butonlar */}
        <div className="p-4 bg-slate-50 border-t border-slate-200 flex flex-wrap items-center justify-between gap-2">
          <span className="text-xs text-slate-500 max-w-xs">
            {t('Alarmı yer ekibi kapatır', 'The ground team closes the alert')} · {t('gecikme', 'delay')} {formatDelay(delaySec, lang)}
          </span>

          <div className="flex items-center gap-2">
            <button onClick={close} className="px-4 py-2 text-sm font-medium text-slate-600 hover:text-slate-900 transition-colors">
              {t('Kapat', 'Close')}
            </button>
            <button
              onClick={handleCompleteProtocol}
              disabled={done < total}
              title={done < total ? t('Önce tüm adımları işaretleyin', 'Check off all steps first') : undefined}
              className="flex items-center gap-1.5 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-300 disabled:cursor-not-allowed text-white text-sm font-bold rounded-xl shadow-sm transition-all"
            >
              <CheckCircle className="w-4 h-4" />
              {t('Adımları tamamladım', 'I completed the steps')}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
