import React, { useEffect, useMemo, useState } from 'react';
import { Check, Moon } from 'lucide-react';
import { Button, Card, FormField, InfoBox } from '../../../components/ui';
import { usePrefs } from '../../../context/PreferencesContext';
import { ApiError } from '../../../lib/apiClient';
import { behavioralApi, errorMessage } from '../api';
import { formatDuration, sleepMinutes } from '../date';
import { CHECKIN_CHOICES, CHECKIN_LABELS, CHECKIN_SLIDERS, SYMPTOMS } from '../questions';
import type { Checkin, CheckinInput, SymptomCode } from '../types';

type Draft = {
  mood: number | null;
  energy: number | null;
  stress: number | null;
  loneliness: number | null;
  crew: number | null;
  bed_time: string;
  wake_time: string;
  sleep_quality: number | null;
  symptoms: SymptomCode[];
  noneSelected: boolean;
};

const emptyDraft: Draft = {
  mood: null,
  energy: null,
  stress: null,
  loneliness: null,
  crew: null,
  bed_time: '',
  wake_time: '',
  sleep_quality: null,
  symptoms: [],
  noneSelected: false,
};

const fromRecord = (c: Checkin): Draft => ({
  mood: c.mood,
  energy: c.energy,
  stress: c.stress,
  loneliness: c.loneliness,
  crew: c.crew,
  bed_time: c.bed_time.slice(0, 5),
  wake_time: c.wake_time.slice(0, 5),
  sleep_quality: c.sleep_quality,
  symptoms: [...(c.symptoms ?? [])],
  noneSelected: (c.symptoms ?? []).length === 0,
});

/** Seçilmemiş başlayan kaydırıcı (0–10) */
const UnsetSlider: React.FC<{
  id: string;
  value: number | null;
  onChange: (v: number) => void;
  minLabel: string;
  maxLabel: string;
  unsetText: string;
}> = ({ id, value, onChange, minLabel, maxLabel, unsetText }) => {
  const set = (e: React.SyntheticEvent<HTMLInputElement>) => onChange(Number(e.currentTarget.value));
  return (
    <div>
      <div className="flex items-center gap-3">
        <input
          id={id}
          type="range"
          min={0}
          max={10}
          step={1}
          value={value ?? 5}
          aria-valuetext={value === null ? unsetText : String(value)}
          onChange={set}
          onPointerUp={set}
          onKeyUp={set}
          className={`ahms-range flex-1 h-11 cursor-pointer ${value === null ? 'range-unset' : ''}`}
          style={{ '--pct': value === null ? '0%' : `${value * 10}%` } as React.CSSProperties}
        />
        <span className={`w-14 text-right font-mono text-lg font-bold ${value === null ? 'text-slate-400 text-xs font-sans' : 'text-slate-900'}`}>
          {value === null ? unsetText : value}
        </span>
      </div>
      <div className="flex justify-between text-xs text-slate-500 pr-[68px]">
        <span>{minLabel}</span>
        <span>{maxLabel}</span>
      </div>
    </div>
  );
};

/** Tek seçimli buton grubu */
const ChoiceGroup: React.FC<{ name: string; options: string[]; value: number | null; onChange: (v: number) => void; offset?: number }> = ({
  name,
  options,
  value,
  onChange,
  offset = 0,
}) => (
  <div role="radiogroup" aria-label={name} className="grid grid-cols-5 gap-1.5">
    {options.map((o, i) => {
      const v = i + offset;
      const active = value === v;
      return (
        <button
          key={o}
          type="button"
          role="radio"
          aria-checked={active}
          onClick={() => onChange(v)}
          className={`min-h-11 px-1 rounded-xl border text-sm font-medium transition-colors ${
            active ? 'bg-blue-600 border-blue-600 text-white' : 'bg-white border-slate-300 text-slate-700 hover:border-blue-400'
          }`}
        >
          {o}
        </button>
      );
    })}
  </div>
);

export const CheckinForm: React.FC<{
  today: string;
  existing: Checkin | null;
  etag: string | null;
  onSaved: (c: Checkin) => void;
  onReloadNeeded: () => Promise<void>;
}> = ({ today, existing, etag, onSaved, onReloadNeeded }) => {
  const { t, pick, lang } = usePrefs();
  const [draft, setDraft] = useState<Draft>(existing ? fromRecord(existing) : emptyDraft);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [confirmSleep, setConfirmSleep] = useState(false);

  // Aynı gün tekrar açılınca önceki cevaplarla dolu gelir
  useEffect(() => {
    setDraft(existing ? fromRecord(existing) : emptyDraft);
  }, [existing]);

  const set = <K extends keyof Draft>(k: K, v: Draft[K]) => {
    setDraft((d) => ({ ...d, [k]: v }));
    setFieldErrors((f) => ({ ...f, [k]: '' }));
  };

  const toggleSymptom = (code: SymptomCode) =>
    setDraft((d) => {
      const has = d.symptoms.includes(code);
      return { ...d, noneSelected: false, symptoms: has ? d.symptoms.filter((s) => s !== code) : [...d.symptoms, code] };
    });

  const selectNone = () => setDraft((d) => ({ ...d, symptoms: [], noneSelected: !d.noneSelected }));

  const mins = draft.bed_time && draft.wake_time ? sleepMinutes(draft.bed_time, draft.wake_time) : null;

  const missing = useMemo(() => {
    const m: string[] = [];
    if (draft.mood === null) m.push('mood');
    if (draft.energy === null) m.push('energy');
    if (draft.stress === null) m.push('stress');
    if (draft.loneliness === null) m.push('loneliness');
    if (draft.crew === null) m.push('crew');
    if (!draft.bed_time) m.push('bed_time');
    if (!draft.wake_time) m.push('wake_time');
    if (draft.sleep_quality === null) m.push('sleep_quality');
    return m;
  }, [draft]);

  // Doldurmaya başlandıktan sonra eksik alanlar işaretlenir
  const started = missing.length < 8;
  const isMissing = (k: string) => started && missing.includes(k);

  const labelOf = (k: string): string => {
    const s = CHECKIN_SLIDERS.find((x) => x.key === k);
    if (s) return pick(s.label);
    const c = CHECKIN_CHOICES.find((x) => x.key === k);
    if (c) return pick(c.label);
    return pick(CHECKIN_LABELS[k as 'bed_time' | 'wake_time' | 'sleep_quality']);
  };

  const submit = async (skipSleepCheck = false) => {
    if (missing.length) return;
    if (!skipSleepCheck && mins !== null && (mins < 120 || mins > 840)) {
      setConfirmSleep(true);
      return;
    }
    setConfirmSleep(false);
    setSaving(true);
    setError(null);
    const body: CheckinInput = {
      mood: draft.mood!,
      energy: draft.energy!,
      stress: draft.stress!,
      loneliness: draft.loneliness!,
      crew: draft.crew!,
      bed_time: draft.bed_time,
      wake_time: draft.wake_time,
      sleep_quality: draft.sleep_quality!,
      symptoms: draft.symptoms,
    };
    try {
      const res = await behavioralApi.putCheckin(today, body, existing ? etag : null);
      onSaved(res.data);
    } catch (e) {
      setError(errorMessage(e, t));
      if (e instanceof ApiError && e.status === 422) {
        setFieldErrors(Object.fromEntries(Object.entries(e.details).map(([k, v]) => [k, String(v)])));
      }
      if (e instanceof ApiError && e.status === 412) {
        // Güncel kaydı yeniden çek, form güncel değerlerle dolar
        await onReloadNeeded();
      }
    } finally {
      setSaving(false);
    }
  };

  const unset = t('Seçilmedi', 'Not set');

  return (
    <Card className="p-5 sm:p-6">
      <div className="flex flex-wrap items-baseline justify-between gap-2 mb-5">
        <h2 className="text-lg font-bold text-slate-900">{t('Günlük check-in', 'Daily check-in')}</h2>
        <span className="text-sm text-slate-500">
          {existing
            ? t('Bugünkü kaydını güncelliyorsun', "You're updating today's entry")
            : t('Yaklaşık 1 dakika', 'About 1 minute')}
        </span>
      </div>

      <form
        className="space-y-6"
        onSubmit={(e) => {
          e.preventDefault();
          void submit();
        }}
      >
        {CHECKIN_SLIDERS.map((s) => (
          <FormField key={s.key} label={pick(s.label)} htmlFor={`ci-${s.key}`} error={fieldErrors[s.key]} missing={isMissing(s.key)}>
            <UnsetSlider
              id={`ci-${s.key}`}
              value={draft[s.key]}
              onChange={(v) => set(s.key, v)}
              minLabel={pick(s.min)}
              maxLabel={pick(s.max)}
              unsetText={unset}
            />
          </FormField>
        ))}

        {CHECKIN_CHOICES.map((c) => (
          <FormField key={c.key} as="fieldset" label={pick(c.label)} error={fieldErrors[c.key]} missing={isMissing(c.key)}>
            <ChoiceGroup name={pick(c.label)} options={c.options.map(pick)} value={draft[c.key]} onChange={(v) => set(c.key, v)} />
          </FormField>
        ))}

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <FormField label={pick(CHECKIN_LABELS.bed_time)} htmlFor="ci-bed" error={fieldErrors.bed_time} missing={isMissing('bed_time')}>
            <input
              id="ci-bed"
              type="time"
              value={draft.bed_time}
              onChange={(e) => set('bed_time', e.target.value)}
              className="w-full min-h-11 px-3 rounded-xl border border-slate-300 bg-white text-slate-900 font-mono"
            />
          </FormField>
          <FormField label={pick(CHECKIN_LABELS.wake_time)} htmlFor="ci-wake" error={fieldErrors.wake_time} missing={isMissing('wake_time')}>
            <input
              id="ci-wake"
              type="time"
              value={draft.wake_time}
              onChange={(e) => set('wake_time', e.target.value)}
              className="w-full min-h-11 px-3 rounded-xl border border-slate-300 bg-white text-slate-900 font-mono"
            />
          </FormField>
        </div>
        {mins !== null && (
          <p className="-mt-3 flex items-center gap-2 text-sm text-slate-600">
            <Moon className="w-4 h-4 text-slate-400" />
            {t('Yaklaşık', 'About')} {formatDuration(mins, lang)} {t('uyku', 'of sleep')}
          </p>
        )}

        <FormField as="fieldset" label={pick(CHECKIN_LABELS.sleep_quality)} error={fieldErrors.sleep_quality} missing={isMissing('sleep_quality')}>
          <ChoiceGroup
            name={pick(CHECKIN_LABELS.sleep_quality)}
            options={['1', '2', '3', '4', '5']}
            value={draft.sleep_quality}
            onChange={(v) => set('sleep_quality', v)}
            offset={1}
          />
          <div className="flex justify-between text-xs text-slate-500 mt-1">
            <span>{pick(CHECKIN_LABELS.sleep_quality_ends.min)}</span>
            <span>{pick(CHECKIN_LABELS.sleep_quality_ends.max)}</span>
          </div>
        </FormField>

        <FormField as="fieldset" label={pick(CHECKIN_LABELS.symptoms)} error={fieldErrors.symptoms}>
          <div className="flex flex-wrap gap-2">
            {SYMPTOMS.map((s) => {
              const on = draft.symptoms.includes(s.code);
              return (
                <button
                  key={s.code}
                  type="button"
                  aria-pressed={on}
                  onClick={() => toggleSymptom(s.code)}
                  className={`min-h-11 px-3.5 rounded-full border text-sm transition-colors ${
                    on ? 'bg-blue-600 border-blue-600 text-white' : 'bg-white border-slate-300 text-slate-700 hover:border-blue-400'
                  }`}
                >
                  {pick(s.label)}
                </button>
              );
            })}
            <button
              type="button"
              aria-pressed={draft.noneSelected}
              onClick={selectNone}
              className={`min-h-11 px-3.5 rounded-full border text-sm font-semibold transition-colors ${
                draft.noneSelected ? 'bg-slate-800 border-slate-800 text-white' : 'bg-white border-slate-300 text-slate-700 hover:border-slate-500'
              }`}
            >
              {pick(CHECKIN_LABELS.none)}
            </button>
          </div>
        </FormField>

        {confirmSleep && mins !== null && (
          <div role="alertdialog" aria-live="assertive" className="p-4 rounded-xl border border-slate-300 bg-slate-50 space-y-3">
            <p className="text-sm font-medium text-slate-800">
              {t(`Uyku süren ${formatDuration(mins, 'tr')} görünüyor, doğru mu?`, `Your sleep looks like ${formatDuration(mins, 'en')}. Is that right?`)}
            </p>
            <div className="flex gap-2">
              <Button onClick={() => void submit(true)}>{t('Evet, kaydet', 'Yes, save')}</Button>
              <Button variant="secondary" onClick={() => setConfirmSleep(false)}>
                {t('Düzelt', 'Fix it')}
              </Button>
            </div>
          </div>
        )}

        {error && <InfoBox>{error}</InfoBox>}

        <div className="flex flex-wrap items-center gap-3 pt-2 border-t border-slate-100">
          <Button type="submit" size="lg" disabled={missing.length > 0 || saving}>
            <Check className="w-4 h-4" />
            {saving ? t('Kaydediliyor…', 'Saving…') : existing ? t('Güncelle', 'Update') : t('Gönder', 'Submit')}
          </Button>
          {missing.length > 0 && (
            <p className="text-sm text-slate-500">
              {t('Eksik', 'Missing')}: {missing.map(labelOf).map((l) => l.replace(/\?$/, '')).join(' · ')}
            </p>
          )}
        </div>
      </form>
    </Card>
  );
};
