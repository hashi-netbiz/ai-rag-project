import type { LoginResponse, QueryResponse } from '@/types/api'

function getToken(): string | null {
  if (typeof window === 'undefined') return null
  return localStorage.getItem('token')
}

function authHeaders(): HeadersInit {
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export async function apiLogin(
  username: string,
  password: string,
): Promise<LoginResponse> {
  const res = await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Login failed' })) as { detail?: string }
    throw new Error(err.detail ?? 'Login failed')
  }
  return res.json() as Promise<LoginResponse>
}

export async function apiChatQuery(query: string): Promise<QueryResponse> {
  const res = await fetch('/api/chat/query', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
    },
    body: JSON.stringify({ query }),
  })
  if (!res.ok) {
    if (res.status === 401) throw new Error('Session expired. Please log in again.')
    const err = await res.json().catch(() => ({ detail: 'Query failed' })) as { detail?: string }
    throw new Error(err.detail ?? 'Query failed')
  }
  return res.json() as Promise<QueryResponse>
}
