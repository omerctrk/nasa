import React, { useCallback, useEffect, useRef, useState } from 'react';
import { usePrefs } from '../../../context/PreferencesContext';
import { deviceString, now, randomInt, watchVisibility } from '../timing';
import type { CognitiveTest, PvtTrial } from '../types';
import {
  InvalidNotice,
  InvalidResult,
  ResultStat,
  ShellButton,
  SubmitStatus,
  TestShell,
  useTestSubmission,
} from './TestShell';

/** Test süresi 180 sn. Yalnızca geliştirme sırasında denemek için URL'ye ?pvt_s=30 eklenebilir. */
const PVT_DURATION_S = (() => {
  const n = parseInt(new URLSearchParams(window.location.search).get('pvt_s') ?? '', 10);
  return n >= 10 && n <= 180 ? n : 180;
})();
const PRACTICE_TRIALS = 3;
const NO_RESPONSE_MS = 30_000;
const FEEDBACK_MS = 1_000;
const EARLY_MS = 800;

type Stage = 'instructions' | 'practice' | 'countdown' | 'test' | 'submitting' | 'invalid';
type Input = 'keyboard' | 'touch' | 'mouse';

export const PvtTest: React.FC<{ onClose: () => void; onFinished: (r: CognitiveTest | null) => void }> = ({ onClose, onFinished }) => {
  const { t } = usePrefs();
  const [stage, setStage] = useState<Stage>('instructions');
  const [count, setCount] = useState(3);
  const sub = useTestSubmission();

  const areaRef = useRef<HTMLDivElement>(null);
  const counterRef = useRef<HTMLDivElement>(null);
  const msgRef = useRef<HTMLDivElement>(null);
  const barRef = useRef<HTMLDivElement>(null);

  // Ölçüm motoru: tümü ref'te, React render'ını beklemez
  const e = useRef({
    mode: 'practice' as 'practice' | 'test',
    phase: 'idle' as 'idle' | 'wait' | 'stim' | 'feedback',
    delay: 0,
    shownAt: 0,
    trials: [] as PvtTrial[],
    practiceDone: 0,
    startAt: 0,
    endAt: 0,
    timers: [] as number[],
    raf: 0,
    endTimer: 0,
    barTimer: 0,
    input: null as Input | null,
  }).current;

  const clearTrialTimers = () => {
    e.timers.forEach((id) => window.clearTimeout(id));
    e.timers = [];
    cancelAnimationFrame(e.raf);
  };
  const clearAll = () => {
    clearTrialTimers();
    window.clearTimeout(e.endTimer);
    window.clearInterval(e.barTimer);
    e.phase = 'idle';
  };

  const hideCounter = () => {
    if (counterRef.current) {
      counterRef.current.style.visibility = 'hidden';
      counterRef.current.textContent = '0';
    }
  };
  const setMsg = (txt: string) => {
    if (msgRef.current) msgRef.current.textContent = txt;
  };

  const finish = useCallback(() => {
    clearAll();
    setStage('submitting');
    sub.submit({
      test_type: 'pvt',
      duration_s: PVT_DURATION_S,
      device: deviceString(e.input ?? 'keyboard'),
      trials: e.trials,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sub.submit]);

  const next = () => {
    hideCounter();
    setMsg('');
    if (e.mode === 'practice' && e.practiceDone >= PRACTICE_TRIALS) {
      e.phase = 'idle';
      setStage('countdown');
      return;
    }
    if (e.mode === 'test' && now() >= e.endAt) {
      finish();
      return;
    }
    startWait();
  };

  const record = (rt: number | null, falseStart: boolean) => {
    if (e.mode === 'practice') {
      e.practiceDone += 1;
      return;
    }
    e.trials.push({ i: e.trials.length + 1, delay_ms: e.delay, rt_ms: rt, false_start: falseStart });
  };

  const tick = () => {
    e.raf = requestAnimationFrame(() => {
      if (e.phase !== 'stim' || !counterRef.current) return;
      counterRef.current.textContent = String(Math.floor(now() - e.shownAt));
      tick();
    });
  };

  const showStimulus = () => {
    e.raf = requestAnimationFrame(() => {
      if (counterRef.current) {
        counterRef.current.textContent = '0';
        counterRef.current.style.visibility = 'visible';
      }
      // Uyarıcıyı görünür yapan karede zaman damgası alınır
      e.shownAt = now();
      e.phase = 'stim';
      tick();
      e.timers.push(
        window.setTimeout(() => {
          // 30 sn basılmadı
          cancelAnimationFrame(e.raf);
          record(null, false);
          next();
        }, NO_RESPONSE_MS)
      );
    });
  };

  const startWait = () => {
    e.phase = 'wait';
    e.delay = randomInt(1000, 4000); // tekdüze 1.000–4.000 ms
    if (import.meta.env.DEV) console.debug('[pvt] bekleme', e.delay, 'ms');
    e.timers.push(window.setTimeout(showStimulus, e.delay));
  };

  // Basış: doğrudan DOM olayında, süre hemen hesaplanır
  const press = (source: Input) => {
    const at = now();
    if (e.input === null && e.mode === 'test') e.input = source;
    if (e.phase === 'wait') {
      clearTrialTimers();
      record(null, true);
      e.phase = 'feedback';
      setMsg(t('Çok erken', 'Too early'));
      e.timers.push(window.setTimeout(next, EARLY_MS));
    } else if (e.phase === 'stim') {
      clearTrialTimers();
      const rt = Math.round(at - e.shownAt);
      if (counterRef.current) counterRef.current.textContent = String(rt);
      record(rt, false);
      e.phase = 'feedback';
      e.timers.push(window.setTimeout(next, FEEDBACK_MS));
    }
  };
  const pressRef = useRef(press);
  pressRef.current = press;

  // Alıştırma başlangıcı
  useEffect(() => {
    if (stage !== 'practice') return;
    e.mode = 'practice';
    e.practiceDone = 0;
    hideCounter();
    startWait();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stage]);

  // 3-2-1 geri sayım
  useEffect(() => {
    if (stage !== 'countdown') return;
    setCount(3);
    const ids = [1, 2].map((k) => window.setTimeout(() => setCount(3 - k), k * 1000));
    ids.push(window.setTimeout(() => setStage('test'), 3000));
    return () => ids.forEach((id) => window.clearTimeout(id));
  }, [stage]);

  // Test başlangıcı
  useEffect(() => {
    if (stage !== 'test') return;
    e.mode = 'test';
    e.trials = [];
    e.input = null;
    e.startAt = now();
    e.endAt = e.startAt + PVT_DURATION_S * 1000;
    e.endTimer = window.setTimeout(finish, PVT_DURATION_S * 1000);
    e.barTimer = window.setInterval(() => {
      const left = Math.max(0, 1 - (now() - e.startAt) / (PVT_DURATION_S * 1000));
      if (barRef.current) barRef.current.style.width = `${left * 100}%`;
    }, 250);
    hideCounter();
    startWait();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stage]);

  // Girdi dinleyicileri + sekme değişimi kuralı
  useEffect(() => {
    if (stage !== 'practice' && stage !== 'test' && stage !== 'countdown') return;
    const onKey = (ev: KeyboardEvent) => {
      if (ev.code !== 'Space') return;
      ev.preventDefault();
      if (ev.repeat || stage === 'countdown') return;
      pressRef.current('keyboard');
    };
    const area = areaRef.current;
    const onPointer = (ev: PointerEvent) => {
      if (stage === 'countdown') return;
      pressRef.current(ev.pointerType === 'touch' ? 'touch' : 'mouse');
    };
    window.addEventListener('keydown', onKey);
    area?.addEventListener('pointerdown', onPointer);
    const stopWatch = watchVisibility(() => {
      clearAll();
      setStage('invalid'); // hiçbir şey gönderilmez
    });
    return () => {
      window.removeEventListener('keydown', onKey);
      area?.removeEventListener('pointerdown', onPointer);
      stopWatch();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stage]);

  useEffect(() => () => clearAll(), []); // eslint-disable-line react-hooks/exhaustive-deps

  const restart = () => {
    clearAll();
    sub.reset();
    setStage('instructions');
  };

  const running = stage === 'practice' || stage === 'countdown' || stage === 'test';
  const result = sub.result;

  return (
    <TestShell
      title={t('Tepki testi', 'Reaction test')}
      running={running}
      onClose={() => {
        clearAll();
        onClose();
      }}
    >
      {stage === 'instructions' && (
        <div className="max-w-lg text-center space-y-6">
          <h2 className="text-2xl font-bold">{t('Tepki testi (PVT)', 'Reaction test (PVT)')}</h2>
          <p className="text-lg leading-relaxed" style={{ color: '#cbd5e1' }}>
            {t(
              'Ekranın ortasında sayı belirdiğinde olabildiğince hızlı dokun veya boşluk tuşuna bas. Sayı görünmeden basma. Test 3 dakika sürer.',
              'When a number appears in the middle of the screen, tap or press the space bar as fast as you can. Do not press before the number appears. The test takes 3 minutes.'
            )}
          </p>
          <p className="text-sm" style={{ color: '#94a3b8' }}>
            {t('Önce 3 alıştırma denemesi yapılır; bunlar kaydedilmez.', 'You will first do 3 practice trials; these are not saved.')}
          </p>
          <ShellButton onClick={() => setStage('practice')} autoFocus>
            {t('Başla', 'Start')}
          </ShellButton>
        </div>
      )}

      {(stage === 'practice' || stage === 'test' || stage === 'countdown') && (
        <div className="w-full h-full flex flex-col">
          <div className="h-6 flex items-center justify-center">
            {stage === 'practice' && (
              <span className="px-3 py-0.5 rounded-md text-sm font-semibold" style={{ backgroundColor: '#1e293b', color: '#cbd5e1' }}>
                {t('Alıştırma', 'Practice')}
              </span>
            )}
            {stage === 'test' && (
              <div className="w-full max-w-md h-1 rounded-full overflow-hidden" style={{ backgroundColor: '#1e293b' }} aria-hidden>
                <div ref={barRef} className="h-full" style={{ width: '100%', backgroundColor: '#475569' }} />
              </div>
            )}
          </div>
          <div
            ref={areaRef}
            className="flex-1 min-h-[60vh] flex flex-col items-center justify-center select-none cursor-pointer"
            style={{ touchAction: 'none' }}
            aria-label={t('Dokunma alanı', 'Tap area')}
          >
            {stage === 'countdown' ? (
              <div className="text-center">
                <p className="text-xl mb-4" style={{ color: '#94a3b8' }}>
                  {t('Test başlıyor', 'Test starting')}
                </p>
                <div className="text-8xl font-bold font-mono">{count}</div>
              </div>
            ) : (
              <>
                <div
                  ref={counterRef}
                  className="text-8xl sm:text-9xl font-bold font-mono tabular-nums"
                  style={{ color: '#facc15', visibility: 'hidden' }}
                >
                  0
                </div>
                <div ref={msgRef} className="h-10 mt-4 text-2xl font-semibold" style={{ color: '#e2e8f0' }} aria-live="polite" />
              </>
            )}
          </div>
        </div>
      )}

      {stage === 'invalid' && <InvalidNotice onRestart={restart} />}

      {stage === 'submitting' && (sub.state === 'sending' || sub.state === 'failed') && (
        <SubmitStatus state={sub.state} error={sub.error} onRetry={() => void sub.retry()} />
      )}

      {stage === 'submitting' && sub.state === 'done' && result && !result.valid && (
        <InvalidResult onRestart={restart} onDone={() => onFinished(result)} />
      )}

      {stage === 'submitting' && sub.state === 'done' && result?.valid && (
        <div className="w-full max-w-xl space-y-6 text-center">
          <h2 className="text-2xl font-bold">{t('Test tamamlandı', 'Test complete')}</h2>
          <div className="grid grid-cols-2 gap-3">
            <ResultStat label={t('Ortalama', 'Mean')} value={`${result.mean_rt_ms} ms`} />
            <ResultStat label={t('Medyan', 'Median')} value={`${result.median_rt_ms} ms`} />
            <ResultStat label={t('Dikkat kaybı', 'Lapses')} value={result.lapses} />
            <ResultStat label={t('Erken basma', 'False starts')} value={result.false_starts} />
          </div>
          <ShellButton onClick={() => onFinished(result)}>{t('Bitti', 'Done')}</ShellButton>
        </div>
      )}
    </TestShell>
  );
};
