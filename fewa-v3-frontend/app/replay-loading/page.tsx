'use client';

import React, { useEffect, useState } from 'react';
import { waitForReplayServiceWorkerActive } from '../utils/apiConfig';

/**
 * Intermediate page for the "Teljes oldal (új fül)" replay link.
 *
 * Regression fix for 2026-08-03. Linking directly to /replay/?source=...
 * is racy: a brand-new tab's first navigation can reach that URL before
 * the Service Worker (which alone can serve it) has finished installing.
 * This sidesteps the race instead of racing it: the new tab opens HERE
 * first — an ordinary Next.js page with no SW dependency, so it always
 * loads — and only navigates to the real replay URL (via location.replace,
 * staying in the same tab) once the /replay/ scope's worker is confirmed
 * 'activated' (see apiConfig.ts::waitForReplayServiceWorkerActive for the
 * full history of why that specific check, not `serviceWorker.ready`, is
 * the one that actually closes this gap — shared with the embedded replay
 * box's own gating so there's exactly one implementation of this check,
 * not two independently-drifting guesses).
 */
export default function ReplayLoadingPage() {
  const [timedOut, setTimedOut] = useState(false);
  // Read on mount, not during render: window.location is unavailable
  // during SSR, and reading it directly in the render body (rather than
  // useEffect) produces a server/client markup mismatch the exact same way
  // as the hydration bug already found elsewhere in this app.
  const [target, setTarget] = useState<string | null | undefined>(undefined);

  useEffect(() => {
    setTarget(new URLSearchParams(window.location.search).get('target'));
  }, []);

  useEffect(() => {
    if (!target) return;
    if (typeof navigator === 'undefined' || !('serviceWorker' in navigator)) {
      window.location.replace(target);
      return;
    }
    let cancelled = false;

    waitForReplayServiceWorkerActive().then(() => {
      if (!cancelled) window.location.replace(target);
    });

    // 60s: direct testing (2026-08-03) showed sw.js (1.2MB) sometimes taking
    // 30+ seconds to reach 'activated' under load, so a shorter cutoff fired
    // before real activation.
    const t = setTimeout(() => { if (!cancelled) setTimedOut(true); }, 60000);
    return () => { cancelled = true; clearTimeout(t); };
  }, [target]);

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      flexDirection: 'column', gap: '1rem', background: '#0a0d14', color: '#9ca3af',
      fontFamily: 'system-ui, sans-serif', padding: '2rem', textAlign: 'center',
    }}>
      {target === null ? (
        <div style={{ color: '#f3f4f6' }}>Hiányzó cél-URL.</div>
      ) : !timedOut ? (
        <>
          <div style={{ fontSize: '0.95rem' }}>A visszajátszó rendszer előkészítése…</div>
          <div style={{ fontSize: '0.8rem', color: '#6b7280' }}>Egy pillanat, és automatikusan megnyílik az archívum.</div>
        </>
      ) : (
        <>
          <div style={{ fontSize: '0.95rem', color: '#f3f4f6' }}>A visszajátszó rendszer nem állt elő időben.</div>
          <a href={target} className="btn-secondary" style={{ padding: '0.5rem 1.2rem', fontSize: '0.85rem' }}>
            Megnyitás mégis
          </a>
        </>
      )}
    </div>
  );
}
