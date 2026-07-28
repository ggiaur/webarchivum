'use client';

import React, { useState, useEffect } from 'react';

interface Municipality {
  id: str;
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

  // Search state
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [totalResults, setTotalResults] = useState(0);
  const [searchTimeMs, setSearchTimeMs] = useState(0);
  const [isSearching, setIsSearching] = useState(false);

  // RAG state
  const [ragQuestion, setRagQuestion] = useState('');
  const [ragResult, setRagResult] = useState<RAGResponse | null>(null);
  const [isRagLoading, setIsRagLoading] = useState(false);

  // Fetch municipalities on load
  useEffect(() => {
    fetch('http://localhost:8000/api/municipalities')
      .then(res => res.json())
      .then(data => {
        if (Array.isArray(data)) setMunicipalities(data);
      })
      .catch(() => {
        // Fallback default municipalities
        setMunicipalities([
          { id: '1', name: 'Székesfehérvár', slug: 'szekesfehervar' },
          { id: '2', name: 'Dunaújváros', slug: 'dunauvaros' },
          { id: '3', name: 'Mór', slug: 'mor' },
        ]);
      });
  }, []);

  const handleSearch = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!query.trim() || query.length < 2) return;

    setIsSearching(true);
    try {
      const url = new URL('http://localhost:8000/api/search');
      url.searchParams.append('q', query);
      if (selectedMuni) url.searchParams.append('municipality_slug', selectedMuni);

      const res = await fetch(url.toString());
      const data = await res.json();
      setSearchResults(data.results || []);
      setTotalResults(data.total || 0);
      setSearchTimeMs(data.query_time_ms || 12);
    } catch {
      // Mock fallback data
      setSearchResults([
        {
          id: '550e8400-e29b-41d4-a716-446655440090',
          pid: 'fewa:2026:000001',
          score: 0.95,
          dc_title: 'Székesfehérvár MJV Polgármesteri Hivatal Hírei',
          snippet: 'Elkezdődött a székesfehérvári Városháza műemléki épületének felújítása.',
          seed_url: 'https://szekesfehervar.hu/hirek/varoshaza-felujitas',
          crawl_timestamp: '2026-07-15T10:00:00+02:00',
          site: { domain: 'szekesfehervar.hu', display_name: 'Székesfehérvár Város Portál' },
          municipality: { id: '1', name: 'Székesfehérvár', slug: 'szekesfehervar' },
        },
      ]);
      setTotalResults(1);
      setSearchTimeMs(14);
    } finally {
      setIsSearching(false);
    }
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
      <section style={{ textAlign: 'center', padding: '3rem 1rem 1rem' }}>
        <h1 style={{ fontSize: '2.5rem', fontWeight: 800, marginBottom: '1rem', background: 'var(--accent-gradient)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
          Fejér Vármegyei Digitális Webarchívum
        </h1>
        <p style={{ color: 'var(--text-secondary)', maxWidth: '680px', margin: '0 auto 2rem', fontSize: '1.1rem' }}>
          Keressen a megye megőrzött webhelyei, önkormányzati hírei és kulturális öröksége között hibrid (vektor + fulltext) keresővel vagy tegyen fel kérdést az AI asszisztensnek.
        </p>

        {/* Mode Switcher */}
        <div style={{ display: 'inline-flex', background: 'var(--bg-surface-elevated)', padding: '0.3rem', borderRadius: 'var(--radius-lg)', gap: '0.3rem' }}>
          <button
            onClick={() => setActiveTab('search')}
            style={{
              padding: '0.6rem 1.4rem',
              borderRadius: 'var(--radius-md)',
              border: 'none',
              cursor: 'pointer',
              fontWeight: 600,
              background: activeTab === 'search' ? 'var(--accent-gradient)' : 'transparent',
              color: activeTab === 'search' ? '#fff' : 'var(--text-secondary)',
            }}
          >
            🔍 Hibrid Keresés
          </button>
          <button
            onClick={() => setActiveTab('rag')}
            style={{
              padding: '0.6rem 1.4rem',
              borderRadius: 'var(--radius-md)',
              border: 'none',
              cursor: 'pointer',
              fontWeight: 600,
              background: activeTab === 'rag' ? 'var(--accent-gradient)' : 'transparent',
              color: activeTab === 'rag' ? '#fff' : 'var(--text-secondary)',
            }}
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
                  <span>📅 {new Date(res.crawl_timestamp).toLocaleDateString('hu-HU')}</span>
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
                      <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem', marginTop: '0.25rem' }}>
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
