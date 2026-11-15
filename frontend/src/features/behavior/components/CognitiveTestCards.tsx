import React, { useState } from 'react';
import { Zap, RotateCw, Clock } from 'lucide-react';
import { Button, Card } from '../../../components/ui';
import { usePrefs } from '../../../context/PreferencesContext';
import { formatDayMonth } from '../date';
import { accuracyPct, type CognitiveTest } from '../types';
import { PvtTest } from '../tests/PvtTest';
import { RotationTest } from '../tests/RotationTest';

/**
 * Refleks testlerinin giriş kartları (PVT + zihinsel döndürme).
 * Hem Davranış modülünün "Testler" sekmesinde hem de sol menüdeki "Testler" sayfasında
 * kullanılır; testler tek yerden (features/behavior/tests) oynatılır.
 * Gösterilen her sayı backend cevabından gelir; renk/durum rozeti yok.
 */
export const CognitiveTestCards: React.FC<{ tests?: CognitiveTest[]; onFinished: () => void | Promise<void> }> = ({ tests = [], onFinished }) => {
  const { t, lang } = usePrefs();
  const [active, setActive] = useState<'pvt' | 'rotation' | null>(null);

  const lastValid = (type: 'pvt' | 'rotation') =>
    tests.filter((x) => x.test_type === type && x.valid).sort((a, b) => b.taken_at.localeCompare(a.taken_at))[0];
  const lastPvt = lastValid('pvt');
  const lastRot = lastValid('rotation');

  const cards = [
    {
      id: 'pvt' as const,
      icon: <Zap className="w-6 h-6" />,
      title: t('Tepki testi (PVT)', 'Reaction test (PVT)'),
      desc: t(
        'Ekranda sayı belirdiğinde olabildiğince hızlı dokun. Uykusuzluk ve yorgunluğa en duyarlı ölçümdür.',
        'Tap as fast as you can when a number appears. The most sensitive measure of sleep loss and fatigue.'
      ),
      time: t('3 dakika · her gün', '3 minutes · daily'),
      last:
        lastPvt && lastPvt.mean_rt_ms !== null
          ? `${t('Son', 'Last')}: ${Math.round(lastPvt.mean_rt_ms)} ms ${t('ortalama', 'mean')} · ${lastPvt.lapses ?? 0} ${t('dikkat kaybı', 'lapses')} · ${formatDayMonth(lastPvt.taken_at.slice(0, 10), lang)}`
          : null,
    },
    {
      id: 'rotation' as const,
      icon: <RotateCw className="w-6 h-6" />,
      title: t('Zihinsel döndürme', 'Mental rotation'),
      desc: t(
        'İki şeklin aynı mı yoksa ayna görüntüsü mü olduğuna karar ver. Uzamsal düşünmeyi ölçer.',
        'Decide whether two shapes are the same or mirror images. Measures spatial thinking.'
      ),
      time: t('~2 dakika · 2 günde bir', '~2 minutes · every 2 days'),
      last:
        lastRot && lastRot.accuracy !== null
          ? `${t('Son', 'Last')}: %${accuracyPct(lastRot.accuracy)} ${t('doğruluk', 'accuracy')} · ${formatDayMonth(lastRot.taken_at.slice(0, 10), lang)}`
          : null,
    },
  ];

  const done = async () => {
    setActive(null);
    await onFinished();
  };

  return (
    <>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {cards.map((c) => (
          <Card key={c.id} className="p-6 flex flex-col">
            <div className="w-12 h-12 rounded-xl bg-slate-100 text-slate-700 flex items-center justify-center">{c.icon}</div>
            <h2 className="text-lg font-bold text-slate-900 mt-4">{c.title}</h2>
            <p className="text-sm text-slate-600 mt-1 leading-relaxed flex-1">{c.desc}</p>
            {c.last && <p className="mt-3 text-sm text-slate-500 font-mono">{c.last}</p>}
            <div className="mt-4 flex items-center justify-between gap-3">
              <span className="flex items-center gap-1.5 text-sm text-slate-500">
                <Clock className="w-4 h-4" />
                {c.time}
              </span>
              <Button onClick={() => setActive(c.id)}>{t('Teste başla', 'Start test')}</Button>
            </div>
          </Card>
        ))}
      </div>

      {active === 'pvt' && <PvtTest onClose={() => setActive(null)} onFinished={() => void done()} />}
      {active === 'rotation' && <RotationTest onClose={() => setActive(null)} onFinished={() => void done()} />}
    </>
  );
};
