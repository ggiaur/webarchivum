'use client';

import React, { useState, useEffect } from 'react';
import { fetchWithAuth } from '../../../utils/apiConfig';

interface SiteItem {
  id: string;
  domain: string;
  base_url?: string;
  display_name: string;
  priority: string;
  category: string;
  crawl_frequency: string;
  oszk_status: string;
  is_active_collection: boolean;
  rights_holder_name?: string;
  rights_holder_email?: string;
  rights_holder_contact_other?: string;
  permission_status?: string;
}

interface SKOSConcept {
  id: string;
  pref_label_hu: string;
  pref_label_en?: string;
  alt_labels?: string[];
  definition?: string;
}

interface CandidateItem {
  id: string;
  dc_title: string;
  seed_url: string;
  domain: string;
  priority: string;
  category: string;
  municipality_name?: string;
  created_at: string;
  created_by_name?: string;
}

interface QualityReviewItem {
  id: string;
  pid?: string;
  dc_title: string;
  seed_url: string;
  qc_score: number | null;
  qc_detail?: {
    pages?: Array<{
      url: string;
      screenshotMatch?: number | null;
      textMatch?: number | null;
      resourceCounts?: Record<string, number> | null;
    }>;
    reason?: string;
    note?: string;
    [key: string]: unknown;
  } | null;
  created_at: string;
}

interface UserItem {
  id: string;
  email: string;
  role: string;
  full_name: string;
  is_active: boolean;
  created_at?: string;
}

const PRIORITY_LABELS_HU: Record<string, string> = {
  critical: 'Kritikus',
  high: 'Magas',
  medium: 'Közepes',
  low: 'Alacsony',
  on_hold: 'Felfüggesztve',
};

const PERMISSION_STATUS_OPTIONS = [
  { value: 'nincs_megkeresve', label: 'Nincs megkeresve' },
  { value: 'megkeresve', label: 'Megkeresve (Válaszra vár)' },
  { value: 'engedélyezve', label: 'Engedélyezve (Jogtulajdonos hozzájárult)' },
  { value: 'elutasítva', label: 'Elutasítva' },
  { value: 'visszavonva', label: 'Engedély visszavonva' },
];

const CATEGORY_OPTIONS = ['kozintézmény', 'civil', 'média', 'vállalkozás', 'kulturális', 'egyéb'];
const PRIORITY_OPTIONS = ['critical', 'high', 'medium', 'low', 'on_hold'];
const ROLE_OPTIONS = ['admin', 'curator', 'archivist', 'indexer', 'viewer'];

export default function AdminDashboardPage() {
  const [activeTab, setActiveTab] = useState<'candidates' | 'sites' | 'thesaurus' | 'quality' | 'users'>('candidates');

  const [candidates, setCandidates] = useState<CandidateItem[]>([]);
  const [candidatesLoading, setCandidatesLoading] = useState(true);
  const [candidatesError, setCandidatesError] = useState(false);
  const [candidateActionError, setCandidateActionError] = useState<string | null>(null);
  const [rejectReasonDrafts, setRejectReasonDrafts] = useState<Record<string, string>>({});

  const [sites, setSites] = useState<SiteItem[]>([]);
  const [sitesLoading, setSitesLoading] = useState(true);
  const [sitesError, setSitesError] = useState(false);
  const [editingSiteId, setEditingSiteId] = useState<string | null>(null);
  const [editSiteDraft, setEditSiteDraft] = useState<Partial<SiteItem>>({});

  const [thesaurus, setThesaurus] = useState<SKOSConcept[]>([]);
  const [thesaurusLoading, setThesaurusLoading] = useState(true);
  const [thesaurusError, setThesaurusError] = useState(false);

  const [qualityItems, setQualityItems] = useState<QualityReviewItem[]>([]);
  const [qualityLoading, setQualityLoading] = useState(true);
  const [qualityError, setQualityError] = useState(false);
  const [qualityThreshold, setQualityThreshold] = useState<number | null>(null);
  const [qualityActionError, setQualityActionError] = useState<string | null>(null);
  const [qualityRejectDrafts, setQualityRejectDrafts] = useState<Record<string, string>>({});
  const [expandedQcId, setExpandedQcId] = useState<string | null>(null);

  const [usersList, setUsersList] = useState<UserItem[]>([]);
  const [usersLoading, setUsersLoading] = useState(false);
  const [usersError, setUsersError] = useState(false);

  const [user, setUser] = useState<any>(null);

  // New site form modal
  const [showAddSite, setShowAddSite] = useState(false);
  const [newDomain, setNewDomain] = useState('');
  const [newBaseUrl, setNewBaseUrl] = useState('');
  const [newPriority, setNewPriority] = useState('medium');
  const [newCategory, setNewCategory] = useState('kozintézmény');
  const [newRightsHolderName, setNewRightsHolderName] = useState('');
  const [newRightsHolderEmail, setNewRightsHolderEmail] = useState('');
  const [newPermissionStatus, setNewPermissionStatus] = useState('nincs_megkeresve');
  const [createSiteError, setCreateSiteError] = useState<string | null>(null);

  // New user form modal
  const [showAddUser, setShowAddUser] = useState(false);
  const [newUserEmail, setNewUserEmail] = useState('');
  const [newUserPassword, setNewUserPassword] = useState('');
  const [newUserRole, setNewUserRole] = useState('curator');
  const [newUserFullName, setNewUserFullName] = useState('');
  const [createUserError, setCreateUserError] = useState<string | null>(null);

  useEffect(() => {
    const userStr = localStorage.getItem('fewa_user');
    if (userStr) setUser(JSON.parse(userStr));

    // URL tab query parameter sync
    const params = new URLSearchParams(window.location.search);
    const tabParam = params.get('tab') as any;
    if (['candidates', 'sites', 'thesaurus', 'quality', 'users'].includes(tabParam)) {
      setActiveTab(tabParam);
    }

    fetchCandidates();
    fetchQualityReview();
    fetchSites();
    fetchThesaurus();
    fetchUsers();
  }, []);

  const changeTab = (tab: 'candidates' | 'sites' | 'thesaurus' | 'quality' | 'users') => {
    setActiveTab(tab);
    const url = new URL(window.location.href);
    url.searchParams.set('tab', tab);
    window.history.replaceState(null, '', url.toString());
  };

  const fetchCandidates = async () => {
    setCandidatesLoading(true);
    setCandidatesError(false);
    try {
      const res = await fetchWithAuth('/api/admin/candidates');
      if (res.ok) {
        const data = await res.json();
        setCandidates(data.items || []);
      } else {
        setCandidatesError(true);
      }
    } catch {
      setCandidatesError(true);
    } finally {
      setCandidatesLoading(false);
    }
  };

  const handleCandidateAction = async (id: string, action: 'approve' | 'reject') => {
    setCandidateActionError(null);
    const reason = rejectReasonDrafts[id] || '';
    if (action === 'reject' && !reason.trim()) {
      setCandidateActionError('Elutasítás esetén a megindoklás kötelező.');
      return;
    }
    try {
      const res = await fetchWithAuth(`/api/admin/candidates/${id}/${action}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: action === 'reject' ? reason : 'Jóváhagyva a kurátori felületről.' }),
      });
      if (res.ok) {
        setCandidates((prev) => prev.filter((item) => item.id !== id));
      } else {
        const err = await res.json().catch(() => ({}));
        setCandidateActionError(err.detail || 'Nem sikerült végrehajtani a műveletet.');
      }
    } catch {
      setCandidateActionError('Hálózati hiba a művelet során.');
    }
  };

  const fetchQualityReview = async () => {
    setQualityLoading(true);
    setQualityError(false);
    try {
      const res = await fetchWithAuth('/api/admin/quality-review');
      if (res.ok) {
        const data = await res.json();
        setQualityItems(data.items || []);
        setQualityThreshold(data.auto_accept_threshold ?? null);
      } else {
        setQualityError(true);
      }
    } catch {
      setQualityError(true);
    } finally {
      setQualityLoading(false);
    }
  };

  const decideQuality = async (id: string, accept: boolean) => {
    setQualityActionError(null);
    const reason = qualityRejectDrafts[id] || '';
    if (!accept && !reason.trim()) {
      setQualityActionError('Visszaküldés esetén az indoklás megadása kötelező.');
      return;
    }
    try {
      const res = await fetchWithAuth(`/api/admin/quality-review/${id}/decide`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: accept ? 'approve' : 'reject',
          reason: accept ? 'Kurátor által manuálisan elfogadva.' : reason,
        }),
      });
      if (res.ok) {
        setQualityItems((prev) => prev.filter((item) => item.id !== id));
      } else {
        const err = await res.json().catch(() => ({}));
        setQualityActionError(err.detail || 'Nem sikerült a minőségi döntés mentése.');
      }
    } catch {
      setQualityActionError('Hálózati hiba a döntés mentésekor.');
    }
  };

  const fetchSites = async () => {
    setSitesLoading(true);
    setSitesError(false);
    try {
      const res = await fetchWithAuth('/api/admin/sites');
      if (res.ok) {
        const data = await res.json();
        setSites(data.items || []);
      } else {
        setSitesError(true);
      }
    } catch {
      setSitesError(true);
    } finally {
      setSitesLoading(false);
    }
  };

  const handleUpdateSite = async (siteId: string) => {
    try {
      const res = await fetchWithAuth(`/api/admin/sites/${siteId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(editSiteDraft),
      });
      if (res.ok) {
        const updated = await res.json();
        setSites((prev) => prev.map((s) => (s.id === siteId ? updated : s)));
        setEditingSiteId(null);
      }
    } catch {
      alert('Nem sikerült a webhely frissítése.');
    }
  };

  const handleCreateSite = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateSiteError(null);
    try {
      const res = await fetchWithAuth('/api/admin/sites', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          domain: newDomain,
          base_url: newBaseUrl,
          priority: newPriority,
          category: newCategory,
          rights_holder_name: newRightsHolderName || undefined,
          rights_holder_email: newRightsHolderEmail || undefined,
          permission_status: newPermissionStatus,
        }),
      });
      if (res.ok) {
        const created = await res.json();
        setSites((prev) => [created, ...prev]);
        setShowAddSite(false);
        setNewDomain('');
        setNewBaseUrl('');
        setNewRightsHolderName('');
        setNewRightsHolderEmail('');
      } else {
        const err = await res.json().catch(() => ({}));
        setCreateSiteError(err.detail || 'Nem sikerült a webhely létrehozása.');
      }
    } catch {
      setCreateSiteError('Hálózati hiba történt.');
    }
  };

  const fetchThesaurus = async () => {
    setThesaurusLoading(true);
    setThesaurusError(false);
    try {
      const res = await fetchWithAuth('/api/thesaurus');
      if (res.ok) {
        const data = await res.json();
        setThesaurus(data.items || []);
      } else {
        setThesaurusError(true);
      }
    } catch {
      setThesaurusError(true);
    } finally {
      setThesaurusLoading(false);
    }
  };

  const fetchUsers = async () => {
    setUsersLoading(true);
    setUsersError(false);
    try {
      const res = await fetchWithAuth('/api/admin/users');
      if (res.ok) {
        const data = await res.json();
        setUsersList(data.items || []);
      } else {
        setUsersError(true);
      }
    } catch {
      setUsersError(true);
    } finally {
      setUsersLoading(false);
    }
  };

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateUserError(null);
    try {
      const res = await fetchWithAuth('/api/admin/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: newUserEmail,
          password: newUserPassword,
          role: newUserRole,
          full_name: newUserFullName,
        }),
      });
      if (res.ok) {
        const created = await res.json();
        setUsersList((prev) => [...prev, created]);
        setShowAddUser(false);
        setNewUserEmail('');
        setNewUserPassword('');
        setNewUserFullName('');
      } else {
        const err = await res.json().catch(() => ({}));
        setCreateUserError(err.detail || 'Nem sikerült a felhasználó létrehozása.');
      }
    } catch {
      setCreateUserError('Hálózati hiba történt.');
    }
  };

  const handleUpdateUserStatus = async (userId: string, role: string, is_active: boolean) => {
    try {
      const res = await fetchWithAuth(`/api/admin/users/${userId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role, is_active }),
      });
      if (res.ok) {
        const updated = await res.json();
        setUsersList((prev) => prev.map((u) => (u.id === userId ? updated : u)));
      } else {
        const err = await res.json().catch(() => ({}));
        alert(err.detail || 'Hiba történt a felhasználó módosításakor.');
      }
    } catch {
      alert('Hálózati hiba történt.');
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
        <div style={{ display: 'flex', gap: '1rem', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '1rem', flexWrap: 'wrap' }}>
          <button
            onClick={() => changeTab('candidates')}
            style={{
              padding: '0.6rem 1.2rem',
              borderRadius: 'var(--radius-md)',
              border: 'none',
              cursor: 'pointer',
              fontWeight: 600,
              background: activeTab === 'candidates' ? 'var(--accent-gradient)' : 'transparent',
              color: activeTab === 'candidates' ? '#fff' : 'var(--text-secondary)',
            }}
          >
            📥 Jóváhagyási Sor ({candidates.length})
          </button>
          <button
            onClick={() => changeTab('sites')}
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
            🌐 Webhelyek & Jogtulajdonosok ({sites.length})
          </button>
          <button
            onClick={() => changeTab('thesaurus')}
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
          <button
            onClick={() => changeTab('quality')}
            style={{
              padding: '0.6rem 1.2rem',
              borderRadius: 'var(--radius-md)',
              border: 'none',
              cursor: 'pointer',
              fontWeight: 600,
              background: activeTab === 'quality' ? 'var(--accent-gradient)' : 'transparent',
              color: activeTab === 'quality' ? '#fff' : 'var(--text-secondary)',
            }}
          >
            🔍 Minőségi Felülvizsgálat ({qualityItems.length})
          </button>
          {user?.role === 'admin' && (
            <button
              onClick={() => changeTab('users')}
              style={{
                padding: '0.6rem 1.2rem',
                borderRadius: 'var(--radius-md)',
                border: 'none',
                cursor: 'pointer',
                fontWeight: 600,
                background: activeTab === 'users' ? 'var(--accent-gradient)' : 'transparent',
                color: activeTab === 'users' ? '#fff' : 'var(--text-secondary)',
              }}
            >
              👥 Felhasználók ({usersList.length})
            </button>
          )}
        </div>

        {/* Tab 0: Candidate Approval Queue */}
        {activeTab === 'candidates' && (
          <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            <h2 style={{ fontSize: '1.2rem' }}>Felfedezett Jelöltek — Jóváhagyásra Várnak</h2>

            {candidateActionError && (
              <div style={{ padding: '0.75rem 1rem', borderRadius: 'var(--radius-sm)', background: 'rgba(244, 63, 94, 0.15)', border: '1px solid rgba(244, 63, 94, 0.4)', color: '#fda4af', fontSize: '0.85rem' }}>
                {candidateActionError}
              </div>
            )}

            {candidatesLoading && (
              <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>Betöltés…</div>
            )}
            {!candidatesLoading && candidatesError && (
              <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
                Nem sikerült betölteni a jóváhagyási sort.
              </div>
            )}
            {!candidatesLoading && !candidatesError && candidates.length === 0 && (
              <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
                Nincs jóváhagyásra váró új jelölt.
              </div>
            )}

            {!candidatesLoading && !candidatesError && candidates.length > 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {candidates.map((c) => (
                  <div key={c.id} className="glass-card" style={{ padding: '1rem 1.25rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem', flexWrap: 'wrap' }}>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', minWidth: '260px' }}>
                        <div style={{ fontWeight: 600 }}>{c.dc_title}</div>
                        <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{c.seed_url}</div>
                        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginTop: '0.25rem' }}>
                          <span className="badge badge-blue">{PRIORITY_LABELS_HU[c.priority] || c.priority}</span>
                          <span className="badge badge-amber">{c.category}</span>
                          {c.municipality_name && <span className="badge badge-cyan">📍 {c.municipality_name}</span>}
                        </div>
                      </div>
                      <div style={{ display: 'flex', gap: '0.5rem' }}>
                        <button onClick={() => handleCandidateAction(c.id, 'approve')} className="btn-primary" style={{ padding: '0.4rem 1rem', fontSize: '0.85rem' }}>
                          ✓ Indítás
                        </button>
                        <button onClick={() => handleCandidateAction(c.id, 'reject')} className="btn-secondary" style={{ padding: '0.4rem 1rem', fontSize: '0.85rem' }}>
                          ✕ Elutasítás
                        </button>
                      </div>
                    </div>
                    <input
                      type="text"
                      placeholder="Elutasítás indoka (kötelező elutasítás esetén)…"
                      value={rejectReasonDrafts[c.id] ?? ''}
                      onChange={(e) => setRejectReasonDrafts((prev) => ({ ...prev, [c.id]: e.target.value }))}
                      style={{
                        padding: '0.5rem 0.75rem',
                        borderRadius: 'var(--radius-sm)',
                        background: 'rgba(255,255,255,0.04)',
                        border: '1px solid rgba(255,255,255,0.1)',
                        color: 'var(--text-primary)',
                        fontSize: '0.85rem',
                      }}
                    />
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Tab 1: Sites List & Rights Holder Edit */}
        {activeTab === 'sites' && (
          <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h2 style={{ fontSize: '1.2rem' }}>Archiválandó Webhelyek & Jogtulajdonosok</h2>
              <button className="btn-primary" onClick={() => setShowAddSite(true)} style={{ padding: '0.4rem 1rem', fontSize: '0.85rem' }}>
                + Új Webhely
              </button>
            </div>

            {sitesLoading && (
              <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>Betöltés…</div>
            )}
            {!sitesLoading && sitesError && (
              <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
                Nem sikerült betölteni a webhelyek listáját.
              </div>
            )}

            {!sitesLoading && !sitesError && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                {sites.map((site) => (
                  <div key={site.id} className="glass-card" style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                      <div>
                        <div style={{ fontWeight: 700, fontSize: '1.1rem' }}>{site.display_name || site.domain}</div>
                        <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>{site.base_url || site.domain}</div>
                      </div>
                      <button
                        onClick={() => {
                          if (editingSiteId === site.id) {
                            setEditingSiteId(null);
                          } else {
                            setEditingSiteId(site.id);
                            setEditSiteDraft(site);
                          }
                        }}
                        className="btn-secondary"
                        style={{ padding: '0.35rem 0.8rem', fontSize: '0.8rem' }}
                      >
                        {editingSiteId === site.id ? 'Mégse' : '✏️ Szerkesztés'}
                      </button>
                    </div>

                    {editingSiteId === site.id ? (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', background: 'rgba(255,255,255,0.02)', padding: '1rem', borderRadius: 'var(--radius-sm)' }}>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem' }}>
                          <div>
                            <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Prioritás</label>
                            <select
                              className="input-search"
                              value={editSiteDraft.priority ?? site.priority}
                              onChange={(e) => setEditSiteDraft({ ...editSiteDraft, priority: e.target.value })}
                            >
                              {PRIORITY_OPTIONS.map((p) => (
                                <option key={p} value={p}>{PRIORITY_LABELS_HU[p] || p}</option>
                              ))}
                            </select>
                          </div>
                          <div>
                            <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Kategória</label>
                            <select
                              className="input-search"
                              value={editSiteDraft.category ?? site.category}
                              onChange={(e) => setEditSiteDraft({ ...editSiteDraft, category: e.target.value })}
                            >
                              {CATEGORY_OPTIONS.map((c) => (
                                <option key={c} value={c}>{c}</option>
                              ))}
                            </select>
                          </div>
                          <div>
                            <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Jogtulajdonos Neve</label>
                            <input
                              type="text"
                              className="input-search"
                              value={editSiteDraft.rights_holder_name ?? site.rights_holder_name ?? ''}
                              onChange={(e) => setEditSiteDraft({ ...editSiteDraft, rights_holder_name: e.target.value })}
                              placeholder="pl. Székesfehérvár MJV"
                            />
                          </div>
                          <div>
                            <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Jogtulajdonos Email</label>
                            <input
                              type="email"
                              className="input-search"
                              value={editSiteDraft.rights_holder_email ?? site.rights_holder_email ?? ''}
                              onChange={(e) => setEditSiteDraft({ ...editSiteDraft, rights_holder_email: e.target.value })}
                              placeholder="kapcsolat@szekesfehervar.hu"
                            />
                          </div>
                          <div>
                            <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Engedély Státusz</label>
                            <select
                              className="input-search"
                              value={editSiteDraft.permission_status ?? site.permission_status ?? 'nincs_megkeresve'}
                              onChange={(e) => setEditSiteDraft({ ...editSiteDraft, permission_status: e.target.value })}
                            >
                              {PERMISSION_STATUS_OPTIONS.map((opt) => (
                                <option key={opt.value} value={opt.value}>{opt.label}</option>
                              ))}
                            </select>
                          </div>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
                          <button onClick={() => handleUpdateSite(site.id)} className="btn-primary" style={{ padding: '0.4rem 1rem', fontSize: '0.85rem' }}>
                            Mentés
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                        <div><strong>Prioritás:</strong> {PRIORITY_LABELS_HU[site.priority] || site.priority}</div>
                        <div><strong>Kategória:</strong> {site.category}</div>
                        <div><strong>Jogtulajdonos:</strong> {site.rights_holder_name || 'Nincs megadva'} ({site.rights_holder_email || 'nincs email'})</div>
                        <div>
                          <strong>Engedély:</strong>{' '}
                          <span className="badge badge-amber">{site.permission_status || 'nincs_megkeresve'}</span>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Tab 2: SKOS Thesaurus */}
        {activeTab === 'thesaurus' && (
          <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            <h2 style={{ fontSize: '1.2rem' }}>SKOS Tezaurusz Fogalmak</h2>
            {thesaurusLoading && <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>Betöltés…</div>}
            {!thesaurusLoading && thesaurusError && (
              <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
                Nem sikerült betölteni a tezaurusz fogalmakat.
              </div>
            )}
            {!thesaurusLoading && !thesaurusError && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '1rem' }}>
                {thesaurus.map((c) => (
                  <div key={c.id} className="glass-card" style={{ padding: '1rem' }}>
                    <div style={{ fontWeight: 600, fontSize: '1rem', color: 'var(--text-primary)' }}>
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
            )}
          </div>
        )}

        {/* Tab 3: Quality Review Queue & UX Breakdown */}
        {activeTab === 'quality' && (
          <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            <div>
              <h2 style={{ fontSize: '1.2rem' }}>Minőségi Felülvizsgálat</h2>
              <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
                Archivált mentések, amelyek QC pontszáma a küszöb alatt van (vagy még nincs kiértékelve)
                {qualityThreshold !== null ? ` — automatikus elfogadási küszöb: ${qualityThreshold}%` : ''}.
              </p>
            </div>

            {qualityActionError && (
              <div style={{ padding: '0.75rem 1rem', borderRadius: 'var(--radius-sm)', background: 'rgba(244, 63, 94, 0.15)', border: '1px solid rgba(244, 63, 94, 0.4)', color: '#fda4af', fontSize: '0.85rem' }}>
                {qualityActionError}
              </div>
            )}

            {qualityLoading && (
              <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>Betöltés…</div>
            )}
            {!qualityLoading && qualityError && (
              <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
                A minőségi felülvizsgálati sor jelenleg nem elérhető.
              </div>
            )}
            {!qualityLoading && !qualityError && qualityItems.length === 0 && (
              <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
                Nincs felülvizsgálatra váró mentés.
              </div>
            )}

            {!qualityLoading && !qualityError && qualityItems.length > 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                {qualityItems.map((q) => (
                  <div key={q.id} className="glass-card" style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem', flexWrap: 'wrap' }}>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', minWidth: '260px' }}>
                        <div style={{ fontWeight: 600 }}>{q.dc_title}</div>
                        <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{q.seed_url}</div>
                        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', fontSize: '0.85rem', flexWrap: 'wrap' }}>
                          <span
                            style={{
                              padding: '0.15rem 0.6rem',
                              borderRadius: '999px',
                              background: q.qc_score === null ? 'rgba(255,255,255,0.06)' : q.qc_score >= 50 ? 'rgba(234,179,8,0.15)' : 'rgba(244,63,94,0.15)',
                              color: q.qc_score === null ? 'var(--text-secondary)' : q.qc_score >= 50 ? '#facc15' : '#fda4af',
                              fontWeight: 600,
                            }}
                          >
                            {q.qc_score === null ? '⏳ QC számítás folyamatban (~15-20 perc)' : `QC Pontszám: ${q.qc_score}%`}
                          </span>
                          <a href={`/admin/documents/${q.id}`} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent-cyan)', textDecoration: 'underline', fontSize: '0.8rem' }}>
                            🔁 Előnézet / Visszajátszás
                          </a>
                          {q.qc_detail?.pages && (
                            <button
                              onClick={() => setExpandedQcId(expandedQcId === q.id ? null : q.id)}
                              className="btn-secondary"
                              style={{ padding: '0.2rem 0.6rem', fontSize: '0.75rem' }}
                            >
                              {expandedQcId === q.id ? 'Elrejtés' : '📊 Részletes pontszám bontás'}
                            </button>
                          )}
                        </div>
                      </div>
                      <div style={{ display: 'flex', gap: '0.5rem' }}>
                        <button onClick={() => decideQuality(q.id, true)} className="btn-primary" style={{ padding: '0.4rem 1rem', fontSize: '0.85rem' }}>
                          ✓ Elfogadás mégis
                        </button>
                        <button onClick={() => decideQuality(q.id, false)} className="btn-secondary" style={{ padding: '0.4rem 1rem', fontSize: '0.85rem' }}>
                          ↩ Visszaküldés
                        </button>
                      </div>
                    </div>

                    {/* Page-by-page QC detail breakdown */}
                    {expandedQcId === q.id && q.qc_detail?.pages && (
                      <div style={{ background: 'rgba(0,0,0,0.2)', padding: '0.75rem', borderRadius: 'var(--radius-sm)', marginTop: '0.5rem' }}>
                        <div style={{ fontSize: '0.8rem', fontWeight: 600, marginBottom: '0.5rem', color: 'var(--text-secondary)' }}>
                          Oldalankénti hasonlósági bontás (Browsertrix QA):
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                          {q.qc_detail.pages.map((p, idx) => (
                            <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', padding: '0.25rem 0.5rem', background: 'rgba(255,255,255,0.03)', borderRadius: '4px' }}>
                              <span style={{ color: 'var(--text-primary)', wordBreak: 'break-all', maxWidth: '60%' }}>{p.url}</span>
                              <div style={{ display: 'flex', gap: '1rem' }}>
                                <span>Kép: {p.screenshotMatch !== null && p.screenshotMatch !== undefined ? `${Math.round(p.screenshotMatch * 100)}%` : 'N/A'}</span>
                                <span>Szöveg: {p.textMatch !== null && p.textMatch !== undefined ? `${Math.round(p.textMatch * 100)}%` : 'N/A'}</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    <input
                      type="text"
                      placeholder="Visszaküldés indoka (kötelező visszaküldéshez)…"
                      value={qualityRejectDrafts[q.id] ?? ''}
                      onChange={(e) => setQualityRejectDrafts((prev) => ({ ...prev, [q.id]: e.target.value }))}
                      style={{
                        padding: '0.5rem 0.75rem',
                        borderRadius: 'var(--radius-sm)',
                        background: 'rgba(255,255,255,0.04)',
                        border: '1px solid rgba(255,255,255,0.1)',
                        color: 'var(--text-primary)',
                        fontSize: '0.85rem',
                      }}
                    />
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Tab 4: Users Management */}
        {activeTab === 'users' && user?.role === 'admin' && (
          <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h2 style={{ fontSize: '1.2rem' }}>Felhasználók Kezelése</h2>
              <button className="btn-primary" onClick={() => setShowAddUser(true)} style={{ padding: '0.4rem 1rem', fontSize: '0.85rem' }}>
                + Új Felhasználó
              </button>
            </div>

            {usersLoading && <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>Betöltés…</div>}
            {!usersLoading && usersError && (
              <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
                Nem sikerült betölteni a felhasználók listáját.
              </div>
            )}

            {!usersLoading && !usersError && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {usersList.map((u) => (
                  <div key={u.id} className="glass-card" style={{ padding: '1rem 1.25rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
                    <div>
                      <div style={{ fontWeight: 600 }}>{u.full_name} ({u.email})</div>
                      <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                        ID: {u.id}
                      </div>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                      <select
                        className="input-search"
                        value={u.role}
                        onChange={(e) => handleUpdateUserStatus(u.id, e.target.value, u.is_active)}
                        disabled={u.id === user?.sub}
                        style={{ padding: '0.3rem 0.6rem', fontSize: '0.85rem' }}
                      >
                        {ROLE_OPTIONS.map((r) => (
                          <option key={r} value={r}>{r}</option>
                        ))}
                      </select>
                      <button
                        onClick={() => handleUpdateUserStatus(u.id, u.role, !u.is_active)}
                        disabled={u.id === user?.sub}
                        className={u.is_active ? 'btn-secondary' : 'btn-primary'}
                        style={{ padding: '0.35rem 0.8rem', fontSize: '0.8rem' }}
                      >
                        {u.is_active ? 'Inaktiválás' : 'Aktiválás'}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Add Site Modal */}
      {showAddSite && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', display: 'grid', placeItems: 'center', zIndex: 100 }}>
          <div className="glass-panel animate-fade-in" style={{ width: '100%', maxWidth: '550px', padding: '2rem' }}>
            <h3 style={{ marginBottom: '1rem' }}>Új Archiválandó Webhely</h3>
            <form onSubmit={handleCreateSite} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {createSiteError && (
                <div style={{ padding: '0.75rem 1rem', borderRadius: 'var(--radius-sm)', background: 'rgba(244, 63, 94, 0.15)', border: '1px solid rgba(244, 63, 94, 0.4)', color: '#fda4af', fontSize: '0.85rem' }}>
                  {createSiteError}
                </div>
              )}
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
                    {PRIORITY_OPTIONS.map((p) => (
                      <option key={p} value={p}>{PRIORITY_LABELS_HU[p] || p}</option>
                    ))}
                  </select>
                </div>
                <div style={{ flex: 1 }}>
                  <label style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Kategória</label>
                  <select className="input-search" value={newCategory} onChange={(e) => setNewCategory(e.target.value)}>
                    {CATEGORY_OPTIONS.map((c) => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                </div>
              </div>
              <div style={{ display: 'flex', gap: '1rem' }}>
                <div style={{ flex: 1 }}>
                  <label style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Jogtulajdonos Neve</label>
                  <input type="text" className="input-search" placeholder="Kovács János" value={newRightsHolderName} onChange={(e) => setNewRightsHolderName(e.target.value)} />
                </div>
                <div style={{ flex: 1 }}>
                  <label style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Jogtulajdonos Email</label>
                  <input type="email" className="input-search" placeholder="janos@example.com" value={newRightsHolderEmail} onChange={(e) => setNewRightsHolderEmail(e.target.value)} />
                </div>
              </div>
              <div>
                <label style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Engedély Státusz</label>
                <select className="input-search" value={newPermissionStatus} onChange={(e) => setNewPermissionStatus(e.target.value)}>
                  {PERMISSION_STATUS_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', marginTop: '1rem' }}>
                <button type="button" className="btn-secondary" onClick={() => { setShowAddSite(false); setCreateSiteError(null); }}>Mégse</button>
                <button type="submit" className="btn-primary">Mentés</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Add User Modal */}
      {showAddUser && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', display: 'grid', placeItems: 'center', zIndex: 100 }}>
          <div className="glass-panel animate-fade-in" style={{ width: '100%', maxWidth: '500px', padding: '2rem' }}>
            <h3 style={{ marginBottom: '1rem' }}>Új Felhasználó Hozzáadása</h3>
            <form onSubmit={handleCreateUser} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {createUserError && (
                <div style={{ padding: '0.75rem 1rem', borderRadius: 'var(--radius-sm)', background: 'rgba(244, 63, 94, 0.15)', border: '1px solid rgba(244, 63, 94, 0.4)', color: '#fda4af', fontSize: '0.85rem' }}>
                  {createUserError}
                </div>
              )}
              <div>
                <label style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Email Cím</label>
                <input type="email" className="input-search" placeholder="ujszerkeszto@vmk.hu" value={newUserEmail} onChange={(e) => setNewUserEmail(e.target.value)} required />
              </div>
              <div>
                <label style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Jelszó (min 8 karakter)</label>
                <input type="password" className="input-search" placeholder="••••••••" value={newUserPassword} onChange={(e) => setNewUserPassword(e.target.value)} required minLength={8} />
              </div>
              <div>
                <label style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Teljes Név</label>
                <input type="text" className="input-search" placeholder="Kovács Anna" value={newUserFullName} onChange={(e) => setNewUserFullName(e.target.value)} required />
              </div>
              <div>
                <label style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Szerepkör (RBAC)</label>
                <select className="input-search" value={newUserRole} onChange={(e) => setNewUserRole(e.target.value)}>
                  {ROLE_OPTIONS.map((r) => (
                    <option key={r} value={r}>{r}</option>
                  ))}
                </select>
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', marginTop: '1rem' }}>
                <button type="button" className="btn-secondary" onClick={() => { setShowAddUser(false); setCreateUserError(null); }}>Mégse</button>
                <button type="submit" className="btn-primary">Létrehozás</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
