import React from 'react';
import OaiNavLink from '../components/OaiNavLink';
import { getApiBaseUrl } from '../utils/apiConfig';

async function getPublicStats(): Promise<{ active_sites: number; published_documents: number } | null> {
  try {
    const res = await fetch(`${getApiBaseUrl()}/api/stats`, { cache: 'no-store' });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export default async function PublicLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const stats = await getPublicStats();

  return (
    <div className="layout-wrapper" suppressHydrationWarning>
      {/* Top Banner */}
      <div style={{
        background: 'linear-gradient(90deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%)',
        borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
        padding: '0.5rem 2rem',
        fontSize: '0.8rem',
        color: '#94a3b8',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: '0.5rem'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          <span style={{ display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%', background: '#10b981', boxShadow: '0 0 10px #10b981' }}></span>
          <span>🏛️ Vörösmarty Mihály Könyvtár — Digitális Örökségvédelem</span>
        </div>
        <div style={{ display: 'flex', gap: '1rem', fontSize: '0.78rem' }}>
          <span>📜 OSZK módszertan szerint</span>
          <span>🔒 ISO 28500 WARC & WACZ</span>
          <span>♿ WCAG 2.1 AA</span>
        </div>
      </div>

      {/* Main Sticky Header */}
      <header className="glass-panel header-sticky" suppressHydrationWarning style={{
        background: 'rgba(10, 13, 20, 0.85)',
        backdropFilter: 'blur(24px)',
        WebkitBackdropFilter: 'blur(24px)',
        borderBottom: '1px solid rgba(59, 130, 246, 0.25)',
        padding: '0.85rem 2rem',
      }}>
        <div className="header-container" style={{ maxWidth: '1280px', margin: '0 auto', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <a href="/" className="logo-link" style={{ display: 'flex', alignItems: 'center', gap: '0.85rem', textDecoration: 'none' }}>
            <div className="logo-avatar" style={{
              width: '42px',
              height: '42px',
              borderRadius: '12px',
              background: 'linear-gradient(135deg, #3b82f6 0%, #06b6d4 100%)',
              display: 'grid',
              placeItems: 'center',
              fontWeight: 800,
              color: '#ffffff',
              fontSize: '1.1rem',
              boxShadow: '0 0 20px rgba(59, 130, 246, 0.4)'
            }}>
              FE
            </div>
            <div>
              <div className="logo-title" style={{ fontSize: '1.35rem', fontWeight: 800, letterSpacing: '-0.02em', background: 'linear-gradient(135deg, #ffffff 0%, #cbd5e1 100%)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
                FEWA
              </div>
              <div className="logo-subtitle" style={{ fontSize: '0.75rem', color: '#64748b', fontWeight: 500 }}>
                Fejér Vármegyei Webarchívum
              </div>
            </div>
          </a>

          {/* Navigation Links */}
          <nav className="nav-links" style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
            <a href="/" className="nav-btn" style={{
              padding: '0.55rem 1.1rem',
              borderRadius: '10px',
              background: 'rgba(59, 130, 246, 0.15)',
              color: '#60a5fa',
              fontWeight: 600,
              fontSize: '0.9rem',
              textDecoration: 'none',
              border: '1px solid rgba(59, 130, 246, 0.3)',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.4rem',
              transition: 'all 0.2s ease'
            }}>
              🔍 Kereső
            </a>
            <a href="/collections" className="nav-btn" style={{
              padding: '0.55rem 1.1rem',
              borderRadius: '10px',
              background: 'rgba(255, 255, 255, 0.04)',
              color: '#cbd5e1',
              fontWeight: 500,
              fontSize: '0.9rem',
              textDecoration: 'none',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.4rem',
              transition: 'all 0.2s ease'
            }}>
              📚 Gyűjtemények
            </a>
            <OaiNavLink />
            <a href="/admin/login" className="btn-primary" style={{
              padding: '0.55rem 1.25rem',
              fontSize: '0.85rem',
              marginLeft: '0.5rem'
            }}>
              🔑 Kurátori Portál
            </a>
          </nav>
        </div>
      </header>

      {/* Main Content */}
      <main className="main-content" style={{ maxWidth: '1280px', width: '100%', margin: '0 auto', padding: '2.5rem 1.5rem' }}>
        {children}
      </main>

      {/* Footer */}
      <footer className="footer-panel" suppressHydrationWarning style={{
        background: '#090d16',
        borderTop: '1px solid rgba(255, 255, 255, 0.08)',
        padding: '3rem 2rem',
        marginTop: 'auto'
      }}>
        <div style={{ maxWidth: '1280px', margin: '0 auto', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '2rem' }}>
          <div>
            <div style={{ fontSize: '1.2rem', fontWeight: 800, color: '#f8fafc', marginBottom: '0.5rem' }}>
              Vörösmarty Mihály Könyvtár
            </div>
            <p style={{ fontSize: '0.9rem', color: '#94a3b8', lineHeight: '1.6', marginBottom: '1rem' }}>
              Fejér Vármegyei Digitális Kulturális Örökségvédelem és Hiteles Webarchívum Tároló.
            </p>
            <div style={{ fontSize: '0.85rem', color: '#64748b' }}>
              📍 8000 Székesfehérvár, Bartók Béla tér 1.
            </div>
          </div>

          <div>
            <div style={{ fontSize: '0.95rem', fontWeight: 700, color: '#f1f5f9', marginBottom: '0.75rem' }}>
              Szabványok & Módszertan
            </div>
            <ul style={{ listStyle: 'none', padding: 0, margin: 0, fontSize: '0.85rem', color: '#94a3b8', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
              <li>✓ OSZK Webarchívum Módszertan</li>
              <li>✓ ISO 28500 WARC Standard Format</li>
              <li>✓ WACZ (Web Archive Collection Zipped)</li>
              <li>✓ WCAG 2.1 AA Akadálymentesítési Szabvány</li>
            </ul>
          </div>

          <div>
            <div style={{ fontSize: '0.95rem', fontWeight: 700, color: '#f1f5f9', marginBottom: '0.75rem' }}>
              Rendszer Állapot
            </div>
            {stats ? (
              <div style={{ background: 'rgba(16, 185, 129, 0.1)', border: '1px solid rgba(16, 185, 129, 0.3)', padding: '0.75rem 1rem', borderRadius: '10px', fontSize: '0.85rem', color: '#34d399' }}>
                🟢 {stats.active_sites} regisztrált gyűjteményi webhely, {stats.published_documents} publikusan kereshető dokumentum.
              </div>
            ) : (
              <div style={{ background: 'rgba(148, 163, 184, 0.1)', border: '1px solid rgba(148, 163, 184, 0.3)', padding: '0.75rem 1rem', borderRadius: '10px', fontSize: '0.85rem', color: '#94a3b8' }}>
                ⚪ A rendszerállapot jelenleg nem elérhető.
              </div>
            )}
          </div>
        </div>
      </footer>
    </div>
  );
}
