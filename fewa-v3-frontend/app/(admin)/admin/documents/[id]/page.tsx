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
  publication_decision?: 'PASS_RELEASE' | 'HOLD_REJECT';
  remediation_status?: 'RELEASED_CLEAN' | 'RELEASED_REMEDIATED' | 'HELD_UNRECOVERABLE';
  remediation_reason?: string;
  remediation_attempts?: number;
  unresolved_resources?: string[];
  replay_url?: string | null;
  site?: {
    domain: string;
    display_name: string;
  };
}

type LoadState = { status: 'loading' } | { status: 'error' } | { status: 'ready'; doc: DocumentDetail };

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
      const rwpEl = replayContainerRef.current?.querySelector('replay-web-page');
      const iframe = rwpEl?.shadowRoot?.querySelector('iframe') as HTMLIFrameElement | null;
      let text = '';
      try {
        text = iframe?.contentDocument?.body?.textContent || '';
      } catch {
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
  const isHeld = doc.publication_decision === 'HOLD_REJECT' || doc.remediation_status === 'HELD_UNRECOVERABLE';
  const isReleased = !isHeld && (doc.publication_decision === 'PASS_RELEASE' || doc.remediation_status === 'RELEASED_CLEAN' || doc.remediation_status === 'RELEASED_REMEDIATED' || !!doc.wacz_url);
  const directReplayTarget = doc.replay_url || (doc.wacz_url ? `/replay-loading?target=${encodeURIComponent(`/replay/?source=${encodeURIComponent(`${typeof window !== 'undefined' ? window.location.origin : ''}${doc.wacz_url}`)}&url=${encodeURIComponent(doc.seed_url)}`)}` : null);

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', padding: '1.5rem' }}>
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
            {isHeld ? (
              <span className="badge badge-rose" id="admin-status-badge-hold" style={{ background: 'rgba(244, 63, 94, 0.2)', color: '#f43f5e', border: '1px solid #f43f5e', fontWeight: 700 }}>
                ⛔ KIADVÁNY-TARTÁS (HOLD_REJECT)
              </span>
            ) : (
              <span className="badge badge-emerald" id="admin-status-badge-release" style={{ background: 'rgba(16, 185, 129, 0.2)', color: '#10b981', border: '1px solid #10b981', fontWeight: 700 }}>
                🟢 KIADVA (PASS_RELEASE)
              </span>
            )}
            {doc.remediation_status && (
              <span className="badge badge-blue" id="admin-status-badge-remediation">
                {doc.remediation_status}
              </span>
            )}
            {doc.remediation_attempts != null && (
              <span className="badge badge-amber" id="admin-status-badge-attempts">
                {doc.remediation_attempts} kísérlet
              </span>
            )}
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

        <div id="admin-remediation-summary-panel" style={{
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
          <div id="admin-remediation-reason-text" style={{ lineHeight: '1.5' }}>
            {doc.remediation_reason || (isHeld ? 'A kiadvány letiltva (HOLD_REJECT): az archivált oldal nem rögzített erőforrásokat vagy sérült elemeket tartalmaz. A lejátszás zárolva van.' : 'Az archivált oldal WACZ lejátszása igazoltan működőképes és közzétételre engedélyezett (PASS_RELEASE).')}
          </div>
          {isHeld && doc.unresolved_resources && doc.unresolved_resources.length > 0 && (
            <div id="admin-unresolved-resources-list" style={{ marginTop: '0.4rem', fontSize: '0.8rem', color: '#fda4af', background: 'rgba(0,0,0,0.3)', padding: '0.5rem 0.75rem', borderRadius: 'var(--radius-sm)', fontFamily: 'var(--font-mono)' }}>
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
            {isReleased && directReplayTarget && (
              <a
                id="admin-direct-usable-replay-link"
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
              <div id="admin-hold-rejection-notice" style={{ padding: '3rem 1.5rem', textAlign: 'center', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid #f43f5e', borderRadius: 'var(--radius-md)', display: 'flex', flexDirection: 'column', gap: '1rem', alignItems: 'center' }}>
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
