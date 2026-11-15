import React, { useRef, useState } from 'react';
import { Info, Send } from 'lucide-react';
import { Button, Card, InfoBox } from '../../../components/ui';
import { usePrefs } from '../../../context/PreferencesContext';
import { newIdempotencyKey } from '../../../lib/apiClient';
import { behavioralApi, errorMessage } from '../api';
import { SUPPORT_NOTE, SUPPORT_THRESHOLD, WEEKLY_INTRO, WEEKLY_SCALES, WEEKLY_SHARE_LABEL } from '../questions';
import type { WeeklyAnswerKey, WeeklyAssessment } from '../types';

const ALL_KEYS = WEEKLY_SCALES.flatMap((s) => s.items.map((i) => i.key));

export const WeeklyForm: React.FC<{ onSaved: (w: WeeklyAssessment) => void }> = ({ onSaved }) => {
  const { t, pick } = usePrefs();
  const [answers, setAnswers] = useState<Partial<Record<WeeklyAnswerKey, number>>>({});
  const [share, setShare] = useState(false); // varsayılan KAPALI
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<WeeklyAssessment | null>(null);
  // Ağ hatasında aynı anahtarla tekrar denenir → ikinci kayıt oluşmaz
  const keyRef = useRef<string | null>(null);

  const missing = ALL_KEYS.filter((k) => answers[k] === undefined);

  const submit = async () => {
    if (missing.length) return;
    keyRef.current ??= newIdempotencyKey();
    setSaving(true);
    setError(null);
    try {
      const res = await behavioralApi.postWeekly(
        { answers: answers as Record<WeeklyAnswerKey, number>, share_with_crew_medical: share },
        keyRef.current
      );
      setResult(res.data);
      keyRef.current = null;
      onSaved(res.data);
    } catch (e) {
      setError(errorMessage(e, t));
    } finally {
      setSaving(false);
    }
  };

  if (result) {
    const needsSupport = result.phq2_score >= SUPPORT_THRESHOLD || result.gad2_score >= SUPPORT_THRESHOLD;
    return (
      <Card className="p-5 sm:p-6 space-y-4">
        <h2 className="text-lg font-bold text-slate-900">{t('Haftalık değerlendirme kaydedildi', 'Weekly assessment saved')}</h2>
        <dl className="grid grid-cols-3 gap-3">
          {[
            ['WHO-5', result.who5_score],
            ['PHQ-2', result.phq2_score],
            ['GAD-2', result.gad2_score],
          ].map(([k, v]) => (
            <div key={k} className="p-3 rounded-xl bg-slate-50 border border-slate-200 text-center">
              <dt className="text-xs text-slate-500">{k}</dt>
              <dd className="text-2xl font-bold font-mono text-slate-900 mt-0.5">{v}</dd>
            </div>
          ))}
        </dl>
        {needsSupport && <InfoBox icon={<Info className="w-4 h-4" />}>{pick(SUPPORT_NOTE)}</InfoBox>}
        <Button variant="secondary" onClick={() => setResult(null)}>
          {t('Kapat', 'Close')}
        </Button>
      </Card>
    );
  }

  return (
    <Card className="p-5 sm:p-6">
      <h2 className="text-lg font-bold text-slate-900">{t('Haftalık değerlendirme', 'Weekly assessment')}</h2>
      <p className="text-sm text-slate-600 mt-1 mb-5">{pick(WEEKLY_INTRO)}</p>

      <form
        className="space-y-7"
        onSubmit={(e) => {
          e.preventDefault();
          void submit();
        }}
      >
        {WEEKLY_SCALES.map((scale) => (
          <section key={scale.id} aria-labelledby={`sc-${scale.id}`} className="space-y-4">
            <h3 id={`sc-${scale.id}`} className="text-sm font-bold text-slate-500 uppercase tracking-wide">
              {scale.title}
            </h3>
            {scale.items.map((item) => (
              <fieldset key={item.key}>
                <legend className="text-sm font-semibold text-slate-800 mb-2">{pick(item.text)}</legend>
                <div
                  role="radiogroup"
                  className={`grid gap-1.5 ${scale.options.length === 6 ? 'grid-cols-3 sm:grid-cols-6' : 'grid-cols-2 sm:grid-cols-4'}`}
                >
                  {scale.options.map((opt, v) => {
                    const active = answers[item.key] === v;
                    return (
                      <button
                        key={v}
                        type="button"
                        role="radio"
                        aria-checked={active}
                        onClick={() => setAnswers((a) => ({ ...a, [item.key]: v }))}
                        className={`min-h-11 px-2 py-1.5 rounded-xl border text-xs leading-tight transition-colors ${
                          active ? 'bg-blue-600 border-blue-600 text-white' : 'bg-white border-slate-300 text-slate-700 hover:border-blue-400'
                        }`}
                      >
                        {pick(opt)}
                      </button>
                    );
                  })}
                </div>
              </fieldset>
            ))}
          </section>
        ))}

        <label className="flex items-start gap-3 min-h-11 cursor-pointer">
          <input
            type="checkbox"
            checked={share}
            onChange={(e) => setShare(e.target.checked)}
            className="mt-1 w-5 h-5 accent-blue-600"
          />
          <span className="text-sm text-slate-700">{pick(WEEKLY_SHARE_LABEL)}</span>
        </label>

        {error && (
          <InfoBox>
            <div className="flex flex-wrap items-center gap-3">
              <span>{error}</span>
              <Button variant="secondary" onClick={() => void submit()}>
                {t('Tekrar dene', 'Try again')}
              </Button>
            </div>
          </InfoBox>
        )}

        <div className="flex flex-wrap items-center gap-3 pt-2 border-t border-slate-100">
          <Button type="submit" size="lg" disabled={missing.length > 0 || saving}>
            <Send className="w-4 h-4" />
            {saving ? t('Gönderiliyor…', 'Sending…') : t('Gönder', 'Submit')}
          </Button>
          {missing.length > 0 && (
            <span className="text-sm text-slate-500">
              {t(`${missing.length} madde cevaplanmadı`, `${missing.length} items unanswered`)}
            </span>
          )}
        </div>
      </form>
    </Card>
  );
};
