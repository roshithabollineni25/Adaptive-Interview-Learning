import React, { useEffect, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { apiClient } from '../api/client';
import type { JobDescription, CandidateSummary, InterviewSessionSummary } from '../types';
import {
  Briefcase, Users, Plus,
  AlertCircle, LogOut, ExternalLink, Calendar,
  RefreshCw, Trash2, Clock
} from 'lucide-react';

const parseIsoDate = (val?: string | null): Date | null => {
  if (!val) return null;
  const str = String(val).trim();
  const d = new Date(str.endsWith('Z') || str.includes('+') ? str : `${str}Z`);
  return isNaN(d.getTime()) ? null : d;
};

const formatIstDate = (val?: string | null): string => {
  const d = parseIsoDate(val);
  if (!d) return '';
  return new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Asia/Kolkata',
    day: '2-digit',
    month: '2-digit',
    year: 'numeric'
  }).format(d);
};

const formatIstTime = (val?: string | null): string => {
  const d = parseIsoDate(val);
  if (!d) return '';
  return new Intl.DateTimeFormat('en-US', {
    timeZone: 'Asia/Kolkata',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true
  }).format(d);
};

export const RecruiterDashboard: React.FC = () => {
  const [jobs, setJobs] = useState<JobDescription[]>([]);
  const [candidates, setCandidates] = useState<CandidateSummary[]>([]);
  const [sessions, setSessions] = useState<InterviewSessionSummary[]>([]);
  const [systemDiag, setSystemDiag] = useState<{ llm_configured: boolean; llm_status_message: string } | null>(null);
  const [showCandidates, setShowCandidates] = useState(false);
  const [refreshingQueue, setRefreshingQueue] = useState(false);
  const [queueMessage, setQueueMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

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

  // Reschedule Modal Form
  const [showRescheduleModal, setShowRescheduleModal] = useState(false);
  const [sessionToReschedule, setSessionToReschedule] = useState<InterviewSessionSummary | null>(null);
  const [rescheduleTime, setRescheduleTime] = useState<string>('');
  const [rescheduling, setRescheduling] = useState(false);

  // Delete Confirmation Modal Form
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [sessionToDelete, setSessionToDelete] = useState<InterviewSessionSummary | null>(null);
  const [deleting, setDeleting] = useState(false);

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
        : `Invitation recorded in database. Note: ${res.email_delivery?.message || 'Email provider configuration required'}`;

      alert(`Interview successfully scheduled! ${emailNotice}\nCandidate direct link: ${window.location.origin}${res.interview_link}`);
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to schedule interview');
    }
  };

  const handleRefreshQueue = async () => {
    if (refreshingQueue) return;
    try {
      setRefreshingQueue(true);
      setQueueMessage(null);
      await loadData();
      setQueueMessage({ type: 'success', text: `Queue refreshed with live data (${sessions.length} sessions).` });
      setTimeout(() => setQueueMessage(null), 4000);
    } catch (err: any) {
      setQueueMessage({ type: 'error', text: 'Failed to refresh queue from backend.' });
    } finally {
      setRefreshingQueue(false);
    }
  };

  const openRescheduleModal = (session: InterviewSessionSummary) => {
    setSessionToReschedule(session);
    // Preset current scheduled time if available
    if (session.scheduled_start) {
      const d = new Date(session.scheduled_start);
      // Format as local YYYY-MM-DDTHH:mm for datetime-local input
      const localIso = new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
      setRescheduleTime(localIso);
    } else {
      setRescheduleTime('');
    }
    setShowRescheduleModal(true);
  };

  const handleReschedule = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!sessionToReschedule || !rescheduleTime) return;

    try {
      setRescheduling(true);
      const res = await apiClient.rescheduleInterview(sessionToReschedule.id, new Date(rescheduleTime).toISOString());
      setShowRescheduleModal(false);
      setSessionToReschedule(null);
      setRescheduleTime('');
      await loadData();

      const emailNotice = res.email_delivery?.delivered
        ? "Updated invitation sent to candidate's registered email."
        : `Schedule persisted in database. Note: ${res.email_delivery?.message || 'Email provider configuration required'}`;

      alert(`Interview successfully rescheduled! ${emailNotice}`);
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to reschedule interview session.');
    } finally {
      setRescheduling(false);
    }
  };

  const openDeleteModal = (session: InterviewSessionSummary) => {
    setSessionToDelete(session);
    setShowDeleteModal(true);
  };

  const handleDeleteSession = async () => {
    if (!sessionToDelete) return;

    try {
      setDeleting(true);
      const res = await apiClient.deleteInterview(sessionToDelete.id);
      setShowDeleteModal(false);
      setSessionToDelete(null);
      await loadData();
      alert(res.message || 'Interview session deleted successfully.');
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to delete interview session.');
    } finally {
      setDeleting(false);
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
          <div>
            <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>Interview Schedules & Human Decision Queue</h2>
            {queueMessage && (
              <div style={{
                marginTop: 6,
                fontSize: 12,
                color: queueMessage.type === 'success' ? 'var(--success)' : 'var(--danger)',
                fontWeight: 500
              }}>
                {queueMessage.text}
              </div>
            )}
          </div>
          <button
            onClick={handleRefreshQueue}
            disabled={refreshingQueue}
            className="btn btn-secondary"
            style={{ fontSize: 12, padding: '6px 14px', display: 'flex', alignItems: 'center', gap: 6 }}
            title="Fetch live candidate queue and interview records from backend"
          >
            <RefreshCw size={14} className={refreshingQueue ? 'animate-spin' : ''} style={{ animation: refreshingQueue ? 'spin 1s linear infinite' : 'none' }} />
            {refreshingQueue ? 'Refreshing...' : 'Refresh Queue'}
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
          <div style={{ maxHeight: '420px', overflowY: 'auto', overflowX: 'auto', border: '1px solid var(--border-light)', borderRadius: 8 }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
              <thead style={{ position: 'sticky', top: 0, backgroundColor: 'var(--bg-card)', zIndex: 10, boxShadow: '0 1px 0 var(--border-light)' }}>
                <tr style={{ textAlign: 'left', color: 'var(--text-muted)' }}>
                  <th style={{ padding: '12px 10px', backgroundColor: 'var(--bg-card)' }}>Candidate</th>
                  <th style={{ padding: '12px 10px', backgroundColor: 'var(--bg-card)' }}>Target Position</th>
                  <th style={{ padding: '12px 10px', backgroundColor: 'var(--bg-card)' }}>Scheduled Start</th>
                  <th style={{ padding: '12px 10px', backgroundColor: 'var(--bg-card)' }}>Status</th>
                  <th style={{ padding: '12px 10px', backgroundColor: 'var(--bg-card)' }}>Identity Verification</th>
                  <th style={{ padding: '12px 10px', backgroundColor: 'var(--bg-card)' }}>AI Score</th>
                  <th style={{ padding: '12px 10px', backgroundColor: 'var(--bg-card)' }}>Recruiter Decision</th>
                  <th style={{ padding: '12px 10px', backgroundColor: 'var(--bg-card)' }}>Actions</th>
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
                          <div>{formatIstDate(s.scheduled_start)}</div>
                          <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{formatIstTime(s.scheduled_start)}</div>
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
                    <td style={{ padding: '14px 10px' }}>
                      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                        <Link to={`/recruiter/sessions/${s.id}`} className="btn btn-secondary" style={{ padding: '5px 10px', fontSize: 12 }}>
                          Review Report
                        </Link>
                        <Link to={`/interview/${s.session_token}`} target="_blank" className="btn btn-primary" style={{ padding: '5px 10px', fontSize: 12 }}>
                          Access Link <ExternalLink size={11} />
                        </Link>
                        {s.status !== 'completed' && (
                          <button
                            onClick={() => openRescheduleModal(s)}
                            className="btn btn-secondary"
                            style={{ padding: '5px 10px', fontSize: 12, display: 'inline-flex', alignItems: 'center', gap: 4 }}
                            title="Reschedule interview session"
                          >
                            <Clock size={12} /> Reschedule
                          </button>
                        )}
                        <button
                          onClick={() => openDeleteModal(s)}
                          className="btn btn-secondary"
                          style={{ padding: '5px 10px', fontSize: 12, color: 'var(--danger)', display: 'inline-flex', alignItems: 'center', gap: 4 }}
                          title="Delete interview session"
                        >
                          <Trash2 size={12} /> Delete
                        </button>
                      </div>
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

      {/* Modal: Reschedule Interview Session */}
      {showRescheduleModal && sessionToReschedule && (
        <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(31, 29, 36, 0.75)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50, backdropFilter: 'blur(4px)' }}>
          <div className="card" style={{ width: 480, maxWidth: '90%' }}>
            <h3 style={{ fontSize: 18, fontWeight: 700, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 8 }}>
              <Clock size={18} color="var(--sage-accent)" /> Reschedule Interview Session
            </h3>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 16 }}>
              Candidate: <strong>{sessionToReschedule.candidate_name}</strong> ({sessionToReschedule.candidate_email})<br />
              Role: <strong>{sessionToReschedule.job_title}</strong>
            </p>

            <form onSubmit={handleReschedule} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div>
                <label style={{ display: 'block', fontSize: 13, marginBottom: 6, color: 'var(--text-secondary)' }}>
                  New Scheduled Date & Time
                </label>
                <input
                  type="datetime-local"
                  required
                  style={{ width: '100%' }}
                  value={rescheduleTime}
                  onChange={(e) => setRescheduleTime(e.target.value)}
                />
                <span style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4, display: 'block' }}>
                  The candidate's secure link will unlock 15 minutes before this updated time and expire after 90 minutes.
                </span>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 10 }}>
                <button
                  type="button"
                  disabled={rescheduling}
                  onClick={() => { setShowRescheduleModal(false); setSessionToReschedule(null); }}
                  className="btn btn-secondary"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={rescheduling}
                  className="btn btn-primary"
                >
                  {rescheduling ? 'Updating Schedule...' : 'Save New Schedule'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Confirm Delete Interview Session */}
      {showDeleteModal && sessionToDelete && (
        <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(31, 29, 36, 0.75)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50, backdropFilter: 'blur(4px)' }}>
          <div className="card" style={{ width: 460, maxWidth: '90%', border: '1px solid var(--border-light)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
              <div style={{ padding: 8, borderRadius: '50%', backgroundColor: '#fee2e2', color: 'var(--danger)' }}>
                <Trash2 size={20} />
              </div>
              <h3 style={{ fontSize: 18, fontWeight: 700, margin: 0, color: 'var(--danger)' }}>
                Confirm Session Deletion
              </h3>
            </div>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.5, marginBottom: 18 }}>
              Are you sure you want to delete the scheduled interview for <strong>{sessionToDelete.candidate_name}</strong> for the <strong>{sessionToDelete.job_title}</strong> position?
              <br /><br />
              <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>
                This removes the interview schedule from the decision queue. The candidate account and uploaded resume will remain safe and unaffected.
              </span>
            </p>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
              <button
                type="button"
                disabled={deleting}
                onClick={() => { setShowDeleteModal(false); setSessionToDelete(null); }}
                className="btn btn-secondary"
              >
                Keep Session
              </button>
              <button
                type="button"
                disabled={deleting}
                onClick={handleDeleteSession}
                className="btn btn-primary"
                style={{ backgroundColor: 'var(--danger)', borderColor: 'var(--danger)' }}
              >
                {deleting ? 'Deleting...' : 'Delete Interview'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
