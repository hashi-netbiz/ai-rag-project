import React, { useState, useRef, useEffect, FormEvent } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { chatQuery, Source } from '../services/api';
import MessageBubble from './MessageBubble';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  sources?: Source[];
}

export default function Chat() {
  const { user, logout } = useAuth();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const query = input.trim();
    if (!query || loading) return;

    setInput('');
    setMessages((prev) => [...prev, { role: 'user', content: query }]);
    setLoading(true);

    try {
      const result = await chatQuery(query);
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: result.answer, sources: result.sources },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: 'Something went wrong. Please try again.' },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const ROLE_COLORS: Record<string, string> = {
    finance: '#16a34a', marketing: '#d97706', hr: '#7c3aed',
    engineering: '#0369a1', c_level: '#dc2626', employee: '#6b7280',
  };
  const roleColor = ROLE_COLORS[user?.role ?? ''] ?? '#6b7280';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: '#f9fafb' }}>
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '12px 20px', background: '#fff', borderBottom: '1px solid #e5e7eb',
        boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
      }}>
        <div>
          <span style={{ fontWeight: 600, fontSize: '1rem', color: '#111827' }}>
            Company Assistant
          </span>
          {user && (
            <span style={{
              marginLeft: '10px', background: roleColor, color: '#fff',
              borderRadius: '12px', padding: '2px 10px', fontSize: '0.75rem',
            }}>
              {user.role}
            </span>
          )}
        </div>
        <button
          onClick={logout}
          style={{
            background: 'none', border: '1px solid #d1d5db', borderRadius: '8px',
            padding: '6px 14px', cursor: 'pointer', fontSize: '0.85rem', color: '#374151',
          }}
        >
          Sign out
        </button>
      </div>

      {/* Messages */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '20px' }}>
        {messages.length === 0 && (
          <p style={{ textAlign: 'center', color: '#9ca3af', marginTop: '60px' }}>
            Ask a question about company data
          </p>
        )}
        {messages.map((msg, i) => (
          <MessageBubble key={i} role={msg.role} content={msg.content} sources={msg.sources} />
        ))}
        {loading && (
          <MessageBubble role="assistant" content="Thinking…" />
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <form
        onSubmit={handleSubmit}
        style={{
          display: 'flex', gap: '10px', padding: '16px 20px',
          background: '#fff', borderTop: '1px solid #e5e7eb',
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a question…"
          disabled={loading}
          style={{
            flex: 1, padding: '10px 14px', borderRadius: '24px',
            border: '1px solid #d1d5db', fontSize: '0.95rem', outline: 'none',
          }}
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          style={{
            padding: '10px 20px', background: loading ? '#93c5fd' : '#0078d4',
            color: '#fff', border: 'none', borderRadius: '24px',
            cursor: loading ? 'not-allowed' : 'pointer', fontSize: '0.95rem',
          }}
        >
          Send
        </button>
      </form>
    </div>
  );
}
