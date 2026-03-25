import React, { useState, FormEvent } from 'react';
import { useAuth } from '../contexts/AuthContext';

export default function Login() {
  const { login } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(username, password);
    } catch {
      setError('Invalid username or password');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center',
      justifyContent: 'center', background: '#f9fafb',
    }}>
      <div style={{
        background: '#fff', borderRadius: '12px', padding: '40px',
        boxShadow: '0 4px 24px rgba(0,0,0,0.08)', width: '340px',
      }}>
        <h1 style={{ margin: '0 0 8px', fontSize: '1.5rem', color: '#111827' }}>
          Company Assistant
        </h1>
        <p style={{ margin: '0 0 24px', color: '#6b7280', fontSize: '0.9rem' }}>
          Sign in to access your knowledge base
        </p>
        <form onSubmit={handleSubmit}>
          <label style={{ display: 'block', marginBottom: '4px', fontSize: '0.85rem', color: '#374151' }}>
            Username
          </label>
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            style={{
              width: '100%', padding: '9px 12px', borderRadius: '8px',
              border: '1px solid #d1d5db', marginBottom: '16px',
              fontSize: '0.95rem', boxSizing: 'border-box',
            }}
          />
          <label style={{ display: 'block', marginBottom: '4px', fontSize: '0.85rem', color: '#374151' }}>
            Password
          </label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            style={{
              width: '100%', padding: '9px 12px', borderRadius: '8px',
              border: '1px solid #d1d5db', marginBottom: '20px',
              fontSize: '0.95rem', boxSizing: 'border-box',
            }}
          />
          {error && (
            <p style={{ color: '#ef4444', fontSize: '0.85rem', margin: '0 0 16px' }}>{error}</p>
          )}
          <button
            type="submit"
            disabled={loading}
            style={{
              width: '100%', padding: '10px', background: loading ? '#93c5fd' : '#0078d4',
              color: '#fff', border: 'none', borderRadius: '8px',
              fontSize: '0.95rem', cursor: loading ? 'not-allowed' : 'pointer',
            }}
          >
            {loading ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
      </div>
    </div>
  );
}
