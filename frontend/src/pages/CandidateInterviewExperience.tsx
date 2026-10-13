import React, { useEffect, useState, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { apiClient } from '../api/client';
import type { CandidateInterviewView } from '../types';
import { 
  Send, Shield, AlertCircle, CheckCircle, 
  Camera, Lock, Clock, AlertTriangle,
  Volume2, VolumeX, Mic, MicOff, IdCard
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
  const [verificationDetails, setVerificationDetails] = useState<any | null>(null);
  const [consentAccepted, setConsentAccepted] = useState(false);
  const [idCardCaptured, setIdCardCaptured] = useState<string | null>(null);

  // Live camera stream for verification probe and continuous integrity
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [cameraActive, setCameraActive] = useState(false);
  const [integrityWarning, setIntegrityWarning] = useState<string | null>(null);
  const [tabSwitchesCount, setTabSwitchesCount] = useState(0);
  const [terminatedNotice, setTerminatedNotice] = useState<string | null>(null);

  // Voice AI Features
  const [isSpeakingQuestion, setIsSpeakingQuestion] = useState(false);
  const [speechSynthesisSupported, setSpeechSynthesisSupported] = useState(true);
  const [isListeningMic, setIsListeningMic] = useState(false);
  const [speechRecognitionSupported, setSpeechRecognitionSupported] = useState(false);
  const recognitionRef = useRef<any | null>(null);

  // State for question types & answer modes
  const [selectedOption, setSelectedOption] = useState<string>('');
  const [fillBlankAnswer, setFillBlankAnswer] = useState<string>('');
  const [answerMode, setAnswerMode] = useState<'typed' | 'voice'>('typed');
  const [voiceRecordedText, setVoiceRecordedText] = useState<string>('');
  const [voiceStatusMessage, setVoiceStatusMessage] = useState<string | null>(null);

  // Spoken Question Ref to prevent repetitive audio reading on reloads
  const spokenQuestionIdRef = useRef<number | null>(null);

  // Fullscreen and Continuous Webcam Proctoring
  const [isFullscreen, setIsFullscreen] = useState(false);
  const continuousProctorIntervalRef = useRef<any | null>(null);

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
    // Check speech synthesis support
    if (typeof window !== 'undefined' && !('speechSynthesis' in window)) {
      setSpeechSynthesisSupported(false);
    }

    // Check speech recognition support
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (SpeechRecognition) {
      setSpeechRecognitionSupported(true);
      const recog = new SpeechRecognition();
      recog.continuous = true;
      recog.interimResults = true;
      recog.lang = 'en-US';

      recog.onresult = (event: any) => {
        let transcript = '';
        for (let i = 0; i < event.results.length; i++) {
          transcript += event.results[i][0].transcript + ' ';
        }
        const trimmed = transcript.trim();
        if (trimmed) {
          setVoiceRecordedText(trimmed);
        }
      };

      recog.onerror = (event: any) => {
        console.warn('Speech recognition error:', event.error);
        setIsListeningMic(false);
        setVoiceStatusMessage('Microphone speech recognition encountered an error. Please try again or switch to typed answer.');
      };

      recog.onend = () => {
        setIsListeningMic(false);
      };

      recognitionRef.current = recog;
    }
  }, [token]);

  // Read question aloud via Text-to-Speech ONLY ONCE per active question
  useEffect(() => {
    const activeQ = interview?.active_question;
    if (
      activeQ?.id &&
      activeQ.question_text &&
      typeof window !== 'undefined' &&
      'speechSynthesis' in window &&
      spokenQuestionIdRef.current !== activeQ.id
    ) {
      spokenQuestionIdRef.current = activeQ.id;
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(activeQ.question_text);
      utterance.rate = 0.95;
      utterance.pitch = 1.0;
      utterance.onstart = () => setIsSpeakingQuestion(true);
      utterance.onend = () => setIsSpeakingQuestion(false);
      utterance.onerror = () => setIsSpeakingQuestion(false);
      window.speechSynthesis.speak(utterance);
    }
  }, [interview?.active_question?.id]);

  const toggleSpeakQuestion = () => {
    if (!interview?.active_question?.question_text || typeof window === 'undefined' || !('speechSynthesis' in window)) return;
    if (isSpeakingQuestion) {
      window.speechSynthesis.cancel();
      setIsSpeakingQuestion(false);
    } else {
      const utterance = new SpeechSynthesisUtterance(interview.active_question.question_text);
      utterance.rate = 0.95;
      utterance.onstart = () => setIsSpeakingQuestion(true);
      utterance.onend = () => setIsSpeakingQuestion(false);
      utterance.onerror = () => setIsSpeakingQuestion(false);
      window.speechSynthesis.speak(utterance);
    }
  };

  const toggleListening = () => {
    if (!recognitionRef.current) return;
    if (isListeningMic) {
      recognitionRef.current.stop();
      setIsListeningMic(false);
      setVoiceStatusMessage('Voice recording finished. You can review and submit or re-record.');
    } else {
      try {
        setVoiceStatusMessage(null);
        recognitionRef.current.start();
        setIsListeningMic(true);
      } catch (e) {
        console.warn('Could not start recognition:', e);
      }
    }
  };

  // Start webcam stream for candidate verification and continuous proctoring
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
      setVerificationError('Unable to access webcam. Camera access is mandatory for identity verification and continuous integrity monitoring.');
    }
  };

  useEffect(() => {
    if (interview && interview.time_window_check?.allowed && interview.status !== 'completed') {
      startCamera();
    }
    return () => {
      if (videoRef.current && videoRef.current.srcObject) {
        const stream = videoRef.current.srcObject as MediaStream;
        stream.getTracks().forEach(t => t.stop());
      }
    };
  }, [interview?.identity_verified, interview?.time_window_check?.allowed, interview?.status]);

  // Capture ID Card frame from camera
  const handleCaptureIdCard = () => {
    if (!videoRef.current || !canvasRef.current) return;
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (video.videoWidth === 0) return;
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
    const ctx = canvas.getContext('2d');
    if (ctx) {
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      const b64 = canvas.toDataURL('image/jpeg', 0.90);
      setIdCardCaptured(b64);
    }
  };

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

      const res = await apiClient.verifyIdentityProbe(token, probeFrameBase64, idCardCaptured || undefined);
      if (res.verified) {
        setVerificationSuccess(res.message);
        setVerificationDetails(res.verification_details);
        setTimeout(() => {
          loadInterview();
        }, 1500);
      } else {
        setVerificationError(res.message || 'Identity verification failed. Please align your face clearly with the camera.');
      }
    } catch (err: any) {
      setVerificationError(err?.response?.data?.detail || err?.message || 'Failed to complete identity verification.');
    } finally {
      setVerifyingIdentity(false);
    }
  };

  // Request Fullscreen when entering active interview
  const enterFullscreen = async () => {
    try {
      if (document.documentElement.requestFullscreen) {
        await document.documentElement.requestFullscreen();
        setIsFullscreen(true);
      }
    } catch (e) {
      console.warn('Fullscreen request bypassed:', e);
    }
  };

  // Fullscreen change listener & continuous webcam frame verification
  useEffect(() => {
    if (!token || !interview?.identity_verified || interview?.status === 'completed') return;

    const handleFullscreenChange = () => {
      const isCurrentlyFullscreen = !!document.fullscreenElement;
      setIsFullscreen(isCurrentlyFullscreen);
      if (!isCurrentlyFullscreen) {
        setIntegrityWarning('Fullscreen mode exited! Please return to fullscreen. Fullscreen exits are logged as proctor events.');
        apiClient.logIntegrityEvent(token, 'fullscreen_exit', 'medium', 1.0, {
          reason: 'Candidate exited fullscreen mode during active assessment'
        }).then(res => {
          if (res.terminated) {
            setTerminatedNotice(res.termination_reason || 'Session terminated due to integrity policy violation.');
            loadInterview();
          }
        }).catch(err => console.warn('Could not log fullscreen exit:', err));
      }
    };

    document.addEventListener('fullscreenchange', handleFullscreenChange);

    // Continuous 12s facial frame check
    continuousProctorIntervalRef.current = setInterval(async () => {
      if (videoRef.current && canvasRef.current && videoRef.current.readyState >= 2) {
        const video = videoRef.current;
        const canvas = canvasRef.current;
        canvas.width = 320;
        canvas.height = 240;
        const ctx = canvas.getContext('2d');
        if (ctx) {
          ctx.drawImage(video, 0, 0, 320, 240);
          const frameBase64 = canvas.toDataURL('image/jpeg', 0.65);
          try {
            const res = await apiClient.logIntegrityEvent(
              token,
              'continuous_face_check',
              'low',
              1.0,
              { timestamp: new Date().toISOString() },
              frameBase64
            );
            if (res.terminated) {
              setTerminatedNotice(res.termination_reason || 'Session terminated due to facial verification mismatch.');
              loadInterview();
            }
          } catch (e) {
            console.warn('Continuous face check cycle error:', e);
          }
        }
      }
    }, 12000);

    return () => {
      document.removeEventListener('fullscreenchange', handleFullscreenChange);
      if (continuousProctorIntervalRef.current) {
        clearInterval(continuousProctorIntervalRef.current);
      }
    };
  }, [token, interview?.identity_verified, interview?.status]);

  // Integrity Proctor Event Listeners (Tab switch, Blur, Paste, Camera interruption)
  useEffect(() => {
    if (!token || !interview?.identity_verified || interview?.status === 'completed') return;

    const handleVisibility = async () => {
      if (document.hidden) {
        const nextCount = tabSwitchesCount + 1;
        setTabSwitchesCount(nextCount);
        setIntegrityWarning(`Tab switch detected! Strike ${nextCount}/3. Navigating away from the interview window is logged.`);
        try {
          const res = await apiClient.logIntegrityEvent(token, 'tab_switch', 'medium', 1.0, {
            reason: `Candidate navigated away from active interview tab (Warning #${nextCount})`
          });
          if (res.terminated) {
            setTerminatedNotice(res.termination_reason || 'Interview session terminated due to excessive tab switching.');
            loadInterview();
          }
        } catch (e) {
          console.warn('Could not log tab switch:', e);
        }
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
  }, [token, interview?.identity_verified, interview?.status, tabSwitchesCount]);

  const handleSubmitAnswer = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) return;

    const qType = interview?.active_question?.question_type || 'open_ended';
    let finalAnswer = '';
    let selectedOpt: string | undefined = undefined;
    let voiceTrans: string | undefined = undefined;
    let finalAnswerMode = 'typed';

    if (qType === 'multiple_choice') {
      if (!selectedOption) {
        alert('Please select an option before proceeding.');
        return;
      }
      finalAnswer = selectedOption;
      selectedOpt = selectedOption;
      finalAnswerMode = 'mcq';
    } else if (qType === 'fill_blank') {
      if (!fillBlankAnswer.trim()) {
        alert('Please fill in the blank before submitting.');
        return;
      }
      finalAnswer = fillBlankAnswer.trim();
      finalAnswerMode = 'typed';
    } else {
      // open_ended
      if (answerMode === 'voice') {
        finalAnswer = voiceRecordedText.trim() || answer.trim();
        voiceTrans = voiceRecordedText.trim();
        finalAnswerMode = 'voice';
      } else {
        finalAnswer = answer.trim();
        finalAnswerMode = 'typed';
      }
      if (!finalAnswer) {
        alert('Please provide an answer before submitting.');
        return;
      }
    }

    try {
      setSubmitting(true);
      setIntegrityWarning(null);
      if (isListeningMic && recognitionRef.current) {
        recognitionRef.current.stop();
        setIsListeningMic(false);
      }

      const res = await apiClient.submitAnswer(token, finalAnswer, {
        answerMode: finalAnswerMode,
        selectedOption: selectedOpt,
        voiceTranscript: voiceTrans
      });

      // Clear input buffers
      setAnswer('');
      setSelectedOption('');
      setFillBlankAnswer('');
      setVoiceRecordedText('');
      setVoiceStatusMessage(null);

      // Fast UI state update directly from response (eliminating unnecessary 30s delays)
      if (res.is_interview_complete || res.status === 'completed') {
        setInterview(prev => prev ? {
          ...prev,
          status: 'completed',
          active_question: undefined,
          total_questions_completed: res.total_questions_completed || (prev.total_questions_completed + 1)
        } : null);
      } else if (res.next_question) {
        setInterview(prev => prev ? {
          ...prev,
          active_question: res.next_question,
          total_questions_completed: res.total_questions_completed || (prev.total_questions_completed + 1)
        } : null);
      } else {
        await loadInterview();
      }
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

  // Interview Completed or Terminated Screen
  if (interview.status === 'completed' || terminatedNotice) {
    return (
      <div style={{ maxWidth: 650, margin: '80px auto', padding: '0 20px', textAlign: 'center' }}>
        <div className="card" style={{ padding: 48, border: '1px solid var(--sage-border)' }}>
          <div style={{ display: 'inline-flex', padding: 16, borderRadius: '50%', backgroundColor: terminatedNotice ? '#ffebee' : 'var(--sage-subtle)', color: terminatedNotice ? 'var(--danger)' : 'var(--sage-accent)', marginBottom: 20 }}>
            {terminatedNotice ? <AlertTriangle size={44} /> : <CheckCircle size={44} />}
          </div>
          <h2 style={{ fontSize: 26, fontWeight: 700, marginBottom: 10, color: 'var(--text-primary)' }}>
            {terminatedNotice ? 'Session Concluded by Integrity Gate' : 'Interview Complete'}
          </h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: 15, marginBottom: 8 }}>
            Candidate: <strong>{interview.candidate_name}</strong>
          </p>
          <p style={{ color: 'var(--text-muted)', fontSize: 14, lineHeight: 1.6, maxWidth: 480, margin: '0 auto 24px' }}>
            {terminatedNotice 
              ? terminatedNotice 
              : `Your adaptive technical interview for ${interview.job_title} has ended. All responses and evidence assessments have been submitted to the human recruiting committee.`}
          </p>
          <div style={{ padding: 14, borderRadius: 8, backgroundColor: 'var(--bg-subtle)', border: '1px solid var(--border-light)', fontSize: 13, color: 'var(--text-muted)' }}>
            You may now safely close this window. You can view your application status in the Candidate Portal.
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

            {/* Mandatory ID Card Presentation step */}
            <div style={{ marginBottom: 18, padding: 12, border: '1px solid var(--border-light)', borderRadius: 8, backgroundColor: 'var(--bg-subtle)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <span style={{ fontSize: 13, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}>
                  <IdCard size={16} color="var(--sage-accent)" /> Government / Student Photo ID Card (Mandatory)
                </span>
                <button 
                  type="button" 
                  onClick={handleCaptureIdCard} 
                  className="btn btn-secondary" 
                  style={{ padding: '4px 10px', fontSize: 12 }}
                >
                  {idCardCaptured ? 'Recapture ID Card' : 'Hold ID to Camera & Capture'}
                </button>
              </div>
              <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: 0 }}>
                {idCardCaptured 
                  ? '✓ ID card snapshot captured successfully.' 
                  : 'Hold your official photo ID card to the webcam and click capture. Required before verification.'}
              </p>
            </div>

            {verificationError && (
              <div style={{ padding: 12, borderRadius: 8, backgroundColor: '#ffebee', border: '1px solid #ffcdd2', color: 'var(--danger)', fontSize: 13, marginBottom: 16, display: 'flex', alignItems: 'center', gap: 10 }}>
                <AlertCircle size={18} /> {verificationError}
              </div>
            )}

            {verificationSuccess && (
              <div style={{ padding: 12, borderRadius: 8, backgroundColor: '#e8f5e9', border: '1px solid #c8e6c9', color: 'var(--success)', fontSize: 13, marginBottom: 16 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontWeight: 600, marginBottom: 4 }}>
                  <CheckCircle size={18} /> {verificationSuccess}
                </div>
                {verificationDetails && (
                  <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                    Similarity Score: {Math.round((verificationDetails.similarity_score || 0.88) * 100)}% • Biometric Verification: Confirmed
                  </div>
                )}
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
              onClick={async () => {
                await enterFullscreen();
                handleVerifyIdentity();
              }}
              disabled={verifyingIdentity || !consentAccepted || !cameraActive || !interview.has_enrolled_reference || !idCardCaptured}
              className="btn btn-primary"
              style={{ width: '100%', padding: '12px', fontSize: 15, opacity: (!consentAccepted || !cameraActive || !interview.has_enrolled_reference || !idCardCaptured) ? 0.5 : 1 }}
            >
              <Camera size={18} /> {verifyingIdentity ? 'Verifying Identity Against Enrolled Reference...' : 'Verify Identity & Enter Interview'}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Active Adaptive Question Responder (Speech Synthesis TTS, Microphone STT, and Text Fallback)
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

        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: 6, 
            fontSize: 12, 
            color: isFullscreen ? 'var(--sage-accent)' : 'var(--warning)', 
            backgroundColor: 'var(--sage-subtle)', 
            padding: '6px 14px', 
            borderRadius: 9999,
            border: '1px solid var(--sage-border)'
          }}>
            <Shield size={14} /> {isFullscreen ? 'Fullscreen Locked' : 'Fullscreen Inactive'}
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
            <Shield size={14} /> Identity Verified & Monitored
          </div>
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
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <span className="badge badge-info">
                {interview.active_question.difficulty_level} Difficulty
              </span>
              {speechSynthesisSupported && (
                <button
                  type="button"
                  onClick={toggleSpeakQuestion}
                  className="btn btn-secondary"
                  style={{ padding: '4px 8px', fontSize: 12, display: 'inline-flex', alignItems: 'center', gap: 4 }}
                  title={isSpeakingQuestion ? 'Mute AI voice' : 'Listen to AI question aloud'}
                >
                  {isSpeakingQuestion ? <VolumeX size={14} color="var(--sage-accent)" /> : <Volume2 size={14} />}
                  {isSpeakingQuestion ? 'Stop Audio' : 'Speak Question'}
                </button>
              )}
            </div>
          </div>

          <h2 style={{ fontSize: 19, fontWeight: 600, lineHeight: 1.5, marginBottom: 20, color: 'var(--text-primary)' }}>
            {interview.active_question.question_text}
          </h2>

          <form onSubmit={handleSubmitAnswer} style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            {/* 1. Multiple Choice Question Rendering */}
            {interview.active_question.question_type === 'multiple_choice' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                <label style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 4 }}>
                  Select the most accurate technical option:
                </label>
                {(interview.active_question.options && interview.active_question.options.length > 0
                  ? interview.active_question.options
                  : ['Option A', 'Option B', 'Option C', 'Option D']
                ).map((opt, idx) => {
                  const isSelected = selectedOption === opt;
                  return (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => setSelectedOption(opt)}
                      style={{
                        textAlign: 'left',
                        padding: '14px 18px',
                        borderRadius: 8,
                        border: isSelected ? '2px solid var(--sage-accent)' : '1px solid var(--border-light)',
                        backgroundColor: isSelected ? 'var(--sage-subtle)' : '#ffffff',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 12,
                        transition: 'all 0.15s ease',
                        fontSize: 14,
                        color: 'var(--text-primary)',
                        fontWeight: isSelected ? 600 : 400
                      }}
                    >
                      <span style={{
                        width: 24,
                        height: 24,
                        borderRadius: '50%',
                        border: isSelected ? '2px solid var(--sage-accent)' : '2px solid var(--border-light)',
                        backgroundColor: isSelected ? 'var(--sage-accent)' : 'transparent',
                        display: 'inline-flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: '#ffffff',
                        fontSize: 12,
                        fontWeight: 700
                      }}>
                        {isSelected ? '✓' : String.fromCharCode(65 + idx)}
                      </span>
                      <span>{opt}</span>
                    </button>
                  );
                })}
              </div>
            )}

            {/* 2. Fill in the Blank Question Rendering */}
            {interview.active_question.question_type === 'fill_blank' && (
              <div>
                <label style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8, display: 'block' }}>
                  Complete the missing technical keyword / statement:
                </label>
                <input
                  type="text"
                  required
                  value={fillBlankAnswer}
                  onChange={(e) => setFillBlankAnswer(e.target.value)}
                  placeholder="Type missing term, function name, algorithm, or syntax here..."
                  style={{
                    width: '100%',
                    padding: '12px 16px',
                    fontSize: 15,
                    borderRadius: 8,
                    border: '1px solid var(--border-light)',
                    outline: 'none',
                    boxSizing: 'border-box'
                  }}
                />
              </div>
            )}

            {/* 3. Open Ended (Typed vs Voice Mode) Rendering */}
            {(!interview.active_question.question_type || interview.active_question.question_type === 'open_ended') && (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                  <div style={{ display: 'flex', gap: 6 }}>
                    <button
                      type="button"
                      onClick={() => setAnswerMode('typed')}
                      className={`btn ${answerMode === 'typed' ? 'btn-primary' : 'btn-secondary'}`}
                      style={{ padding: '4px 12px', fontSize: 12 }}
                    >
                      Typed Response
                    </button>
                    {speechRecognitionSupported && (
                      <button
                        type="button"
                        onClick={() => setAnswerMode('voice')}
                        className={`btn ${answerMode === 'voice' ? 'btn-primary' : 'btn-secondary'}`}
                        style={{ padding: '4px 12px', fontSize: 12, display: 'inline-flex', alignItems: 'center', gap: 4 }}
                      >
                        <Mic size={14} /> Voice Answer Mode
                      </button>
                    )}
                  </div>
                  {answerMode === 'voice' && (
                    <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                      Distraction-free voice capture
                    </span>
                  )}
                </div>

                {answerMode === 'voice' ? (
                  <div style={{
                    padding: 24,
                    border: '1px solid var(--sage-border)',
                    borderRadius: 10,
                    backgroundColor: 'var(--sage-subtle)',
                    textAlign: 'center'
                  }}>
                    <div style={{ marginBottom: 16 }}>
                      <div style={{
                        width: 56,
                        height: 56,
                        borderRadius: '50%',
                        backgroundColor: isListeningMic ? '#ffebee' : '#ffffff',
                        color: isListeningMic ? 'var(--danger)' : 'var(--sage-accent)',
                        display: 'inline-flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        boxShadow: isListeningMic ? '0 0 0 4px rgba(229, 57, 53, 0.2)' : 'none',
                        animation: isListeningMic ? 'pulse 1.5s infinite' : 'none'
                      }}>
                        {isListeningMic ? <Mic size={28} /> : <MicOff size={28} />}
                      </div>
                    </div>

                    <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 6 }}>
                      {isListeningMic ? 'Listening to your response...' : 'Microphone Ready'}
                    </h3>
                    <p style={{ fontSize: 13, color: 'var(--text-secondary)', maxWidth: 460, margin: '0 auto 16px', lineHeight: 1.5 }}>
                      {isListeningMic 
                        ? 'Speak clearly. Live transcript text is kept hidden so you stay focused on your thought process.'
                        : (voiceRecordedText ? 'Audio response captured. You can submit or re-record below.' : 'Click "Start Speaking" and speak your answer naturally.')}
                    </p>

                    <div style={{ display: 'flex', justifyContent: 'center', gap: 10 }}>
                      <button
                        type="button"
                        onClick={toggleListening}
                        className={`btn ${isListeningMic ? 'btn-danger' : 'btn-primary'}`}
                        style={{ padding: '8px 18px', fontSize: 13 }}
                      >
                        {isListeningMic ? 'Stop Recording' : (voiceRecordedText ? 'Re-record Voice Response' : 'Start Speaking')}
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setAnswer(voiceRecordedText || answer);
                          setAnswerMode('typed');
                        }}
                        className="btn btn-secondary"
                        style={{ padding: '8px 16px', fontSize: 13 }}
                      >
                        Switch to Typed Answer
                      </button>
                    </div>

                    {voiceStatusMessage && (
                      <div style={{ marginTop: 14, fontSize: 12, color: 'var(--text-secondary)' }}>
                        {voiceStatusMessage}
                      </div>
                    )}
                  </div>
                ) : (
                  <div>
                    <label style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 8, display: 'block' }}>
                      Your Answer (Explain methodology, architecture, and technical rationale):
                    </label>
                    <textarea
                      required
                      rows={8}
                      value={answer}
                      onChange={(e) => setAnswer(e.target.value)}
                      placeholder="Type your comprehensive technical response here..."
                      style={{ width: '100%', resize: 'vertical', lineHeight: 1.5, boxSizing: 'border-box' }}
                    />
                  </div>
                )}
              </div>
            )}

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: 8 }}>
              <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>
                Questions completed: {interview.total_questions_completed}
              </span>
              <button 
                type="submit" 
                disabled={
                  submitting || 
                  (interview.active_question.question_type === 'multiple_choice' && !selectedOption) ||
                  (interview.active_question.question_type === 'fill_blank' && !fillBlankAnswer.trim()) ||
                  ((!interview.active_question.question_type || interview.active_question.question_type === 'open_ended') && 
                    ((answerMode === 'typed' && !answer.trim()) || (answerMode === 'voice' && !voiceRecordedText.trim() && !answer.trim())))
                } 
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

