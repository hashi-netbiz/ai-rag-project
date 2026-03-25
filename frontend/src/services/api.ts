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
