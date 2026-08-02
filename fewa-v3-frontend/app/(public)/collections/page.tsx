'use client';

import React, { useEffect, useState } from 'react';
import { getApiBaseUrl } from '../../utils/apiConfig';

interface CollectionItem {
  id: string;
  icon: string;
  name: string;
  count: number;
}

// Fixed visual treatment per category id — the backend only returns real
// data (id/icon/name/count from site_category_enum + a live COUNT), not
// styling, so the gradient/border/badge mapping stays on the frontend.
const CATEGORY_STYLE: Record<string, { gradient: string; borderColor: string; badgeColor: string }> = {
  kozintézmény: {
    gradient: 'linear-gradient(135deg, rgba(59, 130, 246, 0.15) 0%, rgba(6, 182, 212, 0.15) 100%)',
    borderColor: 'rgba(59, 130, 246, 0.3)',
    badgeColor: 'badge-blue',
  },
  civil: {
    gradient: 'linear-gradient(135deg, rgba(168, 85, 247, 0.15) 0%, rgba(236, 72, 153, 0.15) 100%)',
    borderColor: 'rgba(168, 85, 247, 0.3)',
    badgeColor: 'badge-blue',
  },
  média: {
    gradient: 'linear-gradient(135deg, rgba(245, 158, 11, 0.15) 0%, rgba(244, 63, 94, 0.15) 100%)',
    borderColor: 'rgba(245, 158, 11, 0.3)',
    badgeColor: 'badge-amber',
  },
  vállalkozás: {
    gradient: 'linear-gradient(135deg, rgba(14, 165, 233, 0.15) 0%, rgba(59, 130, 246, 0.15) 100%)',
    borderColor: 'rgba(14, 165, 233, 0.3)',
    badgeColor: 'badge-blue',
  },
  kulturális: {
    gradient: 'linear-gradient(135deg, rgba(16, 185, 129, 0.15) 0%, rgba(6, 182, 212, 0.15) 100%)',
    borderColor: 'rgba(16, 185, 129, 0.3)',
    badgeColor: 'badge-green',
  },
  egyéb: {
    gradient: 'linear-gradient(135deg, rgba(148, 163, 184, 0.15) 0%, rgba(100, 116, 139, 0.15) 100%)',
    borderColor: 'rgba(148, 163, 184, 0.3)',
    badgeColor: 'badge-blue',
  },
};
const DEFAULT_STYLE = CATEGORY_STYLE.egyéb;

export default function CollectionsPage() {
  const [collections, setCollections] = useState<CollectionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    fetch(`${getApiBaseUrl()}/api/collections`)
      .then((res) => {
        if (!res.ok) throw new Error('failed');
        return res.json();
      })
      .then((data) => setCollections(data.collections || []))
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '2.5rem' }}>
      {/* Header Section */}
      <div style={{
        background: 'linear-gradient(135deg, rgba(18, 24, 36, 0.9) 0%, rgba(26, 34, 52, 0.9) 100%)',
        border: '1px solid rgba(255, 255, 255, 0.1)',
        borderRadius: '20px',
        padding: '3rem 2.5rem',
        boxShadow: '0 20px 40px rgba(0, 0, 0, 0.5)'
      }}>
        <span className="badge badge-blue" style={{ marginBottom: '1rem', fontSize: '0.85rem', padding: '0.4rem 0.8rem' }}>
          🏛️ TEMATIKUS KATALÓGUS
        </span>
        <h1 style={{ fontSize: '2.5rem', fontWeight: 800, marginBottom: '0.75rem', color: '#ffffff', letterSpacing: '-0.02em' }}>
          Kurátori Tematikus Gyűjtemények
        </h1>
        <p style={{ color: '#94a3b8', fontSize: '1.1rem', maxWidth: '720px', lineHeight: '1.6' }}>
          Böngésszen a Vörösmarty Mihály Könyvtár szakkurátorai által összeállított tematikus webarchívum kategóriák között.
        </p>
      </div>

      {loading && (
        <div style={{ padding: '2rem', textAlign: 'center', color: '#94a3b8' }}>Betöltés…</div>
      )}
      {!loading && error && (
        <div style={{ padding: '2rem', textAlign: 'center', color: '#94a3b8' }}>
          A gyűjtemények jelenleg nem elérhetők.
        </div>
      )}
      {!loading && !error && collections.length === 0 && (
        <div style={{ padding: '2rem', textAlign: 'center', color: '#94a3b8' }}>
          Még nincs publikált gyűjtemény.
        </div>
      )}

      {/* Cards Grid */}
      {!loading && !error && collections.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: '2rem' }}>
          {collections.map((col) => {
            const style = CATEGORY_STYLE[col.id] || DEFAULT_STYLE;
            return (
              <div key={col.id} className="glass-card" style={{
                background: style.gradient,
                border: `1px solid ${style.borderColor}`,
                borderRadius: '16px',
                padding: '2rem',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                boxShadow: '0 10px 30px rgba(0,0,0,0.3)',
                transition: 'transform 0.25s ease, box-shadow 0.25s ease'
              }}>
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
                    <span style={{ fontSize: '2.5rem' }}>{col.icon}</span>
                    <span className={`badge ${style.badgeColor}`} style={{ fontSize: '0.85rem', padding: '0.35rem 0.75rem' }}>
                      {col.count} webhely
                    </span>
                  </div>
                  <h2 style={{ fontSize: '1.45rem', fontWeight: 700, color: '#f8fafc', marginBottom: '0.6rem' }}>
                    {col.name}
                  </h2>
                </div>
                <div style={{ marginTop: '2rem' }}>
                  <a href={`/?category=${encodeURIComponent(col.id)}`} className="btn-primary" style={{
                    width: '100%',
                    justifyContent: 'center',
                    padding: '0.75rem',
                    fontSize: '0.95rem'
                  }}>
                    Gyűjtemény böngészése ➔
                  </a>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
