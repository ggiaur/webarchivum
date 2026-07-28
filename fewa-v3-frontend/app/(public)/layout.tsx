import React from 'react';

export default function PublicLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      {/* Header */}
      <header className="glass-panel" style={{ position: 'sticky', top: 0, zIndex: 50, padding: '1rem 2rem' }}>
        <div style={{ maxWidth: '1200px', margin: '0 auto', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <a href="/" style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <div style={{ width: '36px', height: '36px', background: 'var(--accent-gradient)', borderRadius: '10px', display: 'grid', placeItems: 'center', fontWeight: 'bold', color: '#fff' }}>
              FW
            </div>
            <div>
              <div style={{ fontWeight: 700, fontSize: '1.2rem', color: 'var(--text-primary)', fontFamily: 'var(--font-heading)' }}>
                FEWA
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                Fejér Vármegyei Webarchívum
              </div>
            </div>
          </a>

          <nav style={{ display: 'flex', gap: '1.5rem', alignItems: 'center' }}>
            <a href="/" style={{ color: 'var(--text-primary)', fontWeight: 500 }}>
              Kereső
            </a>
            <a href="/collections" style={{ color: 'var(--text-secondary)', fontWeight: 500 }}>
              Gyűjtemények
            </a>
            <a href="http://localhost:8000/oai?verb=Identify" target="_blank" rel="noopener noreferrer" style={{ color: 'var(--text-secondary)', fontWeight: 500 }}>
              OAI-PMH
            </a>
            <a href="/admin/login" className="btn-secondary" style={{ padding: '0.4rem 1rem', fontSize: '0.85rem' }}>
              Kurátori Portál
            </a>
          </nav>
        </div>
      </header>

      {/* Main Content */}
      <main style={{ flex: 1, maxWidth: '1200px', width: '100%', margin: '0 auto', padding: '2rem 1.5rem' }}>
        {children}
      </main>

      {/* Footer */}
      <footer style={{ borderTop: '1px solid var(--border-subtle)', background: 'var(--bg-surface)', padding: '2rem 1.5rem', color: 'var(--text-muted)', fontSize: '0.875rem' }}>
        <div style={{ maxWidth: '1200px', margin: '0 auto', display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.25rem' }}>
              Vörösmarty Mihály Könyvtár
            </div>
            <div>8000 Székesfehérvár, Bartók Béla tér 1. · OSZK webarchívum módszertan szerint</div>
          </div>
          <div>
            <div>WACZ & ISO 28500 WARC szabványos megőrzés · WCAG 2.1 AA akadálymentes</div>
          </div>
        </div>
      </footer>
    </div>
  );
}
