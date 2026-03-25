export interface LoginRequest {
  username: string
  password: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  role: string
}

export interface AuthUser {
  username: string
  role: string
}

export interface Source {
  file: string
  section: string
}

export interface QueryRequest {
  query: string
}

export interface QueryResponse {
  answer: string
  sources: Source[]
  role: string
}

export interface ApiError {
  detail: string
}
