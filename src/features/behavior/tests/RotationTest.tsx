import React, { useCallback, useEffect, useRef, useState } from 'react';
import { ArrowLeft, ArrowRight } from 'lucide-react';
import { usePrefs } from '../../../context/PreferencesContext';
import { deviceString, now, shuffle, watchVisibility } from '../timing';
import { accuracyPct, type CognitiveTest, type RotationAngle, type RotationTrial, type ShapeId } from '../types';
import { SHAPE_IDS, ShapeSvg } from './shapes';
import {
  InvalidNotice,
  InvalidResult,
  ResultStat,
  ShellButton,
  SubmitStatus,
  TestShell,
  useTestSubmission,
} from './TestShell';

const ANGLES: RotationAngle[] = [0, 60, 120, 180];
const MAX_RT_MS = 7_000;
const BLANK_MS = 500;

type Plan = { shape: ShapeId; angle: RotationAngle; mirror: boolean };
type Stage = 'instructions' | 'practice' | 'test' | 'submitting' | 'invalid';
type Answer = 'same' | 'mirror';

const pickShape = (): ShapeId => SHAPE_IDS[Math.floor(Math.random() * SHAPE_IDS.length)];

/** 4 açı × 2 koşul × 2 tekrar = 16 deneme; açı/koşul dağılımı sabit, sıra ve şekil rastgele */
const buildTestPlan = (): Plan[] =>
  shuffle(ANGLES.flatMap((angle) => [false, true].flatMap((mirror) => [0, 1].map(() => ({ shape: pickShape(), angle, mirror })))));

const buildPracticePlan = (): Plan[] => [
  { shape: pickShape(), angle: 60, mirror: false },
  { shape: pickShape(), angle: 120, mirror: true },
];

export const RotationTest: React.FC<{ onClose: () => void; onFinished: (r: CognitiveTest | null) => void }> = ({ onClose, onFinished }) => {
  const { t } = usePrefs();
  const [stage, setStage] = useState<Stage>('instructions');
  const [plan, setPlan] = useState<Plan[]>([]);
  const [idx, setIdx] = useState(0);
  const [visible, setVisible] = useState(false); // false = 500 ms boş ekran
  const [feedback, setFeedback] = useState<string | null>(null);
  const sub = useTestSubmission();

  const pairRef = useRef<HTMLDivElement>(null);
  const e = useRef({
    shownAt: 0,
    answered: true,
    timers: [] as number[],
    raf: 0,
    trials: [] as RotationTrial[],
    input: null as 'keyboard' | 'touch' | 'mouse' | null,
    startAt: 0,
  }).current;

  const clearTimers = () => {
    e.timers.forEach((id) => window.clearTimeout(id));
    e.timers = [];
    cancelAnimationFrame(e.raf);
  };

  const current = plan[idx];
  const isPractice = stage === 'practice';

  // Denemeyi göster: 500 ms boş ekran → şekiller çizilir → zaman damgası
  useEffect(() => {
    if ((stage !== 'practice' && stage !== 'test') || !current || feedback) return;
    setVisible(false);
    e.answered = true;
    e.timers.push(
      window.setTimeout(() => {
        setVisible(true);
        // Şekillerin çizildiği karede zamanlama başlar
        e.raf = requestAnimationFrame(() => {
          e.raf = requestAnimationFrame(() => {
            e.shownAt = now();
            e.answered = false;
            e.timers.push(window.setTimeout(() => respondRef.current(null, null), MAX_RT_MS));
          });
        });
      }, BLANK_MS)
    );
    return clearTimers;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stage, idx, plan, feedback]);

  const finish = useCallback(() => {
    clearTimers();
    setStage('submitting');
    sub.submit({ test_type: 'rotation', duration_s: Math.round((now() - e.startAt) / 1000), device: deviceString(e.input ?? 'mouse'), trials: e.trials });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sub.submit]);

  const respond = (answer: Answer | null, source: 'keyboard' | 'touch' | 'mouse' | null) => {
    const at = now();
    if (e.answered || !current) return;
    e.answered = true;
    clearTimers();
    const rt = answer === null ? null : Math.round(at - e.shownAt);

    if (isPractice) {
      // Alıştırmada geri bildirim var (kaydedilmez)
      const correct = answer !== null && (answer === 'mirror') === current.mirror;
      setFeedback(
        correct
          ? t('Doğru', 'Correct')
          : current.mirror
            ? t('Yanlış, bu bir ayna görüntüsüydü', 'Wrong, this was a mirror image')
            : t('Yanlış, bu aynı şekildi (yalnızca döndürülmüş)', 'Wrong, this was the same shape (only rotated)')
      );
      return;
    }

    if (source && e.input === null) e.input = source;
    e.trials.push({ i: e.trials.length + 1, shape: current.shape, angle: current.angle, mirror: current.mirror, answer, rt_ms: rt });
    if (idx + 1 >= plan.length) finish();
    else setIdx((i) => i + 1);
  };
  const respondRef = useRef(respond);
  respondRef.current = respond;

  const continueAfterFeedback = () => {
    setFeedback(null);
    if (idx + 1 >= plan.length) {
      // Alıştırma bitti → test
      e.trials = [];
      e.input = null;
      e.startAt = now();
      setPlan(buildTestPlan());
      setIdx(0);
      setStage('test');
    } else {
      setIdx((i) => i + 1);
    }
  };

  // ← Aynı, → Ayna + sekme değişimi kuralı
  useEffect(() => {
    if (stage !== 'practice' && stage !== 'test') return;
    const onKey = (ev: KeyboardEvent) => {
      if (ev.key === 'ArrowLeft') {
        ev.preventDefault();
        respondRef.current('same', 'keyboard');
      } else if (ev.key === 'ArrowRight') {
        ev.preventDefault();
        respondRef.current('mirror', 'keyboard');
      }
    };
    window.addEventListener('keydown', onKey);
    const stop = watchVisibility(() => {
      clearTimers();
      setStage('invalid');
    });
    return () => {
      window.removeEventListener('keydown', onKey);
      stop();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stage]);

  useEffect(() => () => clearTimers(), []); // eslint-disable-line react-hooks/exhaustive-deps

  const startPractice = () => {
    setPlan(buildPracticePlan());
    setIdx(0);
    setFeedback(null);
    setStage('practice');
  };

  const restart = () => {
    clearTimers();
    sub.reset();
    setStage('instructions');
  };

  const answerBtn = (answer: Answer) => (
    <button
      type="button"
      disabled={!visible || !!feedback}
      onPointerDown={(ev) => {
        ev.preventDefault();
        respondRef.current(answer, ev.pointerType === 'touch' ? 'touch' : 'mouse');
      }}
      className="flex-1 min-h-16 rounded-2xl text-xl font-bold flex items-center justify-center gap-3 disabled:opacity-40"
      style={{ backgroundColor: '#1e293b', color: '#f1f5f9', border: '1px solid #334155' }}
    >
      {answer === 'same' ? (
        <>
          <ArrowLeft className="w-5 h-5" />
          {t('Aynı', 'Same')}
        </>
      ) : (
        <>
          {t('Ayna', 'Mirror')}
          <ArrowRight className="w-5 h-5" />
        </>
      )}
    </button>
  );

  const result = sub.result;

  return (
    <TestShell
      title={t('Zihinsel döndürme testi', 'Mental rotation test')}
      running={stage === 'practice' || stage === 'test'}
      onClose={() => {
        clearTimers();
        onClose();
      }}
    >
      {stage === 'instructions' && (
        <div className="max-w-2xl text-center space-y-6">
          <h2 className="text-2xl font-bold">{t('Zihinsel döndürme', 'Mental rotation')}</h2>
          <p className="text-lg leading-relaxed" style={{ color: '#cbd5e1' }}>
            {t(
              'Yan yana iki şekil göreceksin. Sağdaki, soldakinin yalnızca döndürülmüş hali ise "Aynı", ayna görüntüsü ise "Ayna" seç. Yaklaşık 2 dakika sürer.',
              'You will see two shapes side by side. If the right one is just the left one rotated, choose "Same"; if it is a mirror image, choose "Mirror". It takes about 2 minutes.'
            )}
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {[
              { mirror: false, label: t('Aynı — yalnızca döndürülmüş', 'Same — only rotated') },
              { mirror: true, label: t('Ayna — yansıtılmış ve döndürülmüş', 'Mirror — flipped and rotated') },
            ].map((ex) => (
              <figure key={String(ex.mirror)} className="p-4 rounded-2xl" style={{ backgroundColor: '#0f172a', border: '1px solid #1e293b' }}>
                <div className="flex items-center justify-center gap-2">
                  <ShapeSvg shape="s1" size={110} />
                  <ShapeSvg shape="s1" angle={120} mirror={ex.mirror} size={110} />
                </div>
                <figcaption className="mt-2 text-sm font-semibold">{ex.label}</figcaption>
              </figure>
            ))}
          </div>
          <p className="text-sm" style={{ color: '#94a3b8' }}>
            {t('Klavyede ← Aynı, → Ayna. Önce 2 alıştırma denemesi yapılır.', 'Keyboard: ← Same, → Mirror. You will first do 2 practice trials.')}
          </p>
          <ShellButton onClick={startPractice} autoFocus>
            {t('Başla', 'Start')}
          </ShellButton>
        </div>
      )}

      {(stage === 'practice' || stage === 'test') && current && (
        <div className="w-full max-w-3xl flex flex-col items-center gap-8">
          <div className="h-6 text-sm" style={{ color: '#94a3b8' }}>
            {isPractice ? (
              <span className="px-3 py-0.5 rounded-md font-semibold" style={{ backgroundColor: '#1e293b', color: '#cbd5e1' }}>
                {t('Alıştırma', 'Practice')}
              </span>
            ) : (
              <span className="font-mono">
                {idx + 1} / {plan.length}
              </span>
            )}
          </div>

          <div ref={pairRef} className="flex items-center justify-center gap-6 sm:gap-16 min-h-[240px]" style={{ visibility: visible ? 'visible' : 'hidden' }}>
            <ShapeSvg shape={current.shape} size={220} />
            <ShapeSvg shape={current.shape} angle={current.angle} mirror={current.mirror} size={220} />
          </div>

          {feedback ? (
            <div className="text-center space-y-4" aria-live="polite">
              <p className="text-xl font-semibold">{feedback}</p>
              <ShellButton onClick={continueAfterFeedback} autoFocus>
                {t('Devam', 'Continue')}
              </ShellButton>
            </div>
          ) : (
            <div className="w-full flex gap-4">
              {answerBtn('same')}
              {answerBtn('mirror')}
            </div>
          )}
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
            <ResultStat label={t('Doğruluk', 'Accuracy')} value={`${accuracyPct(result.accuracy)}%`} />
            <ResultStat label={t('Ortalama süre', 'Mean time')} value={result.mean_rt_ms !== null ? `${result.mean_rt_ms} ms` : '—'} />
          </div>
          <ShellButton onClick={() => onFinished(result)}>{t('Bitti', 'Done')}</ShellButton>
        </div>
      )}
    </TestShell>
  );
};
