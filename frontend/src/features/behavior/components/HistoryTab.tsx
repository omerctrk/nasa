import React, { useState } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Button, Card, Skeleton } from '../../../components/ui';
import { usePrefs } from '../../../context/PreferencesContext';
import { behavioralApi, errorMessage, SHARING_EDITABLE } from '../api';
import { formatDayMonth } from '../date';
import type { BehaviorData } from '../useBehaviorData';
import { accuracyPct, isSynthetic, type WeeklyAssessment } from '../types';

// Nötr renkler (durum rengi yok); açık ve koyu temada okunur
const INK = '#64748b';
const INK_SOFT = '#94a3b8';
const GRID = 'rgba(148,163,184,0.25)';

type Point = { day: number; date: string; value: number | null };

const ChartCard: React.FC<{
  title: string;
  unit?: string;
  simulated: boolean;
  empty: boolean;
  emptyText: string;
  children: React.ReactElement;
}> = ({ title, unit, simulated, empty, emptyText, children }) => {
  const { t } = usePrefs();
  return (
    <Card className="p-5">
      <div className="flex items-start justify-between gap-2 mb-3">
        <h3 className="text-sm font-bold text-slate-900">
          {title} {unit && <span className="font-normal text-slate-500">({unit})</span>}
        </h3>
        {simulated && (
          <span className="px-1.5 py-0.5 rounded-md border border-slate-200 bg-slate-50 text-[11px] text-slate-500 whitespace-nowrap">
            {t('simüle veri', 'simulated data')}
          </span>
        )}
      </div>
      {empty ? (
        <p className="h-48 flex items-center justify-center text-sm text-slate-500 text-center px-4">{emptyText}</p>
      ) : (
        <div className="h-48">
          <ResponsiveContainer width="100%" height="100%">
            {children}
          </ResponsiveContainer>
        </div>
      )}
    </Card>
  );
};

export const HistoryTab: React.FC<{ data: BehaviorData; loading: boolean; onCheckin: () => void; onReload: () => Promise<void> }> = ({
  data,
  loading,
  onCheckin,
  onReload,
}) => {
  const { t, lang } = usePrefs();
  const [sharingBusy, setSharingBusy] = useState<number | null>(null);
  const [sharingError, setSharingError] = useState<string | null>(null);

  if (loading) {
    return (
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5" aria-busy="true">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-64 w-full rounded-2xl" />
        ))}
      </div>
    );
  }

  const today = data.mission?.mission_day ?? 0;
  const days = Array.from({ length: 30 }, (_, k) => today - 29 + k);
  const dateOfDay = (d: number) => {
    const ref = data.mission?.date ?? data.today;
    const dt = new Date(`${ref}T00:00:00Z`);
    dt.setUTCDate(dt.getUTCDate() - (today - d));
    return dt.toISOString().slice(0, 10);
  };

  // Günlük seriler: eksik gün = null (0 çizilmez, çizgi kesilir)
  const ciByDay = new Map(data.checkins.map((c) => [c.mission_day, c]));
  const daily = (pick: (d: number) => number | null): Point[] => days.map((d) => ({ day: d, date: dateOfDay(d), value: pick(d) }));
  const mood = daily((d) => ciByDay.get(d)?.mood_index ?? null);
  const sleep = daily((d) => ciByDay.get(d)?.sleep_hours ?? null);

  // Test başına seriler: geçersiz testler çizilmez
  const validTests = data.tests.filter((x) => x.valid).sort((a, b) => a.taken_at.localeCompare(b.taken_at));
  const perTest = (type: 'pvt' | 'rotation', field: 'mean_rt_ms' | 'lapses' | 'accuracy'): Point[] =>
    validTests
      .filter((x) => x.test_type === type && x[field] !== null)
      .map((x) => ({
        day: x.mission_day,
        date: x.taken_at.slice(0, 10),
        // accuracy backend'de 0–1; grafikte yüzde gösterilir
        value: field === 'accuracy' ? (accuracyPct(x.accuracy) as number) : (x[field] as number),
      }));
  const rt = perTest('pvt', 'mean_rt_ms');
  const lapses = perTest('pvt', 'lapses');
  const acc = perTest('rotation', 'accuracy');

  const ciSeed = data.checkins.some((c) => isSynthetic(c.source));
  const pvtSeed = data.tests.some((x) => x.test_type === 'pvt' && isSynthetic(x.source));
  const rotSeed = data.tests.some((x) => x.test_type === 'rotation' && isSynthetic(x.source));
  const weeklySeed = data.weekly.some((w) => isSynthetic(w.source));

  const xAxis = (
    <XAxis
      dataKey="day"
      type="number"
      domain={[days[0], days[days.length - 1]]}
      tickCount={6}
      allowDecimals={false}
      tick={{ fontSize: 11, fill: INK }}
      stroke={INK_SOFT}
    />
  );
  const yAxis = (domain?: [number | string, number | string]) => (
    <YAxis width={36} domain={domain ?? ['auto', 'auto']} tick={{ fontSize: 11, fill: INK }} stroke={INK_SOFT} />
  );
  const grid = <CartesianGrid stroke={GRID} vertical={false} />;
  // Görev günü 1–7: temel dönem
  const baseline = (
    <ReferenceArea
      x1={1}
      x2={7}
      ifOverflow="hidden"
      fill={INK_SOFT}
      fillOpacity={0.12}
      label={{ value: t('ilk hafta', 'first week'), fontSize: 10, fill: INK, position: 'insideTop' }}
    />
  );
  const tooltip = (unit: string) => (
    <Tooltip
      cursor={{ stroke: INK_SOFT, fill: 'rgba(148,163,184,0.12)' }}
      contentStyle={{ borderRadius: 12, border: '1px solid #cbd5e1', fontSize: 12 }}
      labelFormatter={(_, payload) => {
        const p = payload?.[0]?.payload as Point | undefined;
        return p ? `${t('Görev günü', 'Mission day')} ${p.day} · ${formatDayMonth(p.date, lang)}` : '';
      }}
      formatter={(v) => [`${v} ${unit}`.trim(), '']}
      separator=""
    />
  );

  const noCheckins = t("Henüz check-in yok. İlk check-in'ini yaparak başla.", 'No check-ins yet. Start with your first check-in.');
  const noTests = t('Henüz test kaydı yok.', 'No test records yet.');

  const toggleShare = async (w: WeeklyAssessment) => {
    setSharingBusy(w.id);
    setSharingError(null);
    try {
      await behavioralApi.putWeeklySharing(w.id, !w.share_with_crew_medical);
      await onReload();
    } catch (e) {
      setSharingError(errorMessage(e, t));
    } finally {
      setSharingBusy(null);
    }
  };

  return (
    <div className="space-y-5">
      {data.checkins.length === 0 && (
        <Card className="p-5 flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-slate-600">{noCheckins}</p>
          <Button onClick={onCheckin}>{t('Check-in yap', 'Check in')}</Button>
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <ChartCard title={t('Ruh hali indeksi', 'Mood index')} unit="0–100" simulated={ciSeed} empty={!data.checkins.length} emptyText={noCheckins}>
          <LineChart data={mood} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            {grid}
            {baseline}
            {xAxis}
            {yAxis([0, 100])}
            {tooltip('')}
            <Line type="linear" dataKey="value" stroke={INK} strokeWidth={2} dot={{ r: 2.5, fill: INK }} connectNulls={false} isAnimationActive={false} />
          </LineChart>
        </ChartCard>

        <ChartCard title={t('Uyku', 'Sleep')} unit={t('saat', 'hours')} simulated={ciSeed} empty={!data.checkins.length} emptyText={noCheckins}>
          <BarChart data={sleep} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            {grid}
            {baseline}
            {xAxis}
            {yAxis([0, 'auto'])}
            {tooltip(t('sa', 'h'))}
            <Bar dataKey="value" fill={INK_SOFT} radius={[3, 3, 0, 0]} isAnimationActive={false} />
          </BarChart>
        </ChartCard>

        <ChartCard title={t('Tepki süresi (PVT)', 'Reaction time (PVT)')} unit="ms" simulated={pvtSeed} empty={!rt.length} emptyText={noTests}>
          <LineChart data={rt} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            {grid}
            {baseline}
            {xAxis}
            {yAxis()}
            {tooltip('ms')}
            <Line type="linear" dataKey="value" stroke={INK} strokeWidth={2} dot={{ r: 2.5, fill: INK }} isAnimationActive={false} />
          </LineChart>
        </ChartCard>

        <ChartCard title={t('Dikkat kaybı', 'Lapses')} unit={t('test başına', 'per test')} simulated={pvtSeed} empty={!lapses.length} emptyText={noTests}>
          <BarChart data={lapses} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            {grid}
            {baseline}
            {xAxis}
            {yAxis([0, 'auto'])}
            {tooltip('')}
            <Bar dataKey="value" fill={INK_SOFT} radius={[3, 3, 0, 0]} isAnimationActive={false} />
          </BarChart>
        </ChartCard>

        <ChartCard title={t('Döndürme doğruluğu', 'Rotation accuracy')} unit="%" simulated={rotSeed} empty={!acc.length} emptyText={noTests}>
          <LineChart data={acc} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            {grid}
            {baseline}
            {xAxis}
            {yAxis([0, 100])}
            {tooltip('%')}
            <Line type="linear" dataKey="value" stroke={INK} strokeWidth={1.5} dot={{ r: 4, fill: INK }} isAnimationActive={false} />
          </LineChart>
        </ChartCard>

        {/* Test kayıtları: geçersizler burada etiketle görünür */}
        <Card className="p-5">
          <h3 className="text-sm font-bold text-slate-900 mb-3">{t('Test kayıtları', 'Test records')}</h3>
          {data.tests.length === 0 ? (
            <p className="text-sm text-slate-500">{noTests}</p>
          ) : (
            <ul className="max-h-48 overflow-y-auto divide-y divide-slate-100 text-sm pr-1">
              {data.tests.map((x) => (
                <li key={x.id} className="flex items-center justify-between gap-2 py-1.5">
                  <span className="text-slate-500 font-mono w-16">
                    {t('Gün', 'Day')} {x.mission_day}
                  </span>
                  <span className="flex-1 text-slate-800">{x.test_type === 'pvt' ? t('Tepki', 'Reaction') : t('Döndürme', 'Rotation')}</span>
                  {x.valid ? (
                    <span className="font-mono text-slate-700">
                      {x.test_type === 'pvt' ? `${x.mean_rt_ms} ms` : `${accuracyPct(x.accuracy)}%`}
                    </span>
                  ) : (
                    <span className="px-1.5 py-0.5 rounded-md border border-slate-300 text-xs text-slate-600">{t('geçersiz', 'invalid')}</span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      {/* Haftalık ölçekler: yalnızca bu modülde, yalnızca astronota gösterilir */}
      <Card className="p-5">
        <div className="flex items-start justify-between gap-2 mb-3">
          <h3 className="text-sm font-bold text-slate-900">{t('Haftalık ölçekler', 'Weekly scales')}</h3>
          {weeklySeed && (
            <span className="px-1.5 py-0.5 rounded-md border border-slate-200 bg-slate-50 text-[11px] text-slate-500">
              {t('simüle veri', 'simulated data')}
            </span>
          )}
        </div>
        {data.weekly.length === 0 ? (
          <p className="text-sm text-slate-500">{t('Henüz haftalık değerlendirme yok.', 'No weekly assessments yet.')}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead className="text-xs text-slate-500 border-b border-slate-200">
                <tr>
                  <th className="py-2 pr-3 font-semibold">{t('Tarih', 'Date')}</th>
                  <th className="py-2 pr-3 font-semibold">WHO-5</th>
                  <th className="py-2 pr-3 font-semibold">PHQ-2</th>
                  <th className="py-2 pr-3 font-semibold">GAD-2</th>
                  <th className="py-2 pr-3 font-semibold">{t('Sağlık ekibiyle paylaş', 'Share with medical team')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.weekly.map((w) => (
                  <tr key={w.id}>
                    <td className="py-2.5 pr-3 text-slate-800">
                      {t('Gün', 'Day')} {w.mission_day} · {formatDayMonth(w.taken_at, lang)}
                    </td>
                    <td className="py-2.5 pr-3 font-mono text-slate-800">{w.who5_score}</td>
                    <td className="py-2.5 pr-3 font-mono text-slate-800">{w.phq2_score}</td>
                    <td className="py-2.5 pr-3 font-mono text-slate-800">{w.gad2_score}</td>
                    <td className="py-1.5 pr-3">
                      {!SHARING_EDITABLE ? (
                        // Backend'de paylaşım ayarı ucu henüz yok: yalnız durum gösterilir
                        <span className="text-slate-600">{w.share_with_crew_medical ? t('Paylaşıldı', 'Shared') : t('Yalnız sende', 'Only you')}</span>
                      ) : (
                      <button
                        type="button"
                        role="switch"
                        aria-checked={w.share_with_crew_medical}
                        aria-label={t('Sağlık ekibiyle paylaş', 'Share with medical team')}
                        disabled={sharingBusy === w.id}
                        onClick={() => void toggleShare(w)}
                        className="min-h-11 flex items-center"
                      >
                        <span className={`relative w-11 h-6 rounded-full transition-colors ${w.share_with_crew_medical ? 'bg-blue-600' : 'bg-slate-300'}`}>
                          <span
                            style={{ backgroundColor: '#fff' }}
                            className={`absolute top-0.5 w-5 h-5 rounded-full shadow transition-all ${
                              w.share_with_crew_medical ? 'left-[22px]' : 'left-0.5'
                            }`}
                          />
                        </span>
                      </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {sharingError && <p className="text-sm text-slate-700 mt-2">{sharingError}</p>}
      </Card>
    </div>
  );
};
