import React, { useCallback, useEffect, useState } from 'react';
import { ArrowLeft, ArrowUp, ArrowDown, ArrowRight, Eye, Info, RotateCcw, CheckCircle2 } from 'lucide-react';
import { useTelemetry } from '../../context/TelemetryContext';
import { usePrefs } from '../../context/PreferencesContext';
import { DisplayOnlyNotice } from '../common/DisplayOnlyNotice';
import { Button, PageHeader } from '../ui';
import { playUiBeep } from '../../utils/audio';

/**
 * SANS göz taraması — YALNIZ ARAYÜZ.
 *
 * NASA'nın SANS (uzay uçuşuna bağlı nöro-oküler sendrom) takibinde kullanılan üç kısa test,
 * her göz için ayrı: yakın görme keskinliği (dönen E), kontrast duyarlılığı ve Amsler ızgarası.
 * Backend'e hiçbir şey gönderilmez; sonuç yalnız bu cihazda (son tarama özeti) tutulur.
 * Tıbbi tanı değildir: ekran mesafesi ve parlaklık kontrol edilmediği için değerler yaklaşıktır.
 */

type Dir = 'up' | 'right' | 'down' | 'left';
type EyeId = 'OD' | 'OS';
type Step = 'intro' | 'cover' | 'acuity' | 'contrast' | 'amsler' | 'summary';

interface EyeResult {
  acuity: string | null; // ör. "20/40"; hiç görülemediyse null
  contrastPct: number | null; // görülebilen en düşük kontrast (%)
  amslerCells: number; // bozuk/eksik işaretlenen kare sayısı
}

const DIRS: Dir[] = ['up', 'right', 'down', 'left'];
const ROT: Record<Dir, number> = { right: 0, down: 90, left: 180, up: 270 };

/** Yakın görme: E boyutu küçülür (yaklaşık Snellen eşdeğeri, ~40 cm) */
const ACUITY_LEVELS = [
  { px: 72, label: '20/200' },
  { px: 52, label: '20/100' },
  { px: 38, label: '20/70' },
  { px: 28, label: '20/50' },
  { px: 21, label: '20/40' },
  { px: 16, label: '20/30' },
  { px: 12, label: '20/20' },
];
/** Kontrast: sabit boyutta E, giderek soluklaşır (Pelli-Robson benzeri) */
const CONTRAST_LEVELS = [100, 50, 25, 12.5, 6, 3, 1.5];

const STORE_KEY = 'ahms-eye-last';
export const readLastEyeScreening = (): { day: number; od: EyeResult; os: EyeResult } | null => {
  try {
    const raw = localStorage.getItem(STORE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
};

const randomDir = (not?: Dir) => {
  const pool = DIRS.filter((d) => d !== not);
  return pool[Math.floor(Math.random() * pool.length)];
};

/** Dönen E: 5×5 ızgarada çizilir, yönü E'nin açık tarafıdır */
const TumblingE: React.FC<{ dir: Dir; size: number; contrast?: number }> = ({ dir, size, contrast = 100 }) => {
  const g = Math.round(255 * (1 - contrast / 100));
  const fill = `rgb(${g},${g},${g})`;
  return (
    <svg width={size} height={size} viewBox="0 0 5 5" style={{ transform: `rotate(${ROT[dir]}deg)` }} aria-hidden shapeRendering="crispEdges">
      <rect x="0" y="0" width="1" height="5" fill={fill} />
      <rect x="0" y="0" width="5" height="1" fill={fill} />
      <rect x="0" y="2" width="5" height="1" fill={fill} />
      <rect x="0" y="4" width="5" height="1" fill={fill} />
    </svg>
  );
};

/** Gerçek bir göz tablosu gibi: temadan bağımsız, sabit beyaz yüzey */
const ChartSurface: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div className="rounded-2xl border border-slate-300 flex items-center justify-center min-h-[300px] p-6" style={{ backgroundColor: '#ffffff' }}>
    {children}
  </div>
);

const DirectionPad: React.FC<{ onPick: (d: Dir) => void; disabled?: boolean }> = ({ onPick, disabled }) => {
  const { t } = usePrefs();
  const btn = (d: Dir, icon: React.ReactNode, label: string) => (
    <button
      type="button"
      disabled={disabled}
      onClick={() => onPick(d)}
      aria-label={label}
      className="w-14 h-14 rounded-xl bg-white border border-slate-300 text-slate-800 flex items-center justify-center hover:border-blue-400 disabled:opacity-40"
    >
      {icon}
    </button>
  );
  return (
    <div className="grid grid-cols-3 gap-2 w-fit mx-auto">
      <span />
      {btn('up', <ArrowUp className="w-6 h-6" />, t('Yukarı', 'Up'))}
      <span />
      {btn('left', <ArrowLeft className="w-6 h-6" />, t('Sola', 'Left'))}
      <span />
      {btn('right', <ArrowRight className="w-6 h-6" />, t('Sağa', 'Right'))}
      <span />
      {btn('down', <ArrowDown className="w-6 h-6" />, t('Aşağı', 'Down'))}
      <span />
    </div>
  );
};

/**
 * Basamaklı eşik testi: her seviyede E gösterilir; yanlışta aynı seviyede bir şans daha,
 * iki yanlışta durulur. Sonuç: doğru görülen son seviye.
 */
const useStaircase = (levels: number, onDone: (lastPassed: number) => void) => {
  const [level, setLevel] = useState(0);
  const [miss, setMiss] = useState(0);
  const [dir, setDir] = useState<Dir>(() => randomDir());

  const answer = useCallback(
    (d: Dir) => {
      const ok = d === dir;
      playUiBeep(ok ? 980 : 520, 0.04);
      if (ok) {
        if (level + 1 >= levels) return onDone(level);
        setLevel(level + 1);
        setMiss(0);
      } else if (miss + 1 >= 2) {
        return onDone(level - 1);
      } else {
        setMiss(miss + 1);
      }
      setDir(randomDir(dir));
    },
    [dir, level, miss, levels, onDone]
  );

  // Klavye okları
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const map: Record<string, Dir> = { ArrowUp: 'up', ArrowDown: 'down', ArrowLeft: 'left', ArrowRight: 'right' };
      const d = map[e.key];
      if (!d) return;
      e.preventDefault();
      answer(d);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [answer]);

  return { level, dir, answer };
};

const AcuityTest: React.FC<{ onDone: (label: string | null) => void }> = ({ onDone }) => {
  const { t } = usePrefs();
  const { level, dir, answer } = useStaircase(ACUITY_LEVELS.length, (i) => onDone(i >= 0 ? ACUITY_LEVELS[i].label : null));
  return (
    <TestFrame
      title={t('1 · Yakın görme keskinliği', '1 · Near visual acuity')}
      hint={t('E harfinin açık tarafı hangi yöne bakıyor? Okları veya klavye oklarını kullanın.', 'Which way is the open side of the E facing? Use the arrows or arrow keys.')}
      progress={`${level + 1} / ${ACUITY_LEVELS.length}`}
    >
      <ChartSurface>
        <TumblingE dir={dir} size={ACUITY_LEVELS[level].px} />
      </ChartSurface>
      <DirectionPad onPick={answer} />
    </TestFrame>
  );
};

const ContrastTest: React.FC<{ onDone: (pct: number | null) => void }> = ({ onDone }) => {
  const { t } = usePrefs();
  const { level, dir, answer } = useStaircase(CONTRAST_LEVELS.length, (i) => onDone(i >= 0 ? CONTRAST_LEVELS[i] : null));
  return (
    <TestFrame
      title={t('2 · Kontrast duyarlılığı', '2 · Contrast sensitivity')}
      hint={t('E giderek soluklaşacak. Görebildiğiniz sürece yönünü seçin.', 'The E will get fainter. Pick its direction as long as you can see it.')}
      progress={`${level + 1} / ${CONTRAST_LEVELS.length}`}
    >
      <ChartSurface>
        <TumblingE dir={dir} size={64} contrast={CONTRAST_LEVELS[level]} />
      </ChartSurface>
      <DirectionPad onPick={answer} />
    </TestFrame>
  );
};

const GRID = 10;
const AmslerTest: React.FC<{ onDone: (cells: number) => void }> = ({ onDone }) => {
  const { t } = usePrefs();
  const [marked, setMarked] = useState<Set<number>>(new Set());
  const toggle = (i: number) =>
    setMarked((prev) => {
      const n = new Set(prev);
      if (n.has(i)) n.delete(i);
      else n.add(i);
      return n;
    });
  return (
    <TestFrame
      title={t('3 · Amsler ızgarası', '3 · Amsler grid')}
      hint={t(
        'Gözünüzü ortadaki noktaya sabitleyin. Çizgiler eğri, bulanık ya da eksik görünen kareler varsa üzerlerine dokunun.',
        'Fix your eye on the center dot. Tap any squares where lines look wavy, blurred or missing.'
      )}
    >
      <ChartSurface>
        <svg viewBox={`0 0 ${GRID} ${GRID}`} className="w-full max-w-[280px] aspect-square" role="group" aria-label={t('Amsler ızgarası', 'Amsler grid')}>
          {Array.from({ length: GRID * GRID }, (_, i) => {
            const x = i % GRID;
            const y = Math.floor(i / GRID);
            return (
              <rect
                key={i}
                x={x}
                y={y}
                width={1}
                height={1}
                fill={marked.has(i) ? 'rgba(37,99,235,0.35)' : '#ffffff'}
                stroke="#111827"
                strokeWidth={0.04}
                onClick={() => toggle(i)}
                style={{ cursor: 'pointer' }}
              />
            );
          })}
          <circle cx={GRID / 2} cy={GRID / 2} r={0.18} fill="#111827" />
        </svg>
      </ChartSurface>
      <div className="flex flex-wrap justify-center gap-2">
        <Button variant="secondary" onClick={() => onDone(0)} disabled={marked.size > 0}>
          {t('Tüm çizgiler düz', 'All lines look straight')}
        </Button>
        <Button onClick={() => onDone(marked.size)} disabled={marked.size === 0}>
          {t(`İşaretlediklerimle devam (${marked.size})`, `Continue with marked (${marked.size})`)}
        </Button>
      </div>
    </TestFrame>
  );
};

const TestFrame: React.FC<{ title: string; hint: string; progress?: string; children: React.ReactNode }> = ({ title, hint, progress, children }) => (
  <section className="bg-white rounded-2xl border border-slate-200 p-5 space-y-4">
    <div className="flex items-start justify-between gap-3">
      <div>
        <h2 className="text-lg font-bold text-slate-900">{title}</h2>
        <p className="text-sm text-slate-600 mt-0.5">{hint}</p>
      </div>
      {progress && <span className="text-xs font-mono text-slate-500 shrink-0">{progress}</span>}
    </div>
    {children}
  </section>
);

export const EyeTestPage: React.FC = () => {
  const { setCurrentTab, astronaut } = useTelemetry();
  const { t } = usePrefs();
  const [step, setStep] = useState<Step>('intro');
  const [eye, setEye] = useState<EyeId>('OD');
  const [results, setResults] = useState<Record<EyeId, EyeResult>>({
    OD: { acuity: null, contrastPct: null, amslerCells: 0 },
    OS: { acuity: null, contrastPct: null, amslerCells: 0 },
  });
  // Her adımda yeni test bileşeni (durum sıfırlansın)
  const [round, setRound] = useState(0);

  const eyeName = (e: EyeId) => (e === 'OD' ? t('Sağ göz', 'Right eye') : t('Sol göz', 'Left eye'));
  const other = (e: EyeId) => (e === 'OD' ? t('sol', 'left') : t('sağ', 'right'));

  const save = (patch: Partial<EyeResult>, next: Step) => {
    setResults((r) => ({ ...r, [eye]: { ...r[eye], ...patch } }));
    setRound((n) => n + 1);
    setStep(next);
  };

  const afterAmsler = (cells: number) => {
    const updated = { ...results, [eye]: { ...results[eye], amslerCells: cells } };
    setResults(updated);
    if (eye === 'OD') {
      setEye('OS');
      setRound((n) => n + 1);
      setStep('cover');
    } else {
      try {
        localStorage.setItem(STORE_KEY, JSON.stringify({ day: astronaut.solDay, od: updated.OD, os: updated.OS }));
      } catch {
        /* yalnız kolaylık; tutulamazsa sorun değil */
      }
      setStep('summary');
    }
  };

  const restart = () => {
    setEye('OD');
    setResults({ OD: { acuity: null, contrastPct: null, amslerCells: 0 }, OS: { acuity: null, contrastPct: null, amslerCells: 0 } });
    setRound((n) => n + 1);
    setStep('intro');
  };

  const amslerAny = results.OD.amslerCells > 0 || results.OS.amslerCells > 0;

  return (
    <div className="w-full max-w-3xl mx-auto space-y-5 pb-12 animate-fadeIn">
      <button
        type="button"
        onClick={() => setCurrentTab('tests')}
        className="flex items-center gap-1.5 min-h-11 text-sm font-semibold text-slate-600 hover:text-slate-900"
      >
        <ArrowLeft className="w-4 h-4" />
        {t('Testlere dön', 'Back to tests')}
      </button>

      <PageHeader
        title={t('Göz Taraması (SANS)', 'Eye Screening (SANS)')}
        subtitle={t('Yakın görme · kontrast · Amsler ızgarası — her göz ayrı', 'Near vision · contrast · Amsler grid — each eye separately')}
      />

      {astronaut.isDisplayOnly ? (
        <DisplayOnlyNotice />
      ) : (
        <>
          {step === 'intro' && (
            <section className="bg-white rounded-2xl border border-slate-200 p-6 space-y-4">
              <div className="flex items-center gap-3">
                <span className="w-12 h-12 rounded-xl bg-slate-100 text-slate-700 flex items-center justify-center">
                  <Eye className="w-6 h-6" />
                </span>
                <h2 className="text-lg font-bold text-slate-900">{t('Nasıl yapılır?', 'How it works')}</h2>
              </div>
              <ul className="space-y-2 text-sm text-slate-700 leading-relaxed list-disc pl-5">
                <li>{t('Ekranı yaklaşık 40 cm uzakta tutun; gözlük/lens kullanıyorsanız takın.', 'Hold the screen about 40 cm away; wear your glasses or lenses if you use them.')}</li>
                <li>{t('Önce sağ, sonra sol göz test edilir. Test edilmeyen gözü elinizle kapatın.', 'The right eye is tested first, then the left. Cover the other eye with your hand.')}</li>
                <li>{t('Her göz için üç kısa test: yakın görme, kontrast ve Amsler ızgarası. Toplam ~3 dakika.', 'Three short tests per eye: near vision, contrast and the Amsler grid. About 3 minutes in total.')}</li>
              </ul>
              <p className="flex items-start gap-2 text-xs text-slate-500">
                <Info className="w-4 h-4 shrink-0" />
                {t(
                  'Uzayda vücut sıvısının başa kayması gözü etkileyebilir (SANS). Bu tarama değişiklikleri erken fark etmek içindir; tanı koymaz. Sonuçlar yalnız bu cihazda kalır.',
                  'In space, fluid shifting toward the head can affect the eyes (SANS). This screening helps notice changes early; it is not a diagnosis. Results stay on this device only.'
                )}
              </p>
              <Button onClick={() => setStep('cover')}>{t('Başla', 'Start')}</Button>
            </section>
          )}

          {step === 'cover' && (
            <section className="bg-white rounded-2xl border border-slate-200 p-8 text-center space-y-4">
              <p className="text-sm font-semibold text-slate-500">{eyeName(eye)}</p>
              <h2 className="text-xl font-bold text-slate-900">
                {t(`${other(eye).charAt(0).toUpperCase() + other(eye).slice(1)} gözünüzü kapatın`, `Cover your ${other(eye)} eye`)}
              </h2>
              <p className="text-sm text-slate-600">{t('Hazır olduğunuzda başlayın.', 'Start when you are ready.')}</p>
              <Button onClick={() => setStep('acuity')} autoFocus>
                {t('Hazırım', "I'm ready")}
              </Button>
            </section>
          )}

          {(step === 'acuity' || step === 'contrast' || step === 'amsler') && (
            <p className="text-sm font-semibold text-slate-600">
              {eyeName(eye)} · {t(`${other(eye)} göz kapalı`, `${other(eye)} eye covered`)}
            </p>
          )}
          {step === 'acuity' && <AcuityTest key={`a${round}`} onDone={(acuity) => save({ acuity }, 'contrast')} />}
          {step === 'contrast' && <ContrastTest key={`c${round}`} onDone={(contrastPct) => save({ contrastPct }, 'amsler')} />}
          {step === 'amsler' && <AmslerTest key={`m${round}`} onDone={afterAmsler} />}

          {step === 'summary' && (
            <section className="bg-white rounded-2xl border border-slate-200 p-6 space-y-5">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-5 h-5 text-slate-600" />
                <h2 className="text-lg font-bold text-slate-900">{t('Tarama tamamlandı', 'Screening complete')}</h2>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm text-left">
                  <thead className="text-xs text-slate-500 border-b border-slate-200">
                    <tr>
                      <th className="py-2 pr-3 font-semibold" />
                      <th className="py-2 pr-3 font-semibold">{t('Yakın görme', 'Near vision')}</th>
                      <th className="py-2 pr-3 font-semibold">{t('En düşük kontrast', 'Lowest contrast')}</th>
                      <th className="py-2 pr-3 font-semibold">{t('Amsler', 'Amsler')}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {(['OD', 'OS'] as EyeId[]).map((e) => (
                      <tr key={e}>
                        <td className="py-2.5 pr-3 font-semibold text-slate-800">{eyeName(e)}</td>
                        <td className="py-2.5 pr-3 font-mono text-slate-800">{results[e].acuity ?? '—'}</td>
                        <td className="py-2.5 pr-3 font-mono text-slate-800">{results[e].contrastPct !== null ? `%${results[e].contrastPct}` : '—'}</td>
                        <td className="py-2.5 pr-3 text-slate-800">
                          {results[e].amslerCells === 0 ? t('Düz', 'Straight') : t(`${results[e].amslerCells} kare işaretlendi`, `${results[e].amslerCells} squares marked`)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="text-sm text-slate-600 leading-relaxed">
                {amslerAny
                  ? t(
                      'Amsler ızgarasında bozulma işaretlediniz. Bu, uçuş cerrahına bildirilmesi gereken bir değişiklik olabilir; bir sonraki tıbbi görüşmede paylaşın.',
                      'You marked distortion on the Amsler grid. This may be a change to report to your flight surgeon; share it at your next medical conference.'
                    )
                  : t(
                      'Sonuçlarınızı önceki taramalarla karşılaştırın. Belirgin bir düşüş fark ederseniz uçuş cerrahına bildirin.',
                      'Compare with your previous screenings. If you notice a clear drop, tell your flight surgeon.'
                    )}
              </p>
              <p className="text-xs text-slate-500">
                {t('Değerler yaklaşıktır (ekran mesafesi ve parlaklığa bağlı). Sonuç sisteme gönderilmez.', 'Values are approximate (depend on screen distance and brightness). Results are not sent anywhere.')}
              </p>
              <div className="flex flex-wrap gap-2">
                <Button variant="secondary" onClick={restart}>
                  <RotateCcw className="w-4 h-4" />
                  {t('Tekrarla', 'Repeat')}
                </Button>
                <Button onClick={() => setCurrentTab('tests')}>{t('Bitti', 'Done')}</Button>
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
};
