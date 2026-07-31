'use client';

import React, { useState, useEffect } from 'react';
import { getApiBaseUrl } from '../utils/apiConfig';

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
  const [hasSearched, setHasSearched] = useState(false);
  const [searchError, setSearchError] = useState(false);

  // RAG state
  const [ragQuestion, setRagQuestion] = useState('');
  const [ragResult, setRagResult] = useState<RAGResponse | null>(null);
  const [isRagLoading, setIsRagLoading] = useState(false);
  const [ragError, setRagError] = useState(false);

  useEffect(() => {
    fetch(`${getApiBaseUrl()}/api/municipalities`)
      .then(res => res.json())
      .then(data => {
        if (Array.isArray(data)) setMunicipalities(data);
      })
      .catch(() => setMunicipalities([]));

    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search);
      const catParam = params.get('category');
      const qParam = params.get('q');
      const muniParam = params.get('municipality');

      if (qParam) setQuery(qParam);
      if (muniParam) setSelectedMuni(muniParam);
      if (catParam) setSelectedCategory(catParam);

      executeSearch(qParam || '', muniParam || '', catParam || '');
    }
  }, []);

  const executeSearch = async (qVal: string, muniVal?: string, catVal?: string) => {
    setIsSearching(true);
    setSearchError(false);
    const activeCategory = catVal !== undefined ? catVal : selectedCategory;
    if (catVal !== undefined) setSelectedCategory(catVal);

    try {
      const url = new URL(`${getApiBaseUrl()}/api/search`);
      if (qVal && qVal.trim()) url.searchParams.append('q', qVal.trim());
      if (muniVal) url.searchParams.append('municipality_slug', muniVal);
      if (activeCategory) url.searchParams.append('category', activeCategory);

      const res = await fetch(url.toString());
      if (!res.ok) throw new Error(`Search API returned ${res.status}`);
      const data = await res.json();
      setSearchResults(data.results || []);
      setTotalResults(data.total ?? 0);
      setSearchTimeMs(data.query_time_ms ?? 0);
    } catch {
      setSearchResults([]);
      setTotalResults(0);
      setSearchError(true);
    } finally {
      setHasSearched(true);
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
    setRagError(false);
    try {
      const res = await fetch(`${getApiBaseUrl()}/api/rag`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: ragQuestion }),
      });
      if (!res.ok) throw new Error(`RAG API returned ${res.status}`);
      const data = await res.json();
      setRagResult(data);
    } catch {
      setRagResult(null);
      setRagError(true);
    } finally {
      setIsRagLoading(false);
    }
  };

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '2.5rem' }}>
      {/* Hero Section */}
      <section className="hero-section" style={{
        background: 'linear-gradient(135deg, rgba(18, 24, 36, 0.95) 0%, rgba(30, 58, 138, 0.25) 100%)',
        border: '1px solid rgba(59, 130, 246, 0.3)',
        borderRadius: '24px',
        padding: '3.5rem 2rem',
        boxShadow: '0 20px 50px rgba(0, 0, 0, 0.5)'
      }}>
        <span className="badge badge-blue" style={{ marginBottom: '1rem', padding: '0.4rem 0.9rem', fontSize: '0.85rem' }}>
          🏛️ FEJÉR VÁRMEGYEI WEBARCHÍVUM (FEWA)
        </span>
        <h1 className="hero-heading" style={{ fontSize: '3rem', fontWeight: 800, color: '#ffffff', marginBottom: '1rem', letterSpacing: '-0.02em' }}>
          Digitális Kulturális Örökségvédelem
        </h1>
        <p className="hero-description" style={{ fontSize: '1.15rem', color: '#94a3b8', maxWidth: '720px', lineHeight: '1.7', marginBottom: '2rem' }}>
          Keressen a Vörösmarty Mihály Könyvtár által hitelesen megőrzött önkormányzati hírek, helyi sajtó és kulturális kiadványok WARC/WACZ archívumában.
        </p>

        {/* Search vs RAG Mode Switcher */}
        <div className="mode-switcher" style={{ background: 'rgba(15, 23, 42, 0.8)', padding: '0.4rem', borderRadius: '14px', border: '1px solid rgba(255, 255, 255, 0.1)', marginBottom: '2rem' }}>
          <button
            onClick={() => setActiveTab('search')}
            className={`tab-btn ${activeTab === 'search' ? 'tab-btn-active' : 'tab-btn-inactive'}`}
            style={{ padding: '0.65rem 1.6rem', fontSize: '0.95rem', borderRadius: '10px' }}
          >
            🔍 Hibrid Kereső
          </button>
          <button
            onClick={() => setActiveTab('rag')}
            className={`tab-btn ${activeTab === 'rag' ? 'tab-btn-active' : 'tab-btn-inactive'}`}
            style={{ padding: '0.65rem 1.6rem', fontSize: '0.95rem', borderRadius: '10px' }}
          >
            🤖 AI Kérdés-Válasz (RAG)
          </button>
        </div>

        {/* Tab 1: Hybrid Search */}
        {activeTab === 'search' && (
          <form onSubmit={handleSearch} style={{ width: '100%', maxWidth: '800px', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
              <input
                type="text"
                className="input-search"
                placeholder="Keresés Fejér vármegyei weboldalakon (pl. Városháza, Közgyűlés, Borvidék)..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                style={{ flex: 1, minWidth: '280px', height: '56px', fontSize: '1.05rem', paddingLeft: '1.5rem', background: '#0f172a', border: '1px solid rgba(59, 130, 246, 0.4)' }}
              />
              <select
                className="input-search"
                value={selectedMuni}
                onChange={(e) => {
                  setSelectedMuni(e.target.value);
                  executeSearch(query, e.target.value, selectedCategory);
                }}
                style={{ width: 'auto', height: '56px', background: '#0f172a', border: '1px solid rgba(59, 130, 246, 0.4)', padding: '0 1.25rem' }}
              >
                <option value="">Összes település</option>
                {municipalities.map((m) => (
                  <option key={m.id} value={m.slug}>{m.name}</option>
                ))}
              </select>
              <button type="submit" className="btn-primary" style={{ height: '56px', padding: '0 2rem', fontSize: '1.05rem' }}>
                Keresés ➔
              </button>
            </div>
          </form>
        )}

        {/* Tab 2: RAG AI Q&A */}
        {activeTab === 'rag' && (
          <form onSubmit={handleRAG} style={{ width: '100%', maxWidth: '800px', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            <div style={{ display: 'flex', gap: '0.75rem' }}>
              <input
                type="text"
                className="input-search"
                placeholder="Tegyél fel egy kérdést a vármegyei webarchívumnak (pl. Mi a székesfehérvári beruházás 2. üteme?)..."
                value={ragQuestion}
                onChange={(e) => setRagQuestion(e.target.value)}
                style={{ flex: 1, height: '56px', fontSize: '1.05rem', paddingLeft: '1.5rem', background: '#0f172a', border: '1px solid rgba(6, 182, 212, 0.4)' }}
              />
              <button type="submit" className="btn-primary" disabled={isRagLoading} style={{ height: '56px', padding: '0 2rem', fontSize: '1.05rem', background: 'linear-gradient(135deg, #06b6d4 0%, #3b82f6 100%)' }}>
                {isRagLoading ? 'Elemzés...' : 'Válasz 🤖'}
              </button>
            </div>
          </form>
        )}
      </section>

      {/* Category Filter Pills (if active) */}
      {selectedCategory && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', background: 'rgba(59, 130, 246, 0.15)', border: '1px solid rgba(59, 130, 246, 0.3)', padding: '0.75rem 1.25rem', borderRadius: '12px' }}>
          <span style={{ fontSize: '0.9rem', color: '#93c5fd' }}>🏷️ Aktív Gyűjtemény Szűrő: <strong>{selectedCategory}</strong></span>
          <button onClick={clearCategoryFilter} style={{ background: 'transparent', border: 'none', color: '#f43f5e', cursor: 'pointer', fontWeight: 700, fontSize: '0.9rem' }}>
            ✖ Szűrő törlése
          </button>
        </div>
      )}

      {/* RAG Answer Display */}
      {activeTab === 'rag' && ragError && (
        <div className="glass-panel animate-fade-in" style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
          Az AI kérdés-válasz szolgáltatás jelenleg nem elérhető.
        </div>
      )}
      {activeTab === 'rag' && ragResult && (
        <div className="glass-panel animate-fade-in" style={{ padding: '2rem', border: '1px solid rgba(6, 182, 212, 0.4)', borderRadius: '16px', background: 'rgba(15, 23, 42, 0.9)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <span className="badge badge-green">🤖 AI GENERÁLT VÁLASZ (Konfidencia: {Math.round(ragResult.confidence_score * 100)}%)</span>
            <span style={{ fontSize: '0.8rem', color: '#64748b' }}>ID: {ragResult.trace_id}</span>
          </div>
          <p style={{ fontSize: '1.15rem', color: '#f8fafc', lineHeight: '1.7', marginBottom: '1.5rem', fontWeight: 500 }}>
            {ragResult.answer}
          </p>

          {ragResult.sources.length > 0 && (
            <div style={{ borderTop: '1px solid rgba(255, 255, 255, 0.1)', paddingTop: '1rem' }}>
              <h4 style={{ fontSize: '0.95rem', color: '#38bdf8', marginBottom: '0.75rem' }}>📌 Hiteles Archív Források:</h4>
              {ragResult.sources.map((src, idx) => (
                <div key={idx} style={{ background: 'rgba(255,255,255,0.03)', padding: '0.75rem 1rem', borderRadius: '8px', fontSize: '0.9rem', color: '#94a3b8' }}>
                  <a href={`/documents/${src.snapshot_id}`} style={{ fontWeight: 600, color: '#60a5fa' }}>{src.seed_url}</a> — <em>{src.chunk_excerpt}</em>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Search Results Listing */}
      {activeTab === 'search' && hasSearched && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: '#94a3b8', fontSize: '0.95rem' }}>
            <span>
              {isSearching
                ? 'Keresés…'
                : searchError
                ? 'A keresés jelenleg nem elérhető.'
                : <>Találatok: <strong style={{ color: '#f8fafc' }}>{totalResults} megőrzött archív dokumentum</strong> ({searchTimeMs} ms)</>}
            </span>
            {!searchError && !isSearching && <span>Rendezés: <strong>Relevancia szerint</strong></span>}
          </div>

          {!isSearching && !searchError && searchResults.length === 0 && (
            <div className="glass-panel" style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
              Nincs a keresésnek megfelelő megőrzött dokumentum.
            </div>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            {searchResults.map((item) => (
              <div key={item.id} className="glass-card" style={{ padding: '1.75rem', borderRadius: '16px', display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem' }}>
                  <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                    {item.pid && <span className="badge badge-green">{item.pid}</span>}
                    <span className="badge badge-blue">{item.site?.display_name || item.site?.domain}</span>
                    <span className="badge badge-amber">WACZ</span>
                  </div>
                  <span style={{ fontSize: '0.8rem', color: '#64748b' }}>📅 {new Date(item.crawl_timestamp).toLocaleDateString('hu-HU')}</span>
                </div>

                <div>
                  <h3 style={{ fontSize: '1.35rem', fontWeight: 700, marginBottom: '0.4rem' }}>
                    <a href={`/documents/${item.id}`} style={{ color: '#f8fafc', textDecoration: 'none' }}>
                      {item.dc_title}
                    </a>
                  </h3>
                  <p style={{ color: '#94a3b8', fontSize: '1rem', lineHeight: '1.6' }}>
                    {item.snippet}
                  </p>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid rgba(255, 255, 255, 0.08)', paddingTop: '0.85rem', marginTop: '0.25rem' }}>
                  <span style={{ fontSize: '0.85rem', color: '#64748b' }}>🌐 Domain: <strong style={{ color: '#cbd5e1' }}>{item.seed_url}</strong></span>
                  <a href={`/documents/${item.id}`} className="btn-secondary" style={{ fontSize: '0.85rem', padding: '0.4rem 1rem' }}>
                    Archív Megtekintése (WACZ Replay) ➔
                  </a>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
