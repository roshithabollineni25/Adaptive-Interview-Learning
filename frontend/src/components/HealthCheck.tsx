import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { apiClient } from '../api/client';
import type { HealthStatus } from '../types';
import { Activity, ShieldCheck, Database, Cpu, CheckCircle2, XCircle } from 'lucide-react';

export const HealthCheck: React.FC = () => {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchHealth = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await apiClient.getHealth();
      setHealth(data);
    } catch (err: any) {
      setError(err?.message || 'Failed to reach backend API');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
  }, []);

  return (
    <div style={{ maxWidth: 800, margin: '40px auto', padding: '0 20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 28, fontWeight: 700, color: '#f8fafc' }}>Adaptive Interview Intelligence</h1>
          <p style={{ color: '#94a3b8', fontSize: 14 }}>Google Student Club Hackathon 2026 Foundation Health</p>
        </div>
        <button onClick={fetchHealth} className="btn btn-secondary">
          <Activity size={16} /> Refresh
        </button>
      </div>

      {loading && (
        <div className="card" style={{ textAlign: 'center', padding: 40, color: '#94a3b8' }}>
          Pinging backend foundation...
        </div>
      )}

      {error && (
        <div className="card" style={{ borderColor: 'var(--danger)', backgroundColor: 'rgba(239, 68, 68, 0.1)', marginBottom: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: '#f87171' }}>
            <XCircle size={20} />
            <strong>API Connection Error: {error}</strong>
          </div>
          <p style={{ marginTop: 8, fontSize: 13, color: '#cbd5e1' }}>
            Ensure the FastAPI backend is running on port 8000.
          </p>
        </div>
      )}

      {health && (
        <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--border)', paddingBottom: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{ padding: 10, borderRadius: 8, backgroundColor: 'rgba(59, 130, 246, 0.15)', color: '#60a5fa' }}>
                <ShieldCheck size={28} />
              </div>
              <div>
                <h3 style={{ fontSize: 18, fontWeight: 600 }}>System Status: {health.status.toUpperCase()}</h3>
                <span style={{ fontSize: 13, color: '#94a3b8' }}>Project: {health.project_name}</span>
              </div>
            </div>
            <span className={`badge ${health.status === 'healthy' ? 'badge-success' : 'badge-warning'}`}>
              {health.status}
            </span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <div style={{ border: '1px solid var(--border)', padding: 16, borderRadius: 6, display: 'flex', alignItems: 'center', gap: 12 }}>
              <Database size={24} color={health.database_connected ? '#34d399' : '#f87171'} />
              <div>
                <div style={{ fontSize: 13, color: '#94a3b8' }}>Persistent Database</div>
                <div style={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}>
                  {health.database_connected ? (
                    <>
                      <CheckCircle2 size={16} color="#34d399" /> Connected & Migrated
                    </>
                  ) : (
                    <>
                      <XCircle size={16} color="#f87171" /> Disconnected
                    </>
                  )}
                </div>
              </div>
            </div>

            <div style={{ border: '1px solid var(--border)', padding: 16, borderRadius: 6, display: 'flex', alignItems: 'center', gap: 12 }}>
              <Cpu size={24} color={health.llm_configured ? '#34d399' : '#fbbf24'} />
              <div>
                <div style={{ fontSize: 13, color: '#94a3b8' }}>Backend LLM Service</div>
                <div style={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}>
                  {health.llm_configured ? (
                    <>
                      <CheckCircle2 size={16} color="#34d399" /> LLM Key Configured
                    </>
                  ) : (
                    <span style={{ fontSize: 13, color: '#fbbf24' }}>
                      Ready (Fallback Active / Key Optional)
                    </span>
                  )}
                </div>
              </div>
            </div>
          </div>

          <div style={{ fontSize: 12, color: '#64748b', textAlign: 'right' }}>
            Backend Timestamp: {new Date(health.timestamp).toLocaleString()}
          </div>

          <div style={{ marginTop: 12, display: 'flex', gap: 12 }}>
            <Link to="/recruiter" className="btn btn-primary" style={{ flex: 1 }}>
              Enter Recruiter Portal
            </Link>
            <Link to="/login" className="btn btn-secondary">
              Recruiter Login / Register
            </Link>
          </div>
        </div>
      )}
    </div>
  );
};
