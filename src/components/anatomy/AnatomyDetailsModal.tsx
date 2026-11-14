import React, { useEffect } from 'react';
import { X } from 'lucide-react';
import { useTelemetry } from '../../context/TelemetryContext';
import { usePrefs } from '../../context/PreferencesContext';
import { AnatomyZoneId } from '../../types/telemetry';
import { playUiBeep } from '../../utils/audio';
import { statusMeta } from '../../utils/status';
import { getZoneContent } from './zoneContent';
import { ZoneDetails } from './ZoneDetails';

interface AnatomyDetailsModalProps {
  zone: AnatomyZoneId | null;
  onClose: () => void;
}

export const AnatomyDetailsModal: React.FC<AnatomyDetailsModalProps> = ({ zone, onClose }) => {
  const { vitals, currentTab } = useTelemetry();
  const { t } = usePrefs();

  // Anatomi sayfasında detaylar zaten yan panelde gösterilir
  const open = !!zone && currentTab !== 'anatomy';

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open || !zone) return null;

  const content = getZoneContent(zone, vitals, t);
  const meta = statusMeta(content.status, t);
  const close = () => {
    playUiBeep(600);
    onClose();
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/50 backdrop-blur-sm animate-fadeIn"
      onClick={close}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="zone-title"
        onClick={(e) => e.stopPropagation()}
        className="relative w-full max-w-2xl bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden flex flex-col max-h-[90vh]"
      >
        <div className="flex items-start justify-between gap-3 p-5 border-b border-slate-100">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-200">{content.icon}</div>
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h2 id="zone-title" className="text-lg font-bold text-slate-900">
                  {content.title}
                </h2>
                <span className={`px-2 py-0.5 rounded-md border text-xs font-semibold ${meta.badge}`}>{meta.label}</span>
              </div>
              <p className="text-sm text-slate-500 mt-0.5">{content.subtitle}</p>
            </div>
          </div>
          <button
            onClick={close}
            aria-label={t('Kapat', 'Close')}
            className="p-2 rounded-xl text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 overflow-y-auto">
          <ZoneDetails content={content} onNavigate={onClose} />
        </div>
      </div>
    </div>
  );
};
