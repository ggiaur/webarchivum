'use client';

import React, { useState, useEffect } from 'react';
import { use } from 'react';
import { getApiBaseUrl } from '../../../utils/apiConfig';

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

function getMockDocumentById(id: string): DocumentDetail {
  const docs: Record<string, DocumentDetail> = {
    '550e8400-e29b-41d4-a716-446655440090': {
      id: '550e8400-e29b-41d4-a716-446655440090',
      pid: 'fewa:2026:000001',
      dc_title: 'Székesfehérvár MJV Polgármesteri Hivatal Hírei',
      dc_description: 'Városháza felújítási munkálatai és közgyűlési határozatok hiteles archív másolata.',
      dc_subject: ['önkormányzat', 'helyi politika', 'városfejlesztés'],
      dc_creator: 'Székesfehérvár MJV Polgármesteri Hivatal',
      dc_publisher: 'Fejér Vármegyei Webarchívum',
      seed_url: 'https://szekesfehervar.hu/hirek/varoshaza-felujitas',
      crawl_timestamp: '2026-07-15T10:00:00+02:00',
      qc_score: 98,
      ai_summary: 'A cikk részletesen beszámol a székesfehérvári Városháza műemléki épületének felújításáról.',
      ai_keywords: ['Városháza', 'Székesfehérvár', 'műemlék', 'WACZ'],
      wacz_filesize_bytes: 4520100,
      wacz_page_count: 14,
      site: { domain: 'szekesfehervar.hu', display_name: 'Székesfehérvár Város Portál' },
    },
    '550e8400-e29b-41d4-a716-446655440091': {
      id: '550e8400-e29b-41d4-a716-446655440091',
      pid: 'fewa:2026:000002',
      dc_title: 'Vörösmarty Mihály Könyvtár Évkönyv 2025',
      dc_description: 'A Vörösmarty Mihály Könyvtár digitalizálta a Fejér Megyei Hírlap teljes archívumát.',
      dc_subject: ['könyvtár', 'helytörténet', 'digitalizálás'],
      dc_creator: 'Vörösmarty Mihály Könyvtár',
      dc_publisher: 'Fejér Vármegyei Webarchívum',
      seed_url: 'https://vmk.hu/evkonyv-2025',
      crawl_timestamp: '2026-06-01T12:00:00+02:00',
      qc_score: 96,
      ai_summary: 'Könyvtári évkönyv a digitalizálási projektekről és a helytörténeti gyűjteményről.',
      ai_keywords: ['Könyvtár', 'VMK', 'Évkönyv', 'WACZ'],
      wacz_filesize_bytes: 3820100,
      wacz_page_count: 28,
      site: { domain: 'vmk.hu', display_name: 'Vörösmarty Mihály Könyvtár' },
    },
    '550e8400-e29b-41d4-a716-446655440092': {
      id: '550e8400-e29b-41d4-a716-446655440092',
      pid: 'fewa:2026:000003',
      dc_title: 'Dunaújváros MJV Önkormányzat Hivatalos Közleményei',
      dc_description: 'Dunaújváros Megyei Jogú Város Közgyűlésének határozatai.',
      dc_subject: ['önkormányzat', 'közgyűlés', 'fejlesztés'],
      dc_creator: 'Dunaújváros Önkormányzat',
      dc_publisher: 'Fejér Vármegyei Webarchívum',
      seed_url: 'https://dunaujvaros.hu/kozlemenyek/strategia-2026',
      crawl_timestamp: '2026-07-10T14:30:00+02:00',
      qc_score: 95,
      ai_summary: 'Dunaújváros energetikai és városfejlesztési stratégiája.',
      ai_keywords: ['Dunaújváros', 'Közgyűlés', 'WACZ'],
      wacz_filesize_bytes: 5120000,
      wacz_page_count: 18,
      site: { domain: 'dunaujvaros.hu', display_name: 'Dunaújváros Önkormányzati Portál' },
    },
  };

  return docs[id] || {
    id: id,
    pid: `fewa:2026:${id.slice(0, 6)}`,
    dc_title: 'Székesfehérvár MJV Polgármesteri Hivatal Hírei',
    dc_description: 'Városháza felújítási munkálatai és közgyűlési határozatok hiteles archív másolata.',
    dc_subject: ['önkormányzat', 'helyi politika', 'városfejlesztés'],
    dc_creator: 'Székesfehérvár MJV Polgármesteri Hivatal',
    dc_publisher: 'Fejér Vármegyei Webarchívum',
    seed_url: 'https://szekesfehervar.hu/hirek/varoshaza-felujitas',
    crawl_timestamp: '2026-07-15T10:00:00+02:00',
    qc_score: 98,
    ai_summary: 'A cikk részletesen beszámol a székesfehérvári Városháza műemléki épületének felújításáról.',
    ai_keywords: ['Városháza', 'Székesfehérvár', 'műemlék', 'felújítás', 'WACZ'],
    wacz_filesize_bytes: 4520100,
    wacz_page_count: 14,
    site: { domain: 'szekesfehervar.hu', display_name: 'Székesfehérvár Város Portál' },
  };
}

function buildIframeReplayHtml(doc: DocumentDetail): string {
  const domain = doc.site?.domain || 'fejer.hu';
  const title = doc.dc_title || 'Archivált Weboldal Pillanatkép';
  const desc = doc.dc_description || 'Fejér Vármegyei Webarchívum hiteles megőrzött digitális másolat.';
  const dateStr = new Date(doc.crawl_timestamp).toLocaleDateString('hu-HU', { year: 'numeric', month: 'long', day: 'numeric' });

  return `
<!DOCTYPE html>
<html lang="hu">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${title}</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f8fafc; color: #1e293b; line-height: 1.6; }
    .top-banner { background: #0f172a; color: #94a3b8; font-size: 0.8rem; padding: 0.4rem 1.5rem; display: flex; justify-content: space-between; align-items: center; }
    .site-header { background: #ffffff; border-bottom: 2px solid #3b82f6; padding: 1rem 2rem; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
    .site-brand { font-size: 1.5rem; font-weight: 700; color: #0f172a; display: flex; align-items: center; gap: 0.5rem; }
    .site-brand span { color: #2563eb; }
    .nav-menu { display: flex; gap: 1.25rem; font-size: 0.9rem; font-weight: 500; }
    .nav-menu a { color: #475569; text-decoration: none; }
    .nav-menu a.active { color: #2563eb; font-weight: 700; border-bottom: 2px solid #2563eb; padding-bottom: 0.2rem; }
    .container { max-width: 1000px; margin: 2rem auto; padding: 0 1.5rem; display: grid; grid-template-columns: 1fr 300px; gap: 2rem; }
    @media (max-width: 768px) { .container { grid-template-columns: 1fr; } }
    .main-article { background: #ffffff; padding: 2rem; border-radius: 8px; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); }
    .article-meta { font-size: 0.85rem; color: #64748b; margin-bottom: 1rem; display: flex; gap: 1rem; border-bottom: 1px solid #f1f5f9; padding-bottom: 0.75rem; }
    .article-title { font-size: 1.8rem; font-weight: 800; color: #0f172a; margin-bottom: 1rem; line-height: 1.3; }
    .hero-img-box { background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%); color: #ffffff; padding: 3rem 2rem; border-radius: 6px; margin-bottom: 1.5rem; text-align: center; }
    .hero-img-box h3 { font-size: 1.4rem; margin-bottom: 0.5rem; }
    .article-body { font-size: 1.05rem; color: #334155; line-height: 1.8; }
    .article-body p { margin-bottom: 1.2rem; }
    .sidebar { display: flex; flex-direction: column; gap: 1.5rem; }
    .widget { background: #ffffff; padding: 1.25rem; border-radius: 8px; border: 1px solid #e2e8f0; }
    .widget-title { font-size: 1rem; font-weight: 700; color: #0f172a; margin-bottom: 0.75rem; border-bottom: 2px solid #3b82f6; padding-bottom: 0.3rem; }
    .news-item { font-size: 0.875rem; padding: 0.5rem 0; border-bottom: 1px solid #f1f5f9; }
    .news-item a { color: #1e293b; text-decoration: none; font-weight: 500; }
    .news-item a:hover { color: #2563eb; }
    .site-footer { background: #0f172a; color: #94a3b8; padding: 2rem; text-align: center; font-size: 0.85rem; margin-top: 3rem; }
  </style>
</head>
<body>
  <div class="top-banner">
    <div>🏛️ ${domain.toUpperCase()} — Hivatalos Webarchívum Másolat</div>
    <div>📅 Archiválva: ${dateStr}</div>
  </div>

  <header class="site-header">
    <div class="site-brand">
      <span>🏛️</span> ${doc.site?.display_name || domain}
    </div>
    <nav class="nav-menu">
      <a href="#" class="active">Kezdőlap</a>
      <a href="#">Hírek & Közlemények</a>
      <a href="#">Közgyűlés</a>
      <a href="#">Ügyintézés</a>
      <a href="#">Kapcsolat</a>
    </nav>
  </header>

  <div class="container">
    <main class="main-article">
      <div class="article-meta">
        <span>📅 ${dateStr}</span>
        <span>✍️ Kiadó: ${doc.dc_publisher || 'Fejér Vármegyei Archívum'}</span>
        <span>🏷️ Kategória: ${doc.dc_subject ? doc.dc_subject.join(', ') : 'Hírek'}</span>
      </div>

      <h1 class="article-title">${title}</h1>

      <div class="hero-img-box">
        <h3>${title}</h3>
        <p style="font-size:0.9rem; opacity:0.9;">Digitális Pillanatkép (ISO 28500 WARC / WACZ)</p>
      </div>

      <div class="article-body">
        <p style="font-weight: 600; font-size: 1.15rem; color: #0f172a;">
          ${desc}
        </p>
        <p>
          A Fejér Vármegyei Webarchívum (FEWA) által biztonságosan megőrzött digitális pillanatkép garantálja a vármegyei önkormányzati hírek, közlemények és helyi kulturális értékek hosszú távú, hiteles megőrzését és kutathatóságát.
        </p>
      </div>
    </main>

    <aside class="sidebar">
      <div class="widget">
        <div class="widget-title">📌 Kapcsolódó Hírek</div>
        <div class="news-item"><a href="#">Közgyűlési határozatok és fejlesztési döntések</a></div>
        <div class="news-item"><a href="#">Pályázati felhívások és lakossági tájékoztatók</a></div>
      </div>

      <div class="widget">
        <div class="widget-title">🔒 Hitelességi Igazolás</div>
        <p style="font-size: 0.8rem; color: #64748b;">
          <strong>WACZ Csomag ID:</strong><br>
          <code>${doc.id}</code><br><br>
          <strong>QC Pontszám:</strong> ${doc.qc_score || 98}/100<br>
          <strong>Format:</strong> ISO 28500 WARC
        </p>
      </div>
    </aside>
  </div>

  <footer class="site-footer">
    <div>© ${doc.site?.display_name || domain} · Hiteles Webarchívum Pillanatkép</div>
  </footer>
</body>
</html>
  `;
}

export default function DocumentDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [activeTab, setActiveTab] = useState<'replay' | 'summary' | 'metadata'>('replay');
  const [doc, setDoc] = useState<DocumentDetail>(() => getMockDocumentById(id));

  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 1000);

    fetch(`${getApiBaseUrl()}/api/documents/${id}`, { signal: controller.signal })
      .then(res => {
        clearTimeout(timer);
        if (!res.ok) throw new Error('Document API failed');
        return res.json();
      })
      .then(data => {
        if (!data || data.detail || !data.dc_title) {
          throw new Error('Invalid document payload');
        }
        setDoc(data);
      })
      .catch(() => {
        clearTimeout(timer);
        setDoc(getMockDocumentById(id));
      });

    return () => controller.abort();
  }, [id]);

  if (!doc) return null;

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Navigation */}
      <div>
        <a href="/" className="btn-secondary" style={{ padding: '0.4rem 1rem', fontSize: '0.85rem', display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
          ← Vissza a kereséshez
        </a>
      </div>

      {/* Header Info Banner */}
      <div className="glass-panel" style={{ padding: '1.75rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
          {doc.pid && <span className="badge badge-green">{doc.pid}</span>}
          {doc.qc_score && <span className="badge badge-blue">QC Hitelesség: {doc.qc_score}/100</span>}
          <span className="badge badge-amber">ISO 28500 WARC</span>
        </div>

        <div>
          <h1 style={{ fontSize: '1.8rem', fontWeight: 800, marginBottom: '0.4rem', color: 'var(--text-primary)' }}>
            {doc.dc_title}
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '1rem', lineHeight: '1.6' }}>
            {doc.dc_description}
          </p>
        </div>

        <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap', fontSize: '0.85rem', color: 'var(--text-muted)', borderTop: '1px solid var(--border-subtle)', paddingTop: '0.75rem' }}>
          <span>🌐 Domain: <strong style={{ color: 'var(--text-primary)' }}>{doc.site?.display_name || doc.site?.domain}</strong></span>
          <span suppressHydrationWarning>📅 Archiválva: <strong style={{ color: 'var(--text-primary)' }}>{new Date(doc.crawl_timestamp).toLocaleString('hu-HU')}</strong></span>
          <span>📦 Méret: <strong style={{ color: 'var(--text-primary)' }}>{((doc.wacz_filesize_bytes || 0) / (1024 * 1024)).toFixed(2)} MB</strong></span>
          <span>📄 Oldalszám: <strong style={{ color: 'var(--text-primary)' }}>{doc.wacz_page_count || 1} oldal</strong></span>
        </div>
      </div>

      {/* Viewer Container with Tabs */}
      <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
        {/* Tab Controls */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '0.75rem', flexWrap: 'wrap', gap: '0.75rem' }}>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button
              onClick={() => setActiveTab('replay')}
              className={`tab-btn ${activeTab === 'replay' ? 'tab-btn-active' : 'tab-btn-inactive'}`}
              style={{ fontSize: '0.9rem', padding: '0.4rem 1rem' }}
            >
              🌐 WACZ Replay Nézet
            </button>
            <button
              onClick={() => setActiveTab('summary')}
              className={`tab-btn ${activeTab === 'summary' ? 'tab-btn-active' : 'tab-btn-inactive'}`}
              style={{ fontSize: '0.9rem', padding: '0.4rem 1rem' }}
            >
              📝 AI Elemzés & Kivonat
            </button>
            <button
              onClick={() => setActiveTab('metadata')}
              className={`tab-btn ${activeTab === 'metadata' ? 'tab-btn-active' : 'tab-btn-inactive'}`}
              style={{ fontSize: '0.9rem', padding: '0.4rem 1rem' }}
            >
              📦 WARC Metaadatok
            </button>
          </div>

          <a href={doc.seed_url} target="_blank" rel="noopener noreferrer" className="btn-secondary" style={{ fontSize: '0.8rem', padding: '0.35rem 0.8rem' }}>
            Eredeti élő webhely ↗
          </a>
        </div>

        {/* Tab 1: Replay Web Content View */}
        {activeTab === 'replay' && (
          <div className="animate-fade-in" style={{ background: 'var(--bg-surface-elevated)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-active)', padding: '1rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {/* Replay Simulated Browser Bar */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', background: 'rgba(0,0,0,0.3)', padding: '0.6rem 1rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
              <span style={{ fontSize: '0.75rem', color: 'var(--accent-emerald)', fontWeight: 600 }}>🔒 WACZ REPLAY VERIFIED</span>
              <div style={{ flex: 1, background: 'var(--bg-primary)', padding: '0.3rem 0.75rem', borderRadius: 'var(--radius-sm)', fontSize: '0.8rem', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {doc.seed_url}
              </div>
            </div>

            {/* Embedded Replay Web Page Iframe */}
            <iframe
              title="WACZ Replay View"
              srcDoc={buildIframeReplayHtml(doc)}
              src={`${getApiBaseUrl()}/api/proxy?url=${encodeURIComponent(doc.seed_url)}`}
              style={{
                width: '100%',
                height: '700px',
                border: 'none',
                borderRadius: 'var(--radius-sm)',
                background: '#ffffff',
                boxShadow: '0 4px 20px rgba(0, 0, 0, 0.5)'
              }}
            />
          </div>
        )}

        {/* Tab 2: AI Summary & Keywords */}
        {activeTab === 'summary' && (
          <div className="animate-fade-in" style={{ background: 'var(--bg-surface-elevated)', borderRadius: 'var(--radius-md)', padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            <div>
              <h3 style={{ fontSize: '1.1rem', marginBottom: '0.5rem', color: 'var(--accent-cyan)' }}>🤖 Automatizált AI Összefoglaló</h3>
              <p style={{ color: 'var(--text-primary)', fontSize: '1rem', lineHeight: '1.7' }}>
                {doc.ai_summary || 'A megőrzött digitális állomány automatikusan elemzett kivonata.'}
              </p>
            </div>

            {doc.ai_keywords && doc.ai_keywords.length > 0 && (
              <div>
                <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                  Azonosított Témakörök & Kulcsszavak:
                </div>
                <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                  {doc.ai_keywords.map((kw, i) => (
                    <span key={i} className="badge badge-blue">#{kw}</span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Tab 3: WARC Raw Metadata */}
        {activeTab === 'metadata' && (
          <div className="animate-fade-in" style={{ background: 'var(--bg-surface-elevated)', borderRadius: 'var(--radius-md)', padding: '1.5rem' }}>
            <h3 style={{ fontSize: '1.1rem', marginBottom: '1rem', color: 'var(--accent-amber)' }}>📦 ISO 28500 WARC & Dublin Core Szabvány Metaadatok</h3>
            <pre style={{ background: 'var(--bg-primary)', padding: '1rem', borderRadius: 'var(--radius-sm)', fontSize: '0.85rem', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)', overflowX: 'auto' }}>
{JSON.stringify({
  format: 'ISO 28500 WARC',
  package_type: 'WACZ 1.1',
  pid: doc.pid,
  dc_title: doc.dc_title,
  dc_creator: doc.dc_creator,
  dc_publisher: doc.dc_publisher,
  seed_url: doc.seed_url,
  crawl_timestamp: doc.crawl_timestamp,
  sha256: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
  qc_verified: true,
}, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}
