import { useCallback, useEffect, useState } from 'react';
import { behavioralApi, fetchAllPages } from './api';
import { addDaysUtc, todayUtc } from './date';
import type { Checkin, CognitiveTest, MissionInfo, WeeklyAssessment } from './types';

export interface BehaviorData {
  mission: MissionInfo | null;
  today: string; // UTC
  todayCheckin: Checkin | null;
  todayEtag: string | null;
  checkins: Checkin[]; // son 30 gün
  tests: CognitiveTest[]; // son 30 gün
  weekly: WeeklyAssessment[];
}

const EMPTY: BehaviorData = {
  mission: null,
  today: todayUtc(),
  todayCheckin: null,
  todayEtag: null,
  checkins: [],
  tests: [],
  weekly: [],
};

/** Modülün tüm sekmelerinin kullandığı veriler; tek yerden yüklenir ve yenilenir. */
export const useBehaviorData = () => {
  const [data, setData] = useState<BehaviorData>(EMPTY);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);

  const reload = useCallback(async () => {
    setError(null);
    try {
      const today = todayUtc();
      const from30 = addDaysUtc(today, -30);
      const [mission, todayRes, checkins, tests, weekly] = await Promise.all([
        behavioralApi.getMission(),
        behavioralApi.getCheckin(today),
        fetchAllPages((cursor) => behavioralApi.listCheckins({ from: from30, to: addDaysUtc(today, 1), limit: 100, cursor })),
        fetchAllPages(
          (cursor) => behavioralApi.listTests({ limit: 100, cursor }),
          (items) => items.some((x) => x.taken_at.slice(0, 10) < from30)
        ),
        fetchAllPages((cursor) => behavioralApi.listWeekly({ limit: 100, cursor })),
      ]);
      setData({
        mission,
        today,
        todayCheckin: todayRes.item,
        todayEtag: todayRes.etag,
        checkins,
        // DSST bu arayüzde yok; gelirse gösterilmez
        tests: tests.filter((x) => x.taken_at.slice(0, 10) >= from30 && x.test_type !== 'dsst'),
        weekly,
      });
    } catch (e) {
      setError(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { data, loading, error, reload };
};
