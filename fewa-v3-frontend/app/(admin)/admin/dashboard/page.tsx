'use client';

import React, { useState, useEffect } from 'react';

interface SiteItem {
  id: string;
  domain: string;
  display_name: string;
  priority: string;
  category: string;
  crawl_frequency: string;
  oszk_status: string;
  is_active_collection: boolean;
}

interface SKOSConcept {
  id: string;
  pref_label_hu: string;
  pref_label_en?: string;
  alt_labels?: string[];
  definition?: string;
}

export default function AdminDashboardPage() {
  const [activeTab, setActiveTab] = useState<'sites' | 'thesaurus' | 'jobs'>('sites');
  const [sites, setSites] = useState<SiteItem[]>([]);
  const [thesaurus, setThesaurus] = useState<SKOSConcept[]>([]);
  const [user, setUser] = useState<any>(null);

  // New site form modal
  const [showAddSite, setShowAddSite] = useState(false);
  const [newDomain, setNewDomain] = useState('');
  const [newBaseUrl, setNewBaseUrl] = useState('');
  const [newPriority, setNewPriority] = useState('medium');
  const [newCategory, setNewCategory] = useState('közintézmény');

  useEffect(() => {
    const userStr = localStorage.getItem('fewa_user');
    if (userStr) setUser(JSON.parse(userStr));

    fetchSites();
    fetchThesaurus();
  }, []);

  const fetchSites = async () => {
    const token = localStorage.getItem('fewa_access_token');
    try {
      const res = await fetch('http://localhost:8000/api/admin/sites', {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      setSites(data.items || []);
    } catch {
      setSites([
        {
          id: '550e8400-e29b-41d4-a716-446655440001',
          domain: 'alba.hu',
          display_name: 'Alba Regia Portál',
          priority: 'high',
          category: 'közintézmény',
          crawl_frequency: 'weekly',
          oszk_status: 'no',
          is_active_collection: true,
        },
      ]);
    }
  };

  const fetchThesaurus = async () => {
    const token = localStorage.getItem('fewa_access_token');
    try {
      const res = await fetch('http://localhost:8000/api/thesaurus', {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      setThesaurus(data.items || []);
    } catch {
      setThesaurus([
        {
          id: 'concept-001',
          pref_label_hu: 'helyi politika',
          pref_label_en: 'local politics',
          alt_labels: ['önkormányzati politika', 'helyhatósági ügyek'],
          definition: 'Fejér vármegyei önkormányzati és helyi politikai témák.',
        },
      ]);
    }
  };

  const handleCreateSite = async (e: React.FormEvent) => {
    e.preventDefault();
    const token = localStorage.getItem('fewa_access_token');
    try {
      await fetch('http://localhost:8000/api/admin/sites', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          domain: newDomain,
          base_url: newBaseUrl,
          priority: newPriority,
          category: newCategory,
        }),
      });
      setShowAddSite(false);
      fetchSites();
    } catch (err) {
      alert('Sikertelen mentés.');
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('fewa_access_token');
    localStorage.removeItem('fewa_refresh_token');
    localStorage.removeItem('fewa_user');
    window.location.href = '/admin/login';
  };

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg-primary)', display: 'flex', flexDirection: 'column' }}>
      {/* Admin Top Navigation */}
      <header className="glass-panel" style={{ padding: '1rem 2rem', borderRadius: 0 }}>
        <div style={{ maxWidth: '1400px', margin: '0 auto', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <div style={{ fontWeight: 700, fontSize: '1.2rem', color: 'var(--text-primary)' }}>
              FEWA Admin Dashboard
            </div>
            <span className="badge badge-amber">{user?.role || 'curator'}</span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem' }}>
            <span style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>👤 {user?.full_name || 'Kurátor'}</span>
            <button onClick={handleLogout} className="btn-secondary" style={{ padding: '0.35rem 0.8rem', fontSize: '0.8rem' }}>
              Kijelentkezés
            </button>
          </div>
        </div>
      </header>

      {/* Main Admin Area */}
      <div style={{ maxWidth: '1400px', width: '100%', margin: '0 auto', padding: '2rem 1.5rem', flex: 1, display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
        {/* Navigation Tabs */}
        <div style={{ display: 'flex', gap: '1rem', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '1rem' }}>
          <button
            onClick={() => setActiveTab('sites')}
            style={{
              padding: '0.6rem 1.2rem',
              borderRadius: 'var(--radius-md)',
              border: 'none',
              cursor: 'pointer',
              fontWeight: 600,
              background: activeTab === 'sites' ? 'var(--accent-gradient)' : 'transparent',
              color: activeTab === 'sites' ? '#fff' : 'var(--text-secondary)',
            }}
          >
            🌐 Webhelyek & Prioritások ({sites.length})
          </button>
          <button
            onClick={() => setActiveTab('thesaurus')}
            style={{
              padding: '0.6rem 1.2rem',
              borderRadius: 'var(--radius-md)',
              border: 'none',
              cursor: 'pointer',
              fontWeight: 600,
              background: activeTab === 'thesaurus' ? 'var(--accent-gradient)' : 'transparent',
              color: activeTab === 'thesaurus' ? '#fff' : 'var(--text-secondary)',
            }}
          >
            📚 SKOS Tezaurusz ({thesaurus.length})
          </button>
        </div>

        {/* Tab 1: Sites List */}
        {activeTab === 'sites' && (
          <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h2 style={{ fontSize: '1.2rem' }}>Archiválandó Webhelyek Registre</h2>
              <button onClick={() => setShowAddSite(true)} className="btn-primary" style={{ padding: '0.5rem 1rem', fontSize: '0.85rem' }}>
                + Új Site Hozzáadása
              </button>
            </div>

            {/* Sites Table */}
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.9rem' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-muted)' }}>
                  <th style={{ padding: '0.75rem' }}>Domain</th>
                  <th style={{ padding: '0.75rem' }}>Megnevezés</th>
                  <th style={{ padding: '0.75rem' }}>Prioritás</th>
                  <th style={{ padding: '0.75rem' }}>Kategória</th>
                  <th style={{ padding: '0.75rem' }}>OSZK Státusz</th>
                  <th style={{ padding: '0.75rem' }}>Gyakoriság</th>
                </tr>
              </thead>
              <tbody>
                {sites.map((site) => (
                  <tr key={site.id} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                    <td style={{ padding: '0.75rem', fontWeight: 600 }}>{site.domain}</td>
                    <td style={{ padding: '0.75rem' }}>{site.display_name}</td>
                    <td style={{ padding: '0.75rem' }}>
                      <span className={`badge ${site.priority === 'high' || site.priority === 'critical' ? 'badge-rose' : 'badge-blue'}`}>
                        {site.priority}
                      </span>
                    </td>
                    <td style={{ padding: '0.75rem' }}>{site.category}</td>
                    <td style={{ padding: '0.75rem' }}>
                      <span className="badge badge-amber">{site.oszk_status}</span>
                    </td>
                    <td style={{ padding: '0.75rem' }}>{site.crawl_frequency}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Tab 2: SKOS Thesaurus */}
        {activeTab === 'thesaurus' && (
          <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <h2 style={{ fontSize: '1.2rem' }}>SKOS Tezaurusz Fogalmak</h2>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '1rem' }}>
              {thesaurus.map((c) => (
                <div key={c.id} className="glass-card" style={{ padding: '1rem' }}>
                  <div style={{ fontWeight: 700, fontSize: '1.1rem', color: 'var(--accent-cyan)', marginBottom: '0.25rem' }}>
                    {c.pref_label_hu}
                  </div>
                  {c.pref_label_en && <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>EN: {c.pref_label_en}</div>}
                  <div style={{ fontSize: '0.85rem', marginTop: '0.5rem', color: 'var(--text-secondary)' }}>
                    {c.definition}
                  </div>
                  {c.alt_labels && (
                    <div style={{ marginTop: '0.5rem', display: 'flex', gap: '0.25rem', flexWrap: 'wrap' }}>
                      {c.alt_labels.map((alt, idx) => (
                        <span key={idx} className="badge badge-blue">{alt}</span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Add Site Modal */}
      {showAddSite && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', display: 'grid', placeItems: 'center', zIndex: 100 }}>
          <div className="glass-panel animate-fade-in" style={{ width: '100%', maxWidth: '500px', padding: '2rem' }}>
            <h3 style={{ marginBottom: '1rem' }}>Új Archiválandó Webhely</h3>
            <form onSubmit={handleCreateSite} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div>
                <label style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Domain</label>
                <input type="text" className="input-search" placeholder="fejer.hu" value={newDomain} onChange={(e) => setNewDomain(e.target.value)} required />
              </div>
              <div>
                <label style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Base URL</label>
                <input type="url" className="input-search" placeholder="https://fejer.hu" value={newBaseUrl} onChange={(e) => setNewBaseUrl(e.target.value)} required />
              </div>
              <div style={{ display: 'flex', gap: '1rem' }}>
                <div style={{ flex: 1 }}>
                  <label style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Prioritás</label>
                  <select className="input-search" value={newPriority} onChange={(e) => setNewPriority(e.target.value)}>
                    <option value="critical">Critical</option>
                    <option value="high">High</option>
                    <option value="medium">Medium</option>
                    <option value="low">Low</option>
                  </select>
                </div>
                <div style={{ flex: 1 }}>
                  <label style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Kategória</label>
                  <select className="input-search" value={newCategory} onChange={(e) => setNewCategory(e.target.value)}>
                    <option value="közintézmény">Közintézmény</option>
                    <option value="média">Média</option>
                    <option value="civil">Civil</option>
                    <option value="kulturális">Kulturális</option>
                  </select>
                </div>
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', marginTop: '1rem' }}>
                <button type="button" className="btn-secondary" onClick={() => setShowAddSite(false)}>Mégse</button>
                <button type="submit" className="btn-primary">Mentés</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
