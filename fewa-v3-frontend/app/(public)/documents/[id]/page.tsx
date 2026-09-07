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

const MAX_REPLAY_RETRIES = 4;

export default function DocumentDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [activeTab, setActiveTab] = useState<'replay' | 'summary' | 'metadata'>('replay');
  const [state, setState] = useState<LoadState>({ status: 'loading' });
  const [rwpReady, setRwpReady] = useState(false);
  const [retryKey, setRetryKey] = useState(0);
  const [retryCount, setRetryCount] = useState(0);
  const replayContainerRef = React.useRef<HTMLDivElement>(null);

  // Regression fix for 2026-08-03, real root cause found via direct
  // instrumentation (captured Response.fromServiceWorker() on every
  // /replay/ request in a fresh browser context): mounting
  // <replay-web-page> is what makes ui.js kick off Service Worker
  // registration in the first place (its connectedCallback triggers it) —
  // an EARLIER fix gated mounting on "SW already active", which is a
  // deadlock (registration never starts because the element that starts it
  // never mounts). Mounting must be unconditional (as soon as ui.js itself
  // has loaded). On a brand-new visit, the iframe's OWN first navigation to
  // /replay/?source=... can start before that registration has reached
  // 'activated', so it bypasses the worker entirely and lands on Next.js's
  // plain 404 page instead of being served by the SW (confirmed: identical
  // requests issued after the SW is already active come back
  // fromServiceWorker()=true with the real archived content; the exact same
  // request issued before come back fromServiceWorker()=false with a 404).
  // So this polls the embedded iframe repeatedly (not just once — an
  // earlier version checked a single time after a fixed delay, and if that
  // one check landed before the failure text had even rendered yet, it
  // wrongly concluded success and never looked again) and forces a full
  // remount via the `key` prop the moment a real 404 is seen, giving the
  // SW registration — already progressing in the background since the very
  // first mount — another shot at being active before the next attempt.
  useEffect(() => {
    if (!rwpReady || retryCount >= MAX_REPLAY_RETRIES) return;
    let settled = false;
    const pollMs = 700;
    const maxWaitMs = 7000;
    let elapsed = 0;
    const iv = setInterval(() => {
      if (settled) return;
      elapsed += pollMs;
      // <replay-web-page> renders its iframe inside its OWN shadow root —
      // a plain querySelector from outside never pierces that boundary and
      // silently returns null forever, which is why this polling loop
      // previously ran to completion every time without ever detecting a
      // failure (confirmed directly: the effect always fell through to the
      // maxWaitMs branch, never the failed branch).
      const rwpEl = replayContainerRef.current?.querySelector('replay-web-page');
      const iframe = rwpEl?.shadowRoot?.querySelector('iframe') as HTMLIFrameElement | null;
      let text = '';
      try {
        text = iframe?.contentDocument?.body?.textContent || '';
      } catch {
        // Cross-origin or not-yet-accessible — treat as "can't tell yet", keep polling.
      }
      const failed = text.includes('could not be found');
      const loaded = text.trim().length > 0 && !failed;
      if (failed) {
        settled = true;
        clearInterval(iv);
        setRetryCount((c) => c + 1);
        setRetryKey((k) => k + 1);
      } else if (loaded || elapsed >= maxWaitMs) {
        settled = true;
        clearInterval(iv);
      }
    }, pollMs);
    return () => { settled = true; clearInterval(iv); };
  }, [rwpReady, retryKey, retryCount]);

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
  const isHeld = doc.publication_decision === 'HOLD_REJECT' || doc.remediation_status === 'HELD_UNRECOVERABLE';
  const isReleased = !isHeld && (doc.publication_decision === 'PASS_RELEASE' || doc.remediation_status === 'RELEASED_CLEAN' || doc.remediation_status === 'RELEASED_REMEDIATED' || !!doc.wacz_url);
  const directReplayTarget = doc.replay_url || (doc.wacz_url ? `/replay-loading?target=${encodeURIComponent(`/replay/?source=${encodeURIComponent(`${typeof window !== 'undefined' ? window.location.origin : ''}${doc.wacz_url}`)}&url=${encodeURIComponent(doc.seed_url)}`)}` : null);

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
        onReady={() => { setTimeout(() => window.dispatchEvent(new Event('load')), 50); setRwpReady(true); }}
        onLoad={() => { setTimeout(() => window.dispatchEvent(new Event('load')), 50); setRwpReady(true); }}
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
          {isHeld ? (
            <span className="badge badge-rose" id="status-badge-hold" style={{ background: 'rgba(244, 63, 94, 0.2)', color: '#f43f5e', border: '1px solid #f43f5e', fontWeight: 700 }}>
              ⛔ KIADVÁNY-TARTÁS (HOLD_REJECT)
            </span>
          ) : (
            <span className="badge badge-emerald" id="status-badge-release" style={{ background: 'rgba(16, 185, 129, 0.2)', color: '#10b981', border: '1px solid #10b981', fontWeight: 700 }}>
              🟢 KIADVA (PASS_RELEASE)
            </span>
          )}
          {doc.remediation_status && (
            <span className="badge badge-blue" id="status-badge-remediation">
              {doc.remediation_status}
            </span>
          )}
          {doc.remediation_attempts != null && (
            <span className="badge badge-amber" id="status-badge-attempts">
              {doc.remediation_attempts} kísérlet
            </span>
          )}
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

        {/* Human-readable release/hold reason & remediation summary */}
        <div id="remediation-summary-panel" style={{
          padding: '0.85rem 1.1rem',
          borderRadius: 'var(--radius-md)',
          fontSize: '0.88rem',
          background: isHeld ? 'rgba(225, 29, 72, 0.12)' : 'rgba(16, 185, 129, 0.12)',
          border: `1px solid ${isHeld ? '#f43f5e' : '#10b981'}`,
          color: 'var(--text-primary)',
          display: 'flex',
          flexDirection: 'column',
          gap: '0.4rem'
        }}>
          <div style={{ fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.5rem', color: isHeld ? '#f87171' : '#34d399' }}>
            {isHeld ? '⛔ Kiadvány-tartás indoka (HOLD_REJECT):' : '🟢 Kiadási állapot & minőségigazolás (PASS_RELEASE):'}
          </div>
          <div id="remediation-reason-text" style={{ lineHeight: '1.5' }}>
            {doc.remediation_reason || (isHeld ? 'A kiadvány letiltva (HOLD_REJECT): az archivált oldal nem rögzített erőforrásokat vagy sérült elemeket tartalmaz. A lejátszás zárolva van.' : 'Az archivált oldal WACZ lejátszása igazoltan működőképes és közzétételre engedélyezett (PASS_RELEASE).')}
          </div>
          {isHeld && doc.unresolved_resources && doc.unresolved_resources.length > 0 && (
            <div id="unresolved-resources-list" style={{ marginTop: '0.4rem', fontSize: '0.8rem', color: '#fda4af', background: 'rgba(0,0,0,0.3)', padding: '0.5rem 0.75rem', borderRadius: 'var(--radius-sm)', fontFamily: 'var(--font-mono)' }}>
              <strong>Zárolást kiváltó nem rögzített erőforrások ({doc.unresolved_resources.length}):</strong>
              <ul style={{ margin: '0.25rem 0 0 1.25rem', padding: 0 }}>
                {doc.unresolved_resources.map((resUrl, idx) => (
                  <li key={idx}>{resUrl}</li>
                ))}
              </ul>
            </div>
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

          <div style={{ display: 'flex', gap: '0.5rem' }}>
            {isReleased && directReplayTarget && (
              <a
                id="direct-usable-replay-link"
                href={directReplayTarget}
                target="_blank"
                rel="noopener noreferrer"
                className="btn-secondary"
                style={{ fontSize: '0.8rem', padding: '0.35rem 0.8rem', background: 'var(--accent-emerald)', color: '#000', fontWeight: 700 }}
                title="Megnyitás közvetlenül a ReplayWeb.page saját, teljes oldalas nézetében."
              >
                ⤢ Teljes oldal replay (közvetlen hivatkozás) ↗
              </a>
            )}
            <a href={doc.seed_url} target="_blank" rel="noopener noreferrer" className="btn-secondary" style={{ fontSize: '0.8rem', padding: '0.35rem 0.8rem' }}>
              Eredeti élő webhely ↗
            </a>
          </div>
        </div>

        {/* Tab 1: Real ReplayWeb.page WACZ replay */}
        {activeTab === 'replay' && (
          <div className="animate-fade-in" style={{ background: 'var(--bg-surface-elevated)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-active)', padding: '1rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', background: 'rgba(0,0,0,0.3)', padding: '0.6rem 1rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
              <span style={{ fontSize: '0.75rem', color: isHeld ? '#f43f5e' : 'var(--accent-emerald)', fontWeight: 600 }}>
                {isHeld ? '⛔ KIADVÁNY-TARTÁS (HOLD_REJECT)' : '🔒 WACZ REPLAY (ReplayWeb.page)'}
              </span>
              <div style={{ flex: 1, background: 'var(--bg-primary)', padding: '0.3rem 0.75rem', borderRadius: 'var(--radius-sm)', fontSize: '0.8rem', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {doc.seed_url}
              </div>
              {isReleased && directReplayTarget && (
                <a
                  href={directReplayTarget}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn-secondary"
                  style={{ fontSize: '0.75rem', padding: '0.35rem 0.8rem', whiteSpace: 'nowrap' }}
                  title="Megnyitás a ReplayWeb.page saját, teljes oldalas nézetében."
                >
                  ⤢ Teljes oldal (új fül)
                </a>
              )}
            </div>

            {isHeld ? (
              <div id="hold-rejection-notice" style={{ padding: '3rem 1.5rem', textAlign: 'center', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid #f43f5e', borderRadius: 'var(--radius-md)', display: 'flex', flexDirection: 'column', gap: '1rem', alignItems: 'center' }}>
                <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#f87171' }}>
                  ⛔ Replay Lejátszás Letiltva (HOLD_REJECT)
                </div>
                <p style={{ color: 'var(--text-secondary)', maxWidth: '600px', fontSize: '0.95rem', lineHeight: '1.6', margin: 0 }}>
                  {doc.remediation_reason || 'Ennek a dokumentumnak a közzététele fel van függesztve. Hiányos erőforrások miatt a lejátszás le van tiltva a téves megjelenítés elkerülésére.'}
                </p>
                {doc.unresolved_resources && doc.unresolved_resources.length > 0 && (
                  <div style={{ background: 'var(--bg-primary)', padding: '0.75rem 1rem', borderRadius: 'var(--radius-sm)', fontSize: '0.82rem', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)', textAlign: 'left', maxWidth: '600px', width: '100%', border: '1px solid var(--border-subtle)' }}>
                    <strong style={{ color: '#fda4af' }}>Hiányzó erőforrások:</strong>
                    <ul style={{ margin: '0.3rem 0 0 1.2rem', padding: 0 }}>
                      {doc.unresolved_resources.map((u, i) => <li key={i}>{u}</li>)}
                    </ul>
                  </div>
                )}
              </div>
            ) : !doc.wacz_url ? (
              <div style={{ padding: '3rem 1rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
                Ehhez a dokumentumhoz még nincs archivált WACZ állomány.
              </div>
            ) : !rwpReady ? (
              <div style={{ padding: '3rem 1rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
                Replay betöltése…
              </div>
            ) : (
              <div ref={replayContainerRef}>
                <replay-web-page
                  key={retryKey}
                  source={doc.wacz_url}
                  url={doc.seed_url}
                  embed="replayonly"
                  replaybase="/replay/"
                  newWindowBase="/replay/"
                  style={{ width: '100%', height: '700px', display: 'block', borderRadius: 'var(--radius-sm)', overflow: 'hidden', boxShadow: '0 4px 20px rgba(0, 0, 0, 0.5)' }}
                />
              </div>
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
