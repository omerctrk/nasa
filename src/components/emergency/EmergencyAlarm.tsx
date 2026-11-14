import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Siren, Send, SatelliteDish, Stethoscope, Radio, Loader2, Check, WifiOff, Rocket, ChevronUp, X } from 'lucide-react';
import { useTelemetry } from '../../context/TelemetryContext';
import { usePrefs } from '../../context/PreferencesContext';
import { newIdempotencyKey } from '../../lib/apiClient';
import { emergencyApi, EMERGENCY_REMOTE_AVAILABLE, type EmergencyNotification, type EmergencyStatus } from '../../lib/backend/emergencyApi';
import { mappingByVital } from '../../lib/backend/measurementCodes';
import { useNotifications } from '../../lib/backend/notifications';
import { formatDelay } from '../../data/missionProfiles';
import { vitalLabel } from '../../utils/status';
import { playSirenTone } from '../../utils/audio';

interface Episode {
  metric: string;
  value: number;
  unit: string;
  range: string;
  detectedAt: string;
  key: string;
  record: EmergencyNotification | null;
  offline: boolean;
  acknowledged: boolean;
  expanded: boolean;
}

const ORDER: EmergencyStatus[] = ['SENT', 'RECEIVED', 'SURGEON_ASSIGNED', 'SURGEON_CONNECTED'];
const hhmmss = (iso: string | null | undefined) => (iso ? `${iso.slice(11, 19)} UTC` : '');

/**
 * Kritik yaşamsal bulguda kırmızı alarm:
 * otomatik olarak Dünya'daki Görev Kontrol Merkezi'ne acil bildirim gönderir,
 * uçuş cerrahının yönlendirilmesini canlı izler.
 */
export const EmergencyAlarm: React.FC = () => {
  const { vitals, astronaut, missionProfile, currentAlert, setOpenActionPlanModal } = useTelemetry();
  const { t, pick, lang } = usePrefs();
  const [ep, setEp] = useState<Episode | null>(null);
  // Bu kritik dönem için zaten alarm verilen göstergeler (normale dönünce yeniden kurulur)
  const fired = useRef(new Set<string>());

  // Astronot değişince sıfırla
  useEffect(() => {
    setEp(null);
    fired.current.clear();
  }, [astronaut.id]);

  // 1) Kritik değeri yakala
  useEffect(() => {
    for (const [k, m] of Object.entries(vitals)) {
      if (k === 'sleep') continue;
      if (m.status !== 'critical') fired.current.delete(k);
    }
    if (astronaut.isDisplayOnly) return;
    if (ep && !(ep.record?.status === 'SURGEON_CONNECTED' && ep.acknowledged && !ep.expanded)) return;
    const hit = Object.entries(vitals).find(([k, m]) => k !== 'sleep' && m.status === 'critical' && !fired.current.has(k));
    if (!hit) return;
    const [k, m] = hit;
    fired.current.add(k);
    setEp({
      metric: k,
      value: Number(m.value),
      unit: m.unit,
      range: `${m.minNormal}–${m.maxNormal} ${m.unit}`,
      detectedAt: new Date().toISOString(),
      key: newIdempotencyKey(),
      record: null,
      offline: false,
      acknowledged: false,
      expanded: true,
    });
  }, [vitals, astronaut.isDisplayOnly, ep]);

  // 2) Gönder (ağ hatasında aynı anahtarla tekrar)
  const sending = !!ep && !ep.record;
  useEffect(() => {
    if (!ep || ep.record || !EMERGENCY_REMOTE_AVAILABLE) return;
    let stop = false;
    let timer: number | undefined;
    const send = async () => {
      try {
        const rec = await emergencyApi.create(
          ep.key,
          {
            client_request_id: ep.key,
            astronaut_id: astronaut.id,
            measurement_code: mappingByVital(ep.metric)?.measurement_code ?? ep.metric,
            value: ep.value,
            unit: ep.unit,
            detected_at: ep.detectedAt,
            severity: 'CRITICAL',
          },
          missionProfile.oneWayDelaySec
        );
        if (!stop) setEp((p) => (p && p.key === ep.key ? { ...p, record: rec, offline: false } : p));
      } catch {
        if (stop) return;
        setEp((p) => (p && p.key === ep.key ? { ...p, offline: true } : p));
        timer = window.setTimeout(send, 3000);
      }
    };
    void send();
    return () => {
      stop = true;
      window.clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ep?.key, sending]);

  // 3) Durumu izle
  const refresh = useCallback(async (id: string) => {
    try {
      const rec = await emergencyApi.get(id);
      setEp((p) => (p && p.record?.emergency_id === id ? { ...p, record: rec } : p));
    } catch {
      /* bir sonraki turda tekrar */
    }
  }, []);
  const recId = ep?.record?.emergency_id;
  const done = ep?.record?.status === 'SURGEON_CONNECTED';
  useEffect(() => {
    if (!recId || done) return;
    const id = window.setInterval(() => void refresh(recId), 1000);
    return () => window.clearInterval(id);
  }, [recId, done, refresh]);
  useNotifications((ev) => {
    if (ev.event_type === 'emergency.updated' && recId) void refresh(recId);
  });

  // 4) Siren: astronot görene kadar
  const sirenOn = !!ep && !ep.acknowledged;
  useEffect(() => {
    if (!sirenOn) return;
    playSirenTone();
    const id = window.setInterval(playSirenTone, 1100);
    return () => window.clearInterval(id);
  }, [sirenOn]);

  // Esc: alarmı gördüm
  useEffect(() => {
    if (!ep?.expanded) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setEp((p) => (p ? { ...p, acknowledged: true, expanded: false } : p));
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [ep?.expanded]);

  if (!ep) return null;

  const rec = ep.record;
  const reached = rec ? ORDER.indexOf(rec.status) : -1;
  const live = vitals[ep.metric];
  const stillCritical = live?.status === 'critical';
  const delay = missionProfile.oneWayDelaySec;
  const longDelay = delay >= 60;

  const statusLine = !EMERGENCY_REMOTE_AVAILABLE
    ? t('Yer ekibine sesli kanaldan haber verin', 'Call the ground team on the voice loop')
    : !rec
    ? ep.offline
      ? t('Bağlantı yok — yeniden deneniyor', 'No link — retrying')
      : t('Merkeze gönderiliyor…', 'Sending to Mission Control…')
    : {
        SENT: t('Merkeze gönderildi', 'Sent to Mission Control'),
        RECEIVED: t('Görev Kontrol Merkezi aldı', 'Mission Control received'),
        SURGEON_ASSIGNED: t('Uçuş cerrahı yönlendirildi', 'Flight surgeon dispatched'),
        SURGEON_CONNECTED: t('Uçuş cerrahı bağlantıda', 'Flight surgeon connected'),
      }[rec.status];

  const steps = [
    {
      icon: Send,
      title: t('Acil bildirim gönderildi', 'Emergency notification sent'),
      sub: t('Otomatik · kritik eşik aşıldı', 'Automatic · critical threshold crossed'),
      at: rec?.sent_at,
    },
    {
      icon: SatelliteDish,
      title: t('Görev Kontrol Merkezi aldı', 'Mission Control received it'),
      sub: t(`Dünya · tek yön gecikme ${formatDelay(delay, lang)}`, `Earth · one-way delay ${formatDelay(delay, lang)}`),
      at: rec?.received_at,
    },
    {
      icon: Stethoscope,
      title: t('Uçuş cerrahı yönlendirildi', 'Flight surgeon dispatched'),
      sub: t('Nöbetçi uçuş cerrahı vakayı üstlendi', 'On-duty flight surgeon took the case'),
      at: rec?.surgeon_assigned_at,
    },
    {
      icon: Radio,
      title: t('Cerrah bağlantıda', 'Surgeon connected'),
      sub: t('Acil sesli kanal açık (Space-to-Ground 2)', 'Emergency voice loop open (Space-to-Ground 2)'),
      at: rec?.surgeon_connected_at,
    },
  ];

  const acknowledge = () => setEp((p) => (p ? { ...p, acknowledged: true, expanded: false } : p));
  const close = () => setEp(null);

  // ------------------------------------------------ küçültülmüş şerit
  if (!ep.expanded) {
    return (
      <div className="fixed z-[70] top-3 left-4 right-4 lg:left-[18rem] lg:right-6 mx-auto max-w-xl" role="status">
        <div className="flex items-center gap-3 rounded-2xl border border-red-400/70 bg-red-600 text-white px-4 py-2.5 shadow-lg emergency-pill">
          <span className="relative flex w-3 h-3 shrink-0">
            {!done && <span className="absolute inset-0 rounded-full bg-white animate-ping opacity-70" />}
            <span className="relative w-3 h-3 rounded-full bg-white" />
          </span>
          <div className="min-w-0 flex-1 text-sm leading-tight">
            <span className="font-black tracking-wide">{t('ACİL', 'EMERGENCY')}</span>
            <span className="mx-1.5 opacity-60">·</span>
            <span className="font-semibold">{vitalLabel(ep.metric, t)}</span>
            <span className="block sm:inline sm:ml-2 text-red-100 text-xs">{statusLine}</span>
          </div>
          <button
            type="button"
            onClick={() => setEp((p) => (p ? { ...p, expanded: true } : p))}
            className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-white/15 hover:bg-white/25 text-xs font-semibold shrink-0"
          >
            <ChevronUp className="w-3.5 h-3.5" />
            {t('Ayrıntı', 'Details')}
          </button>
          {done && !stillCritical && (
            <button type="button" onClick={close} aria-label={t('Kapat', 'Close')} className="p-1 rounded-lg hover:bg-white/20 shrink-0">
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>
    );
  }

  // ------------------------------------------------ tam ekran kırmızı alarm
  return (
    <div className="fixed inset-0 z-[90] flex items-center justify-center p-4" role="alertdialog" aria-modal="true" aria-labelledby="emg-title">
      <div className="absolute inset-0 bg-red-950/75 backdrop-blur-sm" />
      <div className="absolute inset-0 emergency-vignette pointer-events-none" aria-hidden />

      <div className="relative w-full max-w-xl max-h-[92vh] overflow-y-auto rounded-3xl border border-red-500/60 bg-slate-950/90 text-slate-100 shadow-2xl emergency-card">
        {/* Başlık */}
        <div className="flex items-center gap-4 px-6 pt-6">
          <span className="relative grid place-items-center w-14 h-14 rounded-full bg-red-600 shrink-0 emergency-beacon">
            <Siren className="w-7 h-7 text-white" />
          </span>
          <div className="min-w-0">
            <h2 id="emg-title" className="text-2xl font-black tracking-wider text-red-400">
              {t('ACİL DURUM', 'EMERGENCY')}
            </h2>
            <p className="text-sm text-slate-300">{t('Kritik yaşamsal bulgu algılandı', 'Critical vital sign detected')}</p>
          </div>
        </div>

        {/* Değer */}
        <div className="mx-6 mt-5 rounded-2xl border border-red-500/40 bg-red-500/10 p-4 flex flex-wrap items-end justify-between gap-3">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wider text-red-300">{vitalLabel(ep.metric, t)}</div>
            <div className="mt-1 text-4xl font-black font-mono text-red-400 leading-none" style={{ textShadow: '0 0 18px rgba(248,113,113,.6)' }}>
              {ep.value}
              <span className="ml-1.5 text-base font-semibold text-red-300">{ep.unit}</span>
            </div>
          </div>
          <div className="text-right text-xs text-slate-300 space-y-0.5">
            <div>
              {t('Normal aralık', 'Normal range')}: <span className="font-mono">{ep.range}</span>
            </div>
            <div>
              {t('Algılandı', 'Detected')}: <span className="font-mono">{hhmmss(ep.detectedAt)}</span>
            </div>
            {live && Number(live.value) !== ep.value && (
              <div className={stillCritical ? 'text-red-300' : 'text-emerald-300'}>
                {t('Şu an', 'Now')}: <span className="font-mono font-semibold">{live.value} {live.unit}</span>
              </div>
            )}
          </div>
        </div>

        {/* Bildirim akışı */}
        <div className="px-6 mt-5">
          <div className="text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-3">
            {t('Dünya’ya acil bildirim', 'Emergency notification to Earth')}
          </div>
          {ep.offline && !rec && (
            <div className="mb-3 flex items-center gap-2 rounded-xl border border-amber-400/50 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
              <WifiOff className="w-4 h-4 shrink-0" />
              {t(
                'İletişim hattı yok. Bildirim kuyrukta; bağlantı gelince aynı kayıtla otomatik gönderilecek.',
                'No comm link. Notification is queued and will auto-send with the same record when the link returns.'
              )}
            </div>
          )}
          {!EMERGENCY_REMOTE_AVAILABLE ? (
            <div className="flex items-start gap-2 rounded-xl border border-amber-400/50 bg-amber-500/10 px-3 py-2.5 text-sm text-amber-100">
              <Radio className="w-4 h-4 mt-0.5 shrink-0" />
              {t(
                'Otomatik acil bildirim bu sürümde henüz merkeze bağlı değil. Görev Kontrol Merkezi’ne acil sesli kanaldan (Space-to-Ground 2) hemen haber verin.',
                'Automatic emergency notification is not yet connected to Mission Control in this version. Call Mission Control on the emergency voice loop (Space-to-Ground 2) now.'
              )}
            </div>
          ) : (
          <ol className="relative">
            {steps.map((s, i) => {
              const ok = i <= reached;
              const active = i === reached + 1;
              const Icon = s.icon;
              return (
                <li key={i} className="relative flex gap-3 pb-4 last:pb-0">
                  {i < steps.length - 1 && (
                    <span
                      className={`absolute left-[15px] top-8 bottom-0 w-0.5 ${i < reached ? 'bg-red-400' : 'bg-slate-700'}`}
                      aria-hidden
                    />
                  )}
                  <span
                    className={`relative z-10 grid place-items-center w-8 h-8 rounded-full border shrink-0 ${
                      ok
                        ? 'bg-red-600 border-red-400 text-white'
                        : active
                          ? 'border-red-400/70 text-red-300 bg-slate-900'
                          : 'border-slate-700 text-slate-500 bg-slate-900'
                    }`}
                    style={ok ? { boxShadow: '0 0 14px rgba(239,68,68,.6)' } : undefined}
                  >
                    {ok ? <Check className="w-4 h-4" /> : active ? <Loader2 className="w-4 h-4 animate-spin" /> : <Icon className="w-4 h-4" />}
                  </span>
                  <div className="min-w-0 flex-1 pt-0.5">
                    <div className="flex flex-wrap items-baseline justify-between gap-x-2">
                      <span className={`text-sm font-semibold ${ok ? 'text-white' : active ? 'text-red-200' : 'text-slate-500'}`}>{s.title}</span>
                      {ok && <span className="text-[11px] font-mono text-slate-400">{hhmmss(s.at)}</span>}
                    </div>
                    <div className={`text-xs ${ok || active ? 'text-slate-400' : 'text-slate-600'}`}>
                      {s.sub}
                    </div>
                  </div>
                </li>
              );
            })}
          </ol>
          )}
          {longDelay && (
            <p className="mt-3 text-xs text-amber-200/90 leading-relaxed">
              {t(
                `Dünya ile gecikme yüksek: cerrahın yanıtı en erken ${formatDelay(delay * 2, lang)} sonra ulaşır. Bu sürede aşağıdaki adımları uygulayın. (Demo: süreler kısaltıldı)`,
                `High Earth delay: the surgeon’s reply arrives in ${formatDelay(delay * 2, lang)} at the earliest. Follow the steps below meanwhile. (Demo: times shortened)`
              )}
            </p>
          )}
        </div>

        {/* Hemen yapılacaklar */}
        {currentAlert && currentAlert.steps.length > 0 && (
          <div className="mx-6 mt-5 rounded-2xl border border-slate-700 bg-slate-900/70 p-4">
            <div className="text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-2">
              {t('Yanıt beklerken şimdi yapın', 'Do now while waiting')}
            </div>
            <ol className="space-y-1.5 text-sm text-slate-200">
              {currentAlert.steps.slice(0, 2).map((s, i) => (
                <li key={i} className="flex gap-2">
                  <span className="font-mono font-bold text-red-400">{i + 1}.</span>
                  <span className="leading-snug">{pick(s)}</span>
                </li>
              ))}
            </ol>
          </div>
        )}

        {/* Düğmeler */}
        <div className="flex flex-col-reverse sm:flex-row gap-2 px-6 py-6">
          <button
            type="button"
            onClick={() => {
              acknowledge();
              setOpenActionPlanModal(true);
            }}
            disabled={!currentAlert}
            className="flex-1 flex items-center justify-center gap-1.5 px-4 py-3 rounded-xl border border-slate-600 text-slate-100 font-semibold hover:bg-slate-800 disabled:opacity-40"
          >
            <Rocket className="w-4 h-4" />
            {t('Eylem planını aç', 'Open action plan')}
          </button>
          <button
            type="button"
            onClick={acknowledge}
            autoFocus
            className="flex-1 px-4 py-3 rounded-xl bg-red-600 hover:bg-red-500 text-white font-bold"
            style={{ boxShadow: '0 0 22px -2px rgba(239,68,68,.7)' }}
          >
            {t('Alarmı gördüm', 'Acknowledge alarm')}
          </button>
        </div>
      </div>
    </div>
  );
};
