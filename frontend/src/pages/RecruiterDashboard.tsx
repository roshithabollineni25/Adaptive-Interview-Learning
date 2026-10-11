import React, { useEffect, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { apiClient } from '../api/client';
import type { JobDescription, CandidateSummary, InterviewSessionSummary } from '../types';
import {
  Briefcase, Users, Plus,
  AlertCircle, LogOut, ExternalLink, Calendar
} from 'lucide-react';

export const RecruiterDashboard: React.FC = () => {
  const [jobs, setJobs] = useState<JobDescription[]>([]);
  const [candidates, setCandidates] = useState<CandidateSummary[]>([]);
  const [sessions, setSessions] = useState<InterviewSessionSummary[]>([]);
  const [systemDiag, setSystemDiag] = useState<{ llm_configured: boolean; llm_status_message: string } | null>(null);
  const [showCandidates, setShowCandidates] = useState(false);

  // Job creation form
  const [showJobModal, setShowJobModal] = useState(false);
  const [jobTitle, setJobTitle] = useState('');
  const [jobDept, setJobDept] = useState('');
  const [jobText, setJobText] = useState('');

  // Schedule Interview Session Form
  const [showScheduleModal, setShowScheduleModal] = useState(false);
  const [selectedCandidateId, setSelectedCandidateId] = useState<number | ''>('');
  const [selectedJobId, setSelectedJobId] = useState<number | ''>('');
  const [scheduleTime, setScheduleTime] = useState<string>('');

  const navigate = useNavigate();

  const loadData = async () => {
    try {
      const [jobsData, candidatesData, sessionsData, diagData] = await Promise.all([
        apiClient.getJobs().catch(e => { console.error('getJobs error', e); return []; }),
        apiClient.getCandidates().catch(e => { console.error('getCandidates error', e); return []; }),
        apiClient.getSessions().catch(e => { console.error('getSessions error', e); return []; }),
        apiClient.getSystemStatus().catch(() => null)
      ]);
      setJobs(jobsData);
      setCandidates(candidatesData);
      setSessions(sessionsData);
      if (diagData) setSystemDiag(diagData);
    } catch (err: any) {
      if (err?.response?.status === 401 || err?.response?.status === 403) {
        navigate('/login');
      }
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const openScheduleModal = async () => {
    try {
      const [candidatesData, jobsData] = await Promise.all([
        apiClient.getCandidates().catch(() => candidates),
        apiClient.getJobs().catch(() => jobs)
      ]);
      setCandidates(candidatesData);
      setJobs(jobsData);
    } catch (e) {
      console.error('Failed to refresh data on opening schedule modal', e);
    }
    setSelectedCandidateId('');
    setSelectedJobId('');
    setScheduleTime('');
    setShowScheduleModal(true);
  };

  const handleCreateJob = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await apiClient.createJob({ title: jobTitle, department: jobDept, raw_text: jobText });
      setShowJobModal(false);
      setJobTitle('');
      setJobDept('');
      setJobText('');
      loadData();
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to create job');
    }
  };

  const handleScheduleSession = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCandidateId || !selectedJobId || !scheduleTime) return;

    try {
      const res = await apiClient.scheduleInterview({
        candidate_id: Number(selectedCandidateId),
        job_description_id: Number(selectedJobId),
        scheduled_start: new Date(scheduleTime).toISOString()
      });
      setShowScheduleModal(false);
      setSelectedCandidateId('');
      setSelectedJobId('');
      setScheduleTime('');
      await loadData();

      const emailNotice = res.email_delivery?.delivered
        ? `Invitation sent to candidate's registered email address.`
        : `Invitation recorded in database. Note: ${res.email_delivery?.message || 'SMTP config required'}`;

      alert(`Interview successfully scheduled! ${emailNotice}\nCandidate direct link: ${window.location.origin}${res.interview_link}`);
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to schedule interview');
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    navigate('/login');
  };

  return (
    <div style={{ maxWidth: 1180, margin: '40px auto', padding: '0 24px' }}>
      {/* Top Header */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: 28,
        borderBottom: '1px solid var(--border-light)',
        paddingBottom: 20
      }}>
        <div>
          <span style={{ fontSize: 12, color: 'var(--sage-accent)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Recruiter Workspace
          </span>
          <h1 style={{ fontSize: 26, fontWeight: 700, color: 'var(--text-primary)' }}>Adaptive Interview Intelligence</h1>
        </div>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <Link to="/" className="btn btn-secondary" style={{ fontSize: 13, padding: '7px 14px' }}>
            Public Landing Page
          </Link>
          <button onClick={handleLogout} className="btn btn-secondary" style={{ fontSize: 13, padding: '7px 14px' }}>
            <LogOut size={14} /> Logout
          </button>
        </div>
      </div>

      {/* Honest LLM Configuration Disclosure Notice */}
      {systemDiag && !systemDiag.llm_configured && (
        <div style={{
          marginBottom: 24,
          padding: '14px 18px',
          borderRadius: 8,
          backgroundColor: '#fff3e0',
          border: '1px solid #ffe0b2',
          color: 'var(--warning)',
          fontSize: 13,
          display: 'flex',
          alignItems: 'flex-start',
          gap: 12
        }}>
          <AlertCircle size={20} style={{ flexShrink: 0, marginTop: 2 }} />
          <div>
            <strong>Configuration Disclosure:</strong> {systemDiag.llm_status_message}
            <div style={{ marginTop: 4, color: 'var(--text-secondary)', fontSize: 12 }}>
              To enable real Google Gemini evaluations: add <code>GEMINI_API_KEY=your_key</code> in <code>.env</code> and restart the backend server.
            </div>
          </div>
        </div>
      )}

      {/* Quick Metric Blocks */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 18, marginBottom: 32 }}>
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
            <span style={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8 }}>
              <Briefcase size={18} color="var(--sage-accent)" /> Job Positions ({jobs.length})
            </span>
            <button onClick={() => setShowJobModal(true)} className="btn btn-primary" style={{ padding: '5px 12px', fontSize: 12 }}>
              <Plus size={14} /> Add Role
            </button>
          </div>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
            Define positions and extract AI-weighted core competencies.
          </p>
        </div>

        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
            <span style={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8 }}>
              <Users size={18} color="var(--sage-accent)" /> Registered Candidates ({candidates.length})
            </span>
            <button
              type="button"
              onClick={() => setShowCandidates(true)}
              className="btn btn-secondary"
              style={{ padding: '5px 12px', fontSize: 12 }}
            >
              View Candidates
            </button>
          </div>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
            Candidates submit target roles & resumes via the Candidate Portal.
          </p>
        </div>

        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
            <span style={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8 }}>
              <Calendar size={18} color="var(--sage-accent)" /> Interview Sessions ({sessions.length})
            </span>
            <button
              onClick={openScheduleModal}
              disabled={jobs.length === 0}
              className="btn btn-primary"
              style={{ padding: '5px 12px', fontSize: 12, opacity: jobs.length === 0 ? 0.5 : 1 }}
            >
              <Calendar size={14} /> Schedule Interview
            </button>
          </div>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
            Confirm scheduled windows and dispatch email invitations.
          </p>
        </div>
      </div>

      {showCandidates && (
        <div className="card" style={{ marginBottom: 24 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h3>Registered Candidates</h3>
            <button className="btn btn-secondary" onClick={() => setShowCandidates(false)}>
              Close
            </button>
          </div>

          {candidates.length === 0 ? (
            <p>No registered candidates found.</p>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    <th align="left">Name</th>
                    <th align="left">Email</th>
                    <th align="left">Target Role</th>
                    <th align="left">Resume</th>
                  </tr>
                </thead>
                <tbody>
                  {candidates.map((candidate) => (
                    <tr key={candidate.id}>
                      <td>{candidate.full_name}</td>
                      <td>{candidate.email}</td>
                      <td>{candidate.target_role || 'Not provided'}</td>
                      <td>{candidate.resume_filename || 'Not uploaded'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
      {/* Real Sessions Table */}
      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 18 }}>
          <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>Interview Schedules & Human Decision Queue</h2>
          <button
            onClick={loadData}
            className="btn btn-secondary"
            style={{ fontSize: 12, padding: '5px 12px' }}
            title="Refresh candidates and scheduled interview sessions"
          >
            Refresh Queue
          </button>
        </div>
        {sessions.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '40px 20px', color: 'var(--text-muted)' }}>
            <p style={{ fontSize: 15, fontWeight: 600, marginBottom: 6 }}>No interviews scheduled yet.</p>
            <p style={{ fontSize: 13 }}>
              Once a candidate is registered, click <strong>Schedule Interview</strong> to confirm an interview window and issue an invitation.
            </p>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border-light)', textAlign: 'left', color: 'var(--text-muted)' }}>
                  <th style={{ padding: '12px 10px' }}>Candidate</th>
                  <th style={{ padding: '12px 10px' }}>Target Position</th>
                  <th style={{ padding: '12px 10px' }}>Scheduled Start</th>
                  <th style={{ padding: '12px 10px' }}>Status</th>
                  <th style={{ padding: '12px 10px' }}>Identity Verification</th>
                  <th style={{ padding: '12px 10px' }}>AI Score</th>
                  <th style={{ padding: '12px 10px' }}>Recruiter Decision</th>
                  <th style={{ padding: '12px 10px' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {sessions.map((s) => (
                  <tr key={s.id} style={{ borderBottom: '1px solid var(--border-light)' }}>
                    <td style={{ padding: '14px 10px', fontWeight: 600 }}>
                      {s.candidate_name}
                      <div style={{ fontSize: 12, color: 'var(--text-muted)', fontWeight: 400 }}>{s.candidate_email}</div>
                    </td>
                    <td style={{ padding: '14px 10px' }}>{s.job_title}</td>
                    <td style={{ padding: '14px 10px' }}>
                      {s.scheduled_start ? (
                        <div>
                          <div>{new Date(s.scheduled_start).toLocaleDateString()}</div>
                          <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{new Date(s.scheduled_start).toLocaleTimeString()}</div>
                        </div>
                      ) : (
                        <span style={{ color: 'var(--text-muted)' }}>Immediate</span>
                      )}
                    </td>
                    <td style={{ padding: '14px 10px' }}>
                      <span className={`badge ${s.status === 'completed' ? 'badge-success' : s.status === 'in_progress' ? 'badge-info' : 'badge-warning'
                        }`}>
                        {s.status.replace('_', ' ')}
                      </span>
                    </td>
                    <td style={{ padding: '14px 10px' }}>
                      {s.identity_verified ? (
                        <span className="badge badge-success">✓ Verified</span>
                      ) : (
                        <span className="badge badge-warning">Gate Pending</span>
                      )}
                    </td>
                    <td style={{ padding: '14px 10px' }}>
                      {s.final_score !== undefined && s.final_score !== null ? (
                        <span style={{ fontWeight: 700, color: s.final_score >= 7 ? 'var(--success)' : 'var(--warning)' }}>
                          {s.final_score} / 10
                        </span>
                      ) : (
                        <span style={{ color: 'var(--text-muted)' }}>In progress</span>
                      )}
                    </td>
                    <td style={{ padding: '14px 10px' }}>
                      {s.recruiter_decision ? (
                        <span className={`badge ${s.recruiter_decision === 'Hired' ? 'badge-success' : s.recruiter_decision === 'Rejected' ? 'badge-danger' : 'badge-warning'
                          }`}>
                          {s.recruiter_decision}
                        </span>
                      ) : (
                        <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>Under Review</span>
                      )}
                    </td>
                    <td style={{ padding: '14px 10px', display: 'flex', gap: 8 }}>
                      <Link to={`/recruiter/sessions/${s.id}`} className="btn btn-secondary" style={{ padding: '5px 12px', fontSize: 12 }}>
                        Review Report
                      </Link>
                      <Link to={`/interview/${s.session_token}`} target="_blank" className="btn btn-primary" style={{ padding: '5px 12px', fontSize: 12 }}>
                        Access Link <ExternalLink size={12} />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Modal: Add Job */}
      {showJobModal && (
        <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(31, 29, 36, 0.75)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50, backdropFilter: 'blur(4px)' }}>
          <div className="card" style={{ width: 520, maxWidth: '90%' }}>
            <h3 style={{ fontSize: 18, fontWeight: 700, marginBottom: 16 }}>Create Job Role Specification</h3>
            <form onSubmit={handleCreateJob} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div>
                <label style={{ display: 'block', fontSize: 13, marginBottom: 6, color: 'var(--text-secondary)' }}>Job Title</label>
                <input required style={{ width: '100%' }} value={jobTitle} onChange={(e) => setJobTitle(e.target.value)} placeholder="e.g. Senior Distributed Systems Engineer" />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: 13, marginBottom: 6, color: 'var(--text-secondary)' }}>Department</label>
                <input style={{ width: '100%' }} value={jobDept} onChange={(e) => setJobDept(e.target.value)} placeholder="e.g. Cloud Infrastructure" />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: 13, marginBottom: 6, color: 'var(--text-secondary)' }}>Job Description & Core Responsibilities</label>
                <textarea required rows={5} style={{ width: '100%' }} value={jobText} onChange={(e) => setJobText(e.target.value)} placeholder="Paste job description text for AI competency extraction..." />
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 10 }}>
                <button type="button" onClick={() => setShowJobModal(false)} className="btn btn-secondary">Cancel</button>
                <button type="submit" className="btn btn-primary">Save Role</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Schedule Interview with Date/Time & Real Email Delivery */}
      {showScheduleModal && (
        <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(31, 29, 36, 0.75)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50, backdropFilter: 'blur(4px)' }}>
          <div className="card" style={{ width: 500, maxWidth: '90%' }}>
            <h3 style={{ fontSize: 18, fontWeight: 700, marginBottom: 8 }}>Schedule Adaptive Interview</h3>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 16 }}>
              Select candidate and job role. An email invitation containing the secure link will be sent to the candidate.
            </p>

            <form onSubmit={handleScheduleSession} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div>
                <label style={{ display: 'block', fontSize: 13, marginBottom: 6, color: 'var(--text-secondary)' }}>Select Candidate</label>
                <select required style={{ width: '100%' }} value={selectedCandidateId} onChange={(e) => setSelectedCandidateId(Number(e.target.value))}>
                  <option value="">-- Choose Candidate --</option>
                  {candidates.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.full_name} ({c.email}){c.target_role ? ` • Role: ${c.target_role}` : ''} {c.has_enrolled_face ? '• Face Enrolled' : ''}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: 13, marginBottom: 6, color: 'var(--text-secondary)' }}>Select Job Position</label>
                <select required style={{ width: '100%' }} value={selectedJobId} onChange={(e) => setSelectedJobId(Number(e.target.value))}>
                  <option value="">-- Choose Role --</option>
                  {jobs.map((j) => (
                    <option key={j.id} value={j.id}>{j.title}</option>
                  ))}
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: 13, marginBottom: 6, color: 'var(--text-secondary)' }}>
                  Confirmed Interview Date & Time (UTC/Local)
                </label>
                <input
                  type="datetime-local"
                  required
                  style={{ width: '100%' }}
                  value={scheduleTime}
                  onChange={(e) => setScheduleTime(e.target.value)}
                />
                <span style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4, display: 'block' }}>
                  The candidate link unlocks 15 mins prior and expires 90 mins after this time.
                </span>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 10 }}>
                <button type="button" onClick={() => setShowScheduleModal(false)} className="btn btn-secondary">Cancel</button>
                <button type="submit" className="btn btn-primary">Confirm Schedule & Dispatch Invite</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
