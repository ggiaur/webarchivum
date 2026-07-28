'use client';

import React, { useState } from 'react';

export default function AdminLoginPage() {
  const [email, setEmail] = useState('curator@vmk.hu');
  const [password, setPassword] = useState('SecretPassword123!');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      const res = await fetch('http://localhost:8000/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || 'Érvénytelen bejelentkezési adatok.');
      }

      const data = await res.json();
      localStorage.setItem('fewa_access_token', data.access_token);
      localStorage.setItem('fewa_refresh_token', data.refresh_token);
      localStorage.setItem('fewa_user', JSON.stringify(data.user));

      window.location.href = '/admin/dashboard';
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', background: 'var(--bg-primary)', padding: '1rem' }}>
      <div className="glass-panel animate-fade-in" style={{ width: '100%', maxWidth: '420px', padding: '2.5rem' }}>
        <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
          <div style={{ width: '48px', height: '48px', background: 'var(--accent-gradient)', borderRadius: '12px', display: 'grid', placeItems: 'center', fontWeight: 'bold', fontSize: '1.2rem', color: '#fff', margin: '0 auto 1rem' }}>
            FW
          </div>
          <h1 style={{ fontSize: '1.6rem', marginBottom: '0.25rem' }}>Kurátori Portál</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>Vörösmarty Mihály Könyvtár Adminisztráció</p>
        </div>

        {error && (
          <div style={{ background: 'rgba(244, 63, 94, 0.15)', border: '1px solid rgba(244, 63, 94, 0.3)', color: '#f43f5e', padding: '0.75rem', borderRadius: 'var(--radius-sm)', fontSize: '0.85rem', marginBottom: '1.5rem' }}>
            ⚠️ {error}
          </div>
        )}

        <form onSubmit={handleLogin} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <div>
            <label htmlFor="login-email" style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.4rem' }}>
              Könyvtáros Email
            </label>
            <input
              id="login-email"
              type="email"
              className="input-search"
              style={{ borderRadius: 'var(--radius-md)', fontSize: '0.95rem' }}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>

          <div>
            <label htmlFor="login-password" style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.4rem' }}>
              Jelszó
            </label>
            <input
              id="login-password"
              type="password"
              className="input-search"
              style={{ borderRadius: 'var(--radius-md)', fontSize: '0.95rem' }}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>

          <button type="submit" className="btn-primary" style={{ justifyContent: 'center', marginTop: '0.5rem' }} disabled={isLoading}>
            {isLoading ? 'Bejelentkezés...' : 'Bejelentkezés ➔'}
          </button>
        </form>
      </div>
    </div>
  );
}
