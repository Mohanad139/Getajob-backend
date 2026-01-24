import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { applicationsAPI } from '../services/api';

const Dashboard = () => {
  const [stats, setStats] = useState(null);
  const [recentApplications, setRecentApplications] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadDashboard();
  }, []);

  const loadDashboard = async () => {
    try {
      const [statsRes, appsRes] = await Promise.all([
        applicationsAPI.getDashboardStats(),
        applicationsAPI.getAll()
      ]);
      setStats(statsRes.data);
      setRecentApplications(appsRes.data.slice(0, 5));
    } catch (error) {
      console.error('Error loading dashboard:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="loading">
        <div className="spinner"></div>
      </div>
    );
  }

  return (
    <div className="container">
      <div className="page-header">
        <h1>Dashboard</h1>
        <Link to="/jobs" className="btn btn-primary">
          Search Jobs
        </Link>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-4" style={{ marginBottom: '30px' }}>
        <div className="stat-card primary">
          <h3>Total Applications</h3>
          <div className="stat-value">{stats?.total || 0}</div>
        </div>
        <div className="stat-card">
          <h3>Interviews</h3>
          <div className="stat-value">{stats?.by_status?.interview || 0}</div>
        </div>
        <div className="stat-card">
          <h3>Offers</h3>
          <div className="stat-value">{stats?.by_status?.offered || 0}</div>
        </div>
        <div className="stat-card">
          <h3>Practice Sessions</h3>
          <div className="stat-value">{stats?.interview_sessions || 0}</div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="card">
        <div className="card-header">
          <h2 className="card-title">Quick Actions</h2>
        </div>
        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
          <Link to="/jobs" className="btn btn-primary">Search Jobs</Link>
          <Link to="/resume" className="btn btn-secondary">Build Resume</Link>
          <Link to="/interview" className="btn btn-success">Practice Interview</Link>
          <Link to="/applications" className="btn btn-outline">View Applications</Link>
        </div>
      </div>

      {/* Recent Applications */}
      <div className="card">
        <div className="card-header">
          <h2 className="card-title">Recent Applications</h2>
          <Link to="/applications" className="btn btn-sm btn-outline">View All</Link>
        </div>

        {recentApplications.length === 0 ? (
          <div className="empty-state">
            <h3>No applications yet</h3>
            <p>Start applying to jobs to track them here</p>
            <Link to="/jobs" className="btn btn-primary" style={{ marginTop: '20px' }}>
              Search Jobs
            </Link>
          </div>
        ) : (
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Job Title</th>
                  <th>Company</th>
                  <th>Status</th>
                  <th>Applied</th>
                </tr>
              </thead>
              <tbody>
                {recentApplications.map((app) => (
                  <tr key={app.id}>
                    <td>{app.job_title}</td>
                    <td>{app.company}</td>
                    <td>
                      <span className={`badge badge-${app.status}`}>
                        {app.status}
                      </span>
                    </td>
                    <td>{new Date(app.applied_date).toLocaleDateString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Status Breakdown */}
      {stats && (
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">Application Status Breakdown</h2>
          </div>
          <div className="grid grid-2">
            {Object.entries(stats.by_status || {}).map(([status, count]) => (
              <div key={status} style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '12px 0' }}>
                <span className={`badge badge-${status}`} style={{ minWidth: '100px', textAlign: 'center' }}>
                  {status}
                </span>
                <div className="progress-bar" style={{ flex: 1 }}>
                  <div
                    className="progress"
                    style={{ width: `${(count / stats.total) * 100}%` }}
                  ></div>
                </div>
                <span style={{ fontWeight: '600', minWidth: '30px' }}>{count}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default Dashboard;
