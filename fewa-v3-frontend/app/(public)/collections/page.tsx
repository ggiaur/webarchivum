'use client';

import React from 'react';

export default function CollectionsPage() {
  const collections = [
    {
      id: 'col-001',
      icon: '🏛️',
      name: 'Önkormányzatok & Hivatalok',
      description: 'Fejér vármegyei megyei és települési önkormányzatok hivatalos weboldalai.',
      count: 42,
      gradient: 'linear-gradient(135deg, rgba(59, 130, 246, 0.15) 0%, rgba(6, 182, 212, 0.15) 100%)',
      borderColor: 'rgba(59, 130, 246, 0.3)',
      badgeColor: 'badge-blue',
    },
    {
      id: 'col-002',
      icon: '📰',
      name: 'Helyi Sajtó & Média',
      description: 'Fejér megyei hírportálok, helyi lapok és médiatartalmak archívuma.',
      count: 18,
      gradient: 'linear-gradient(135deg, rgba(245, 158, 11, 0.15) 0%, rgba(244, 63, 94, 0.15) 100%)',
      borderColor: 'rgba(245, 158, 11, 0.3)',
      badgeColor: 'badge-amber',
    },
    {
      id: 'col-003',
      icon: '📚',
      name: 'Kulturális & Könyvtári Örökség',
      description: 'Múzeumok, színházak, helytörténeti gyűjtemények és könyvtári portálok.',
      count: 27,
      gradient: 'linear-gradient(135deg, rgba(16, 185, 129, 0.15) 0%, rgba(6, 182, 212, 0.15) 100%)',
      borderColor: 'rgba(16, 185, 129, 0.3)',
      badgeColor: 'badge-green',
    },
  ];

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

      {/* Cards Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: '2rem' }}>
        {collections.map((col) => (
          <div key={col.id} className="glass-card" style={{
            background: col.gradient,
            border: `1px solid ${col.borderColor}`,
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
                <span className={`badge ${col.badgeColor}`} style={{ fontSize: '0.85rem', padding: '0.35rem 0.75rem' }}>
                  {col.count} webhely
                </span>
              </div>
              <h2 style={{ fontSize: '1.45rem', fontWeight: 700, color: '#f8fafc', marginBottom: '0.6rem' }}>
                {col.name}
              </h2>
              <p style={{ color: '#cbd5e1', fontSize: '0.98rem', lineHeight: '1.6' }}>
                {col.description}
              </p>
            </div>
            <div style={{ marginTop: '2rem' }}>
              <a href={`/?category=${encodeURIComponent(col.name)}`} className="btn-primary" style={{
                width: '100%',
                justifyContent: 'center',
                padding: '0.75rem',
                fontSize: '0.95rem'
              }}>
                Gyűjtemény böngészése ➔
              </a>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
