import React, { useState, useEffect, useRef } from 'react';
import confetti from 'canvas-confetti';
import { Brain, Zap, ArrowLeft, Timer, CheckCircle2, XCircle, RotateCcw, ChevronRight, Save, Layers, Info, AlertTriangle } from 'lucide-react';
import { useTelemetry } from '../../context/TelemetryContext';
import { DisplayOnlyNotice } from '../common/DisplayOnlyNotice';
import { usePrefs } from '../../context/PreferencesContext';
import { playUiBeep, playSuccessChime, playWarningTone, playCueBeep } from '../../utils/audio';

type Mode = 'reaction' | 'memory' | 'attention';
type ReactionState = 'idle' | 'waiting' | 'ready' | 'too_early' | 'round_complete';

const ROUNDS = 5;

export const CognitiveTestPage: React.FC = () => {
  const { setCurrentTab, astronaut, addCognitiveTestResult } = useTelemetry();
  const { t } = usePrefs();

  const [mode, setMode] = useState<Mode>('reaction');

  // Reaksiyon
  const [reactionState, setReactionState] = useState<ReactionState>('idle');
  const [trials, setTrials] = useState<number[]>([]);
  const [falseStarts, setFalseStarts] = useState(0);
  const [lastTime, setLastTime] = useState<number | null>(null);
  const startRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Hafıza
  const [sequence, setSequence] = useState<number[]>([]);
  const [userSeq, setUserSeq] = useState<number[]>([]);
  const [showing, setShowing] = useState(false);
  const [activeTile, setActiveTile] = useState<number | null>(null);
  const [memoryLevel, setMemoryLevel] = useState(3);
  const [memoryScore, setMemoryScore] = useState(0);
  const [memoryMsg, setMemoryMsg] = useState<{ ok: boolean; text: string } | null>(null);

  // Dikkat (Stroop)
  const COLORS = [
    { name: t('KIRMIZI', 'RED'), cls: 'text-red-600' },
    { name: t('MAVİ', 'BLUE'), cls: 'text-blue-600' },
    { name: t('YEŞİL', 'GREEN'), cls: 'text-emerald-600' },
    { name: t('SARI', 'YELLOW'), cls: 'text-amber-500' },
  ];
  const [question, setQuestion] = useState<{ word: number; color: number } | null>(null);
  const [attention, setAttention] = useState({ correct: 0, wrong: 0 });

  const [finished, setFinished] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => () => {
    if (timerRef.current) clearTimeout(timerRef.current);
  }, []);

  // --- Reaksiyon ---
  const startRound = () => {
    playUiBeep(700);
    setReactionState('waiting');
    setLastTime(null);
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      setReactionState('ready');
      startRef.current = performance.now();
      playCueBeep();
    }, Math.floor(Math.random() * 2400) + 1800);
  };

  const handleReactionClick = () => {
    if (reactionState === 'waiting') {
      if (timerRef.current) clearTimeout(timerRef.current);
      playWarningTone();
      setReactionState('too_early');
      setFalseStarts((p) => p + 1);
    } else if (reactionState === 'ready') {
      const ms = Math.round(performance.now() - startRef.current);
      playUiBeep(1100, 0.05);
      setLastTime(ms);
      setTrials((p) => [...p, ms]);
      setReactionState('round_complete');
    } else if (reactionState === 'idle' || reactionState === 'too_early' || reactionState === 'round_complete') {
      if (trials.length < ROUNDS) startRound();
    }
  };

  // --- Hafıza ---
  const startMemory = () => {
    playUiBeep(800);
    setMemoryMsg(null);
    const seq = Array.from({ length: memoryLevel }, () => Math.floor(Math.random() * 9));
    setSequence(seq);
    setUserSeq([]);
    setShowing(true);
    seq.forEach((tile, step) => {
      setTimeout(() => {
        setActiveTile(tile);
        playUiBeep(600 + tile * 60, 0.1);
        setTimeout(() => setActiveTile(null), 400);
      }, (step + 1) * 750);
    });
    setTimeout(() => setShowing(false), (seq.length + 1) * 750);
  };

  const handleTile = (i: number) => {
    if (showing || sequence.length === 0) return;
    playUiBeep(600 + i * 60, 0.08);
    const next = [...userSeq, i];
    setUserSeq(next);

    if (next[next.length - 1] !== sequence[next.length - 1]) {
      playWarningTone();
      setMemoryMsg({ ok: false, text: t('Sıra hatalı. 3 kareden yeniden başlayın.', 'Wrong order. Start again from 3 tiles.') });
      setMemoryLevel(3);
      setSequence([]);
      setUserSeq([]);
      return;
    }
    if (next.length === sequence.length) {
      playSuccessChime();
      setMemoryScore((p) => p + 1);
      setMemoryMsg({
        ok: true,
        text: t(`Harika! ${sequence.length} kare doğru. Sonraki tur: ${Math.min(8, sequence.length + 1)} kare.`, `Great! ${sequence.length} tiles correct. Next round: ${Math.min(8, sequence.length + 1)} tiles.`),
      });
      setMemoryLevel((p) => Math.min(8, p + 1));
      setSequence([]);
    }
  };

  // --- Dikkat ---
  const nextQuestion = () =>
    setQuestion({ word: Math.floor(Math.random() * 4), color: Math.floor(Math.random() * 4) });

  useEffect(() => {
    if (mode === 'attention' && !question) nextQuestion();
  }, [mode, question]);

  const answer = (saysMatch: boolean) => {
    if (!question) return;
    const ok = saysMatch === (question.word === question.color);
    if (ok) playUiBeep(1100, 0.04);
    else playWarningTone();
    setAttention((p) => (ok ? { ...p, correct: p.correct + 1 } : { ...p, wrong: p.wrong + 1 }));
    nextQuestion();
  };

  // --- Sonuç hesaplama ---
  const avgMs = trials.length ? Math.round(trials.reduce((a, b) => a + b, 0) / trials.length) : null;
  const bestMs = trials.length ? Math.min(...trials) : null;
  const attnTotal = attention.correct + attention.wrong;
  const attnPct = attnTotal ? Math.round((attention.correct / attnTotal) * 100) : null;
  const totalCorrect = trials.length + memoryScore + attention.correct;
  const totalWrong = falseStarts + attention.wrong;
  const accuracy = Math.round((totalCorrect / Math.max(1, totalCorrect + totalWrong)) * 100);
  const fatigue = avgMs ? Math.max(5, Math.min(60, Math.round((avgMs - 200) * 0.25 + falseStarts * 3))) : null;

  const verdict =
    avgMs === null
      ? { level: 'none' as const, text: t('Yeterli veri yok', 'Not enough data') }
      : avgMs < 250 && accuracy >= 85
        ? { level: 'good' as const, text: t('Göreve hazır', 'Mission-ready') }
        : avgMs < 320 && accuracy >= 70
          ? { level: 'ok' as const, text: t('Dinlenme önerilir', 'Rest recommended') }
          : { level: 'low' as const, text: t('Kritik görevleri erteleyin', 'Postpone critical tasks') };

  const finish = () => {
    setFinished(true);
    playSuccessChime();
    if (verdict.level === 'good') confetti({ particleCount: 70, spread: 80, origin: { y: 0.6 } });
  };

  const save = () => {
    if (avgMs === null) return;
    playSuccessChime();
    addCognitiveTestResult({
      date: { tr: `Gün ${astronaut.solDay} (şimdi)`, en: `Day ${astronaut.solDay} (now)` },
      reactionTimeMs: avgMs,
      accuracyPercent: accuracy,
      memoryLevel,
      fatigueIndexPercent: fatigue ?? 0,
      readinessLevel: {
        tr: verdict.level === 'good' ? 'Göreve hazır' : verdict.level === 'ok' ? 'Dinlenme önerilir' : 'Kritik görev ertelenmeli',
        en: verdict.level === 'good' ? 'Mission-ready' : verdict.level === 'ok' ? 'Rest recommended' : 'Postpone critical tasks',
      },
    });
    setSaved(true);
  };

  const restart = () => {
    playUiBeep(650);
    setFinished(false);
    setTrials([]);
    setFalseStarts(0);
    setReactionState('idle');
    setMemoryLevel(3);
    setMemoryScore(0);
    setMemoryMsg(null);
    setAttention({ correct: 0, wrong: 0 });
    setSaved(false);
  };

  const tabs: { id: Mode; icon: React.ReactNode; label: string; count: string; active: string }[] = [
    { id: 'reaction', icon: <Zap className="w-4 h-4" />, label: t('Reaksiyon', 'Reaction'), count: `${trials.length}/${ROUNDS}`, active: 'bg-blue-600' },
    { id: 'memory', icon: <Layers className="w-4 h-4" />, label: t('Hafıza', 'Memory'), count: `${memoryScore}`, active: 'bg-indigo-600' },
    { id: 'attention', icon: <Brain className="w-4 h-4" />, label: t('Dikkat', 'Attention'), count: `${attnTotal}`, active: 'bg-purple-600' },
  ];

  const verdictCls =
    verdict.level === 'good'
      ? 'bg-emerald-50 border-emerald-300 text-emerald-800'
      : verdict.level === 'ok'
        ? 'bg-amber-50 border-amber-300 text-amber-800'
        : verdict.level === 'low'
          ? 'bg-red-50 border-red-300 text-red-800'
          : 'bg-slate-50 border-slate-200 text-slate-700';

  if (astronaut.isDisplayOnly) {
    return (
      <div className="w-full max-w-5xl mx-auto pb-12">
        <DisplayOnlyNotice />
      </div>
    );
  }

  return (
    <div className="w-full max-w-5xl mx-auto space-y-6 pb-12 animate-fadeIn">
      <div className="flex items-center gap-3">
        <button
          onClick={() => {
            playUiBeep(600);
            setCurrentTab('tests');
          }}
          aria-label={t('Testlere dön', 'Back to tests')}
          className="p-2 rounded-xl bg-white border border-slate-200 text-slate-600 hover:text-indigo-600 transition-colors shadow-sm"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{t('Refleks & Bilişsel Test', 'Reflex & Cognitive Test')}</h1>
          <p className="text-sm text-slate-500">
            {t('3 kısa bölüm: reaksiyon, hafıza ve dikkat', '3 short parts: reaction, memory and attention')}
          </p>
        </div>
      </div>

      {!finished ? (
        <div className="space-y-5">
          {/* Bölüm seçici */}
          <div role="tablist" className="grid grid-cols-3 gap-1.5 p-1.5 bg-white rounded-2xl border border-slate-200 shadow-sm">
            {tabs.map((tab, i) => (
              <button
                key={tab.id}
                role="tab"
                aria-selected={mode === tab.id}
                onClick={() => {
                  playUiBeep(700);
                  setMode(tab.id);
                }}
                className={`py-2.5 px-3 rounded-xl text-sm font-bold flex items-center justify-center gap-2 transition-all ${
                  mode === tab.id ? `${tab.active} text-white shadow-sm` : 'text-slate-600 hover:bg-slate-100'
                }`}
              >
                <span className="hidden sm:inline text-xs opacity-70">{i + 1}.</span>
                {tab.icon}
                <span>{tab.label}</span>
                <span className="font-mono text-xs opacity-80">({tab.count})</span>
              </button>
            ))}
          </div>

          {/* 1. Reaksiyon */}
          {mode === 'reaction' && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
              <section className="lg:col-span-2 bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
                <button
                  type="button"
                  onClick={handleReactionClick}
                  className={`w-full min-h-[300px] rounded-2xl border-2 flex flex-col items-center justify-center p-8 select-none transition-all duration-150 ${
                    reactionState === 'waiting'
                      ? 'bg-amber-50 border-amber-300'
                      : reactionState === 'ready'
                        ? 'bg-emerald-500 border-emerald-400 shadow-2xl'
                        : reactionState === 'too_early'
                          ? 'bg-red-50 border-red-300'
                          : 'bg-slate-50 border-slate-300 hover:border-blue-400'
                  }`}
                >
                  {reactionState === 'idle' && (
                    <div className="text-center space-y-3">
                      <div className="w-16 h-16 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center mx-auto">
                        <Zap className="w-8 h-8" />
                      </div>
                      <h2 className="text-xl font-bold text-slate-900">{t('Başlamak için tıklayın', 'Click to start')}</h2>
                      <p className="text-sm text-slate-600 max-w-md mx-auto">
                        {t(
                          'Kutu yeşile döndüğü anda olabildiğince hızlı tıklayın. Sarı bekleme sırasında tıklamayın.',
                          'Click as fast as you can the moment the box turns green. Do not click while it is yellow.'
                        )}
                      </p>
                    </div>
                  )}
                  {reactionState === 'waiting' && (
                    <div className="text-center space-y-2">
                      <div className="w-12 h-12 rounded-full border-4 border-amber-500 border-t-transparent animate-spin mx-auto" />
                      <h2 className="text-3xl font-black text-amber-700">{t('Bekleyin…', 'Wait…')}</h2>
                    </div>
                  )}
                  {reactionState === 'ready' && (
                    <h2 className="text-5xl font-black text-white tracking-wide">{t('TIKLA!', 'CLICK!')}</h2>
                  )}
                  {reactionState === 'too_early' && (
                    <div className="text-center space-y-2">
                      <XCircle className="w-12 h-12 text-red-500 mx-auto" />
                      <h2 className="text-xl font-bold text-red-700">{t('Çok erken!', 'Too early!')}</h2>
                      <p className="text-sm text-slate-600">{t('Tekrar denemek için tıklayın.', 'Click to try again.')}</p>
                    </div>
                  )}
                  {reactionState === 'round_complete' && (
                    <div className="text-center space-y-2">
                      <Timer className="w-8 h-8 text-blue-600 mx-auto" />
                      <div className="text-5xl font-black font-mono text-blue-700">{lastTime} ms</div>
                      <p className="text-sm text-slate-600">
                        {lastTime && lastTime < 250
                          ? t('Çok iyi refleks', 'Excellent reflex')
                          : lastTime && lastTime < 320
                            ? t('Normal refleks', 'Normal reflex')
                            : t('Yavaş — yorgun olabilirsiniz', 'Slow — you may be tired')}
                      </p>
                      <p className="text-sm font-semibold text-slate-700">
                        {trials.length < ROUNDS
                          ? t('Sonraki tur için tıklayın', 'Click for the next round')
                          : t('Reaksiyon bölümü tamamlandı', 'Reaction part complete')}
                      </p>
                    </div>
                  )}
                </button>

                <div className="mt-4 flex items-center justify-between text-sm">
                  <span className="text-slate-500">
                    {t('Erken tıklama', 'Early clicks')}: <strong className="text-red-600">{falseStarts}</strong>
                  </span>
                  {trials.length >= ROUNDS && (
                    <button
                      onClick={() => setMode('memory')}
                      className="flex items-center gap-1 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-sm font-bold transition-colors"
                    >
                      {t('Sonraki bölüm', 'Next part')} <ChevronRight className="w-4 h-4" />
                    </button>
                  )}
                </div>
              </section>

              <aside className="space-y-4">
                <section className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
                  <h2 className="text-sm font-bold text-slate-800 mb-2">{t('Turlar', 'Rounds')}</h2>
                  <ol className="space-y-1.5">
                    {Array.from({ length: ROUNDS }, (_, i) => (
                      <li key={i} className="flex items-center justify-between px-3 py-2 rounded-lg bg-slate-50 border border-slate-100 text-sm">
                        <span className="text-slate-500">
                          {t('Tur', 'Round')} {i + 1}
                        </span>
                        <span className={`font-mono font-bold ${trials[i] ? 'text-blue-700' : 'text-slate-400'}`}>
                          {trials[i] ? `${trials[i]} ms` : '—'}
                        </span>
                      </li>
                    ))}
                  </ol>
                  <div className="mt-3 pt-3 border-t border-slate-100 flex items-center justify-between text-sm">
                    <span className="text-slate-500">{t('Ortalama', 'Average')}</span>
                    <span className="text-lg font-bold font-mono text-slate-900">{avgMs ?? '—'} {avgMs ? 'ms' : ''}</span>
                  </div>
                </section>
                <p className="flex items-start gap-2 p-4 bg-sky-50 rounded-2xl border border-sky-200 text-sm text-slate-700 leading-relaxed">
                  <Info className="w-4 h-4 mt-0.5 shrink-0 text-sky-600" />
                  {t(
                    'Kenetlenme ve robotik kol gibi kritik görevler için tepki süresinin 250 ms altında olması hedeflenir.',
                    'For critical tasks like docking or robotic arm operations, the target reaction time is under 250 ms.'
                  )}
                </p>
              </aside>
            </div>
          )}

          {/* 2. Hafıza */}
          {mode === 'memory' && (
            <section className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm max-w-2xl mx-auto space-y-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="text-lg font-bold text-slate-900">{t('Sıralı hafıza', 'Sequence memory')}</h2>
                  <p className="text-sm text-slate-600 mt-0.5">
                    {t('Yanan kareleri izleyin, sonra aynı sırayla tıklayın.', 'Watch the tiles light up, then click them in the same order.')}
                  </p>
                </div>
                <span className="text-sm font-mono font-bold text-indigo-700 bg-indigo-50 px-2.5 py-1 rounded-lg border border-indigo-200 whitespace-nowrap">
                  {memoryLevel} {t('kare', 'tiles')}
                </span>
              </div>

              <div className="grid grid-cols-3 gap-3 w-fit mx-auto p-4 rounded-2xl" style={{ backgroundColor: '#0f172a' }}>
                {Array.from({ length: 9 }, (_, i) => (
                  <button
                    key={i}
                    onClick={() => handleTile(i)}
                    disabled={showing}
                    aria-label={`${t('Kare', 'Tile')} ${i + 1}`}
                    className="w-20 h-20 rounded-xl transition-all duration-150 active:scale-95 border-2"
                    style={
                      activeTile === i
                        ? { backgroundColor: '#22d3ee', borderColor: '#ffffff', boxShadow: '0 0 20px rgba(34,211,238,0.6)' }
                        : { backgroundColor: '#1e293b', borderColor: '#334155' }
                    }
                  />
                ))}
              </div>

              {memoryMsg && (
                <div
                  role="status"
                  className={`flex items-center gap-2 p-3 rounded-xl border text-sm font-medium ${
                    memoryMsg.ok ? 'bg-emerald-50 border-emerald-200 text-emerald-800' : 'bg-red-50 border-red-200 text-red-800'
                  }`}
                >
                  {memoryMsg.ok ? <CheckCircle2 className="w-4 h-4" /> : <AlertTriangle className="w-4 h-4" />}
                  {memoryMsg.text}
                </div>
              )}

              <div className="flex items-center justify-between pt-4 border-t border-slate-100">
                <span className="text-sm text-slate-500">
                  {showing
                    ? t('İzleyin…', 'Watch…')
                    : sequence.length
                      ? t(`Sıranızı girin (${userSeq.length}/${sequence.length})`, `Enter the sequence (${userSeq.length}/${sequence.length})`)
                      : t('Hazır olduğunuzda başlatın', 'Start when ready')}
                </span>
                <div className="flex gap-2">
                  {memoryScore > 0 && (
                    <button
                      onClick={() => setMode('attention')}
                      className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-sm font-semibold transition-colors"
                    >
                      {t('Sonraki bölüm', 'Next part')}
                    </button>
                  )}
                  <button
                    onClick={startMemory}
                    disabled={showing}
                    className="px-5 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-xl text-sm font-bold shadow-sm transition-all"
                  >
                    {sequence.length ? t('Tekrar göster', 'Show again') : t('Başlat', 'Start')}
                  </button>
                </div>
              </div>
            </section>
          )}

          {/* 3. Dikkat */}
          {mode === 'attention' && question && (
            <section className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm max-w-xl mx-auto space-y-5 text-center">
              <div>
                <h2 className="text-lg font-bold text-slate-900">{t('Renk–kelime dikkati', 'Color–word attention')}</h2>
                <p className="text-sm text-slate-600 mt-1">
                  {t('Kelimenin ', 'Does the ')}
                  <strong>{t('anlamı', 'meaning')}</strong>
                  {t(' ile ', ' of the word match the ')}
                  <strong>{t('rengi', 'color')}</strong>
                  {t(' aynı mı?', ' it is written in?')}
                </p>
              </div>

              <div className="p-10 rounded-2xl border border-slate-200" style={{ backgroundColor: '#f8fafc' }}>
                <div className={`text-5xl font-black tracking-wider ${COLORS[question.color].cls}`}>{COLORS[question.word].name}</div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <button
                  onClick={() => answer(true)}
                  className="py-4 bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-base rounded-xl shadow-sm transition-all flex items-center justify-center gap-2"
                >
                  <CheckCircle2 className="w-5 h-5" />
                  {t('Evet, aynı', 'Yes, match')}
                </button>
                <button
                  onClick={() => answer(false)}
                  className="py-4 bg-red-600 hover:bg-red-700 text-white font-bold text-base rounded-xl shadow-sm transition-all flex items-center justify-center gap-2"
                >
                  <XCircle className="w-5 h-5" />
                  {t('Hayır, farklı', 'No, different')}
                </button>
              </div>

              <div className="flex items-center justify-center gap-6 text-sm text-slate-600">
                <span>
                  {t('Doğru', 'Correct')}: <strong className="text-emerald-700">{attention.correct}</strong>
                </span>
                <span>
                  {t('Yanlış', 'Wrong')}: <strong className="text-red-700">{attention.wrong}</strong>
                </span>
              </div>
            </section>
          )}

          <div className="flex flex-col items-center gap-2 pt-2">
            <button
              onClick={finish}
              disabled={trials.length === 0}
              className="flex items-center gap-2 px-6 py-3 bg-slate-800 hover:bg-slate-900 disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-xl text-sm font-bold shadow-lg transition-all"
            >
              <CheckCircle2 className="w-4 h-4" />
              {t('Testi bitir ve sonucu gör', 'Finish and see results')}
            </button>
            {trials.length === 0 && (
              <span className="text-xs text-slate-500">{t('En az bir reaksiyon turu gerekli', 'At least one reaction round is required')}</span>
            )}
          </div>
        </div>
      ) : (
        /* Sonuç */
        <section className="bg-white rounded-2xl border border-slate-200 shadow-xl p-8 max-w-3xl mx-auto space-y-6">
          <div className="text-center">
            <div className="w-16 h-16 rounded-2xl bg-indigo-100 text-indigo-600 flex items-center justify-center mx-auto">
              <Brain className="w-8 h-8" />
            </div>
            <h2 className="text-2xl font-bold text-slate-900 mt-3">{t('Test sonucu', 'Test result')}</h2>
          </div>

          <div className={`p-5 rounded-2xl border-2 text-center ${verdictCls}`}>
            <div className="text-sm font-semibold opacity-80">{t('Genel değerlendirme', 'Overall assessment')}</div>
            <div className="text-2xl font-bold mt-1">{verdict.text}</div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[
              { k: t('Ort. tepki', 'Avg. reaction'), v: avgMs ? `${avgMs} ms` : '—', s: bestMs ? `${t('En iyi', 'Best')}: ${bestMs} ms` : '' },
              { k: t('Doğruluk', 'Accuracy'), v: `${accuracy}%`, s: `${totalCorrect} ${t('doğru', 'correct')} / ${totalWrong} ${t('hata', 'errors')}` },
              { k: t('Hafıza', 'Memory'), v: `${memoryScore}`, s: t('tamamlanan tur', 'rounds passed') },
              { k: t('Dikkat', 'Attention'), v: attnPct !== null ? `${attnPct}%` : '—', s: `${attnTotal} ${t('soru', 'questions')}` },
            ].map((c) => (
              <div key={c.k} className="p-4 bg-slate-50 rounded-xl border border-slate-200 text-center">
                <div className="text-sm text-slate-500">{c.k}</div>
                <div className="text-2xl font-bold font-mono text-slate-900 mt-1">{c.v}</div>
                <div className="text-xs text-slate-500 mt-0.5">{c.s}</div>
              </div>
            ))}
          </div>

          <div className="p-4 rounded-xl border border-slate-200 bg-slate-50 text-sm text-slate-700 leading-relaxed">
            <strong className="block text-slate-900 mb-1">{t('Ne yapmalıyım?', 'What should I do?')}</strong>
            {verdict.level === 'good'
              ? t('Sonuçlarınız iyi. Normal görev programınıza devam edebilirsiniz.', 'Your results are good. You can continue your normal schedule.')
              : verdict.level === 'ok'
                ? t(
                    'Hafif yorgunluk belirtileri var. Kritik bir görevden önce kısa bir mola verin ve su için.',
                    'There are mild signs of fatigue. Take a short break and drink water before any critical task.'
                  )
                : t(
                    'Tepki süreniz veya doğruluğunuz düşük. Kritik görevleri erteleyin, dinlenin ve testi tekrarlayın. Devam ederse uçuş cerrahına bildirin.',
                    'Your reaction time or accuracy is low. Postpone critical tasks, rest, and retake the test. If it persists, tell the flight surgeon.'
                  )}
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 pt-4 border-t border-slate-100">
            <button
              onClick={restart}
              className="flex items-center gap-2 px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-sm font-semibold transition-colors"
            >
              <RotateCcw className="w-4 h-4" />
              {t('Tekrarla', 'Retake')}
            </button>
            <div className="flex items-center gap-2">
              <button
                onClick={save}
                disabled={saved || avgMs === null}
                className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-bold text-white transition-all disabled:opacity-60 ${
                  saved ? 'bg-emerald-600' : 'bg-indigo-600 hover:bg-indigo-700 shadow-sm'
                }`}
              >
                {saved ? <CheckCircle2 className="w-4 h-4" /> : <Save className="w-4 h-4" />}
                {saved ? t('Kaydedildi', 'Saved') : t('Sonucu kaydet', 'Save result')}
              </button>
              <button
                onClick={() => {
                  playUiBeep(700);
                  setCurrentTab('dashboard');
                }}
                className="flex items-center gap-1.5 px-4 py-2 bg-slate-800 hover:bg-slate-900 text-white rounded-xl text-sm font-bold transition-colors"
              >
                {t('Ana panel', 'Dashboard')}
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        </section>
      )}
    </div>
  );
};
