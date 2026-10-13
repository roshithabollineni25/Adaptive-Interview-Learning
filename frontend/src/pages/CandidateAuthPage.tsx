import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { apiClient } from '../api/client';
import { User, LogIn, UserPlus, ArrowLeft } from 'lucide-react';

export const CandidateAuthPage: React.FC = () => {
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      if (isRegister) {
        const res = await apiClient.register({ email, password, full_name: fullName, role: 'candidate' });
        localStorage.setItem('token', res.access_token);
        localStorage.setItem('user', JSON.stringify(res.user));
        navigate('/candidate/dashboard');
      } else {
        const res = await apiClient.login({ email, password });
        if (res.user.role !== 'candidate') {
          setError('This account is registered with recruiter privileges. Please use the Recruiter Portal sign-in.');
          setLoading(false);
          return;
        }
        localStorage.setItem('token', res.access_token);
        localStorage.setItem('user', JSON.stringify(res.user));
        navigate('/candidate/dashboard');
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Authentication failed. Please check credentials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: 440, margin: '80px auto', padding: '0 20px' }}>
      <div style={{ marginBottom: 16 }}>
        <Link to="/" style={{ color: 'var(--text-muted)', fontSize: 13, display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <ArrowLeft size={14} /> Back to Public Landing
        </Link>
      </div>

      <div className="card" style={{ padding: 36 }}>
        <div style={{ textAlign: 'center', marginBottom: 28 }}>
          <div style={{ 
            width: 40, 
            height: 40, 
            borderRadius: 10, 
            backgroundColor: 'var(--sage-subtle)', 
            color: 'var(--sage-accent)',
            display: 'inline-flex', 
            alignItems: 'center', 
            justifyContent: 'center',
            marginBottom: 12
          }}>
            <User size={22} />
          </div>
          <h2 style={{ fontSize: 22, fontWeight: 700, color: 'var(--text-primary)' }}>
            {isRegister ? 'Candidate Account Registration' : 'Candidate Portal Sign In'}
          </h2>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 4 }}>
            Apply for positions, complete verification, and track interview schedules
          </p>
        </div>

        {error && (
          <div style={{ padding: 12, borderRadius: 8, backgroundColor: '#ffebee', border: '1px solid #ffcdd2', color: 'var(--danger)', fontSize: 13, marginBottom: 20 }}>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {isRegister && (
            <div>
              <label style={{ display: 'block', fontSize: 13, marginBottom: 6, color: 'var(--text-secondary)' }}>Full Legal Name</label>
              <input
                type="text"
                required
                style={{ width: '100%' }}
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Marcus Vance"
              />
            </div>
          )}

          <div>
            <label style={{ display: 'block', fontSize: 13, marginBottom: 6, color: 'var(--text-secondary)' }}>Email Address</label>
            <input
              type="email"
              required
              style={{ width: '100%' }}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="candidate@example.com"
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: 13, marginBottom: 6, color: 'var(--text-secondary)' }}>Password</label>
            <input
              type="password"
              required
              style={{ width: '100%' }}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
            />
          </div>

          <button type="submit" disabled={loading} className="btn btn-primary" style={{ marginTop: 8, padding: '12px' }}>
            {isRegister ? <UserPlus size={16} /> : <LogIn size={16} />}
            {loading ? 'Processing...' : isRegister ? 'Register Candidate Account' : 'Sign In to Candidate Portal'}
          </button>
        </form>

        {/* Clearly Labeled Demo Candidate Login */}
        <div style={{ marginTop: 20, paddingTop: 18, borderTop: '1px solid var(--border-light)', textAlign: 'center' }}>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 8 }}>
            Evaluating as a candidate?
          </p>
          <button
            type="button"
            disabled={loading}
            onClick={async () => {
              setError(null);
              setLoading(true);
              try {
                const res = await apiClient.login({
                  email: 'demo.candidate@adaptiveinterview.io',
                  password: 'DemoCandidate123!'
                });
                localStorage.setItem('token', res.access_token);
                localStorage.setItem('user', JSON.stringify(res.user));
                navigate('/candidate/dashboard');
              } catch (err: any) {
                setError(err?.response?.data?.detail || 'Demo login failed');
              } finally {
                setLoading(false);
              }
            }}
            className="btn btn-secondary"
            style={{ width: '100%', fontSize: 13, padding: '9px 14px' }}
          >
            Demo Candidate One-Click Sign In
          </button>
        </div>

        <div style={{ marginTop: 20, textAlign: 'center', fontSize: 13, color: 'var(--text-secondary)' }}>
          {isRegister ? 'Already have a candidate account?' : "New candidate?"}{' '}
          <button
            onClick={() => { setIsRegister(!isRegister); setError(null); }}
            style={{ background: 'none', border: 'none', color: 'var(--sage-accent)', cursor: 'pointer', textDecoration: 'underline', fontWeight: 600 }}
          >
            {isRegister ? 'Sign In' : 'Register Here'}
          </button>
        </div>
      </div>
    </div>
  );
};
