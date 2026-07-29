'use client';

import React, { useState } from 'react';

export default function CollectionsPage() {
  const collections = [
    {
      id: 'col-001',
      name: 'Önkormányzatok & Hivatalok',
      description: 'Fejér vármegyei megyei és települési önkormányzatok hivatalos weboldalai.',
      count: 42,
    },
    {
      id: 'col-002',
      name: 'Helyi Sajtó & Média',
      description: 'Fejér megyei hírportálok, helyi lapok és médiatartalmak archívuma.',
      count: 18,
    },
    {
      id: 'col-003',
      name: 'Kulturális & Könyvtári Örökség',
      description: 'Múzeumok, színházak, helytörténeti gyűjtemények és könyvtári portálok.',
      count: 27,
    },
  ];

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      <div>
        <h1 style={{ fontSize: '2.2rem', marginBottom: '0.5rem', background: 'var(--accent-gradient)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
          Kurátori Tematikus Gyűjtemények
        </h1>
        <p style={{ color: 'var(--text-secondary)' }}>
          Böngésszen a Vörösmarty Mihály Könyvtár kurátorai által összeállított tematikus webarchívum kategóriák között.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '1.5rem' }}>
        {collections.map((col) => (
          <div key={col.id} className="glass-card" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
            <div>
              <span className="badge badge-blue" style={{ marginBottom: '0.75rem' }}>{col.count} webhely</span>
              <h2 style={{ fontSize: '1.3rem', marginBottom: '0.5rem' }}>{col.name}</h2>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem' }}>{col.description}</p>
            </div>
            <div style={{ marginTop: '1.5rem' }}>
              <a href={`/?category=${encodeURIComponent(col.name)}`} className="btn-secondary" style={{ width: '100%', textAlign: 'center', display: 'block', padding: '0.5rem' }}>
                Gyűjtemény böngészése ➔
              </a>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
