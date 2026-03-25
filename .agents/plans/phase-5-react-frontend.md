# Feature: Phase 5 — React Frontend

The following plan is complete. All stubs are in `frontend/src/`. Implementation order matters — each file depends on the one above it.

## Feature Description

Build the complete React TypeScript chat UI: JWT auth context, Axios service layer, Login form, Chat interface, message bubbles, and source citation chips. Replace the CRA boilerplate `App.tsx` with the actual app routing (Login ↔ Chat based on auth state).

## User Story

As an employee,
I want to log in with my username and password and send natural language queries,
So that I receive role-appropriate answers with source citations in a clean chat interface.

## Problem Statement

All 6 component/context/service files are empty stubs. `App.tsx` is the default CRA boilerplate. The frontend renders nothing useful.

## Solution Statement

Implement in dependency order:
1. `services/api.ts` — Axios instance + login/query functions (no React dependencies)
2. `contexts/AuthContext.tsx` — JWT state + localStorage persistence (depends on api.ts)
3. `components/SourceCitation.tsx` — leaf component, no deps on other custom components
4. `components/MessageBubble.tsx` — uses SourceCitation
5. `components/Login.tsx` — uses AuthContext
6. `components/Chat.tsx` — uses AuthContext + api.ts + MessageBubble
7. `App.tsx` — wires AuthProvider + conditional Login/Chat render
8. `App.css` — minimal viewport reset

## Feature Metadata

**Feature Type**: New Capability
**Estimated Complexity**: Medium
**Primary Systems Affected**: `frontend/src/`
**Dependencies**: React 19, TypeScript 4.9.5, Axios 1.13.6 — all installed

---

## CONTEXT REFERENCES

### Backend API Contract (from Phase 3 & 4)

```
POST http://localhost:8000/auth/login
Body: {"username": string, "password": string}
Response: {"access_token": string, "token_type": "bearer", "role": string}
Error 401: {"detail": "Incorrect username or password"}

POST http://localhost:8000/chat/query
Header: Authorization: Bearer <token>
Body: {"query": string}
Response: {
  "answer": string,
  "sources": [{"file": string, "section": string}],
  "role": string
}
Error 401: {"detail": "Not authenticated"}

GET http://localhost:8000/health
Response: {"status": "ok"}
```

### Files to Implement (all stubs)
- `frontend/src/services/api.ts`
- `frontend/src/contexts/AuthContext.tsx`
- `frontend/src/components/SourceCitation.tsx`
- `frontend/src/components/MessageBubble.tsx`
- `frontend/src/components/Login.tsx`
- `frontend/src/components/Chat.tsx`

### Files to Replace
- `frontend/src/App.tsx` — CRA boilerplate → auth-conditional render
- `frontend/src/App.css` — CRA defaults → minimal app styles

### Files to Keep Unchanged
- `frontend/src/index.tsx`, `index.css`, `reportWebVitals.ts`, `setupTests.ts`, `react-app-env.d.ts`

---

## STEP-BY-STEP TASKS

### TASK 1 — IMPLEMENT `frontend/src/services/api.ts`

```typescript
import axios from 'axios';

const BASE_URL = 'http://localhost:8000';

const apiClient = axios.create({ baseURL: BASE_URL });

// Attach stored JWT to every request
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export interface LoginResponse {
  access_token: string;
  token_type: string;
  role: string;
}

export interface Source {
  file: string;
  section: string;
}

export interface QueryResponse {
  answer: string;
  sources: Source[];
  role: string;
}

export const login = async (username: string, password: string): Promise<LoginResponse> => {
  const response = await apiClient.post<LoginResponse>('/auth/login', { username, password });
  return response.data;
};

export const chatQuery = async (query: string): Promise<QueryResponse> => {
  const response = await apiClient.post<QueryResponse>('/chat/query', { query });
  return response.data;
};

export default apiClient;
```

- **VALIDATE**: TypeScript compiles — checked via `cd frontend && npx tsc --noEmit`

---

### TASK 2 — IMPLEMENT `frontend/src/contexts/AuthContext.tsx`

```typescript
import React, { createContext, useContext, useState, ReactNode } from 'react';
import { login as apiLogin, LoginResponse } from '../services/api';

interface AuthUser {
  username: string;
  role: string;
}

interface AuthContextType {
  user: AuthUser | null;
  token: string | null;
  isAuthenticated: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('token'));
  const [user, setUser] = useState<AuthUser | null>(() => {
    const stored = localStorage.getItem('user');
    return stored ? JSON.parse(stored) : null;
  });

  const login = async (username: string, password: string): Promise<void> => {
    const data: LoginResponse = await apiLogin(username, password);
    localStorage.setItem('token', data.access_token);
    localStorage.setItem('user', JSON.stringify({ username, role: data.role }));
    setToken(data.access_token);
    setUser({ username, role: data.role });
  };

  const logout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, token, isAuthenticated: !!token, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
```

- **GOTCHA**: `useState` initializer reads from `localStorage` synchronously — safe in browser, not in SSR (not relevant here).
- **VALIDATE**: `cd frontend && npx tsc --noEmit`

---

### TASK 3 — IMPLEMENT `frontend/src/components/SourceCitation.tsx`

```typescript
import React from 'react';
import { Source } from '../services/api';

interface Props {
  source: Source;
}

export default function SourceCitation({ source }: Props) {
  const label = source.section ? `${source.file} › ${source.section}` : source.file;
  return (
    <span style={{
      display: 'inline-block',
      background: '#e8f4fd',
      border: '1px solid #b3d9f5',
      borderRadius: '12px',
      padding: '2px 10px',
      fontSize: '0.75rem',
      color: '#1a6ea0',
      margin: '2px 4px 2px 0',
    }}>
      📄 {label}
    </span>
  );
}
```

---

### TASK 4 — IMPLEMENT `frontend/src/components/MessageBubble.tsx`

```typescript
import React from 'react';
import SourceCitation from './SourceCitation';
import { Source } from '../services/api';

interface Props {
  role: 'user' | 'assistant';
  content: string;
  sources?: Source[];
}

export default function MessageBubble({ role, content, sources }: Props) {
  const isUser = role === 'user';
  return (
    <div style={{
      display: 'flex',
      justifyContent: isUser ? 'flex-end' : 'flex-start',
      marginBottom: '12px',
    }}>
      <div style={{
        maxWidth: '75%',
        background: isUser ? '#0078d4' : '#f3f4f6',
        color: isUser ? '#fff' : '#1f2937',
        borderRadius: isUser ? '18px 18px 4px 18px' : '18px 18px 18px 4px',
        padding: '10px 14px',
        boxShadow: '0 1px 2px rgba(0,0,0,0.08)',
      }}>
        <p style={{ margin: 0, lineHeight: 1.5, whiteSpace: 'pre-wrap' }}>{content}</p>
        {sources && sources.length > 0 && (
          <div style={{ marginTop: '8px' }}>
            {sources.map((s, i) => (
              <SourceCitation key={i} source={s} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
```

---

### TASK 5 — IMPLEMENT `frontend/src/components/Login.tsx`

```typescript
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
```

---

### TASK 6 — IMPLEMENT `frontend/src/components/Chat.tsx`

```typescript
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
```

---

### TASK 7 — REPLACE `frontend/src/App.tsx`

```typescript
import React from 'react';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import Login from './components/Login';
import Chat from './components/Chat';

function AppContent() {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? <Chat /> : <Login />;
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}
```

- **GOTCHA**: `useAuth()` must be called inside a component that is a child of `AuthProvider`. `AppContent` is a child of `AuthProvider` in `App`. Do NOT call `useAuth()` directly in `App`.

---

### TASK 8 — REPLACE `frontend/src/App.css`

```css
*, *::before, *::after {
  box-sizing: border-box;
}

body, html, #root {
  margin: 0;
  padding: 0;
  height: 100%;
}
```

---

### TASK 9 — VERIFY TypeScript compile + build

```bash
cd frontend && npx tsc --noEmit
cd frontend && npm run build 2>&1 | tail -10
```

---

## VALIDATION COMMANDS

### Level 1: TypeScript compile (no errors)
```bash
cd frontend && npx tsc --noEmit
```

### Level 2: Production build succeeds
```bash
cd frontend && npm run build 2>&1 | tail -10
```

### Level 3: Dev server starts
```bash
cd frontend && npm start &
sleep 5
curl -s http://localhost:3000 | grep -o '<div id="root">' || echo "root div not found"
kill %1
```

---

## ACCEPTANCE CRITERIA

- [ ] TypeScript compiles with zero errors
- [ ] `npm run build` succeeds
- [ ] Dev server starts on port 3000
- [ ] Login form renders when unauthenticated
- [ ] Successful login renders Chat UI with role badge
- [ ] Failed login shows error message
- [ ] Sending a query shows answer + source citation chips
- [ ] Sign out returns to Login screen and clears localStorage

---

## NOTES

**No external style library**: All styling is done with inline styles — no Tailwind, Bootstrap, or CSS modules. This avoids any new dependency and keeps the build clean.

**`App.test.tsx`**: The existing default test checks for "learn react" text — it will break after we replace `App.tsx`. It should be deleted or updated. For MVP purposes, deleting it is acceptable since no test strategy is defined for the frontend. Updated to `export {};` stub.

**CORS**: Backend is already configured for `http://localhost:3000` — no changes needed.

**`logo.svg` import**: The current `App.tsx` imports `logo.svg`. After replacement, this import is gone. The file can stay in `src/` — it just won't be referenced.
