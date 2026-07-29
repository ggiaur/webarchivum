import React from 'react';

export default function PublicLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="layout-wrapper" suppressHydrationWarning>
      {/* Header */}
      <header className="glass-panel header-sticky" suppressHydrationWarning>
        <div className="header-container">
          <a href="/" className="logo-link">
            <div className="logo-avatar">
              FW
            </div>
            <div>
              <div className="logo-title">
                FEWA
              </div>
              <div className="logo-subtitle">
                Fejér Vármegyei Webarchívum
              </div>
            </div>
          </a>

          <nav className="nav-links">
            <a href="/" className="nav-item-primary">
              Kereső
            </a>
            <a href="/collections" className="nav-item-secondary">
              Gyűjtemények
            </a>
            <a href="http://localhost:8000/oai?verb=Identify" target="_blank" rel="noopener noreferrer" className="nav-item-secondary">
              OAI-PMH
            </a>
            <a href="/admin/login" className="btn-secondary" style={{ padding: '0.4rem 1rem', fontSize: '0.85rem' }}>
              Kurátori Portál
            </a>
          </nav>
        </div>
      </header>

      {/* Main Content */}
      <main className="main-content">
        {children}
      </main>

      {/* Footer */}
      <footer className="footer-panel" suppressHydrationWarning>
        <div className="footer-container">
          <div>
            <div className="footer-title">
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
