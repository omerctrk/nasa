import React, { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Maximize2, X, RotateCcw, Info } from 'lucide-react';
import { usePrefs } from '../../../context/PreferencesContext';
import { newIdempotencyKey } from '../../../lib/apiClient';
import { behavioralApi, errorMessage } from '../api';
import { exitFullscreen, requestFullscreen } from '../timing';
import type { CognitiveTest, CognitiveTestInput } from '../types';

/**
 * Test ekranlarının ortak çerçevesi: tüm ekranı kaplayan sade, koyu zemin.
 * Test sırasında menü, bildirim veya animasyon görünmez. Her temada koyu kalır.
 */
export const TestShell: React.FC<{
  title: string;
  onClose: () => void;
  /** Test sürerken kapatma düğmesi soluk görünür */
  running?: boolean;
  children: React.ReactNode;
}> = ({ title, onClose, running = false, children }) => {
  const { t } = usePrefs();
  const rootRef = useRef<HTMLDivElement>(null);

  // Arka plandaki sayfa kaymasın
  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = prev;
      exitFullscreen();
    };
  }, []);

  // body'ye taşınır: üst öğelerdeki transform/animasyon 'fixed' konumu bozmasın
  return createPortal(
    <div
      ref={rootRef}
      role="dialog"
      aria-modal="true"
      aria-label={title}
      className="fixed inset-0 z-[100] flex flex-col"
      style={{ backgroundColor: '#020617', color: '#e2e8f0' }}
    >
      <div className={`flex items-center justify-between px-4 py-3 transition-opacity ${running ? 'opacity-25 hover:opacity-100' : ''}`}>
        <button
          type="button"
          onClick={onClose}
          className="flex items-center gap-1.5 min-h-11 px-3 rounded-xl text-sm"
          style={{ color: '#94a3b8' }}
        >
          <X className="w-4 h-4" />
          {running ? t('Testi bırak', 'Quit test') : t('Kapat', 'Close')}
        </button>
        {!running && (
          <button
            type="button"
            onClick={() => requestFullscreen(rootRef.current)}
            className="flex items-center gap-1.5 min-h-11 px-3 rounded-xl text-sm"
            style={{ color: '#94a3b8' }}
          >
            <Maximize2 className="w-4 h-4" />
            {t('Tam ekran', 'Full screen')}
          </button>
        )}
      </div>
      <div className="flex-1 flex flex-col items-center justify-center px-4 pb-8 overflow-y-auto">{children}</div>
    </div>,
    document.body
  );
};

/** Koyu zeminde birincil buton */
export const ShellButton: React.FC<React.ButtonHTMLAttributes<HTMLButtonElement> & { tone?: 'primary' | 'secondary' }> = ({
  tone = 'primary',
  className = '',
  style,
  ...rest
}) => (
  <button
    type="button"
    className={`min-h-12 px-6 rounded-xl text-base font-semibold transition-opacity hover:opacity-90 disabled:opacity-40 ${className}`}
    style={
      tone === 'primary'
        ? { backgroundColor: '#2563eb', color: '#fff', ...style }
        : { backgroundColor: 'transparent', color: '#e2e8f0', border: '1px solid #475569', ...style }
    }
    {...rest}
  />
);

/**
 * Sonuç gönderimi: ham denemeler bellekte tutulur, ağ hatasında aynı
 * Idempotency-Key ile tekrar gönderilir (ikinci kayıt oluşmaz).
 */
export const useTestSubmission = () => {
  const { t } = usePrefs();
  const [state, setState] = useState<'idle' | 'sending' | 'done' | 'failed'>('idle');
  const [result, setResult] = useState<CognitiveTest | null>(null);
  const [error, setError] = useState<string | null>(null);
  const payloadRef = useRef<CognitiveTestInput | null>(null);
  const keyRef = useRef<string | null>(null);

  const send = useCallback(async () => {
    if (!payloadRef.current || !keyRef.current) return;
    setState('sending');
    setError(null);
    try {
      const res = await behavioralApi.postTest(payloadRef.current, keyRef.current);
      setResult(res.data);
      setState('done');
    } catch (e) {
      setError(errorMessage(e, t));
      setState('failed');
    }
  }, [t]);

  const submit = useCallback(
    (payload: CognitiveTestInput) => {
      payloadRef.current = payload;
      keyRef.current = newIdempotencyKey();
      if (import.meta.env.DEV) console.debug('[test] gönderilen', keyRef.current, payload);
      void send();
    },
    [send]
  );

  const reset = useCallback(() => {
    payloadRef.current = null;
    keyRef.current = null;
    setResult(null);
    setError(null);
    setState('idle');
  }, []);

  return { state, result, error, submit, retry: send, reset };
};

/** "Sonuçlar kaydediliyor…" / hata + Tekrar dene */
export const SubmitStatus: React.FC<{ state: 'sending' | 'failed'; error: string | null; onRetry: () => void }> = ({
  state,
  error,
  onRetry,
}) => {
  const { t } = usePrefs();
  if (state === 'sending') {
    return (
      <div className="text-center space-y-3" role="status">
        <div className="w-10 h-10 rounded-full border-4 border-t-transparent animate-spin mx-auto" style={{ borderColor: '#475569', borderTopColor: 'transparent' }} />
        <p className="text-lg">{t('Sonuçlar kaydediliyor…', 'Saving results…')}</p>
      </div>
    );
  }
  return (
    <div className="text-center space-y-4 max-w-md">
      <p className="text-lg">{error}</p>
      <p className="text-sm" style={{ color: '#94a3b8' }}>
        {t('Denemelerin kaybolmadı; tekrar gönderilebilir.', 'Your trials are kept and can be sent again.')}
      </p>
      <ShellButton onClick={onRetry}>
        <span className="inline-flex items-center gap-2">
          <RotateCcw className="w-4 h-4" />
          {t('Tekrar dene', 'Try again')}
        </span>
      </ShellButton>
    </div>
  );
};

/** Test yarıda kaldı (sekme değişimi) — hiçbir şey gönderilmez */
export const InvalidNotice: React.FC<{ onRestart: () => void }> = ({ onRestart }) => {
  const { t } = usePrefs();
  return (
    <div className="text-center space-y-4 max-w-md">
      <Info className="w-8 h-8 mx-auto" style={{ color: '#94a3b8' }} />
      <p className="text-xl font-semibold">{t('Test yarıda kaldı. Lütfen tekrar dene.', 'The test was interrupted. Please try again.')}</p>
      <ShellButton onClick={onRestart}>{t('Tekrar dene', 'Try again')}</ShellButton>
    </div>
  );
};

/** Backend valid:false döndüğünde */
export const InvalidResult: React.FC<{ onRestart: () => void; onDone: () => void }> = ({ onRestart, onDone }) => {
  const { t } = usePrefs();
  return (
    <div className="text-center space-y-4 max-w-md">
      <p className="text-lg">
        {t(
          'Test geçerli sayılmadı (çok fazla erken basma veya az deneme). İstersen tekrar yapabilirsin.',
          'The test was not counted (too many early presses or too few trials). You can take it again if you like.'
        )}
      </p>
      <div className="flex justify-center gap-3">
        <ShellButton onClick={onRestart}>{t('Tekrar dene', 'Try again')}</ShellButton>
        <ShellButton tone="secondary" onClick={onDone}>
          {t('Bitti', 'Done')}
        </ShellButton>
      </div>
    </div>
  );
};

/** Sonuç ekranında bir değer kutusu (renk yok) */
export const ResultStat: React.FC<{ label: string; value: React.ReactNode }> = ({ label, value }) => (
  <div className="p-4 rounded-xl text-center" style={{ backgroundColor: '#0f172a', border: '1px solid #1e293b' }}>
    <div className="text-sm" style={{ color: '#94a3b8' }}>
      {label}
    </div>
    <div className="text-3xl font-bold font-mono mt-1">{value}</div>
  </div>
);
