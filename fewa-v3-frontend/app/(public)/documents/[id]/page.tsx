'use client';

import React, { useState, useEffect } from 'react';
import { use } from 'react';
import Script from 'next/script';
import { getApiBaseUrl } from '../../../utils/apiConfig';

declare module 'react' {
  namespace JSX {
    interface IntrinsicElements {
      'replay-web-page': React.DetailedHTMLProps<React.HTMLAttributes<HTMLElement>, HTMLElement> & {
        source?: string;
        url?: string;
        ts?: string;
        embed?: string;
        replaybase?: string;
        newWindowBase?: string;
      };
    }
  }
}

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
  wacz_sha256?: string;
  ai_summary?: string;
  ai_keywords?: string[];
  wacz_filesize_bytes?: number;
  wacz_page_count?: number;
  wacz_url?: string | null;
  site?: {
    domain: string;
    display_name: string;
  };
}

type LoadState = { status: 'loading' } | { status: 'error' } | { status: 'ready'; doc: DocumentDetail };

export default function DocumentDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [activeTab, setActiveTab] = useState<'replay' | 'summary' | 'metadata'>('replay');
  const [state, setState] = useState<LoadState>({ status: 'loading' });
  const [rwpReady, setRwpReady] = useState(false);

  useEffect(() => {
    const controller = new AbortController();

    fetch(`${getApiBaseUrl()}/api/documents/${id}`, { signal: controller.signal })
      .then(res => {
        if (!res.ok) throw new Error(`Document API returned ${res.status}`);
        return res.json();
      })
      .then(data => setState({ status: 'ready', doc: data }))
      .catch(err => {
        if (err.name !== 'AbortError') setState({ status: 'error' });
      });

    return () => controller.abort();
  }, [id]);

  if (state.status === 'loading') {
    return (
      <div className="glass-panel" style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
        Betöltés…
      </div>
    );
  }

  if (state.status === 'error') {
    return (
      <div className="glass-panel" style={{ padding: '2rem', textAlign: 'center', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <div style={{ fontSize: '1.1rem', color: 'var(--text-primary)' }}>
          A dokumentum nem található, vagy még nem publikus.
        </div>
        <a href="/" className="btn-secondary" style={{ padding: '0.4rem 1rem', fontSize: '0.85rem', alignSelf: 'center' }}>
          ← Vissza a kereséshez
        </a>
      </div>
    );
  }

  const doc = state.doc;

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/*
        ReplayWeb.page's SW registration (via the register-service-worker
        package it bundles) waits on `window.addEventListener('load', ...)`,
        evaluated the moment ui.js's module code runs. Loaded via
        `afterInteractive`, ui.js always executes after the real `load`
        event already fired, so that promise never resolves and
        registration hangs forever with no error. Dispatching a synthetic
        `load` event right after ui.js loads unsticks it — safe even if the
        real event already resolved it (Promises only resolve once).
      */}
      <Script
        src="/ui.js"
        strategy="afterInteractive"
        onReady={() => { setRwpReady(true); window.dispatchEvent(new Event('load')); }}
        onLoad={() => { setRwpReady(true); window.dispatchEvent(new Event('load')); }}
      />

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
          {doc.qc_score != null && <span className="badge badge-blue">QC Hitelesség: {doc.qc_score}/100</span>}
          <span className="badge badge-amber">WACZ</span>
        </div>

        <div>
          <h1 style={{ fontSize: '1.8rem', fontWeight: 800, marginBottom: '0.4rem', color: 'var(--text-primary)' }}>
            {doc.dc_title}
          </h1>
          {doc.dc_description && (
            <p style={{ color: 'var(--text-secondary)', fontSize: '1rem', lineHeight: '1.6' }}>
              {doc.dc_description}
            </p>
          )}
        </div>

        <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap', fontSize: '0.85rem', color: 'var(--text-muted)', borderTop: '1px solid var(--border-subtle)', paddingTop: '0.75rem' }}>
          <span>🌐 Domain: <strong style={{ color: 'var(--text-primary)' }}>{doc.site?.display_name || doc.site?.domain}</strong></span>
          {doc.crawl_timestamp && (
            <span suppressHydrationWarning>📅 Archiválva: <strong style={{ color: 'var(--text-primary)' }}>{new Date(doc.crawl_timestamp).toLocaleString('hu-HU')}</strong></span>
          )}
          {doc.wacz_filesize_bytes != null && (
            <span>📦 Méret: <strong style={{ color: 'var(--text-primary)' }}>{(doc.wacz_filesize_bytes / (1024 * 1024)).toFixed(2)} MB</strong></span>
          )}
          {doc.wacz_page_count != null && (
            <span>📄 Oldalszám: <strong style={{ color: 'var(--text-primary)' }}>{doc.wacz_page_count} oldal</strong></span>
          )}
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

        {/* Tab 1: Real ReplayWeb.page WACZ replay */}
        {activeTab === 'replay' && (
          <div className="animate-fade-in" style={{ background: 'var(--bg-surface-elevated)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-active)', padding: '1rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', background: 'rgba(0,0,0,0.3)', padding: '0.6rem 1rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
              <span style={{ fontSize: '0.75rem', color: 'var(--accent-emerald)', fontWeight: 600 }}>🔒 WACZ REPLAY (ReplayWeb.page)</span>
              <div style={{ flex: 1, background: 'var(--bg-primary)', padding: '0.3rem 0.75rem', borderRadius: 'var(--radius-sm)', fontSize: '0.8rem', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {doc.seed_url}
              </div>
            </div>

            {!doc.wacz_url ? (
              <div style={{ padding: '3rem 1rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
                Ehhez a dokumentumhoz még nincs archivált WACZ állomány.
              </div>
            ) : !rwpReady ? (
              <div style={{ padding: '3rem 1rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
                Replay betöltése…
              </div>
            ) : (
              <replay-web-page
                source={doc.wacz_url}
                url={doc.seed_url}
                embed="replayonly"
                replaybase="/replay/"
                newWindowBase="/replay/"
                style={{ width: '100%', height: '700px', display: 'block', borderRadius: 'var(--radius-sm)', overflow: 'hidden', boxShadow: '0 4px 20px rgba(0, 0, 0, 0.5)' }}
              />
            )}
          </div>
        )}

        {/* Tab 2: AI Summary & Keywords */}
        {activeTab === 'summary' && (
          <div className="animate-fade-in" style={{ background: 'var(--bg-surface-elevated)', borderRadius: 'var(--radius-md)', padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            <div>
              <h3 style={{ fontSize: '1.1rem', marginBottom: '0.5rem', color: 'var(--accent-cyan)' }}>🤖 Automatizált AI Összefoglaló</h3>
              <p style={{ color: 'var(--text-primary)', fontSize: '1rem', lineHeight: '1.7' }}>
                {doc.ai_summary || 'Ehhez a dokumentumhoz még nem készült AI összefoglaló.'}
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

        {/* Tab 3: Real WARC/Dublin Core metadata */}
        {activeTab === 'metadata' && (
          <div className="animate-fade-in" style={{ background: 'var(--bg-surface-elevated)', borderRadius: 'var(--radius-md)', padding: '1.5rem' }}>
            <h3 style={{ fontSize: '1.1rem', marginBottom: '1rem', color: 'var(--accent-amber)' }}>📦 WACZ & Dublin Core Metaadatok</h3>
            <pre style={{ background: 'var(--bg-primary)', padding: '1rem', borderRadius: 'var(--radius-sm)', fontSize: '0.85rem', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)', overflowX: 'auto' }}>
{JSON.stringify({
  pid: doc.pid,
  dc_title: doc.dc_title,
  dc_creator: doc.dc_creator,
  dc_publisher: doc.dc_publisher,
  seed_url: doc.seed_url,
  crawl_timestamp: doc.crawl_timestamp,
  wacz_sha256: doc.wacz_sha256 ?? null,
  qc_score: doc.qc_score ?? null,
}, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}
