import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'FEWA — Fejér Vármegyei Webarchívum',
  description: 'A Vörösmarty Mihály Könyvtár által kezelt Fejér vármegyei digitális webarchívum. Hibrid keresés, AI asszisztens és WACZ megőrzés.',
  keywords: ['Fejér vármegye', 'webarchívum', 'Székesfehérvár', 'Vörösmarty Mihály Könyvtár', 'OSZK', 'WACZ', 'hibrid keresés'],
  authors: [{ name: 'Vörösmarty Mihály Könyvtár' }],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="hu" suppressHydrationWarning>
      <body suppressHydrationWarning>
        <div id="app-root">
          {children}
        </div>
      </body>
    </html>
  );
}
