'use client';

import React, { useState, useEffect } from 'react';
import { use } from 'react';
import Script from 'next/script';
import { fetchWithAuth } from '../../../../utils/apiConfig';

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
  seed_url: string;
  crawl_timestamp: string;
  lifecycle_status: string;
  qc_score?: number | null;
  wacz_filesize_bytes?: number;
  wacz_page_count?: number;
  wacz_url?: string | null;
  site?: {
    domain: string;
    display_name: string;
  };
}

type LoadState = { status: 'loading' } | { status: 'error' } | { status: 'ready'; doc: DocumentDetail };

// Admin-scoped counterpart of (public)/documents/[id] — that page only
// ever shows 'published' snapshots (by design, for public search), so the
// quality-review queue's replay link pointed nowhere useful: every item
// in that queue is pre-publication. This fetches from /api/admin/documents
// (curator-authenticated, no publish gate) so a curator can actually
// inspect content before deciding accept/reject.
export default function AdminDocumentPreviewPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [activeTab, setActiveTab] = useState<'replay' | 'metadata'>('replay');
  const [state, setState] = useState<LoadState>({ status: 'loading' });
  const [rwpReady, setRwpReady] = useState(false);
  const [retryKey, setRetryKey] = useState(0);
  const [retryCount, setRetryCount] = useState(0);
  const replayContainerRef = React.useRef<HTMLDivElement>(null);

  const [showWithdrawModal, setShowWithdrawModal] = useState(false);
  const [withdrawReason, setWithdrawReason] = useState('');
  const [withdrawSubmitting, setWithdrawSubmitting] = useState(false);
  const [withdrawError, setWithdrawError] = useState<string | null>(null);

  const handleWithdraw = async () => {
    if (!withdrawReason.trim()) return;
    setWithdrawSubmitting(true);
    setWithdrawError(null);
    try {
      const res = await fetchWithAuth(`/api/admin/documents/${id}/withdraw`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: withdrawReason.trim() }),
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Szerver hiba (${res.status})`);
      }
      const updatedDoc = await res.json();
      setState(prev => prev.status === 'ready' ? { status: 'ready', doc: { ...prev.doc, lifecycle_status: updatedDoc.lifecycle_status || 'withdrawn' } } : prev);
      setShowWithdrawModal(false);
      setWithdrawReason('');
    } catch (err: any) {
      setWithdrawError(err.message || 'A visszavonás nem sikerült.');
    } finally {
      setWithdrawSubmitting(false);
    }
  };

  // See (public)/documents/[id]/page.tsx for the full history and the
  // instrumented proof of the root cause: mounting <replay-web-page> is
  // what triggers ui.js's Service Worker registration, so gating mount on
  // "SW already active" is a deadlock. Mount unconditionally, then POLL
  // (not a single delayed check — that variant could look too early, see
  // early observed content, wrongly conclude success, and never look
  // again) the embedded iframe for landing on a real 404 (the SW genuinely
  // wasn't active yet for THIS mount's navigation) and force a remount via
  // the `key` prop, giving the registration — already running in the
  // background since the very first mount — another chance.
  const MAX_REPLAY_RETRIES = 4;
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
      // a plain querySelector from outside never pierces that boundary.
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
    let cancelled = false;

    fetchWithAuth(`/api/admin/documents/${id}`)
      .then(res => {
        if (!res.ok) throw new Error(`Document API returned ${res.status}`);
        return res.json();
      })
      .then(data => { if (!cancelled) setState({ status: 'ready', doc: data }); })
      .catch(() => { if (!cancelled) setState({ status: 'error' }); });

    return () => { cancelled = true; };
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
          A dokumentum nem található.
        </div>
        <a href="/admin/dashboard" className="btn-secondary" style={{ padding: '0.4rem 1rem', fontSize: '0.85rem', alignSelf: 'center' }}>
          ← Vissza a Kurátori Portálhoz
        </a>
      </div>
    );
  }

  const doc = state.doc;

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', padding: '1.5rem' }}>
      {/* See (public)/documents/[id]/page.tsx for why this synthetic 'load'
          dispatch is needed — ReplayWeb.page's SW registration waits on a
          load event that (via afterInteractive) has always already fired. */}
      <Script
        src="/ui.js"
        strategy="afterInteractive"
        onReady={() => { window.dispatchEvent(new Event('load')); setRwpReady(true); }}
        onLoad={() => { window.dispatchEvent(new Event('load')); setRwpReady(true); }}
      />

      <div>
        <a href="/admin/dashboard" className="btn-secondary" style={{ padding: '0.4rem 1rem', fontSize: '0.85rem', display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
          ← Vissza a Kurátori Portálhoz
        </a>
      </div>

      <div className="glass-panel" style={{ padding: '1.75rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem' }}>
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
            <span className={`badge ${doc.lifecycle_status === 'published' ? 'badge-emerald' : doc.lifecycle_status === 'withdrawn' ? 'badge-rose' : 'badge-amber'}`}>
              {doc.lifecycle_status}
            </span>
            {doc.qc_score != null && <span className="badge badge-blue">QC: {doc.qc_score}%</span>}
            {doc.qc_score == null && <span className="badge badge-rose">Nincs QC eredmény</span>}
          </div>
          {doc.lifecycle_status === 'published' && (
            <button
              onClick={() => { setShowWithdrawModal(true); setWithdrawError(null); setWithdrawReason(''); }}
              style={{
                fontSize: '0.85rem', padding: '0.4rem 1rem', background: '#e11d48',
                color: '#fff', border: 'none', borderRadius: '0.375rem', cursor: 'pointer',
                fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '0.4rem'
              }}
            >
              🚫 Dokumentum Visszavonása
            </button>
          )}
        </div>

        <div>
          <h1 style={{ fontSize: '1.8rem', fontWeight: 800, marginBottom: '0.4rem', color: 'var(--text-primary)' }}>
            {doc.dc_title}
          </h1>
        </div>

        <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap', fontSize: '0.85rem', color: 'var(--text-muted)', borderTop: '1px solid var(--border-subtle)', paddingTop: '0.75rem' }}>
          <span>🌐 Domain: <strong style={{ color: 'var(--text-primary)' }}>{doc.site?.display_name || doc.site?.domain}</strong></span>
          {doc.crawl_timestamp && (
            <span suppressHydrationWarning>📅 Archiválva: <strong style={{ color: 'var(--text-primary)' }}>{new Date(doc.crawl_timestamp).toLocaleString('hu-HU')}</strong></span>
          )}
          {doc.wacz_filesize_bytes != null && (
            <span>📦 Méret: <strong style={{ color: 'var(--text-primary)' }}>{(doc.wacz_filesize_bytes / (1024 * 1024)).toFixed(2)} MB</strong></span>
          )}
        </div>
      </div>

      <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
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
              onClick={() => setActiveTab('metadata')}
              className={`tab-btn ${activeTab === 'metadata' ? 'tab-btn-active' : 'tab-btn-inactive'}`}
              style={{ fontSize: '0.9rem', padding: '0.4rem 1rem' }}
            >
              📦 Metaadatok
            </button>
          </div>

          <div style={{ display: 'flex', gap: '0.5rem' }}>
            {doc.wacz_url && (
              <a
                href={`/replay-loading?target=${encodeURIComponent(`/replay/?source=${encodeURIComponent(`${window.location.origin}${doc.wacz_url}`)}&url=${encodeURIComponent(doc.seed_url)}`)}`}
                target="_blank"
                rel="noopener noreferrer"
                className="btn-secondary"
                style={{ fontSize: '0.8rem', padding: '0.35rem 0.8rem' }}
                title="Megnyitás a ReplayWeb.page saját, teljes oldalas nézetében, külön fülön."
              >
                ⤢ Teljes oldal (új fül)
              </a>
            )}
            <a href={doc.seed_url} target="_blank" rel="noopener noreferrer" className="btn-secondary" style={{ fontSize: '0.8rem', padding: '0.35rem 0.8rem' }}>
              Eredeti élő webhely ↗
            </a>
          </div>
        </div>

        {activeTab === 'replay' && (
          <div className="animate-fade-in" style={{ background: 'var(--bg-surface-elevated)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-active)', padding: '1rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {!doc.wacz_url ? (
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

        {activeTab === 'metadata' && (
          <div className="animate-fade-in" style={{ background: 'var(--bg-surface-elevated)', borderRadius: 'var(--radius-md)', padding: '1.5rem' }}>
            <pre style={{ background: 'var(--bg-primary)', padding: '1rem', borderRadius: 'var(--radius-sm)', fontSize: '0.85rem', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)', overflowX: 'auto' }}>
{JSON.stringify({
  pid: doc.pid ?? null,
  dc_title: doc.dc_title,
  seed_url: doc.seed_url,
  crawl_timestamp: doc.crawl_timestamp,
  lifecycle_status: doc.lifecycle_status,
  qc_score: doc.qc_score ?? null,
  wacz_page_count: doc.wacz_page_count ?? null,
}, null, 2)}
            </pre>
          </div>
        )}
      </div>

      {showWithdrawModal && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.75)', display: 'flex',
          alignItems: 'center', justifyContent: 'center', zIndex: 9999,
          padding: '1rem'
        }}>
          <div className="glass-panel" style={{ width: '100%', maxWidth: '500px', padding: '1.75rem', display: 'flex', flexDirection: 'column', gap: '1rem', background: 'var(--bg-surface-elevated, #18181b)' }}>
            <h3 style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--text-primary, #f4f4f5)', margin: 0 }}>
              Publikált dokumentum visszavonása
            </h3>
            <p style={{ fontSize: '0.9rem', color: 'var(--text-muted, #a1a1aa)', margin: 0 }}>
              Kérjük, adja meg a visszavonás indokát (pl. jogi kérés, hibás aratás):
            </p>
            <textarea
              value={withdrawReason}
              onChange={(e) => setWithdrawReason(e.target.value)}
              placeholder="Visszavonás indoklása..."
              rows={3}
              style={{
                width: '100%', padding: '0.75rem', borderRadius: '0.375rem',
                background: 'var(--bg-primary, #09090b)', border: '1px solid var(--border-subtle, #27272a)',
                color: 'var(--text-primary, #f4f4f5)', fontSize: '0.9rem', resize: 'vertical'
              }}
            />
            {withdrawError && (
              <div style={{ color: '#f43f5e', fontSize: '0.85rem' }}>{withdrawError}</div>
            )}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
              <button
                onClick={() => { setShowWithdrawModal(false); setWithdrawError(null); }}
                className="btn-secondary"
                disabled={withdrawSubmitting}
                style={{ padding: '0.4rem 1rem', fontSize: '0.85rem' }}
              >
                Mégse
              </button>
              <button
                onClick={handleWithdraw}
                disabled={withdrawSubmitting || !withdrawReason.trim()}
                style={{
                  padding: '0.4rem 1rem', fontSize: '0.85rem', background: '#e11d48',
                  color: '#fff', border: 'none', borderRadius: '0.375rem',
                  cursor: withdrawSubmitting || !withdrawReason.trim() ? 'not-allowed' : 'pointer',
                  fontWeight: 600, opacity: withdrawSubmitting || !withdrawReason.trim() ? 0.6 : 1
                }}
              >
                {withdrawSubmitting ? 'Visszavonás...' : 'Visszavonás megerősítése'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
