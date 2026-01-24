import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle auth errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// Auth APIs
export const authAPI = {
  register: (data) => api.post('/api/auth/register', data),
  login: (data) => api.post('/api/auth/login', data),
  getMe: () => api.get('/api/auth/me'),
  updateProfile: (data) => api.put('/api/auth/profile', data),
};

// Jobs APIs
export const jobsAPI = {
  search: (data) => api.post('/api/jobs/search', data),
  getAll: () => api.get('/api/jobs'),
  getOne: (id) => api.get(`/api/jobs/${id}`),
  save: (job) => api.post('/api/jobs', job),
  delete: (id) => api.delete(`/api/jobs/${id}`),
  getStats: () => api.get('/api/stats'),
};

// Applications APIs
export const applicationsAPI = {
  getAll: () => api.get('/api/applications'),
  create: (data) => api.post('/api/applications', data),
  update: (id, data) => api.put(`/api/applications/${id}`, data),
  delete: (id) => api.delete(`/api/applications/${id}`),
  getDashboardStats: () => api.get('/api/dashboard/stats'),
};

// Work Experience APIs
export const workExperienceAPI = {
  getAll: () => api.get('/api/work-experience'),
  create: (data) => api.post('/api/work-experience', data),
  update: (id, data) => api.put(`/api/work-experience/${id}`, data),
  delete: (id) => api.delete(`/api/work-experience/${id}`),
};

// Education APIs
export const educationAPI = {
  getAll: () => api.get('/api/education'),
  create: (data) => api.post('/api/education', data),
  update: (id, data) => api.put(`/api/education/${id}`, data),
  delete: (id) => api.delete(`/api/education/${id}`),
};

// Skills APIs
export const skillsAPI = {
  getAll: () => api.get('/api/skills'),
  create: (data) => api.post('/api/skills', data),
  update: (id, data) => api.put(`/api/skills/${id}`, data),
  delete: (id) => api.delete(`/api/skills/${id}`),
};

// Projects APIs
export const projectsAPI = {
  getAll: () => api.get('/api/projects'),
  create: (data) => api.post('/api/projects', data),
  update: (id, data) => api.put(`/api/projects/${id}`, data),
  delete: (id) => api.delete(`/api/projects/${id}`),
};

// Resume APIs
export const resumeAPI = {
  getComplete: () => api.get('/api/resume'),
  download: (userId) => api.get(`/api/users/${userId}/resume/download`, { responseType: 'blob' }),
  analyze: (userId, jobDescription) => api.post(`/api/users/${userId}/resume/analyze`, { job_description: jobDescription }),
  tailor: (userId, data) => api.post(`/api/users/${userId}/resume/tailor`, data, { responseType: 'blob' }),
};

// Interview APIs
export const interviewAPI = {
  start: (data) => api.post('/api/interview/start', data),
  getSessions: () => api.get('/api/interview/sessions'),
  getQuestions: (sessionId) => api.get(`/api/interview/${sessionId}/questions`),
  submitAnswer: (sessionId, data) => api.post(`/api/interview/${sessionId}/answer`, data),
  getFeedback: (sessionId) => api.get(`/api/interview/${sessionId}/feedback`),
};

export default api;
