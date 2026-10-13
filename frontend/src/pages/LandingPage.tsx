import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { 
  ArrowRight, Briefcase, User, X
} from 'lucide-react';

export const LandingPage: React.FC = () => {
  const [candidateToken, setCandidateToken] = useState('');
  const [showPortalModal, setShowPortalModal] = useState(false);
  const navigate = useNavigate();

  const handleCandidateEnter = (e: React.FormEvent) => {
    e.preventDefault();
    if (!candidateToken.trim()) return;
    const cleanToken = candidateToken.trim().split('/').pop() || candidateToken.trim();
    navigate(`/interview/${cleanToken}`);
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', backgroundColor: 'var(--bg-main)' }}>
      {/* Top Navigation */}
      <header style={{ 
        borderBottom: '1px solid var(--border-light)', 
        backgroundColor: 'rgba(255, 255, 255, 0.95)',
        position: 'sticky',
        top: 0,
        zIndex: 40,
        backdropFilter: 'blur(8px)'
      }}>
        <div style={{ 
          maxWidth: 1200, 
          margin: '0 auto', 
          padding: '16px 24px', 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center' 
        }}>
          <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ 
              width: 34, 
              height: 34, 
              borderRadius: 8, 
              backgroundColor: 'var(--sage-accent)', 
              display: 'flex', 
              alignItems: 'center', 
              justifyContent: 'center',
              color: '#ffffff',
              fontWeight: 800,
              fontSize: 16
            }}>
              A
            </div>
            <div>
              <span style={{ fontSize: 17, fontWeight: 700, letterSpacing: '-0.02em', color: 'var(--text-primary)' }}>
                Adaptive Interview Intelligence
              </span>
            </div>
          </Link>

          {/* Single Primary Top-Right Button: Enter Interview Portals */}
          <div>
            <button 
              onClick={() => setShowPortalModal(true)} 
              className="btn btn-primary" 
              style={{ fontSize: 13, padding: '8px 18px', display: 'inline-flex', alignItems: 'center', gap: 6 }}
            >
              Enter Interview Portals <ArrowRight size={14} />
            </button>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <main style={{ flex: 1 }}>
        <section style={{ 
          maxWidth: 1200, 
          margin: '0 auto', 
          padding: '80px 24px 60px', 
          display: 'grid', 
          gridTemplateColumns: '1.2fr 1fr', 
          gap: 60,
          alignItems: 'center' 
        }}>
          <div>
            <div style={{ 
              display: 'inline-flex', 
              alignItems: 'center', 
              gap: 8, 
              padding: '6px 14px', 
              borderRadius: 9999, 
              backgroundColor: 'var(--sage-subtle)', 
              border: '1px solid var(--sage-border)',
              fontSize: 12,
              color: 'var(--sage-accent)',
              fontWeight: 600,
              marginBottom: 24
            }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', backgroundColor: 'var(--sage-accent)' }}></span>
              Adaptive Recruitment & Evaluation Platform
            </div>

            <h1 style={{ 
              fontSize: 48, 
              fontWeight: 800, 
              lineHeight: 1.15, 
              letterSpacing: '-0.03em', 
              color: 'var(--text-primary)',
              marginBottom: 20
            }}>
              Interviews that adapt. <br />
              <span style={{ color: 'var(--sage-accent)' }}>Evidence</span> that informs better hiring.
            </h1>

            <p style={{ 
              fontSize: 18, 
              lineHeight: 1.6, 
              color: 'var(--text-secondary)', 
              marginBottom: 36,
              maxWidth: 580
            }}>
              Conduct role-specific technical assessments with multi-factor biometric identity protection,
              evidence-backed response scoring, and verifiable human hiring authority.
            </p>

            <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', marginBottom: 40 }}>
              <button 
                onClick={() => setShowPortalModal(true)} 
                className="btn btn-primary" 
                style={{ padding: '12px 26px', fontSize: 15, display: 'inline-flex', alignItems: 'center', gap: 8 }}
              >
                Enter Interview Portals <ArrowRight size={16} />
              </button>
            </div>

            <div style={{ display: 'flex', gap: 24, borderTop: '1px solid var(--border-light)', paddingTop: 24 }}>
              <div>
                <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>Decision Authority</div>
                <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>Human Recruiter Final Choice</div>
              </div>
              <div style={{ width: 1, backgroundColor: 'var(--border-light)' }}></div>
              <div>
                <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>Identity Gate</div>
                <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>Biometric Consent & Verification</div>
              </div>
              <div style={{ width: 1, backgroundColor: 'var(--border-light)' }}></div>
              <div>
                <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>Schedule Enforcement</div>
                <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>Strict Backend Time Window</div>
              </div>
            </div>
          </div>

          {/* Clean Interview Interface Preview */}
          <div style={{ 
            backgroundColor: 'var(--bg-surface)', 
            border: '1px solid var(--border-light)', 
            borderRadius: 14, 
            boxShadow: 'var(--shadow-md)',
            overflow: 'hidden'
          }}>
            <div style={{ 
              backgroundColor: 'var(--bg-subtle)', 
              padding: '14px 18px', 
              borderBottom: '1px solid var(--border-light)',
              display: 'flex', 
              alignItems: 'center', 
              justifyContent: 'space-between' 
            }}>
              <div style={{ display: 'flex', gap: 6 }}>
                <span style={{ width: 10, height: 10, borderRadius: '50%', backgroundColor: '#ef4444' }}></span>
                <span style={{ width: 10, height: 10, borderRadius: '50%', backgroundColor: '#f59e0b' }}></span>
                <span style={{ width: 10, height: 10, borderRadius: '50%', backgroundColor: '#10b981' }}></span>
              </div>
              <span style={{ fontSize: 12, color: 'var(--text-muted)', fontFamily: 'monospace' }}>
                live-adaptive-interview-preview
              </span>
              <span className="badge badge-info" style={{ fontSize: 11 }}>
                Scheduled Window
              </span>
            </div>

            <div style={{ padding: 24 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <span style={{ fontSize: 12, color: 'var(--sage-accent)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Question 2 of 5 • Cloud Architecture
                </span>
                <span className="badge badge-warning" style={{ fontSize: 11 }}>
                  High Difficulty
                </span>
              </div>

              <h4 style={{ fontSize: 15, fontWeight: 600, lineHeight: 1.5, marginBottom: 16, color: 'var(--text-primary)' }}>
                "How do you mitigate downstream cascading failure when asynchronous message ingestion spikes 10x beyond database pool throughput?"
              </h4>

              <div style={{ 
                backgroundColor: 'var(--bg-subtle)', 
                border: '1px solid var(--border-light)', 
                borderRadius: 8, 
                padding: 14, 
                marginBottom: 16 
              }}>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6, display: 'flex', justifyContent: 'space-between' }}>
                  <span>Candidate Response Analysis:</span>
                  <span style={{ color: 'var(--sage-accent)', fontWeight: 600 }}>Evidence Verified</span>
                </div>
                <div style={{ fontSize: 13, color: 'var(--text-secondary)', fontStyle: 'italic', lineHeight: 1.5 }}>
                  "Decoupling consumers with reactive backpressure, utilizing circuit breakers and leasing database connections dynamically..."
                </div>
              </div>

              <div style={{ 
                borderTop: '1px solid var(--border-light)', 
                paddingTop: 14, 
                display: 'grid', 
                gridTemplateColumns: '1fr 1fr', 
                gap: 12,
                fontSize: 12 
              }}>
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>Evidence Quote:</span>
                  <div style={{ fontWeight: 600, color: 'var(--sage-accent)', marginTop: 2 }}>Backpressure Strategy</div>
                </div>
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>Skill Assessment:</span>
                  <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginTop: 2 }}>Demonstrated Competency</div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Portals Access Section */}
        <section id="two-portals" style={{ 
          backgroundColor: 'var(--bg-surface)', 
          borderTop: '1px solid var(--border-light)', 
          borderBottom: '1px solid var(--border-light)',
          padding: '80px 24px' 
        }}>
          <div style={{ maxWidth: 1200, margin: '0 auto' }}>
            <div style={{ textAlign: 'center', marginBottom: 48 }}>
              <h2 style={{ fontSize: 32, fontWeight: 700, letterSpacing: '-0.02em', marginBottom: 10 }}>
                Two Distinct Portals. One Cohesive System.
              </h2>
              <p style={{ color: 'var(--text-secondary)', fontSize: 16, maxWidth: 640, margin: '0 auto' }}>
                Secure, role-based workflows designed specifically for hiring teams and prospective candidates.
              </p>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 28, maxWidth: 960, margin: '0 auto' }}>
              {/* Recruiter Portal Card */}
              <div className="card" style={{ padding: 32, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                <div>
                  <div style={{ width: 44, height: 44, borderRadius: 10, backgroundColor: 'var(--sage-subtle)', color: 'var(--sage-accent)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 18 }}>
                    <Briefcase size={22} />
                  </div>
                  <h3 style={{ fontSize: 20, fontWeight: 700, marginBottom: 8 }}>Recruiter Portal</h3>
                  <p style={{ fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: 20 }}>
                    Manage positions, review applicant resumes, schedule AI-assisted adaptive sessions, inspect evidence quotes and skill gaps, and record final hiring decisions.
                  </p>
                  <ul style={{ listStyle: 'none', padding: 0, margin: '0 0 24px 0', fontSize: 13, color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: 8 }}>
                    <li>✓ Role creation & competency extraction</li>
                    <li>✓ AI-assisted interview scheduling & email invitations</li>
                    <li>✓ Proctor integrity audit & telemetry review</li>
                    <li>✓ Evidence dossiers & human hiring authority</li>
                  </ul>
                </div>
                <div style={{ display: 'flex', gap: 10 }}>
                  <Link to="/login" className="btn btn-primary" style={{ flex: 1 }}>
                    Recruiter Sign In <ArrowRight size={14} />
                  </Link>
                </div>
              </div>

              {/* Candidate Portal Card */}
              <div className="card" style={{ padding: 32, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                <div>
                  <div style={{ width: 44, height: 44, borderRadius: 10, backgroundColor: 'var(--sage-subtle)', color: 'var(--sage-accent)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 18 }}>
                    <User size={22} />
                  </div>
                  <h3 style={{ fontSize: 20, fontWeight: 700, marginBottom: 8 }}>Candidate Portal</h3>
                  <p style={{ fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: 20 }}>
                    Apply for target roles, upload PDF/DOCX resumes, enroll your biometric identity reference, check scheduled interview dates, and access your secure session.
                  </p>
                  <ul style={{ listStyle: 'none', padding: 0, margin: '0 0 24px 0', fontSize: 13, color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: 8 }}>
                    <li>✓ Application submission & target role entry</li>
                    <li>✓ Secure resume parsing & skill profile persistence</li>
                    <li>✓ Consent-based biometric reference enrollment</li>
                    <li>✓ Scheduled interview tracking & window access</li>
                  </ul>
                </div>
                <div style={{ display: 'flex', gap: 10 }}>
                  <Link to="/candidate/login" className="btn btn-primary" style={{ flex: 1 }}>
                    Candidate Sign In / Apply <ArrowRight size={14} />
                  </Link>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Direct Interview Invitation Token Link Entry */}
        <section style={{ maxWidth: 800, margin: '0 auto', padding: '70px 24px' }}>
          <div className="card" style={{ padding: 36 }}>
            <h3 style={{ fontSize: 19, fontWeight: 700, marginBottom: 8 }}>Direct Invitation Token Access</h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: 14, marginBottom: 20 }}>
              Received an email invitation link with an interview session token? Enter it below to launch the interview gateway directly:
            </p>
            <form onSubmit={handleCandidateEnter} style={{ display: 'flex', gap: 12 }}>
              <input
                type="text"
                required
                style={{ flex: 1, padding: '12px 16px', fontSize: 14 }}
                value={candidateToken}
                onChange={(e) => setCandidateToken(e.target.value)}
                placeholder="Paste interview session token (e.g., 3fa85f64-5717-...)"
              />
              <button type="submit" className="btn btn-primary" style={{ padding: '12px 24px', whiteSpace: 'nowrap' }}>
                Open Session <ArrowRight size={14} />
              </button>
            </form>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer style={{ 
        borderTop: '1px solid var(--border-light)', 
        backgroundColor: 'var(--bg-surface)', 
        padding: '24px', 
        fontSize: 13,
        color: 'var(--text-muted)'
      }}>
        <div style={{ maxWidth: 1200, margin: '0 auto', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>Adaptive Interview Intelligence • Google Student Club Welcome Hackathon 2026</span>
          <div style={{ display: 'flex', gap: 20 }}>
            <Link to="/candidate/login" style={{ color: 'var(--sage-accent)' }}>Candidate Portal</Link>
            <Link to="/login" style={{ color: 'var(--sage-accent)' }}>Recruiter Portal</Link>
          </div>
        </div>
      </footer>

      {/* Portal Selection Modal */}
      {showPortalModal && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.55)',
          backdropFilter: 'blur(4px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 100,
          padding: 20
        }}>
          <div className="card" style={{ maxWidth: 600, width: '100%', padding: 32, position: 'relative' }}>
            <button
              onClick={() => setShowPortalModal(false)}
              style={{
                position: 'absolute',
                top: 18,
                right: 18,
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                color: 'var(--text-muted)'
              }}
            >
              <X size={20} />
            </button>

            <h3 style={{ fontSize: 22, fontWeight: 700, marginBottom: 6, color: 'var(--text-primary)' }}>
              Select Your Portal
            </h3>
            <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginBottom: 24 }}>
              Choose your role to access applicant workflows or recruiting workspace.
            </p>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              {/* Candidate Option */}
              <div 
                onClick={() => navigate('/candidate/login')}
                style={{
                  padding: 20,
                  border: '1px solid var(--border-light)',
                  borderRadius: 10,
                  cursor: 'pointer',
                  backgroundColor: 'var(--bg-subtle)',
                  transition: 'all 0.15s ease'
                }}
              >
                <div style={{
                  width: 38,
                  height: 38,
                  borderRadius: 8,
                  backgroundColor: 'var(--sage-subtle)',
                  color: 'var(--sage-accent)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  marginBottom: 12
                }}>
                  <User size={20} />
                </div>
                <h4 style={{ fontSize: 16, fontWeight: 600, marginBottom: 4 }}>Candidate Portal</h4>
                <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5, marginBottom: 16 }}>
                  Register, apply for roles, upload resume, enroll biometric reference, and access interviews.
                </p>
                <span className="btn btn-secondary" style={{ width: '100%', fontSize: 12, padding: '6px 12px', textAlign: 'center' }}>
                  Candidate Sign In / Register
                </span>
              </div>

              {/* Recruiter Option */}
              <div 
                onClick={() => navigate('/login')}
                style={{
                  padding: 20,
                  border: '1px solid var(--sage-border)',
                  borderRadius: 10,
                  cursor: 'pointer',
                  backgroundColor: '#ffffff',
                  boxShadow: 'var(--shadow-sm)',
                  transition: 'all 0.15s ease'
                }}
              >
                <div style={{
                  width: 38,
                  height: 38,
                  borderRadius: 8,
                  backgroundColor: 'var(--sage-accent)',
                  color: '#ffffff',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  marginBottom: 12
                }}>
                  <Briefcase size={20} />
                </div>
                <h4 style={{ fontSize: 16, fontWeight: 600, marginBottom: 4 }}>Recruiter Portal</h4>
                <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5, marginBottom: 16 }}>
                  Post roles, schedule interviews, review proctor telemetry, inspect evidence, and decide outcomes.
                </p>
                <span className="btn btn-primary" style={{ width: '100%', fontSize: 12, padding: '6px 12px', textAlign: 'center' }}>
                  Recruiter Sign In
                </span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
