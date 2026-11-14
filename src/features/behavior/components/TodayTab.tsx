import React from 'react';
import { Check, ClipboardList, Zap, RotateCw, CalendarClock, Info, ArrowRight } from 'lucide-react';
import { Button, Card, InfoBox, Skeleton } from '../../../components/ui';
import { usePrefs } from '../../../context/PreferencesContext';
import { daysBetween, formatTimeUtc } from '../date';
import { SUPPORT_NOTE, SUPPORT_THRESHOLD } from '../questions';
import type { BehaviorData } from '../useBehaviorData';
import { MiniTrend } from './MiniTrend';
import { accuracyPct } from '../types';

export type BehaviorAction = 'checkin' | 'weekly' | 'pvt' | 'rotation';

const TaskRow: React.FC<{
  icon: React.ReactNode;
  title: string;
  done: boolean;
  doneText?: React.ReactNode;
  action?: React.ReactNode;
}> = ({ icon, title, done, doneText, action }) => (
  <li className="flex flex-wrap items-center gap-3 py-3 border-b border-slate-100 last:border-0">
    <span className="w-10 h-10 rounded-xl bg-slate-100 text-slate-600 flex items-center justify-center shrink-0">{icon}</span>
    <div className="flex-1 min-w-[160px]">
      <div className="text-sm font-semibold text-slate-900">{title}</div>
      {done && doneText && (
        <div className="flex items-center gap-1.5 text-sm text-slate-600 mt-0.5">
          <Check className="w-4 h-4 text-slate-700" aria-hidden />
          {doneText}
        </div>
      )}
    </div>
    {action}
  </li>
);

export const TodayTab: React.FC<{ data: BehaviorData; loading: boolean; onAction: (a: BehaviorAction) => void }> = ({
  data,
  loading,
  onAction,
}) => {
  const { t, pick } = usePrefs();
  const { today, todayCheckin, tests, weekly, checkins } = data;

  if (loading) {
    return (
      <div className="space-y-4" aria-busy="true">
        <Skeleton className="h-64 w-full rounded-2xl" />
        <Skeleton className="h-48 w-full rounded-2xl" />
      </div>
    );
  }

  const valid = tests.filter((x) => x.valid);
  const todays = (type: 'pvt' | 'rotation') => valid.find((x) => x.test_type === type && x.taken_at.slice(0, 10) === today);
  const lastOf = (type: 'pvt' | 'rotation') => valid.find((x) => x.test_type === type);

  const pvtToday = todays('pvt');
  const rotToday = todays('rotation');
  const lastRot = lastOf('rotation');
  const rotDue = !lastRot || daysBetween(lastRot.taken_at, today) >= 2;
  const lastWeekly = weekly[0];
  const weeklyDue = !lastWeekly || daysBetween(lastWeekly.taken_at, today) >= 7;

  const needsSupport = !!lastWeekly && (lastWeekly.phq2_score >= SUPPORT_THRESHOLD || lastWeekly.gad2_score >= SUPPORT_THRESHOLD);

  // Son 7 günün değerleri (görev gününe göre)
  const day = data.mission?.mission_day ?? 0;
  const last7 = Array.from({ length: 7 }, (_, k) => day - 6 + k);
  const series = (fn: (d: number) => number | null) => last7.map(fn);
  const ciByDay = new Map(checkins.map((c) => [c.mission_day, c]));
  const lastPerDay = (type: 'pvt' | 'rotation', d: number) => valid.find((x) => x.test_type === type && x.mission_day === d);

  const lastCi = checkins[0];
  const lastPvt = lastOf('pvt');

  const values = [
    {
      label: t('Ruh hali indeksi', 'Mood index'),
      value: lastCi ? `${lastCi.mood_index}` : '—',
      unit: '/ 100',
      data: series((d) => ciByDay.get(d)?.mood_index ?? null),
    },
    {
      label: t('Uyku süresi', 'Sleep'),
      value: lastCi ? `${lastCi.sleep_hours}` : '—',
      unit: t('saat', 'h'),
      data: series((d) => ciByDay.get(d)?.sleep_hours ?? null),
    },
    {
      label: t('Tepki süresi (PVT)', 'Reaction time (PVT)'),
      value: lastPvt?.mean_rt_ms != null ? `${lastPvt.mean_rt_ms}` : '—',
      unit: 'ms',
      data: series((d) => lastPerDay('pvt', d)?.mean_rt_ms ?? null),
    },
    {
      label: t('Dikkat kaybı', 'Lapses'),
      value: lastPvt?.lapses != null ? `${lastPvt.lapses}` : '—',
      unit: '',
      data: series((d) => lastPerDay('pvt', d)?.lapses ?? null),
    },
    {
      label: t('Döndürme doğruluğu', 'Rotation accuracy'),
      value: lastRot?.accuracy != null ? `${accuracyPct(lastRot.accuracy)}` : '—',
      unit: '%',
      data: series((d) => accuracyPct(lastPerDay('rotation', d)?.accuracy)),
    },
  ];

  return (
    <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">
      <Card className="p-5 lg:col-span-3">
        <h2 className="text-base font-bold text-slate-900 mb-1">{t('Bugünkü görevler', "Today's tasks")}</h2>
        <ul>
          <TaskRow
            icon={<ClipboardList className="w-5 h-5" />}
            title={t('Günlük check-in', 'Daily check-in')}
            done={!!todayCheckin}
            doneText={todayCheckin && `${formatTimeUtc(todayCheckin.updated_at)} UTC`}
            action={
              todayCheckin ? (
                <button type="button" onClick={() => onAction('checkin')} className="min-h-11 px-3 text-sm font-semibold text-blue-700 underline-offset-2 hover:underline">
                  {t('Düzenle', 'Edit')}
                </button>
              ) : (
                <Button onClick={() => onAction('checkin')}>{t('Check-in yap', 'Check in')}</Button>
              )
            }
          />
          <TaskRow
            icon={<Zap className="w-5 h-5" />}
            title={t('Tepki testi (3 dk)', 'Reaction test (3 min)')}
            done={!!pvtToday}
            doneText={pvtToday && `${t('Ortalama', 'Mean')} ${pvtToday.mean_rt_ms} ms`}
            action={!pvtToday && <Button onClick={() => onAction('pvt')}>{t('Teste başla', 'Start test')}</Button>}
          />
          {(rotToday || rotDue) && (
            <TaskRow
              icon={<RotateCw className="w-5 h-5" />}
              title={t('Zihinsel döndürme', 'Mental rotation')}
              done={!!rotToday}
              doneText={rotToday && `${t('Doğruluk', 'Accuracy')} ${accuracyPct(rotToday.accuracy)}%`}
              action={!rotToday && <Button onClick={() => onAction('rotation')}>{t('Teste başla', 'Start test')}</Button>}
            />
          )}
          <TaskRow
            icon={<CalendarClock className="w-5 h-5" />}
            title={weeklyDue ? t('Bugün haftalık değerlendirme günü', 'Weekly assessment is due today') : t('Haftalık değerlendirme', 'Weekly assessment')}
            done={!weeklyDue}
            doneText={t('Bu haftaki test tamamlandı', "This week's assessment is done")}
            action={
              weeklyDue && (
                <Button variant="secondary" onClick={() => onAction('weekly')}>
                  {t('Değerlendirmeye git', 'Go to assessment')}
                  <ArrowRight className="w-4 h-4" />
                </Button>
              )
            }
          />
        </ul>
      </Card>

      <div className="lg:col-span-2 space-y-5">
        <Card className="p-5">
          <h2 className="text-base font-bold text-slate-900 mb-3">{t('Son değerler', 'Latest values')}</h2>
          {checkins.length === 0 && tests.length === 0 ? (
            <div className="space-y-3">
              <p className="text-sm text-slate-600">
                {t("Henüz check-in yok. İlk check-in'ini yaparak başla.", 'No check-ins yet. Start with your first check-in.')}
              </p>
              <Button onClick={() => onAction('checkin')}>{t('Check-in yap', 'Check in')}</Button>
            </div>
          ) : (
            <ul className="divide-y divide-slate-100">
              {values.map((v) => (
                <li key={v.label} className="flex items-center gap-3 py-2.5">
                  <div className="flex-1 min-w-0">
                    <div className="text-xs text-slate-500">{v.label}</div>
                    <div className="text-lg font-bold font-mono text-slate-900">
                      {v.value} <span className="text-xs font-sans font-normal text-slate-500">{v.value !== '—' && v.unit}</span>
                    </div>
                  </div>
                  <MiniTrend data={v.data} label={`${v.label} – ${t('son 7 gün', 'last 7 days')}`} />
                </li>
              ))}
            </ul>
          )}
          <p className="text-xs text-slate-400 mt-2">{t('Küçük grafikler: son 7 gün', 'Sparklines: last 7 days')}</p>
        </Card>

        {needsSupport && <InfoBox icon={<Info className="w-4 h-4" />}>{pick(SUPPORT_NOTE)}</InfoBox>}
      </div>
    </div>
  );
};
