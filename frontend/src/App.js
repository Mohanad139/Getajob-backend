import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from './context/AuthContext';
import Sidebar from './components/Sidebar';
import Login from './pages/Login';
import Register from './pages/Register';
import Dashboard from './pages/Dashboard';
import Jobs from './pages/Jobs';
import Applications from './pages/Applications';
import ResumeBuilder from './pages/ResumeBuilder';
import Interview from './pages/Interview';

const PrivateRoute = ({ children }) => {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="loading">
        <div className="spinner"></div>
      </div>
    );
  }

  return user ? children : <Navigate to="/login" />;
};

const PublicRoute = ({ children }) => {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="loading">
        <div className="spinner"></div>
      </div>
    );
  }

  return user ? <Navigate to="/dashboard" /> : children;
};

const AppLayout = ({ children }) => {
  return (
    <div className="app-layout">
      <Sidebar />
      <main className="main-content">
        {children}
      </main>
    </div>
  );
};

function App() {
  const { user } = useAuth();

  return (
    <div className="app">
      <Routes>
        <Route path="/login" element={<PublicRoute><Login /></PublicRoute>} />
        <Route path="/register" element={<PublicRoute><Register /></PublicRoute>} />
        <Route path="/dashboard" element={
          <PrivateRoute>
            <AppLayout><Dashboard /></AppLayout>
          </PrivateRoute>
        } />
        <Route path="/jobs" element={
          <PrivateRoute>
            <AppLayout><Jobs /></AppLayout>
          </PrivateRoute>
        } />
        <Route path="/applications" element={
          <PrivateRoute>
            <AppLayout><Applications /></AppLayout>
          </PrivateRoute>
        } />
        <Route path="/resume" element={
          <PrivateRoute>
            <AppLayout><ResumeBuilder /></AppLayout>
          </PrivateRoute>
        } />
        <Route path="/interview" element={
          <PrivateRoute>
            <AppLayout><Interview /></AppLayout>
          </PrivateRoute>
        } />
        <Route path="/" element={<Navigate to={user ? "/dashboard" : "/login"} />} />
      </Routes>
    </div>
  );
}

export default App;
