'use client';

import React, { useState, useEffect } from 'react';
import { use } from 'react';

interface DocumentDetail {
  id: string;
  pid?: string;
  dc_title?: string;
  dc_description?: string;
  dc_subject?: string[];
  dc_creator?: string;
  dc_publisher?: string;
  seed_url: string;
  crawl_timestamp: string;
  qc_score?: number;
  ai_summary?: string;
  ai_keywords?: string[];
  wacz_filesize_bytes?: number;
  wacz_page_count?: number;
  site?: {
    domain: string;
    display_name: string;
  };
}

export default function DocumentDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [doc, setDoc] = useState<DocumentDetail | null>(null);

  useEffect(() => {
    fetch(`http://localhost:8000/api/documents/${id}`)
      .then(res => res.json())
      .then(data => setDoc(data))
      .catch(() => {
        // Fallback mock detail
        setDoc({
          id: id,
          pid: 'fewa:2026:000001',
          dc_title: 'Székesfehérvár MJV Polgármesteri Hivatal Hírei',
          dc_description: 'Városháza felújítási munkálatai és közgyűlési határozatok.',
          dc_subject: ['helyi politika', 'városfejlesztés'],
          dc_creator: 'Székesfehérvár MJV',
          dc_publisher: 'Székesfehérvár MJV Polgármesteri Hivatal',
          seed_url: 'https://szekesfehervar.hu/hirek/varoshaza-felujitas',
          crawl_timestamp: '2026-07-15T10:00:00+02:00',
          qc_score: 98,
          ai_summary: 'A cikk beszámol a székesfehérvári Városháza műemléki felújításának 2. üteméről.',
          ai_keywords: ['Városháza', 'Székesfehérvár', 'műemlék', 'felújítás'],
          wacz_filesize_bytes: 4520100,
          wacz_page_count: 14,
          site: {
            domain: 'szekesfehervar.hu',
            display_name: 'Székesfehérvár Város Portál',
          },
        });
      });
  }, [id]);

  if (!doc) return <div style={{ padding: '3rem', textAlign: 'center' }}>Betöltés...</div>;

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      {/* Back button */}
      <div>
        <a href="/" className="btn-secondary" style={{ padding: '0.4rem 1rem', fontSize: '0.85rem' }}>
          ← Vissza a kereséshez
        </a>
      </div>

      {/* Header */}
      <div className="glass-panel" style={{ padding: '2rem' }}>
        <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.75rem' }}>
          {doc.pid && <span className="badge badge-green">{doc.pid}</span>}
          {doc.qc_score && <span className="badge badge-blue">QC Score: {doc.qc_score}/100</span>}
        </div>

        <h1 style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>{doc.dc_title}</h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: '1.05rem', marginBottom: '1rem' }}>{doc.dc_description}</p>

        <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
          <span>🌐 Domain: <strong>{doc.site?.domain}</strong></span>
          <span>📅 Archiválva: <strong>{new Date(doc.crawl_timestamp).toLocaleString('hu-HU')}</strong></span>
          <span>📦 Méret: <strong>{((doc.wacz_filesize_bytes || 0) / (1024 * 1024)).toFixed(2)} MB</strong></span>
          <span>📄 Oldalszám: <strong>{doc.wacz_page_count || 1}</strong></span>
        </div>
      </div>

      {/* Replay Viewer Frame */}
      <div className="glass-panel" style={{ padding: '1rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '0.75rem' }}>
          <h2 style={{ fontSize: '1.1rem' }}>🌐 Interaktív Replay Nézet (WACZ Megjelenítő)</h2>
          <a href={doc.seed_url} target="_blank" rel="noopener noreferrer" className="btn-secondary" style={{ fontSize: '0.8rem', padding: '0.3rem 0.8rem' }}>
            Eredeti élő webhely nyitása ↗
          </a>
        </div>

        {/* Simulated Replay Web Viewer */}
        <div style={{ width: '100%', height: '500px', background: '#ffffff', borderRadius: 'var(--radius-md)', color: '#000', padding: '2rem', overflowY: 'auto' }}>
          <header style={{ borderBottom: '2px solid #333', paddingBottom: '1rem', marginBottom: '1.5rem' }}>
            <h1 style={{ fontSize: '1.8rem', color: '#1a202c' }}>{doc.dc_title}</h1>
            <div style={{ color: '#718096', fontSize: '0.85rem' }}>Eredeti URL: {doc.seed_url}</div>
          </header>
          <div style={{ fontSize: '1.05rem', lineHeight: '1.8', color: '#2d3748' }}>
            <p style={{ marginBottom: '1rem' }}>
              Ez a bejegyzés a Fejér Vármegyei Webarchívum (FEWA) által megőrzött eredeti digitális pillanatkép hiteles Replay másolata.
            </p>
            <p style={{ marginBottom: '1rem' }}>
              {doc.dc_description} A felújítási munkálatok során a műemléki előírások teljes mértékben betartásra kerülnek.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
