import React from 'react';

/** Arka planda yavaşça nefes alan kozmik aurora (yalnız dekoratif). */
export const AuroraBackground: React.FC = () => (
  <div className="aurora" aria-hidden>
    <div className="aurora-stars" />
    <div className="aurora-blob a1" />
    <div className="aurora-blob a2" />
    <div className="aurora-blob a3" />
    <div className="aurora-blob a4" />
  </div>
);
