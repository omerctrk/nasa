import React, { useState } from 'react';
import confetti from 'canvas-confetti';
import { ArrowLeft, CheckCircle2, RotateCcw, ChevronRight, FileCheck, Save, Activity, Info, Check, X } from 'lucide-react';
import { useTelemetry } from '../../context/TelemetryContext';
import { DisplayOnlyNotice } from '../common/DisplayOnlyNotice';
import { usePrefs } from '../../context/PreferencesContext';
import { RiskLevel } from '../../types/telemetry';
import { playUiBeep, playSuccessChime, playWarningTone } from '../../utils/audio';

interface SnellenLevel {
  acuity: string;
  fontSize: string;
  letter: string;
  options: string[];
}

// Harf boyutu her adımda küçülür
const SNELLEN_LEVELS: SnellenLevel[] = [
  { acuity: '20/200', fontSize: 'text-8xl font-black', letter: 'E', options: ['E', 'F', 'P', 'B'] },
  { acuity: '20/100', fontSize: 'text-7xl font-extrabold', letter: 'F', options: ['T', 'F', 'P', 'L'] },
  { acuity: '20/70', fontSize: 'text-6xl font-bold', letter: 'T', options: ['T', 'Z', 'O', 'D'] },
  { acuity: '20/50', fontSize: 'text-5xl font-bold', letter: 'L', options: ['E', 'F', 'L', 'P'] },
  { acuity: '20/30', fontSize: 'text-4xl font-bold', letter: 'P', options: ['D', 'P', 'B', 'R'] },
  { acuity: '20/20', fontSize: 'text-2xl font-bold', letter: 'D', options: ['O', 'D', 'C', 'Q'] },
  { acuity: '20/15', fontSize: 'text-lg font-bold', letter: 'Z', options: ['X', 'Z', 'V', 'K'] },
];

/** Doğru cevap sayısından görme keskinliği (ekran ve kayıt aynı fonksiyonu kullanır) */
const acuityFor = (correct: number) =>
  correct >= 7 ? '20/15' : correct >= 6 ? '20/20' : correct >= 5 ? '20/30' : correct >= 4 ? '20/50' : correct >= 3 ? '20/70' : '20/100';

const riskFor = (iop: number): RiskLevel => (iop > 21 ? 'high' : iop > 18 ? 'medium' : 'low');

export const VisionTestPage: React.FC = () => {
  const { setCurrentTab, vitals, astronaut, addVisionTestResult } = useTelemetry();
  const { t } = usePrefs();

  const [idx, setIdx] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const [log, setLog] = useState<{ acuity: string; isCorrect: boolean }[]>([]);
  const [finished, setFinished] = useState(false);
  const [saved, setSaved] = useState(false);

  const level = SNELLEN_LEVELS[idx];
  const progress = Math.round((log.length / SNELLEN_LEVELS.length) * 100);
  const correct = log.filter((a) => a.isCorrect).length;
  const accuracy = log.length ? Math.round((correct / log.length) * 100) : 0;
  const acuity = acuityFor(correct);
  const good = correct >= 6;
  const risk = riskFor(vitals.iop.value);
  const riskText = risk === 'high' ? t('Yüksek', 'High') : risk === 'medium' ? t('Orta', 'Medium') : t('Düşük', 'Low');

  const finish = () => {
    setFinished(true);
    playSuccessChime();
    confetti({ particleCount: 60, spread: 70, origin: { y: 0.6 } });
  };

  const handleSelect = (opt: string) => {
    if (selected) return;
    setSelected(opt);
    const ok = opt === level.letter;
    if (ok) playUiBeep(1040, 0.05);
    else playWarningTone();
    setLog((prev) => [...prev, { acuity: level.acuity, isCorrect: ok }]);

    setTimeout(() => {
      if (idx < SNELLEN_LEVELS.length - 1) {
        setIdx((p) => p + 1);
        setSelected(null);
      } else {
        finish();
      }
    }, 450);
  };

  const handleSave = () => {
    playSuccessChime();
    addVisionTestResult({
      date: { tr: `Gün ${astronaut.solDay} (şimdi)`, en: `Day ${astronaut.solDay} (now)` },
      acuityScore: acuity,
      eyePressureMmHg: vitals.iop.value,
      sansRisk: risk,
      accuracyPercent: accuracy,
    });
    setSaved(true);
  };

  const restart = () => {
    playUiBeep(650);
    setIdx(0);
    setSelected(null);
    setLog([]);
    setFinished(false);
    setSaved(false);
  };

  const back = () => {
    playUiBeep(600);
    setCurrentTab('tests');
  };

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
          onClick={back}
          aria-label={t('Testlere dön', 'Back to tests')}
          className="p-2 rounded-xl bg-white border border-slate-200 text-slate-600 hover:text-blue-600 transition-colors shadow-sm"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{t('Görme Keskinliği Testi', 'Visual Acuity Test')}</h1>
          <p className="text-sm text-slate-500">{astronaut.name}</p>
        </div>
      </div>

      {!finished ? (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          {/* Test alanı */}
          <section className="lg:col-span-2 bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
            <div className="flex items-center justify-between text-sm mb-2">
              <span className="font-bold text-slate-800">
                {t('Adım', 'Step')} {idx + 1} / {SNELLEN_LEVELS.length}
              </span>
              <span className="font-mono text-slate-500">{level.acuity}</span>
            </div>
            <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden mb-5">
              <div className="bg-blue-600 h-full rounded-full transition-all duration-300" style={{ width: `${progress}%` }} />
            </div>

            {/* Göz tablosu: her temada beyaz zemin, siyah harf */}
            <div
              className="rounded-2xl border border-slate-300 flex items-center justify-center min-h-[260px]"
              style={{ backgroundColor: '#ffffff', color: '#0f172a' }}
            >
              <span className={`font-mono select-none tracking-widest ${level.fontSize}`}>{level.letter}</span>
            </div>

            <p className="mt-5 text-center text-sm font-semibold text-slate-700">
              {t('Gördüğünüz harfi seçin', 'Pick the letter you see')}
            </p>
            <div className="mt-3 grid grid-cols-4 gap-3">
              {level.options.map((opt) => {
                const isSel = selected === opt;
                const isTarget = opt === level.letter;
                return (
                  <button
                    key={opt}
                    onClick={() => handleSelect(opt)}
                    disabled={!!selected}
                    className={`py-4 rounded-xl font-mono text-2xl font-bold border-2 transition-all active:scale-95 ${
                      isSel
                        ? isTarget
                          ? 'bg-emerald-600 text-white border-emerald-600'
                          : 'bg-red-600 text-white border-red-600'
                        : 'bg-white hover:bg-blue-50 text-slate-800 border-slate-200 hover:border-blue-400'
                    }`}
                  >
                    {opt}
                  </button>
                );
              })}
            </div>

            <div className="mt-6 pt-4 border-t border-slate-100 flex flex-wrap items-center justify-between gap-3">
              <p className="flex items-start gap-1.5 text-sm text-slate-500">
                <Info className="w-4 h-4 mt-0.5 shrink-0" />
                {t('Ekrandan yaklaşık 60 cm uzakta oturun ve bir gözünüzü kapatın.', 'Sit about 60 cm from the screen and cover one eye.')}
              </p>
              <button
                onClick={finish}
                className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-sm font-semibold transition-colors"
              >
                {t('Testi bitir', 'Finish test')}
              </button>
            </div>
          </section>

          {/* Yan panel */}
          <aside className="space-y-4">
            <section className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
              <h2 className="flex items-center gap-2 text-sm font-bold text-slate-800">
                <Activity className="w-4 h-4 text-sky-600" />
                {t('Güncel göz basıncı', 'Current eye pressure')}
              </h2>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-3xl font-bold font-mono text-slate-900">{vitals.iop.value}</span>
                <span className="text-sm text-slate-500">mmHg</span>
                <span
                  className={`ml-auto px-2 py-0.5 rounded-md border text-xs font-semibold ${
                    vitals.iop.status === 'normal'
                      ? 'bg-emerald-100 text-emerald-800 border-emerald-200'
                      : 'bg-amber-100 text-amber-800 border-amber-300'
                  }`}
                >
                  {vitals.iop.status === 'normal' ? t('Normal', 'Normal') : t('Yüksek', 'Elevated')}
                </span>
              </div>
              <p className="text-sm text-slate-600 leading-relaxed mt-2">
                {t(
                  'Görme skoru ve göz basıncı birlikte değerlendirilerek SANS riski belirlenir.',
                  'Your vision score and eye pressure are combined to estimate SANS risk.'
                )}
              </p>
            </section>

            <section className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
              <h2 className="text-sm font-bold text-slate-800 mb-2">{t('Adımlar', 'Steps')}</h2>
              <ol className="space-y-1.5 text-sm">
                {SNELLEN_LEVELS.map((lvl, i) => {
                  const item = log[i];
                  const isCurrent = i === idx && !item;
                  return (
                    <li
                      key={lvl.acuity}
                      className={`flex items-center justify-between px-3 py-2 rounded-lg border ${
                        isCurrent
                          ? 'bg-blue-50 border-blue-300 font-semibold text-slate-800'
                          : item
                            ? item.isCorrect
                              ? 'bg-emerald-50 border-emerald-200 text-slate-700'
                              : 'bg-red-50 border-red-200 text-slate-700'
                            : 'bg-slate-50 border-slate-100 text-slate-400'
                      }`}
                    >
                      <span className="font-mono">{lvl.acuity}</span>
                      {item ? (
                        item.isCorrect ? (
                          <span className="flex items-center gap-1 text-emerald-700 font-semibold">
                            <Check className="w-4 h-4" /> {t('Doğru', 'Correct')}
                          </span>
                        ) : (
                          <span className="flex items-center gap-1 text-red-700 font-semibold">
                            <X className="w-4 h-4" /> {t('Yanlış', 'Wrong')}
                          </span>
                        )
                      ) : isCurrent ? (
                        <span className="text-blue-700">{t('Şimdi', 'Now')}</span>
                      ) : (
                        <span>—</span>
                      )}
                    </li>
                  );
                })}
              </ol>
            </section>
          </aside>
        </div>
      ) : (
        /* Sonuç */
        <section className="bg-white rounded-2xl border border-slate-200 shadow-lg p-8 max-w-3xl mx-auto space-y-6">
          <div className="text-center">
            <div className="w-16 h-16 rounded-2xl bg-emerald-100 text-emerald-600 flex items-center justify-center mx-auto">
              <FileCheck className="w-8 h-8" />
            </div>
            <h2 className="text-2xl font-bold text-slate-900 mt-3">{t('Test tamamlandı', 'Test complete')}</h2>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 text-center">
              <div className="text-sm text-slate-500">{t('Görme keskinliği', 'Visual acuity')}</div>
              <div className="text-3xl font-extrabold font-mono text-blue-700 mt-1">{acuity}</div>
              <div className={`text-sm font-semibold mt-1 ${good ? 'text-emerald-700' : 'text-amber-700'}`}>
                {good ? t('Uçuş standardında', 'Meets flight standard') : t('Takip önerilir', 'Follow-up advised')}
              </div>
            </div>
            <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 text-center">
              <div className="text-sm text-slate-500">{t('Doğru cevap', 'Correct answers')}</div>
              <div className="text-3xl font-extrabold font-mono text-slate-900 mt-1">
                {correct}/{log.length || SNELLEN_LEVELS.length}
              </div>
              <div className="text-sm text-slate-500 mt-1">{accuracy}%</div>
            </div>
            <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 text-center">
              <div className="text-sm text-slate-500">{t('SANS riski', 'SANS risk')}</div>
              <div
                className={`text-3xl font-extrabold mt-1 ${
                  risk === 'high' ? 'text-red-700' : risk === 'medium' ? 'text-amber-700' : 'text-emerald-700'
                }`}
              >
                {riskText}
              </div>
              <div className="text-sm text-slate-500 mt-1 font-mono">{vitals.iop.value} mmHg</div>
            </div>
          </div>

          <div className={`p-4 rounded-xl border text-sm leading-relaxed ${good && risk === 'low' ? 'bg-emerald-50 border-emerald-200 text-slate-700' : 'bg-amber-50 border-amber-200 text-slate-700'}`}>
            <strong className="block text-slate-900 mb-1">{t('Ne anlama geliyor?', 'What does this mean?')}</strong>
            {good && risk === 'low'
              ? t(
                  'Görmeniz uçuş standardında ve göz basıncınız normal. Haftalık testlere devam edin.',
                  'Your vision meets the flight standard and eye pressure is normal. Keep up with weekly tests.'
                )
              : t(
                  'Sonuç takip gerektiriyor. Testi yarın tekrarlayın; görmede bulanıklık varsa uçuş cerrahınıza bildirin.',
                  'This result needs follow-up. Repeat the test tomorrow, and tell your flight surgeon if your vision is blurry.'
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
                onClick={handleSave}
                disabled={saved}
                className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-bold text-white transition-all ${
                  saved ? 'bg-emerald-600' : 'bg-blue-600 hover:bg-blue-700 shadow-sm'
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
