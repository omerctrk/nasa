import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Sparkles, RotateCcw, Loader2, CheckCircle2, AlertTriangle, Info } from 'lucide-react';
import { useTelemetry } from '../../context/TelemetryContext';
import { usePrefs } from '../../context/PreferencesContext';
import { newIdempotencyKey } from '../../lib/apiClient';
import { analysisApi, isTerminal, RESULT_DETAILS_AVAILABLE } from '../../lib/backend/analysisApi';
import { anomalyLevelToStatus } from '../../lib/backend/adapters';
import { useNotifications } from '../../lib/backend/notifications';
import type { AnalysisJob, AnomalyResult } from '../../lib/backend/types';
import { statusMeta } from '../../utils/status';
import { errorMessage } from '../../features/behavior/api';

/** Analiz işini başlatır ve QUEUED → … → COMPLETED/FAILED boyunca izler. */
const useAnalysisJob = (astronautId: string, onFinished?: (job: AnalysisJob, result: AnomalyResult | null) => void) => {
  const { t } = usePrefs();
  const [job, setJob] = useState<AnalysisJob | null>(null);
  const [result, setResult] = useState<AnomalyResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const keyRef = useRef<string | null>(null);
  const finishedRef = useRef<string | null>(null);
  const onFinishedRef = useRef(onFinished);
  onFinishedRef.current = onFinished;

  // Astronot değişince sıfırla
  useEffect(() => {
    setJob(null);
    setResult(null);
    setError(null);
    keyRef.current = null;
  }, [astronautId]);

  const refresh = useCallback(
    async (id: string) => {
      try {
        const j = await analysisApi.getJob(id);
        setJob(j);
        let res: AnomalyResult | null = null;
        if (j.state === 'COMPLETED' && j.anomaly_result_id && RESULT_DETAILS_AVAILABLE) {
          res = await analysisApi.getResult(j.anomaly_result_id);
          setResult(res);
        }
        // Bitişi bir kez bildir: panel verisi (alarm, AI paneli, durumlar) yenilensin
        if (isTerminal(j.state) && finishedRef.current !== j.job_id) {
          finishedRef.current = j.job_id;
          onFinishedRef.current?.(j, res);
        }
      } catch (e) {
        setError(errorMessage(e, t));
      }
    },
    [t]
  );

  // Terminal duruma gelene kadar yokla (bildirim gelirse daha erken güncellenir)
  useEffect(() => {
    if (!job || isTerminal(job.state)) return;
    const id = window.setTimeout(() => void refresh(job.job_id), 1000);
    return () => window.clearTimeout(id);
  }, [job, refresh]);

  useNotifications((ev) => {
    if (job && ev.job_id === job.job_id) void refresh(job.job_id);
  });

  const start = async () => {
    setError(null);
    setResult(null);
    // Ağ hatasında aynı anahtarla tekrar → aynı iş döner
    keyRef.current ??= newIdempotencyKey();
    try {
      setJob(await analysisApi.createJob(keyRef.current, astronautId));
      keyRef.current = null;
    } catch (e) {
      setError(errorMessage(e, t));
    }
  };

  const retry = async () => {
    if (!job) return;
    setError(null);
    try {
      setJob(await analysisApi.retryJob(job.job_id));
    } catch (e) {
      setError(errorMessage(e, t));
    }
  };

  return { job, result, error, start, retry };
};

export const AnalysisStatus: React.FC<{ onFinished?: (job: AnalysisJob, result: AnomalyResult | null) => void }> = ({ onFinished }) => {
  const { astronaut } = useTelemetry();
  const { t } = usePrefs();
  const { job, result, error, start, retry } = useAnalysisJob(astronaut.id, onFinished);
  const busy = !!job && !isTerminal(job.state);

  const stateText: Record<string, string> = {
    QUEUED: t('Sıraya alındı', 'Queued'),
    SYNCING: t('Veriler toplanıyor', 'Collecting data'),
    ANALYZING: t('Analiz ediliyor', 'Analyzing'),
  };

  let body: React.ReactNode = (
    <span className="text-slate-500">{t('Bugünün verisini önceki günlerinle karşılaştırır; sapmayı yapay zekâ yorumlar.', 'Compares today with your previous days; AI interprets deviations.')}</span>
  );
  if (busy && job) {
    body = (
      <span className="flex items-center gap-1.5 text-slate-700" role="status">
        <Loader2 className="w-3.5 h-3.5 animate-spin" />
        {stateText[job.state]}…
      </span>
    );
  } else if (job?.state === 'FAILED') {
    body = (
      <span className="flex items-center gap-1.5 text-slate-700">
        <AlertTriangle className="w-3.5 h-3.5 text-slate-500" />
        {t('Analiz tamamlanamadı. Sonuç yok.', 'Analysis could not finish. No result.')}
      </span>
    );
  } else if (job?.state === 'COMPLETED' && !result && job.evaluation_status === 'evaluated') {
    body = (
      <span className="flex items-center gap-1.5 text-slate-700">
        <CheckCircle2 className="w-3.5 h-3.5 text-slate-500" />
        {t('Analiz tamamlandı. Sonuç uyarı olarak bildirilirse burada görünür.', 'Analysis complete. If it raises an alert, it will show here.')}
      </span>
    );
  } else if (job?.state === 'COMPLETED' && !result && job.evaluation_status !== 'evaluated') {
    body = (
      <span className="flex items-center gap-1.5 text-slate-700">
        <Info className="w-3.5 h-3.5 text-slate-500" />
        {job.evaluation_status === 'invalid_data'
          ? t('Veri geçersiz; değerlendirme yapılamadı.', 'Data invalid; could not evaluate.')
          : t('Yeterli veri yok; değerlendirme yapılamadı.', 'Not enough data to evaluate.')}
      </span>
    );
  } else if (result) {
    const meta = statusMeta(anomalyLevelToStatus(result.level), t);
    const levelText = { normal: t('Normal', 'Normal'), watch: t('İzle', 'Watch'), review: t('İncele', 'Review') }[result.level];
    body = (
      <span className="flex flex-col gap-1">
        <span className="flex items-center gap-1.5">
          <CheckCircle2 className="w-3.5 h-3.5 text-slate-500" />
          <span className={`px-1.5 py-0.5 rounded-md border text-xs font-semibold ${meta.badge}`}>{levelText}</span>
          <span className="text-slate-500 font-mono">{result.created_at.slice(11, 16)} UTC</span>
        </span>
        <span className="text-slate-600 leading-snug">{result.summary}</span>
      </span>
    );
  }

  return (
    <div className="mt-4 pt-3 border-t border-slate-100 text-xs">
      <div className="flex items-center justify-between gap-2 mb-1.5">
        <span className="flex items-center gap-1.5 font-semibold text-slate-700">
          <Sparkles className="w-3.5 h-3.5 text-blue-600" />
          {t('Anomali analizi', 'Anomaly analysis')}
        </span>
        {job?.state === 'FAILED' ? (
          <button
            type="button"
            onClick={() => void retry()}
            className="flex items-center gap-1 px-2.5 py-1 rounded-lg border border-slate-300 text-slate-700 font-semibold hover:border-blue-400"
          >
            <RotateCcw className="w-3 h-3" />
            {t('Tekrar dene', 'Retry')}
          </button>
        ) : (
          <button
            type="button"
            onClick={() => void start()}
            disabled={busy || !!astronaut.isDisplayOnly}
            title={astronaut.isDisplayOnly ? t('Yalnız gösterim profili', 'Display-only profile') : undefined}
            className="px-2.5 py-1 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {result ? t('Yeniden analiz et', 'Analyze again') : t('Analiz et', 'Analyze')}
          </button>
        )}
      </div>
      {body}
      {error && <p className="mt-1 text-slate-700">{error}</p>}
    </div>
  );
};
