'use client';

import React, { useState, useEffect } from 'react';
import { getApiBaseUrl } from '../utils/apiConfig';

export default function OaiNavLink() {
  const [url, setUrl] = useState('http://localhost:8000/oai?verb=Identify');

  useEffect(() => {
    setUrl(`${getApiBaseUrl()}/oai?verb=Identify`);
  }, []);

  return (
    <a href={url} target="_blank" rel="noopener noreferrer" className="nav-btn" style={{
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
      🌐 OAI-PMH
    </a>
  );
}
