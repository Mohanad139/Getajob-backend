import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const Navbar = () => {
  const { user, logout } = useAuth();
  const location = useLocation();

  const isActive = (path) => location.pathname === path;

  return (
    <nav className="navbar">
      <Link to="/dashboard" className="navbar-brand">
        GetAJob
      </Link>
      <div className="navbar-nav">
        <Link to="/dashboard" className={`nav-link ${isActive('/dashboard') ? 'active' : ''}`}>
          Dashboard
        </Link>
        <Link to="/jobs" className={`nav-link ${isActive('/jobs') ? 'active' : ''}`}>
          Jobs
        </Link>
        <Link to="/applications" className={`nav-link ${isActive('/applications') ? 'active' : ''}`}>
          Applications
        </Link>
        <Link to="/resume" className={`nav-link ${isActive('/resume') ? 'active' : ''}`}>
          Resume
        </Link>
        <Link to="/interview" className={`nav-link ${isActive('/interview') ? 'active' : ''}`}>
          Interview
        </Link>
      </div>
      <div className="nav-user">
        <span>{user?.name}</span>
        <button className="btn btn-sm btn-outline" onClick={logout} style={{ color: 'white', borderColor: 'white' }}>
          Logout
        </button>
      </div>
    </nav>
  );
};

export default Navbar;
