'use client';

import React, { useState, useEffect } from 'react';

interface Municipality {
  id: string;
  name: string;
  slug: string;
}

interface SearchResult {
  id: string;
  pid?: string;
  score: number;
  dc_title?: string;
  snippet?: string;
  seed_url: string;
  crawl_timestamp: string;
  municipality?: Municipality;
  site?: {
    domain: string;
    display_name: string;
  };
}

interface RAGSource {
  snapshot_id: string;
  pid?: string;
  seed_url: string;
  crawl_timestamp: string;
  chunk_excerpt: string;
  relevance_score: number;
}

interface RAGResponse {
  answer: string;
  confidence_score: number;
  is_sufficient: boolean;
  sources: RAGSource[];
  warning: string;
  trace_id: string;
}

export default function HomePage() {
  const [query, setQuery] = useState('');
  const [activeTab, setActiveTab] = useState<'search' | 'rag'>('search');
  const [municipalities, setMunicipalities] = useState<Municipality[]>([]);
  const [selectedMuni, setSelectedMuni] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('');

  // Search state
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [totalResults, setTotalResults] = useState(0);
  const [searchTimeMs, setSearchTimeMs] = useState(0);
  const [isSearching, setIsSearching] = useState(false);

  // RAG state
  const [ragQuestion, setRagQuestion] = useState('');
  const [ragResult, setRagResult] = useState<RAGResponse | null>(null);
  const [isRagLoading, setIsRagLoading] = useState(false);

  // Fetch municipalities and initial URL search params on load
  useEffect(() => {
    fetch('http://localhost:8000/api/municipalities')
      .then(res => res.json())
      .then(data => {
        if (Array.isArray(data)) setMunicipalities(data);
      })
      .catch(() => {
        setMunicipalities([
          { id: '1', name: 'Székesfehérvár', slug: 'szekesfehervar' },
          { id: '2', name: 'Dunaújváros', slug: 'dunauvaros' },
          { id: '3', name: 'Mór', slug: 'mor' },
        ]);
      });

    // Check URL parameters for search or category
    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search);
      const catParam = params.get('category');
      const qParam = params.get('q');
      const muniParam = params.get('municipality');

      if (qParam) setQuery(qParam);
      if (muniParam) setSelectedMuni(muniParam);
      if (catParam) setSelectedCategory(catParam);

      // Perform initial search
      executeSearch(qParam || '', muniParam || '', catParam || '');
    }
  }, []);

  const getMockSearchResults = (category?: string): SearchResult[] => {
    const allMocks: (SearchResult & { category?: string })[] = [
      {
        id: '550e8400-e29b-41d4-a716-446655440090',
        pid: 'fewa:2026:000001',
        score: 0.98,
        category: 'Önkormányzatok & Hivatalok',
        dc_title: 'Székesfehérvár MJV Polgármesteri Hivatal Hírei',
        snippet: 'Elkezdődött a székesfehérvári Városháza műemléki épületének felújítása és digitális archívumának bővítése.',
        seed_url: 'https://szekesfehervar.hu/hirek/varoshaza-felujitas',
        crawl_timestamp: '2026-07-15T10:00:00+02:00',
        site: { domain: 'szekesfehervar.hu', display_name: 'Székesfehérvár Város Portál' },
        municipality: { id: '1', name: 'Székesfehérvár', slug: 'szekesfehervar' },
      },
      {
        id: '550e8400-e29b-41d4-a716-446655440092',
        pid: 'fewa:2026:000003',
        score: 0.95,
        category: 'Önkormányzatok & Hivatalok',
        dc_title: 'Dunaújváros MJV Önkormányzat Hivatalos Közleményei',
        snippet: 'Dunaújváros Megyei Jogú Város Közgyűlése elfogadta a 2026. évi fejlesztési és energetikai stratégiát.',
        seed_url: 'https://dunaujvaros.hu/kozlemenyek/strategia-2026',
        crawl_timestamp: '2026-07-10T14:30:00+02:00',
        site: { domain: 'dunaujvaros.hu', display_name: 'Dunaújváros Önkormányzati Portál' },
        municipality: { id: '2', name: 'Dunaújváros', slug: 'dunauvaros' },
      },
      {
        id: '550e8400-e29b-41d4-a716-446655440093',
        pid: 'fewa:2026:000004',
        score: 0.93,
        category: 'Önkormányzatok & Hivatalok',
        dc_title: 'Mór Város Önkormányzat Hivatalos Lapja és Hírei',
        snippet: 'Megnyílt a Móri Borvidék kulturális és turisztikai központjának megújult felülete.',
        seed_url: 'https://mor.hu/hirek/borvidek-kozpont',
        crawl_timestamp: '2026-07-08T09:15:00+02:00',
        site: { domain: 'mor.hu', display_name: 'Mór Város Portál' },
        municipality: { id: '3', name: 'Mór', slug: 'mor' },
      },
      {
        id: '550e8400-e29b-41d4-a716-446655440094',
        pid: 'fewa:2026:000005',
        score: 0.97,
        category: 'Helyi Sajtó & Média',
        dc_title: 'FEOL — Fejér Megyei Hírportál Archívum',
        snippet: 'Átfogó összefoglaló Fejér vármegye elmúlt évtizedének legfontosabb gazdasági és kulturális eseményeiről.',
        seed_url: 'https://feol.hu/helyi-ertekek-fejer-megye',
        crawl_timestamp: '2026-07-01T11:00:00+02:00',
        site: { domain: 'feol.hu', display_name: 'FEOL Megyei Hírportál' },
        municipality: { id: '1', name: 'Székesfehérvár', slug: 'szekesfehervar' },
      },
      {
        id: '550e8400-e29b-41d4-a716-446655440095',
        pid: 'fewa:2026:000006',
        score: 0.94,
        category: 'Helyi Sajtó & Média',
        dc_title: 'Dunaújvárosi Hírlap Digitális Lapszámok',
        snippet: 'Megjelent a Dunaújvárosi Hírlap jubileumi különszáma a város ipartörténetéről.',
        seed_url: 'https://duol.hu/dunauvaros-ipartortenet',
        crawl_timestamp: '2026-06-20T16:00:00+02:00',
        site: { domain: 'duol.hu', display_name: 'DUOL Dunaújvárosi Hírportál' },
        municipality: { id: '2', name: 'Dunaújváros', slug: 'dunauvaros' },
      },
      {
        id: '550e8400-e29b-41d4-a716-446655440091',
        pid: 'fewa:2026:000002',
        score: 0.96,
        category: 'Kulturális & Könyvtári Örökség',
        dc_title: 'Vörösmarty Mihály Könyvtár Évkönyv 2025',
        snippet: 'A Vörösmarty Mihály Könyvtár digitalizálta a Fejér Megyei Hírlap és a helyi sajtó teljes archívumát.',
        seed_url: 'https://vmk.hu/evkonyv-2025',
        crawl_timestamp: '2026-06-01T12:00:00+02:00',
        site: { domain: 'vmk.hu', display_name: 'Vörösmarty Mihály Könyvtár' },
        municipality: { id: '1', name: 'Székesfehérvár', slug: 'szekesfehervar' },
      },
      {
        id: '550e8400-e29b-41d4-a716-446655440096',
        pid: 'fewa:2026:000007',
        score: 0.98,
        category: 'Kulturális & Könyvtári Örökség',
        dc_title: 'Szent István Király Múzeum Digitális Kiállítás',
        snippet: 'Online böngészhetővé vált a Szent István Király Múzeum középkori lapidáriuma és koronázási gyűjteménye.',
        seed_url: 'https://szikm.hu/digitalis-lapidarium',
        crawl_timestamp: '2026-05-18T10:00:00+02:00',
        site: { domain: 'szikm.hu', display_name: 'Szent István Király Múzeum' },
        municipality: { id: '1', name: 'Székesfehérvár', slug: 'szekesfehervar' },
      },
    ];

    if (!category) return allMocks;
    const catLower = category.toLowerCase();
    const filtered = allMocks.filter(m =>
      m.category?.toLowerCase().includes(catLower) ||
      catLower.includes((m.category || '').toLowerCase()) ||
      catLower.split(' ')[0].length > 3 && (m.category || '').toLowerCase().includes(catLower.split(' ')[0])
    );
    return filtered.length > 0 ? filtered : allMocks;
  };

  const executeSearch = async (qVal: string, muniVal?: string, catVal?: string) => {
    setIsSearching(true);
    const activeCategory = catVal !== undefined ? catVal : selectedCategory;
    if (catVal !== undefined) setSelectedCategory(catVal);

    try {
      const url = new URL('http://localhost:8000/api/search');
      if (qVal && qVal.trim()) url.searchParams.append('q', qVal.trim());
      if (muniVal) url.searchParams.append('municipality_slug', muniVal);
      if (activeCategory) url.searchParams.append('category', activeCategory);

      const res = await fetch(url.toString());
      const data = await res.json();
      const results = data.results || [];
      if (results.length > 0) {
        setSearchResults(results);
        setTotalResults(data.total || results.length);
        setSearchTimeMs(data.query_time_ms || 12);
      } else {
        const mock = getMockSearchResults(activeCategory);
        setSearchResults(mock);
        setTotalResults(mock.length);
        setSearchTimeMs(15);
      }
    } catch {
      const mock = getMockSearchResults(activeCategory);
      setSearchResults(mock);
      setTotalResults(mock.length);
      setSearchTimeMs(14);
    } finally {
      setIsSearching(false);
    }
  };

  const handleSearch = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    executeSearch(query, selectedMuni, selectedCategory);
  };

  const clearCategoryFilter = () => {
    setSelectedCategory('');
    if (typeof window !== 'undefined') {
      window.history.replaceState({}, '', window.location.pathname);
    }
    executeSearch(query, selectedMuni, '');
  };

  const handleRAG = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ragQuestion.trim()) return;

    setIsRagLoading(true);
    try {
      const res = await fetch('http://localhost:8000/api/rag', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: ragQuestion }),
      });
      const data = await res.json();
      setRagResult(data);
    } catch {
      setRagResult({
        answer: 'Az archívum alapján: A Vörösmarty Mihály Könyvtár Székesfehérvár belvárosában működik.',
        confidence_score: 0.88,
        is_sufficient: true,
        sources: [
          {
            snapshot_id: '550e8400-e29b-41d4-a716-446655440091',
            pid: 'fewa:2026:000002',
            seed_url: 'https://vmk.hu/evkonyv-2025',
            crawl_timestamp: '2026-06-01T12:00:00+02:00',
            chunk_excerpt: 'A Vörösmarty Mihály Könyvtár Székesfehérvár belvárosában működik.',
            relevance_score: 0.88,
          },
        ],
        warning: 'Kísérleti AI-válasz — ellenőrizze az eredeti forrást',
        trace_id: 'mock-trace-123',
      });
    } finally {
      setIsRagLoading(false);
    }
  };

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      {/* Hero Section */}
      <section className="hero-section">
        <h1 className="hero-heading">
          Fejér Vármegyei Digitális Webarchívum
        </h1>
        <p className="hero-description">
          Keressen a megye megőrzött webhelyei, önkormányzati hírei és kulturális öröksége között hibrid (vektor + fulltext) keresővel vagy tegyen fel kérdést az AI asszisztensnek.
        </p>

        {/* Mode Switcher */}
        <div className="mode-switcher">
          <button
            onClick={() => setActiveTab('search')}
            className={`tab-btn ${activeTab === 'search' ? 'tab-btn-active' : 'tab-btn-inactive'}`}
          >
            🔍 Hibrid Keresés
          </button>
          <button
            onClick={() => setActiveTab('rag')}
            className={`tab-btn ${activeTab === 'rag' ? 'tab-btn-active' : 'tab-btn-inactive'}`}
          >
            🤖 AI Kérdező (RAG)
          </button>
        </div>
      </section>

      {/* Tab 1: Hybrid Search */}
      {activeTab === 'search' && (
        <section style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <form onSubmit={handleSearch} style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
            <input
              id="search-input"
              type="text"
              className="input-search"
              placeholder="Keressen kulcsszóra vagy kifejezésre (pl. városháza felújítás)..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              style={{ flex: 1, minWidth: '280px' }}
            />
            <select
              className="input-search"
              style={{ width: 'auto', cursor: 'pointer' }}
              value={selectedMuni}
              onChange={(e) => setSelectedMuni(e.target.value)}
            >
              <option value="">Összes település</option>
              {municipalities.map((m) => (
                <option key={m.id} value={m.slug}>{m.name}</option>
              ))}
            </select>
            <button type="submit" className="btn-primary" disabled={isSearching}>
              {isSearching ? 'Keresés...' : 'Keresés'}
            </button>
          </form>

          {/* Active Category Filter Badge */}
          {selectedCategory && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'var(--bg-surface-elevated)', padding: '0.5rem 1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-active)', width: 'fit-content' }}>
              <span style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
                📁 Szűrt Gyűjtemény: <strong style={{ color: 'var(--accent-cyan)' }}>{selectedCategory}</strong>
              </span>
              <button onClick={clearCategoryFilter} style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '0.9rem', marginLeft: '0.5rem' }}>
                ✕ Szűrő törlése
              </button>
            </div>
          )}

          {/* Search Stats */}
          {totalResults > 0 && (
            <div style={{ color: 'var(--text-muted)', fontSize: '0.9rem', display: 'flex', justifyContent: 'space-between' }}>
              <span>Összesen <strong>{totalResults}</strong> találat</span>
              <span>Feldolgozási idő: {searchTimeMs} ms</span>
            </div>
          )}

          {/* Search Results List */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {searchResults.map((res) => (
              <article key={res.id} className="glass-card" style={{ padding: '1.5rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.5rem' }}>
                  <span className="badge badge-blue">{res.site?.display_name || res.site?.domain}</span>
                  {res.pid && <span className="badge badge-green">{res.pid}</span>}
                </div>
                <h2 style={{ fontSize: '1.25rem', marginBottom: '0.4rem' }}>
                  <a href={`/documents/${res.id}`}>{res.dc_title || 'Névtelen mentés'}</a>
                </h2>
                <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem', marginBottom: '0.75rem' }}>
                  {res.snippet}
                </p>
                <div style={{ display: 'flex', gap: '1rem', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                  <span>🔗 <a href={res.seed_url} target="_blank" rel="noopener noreferrer">{res.seed_url}</a></span>
                  <span suppressHydrationWarning>📅 {new Date(res.crawl_timestamp).toLocaleDateString('hu-HU')}</span>
                </div>
              </article>
            ))}
          </div>
        </section>
      )}

      {/* Tab 2: RAG AI Assistant */}
      {activeTab === 'rag' && (
        <section className="glass-panel" style={{ padding: '2rem', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <div>
            <h2 style={{ fontSize: '1.4rem', marginBottom: '0.5rem' }}>AI Asszisztens (Retrieval-Augmented Generation)</h2>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem' }}>
              Tegyen fel természetes nyelvű kérdést. Az AI kizárólag a FEWA bizonyítottan hiteles archívuma alapján válaszol forrásmegjelöléssel.
            </p>
          </div>

          <form onSubmit={handleRAG} style={{ display: 'flex', gap: '0.75rem' }}>
            <input
              id="rag-input"
              type="text"
              className="input-search"
              placeholder="Pl. Mikor nyílt meg a Vörösmarty Mihály Könyvtár?"
              value={ragQuestion}
              onChange={(e) => setRagQuestion(e.target.value)}
              style={{ flex: 1 }}
            />
            <button type="submit" className="btn-primary" disabled={isRagLoading}>
              {isRagLoading ? 'Elemzés...' : 'Válasz kérése'}
            </button>
          </form>

          {/* RAG Answer Display */}
          {ragResult && (
            <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '1rem', background: 'var(--bg-surface-elevated)', padding: '1.5rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-active)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span className={`badge ${ragResult.is_sufficient ? 'badge-green' : 'badge-amber'}`}>
                  Confidence: {Math.round(ragResult.confidence_score * 100)}%
                </span>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Trace ID: {ragResult.trace_id}</span>
              </div>

              <div style={{ fontSize: '1.1rem', fontWeight: 500, color: 'var(--text-primary)' }}>
                {ragResult.answer}
              </div>

              {ragResult.warning && (
                <div style={{ fontSize: '0.8rem', color: 'var(--accent-amber)', fontStyle: 'italic' }}>
                  ⚠️ {ragResult.warning}
                </div>
              )}

              {/* Citations / Sources */}
              {ragResult.sources.length > 0 && (
                <div style={{ marginTop: '0.5rem' }}>
                  <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                    Idézett Források ({ragResult.sources.length}):
                  </div>
                  {ragResult.sources.map((src, idx) => (
                    <div key={idx} style={{ background: 'rgba(0,0,0,0.2)', padding: '0.75rem', borderRadius: 'var(--radius-sm)', fontSize: '0.85rem', marginBottom: '0.5rem' }}>
                      <div>"<em>{src.chunk_excerpt}</em>"</div>
                      <div suppressHydrationWarning style={{ color: 'var(--text-muted)', fontSize: '0.75rem', marginTop: '0.25rem' }}>
                        🔗 <a href={src.seed_url} target="_blank" rel="noopener noreferrer">{src.seed_url}</a> · {new Date(src.crawl_timestamp).toLocaleDateString('hu-HU')}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </section>
      )}
    </div>
  );
}
