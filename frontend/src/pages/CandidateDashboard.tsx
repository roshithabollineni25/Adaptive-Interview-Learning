import React, { useEffect, useState, useRef } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { apiClient } from '../api/client';
import type { CandidateApplication, CandidateInterviewScheduleItem } from '../types';
import { 
  FileText, Upload, Calendar, Camera, CheckCircle2, 
  AlertCircle, LogOut, ArrowRight, CheckCircle, Clock, XCircle 
} from 'lucide-react';

export const CandidateDashboard: React.FC = () => {
  const [profile, setProfile] = useState<CandidateApplication | null>(null);
  const [interviews, setInterviews] = useState<CandidateInterviewScheduleItem[]>([]);
  const [loading, setLoading] = useState(true);

  // Application submission form
  const [targetRole, setTargetRole] = useState('');
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [submittingApp, setSubmittingApp] = useState(false);
  const [appSuccess, setAppSuccess] = useState<string | null>(null);

  // Biometric reference enrollment
  const [showCameraModal, setShowCameraModal] = useState(false);
  const [cameraStreaming, setCameraStreaming] = useState(false);
  const [enrollingFace, setEnrollingFace] = useState(false);
  const [enrollMsg, setEnrollMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  const navigate = useNavigate();

  const loadData = async () => {
    try {
      setLoading(true);
      const [profData, intData] = await Promise.all([
        apiClient.getCandidateProfile().catch((err) => {
          if (err?.response?.status === 401 || err?.response?.status === 403) {
            throw err;
          }
          console.error("Failed to load candidate profile", err);
          return null;
        }),
        apiClient.getCandidateInterviews().catch((err) => {
          if (err?.response?.status === 401 || err?.response?.status === 403) {
            throw err;
          }
          console.error("Failed to load candidate interviews", err);
          return [];
        })
      ]);
      if (profData) {
        setProfile(profData);
        if (profData.target_role) setTargetRole(profData.target_role);
      }
      setInterviews(intData || []);
    } catch (err: any) {
      if (err?.response?.status === 401 || err?.response?.status === 403) {
        navigate('/candidate/login');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleApplicationSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!resumeFile) return;

    try {
      setSubmittingApp(true);
      setAppSuccess(null);
      const fd = new FormData();
      fd.append('target_role', targetRole);
      fd.append('file', resumeFile);

      const res = await apiClient.submitCandidateApplication(fd);
      setAppSuccess(res.message);
      setResumeFile(null);
      await loadData();
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to submit application');
    } finally {
      setSubmittingApp(false);
    }
  };

  const startCamera = async () => {
    setShowCameraModal(true);
    setEnrollMsg(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 }, audio: false });
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        setCameraStreaming(true);
      }
    } catch (err) {
      setEnrollMsg({ type: 'error', text: 'Unable to access webcam. Please allow camera permissions in your browser.' });
    }
  };

  const stopCamera = () => {
    if (videoRef.current && videoRef.current.srcObject) {
      const stream = videoRef.current.srcObject as MediaStream;
      stream.getTracks().forEach(t => t.stop());
      videoRef.current.srcObject = null;
    }
    setCameraStreaming(false);
    setShowCameraModal(false);
  };

  const captureAndEnroll = async () => {
    if (!videoRef.current || !canvasRef.current) return;
    const video = videoRef.current;
    const canvas = canvasRef.current;

    // Check if video stream is active and has valid dimensions
    if (video.readyState < 2 || video.videoWidth === 0 || video.videoHeight === 0) {
      setEnrollMsg({ 
        type: 'error', 
        text: 'Camera stream is still initializing. Please wait a second until the preview appears and try again.' 
      });
      return;
    }

    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;

    const ctx = canvas.getContext('2d');
    if (!ctx) {
      setEnrollMsg({ type: 'error', text: 'Browser canvas context could not be created.' });
      return;
    }

    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    const base64Image = canvas.toDataURL('image/jpeg', 0.90);

    try {
      setEnrollingFace(true);
      setEnrollMsg(null);
      const res = await apiClient.enrollFace(base64Image);
      setEnrollMsg({ 
        type: 'success', 
        text: res.message || 'Biometric reference successfully enrolled.' 
      });
      setTimeout(() => {
        stopCamera();
        loadData();
      }, 1500);
    } catch (err: any) {
      const errMsg = err?.response?.data?.detail || err?.message || 'Failed to verify face in captured frame.';
      setEnrollMsg({ type: 'error', text: errMsg });
    } finally {
      setEnrollingFace(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    navigate('/candidate/login');
  };

  if (loading && !profile) {
    return (
      <div style={{ maxWidth: 900, margin: '80px auto', textAlign: 'center', color: 'var(--text-muted)' }}>
        Loading Candidate Portal workspace...
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 1080, margin: '40px auto', padding: '0 24px' }}>
      {/* Top Header */}
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center', 
        marginBottom: 32,
        borderBottom: '1px solid var(--border-light)',
        paddingBottom: 20
      }}>
        <div>
          <span style={{ fontSize: 12, color: 'var(--sage-accent)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Candidate Portal
          </span>
          <h1 style={{ fontSize: 26, fontWeight: 700, color: 'var(--text-primary)' }}>Welcome, {profile?.full_name}</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: 14 }}>{profile?.email}</p>
        </div>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <Link to="/" className="btn btn-secondary" style={{ fontSize: 13, padding: '7px 14px' }}>
            Public Landing
          </Link>
          <button onClick={handleLogout} className="btn btn-secondary" style={{ fontSize: 13, padding: '7px 14px' }}>
            <LogOut size={14} /> Logout
          </button>
        </div>
      </div>

      {/* Grid: Application Status & Biometric Enrollment */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: 24, marginBottom: 32 }}>
        {/* Section 1: Target Role & Resume Application */}
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
            <FileText size={20} color="var(--sage-accent)" />
            <h2 style={{ fontSize: 18, fontWeight: 700 }}>Job Role & Resume Submission</h2>
          </div>

          {appSuccess && (
            <div style={{ padding: 12, borderRadius: 8, backgroundColor: '#e8f5e9', border: '1px solid #c8e6c9', color: 'var(--success)', fontSize: 13, marginBottom: 16 }}>
              {appSuccess}
            </div>
          )}

          {profile?.resume_filename ? (
            <div style={{ padding: 16, backgroundColor: 'var(--bg-subtle)', borderRadius: 8, border: '1px solid var(--border-light)', marginBottom: 20 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>Applied Position:</span>
                <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{profile.target_role || 'Not specified'}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>Uploaded Resume:</span>
                <span style={{ fontWeight: 600, color: 'var(--sage-accent)' }}>{profile.resume_filename}</span>
              </div>
              <div style={{ borderTop: '1px solid var(--border-light)', paddingTop: 10 }}>
                <span style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>Extracted Skills Profile:</span>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {profile.extracted_skills.map((sk, idx) => (
                    <span key={idx} style={{ backgroundColor: '#ffffff', border: '1px solid var(--border-light)', padding: '2px 8px', borderRadius: 4, fontSize: 11 }}>
                      {sk}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 16 }}>
              Submit your target role and resume to begin your interview scheduling process.
            </p>
          )}

          <form onSubmit={handleApplicationSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div>
              <label style={{ display: 'block', fontSize: 13, marginBottom: 6, color: 'var(--text-secondary)' }}>Target Job Role</label>
              <input
                type="text"
                required
                style={{ width: '100%' }}
                value={targetRole}
                onChange={(e) => setTargetRole(e.target.value)}
                placeholder="e.g. Senior Software Engineer"
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: 13, marginBottom: 6, color: 'var(--text-secondary)' }}>
                {profile?.resume_filename ? 'Update Resume Document (PDF / DOCX)' : 'Upload Resume (PDF / DOCX)'}
              </label>
              <input
                type="file"
                required={!profile?.resume_filename}
                accept=".pdf,.docx,.txt"
                onChange={(e) => setResumeFile(e.target.files?.[0] || null)}
                style={{ width: '100%' }}
              />
            </div>

            <button type="submit" disabled={submittingApp} className="btn btn-primary" style={{ alignSelf: 'flex-start', padding: '10px 20px' }}>
              <Upload size={16} /> {submittingApp ? 'Processing Resume...' : profile?.resume_filename ? 'Update Application' : 'Submit Application'}
            </button>
          </form>
        </div>

        {/* Section 2: Biometric Identity Enrollment Gate */}
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
            <Camera size={20} color="var(--sage-accent)" />
            <h2 style={{ fontSize: 18, fontWeight: 700 }}>Identity Verification Enrollment</h2>
          </div>

          <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: 18 }}>
            Before your scheduled technical interview, ethical identity verification requires enrolling a verified live reference photo with your consent.
          </p>

          <div style={{ padding: 18, backgroundColor: 'var(--bg-subtle)', borderRadius: 8, border: '1px solid var(--border-light)', marginBottom: 20 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
              {profile?.has_enrolled_face ? (
                <>
                  <CheckCircle2 size={20} color="var(--success)" />
                  <span style={{ fontWeight: 600, color: 'var(--success)' }}>Biometric Reference Enrolled</span>
                </>
              ) : (
                <>
                  <AlertCircle size={20} color="var(--warning)" />
                  <span style={{ fontWeight: 600, color: 'var(--warning)' }}>Enrollment Required Before Interview</span>
                </>
              )}
            </div>
            <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>
              {profile?.has_enrolled_face 
                ? `Enrolled on ${new Date(profile.enrolled_at || '').toLocaleDateString()}. Used for pre-interview biometric match.`
                : 'Your camera will verify a single face with liveness and focus checks.'}
            </p>
          </div>

          <button onClick={startCamera} className="btn btn-secondary" style={{ width: '100%', padding: '11px' }}>
            <Camera size={16} /> {profile?.has_enrolled_face ? 'Re-enroll Reference Photo' : 'Enroll Camera Identity Reference'}
          </button>
        </div>
      </div>

      {/* Section 3: Scheduled Interviews Table */}
      <div className="card">
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 18 }}>
          <Calendar size={20} color="var(--sage-accent)" />
          <h2 style={{ fontSize: 18, fontWeight: 700 }}>Your Scheduled Interviews</h2>
        </div>

        {interviews.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '36px 20px', color: 'var(--text-muted)' }}>
            <p style={{ fontSize: 14 }}>No interviews scheduled yet.</p>
            <p style={{ fontSize: 12, marginTop: 4 }}>
              Once a recruiter reviews your resume and schedules a session, your date, time, and access link will appear here.
            </p>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border-light)', textAlign: 'left', color: 'var(--text-muted)' }}>
                  <th style={{ padding: '12px 10px' }}>Position</th>
                  <th style={{ padding: '12px 10px' }}>Scheduled Start</th>
                  <th style={{ padding: '12px 10px' }}>Window Status</th>
                  <th style={{ padding: '12px 10px' }}>Identity Status</th>
                  <th style={{ padding: '12px 10px' }}>Hiring Decision</th>
                  <th style={{ padding: '12px 10px' }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {interviews.map((item) => (
                  <tr key={item.id} style={{ borderBottom: '1px solid var(--border-light)' }}>
                    <td style={{ padding: '14px 10px', fontWeight: 600 }}>
                      {item.job_title}
                      {item.candidate_feedback && (
                        <div style={{ marginTop: 6, fontSize: 12, color: 'var(--text-secondary)', background: 'var(--bg-subtle)', padding: '6px 10px', borderRadius: 6, border: '1px solid var(--border-light)', fontWeight: 400 }}>
                          <span style={{ fontWeight: 600, color: 'var(--sage-accent)' }}>Feedback: </span>
                          {item.candidate_feedback}
                        </div>
                      )}
                    </td>
                    <td style={{ padding: '14px 10px' }}>
                      {item.scheduled_start 
                        ? new Date(item.scheduled_start).toLocaleString() 
                        : <span style={{ color: 'var(--text-muted)' }}>To be scheduled</span>}
                    </td>
                    <td style={{ padding: '14px 10px' }}>
                      <span className={`badge ${
                        item.window_status === 'open' ? 'badge-success' : item.window_status === 'too_early' ? 'badge-info' : 'badge-warning'
                      }`}>
                        {item.window_status === 'open' ? 'Active Window Open' : item.window_status === 'too_early' ? 'Opens 15m Prior' : item.window_status}
                      </span>
                    </td>
                    <td style={{ padding: '14px 10px' }}>
                      {item.identity_verified ? (
                        <span className="badge badge-success">Verified</span>
                      ) : (
                        <span className="badge badge-warning">Verification Gate Pending</span>
                      )}
                    </td>
                    <td style={{ padding: '14px 10px' }}>
                      {item.decision_status === 'Selected' ? (
                        <span className="badge badge-success" style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontWeight: 700, padding: '5px 10px' }}>
                          <CheckCircle size={13} /> Selected
                        </span>
                      ) : item.decision_status === 'Rejected' ? (
                        <span className="badge badge-danger" style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontWeight: 600, padding: '5px 10px' }}>
                          <XCircle size={13} /> Rejected
                        </span>
                      ) : item.decision_status === 'On Hold' ? (
                        <span className="badge badge-warning" style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '5px 10px' }}>
                          <Clock size={13} /> On Hold
                        </span>
                      ) : (
                        <span className="badge badge-info" style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '5px 10px' }}>
                          <Clock size={13} /> Decision Pending
                        </span>
                      )}
                      {item.decision_at && (
                        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
                          {new Date(item.decision_at).toLocaleDateString()}
                        </div>
                      )}
                    </td>
                    <td style={{ padding: '14px 10px' }}>
                      {item.status === 'completed' ? (
                        <span style={{ fontSize: 12, color: 'var(--text-muted)', fontWeight: 500 }}>
                          Interview Completed
                        </span>
                      ) : (
                        <Link 
                          to={item.interview_url} 
                          className={`btn ${item.window_status === 'open' ? 'btn-primary' : 'btn-secondary'}`}
                          style={{ padding: '6px 14px', fontSize: 12 }}
                        >
                          Enter Gateway <ArrowRight size={12} />
                        </Link>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Modal: Webcam Face Enrollment */}
      {showCameraModal && (
        <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(31, 29, 36, 0.75)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 60, backdropFilter: 'blur(4px)' }}>
          <div className="card" style={{ width: 560, maxWidth: '92%', padding: 28 }}>
            <h3 style={{ fontSize: 18, fontWeight: 700, marginBottom: 6 }}>Biometric Reference Enrollment</h3>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 16 }}>
              Center your face within the frame. Ensure good lighting and remove sunglasses or obscuring accessories.
            </p>

            {enrollMsg && (
              <div style={{ 
                padding: 12, 
                borderRadius: 8, 
                backgroundColor: enrollMsg.type === 'success' ? '#e8f5e9' : '#ffebee', 
                border: `1px solid ${enrollMsg.type === 'success' ? '#c8e6c9' : '#ffcdd2'}`, 
                color: enrollMsg.type === 'success' ? 'var(--success)' : 'var(--danger)', 
                fontSize: 13, 
                marginBottom: 16 
              }}>
                {enrollMsg.text}
              </div>
            )}

            <div style={{ position: 'relative', width: '100%', height: 320, backgroundColor: '#000000', borderRadius: 10, overflow: 'hidden', marginBottom: 20 }}>
              <video ref={videoRef} autoPlay playsInline muted style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
              <canvas ref={canvasRef} style={{ display: 'none' }} />
              
              {/* Overlay oval guide */}
              <div style={{ 
                position: 'absolute', 
                top: '50%', 
                left: '50%', 
                transform: 'translate(-50%, -50%)', 
                width: 180, 
                height: 230, 
                border: '2px dashed rgba(255, 255, 255, 0.7)', 
                borderRadius: '50%',
                pointerEvents: 'none'
              }}></div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12 }}>
              <button type="button" onClick={stopCamera} className="btn btn-secondary">
                Cancel
              </button>
              <button 
                type="button" 
                onClick={captureAndEnroll} 
                disabled={enrollingFace || !cameraStreaming} 
                className="btn btn-primary"
              >
                <Camera size={16} /> {enrollingFace ? 'Analyzing Biometrics...' : 'Capture Reference Photo'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
