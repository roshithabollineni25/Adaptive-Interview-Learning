import React, { useEffect, useState, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { apiClient } from '../api/client';
import type { CandidateInterviewView } from '../types';
import { 
  Send, Shield, AlertCircle, CheckCircle, 
  Camera, Lock, Clock, AlertTriangle 
} from 'lucide-react';

export const CandidateInterviewExperience: React.FC = () => {
  const { token } = useParams<{ token: string }>();
  const [interview, setInterview] = useState<CandidateInterviewView | null>(null);
  const [answer, setAnswer] = useState('');
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  
  // Verification Gate state
  const [verifyingIdentity, setVerifyingIdentity] = useState(false);
  const [verificationError, setVerificationError] = useState<string | null>(null);
  const [verificationSuccess, setVerificationSuccess] = useState<string | null>(null);
  const [consentAccepted, setConsentAccepted] = useState(false);

  // Live camera stream for verification probe and continuous integrity
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [cameraActive, setCameraActive] = useState(false);
  const [integrityWarning, setIntegrityWarning] = useState<string | null>(null);

  const loadInterview = async () => {
    if (!token) return;
    try {
      setLoading(true);
      const data = await apiClient.getCandidateInterview(token);
      setInterview(data);
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Invalid or expired interview session link');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadInterview();
  }, [token]);

  // Start webcam stream for candidate verification
  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ 
        video: { width: 640, height: 480 }, 
        audio: true 
      });
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        setCameraActive(true);
      }
    } catch (err) {
      setVerificationError('Unable to access webcam. Camera access is mandatory for identity verification.');
    }
  };

  useEffect(() => {
    if (interview && !interview.identity_verified && interview.time_window_check?.allowed) {
      startCamera();
    }
    return () => {
      if (videoRef.current && videoRef.current.srcObject) {
        const stream = videoRef.current.srcObject as MediaStream;
        stream.getTracks().forEach(t => t.stop());
      }
    };
  }, [interview?.identity_verified, interview?.time_window_check?.allowed]);

  // Run Real Biometric Identity Verification Gate
  const handleVerifyIdentity = async () => {
    if (!token || !videoRef.current || !canvasRef.current) return;
    const video = videoRef.current;
    const canvas = canvasRef.current;

    // Check if video stream is active and has valid dimensions
    if (video.readyState < 2 || video.videoWidth === 0 || video.videoHeight === 0) {
      setVerificationError('Camera feed is still initializing. Please wait a second for the stream to stabilize.');
      return;
    }

    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;

    const ctx = canvas.getContext('2d');
    if (!ctx) {
      setVerificationError('Failed to capture video frame from browser canvas.');
      return;
    }

    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    const probeFrameBase64 = canvas.toDataURL('image/jpeg', 0.90);

    try {
      setVerifyingIdentity(true);
      setVerificationError(null);
      setVerificationSuccess(null);

      const res = await apiClient.verifyIdentityProbe(token, probeFrameBase64);
      if (res.verified) {
        setVerificationSuccess(res.message);
        setTimeout(() => {
          loadInterview();
        }, 1200);
      } else {
        setVerificationError(res.message || 'Identity verification failed. Please align your face clearly with the camera.');
      }
    } catch (err: any) {
      setVerificationError(err?.response?.data?.detail || err?.message || 'Failed to complete identity verification.');
    } finally {
      setVerifyingIdentity(false);
    }
  };

  // Integrity Proctor Event Listeners (Tab switch, Blur, Paste, Camera interruption)
  useEffect(() => {
    if (!token || !interview?.identity_verified || interview?.status === 'completed') return;

    const handleVisibility = () => {
      if (document.hidden) {
        setIntegrityWarning('Tab switch detected! Maintaining active focus on this window is monitored.');
        apiClient.logIntegrityEvent(token, 'tab_switch', 'medium', 1.0, {
          reason: 'Candidate navigated away from active interview tab'
        });
      }
    };

    const handleBlur = () => {
      apiClient.logIntegrityEvent(token, 'window_blur', 'low', 1.0, {});
    };

    const handlePaste = () => {
      setIntegrityWarning('Paste action detected and recorded in session telemetry.');
      apiClient.logIntegrityEvent(token, 'paste_detected', 'medium', 1.0, {});
    };

    document.addEventListener('visibilitychange', handleVisibility);
    window.addEventListener('blur', handleBlur);
    window.addEventListener('paste', handlePaste);

    return () => {
      document.removeEventListener('visibilitychange', handleVisibility);
      window.removeEventListener('blur', handleBlur);
      window.removeEventListener('paste', handlePaste);
    };
  }, [token, interview?.identity_verified, interview?.status]);

  const handleSubmitAnswer = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !answer.trim()) return;

    try {
      setSubmitting(true);
      setIntegrityWarning(null);
      await apiClient.submitAnswer(token, answer);
      setAnswer('');
      await loadInterview();
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to submit response');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div style={{ maxWidth: 700, margin: '80px auto', textAlign: 'center', color: 'var(--text-muted)' }}>
        Loading interview session gateway...
      </div>
    );
  }

  if (!interview) {
    return (
      <div style={{ maxWidth: 600, margin: '80px auto', padding: '0 20px', textAlign: 'center' }}>
        <div className="card" style={{ padding: 40 }}>
          <AlertTriangle size={40} color="var(--danger)" style={{ marginBottom: 16 }} />
          <h2 style={{ fontSize: 20, color: 'var(--danger)', marginBottom: 8 }}>Interview Link Expired or Invalid</h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: 14 }}>
            Please check the link provided by your recruiter or contact the hiring team.
          </p>
        </div>
      </div>
    );
  }

  // Time Restriction Check Gate
  if (!interview.time_window_check?.allowed && interview.status !== 'completed') {
    return (
      <div style={{ maxWidth: 680, margin: '80px auto', padding: '0 20px' }}>
        <div className="card" style={{ padding: 40, textAlign: 'center' }}>
          <div style={{ width: 48, height: 48, borderRadius: '50%', backgroundColor: 'var(--sage-subtle)', color: 'var(--sage-accent)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', marginBottom: 16 }}>
            <Clock size={26} />
          </div>
          <h2 style={{ fontSize: 22, fontWeight: 700, marginBottom: 10 }}>Interview Window Restricted</h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: 15, lineHeight: 1.6, maxWidth: 520, margin: '0 auto 20px' }}>
            {interview.time_window_check.reason}
          </p>
          {interview.scheduled_start && (
            <div style={{ padding: 14, backgroundColor: 'var(--bg-subtle)', borderRadius: 8, display: 'inline-block', fontSize: 13, color: 'var(--text-primary)', border: '1px solid var(--border-light)' }}>
              Confirmed Scheduled Start: <strong>{new Date(interview.scheduled_start).toLocaleString()}</strong>
            </div>
          )}
        </div>
      </div>
    );
  }

  // Interview Completed Screen
  if (interview.status === 'completed') {
    return (
      <div style={{ maxWidth: 650, margin: '80px auto', padding: '0 20px', textAlign: 'center' }}>
        <div className="card" style={{ padding: 48, border: '1px solid var(--sage-border)' }}>
          <div style={{ display: 'inline-flex', padding: 16, borderRadius: '50%', backgroundColor: 'var(--sage-subtle)', color: 'var(--sage-accent)', marginBottom: 20 }}>
            <CheckCircle size={44} />
          </div>
          <h2 style={{ fontSize: 26, fontWeight: 700, marginBottom: 10, color: 'var(--text-primary)' }}>Interview Complete</h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: 15, marginBottom: 8 }}>
            Thank you, <strong>{interview.candidate_name}</strong>.
          </p>
          <p style={{ color: 'var(--text-muted)', fontSize: 14, lineHeight: 1.6, maxWidth: 480, margin: '0 auto 24px' }}>
            Your adaptive technical interview for <strong>{interview.job_title}</strong> has ended. All responses and evidence assessments have been submitted to the human recruiting committee.
          </p>
          <div style={{ padding: 14, borderRadius: 8, backgroundColor: 'var(--bg-subtle)', border: '1px solid var(--border-light)', fontSize: 13, color: 'var(--text-muted)' }}>
            You may now safely close this window. You will hear directly from the recruiting team regarding final decisions.
          </div>
        </div>
      </div>
    );
  }

  // Mandatory Pre-Interview Identity Verification Gate
  if (!interview.identity_verified) {
    return (
      <div style={{ maxWidth: 780, margin: '40px auto', padding: '0 20px' }}>
        <div className="card" style={{ padding: 36 }}>
          <div style={{ borderBottom: '1px solid var(--border-light)', paddingBottom: 18, marginBottom: 24 }}>
            <span className="badge badge-info" style={{ marginBottom: 8 }}>Mandatory Identity Verification Gate</span>
            <h1 style={{ fontSize: 24, fontWeight: 700, color: 'var(--text-primary)' }}>{interview.job_title} Technical Interview</h1>
            <p style={{ color: 'var(--text-secondary)', fontSize: 14 }}>
              Candidate: <strong>{interview.candidate_name}</strong>
            </p>
          </div>

          {/* AI Disclosure */}
          <div style={{ padding: 16, backgroundColor: 'var(--bg-subtle)', borderRadius: 8, border: '1px solid var(--border-light)', marginBottom: 24 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6, color: 'var(--sage-accent)' }}>
              <Lock size={16} />
              <strong style={{ fontSize: 14 }}>AI Assessment Disclosure & Consent</strong>
            </div>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
              This interview uses an adaptive AI assessment engine to analyze technical depth and generate follow-up questions. Final hiring authority remains exclusively with human recruiters.
            </p>
          </div>

          {/* Camera Frame Preview for Biometric Verification */}
          <div style={{ marginBottom: 24 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
              <span style={{ fontSize: 14, fontWeight: 600 }}>Biometric Face Match & Liveness Check</span>
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Position face in center frame</span>
            </div>

            <div style={{ position: 'relative', width: '100%', height: 320, backgroundColor: '#000000', borderRadius: 10, overflow: 'hidden', marginBottom: 16 }}>
              <video ref={videoRef} autoPlay playsInline muted style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
              <canvas ref={canvasRef} style={{ display: 'none' }} />

              <div style={{ 
                position: 'absolute', 
                top: '50%', 
                left: '50%', 
                transform: 'translate(-50%, -50%)', 
                width: 170, 
                height: 220, 
                border: '2px dashed rgba(255, 255, 255, 0.7)', 
                borderRadius: '50%',
                pointerEvents: 'none'
              }}></div>
            </div>

            {verificationError && (
              <div style={{ padding: 12, borderRadius: 8, backgroundColor: '#ffebee', border: '1px solid #ffcdd2', color: 'var(--danger)', fontSize: 13, marginBottom: 16, display: 'flex', alignItems: 'center', gap: 10 }}>
                <AlertCircle size={18} /> {verificationError}
              </div>
            )}

            {verificationSuccess && (
              <div style={{ padding: 12, borderRadius: 8, backgroundColor: '#e8f5e9', border: '1px solid #c8e6c9', color: 'var(--success)', fontSize: 13, marginBottom: 16, display: 'flex', alignItems: 'center', gap: 10 }}>
                <CheckCircle size={18} /> {verificationSuccess}
              </div>
            )}

            {!interview.has_enrolled_reference && (
              <div style={{ padding: 12, borderRadius: 8, backgroundColor: '#fff3e0', border: '1px solid #ffe0b2', color: 'var(--warning)', fontSize: 13, marginBottom: 16 }}>
                <strong>No Enrolled Biometric Reference:</strong> Please visit the <Link to="/candidate/dashboard" style={{ textDecoration: 'underline', fontWeight: 600 }}>Candidate Portal</Link> to enroll your reference photo before verifying.
              </div>
            )}

            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10, marginBottom: 20 }}>
              <input
                type="checkbox"
                id="consentCheck"
                checked={consentAccepted}
                onChange={(e) => setConsentAccepted(e.target.checked)}
                style={{ marginTop: 4, cursor: 'pointer', accentColor: 'var(--sage-accent)' }}
              />
              <label htmlFor="consentCheck" style={{ fontSize: 13, color: 'var(--text-secondary)', cursor: 'pointer', lineHeight: 1.5 }}>
                I verify that I am {interview.candidate_name}, and I consent to biometric identity verification and active session telemetry.
              </label>
            </div>

            <button
              onClick={handleVerifyIdentity}
              disabled={verifyingIdentity || !consentAccepted || !cameraActive || !interview.has_enrolled_reference}
              className="btn btn-primary"
              style={{ width: '100%', padding: '12px', fontSize: 15, opacity: (!consentAccepted || !cameraActive || !interview.has_enrolled_reference) ? 0.5 : 1 }}
            >
              <Camera size={18} /> {verifyingIdentity ? 'Verifying Identity Against Enrolled Reference...' : 'Verify Identity & Enter Interview'}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Active Adaptive Question Responder (No recruiter scores, no chatbot, calm UI)
  return (
    <div style={{ maxWidth: 840, margin: '40px auto', padding: '0 24px' }}>
      {/* Session Top Bar */}
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center', 
        marginBottom: 24,
        paddingBottom: 16,
        borderBottom: '1px solid var(--border-light)'
      }}>
        <div>
          <span style={{ fontSize: 12, color: 'var(--sage-accent)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Technical Assessment
          </span>
          <h1 style={{ fontSize: 20, fontWeight: 700, color: 'var(--text-primary)' }}>{interview.job_title}</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: 13 }}>Candidate: {interview.candidate_name}</p>
        </div>

        <div style={{ 
          display: 'flex', 
          alignItems: 'center', 
          gap: 6, 
          fontSize: 12, 
          color: 'var(--sage-accent)', 
          backgroundColor: 'var(--sage-subtle)', 
          padding: '6px 14px', 
          borderRadius: 9999,
          border: '1px solid var(--sage-border)'
        }}>
          <Shield size={14} /> Identity Verified & Protected
        </div>
      </div>

      {integrityWarning && (
        <div style={{ 
          marginBottom: 20, 
          padding: '12px 16px', 
          borderRadius: 8, 
          backgroundColor: '#fff3e0', 
          border: '1px solid #ffe0b2', 
          color: 'var(--warning)', 
          fontSize: 13, 
          display: 'flex', 
          alignItems: 'center', 
          gap: 10 
        }}>
          <AlertCircle size={18} /> {integrityWarning}
        </div>
      )}

      {/* Active Question Box */}
      {interview.active_question ? (
        <div className="card" style={{ padding: 32 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <span style={{ fontSize: 13, color: 'var(--sage-accent)', fontWeight: 600 }}>
              Question {interview.active_question.order_index} • Focus: {interview.active_question.competency_tested}
            </span>
            <span className="badge badge-info">
              {interview.active_question.difficulty_level} Difficulty
            </span>
          </div>

          <h2 style={{ fontSize: 19, fontWeight: 600, lineHeight: 1.5, marginBottom: 24, color: 'var(--text-primary)' }}>
            {interview.active_question.question_text}
          </h2>

          <form onSubmit={handleSubmitAnswer} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div>
              <label style={{ display: 'block', fontSize: 13, color: 'var(--text-secondary)', marginBottom: 8 }}>
                Your Answer (Explain your methodology, system architecture or technical rationale in detail):
              </label>
              <textarea
                required
                rows={9}
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                placeholder="Write your comprehensive technical response here..."
                style={{ width: '100%', resize: 'vertical', lineHeight: 1.5 }}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: 8 }}>
              <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>
                Questions completed: {interview.total_questions_completed}
              </span>
              <button 
                type="submit" 
                disabled={submitting || !answer.trim()} 
                className="btn btn-primary"
                style={{ padding: '10px 22px' }}
              >
                <Send size={16} /> {submitting ? 'Submitting & Evaluating...' : 'Submit Answer & Proceed'}
              </button>
            </div>
          </form>
        </div>
      ) : (
        <div className="card" style={{ textAlign: 'center', padding: 48, color: 'var(--text-muted)' }}>
          Evaluating previous response and adapting trajectory...
        </div>
      )}
    </div>
  );
};
