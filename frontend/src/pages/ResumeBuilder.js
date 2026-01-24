import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import {
  workExperienceAPI,
  educationAPI,
  skillsAPI,
  projectsAPI,
  resumeAPI,
  authAPI
} from '../services/api';
import { parseError } from '../services/utils';

const ResumeBuilder = () => {
  const { user, loadUser } = useAuth();
  const [activeTab, setActiveTab] = useState('profile');
  const [workExperiences, setWorkExperiences] = useState([]);
  const [education, setEducation] = useState([]);
  const [skills, setSkills] = useState([]);
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState({ type: '', text: '' });

  // Modal states
  const [showModal, setShowModal] = useState(false);
  const [modalType, setModalType] = useState('');
  const [editingItem, setEditingItem] = useState(null);
  const [formData, setFormData] = useState({});
  const [saving, setSaving] = useState(false);

  // AI Modal states
  const [showAnalyzeModal, setShowAnalyzeModal] = useState(false);
  const [showTailorModal, setShowTailorModal] = useState(false);
  const [jobDescription, setJobDescription] = useState('');
  const [jobTitle, setJobTitle] = useState('');
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState(null);

  // Profile states
  const [profileData, setProfileData] = useState({
    name: '',
    phone: '',
    location: '',
    headline: '',
    summary: ''
  });
  const [savingProfile, setSavingProfile] = useState(false);

  useEffect(() => {
    loadAllData();
  }, []);

  useEffect(() => {
    if (user) {
      setProfileData({
        name: user.name || '',
        phone: user.phone || '',
        location: user.location || '',
        headline: user.headline || '',
        summary: user.summary || ''
      });
    }
  }, [user]);

  const loadAllData = async () => {
    try {
      const [workRes, eduRes, skillsRes, projectsRes] = await Promise.all([
        workExperienceAPI.getAll(),
        educationAPI.getAll(),
        skillsAPI.getAll(),
        projectsAPI.getAll()
      ]);
      setWorkExperiences(workRes.data);
      setEducation(eduRes.data);
      setSkills(skillsRes.data);
      setProjects(projectsRes.data);
    } catch (error) {
      console.error('Error loading resume data:', error);
    } finally {
      setLoading(false);
    }
  };

  const openModal = (type, item = null) => {
    setModalType(type);
    setEditingItem(item);
    setShowModal(true);

    switch (type) {
      case 'experience':
        setFormData(item || {
          company: '',
          title: '',
          location: '',
          start_date: '',
          end_date: '',
          is_current: false,
          responsibilities: ''
        });
        break;
      case 'education':
        setFormData(item || {
          school: '',
          degree: '',
          field_of_study: '',
          start_date: '',
          end_date: '',
          gpa: ''
        });
        break;
      case 'skill':
        setFormData(item || {
          skill_name: '',
          proficiency: 'intermediate'
        });
        break;
      case 'project':
        setFormData(item || {
          title: '',
          description: '',
          technologies: '',
          url: '',
          start_date: '',
          end_date: ''
        });
        break;
      default:
        setFormData({});
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);

    try {
      let api;
      let loadFn;

      switch (modalType) {
        case 'experience':
          api = workExperienceAPI;
          loadFn = () => workExperienceAPI.getAll().then(res => setWorkExperiences(res.data));
          break;
        case 'education':
          api = educationAPI;
          loadFn = () => educationAPI.getAll().then(res => setEducation(res.data));
          break;
        case 'skill':
          api = skillsAPI;
          loadFn = () => skillsAPI.getAll().then(res => setSkills(res.data));
          break;
        case 'project':
          api = projectsAPI;
          loadFn = () => projectsAPI.getAll().then(res => setProjects(res.data));
          break;
        default:
          return;
      }

      if (editingItem) {
        await api.update(editingItem.id, formData);
        setMessage({ type: 'success', text: 'Updated successfully!' });
      } else {
        await api.create(formData);
        setMessage({ type: 'success', text: 'Added successfully!' });
      }

      await loadFn();
      setShowModal(false);
    } catch (error) {
      setMessage({ type: 'error', text: parseError(error) || 'Failed to save.' });
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (type, id) => {
    if (!window.confirm('Are you sure you want to delete this item?')) return;

    try {
      let api;
      let loadFn;

      switch (type) {
        case 'experience':
          api = workExperienceAPI;
          loadFn = () => workExperienceAPI.getAll().then(res => setWorkExperiences(res.data));
          break;
        case 'education':
          api = educationAPI;
          loadFn = () => educationAPI.getAll().then(res => setEducation(res.data));
          break;
        case 'skill':
          api = skillsAPI;
          loadFn = () => skillsAPI.getAll().then(res => setSkills(res.data));
          break;
        case 'project':
          api = projectsAPI;
          loadFn = () => projectsAPI.getAll().then(res => setProjects(res.data));
          break;
        default:
          return;
      }

      await api.delete(id);
      await loadFn();
      setMessage({ type: 'success', text: 'Deleted successfully!' });
    } catch (error) {
      setMessage({ type: 'error', text: 'Failed to delete.' });
    }
  };

  const downloadResume = async () => {
    try {
      const response = await resumeAPI.download(user.id);
      const blob = new Blob([response.data], { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${user.name}_Resume.docx`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      setMessage({ type: 'error', text: 'Failed to download resume.' });
    }
  };

  const analyzeResume = async () => {
    if (!jobDescription.trim()) return;

    setAnalyzing(true);
    try {
      const response = await resumeAPI.analyze(user.id, jobDescription);
      setAnalysisResult(response.data);
    } catch (error) {
      setMessage({ type: 'error', text: 'Failed to analyze resume.' });
    } finally {
      setAnalyzing(false);
    }
  };

  const tailorResume = async () => {
    if (!jobDescription.trim() || !jobTitle.trim()) return;

    setAnalyzing(true);
    try {
      const response = await resumeAPI.tailor(user.id, {
        job_description: jobDescription,
        job_title: jobTitle
      });
      const blob = new Blob([response.data], { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${user.name}_Tailored_Resume.docx`;
      a.click();
      window.URL.revokeObjectURL(url);
      setShowTailorModal(false);
      setMessage({ type: 'success', text: 'Tailored resume downloaded!' });
    } catch (error) {
      setMessage({ type: 'error', text: 'Failed to generate tailored resume.' });
    } finally {
      setAnalyzing(false);
    }
  };

  const saveProfile = async (e) => {
    e.preventDefault();
    setSavingProfile(true);
    try {
      await authAPI.updateProfile(profileData);
      if (loadUser) {
        await loadUser();
      }
      setMessage({ type: 'success', text: 'Profile updated successfully!' });
    } catch (error) {
      setMessage({ type: 'error', text: parseError(error) || 'Failed to update profile.' });
    } finally {
      setSavingProfile(false);
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
        <h1>Resume Builder</h1>
        <div style={{ display: 'flex', gap: '12px' }}>
          <button className="btn btn-outline" onClick={() => { setShowAnalyzeModal(true); setAnalysisResult(null); setJobDescription(''); }}>
            Analyze Match
          </button>
          <button className="btn btn-success" onClick={() => { setShowTailorModal(true); setJobDescription(''); setJobTitle(''); }}>
            Tailor Resume
          </button>
          <button className="btn btn-primary" onClick={downloadResume}>
            Download Resume
          </button>
        </div>
      </div>

      {message.text && (
        <div className={`alert alert-${message.type}`}>
          {message.text}
          <button onClick={() => setMessage({ type: '', text: '' })} style={{ float: 'right', background: 'none', border: 'none', cursor: 'pointer' }}>×</button>
        </div>
      )}

      {/* Tabs */}
      <div className="tabs">
        {[
          { key: 'profile', label: 'Profile' },
          { key: 'experience', label: 'Work Experience' },
          { key: 'education', label: 'Education' },
          { key: 'skills', label: 'Skills' },
          { key: 'projects', label: 'Projects' }
        ].map(tab => (
          <button
            key={tab.key}
            className={`tab ${activeTab === tab.key ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Profile */}
      {activeTab === 'profile' && (
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">Personal Information</h2>
          </div>
          <form onSubmit={saveProfile}>
            <div className="form-group">
              <label className="form-label">Full Name *</label>
              <input
                type="text"
                className="form-control"
                value={profileData.name}
                onChange={(e) => setProfileData({ ...profileData, name: e.target.value })}
                placeholder="Your full name"
                required
              />
            </div>

            <div className="form-group">
              <label className="form-label">Professional Title / Headline</label>
              <input
                type="text"
                className="form-control"
                value={profileData.headline}
                onChange={(e) => setProfileData({ ...profileData, headline: e.target.value })}
                placeholder="e.g., Software Engineer, Data Analyst, Marketing Manager"
              />
              <small style={{ color: '#6b7280', marginTop: '4px', display: 'block' }}>
                This appears below your name on the resume
              </small>
            </div>

            <div className="grid grid-2">
              <div className="form-group">
                <label className="form-label">Phone</label>
                <input
                  type="tel"
                  className="form-control"
                  value={profileData.phone}
                  onChange={(e) => setProfileData({ ...profileData, phone: e.target.value })}
                  placeholder="+1 (555) 123-4567"
                />
              </div>
              <div className="form-group">
                <label className="form-label">Location</label>
                <input
                  type="text"
                  className="form-control"
                  value={profileData.location}
                  onChange={(e) => setProfileData({ ...profileData, location: e.target.value })}
                  placeholder="City, Country"
                />
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">About Me / Professional Summary</label>
              <textarea
                className="form-control"
                value={profileData.summary}
                onChange={(e) => setProfileData({ ...profileData, summary: e.target.value })}
                rows={5}
                placeholder="Write a brief professional summary about yourself, your experience, and what you're looking for..."
              />
              <small style={{ color: '#6b7280', marginTop: '4px', display: 'block' }}>
                This appears in the "About Me" section of your resume
              </small>
            </div>

            <button type="submit" className="btn btn-primary" disabled={savingProfile}>
              {savingProfile ? 'Saving...' : 'Save Profile'}
            </button>
          </form>
        </div>
      )}

      {/* Work Experience */}
      {activeTab === 'experience' && (
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">Work Experience</h2>
            <button className="btn btn-primary btn-sm" onClick={() => openModal('experience')}>
              Add Experience
            </button>
          </div>
          {workExperiences.length === 0 ? (
            <div className="empty-state">
              <p>No work experience added yet</p>
            </div>
          ) : (
            workExperiences.map(exp => (
              <div key={exp.id} style={{ padding: '16px', borderBottom: '1px solid #e5e7eb' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div>
                    <h3 style={{ marginBottom: '4px' }}>{exp.title}</h3>
                    <p style={{ color: '#4f46e5', fontWeight: '500' }}>{exp.company}</p>
                    <p style={{ color: '#6b7280', fontSize: '0.9rem' }}>
                      {exp.location} | {exp.start_date} - {exp.is_current ? 'Present' : exp.end_date}
                    </p>
                    {exp.responsibilities && (
                      <p style={{ marginTop: '8px', whiteSpace: 'pre-line' }}>{exp.responsibilities}</p>
                    )}
                  </div>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <button className="btn btn-sm btn-outline" onClick={() => openModal('experience', exp)}>Edit</button>
                    <button className="btn btn-sm btn-danger" onClick={() => handleDelete('experience', exp.id)}>Delete</button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Education */}
      {activeTab === 'education' && (
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">Education</h2>
            <button className="btn btn-primary btn-sm" onClick={() => openModal('education')}>
              Add Education
            </button>
          </div>
          {education.length === 0 ? (
            <div className="empty-state">
              <p>No education added yet</p>
            </div>
          ) : (
            education.map(edu => (
              <div key={edu.id} style={{ padding: '16px', borderBottom: '1px solid #e5e7eb' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div>
                    <h3 style={{ marginBottom: '4px' }}>{edu.degree} {edu.field_of_study && `in ${edu.field_of_study}`}</h3>
                    <p style={{ color: '#4f46e5', fontWeight: '500' }}>{edu.school}</p>
                    <p style={{ color: '#6b7280', fontSize: '0.9rem' }}>
                      {edu.start_date} - {edu.end_date} {edu.gpa && `| GPA: ${edu.gpa}`}
                    </p>
                  </div>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <button className="btn btn-sm btn-outline" onClick={() => openModal('education', edu)}>Edit</button>
                    <button className="btn btn-sm btn-danger" onClick={() => handleDelete('education', edu.id)}>Delete</button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Skills */}
      {activeTab === 'skills' && (
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">Skills</h2>
            <button className="btn btn-primary btn-sm" onClick={() => openModal('skill')}>
              Add Skill
            </button>
          </div>
          {skills.length === 0 ? (
            <div className="empty-state">
              <p>No skills added yet</p>
            </div>
          ) : (
            <div className="skills-container">
              {skills.map(skill => (
                <div key={skill.id} className="skill-tag removable">
                  {skill.skill_name}
                  <span style={{ opacity: 0.7, fontSize: '0.75rem' }}>({skill.proficiency})</span>
                  <button onClick={() => openModal('skill', skill)} title="Edit">✎</button>
                  <button onClick={() => handleDelete('skill', skill.id)} title="Delete">×</button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Projects */}
      {activeTab === 'projects' && (
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">Projects</h2>
            <button className="btn btn-primary btn-sm" onClick={() => openModal('project')}>
              Add Project
            </button>
          </div>
          {projects.length === 0 ? (
            <div className="empty-state">
              <p>No projects added yet</p>
            </div>
          ) : (
            projects.map(proj => (
              <div key={proj.id} style={{ padding: '16px', borderBottom: '1px solid #e5e7eb' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div>
                    <h3 style={{ marginBottom: '4px' }}>{proj.title}</h3>
                    {proj.technologies && (
                      <p style={{ color: '#4f46e5', fontSize: '0.9rem' }}>Tech: {proj.technologies}</p>
                    )}
                    {proj.description && (
                      <p style={{ marginTop: '8px', whiteSpace: 'pre-line' }}>{proj.description}</p>
                    )}
                    {proj.url && (
                      <a href={proj.url} target="_blank" rel="noopener noreferrer" style={{ color: '#4f46e5', fontSize: '0.9rem' }}>
                        View Project
                      </a>
                    )}
                  </div>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <button className="btn btn-sm btn-outline" onClick={() => openModal('project', proj)}>Edit</button>
                    <button className="btn btn-sm btn-danger" onClick={() => handleDelete('project', proj.id)}>Delete</button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Add/Edit Modal */}
      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>{editingItem ? 'Edit' : 'Add'} {modalType.charAt(0).toUpperCase() + modalType.slice(1)}</h2>
              <button className="modal-close" onClick={() => setShowModal(false)}>×</button>
            </div>
            <form onSubmit={handleSubmit}>
              <div className="modal-body">
                {modalType === 'experience' && (
                  <>
                    <div className="grid grid-2">
                      <div className="form-group">
                        <label className="form-label">Job Title *</label>
                        <input type="text" className="form-control" value={formData.title || ''} onChange={(e) => setFormData({ ...formData, title: e.target.value })} required />
                      </div>
                      <div className="form-group">
                        <label className="form-label">Company *</label>
                        <input type="text" className="form-control" value={formData.company || ''} onChange={(e) => setFormData({ ...formData, company: e.target.value })} required />
                      </div>
                    </div>
                    <div className="form-group">
                      <label className="form-label">Location</label>
                      <input type="text" className="form-control" value={formData.location || ''} onChange={(e) => setFormData({ ...formData, location: e.target.value })} />
                    </div>
                    <div className="grid grid-2">
                      <div className="form-group">
                        <label className="form-label">Start Date *</label>
                        <input type="date" className="form-control" value={formData.start_date || ''} onChange={(e) => setFormData({ ...formData, start_date: e.target.value })} required />
                      </div>
                      <div className="form-group">
                        <label className="form-label">End Date</label>
                        <input type="date" className="form-control" value={formData.end_date || ''} onChange={(e) => setFormData({ ...formData, end_date: e.target.value })} disabled={formData.is_current} />
                      </div>
                    </div>
                    <div className="form-group">
                      <label style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <input type="checkbox" checked={formData.is_current || false} onChange={(e) => setFormData({ ...formData, is_current: e.target.checked, end_date: '' })} />
                        Currently working here
                      </label>
                    </div>
                    <div className="form-group">
                      <label className="form-label">Responsibilities</label>
                      <textarea className="form-control" value={formData.responsibilities || ''} onChange={(e) => setFormData({ ...formData, responsibilities: e.target.value })} rows={4} placeholder="Describe your responsibilities and achievements..." />
                    </div>
                  </>
                )}

                {modalType === 'education' && (
                  <>
                    <div className="form-group">
                      <label className="form-label">School/University *</label>
                      <input type="text" className="form-control" value={formData.school || ''} onChange={(e) => setFormData({ ...formData, school: e.target.value })} required />
                    </div>
                    <div className="grid grid-2">
                      <div className="form-group">
                        <label className="form-label">Degree *</label>
                        <input type="text" className="form-control" value={formData.degree || ''} onChange={(e) => setFormData({ ...formData, degree: e.target.value })} required placeholder="e.g., Bachelor's, Master's" />
                      </div>
                      <div className="form-group">
                        <label className="form-label">Field of Study</label>
                        <input type="text" className="form-control" value={formData.field_of_study || ''} onChange={(e) => setFormData({ ...formData, field_of_study: e.target.value })} placeholder="e.g., Computer Science" />
                      </div>
                    </div>
                    <div className="grid grid-2">
                      <div className="form-group">
                        <label className="form-label">Start Date</label>
                        <input type="date" className="form-control" value={formData.start_date || ''} onChange={(e) => setFormData({ ...formData, start_date: e.target.value })} />
                      </div>
                      <div className="form-group">
                        <label className="form-label">End Date</label>
                        <input type="date" className="form-control" value={formData.end_date || ''} onChange={(e) => setFormData({ ...formData, end_date: e.target.value })} />
                      </div>
                    </div>
                    <div className="form-group">
                      <label className="form-label">GPA</label>
                      <input type="text" className="form-control" value={formData.gpa || ''} onChange={(e) => setFormData({ ...formData, gpa: e.target.value })} placeholder="e.g., 3.8" />
                    </div>
                  </>
                )}

                {modalType === 'skill' && (
                  <>
                    <div className="form-group">
                      <label className="form-label">Skill Name *</label>
                      <input type="text" className="form-control" value={formData.skill_name || ''} onChange={(e) => setFormData({ ...formData, skill_name: e.target.value })} required placeholder="e.g., JavaScript, Python, Project Management" />
                    </div>
                    <div className="form-group">
                      <label className="form-label">Proficiency Level</label>
                      <select className="form-control" value={formData.proficiency || 'intermediate'} onChange={(e) => setFormData({ ...formData, proficiency: e.target.value })}>
                        <option value="beginner">Beginner</option>
                        <option value="intermediate">Intermediate</option>
                        <option value="advanced">Advanced</option>
                        <option value="expert">Expert</option>
                      </select>
                    </div>
                  </>
                )}

                {modalType === 'project' && (
                  <>
                    <div className="form-group">
                      <label className="form-label">Project Title *</label>
                      <input type="text" className="form-control" value={formData.title || ''} onChange={(e) => setFormData({ ...formData, title: e.target.value })} required />
                    </div>
                    <div className="form-group">
                      <label className="form-label">Description</label>
                      <textarea className="form-control" value={formData.description || ''} onChange={(e) => setFormData({ ...formData, description: e.target.value })} rows={4} placeholder="Describe your project..." />
                    </div>
                    <div className="form-group">
                      <label className="form-label">Technologies Used</label>
                      <input type="text" className="form-control" value={formData.technologies || ''} onChange={(e) => setFormData({ ...formData, technologies: e.target.value })} placeholder="e.g., React, Node.js, PostgreSQL" />
                    </div>
                    <div className="form-group">
                      <label className="form-label">Project URL</label>
                      <input type="url" className="form-control" value={formData.url || ''} onChange={(e) => setFormData({ ...formData, url: e.target.value })} placeholder="https://..." />
                    </div>
                    <div className="grid grid-2">
                      <div className="form-group">
                        <label className="form-label">Start Date</label>
                        <input type="date" className="form-control" value={formData.start_date || ''} onChange={(e) => setFormData({ ...formData, start_date: e.target.value })} />
                      </div>
                      <div className="form-group">
                        <label className="form-label">End Date</label>
                        <input type="date" className="form-control" value={formData.end_date || ''} onChange={(e) => setFormData({ ...formData, end_date: e.target.value })} />
                      </div>
                    </div>
                  </>
                )}
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setShowModal(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={saving}>{saving ? 'Saving...' : 'Save'}</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Analyze Modal */}
      {showAnalyzeModal && (
        <div className="modal-overlay" onClick={() => setShowAnalyzeModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '700px' }}>
            <div className="modal-header">
              <h2>Analyze Resume Match</h2>
              <button className="modal-close" onClick={() => setShowAnalyzeModal(false)}>×</button>
            </div>
            <div className="modal-body">
              {!analysisResult ? (
                <>
                  <div className="form-group">
                    <label className="form-label">Paste the Job Description</label>
                    <textarea
                      className="form-control"
                      value={jobDescription}
                      onChange={(e) => setJobDescription(e.target.value)}
                      rows={8}
                      placeholder="Paste the full job description here..."
                    />
                  </div>
                  <button className="btn btn-primary" onClick={analyzeResume} disabled={analyzing || !jobDescription.trim()}>
                    {analyzing ? 'Analyzing...' : 'Analyze Match'}
                  </button>
                </>
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

                  <button className="btn btn-outline" onClick={() => setAnalysisResult(null)} style={{ marginTop: '20px' }}>
                    Analyze Another Job
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Tailor Modal */}
      {showTailorModal && (
        <div className="modal-overlay" onClick={() => setShowTailorModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Generate Tailored Resume</h2>
              <button className="modal-close" onClick={() => setShowTailorModal(false)}>×</button>
            </div>
            <div className="modal-body">
              <p style={{ marginBottom: '20px', color: '#6b7280' }}>
                This will create a new resume with your existing content rephrased to better match the job description.
              </p>
              <div className="form-group">
                <label className="form-label">Job Title *</label>
                <input
                  type="text"
                  className="form-control"
                  value={jobTitle}
                  onChange={(e) => setJobTitle(e.target.value)}
                  placeholder="e.g., Senior Software Engineer"
                />
              </div>
              <div className="form-group">
                <label className="form-label">Job Description *</label>
                <textarea
                  className="form-control"
                  value={jobDescription}
                  onChange={(e) => setJobDescription(e.target.value)}
                  rows={8}
                  placeholder="Paste the full job description here..."
                />
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setShowTailorModal(false)}>Cancel</button>
              <button className="btn btn-primary" onClick={tailorResume} disabled={analyzing || !jobDescription.trim() || !jobTitle.trim()}>
                {analyzing ? 'Generating...' : 'Generate & Download'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ResumeBuilder;
