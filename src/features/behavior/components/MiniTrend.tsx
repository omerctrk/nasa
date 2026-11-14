import React from 'react';

/**
 * Renksiz mini trend (sparkline). Eksik günler boş kalır; çizgi o günde kesilir.
 */
export const MiniTrend: React.FC<{ data: (number | null)[]; label: string }> = ({ data, label }) => {
  const W = 96;
  const H = 28;
  const P = 3;
  const vals = data.filter((v): v is number => v !== null);
  if (vals.length === 0) return <div className="w-24 h-7 shrink-0" aria-hidden />;
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const range = max - min || 1;
  const x = (i: number) => P + (i / Math.max(1, data.length - 1)) * (W - 2 * P);
  const y = (v: number) => H - P - ((v - min) / range) * (H - 2 * P);

  // null değerlerde çizgiyi böl
  const segments: string[] = [];
  let cur: string[] = [];
  data.forEach((v, i) => {
    if (v === null) {
      if (cur.length) segments.push(cur.join(' '));
      cur = [];
    } else cur.push(`${x(i).toFixed(1)},${y(v).toFixed(1)}`);
  });
  if (cur.length) segments.push(cur.join(' '));

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-24 h-7 shrink-0 text-slate-500" role="img" aria-label={label}>
      {segments.map((pts, k) =>
        pts.includes(' ') ? (
          <polyline key={k} points={pts} fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinejoin="round" strokeLinecap="round" />
        ) : null
      )}
      {data.map((v, i) => (v === null ? null : <circle key={i} cx={x(i)} cy={y(v)} r="1.8" fill="currentColor" />))}
    </svg>
  );
};
