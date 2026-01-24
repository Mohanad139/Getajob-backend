import React, { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { interviewAPI } from '../services/api';
import { parseError } from '../services/utils';

const Interview = () => {
  const location = useLocation();
  const [view, setView] = useState('start'); // start, questions, feedback, history
  const [sessions, setSessions] = useState([]);
  const [currentSession, setCurrentSession] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [answer, setAnswer] = useState('');
  const [feedback, setFeedback] = useState(null);
  const [overallFeedback, setOverallFeedback] = useState(null);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState({ type: '', text: '' });

  // Start form
  const [jobTitle, setJobTitle] = useState('');
  const [jobDescription, setJobDescription] = useState('');
  const [numQuestions, setNumQuestions] = useState(5);

  useEffect(() => {
    loadSessions();
    // Check if navigated from Applications with a sessionId
    if (location.state?.sessionId) {
      loadSessionFromNavigation(location.state.sessionId);
    }
  }, [location.state]);

  const loadSessionFromNavigation = async (sessionId) => {
    setLoading(true);
    try {
      const questionsRes = await interviewAPI.getQuestions(sessionId);
      setQuestions(questionsRes.data.questions);
      setCurrentSession({ session_id: sessionId });
      setCurrentQuestionIndex(0);
      setView('questions');
      setFeedback(null);
      setAnswer('');
    } catch (error) {
      setMessage({ type: 'error', text: parseError(error) || 'Failed to load interview session.' });
    } finally {
      setLoading(false);
    }
  };

  const loadSessions = async () => {
    try {
      const response = await interviewAPI.getSessions();
      setSessions(response.data);
    } catch (error) {
      console.error('Error loading sessions:', error);
    }
  };

  const startInterview = async () => {
    if (!jobTitle.trim() || !jobDescription.trim()) return;

    setLoading(true);
    try {
      const response = await interviewAPI.start({
        job_title: jobTitle,
        job_description: jobDescription,
        num_questions: numQuestions
      });
      setCurrentSession(response.data);

      // Load questions
      const questionsRes = await interviewAPI.getQuestions(response.data.session_id);
      setQuestions(questionsRes.data.questions);
      setCurrentQuestionIndex(0);
      setView('questions');
      setFeedback(null);
    } catch (error) {
      setMessage({ type: 'error', text: parseError(error) || 'Failed to start interview session.' });
    } finally {
      setLoading(false);
    }
  };

  const submitAnswer = async () => {
    if (!answer.trim()) return;

    setSubmitting(true);
    try {
      const currentQuestion = questions[currentQuestionIndex];
      const response = await interviewAPI.submitAnswer(currentSession.session_id, {
        question_id: currentQuestion.id,
        answer: answer
      });
      setFeedback(response.data);
    } catch (error) {
      setMessage({ type: 'error', text: parseError(error) || 'Failed to submit answer.' });
    } finally {
      setSubmitting(false);
    }
  };

  const nextQuestion = () => {
    if (currentQuestionIndex < questions.length - 1) {
      setCurrentQuestionIndex(currentQuestionIndex + 1);
      setAnswer('');
      setFeedback(null);
    } else {
      // All questions answered, get overall feedback
      getOverallFeedback();
    }
  };

  const getOverallFeedback = async () => {
    setLoading(true);
    try {
      const response = await interviewAPI.getFeedback(currentSession.session_id);
      setOverallFeedback(response.data);
      setView('feedback');
      loadSessions();
    } catch (error) {
      setMessage({ type: 'error', text: parseError(error) || 'Failed to get overall feedback.' });
    } finally {
      setLoading(false);
    }
  };

  const startNewSession = () => {
    setView('start');
    setCurrentSession(null);
    setQuestions([]);
    setCurrentQuestionIndex(0);
    setAnswer('');
    setFeedback(null);
    setOverallFeedback(null);
    setJobTitle('');
    setJobDescription('');
  };

  const resumeSession = async (session) => {
    setLoading(true);
    try {
      setCurrentSession(session);
      const questionsRes = await interviewAPI.getQuestions(session.id);
      const allQuestions = questionsRes.data.questions;
      setQuestions(allQuestions);

      // Find first unanswered question
      const unansweredIndex = allQuestions.findIndex(q => !q.user_answer);
      if (unansweredIndex === -1) {
        // All answered, show feedback
        const feedbackRes = await interviewAPI.getFeedback(session.id);
        setOverallFeedback(feedbackRes.data);
        setView('feedback');
      } else {
        setCurrentQuestionIndex(unansweredIndex);
        setView('questions');
      }
    } catch (error) {
      setMessage({ type: 'error', text: parseError(error) || 'Failed to load session.' });
    } finally {
      setLoading(false);
    }
  };

  const currentQuestion = questions[currentQuestionIndex];

  return (
    <div className="container">
      {message.text && (
        <div className={`alert alert-${message.type}`}>
          {message.text}
          <button onClick={() => setMessage({ type: '', text: '' })} style={{ float: 'right', background: 'none', border: 'none', cursor: 'pointer' }}>×</button>
        </div>
      )}

      {/* Start View */}
      {view === 'start' && (
        <>
          <div className="page-header">
            <h1>Interview Practice</h1>
            {sessions.length > 0 && (
              <button className="btn btn-outline" onClick={() => setView('history')}>
                View History
              </button>
            )}
          </div>

          <div className="card">
            <div className="card-header">
              <h2 className="card-title">Start New Interview Session</h2>
            </div>
            <p style={{ color: '#6b7280', marginBottom: '24px' }}>
              Practice for your upcoming interview! Enter the job details and we'll generate relevant questions based on the job description.
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

            <div className="form-group">
              <label className="form-label">Number of Questions</label>
              <select
                className="form-control"
                value={numQuestions}
                onChange={(e) => setNumQuestions(parseInt(e.target.value))}
                style={{ width: 'auto' }}
              >
                <option value={3}>3 Questions</option>
                <option value={5}>5 Questions</option>
                <option value={7}>7 Questions</option>
                <option value={10}>10 Questions</option>
              </select>
            </div>

            <button
              className="btn btn-primary btn-lg"
              onClick={startInterview}
              disabled={loading || !jobTitle.trim() || !jobDescription.trim()}
            >
              {loading ? 'Generating Questions...' : 'Start Interview'}
            </button>
          </div>
        </>
      )}

      {/* Questions View */}
      {view === 'questions' && currentQuestion && (
        <>
          <div className="page-header">
            <h1>Interview Practice</h1>
            <span style={{ color: '#6b7280' }}>
              Question {currentQuestionIndex + 1} of {questions.length}
            </span>
          </div>

          {/* Progress Bar */}
          <div className="progress-bar" style={{ marginBottom: '24px' }}>
            <div
              className="progress"
              style={{ width: `${((currentQuestionIndex + 1) / questions.length) * 100}%` }}
            ></div>
          </div>

          {/* Question Card */}
          <div className="question-card">
            <span className={`question-type ${currentQuestion.type}`}>
              {currentQuestion.type}
            </span>
            <p className="question-text">{currentQuestion.text}</p>
          </div>

          {/* Answer Section */}
          {!feedback ? (
            <div className="card">
              <div className="form-group">
                <label className="form-label">Your Answer</label>
                <textarea
                  className="form-control"
                  value={answer}
                  onChange={(e) => setAnswer(e.target.value)}
                  rows={8}
                  placeholder="Type your answer here... Speak as if you were in an actual interview."
                />
              </div>
              <button
                className="btn btn-primary"
                onClick={submitAnswer}
                disabled={submitting || !answer.trim()}
              >
                {submitting ? 'Analyzing...' : 'Submit Answer'}
              </button>
            </div>
          ) : (
            <div className="feedback-card">
              <div className="feedback-score">
                {feedback.score}/10
              </div>
              <p style={{ textAlign: 'center', color: '#6b7280', marginBottom: '24px' }}>
                {feedback.score >= 8 ? 'Excellent!' : feedback.score >= 6 ? 'Good job!' : feedback.score >= 4 ? 'Room for improvement' : 'Keep practicing!'}
              </p>

              <div className="feedback-section">
                <h4>Strengths</h4>
                <ul>
                  {feedback.strengths?.map((s, i) => <li key={i}>{s}</li>)}
                </ul>
              </div>

              <div className="feedback-section">
                <h4>Areas for Improvement</h4>
                <ul>
                  {feedback.weaknesses?.map((w, i) => <li key={i}>{w}</li>)}
                </ul>
              </div>

              <div className="feedback-section">
                <h4>Suggestions</h4>
                <ul>
                  {feedback.suggestions?.map((s, i) => <li key={i}>{s}</li>)}
                </ul>
              </div>

              <button className="btn btn-primary" onClick={nextQuestion} style={{ marginTop: '20px' }}>
                {currentQuestionIndex < questions.length - 1 ? 'Next Question' : 'See Overall Feedback'}
              </button>
            </div>
          )}
        </>
      )}

      {/* Overall Feedback View */}
      {view === 'feedback' && overallFeedback && (
        <>
          <div className="page-header">
            <h1>Interview Complete!</h1>
          </div>

          <div className="card" style={{ textAlign: 'center', padding: '40px' }}>
            <div style={{ fontSize: '4rem', fontWeight: '700', color: '#4f46e5', marginBottom: '8px' }}>
              {overallFeedback.average_score?.toFixed(1)}/10
            </div>
            <p style={{ color: '#6b7280', marginBottom: '16px' }}>Average Score</p>
            <span className={`badge ${
              overallFeedback.readiness === 'Highly Ready' ? 'badge-offered' :
              overallFeedback.readiness === 'Ready' ? 'badge-interview' :
              overallFeedback.readiness === 'Needs Work' ? 'badge-applied' :
              'badge-rejected'
            }`} style={{ fontSize: '1rem', padding: '8px 20px' }}>
              {overallFeedback.readiness}
            </span>
          </div>

          <div className="card">
            <h3 style={{ marginBottom: '16px' }}>Overall Summary</h3>
            <p style={{ color: '#374151' }}>{overallFeedback.overall_summary}</p>
          </div>

          <div className="grid grid-2">
            <div className="card">
              <h3 style={{ marginBottom: '16px', color: '#059669' }}>Top Strengths</h3>
              <ul style={{ paddingLeft: '20px' }}>
                {overallFeedback.top_strengths?.map((s, i) => (
                  <li key={i} style={{ marginBottom: '8px' }}>{s}</li>
                ))}
              </ul>
            </div>

            <div className="card">
              <h3 style={{ marginBottom: '16px', color: '#dc2626' }}>Areas to Improve</h3>
              <ul style={{ paddingLeft: '20px' }}>
                {overallFeedback.top_improvements?.map((i, idx) => (
                  <li key={idx} style={{ marginBottom: '8px' }}>{i}</li>
                ))}
              </ul>
            </div>
          </div>

          <div className="card">
            <h3 style={{ marginBottom: '16px' }}>Recommendations</h3>
            <ul style={{ paddingLeft: '20px' }}>
              {overallFeedback.recommendations?.map((r, i) => (
                <li key={i} style={{ marginBottom: '8px' }}>{r}</li>
              ))}
            </ul>
          </div>

          <div style={{ display: 'flex', gap: '12px', marginTop: '24px' }}>
            <button className="btn btn-primary" onClick={startNewSession}>
              Start New Session
            </button>
            <button className="btn btn-outline" onClick={() => setView('history')}>
              View History
            </button>
          </div>
        </>
      )}

      {/* History View */}
      {view === 'history' && (
        <>
          <div className="page-header">
            <h1>Interview History</h1>
            <button className="btn btn-primary" onClick={() => setView('start')}>
              Start New Session
            </button>
          </div>

          {sessions.length === 0 ? (
            <div className="empty-state">
              <h3>No interview sessions yet</h3>
              <p>Start your first practice interview!</p>
              <button className="btn btn-primary" onClick={() => setView('start')} style={{ marginTop: '20px' }}>
                Start Interview
              </button>
            </div>
          ) : (
            <div className="card">
              <div className="table-container">
                <table>
                  <thead>
                    <tr>
                      <th>Job Title</th>
                      <th>Questions</th>
                      <th>Status</th>
                      <th>Date</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sessions.map((session) => (
                      <tr key={session.id}>
                        <td><strong>{session.job_title}</strong></td>
                        <td>{session.total_questions} questions</td>
                        <td>
                          <span className={`badge ${session.is_completed ? 'badge-offered' : 'badge-applied'}`}>
                            {session.is_completed ? 'Completed' : 'In Progress'}
                          </span>
                        </td>
                        <td>{new Date(session.created_at).toLocaleDateString()}</td>
                        <td>
                          <button
                            className="btn btn-sm btn-primary"
                            onClick={() => resumeSession(session)}
                          >
                            {session.is_completed ? 'View Results' : 'Resume'}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}

      {/* Loading Overlay */}
      {loading && view !== 'start' && (
        <div className="modal-overlay">
          <div style={{ textAlign: 'center', color: 'white' }}>
            <div className="spinner" style={{ margin: '0 auto 20px', borderTopColor: 'white' }}></div>
            <p>Loading...</p>
          </div>
        </div>
      )}
    </div>
  );
};

export default Interview;
