import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { applicationsAPI, resumeAPI, interviewAPI } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { parseError } from '../services/utils';

const Applications = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [applications, setApplications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');
  const [showModal, setShowModal] = useState(false);
  const [editingApp, setEditingApp] = useState(null);
  const [formData, setFormData] = useState({
    job_title: '',
    company: '',
    location: '',
    job_url: '',
    job_description: '',
    status: 'applied',
    notes: ''
  });
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState({ type: '', text: '' });

  // Resume AI states
  const [showAnalyzeModal, setShowAnalyzeModal] = useState(false);
  const [showTailorModal, setShowTailorModal] = useState(false);
  const [selectedApp, setSelectedApp] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState(null);

  // Interview states
  const [showInterviewModal, setShowInterviewModal] = useState(false);
  const [startingInterview, setStartingInterview] = useState(false);

  useEffect(() => {
    loadApplications();
  }, []);

  const loadApplications = async () => {
    try {
      const response = await applicationsAPI.getAll();
      setApplications(response.data);
    } catch (error) {
      console.error('Error loading applications:', error);
    } finally {
      setLoading(false);
    }
  };

  const filteredApplications = filter === 'all'
    ? applications
    : applications.filter(app => app.status === filter);

  const openAddModal = () => {
    setEditingApp(null);
    setFormData({
      job_title: '',
      company: '',
      location: '',
      job_url: '',
      job_description: '',
      status: 'applied',
      notes: ''
    });
    setShowModal(true);
  };

  const openEditModal = (app) => {
    setEditingApp(app);
    setFormData({
      job_title: app.job_title,
      company: app.company,
      location: app.location || '',
      job_url: app.job_url || '',
      job_description: app.job_description || '',
      status: app.status,
      notes: app.notes || ''
    });
    setShowModal(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);

    try {
      if (editingApp) {
        await applicationsAPI.update(editingApp.id, formData);
        setMessage({ type: 'success', text: 'Application updated successfully!' });
      } else {
        await applicationsAPI.create(formData);
        setMessage({ type: 'success', text: 'Application added successfully!' });
      }
      setShowModal(false);
      loadApplications();
    } catch (error) {
      setMessage({ type: 'error', text: parseError(error) || 'Failed to save application.' });
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Are you sure you want to delete this application?')) return;

    try {
      await applicationsAPI.delete(id);
      setMessage({ type: 'success', text: 'Application deleted successfully!' });
      loadApplications();
    } catch (error) {
      setMessage({ type: 'error', text: 'Failed to delete application.' });
    }
  };

  const handleStatusChange = async (app, newStatus) => {
    try {
      await applicationsAPI.update(app.id, { ...app, status: newStatus });
      loadApplications();
    } catch (error) {
      setMessage({ type: 'error', text: 'Failed to update status.' });
    }
  };

  const openAnalyzeModal = (app) => {
    if (!app.job_description) {
      setMessage({ type: 'error', text: 'This application has no job description. Edit it to add one.' });
      return;
    }
    setSelectedApp(app);
    setAnalysisResult(null);
    setShowAnalyzeModal(true);
  };

  const openTailorModal = (app) => {
    if (!app.job_description) {
      setMessage({ type: 'error', text: 'This application has no job description. Edit it to add one.' });
      return;
    }
    setSelectedApp(app);
    setShowTailorModal(true);
  };

  const analyzeResume = async () => {
    if (!selectedApp) return;

    setAnalyzing(true);
    try {
      const response = await resumeAPI.analyze(user.id, selectedApp.job_description);
      setAnalysisResult(response.data);
    } catch (error) {
      setMessage({ type: 'error', text: parseError(error) || 'Failed to analyze resume.' });
    } finally {
      setAnalyzing(false);
    }
  };

  const tailorResume = async () => {
    if (!selectedApp) return;

    setAnalyzing(true);
    try {
      const response = await resumeAPI.tailor(user.id, {
        job_description: selectedApp.job_description,
        job_title: selectedApp.job_title
      });
      const blob = new Blob([response.data], { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${user.name}_Resume_${selectedApp.company}.docx`;
      a.click();
      window.URL.revokeObjectURL(url);
      setShowTailorModal(false);
      setMessage({ type: 'success', text: 'Tailored resume downloaded!' });
    } catch (error) {
      setMessage({ type: 'error', text: parseError(error) || 'Failed to generate tailored resume.' });
    } finally {
      setAnalyzing(false);
    }
  };

  const openInterviewModal = (app) => {
    if (!app.job_description) {
      setMessage({ type: 'error', text: 'This application has no job description. Edit it to add one.' });
      return;
    }
    setSelectedApp(app);
    setShowInterviewModal(true);
  };

  const startInterview = async () => {
    if (!selectedApp) return;

    setStartingInterview(true);
    try {
      const response = await interviewAPI.start({
        job_title: selectedApp.job_title,
        job_description: selectedApp.job_description,
        num_questions: 5
      });
      setShowInterviewModal(false);
      // Navigate to interview page with the session
      navigate('/interview', { state: { sessionId: response.data.session_id } });
    } catch (error) {
      setMessage({ type: 'error', text: parseError(error) || 'Failed to start interview session.' });
    } finally {
      setStartingInterview(false);
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
        <h1>Applications</h1>
        <button className="btn btn-primary" onClick={openAddModal}>
          Add Application
        </button>
      </div>

      {message.text && (
        <div className={`alert alert-${message.type}`}>
          {message.text}
          <button onClick={() => setMessage({ type: '', text: '' })} style={{ float: 'right', background: 'none', border: 'none', cursor: 'pointer' }}>×</button>
        </div>
      )}

      {/* Filter Tabs */}
      <div className="tabs">
        {['all', 'saved', 'applied', 'interview', 'offered', 'rejected'].map((status) => (
          <button
            key={status}
            className={`tab ${filter === status ? 'active' : ''}`}
            onClick={() => setFilter(status)}
          >
            {status.charAt(0).toUpperCase() + status.slice(1)}
            {status !== 'all' && (
              <span style={{ marginLeft: '8px', opacity: 0.7 }}>
                ({applications.filter(a => a.status === status).length})
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Applications Table */}
      {filteredApplications.length === 0 ? (
        <div className="empty-state">
          <h3>No applications found</h3>
          <p>{filter === 'all' ? 'Start tracking your job applications' : `No ${filter} applications`}</p>
          <button className="btn btn-primary" onClick={openAddModal} style={{ marginTop: '20px' }}>
            Add Application
          </button>
        </div>
      ) : (
        <div className="card">
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Job Title</th>
                  <th>Company</th>
                  <th>Location</th>
                  <th>Status</th>
                  <th>Applied</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredApplications.map((app) => (
                  <tr key={app.id}>
                    <td>
                      <strong>{app.job_title}</strong>
                    </td>
                    <td>{app.company}</td>
                    <td>{app.location || '-'}</td>
                    <td>
                      <select
                        className={`badge badge-${app.status}`}
                        value={app.status}
                        onChange={(e) => handleStatusChange(app, e.target.value)}
                        style={{ border: 'none', cursor: 'pointer', padding: '4px 8px' }}
                      >
                        <option value="saved">Saved</option>
                        <option value="applied">Applied</option>
                        <option value="interview">Interview</option>
                        <option value="offered">Offered</option>
                        <option value="rejected">Rejected</option>
                      </select>
                    </td>
                    <td>{new Date(app.applied_date).toLocaleDateString()}</td>
                    <td>
                      <div className="action-buttons">
                        <button className="action-btn" onClick={() => openEditModal(app)} title="Edit">
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                          </svg>
                        </button>
                        <button
                          className="action-btn"
                          onClick={() => openAnalyzeModal(app)}
                          title={app.job_description ? 'Analyze resume match' : 'Add job description first'}
                        >
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>
                          </svg>
                        </button>
                        <button
                          className="action-btn action-btn-success"
                          onClick={() => openTailorModal(app)}
                          title={app.job_description ? 'Generate tailored resume' : 'Add job description first'}
                        >
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                            <polyline points="14 2 14 8 20 8"></polyline>
                          </svg>
                        </button>
                        <button
                          className="action-btn action-btn-primary"
                          onClick={() => openInterviewModal(app)}
                          title={app.job_description ? 'Practice interview' : 'Add job description first'}
                        >
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                          </svg>
                        </button>
                        {app.job_url && (
                          <a href={app.job_url} target="_blank" rel="noopener noreferrer" className="action-btn" title="View job posting">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                              <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
                              <polyline points="15 3 21 3 21 9"></polyline>
                              <line x1="10" y1="14" x2="21" y2="3"></line>
                            </svg>
                          </a>
                        )}
                        <button className="action-btn action-btn-danger" onClick={() => handleDelete(app.id)} title="Delete">
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <polyline points="3 6 5 6 21 6"></polyline>
                            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                          </svg>
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Add/Edit Modal */}
      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>{editingApp ? 'Edit Application' : 'Add Application'}</h2>
              <button className="modal-close" onClick={() => setShowModal(false)}>×</button>
            </div>
            <form onSubmit={handleSubmit}>
              <div className="modal-body">
                <div className="grid grid-2">
                  <div className="form-group">
                    <label className="form-label">Job Title *</label>
                    <input
                      type="text"
                      className="form-control"
                      value={formData.job_title}
                      onChange={(e) => setFormData({ ...formData, job_title: e.target.value })}
                      required
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Company *</label>
                    <input
                      type="text"
                      className="form-control"
                      value={formData.company}
                      onChange={(e) => setFormData({ ...formData, company: e.target.value })}
                      required
                    />
                  </div>
                </div>

                <div className="grid grid-2">
                  <div className="form-group">
                    <label className="form-label">Location</label>
                    <input
                      type="text"
                      className="form-control"
                      value={formData.location}
                      onChange={(e) => setFormData({ ...formData, location: e.target.value })}
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Status</label>
                    <select
                      className="form-control"
                      value={formData.status}
                      onChange={(e) => setFormData({ ...formData, status: e.target.value })}
                    >
                      <option value="saved">Saved</option>
                      <option value="applied">Applied</option>
                      <option value="interview">Interview</option>
                      <option value="offered">Offered</option>
                      <option value="rejected">Rejected</option>
                    </select>
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label">Job URL</label>
                  <input
                    type="url"
                    className="form-control"
                    value={formData.job_url}
                    onChange={(e) => setFormData({ ...formData, job_url: e.target.value })}
                    placeholder="https://..."
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Job Description</label>
                  <textarea
                    className="form-control"
                    value={formData.job_description}
                    onChange={(e) => setFormData({ ...formData, job_description: e.target.value })}
                    rows={4}
                    placeholder="Paste the job description here for resume analysis and tailoring..."
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Notes</label>
                  <textarea
                    className="form-control"
                    value={formData.notes}
                    onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                    rows={2}
                  />
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setShowModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={saving}>
                  {saving ? 'Saving...' : editingApp ? 'Update' : 'Add Application'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Analyze Modal */}
      {showAnalyzeModal && selectedApp && (
        <div className="modal-overlay" onClick={() => setShowAnalyzeModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '700px' }}>
            <div className="modal-header">
              <h2>Analyze Resume Match</h2>
              <button className="modal-close" onClick={() => setShowAnalyzeModal(false)}>×</button>
            </div>
            <div className="modal-body">
              <div style={{ marginBottom: '20px', padding: '16px', background: '#f9fafb', borderRadius: '8px' }}>
                <h3 style={{ marginBottom: '4px' }}>{selectedApp.job_title}</h3>
                <p style={{ color: '#4f46e5' }}>{selectedApp.company}</p>
              </div>

              {!analysisResult ? (
                <div style={{ textAlign: 'center' }}>
                  <p style={{ marginBottom: '20px', color: '#6b7280' }}>
                    Analyze how well your resume matches this job's requirements.
                  </p>
                  <button className="btn btn-primary" onClick={analyzeResume} disabled={analyzing}>
                    {analyzing ? 'Analyzing...' : 'Analyze Match'}
                  </button>
                </div>
              ) : (
                <div>
                  <div style={{ textAlign: 'center', marginBottom: '24px' }}>
                    <div style={{ fontSize: '3rem', fontWeight: '700', color: analysisResult.match_score >= 70 ? '#059669' : analysisResult.match_score >= 50 ? '#d97706' : '#dc2626' }}>
                      {analysisResult.match_score}%
                    </div>
                    <p style={{ color: '#6b7280' }}>Match Score</p>
                  </div>

                  <div className="feedback-section">
                    <h4>Strengths</h4>
                    <ul>
                      {analysisResult.strengths?.map((s, i) => <li key={i}>{s}</li>)}
                    </ul>
                  </div>

                  <div className="feedback-section">
                    <h4>Gaps</h4>
                    <ul>
                      {analysisResult.gaps?.map((g, i) => <li key={i}>{g}</li>)}
                    </ul>
                  </div>

                  <div className="feedback-section">
                    <h4>Suggestions</h4>
                    <ul>
                      {analysisResult.suggestions?.map((s, i) => <li key={i}>{s}</li>)}
                    </ul>
                  </div>

                  {analysisResult.keywords_to_add?.length > 0 && (
                    <div className="feedback-section">
                      <h4>Keywords to Add</h4>
                      <div className="skills-container">
                        {analysisResult.keywords_to_add.map((k, i) => (
                          <span key={i} className="skill-tag">{k}</span>
                        ))}
                      </div>
                    </div>
                  )}

                  <div style={{ marginTop: '20px', display: 'flex', gap: '12px' }}>
                    <button className="btn btn-outline" onClick={() => setAnalysisResult(null)}>
                      Analyze Again
                    </button>
                    <button className="btn btn-success" onClick={() => { setShowAnalyzeModal(false); openTailorModal(selectedApp); }}>
                      Generate Tailored Resume
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Tailor Modal */}
      {showTailorModal && selectedApp && (
        <div className="modal-overlay" onClick={() => setShowTailorModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Generate Tailored Resume</h2>
              <button className="modal-close" onClick={() => setShowTailorModal(false)}>×</button>
            </div>
            <div className="modal-body">
              <div style={{ marginBottom: '20px', padding: '16px', background: '#f9fafb', borderRadius: '8px' }}>
                <h3 style={{ marginBottom: '4px' }}>{selectedApp.job_title}</h3>
                <p style={{ color: '#4f46e5' }}>{selectedApp.company}</p>
              </div>

              <p style={{ marginBottom: '20px', color: '#6b7280' }}>
                This will create a new resume with your existing content rephrased to better match the job description for this position.
              </p>
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setShowTailorModal(false)}>Cancel</button>
              <button className="btn btn-primary" onClick={tailorResume} disabled={analyzing}>
                {analyzing ? 'Generating...' : 'Generate & Download'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Interview Modal */}
      {showInterviewModal && selectedApp && (
        <div className="modal-overlay" onClick={() => setShowInterviewModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Practice Interview</h2>
              <button className="modal-close" onClick={() => setShowInterviewModal(false)}>×</button>
            </div>
            <div className="modal-body">
              <div style={{ marginBottom: '20px', padding: '16px', background: '#f9fafb', borderRadius: '8px' }}>
                <h3 style={{ marginBottom: '4px' }}>{selectedApp.job_title}</h3>
                <p style={{ color: '#4f46e5' }}>{selectedApp.company}</p>
              </div>

              <p style={{ marginBottom: '20px', color: '#6b7280' }}>
                Start a practice interview session with AI-generated questions based on this job's requirements. You'll get 5 questions to practice with immediate feedback.
              </p>
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setShowInterviewModal(false)}>Cancel</button>
              <button className="btn btn-primary" onClick={startInterview} disabled={startingInterview}>
                {startingInterview ? 'Starting...' : 'Start Interview'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Applications;
