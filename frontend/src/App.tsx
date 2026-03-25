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
