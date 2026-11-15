import React from 'react';
import type { ShapeId } from '../types';

/**
 * Zihinsel döndürme şekilleri: 5–6 kareden oluşan asimetrik (kiral) blok şekiller.
 * Hiçbirinin ayna görüntüsü döndürmeyle elde edilemez (doğrulandı).
 * Harf veya rakam kullanılmaz.
 */
export const SHAPES: Record<ShapeId, [number, number][]> = {
  s1: [[1, 0], [2, 0], [0, 1], [1, 1], [1, 2]], // F benzeri
  s2: [[0, 0], [0, 1], [1, 1], [1, 2], [1, 3]], // N benzeri
  s3: [[0, 0], [1, 0], [0, 1], [1, 1], [0, 2]], // P benzeri
  s4: [[0, 0], [1, 0], [1, 1], [1, 2], [2, 2], [2, 3]], // 6 kare
};

export const SHAPE_IDS = Object.keys(SHAPES) as ShapeId[];

const CELL = 22;

/**
 * Şekli çizer. Ayna: önce yatay yansıtma (scale(-1,1)), sonra döndürme.
 * Döndürülünce kesilmemesi için viewBox geniş tutulur.
 */
export const ShapeSvg: React.FC<{ shape: ShapeId; angle?: number; mirror?: boolean; size?: number; color?: string }> = ({
  shape,
  angle = 0,
  mirror = false,
  size = 200,
  color = '#e2e8f0',
}) => {
  const cells = SHAPES[shape];
  const xs = cells.map(([x]) => x);
  const ys = cells.map(([, y]) => y);
  const cx = ((Math.min(...xs) + Math.max(...xs) + 1) / 2) * CELL;
  const cy = ((Math.min(...ys) + Math.max(...ys) + 1) / 2) * CELL;
  const R = 70;
  return (
    <svg viewBox={`${-R} ${-R} ${2 * R} ${2 * R}`} width={size} height={size} aria-hidden>
      {/* SVG dönüşümleri sağdan sola uygulanır: önce ortala, sonra yansıt, sonra döndür */}
      <g transform={`rotate(${angle}) scale(${mirror ? -1 : 1}, 1) translate(${-cx}, ${-cy})`}>
        {cells.map(([x, y]) => (
          <rect key={`${x}-${y}`} x={x * CELL} y={y * CELL} width={CELL} height={CELL} fill={color} stroke="#0f172a" strokeWidth={2} />
        ))}
      </g>
    </svg>
  );
};
