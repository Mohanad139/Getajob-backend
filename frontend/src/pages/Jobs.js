import React, { useState, useEffect } from 'react';
import { jobsAPI, applicationsAPI } from '../services/api';
import { parseError } from '../services/utils';

const Jobs = () => {
  // Load persisted state from localStorage
  const getPersistedState = (key, defaultValue) => {
    try {
      const saved = localStorage.getItem(`jobs_${key}`);
      return saved ? JSON.parse(saved) : defaultValue;
    } catch {
      return defaultValue;
    }
  };

  const [jobs, setJobs] = useState(() => getPersistedState('searchResults', []));
  const [savedJobs, setSavedJobs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [loadingSaved, setLoadingSaved] = useState(true);
  const [searchQuery, setSearchQuery] = useState(() => getPersistedState('searchQuery', ''));
  const [searched, setSearched] = useState(() => getPersistedState('searched', false));
  const [viewMode, setViewMode] = useState(() => getPersistedState('viewMode', 'saved'));
  const [selectedJob, setSelectedJob] = useState(null);
  const [showApplyModal, setShowApplyModal] = useState(false);
  const [applyStatus, setApplyStatus] = useState('applied');
  const [applyNotes, setApplyNotes] = useState('');
  const [applying, setApplying] = useState(false);
  const [message, setMessage] = useState({ type: '', text: '' });

  // Persist state to localStorage when it changes
  useEffect(() => {
    localStorage.setItem('jobs_searchResults', JSON.stringify(jobs));
  }, [jobs]);

  useEffect(() => {
    localStorage.setItem('jobs_searchQuery', JSON.stringify(searchQuery));
  }, [searchQuery]);

  useEffect(() => {
    localStorage.setItem('jobs_searched', JSON.stringify(searched));
  }, [searched]);

  useEffect(() => {
    localStorage.setItem('jobs_viewMode', JSON.stringify(viewMode));
  }, [viewMode]);

  useEffect(() => {
    loadSavedJobs();
  }, []);

  const loadSavedJobs = async () => {
    try {
      const response = await jobsAPI.getAll();
      setSavedJobs(response.data || []);
    } catch (error) {
      console.error('Error loading saved jobs:', error);
    } finally {
      setLoadingSaved(false);
    }
  };

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;

    setLoading(true);
    setSearched(true);
    setViewMode('search');
    try {
      const response = await jobsAPI.search({
        query: searchQuery
      });
      setJobs(response.data.jobs || []);
    } catch (error) {
      console.error('Search error:', error);
      setMessage({ type: 'error', text: 'Failed to search jobs. Please try again.' });
    } finally {
      setLoading(false);
    }
  };

  const handleSaveJob = async (job, index) => {
    try {
      await jobsAPI.save({
        title: job.title,
        company: job.company,
        location: job.location || null,
        salary: job.salary || null,
        description: job.description || null,
        url: job.url || null,
        job_type: job.job_type || null,
        posted_date: job.posted_date || null
      });
      // Remove from search results
      setJobs(prev => prev.filter((_, i) => i !== index));
      // Reload saved jobs
      loadSavedJobs();
      setMessage({ type: 'success', text: 'Job saved successfully!' });
    } catch (error) {
      setMessage({ type: 'error', text: parseError(error) || 'Failed to save job.' });
    }
  };

  const handleSkipJob = (index) => {
    // Just remove from search results (don't save to DB)
    setJobs(prev => prev.filter((_, i) => i !== index));
  };

  const handleDeleteSavedJob = async (jobId) => {
    if (!window.confirm('Are you sure you want to remove this saved job?')) return;

    try {
      await jobsAPI.delete(jobId);
      setSavedJobs(prev => prev.filter(job => job.id !== jobId));
      setMessage({ type: 'success', text: 'Job removed successfully!' });
    } catch (error) {
      setMessage({ type: 'error', text: parseError(error) || 'Failed to remove job.' });
    }
  };

  const handleApply = (job) => {
    setSelectedJob(job);
    setShowApplyModal(true);
    setApplyStatus('applied');
    setApplyNotes('');
  };

  const submitApplication = async () => {
    if (!selectedJob) return;

    setApplying(true);
    try {
      await applicationsAPI.create({
        job_title: selectedJob.title,
        company: selectedJob.company,
        location: selectedJob.location || '',
        job_url: selectedJob.url || '',
        job_description: selectedJob.description || '',
        status: applyStatus,
        notes: applyNotes
      });
      setMessage({ type: 'success', text: 'Application tracked successfully!' });
      setShowApplyModal(false);
      setSelectedJob(null);
    } catch (error) {
      setMessage({ type: 'error', text: parseError(error) || 'Failed to save application.' });
    } finally {
      setApplying(false);
    }
  };

  return (
    <div className="container">
      <div className="page-header">
        <h1>Search Jobs</h1>
      </div>

      {message.text && (
        <div className={`alert alert-${message.type}`}>
          {message.text}
          <button onClick={() => setMessage({ type: '', text: '' })} style={{ float: 'right', background: 'none', border: 'none', cursor: 'pointer' }}>×</button>
        </div>
      )}

      {/* Search Form */}
      <div className="card">
        <form onSubmit={handleSearch}>
          <div className="filters">
            <input
              type="text"
              className="form-control"
              placeholder="e.g. Software Engineer in Canada, Data Analyst in Toronto"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{ flex: 1, minWidth: '300px' }}
            />
            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? 'Searching...' : 'Search Jobs'}
            </button>
          </div>
        </form>
      </div>

      {/* View Mode Tabs */}
      <div className="tabs" style={{ marginBottom: '20px' }}>
        <button
          className={`tab ${viewMode === 'saved' ? 'active' : ''}`}
          onClick={() => setViewMode('saved')}
        >
          Saved Jobs
          <span style={{ marginLeft: '8px', opacity: 0.7 }}>({savedJobs.length})</span>
        </button>
        <button
          className={`tab ${viewMode === 'search' ? 'active' : ''}`}
          onClick={() => setViewMode('search')}
        >
          Search Results
          {searched && <span style={{ marginLeft: '8px', opacity: 0.7 }}>({jobs.length})</span>}
        </button>
      </div>

      {/* Results */}
      {loading || loadingSaved ? (
        <div className="loading">
          <div className="spinner"></div>
        </div>
      ) : viewMode === 'search' ? (
        // Search Results View
        searched && jobs.length === 0 ? (
          <div className="empty-state">
            <h3>No jobs found</h3>
            <p>Try a different search like "Python Developer in USA"</p>
          </div>
        ) : !searched ? (
          <div className="empty-state">
            <h3>Search for jobs</h3>
            <p>Try: "Software Engineer in Canada" or "Data Analyst in Toronto"</p>
          </div>
        ) : (
          <div className="grid grid-2">
            {jobs.map((job, index) => (
              <div key={index} className="job-card">
                <div className="job-card-header">
                  <div>
                    <h3>{job.title}</h3>
                    <p className="company">{job.company}</p>
                    <p className="location">{job.location}</p>
                  </div>
                </div>
                {job.salary && (
                  <p style={{ color: '#059669', fontWeight: '500', marginBottom: '12px' }}>
                    {job.salary}
                  </p>
                )}
                {job.description && (
                  <p style={{ color: '#6b7280', fontSize: '0.9rem', marginBottom: '12px' }}>
                    {job.description.substring(0, 150)}...
                  </p>
                )}
                <div className="job-card-actions">
                  <button className="btn btn-primary btn-sm" onClick={() => handleSaveJob(job, index)}>
                    Save
                  </button>
                  <button className="btn btn-danger btn-sm" onClick={() => handleSkipJob(index)}>
                    Skip
                  </button>
                  {job.url && (
                    <a href={job.url} target="_blank" rel="noopener noreferrer" className="btn btn-outline btn-sm">
                      View
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        )
      ) : (
        // Saved Jobs View
        savedJobs.length === 0 ? (
          <div className="empty-state">
            <h3>No saved jobs yet</h3>
            <p>Search for jobs and save the ones you're interested in</p>
          </div>
        ) : (
          <div className="grid grid-2">
            {savedJobs.map((job) => (
              <div key={job.id} className="job-card">
                <div className="job-card-header">
                  <div>
                    <h3>{job.title}</h3>
                    <p className="company">{job.company}</p>
                    <p className="location">{job.location}</p>
                  </div>
                </div>
                {job.salary && (
                  <p style={{ color: '#059669', fontWeight: '500', marginBottom: '12px' }}>
                    {job.salary}
                  </p>
                )}
                {job.description && (
                  <p style={{ color: '#6b7280', fontSize: '0.9rem', marginBottom: '12px' }}>
                    {job.description.substring(0, 150)}...
                  </p>
                )}
                {job.posted_date && (
                  <p style={{ color: '#9ca3af', fontSize: '0.8rem', marginBottom: '12px' }}>
                    Posted: {new Date(job.posted_date).toLocaleDateString()}
                  </p>
                )}
                <div className="job-card-actions">
                  <button className="btn btn-primary btn-sm" onClick={() => handleApply(job)}>
                    Track Application
                  </button>
                  {job.url && (
                    <a href={job.url} target="_blank" rel="noopener noreferrer" className="btn btn-outline btn-sm">
                      View
                    </a>
                  )}
                  <button className="btn btn-danger btn-sm" onClick={() => handleDeleteSavedJob(job.id)}>
                    Remove
                  </button>
                </div>
              </div>
            ))}
          </div>
        )
      )}

      {/* Apply Modal */}
      {showApplyModal && selectedJob && (
        <div className="modal-overlay" onClick={() => setShowApplyModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Track Application</h2>
              <button className="modal-close" onClick={() => setShowApplyModal(false)}>×</button>
            </div>
            <div className="modal-body">
              <div style={{ marginBottom: '20px', padding: '16px', background: '#f9fafb', borderRadius: '8px' }}>
                <h3 style={{ marginBottom: '4px' }}>{selectedJob.title}</h3>
                <p style={{ color: '#4f46e5' }}>{selectedJob.company}</p>
                <p style={{ color: '#6b7280', fontSize: '0.9rem' }}>{selectedJob.location}</p>
              </div>

              <div className="form-group">
                <label className="form-label">Application Status</label>
                <select
                  className="form-control"
                  value={applyStatus}
                  onChange={(e) => setApplyStatus(e.target.value)}
                >
                  <option value="saved">Saved</option>
                  <option value="applied">Applied</option>
                  <option value="interview">Interview</option>
                  <option value="offered">Offered</option>
                  <option value="rejected">Rejected</option>
                </select>
              </div>

              <div className="form-group">
                <label className="form-label">Notes (optional)</label>
                <textarea
                  className="form-control"
                  value={applyNotes}
                  onChange={(e) => setApplyNotes(e.target.value)}
                  placeholder="Add any notes about this application..."
                  rows={3}
                />
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setShowApplyModal(false)}>
                Cancel
              </button>
              <button className="btn btn-primary" onClick={submitApplication} disabled={applying}>
                {applying ? 'Saving...' : 'Save Application'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Jobs;
