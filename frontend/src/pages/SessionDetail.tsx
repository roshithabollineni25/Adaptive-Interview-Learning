import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { apiClient } from '../api/client';
import type { InterviewSessionDetail } from '../types';
import { 
  ArrowLeft, CheckCircle, ShieldAlert, 
  BarChart3, Award, Quote, UserCheck 
} from 'lucide-react';

export const SessionDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [session, setSession] = useState<InterviewSessionDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [decision, setDecision] = useState<string>('Hired');
  const [notes, setNotes] = useState<string>('');
  const [candidateFeedback, setCandidateFeedback] = useState<string>('');
  const [savingDecision, setSavingDecision] = useState(false);
  const [decisionNotice, setDecisionNotice] = useState<{ type: 'success' | 'warning' | 'error'; text: string } | null>(null);

  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const loadDetail = async () => {
    if (!id) return;
    try {
      setLoading(true);
      setErrorMsg(null);
      const data = await apiClient.getSessionDetail(Number(id));
      setSession(data);
      if (data.recruiter_decision) setDecision(data.recruiter_decision);
      if (data.recruiter_notes) setNotes(data.recruiter_notes);
      if (data.candidate_feedback) setCandidateFeedback(data.candidate_feedback);
    } catch (err: any) {
      if (err?.response?.status === 401 || err?.response?.status === 403) {
        window.location.href = '/login';
        return;
      }
      const detail = err?.response?.data?.detail;
      if (err?.response?.status === 404) {
        setErrorMsg(`Interview session #${id} was not found in the database.`);
      } else {
        setErrorMsg(detail || 'Evaluation report is not available for this session yet.');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDetail();
  }, [id]);

  const handleSaveDecision = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!id) return;
    try {
      setSavingDecision(true);
      setDecisionNotice(null);
      const res = await apiClient.updateDecision(Number(id), {
        recruiter_decision: decision,
        recruiter_notes: notes,
        candidate_feedback: candidateFeedback
      });

      const emailStatus = res.email_delivery?.status;
      const emailDelivered = res.email_delivery?.delivered;
      const emailMsg = res.email_delivery?.message || '';

      if (emailDelivered) {
        setDecisionNotice({
          type: 'success',
          text: `Decision saved to database! Candidate notified via email at ${session?.candidate?.email}.`
        });
      } else if (emailStatus === 'configuration_required' || emailStatus === 'delivery_failed') {
        setDecisionNotice({
          type: 'warning',
          text: `Decision saved in database and updated in Candidate Portal. Email notice: ${emailMsg}`
        });
      } else {
        setDecisionNotice({
          type: 'success',
          text: `Decision '${res.decision}' recorded successfully.`
        });
      }
      loadDetail();
    } catch (err: any) {
      setDecisionNotice({
        type: 'error',
        text: err?.response?.data?.detail || 'Failed to update recruiter decision.'
      });
    } finally {
      setSavingDecision(false);
    }
  };

  if (loading) {
    return (
      <div style={{ maxWidth: 1000, margin: '60px auto', textAlign: 'center', color: 'var(--text-muted)' }}>
        Loading Candidate Dossier & Evidence Reports...
      </div>
    );
  }

  if (errorMsg || !session) {
    return (
      <div style={{ maxWidth: 800, margin: '60px auto', padding: '0 20px' }}>
        <div style={{ marginBottom: 20 }}>
          <Link to="/recruiter" className="btn btn-secondary" style={{ padding: '6px 14px', fontSize: 13 }}>
            <ArrowLeft size={16} /> Back to Recruiter Dashboard
          </Link>
        </div>
        <div className="card" style={{ textAlign: 'center', padding: '48px 24px' }}>
          <div style={{ display: 'inline-flex', padding: 12, borderRadius: '50%', backgroundColor: 'var(--bg-subtle)', marginBottom: 16 }}>
            <BarChart3 size={32} color="var(--sage-accent)" />
          </div>
          <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 8, color: 'var(--text-primary)' }}>
            Report Not Available Yet
          </h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: 14, maxWidth: 500, margin: '0 auto 24px', lineHeight: 1.6 }}>
            {errorMsg || 'This interview session has not generated an evaluation report yet. Once the candidate completes the session questions, the full skill-gap and evidence dossier will appear here.'}
          </p>
          <div style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
            <button onClick={loadDetail} className="btn btn-primary" style={{ padding: '8px 18px', fontSize: 13 }}>
              Retry Fetching Report
            </button>
            <Link to="/recruiter" className="btn btn-secondary" style={{ padding: '8px 18px', fontSize: 13 }}>
              Return to Queue
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 1120, margin: '40px auto', padding: '0 24px' }}>
      <div style={{ marginBottom: 20 }}>
        <Link to="/recruiter" className="btn btn-secondary" style={{ padding: '6px 14px', fontSize: 13 }}>
          <ArrowLeft size={16} /> Back to Recruiter Dashboard
        </Link>
      </div>

      {/* Candidate Overview Card */}
      <div className="card" style={{ marginBottom: 24, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <span style={{ fontSize: 12, color: 'var(--sage-accent)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Evidence-Based Candidate Report
          </span>
          <h1 style={{ fontSize: 26, fontWeight: 700, marginTop: 4, color: 'var(--text-primary)' }}>{session.candidate.full_name}</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: 14 }}>
            {session.candidate.email} • Position: <strong>{session.job.title}</strong>
          </p>
          <div style={{ marginTop: 12, display: 'flex', gap: 12, alignItems: 'center' }}>
            {session.identity_verified ? (
              <span className="badge badge-success">✓ Identity Verified Before Questioning</span>
            ) : (
              <span className="badge badge-warning">Identity Verification Pending/Bypassed</span>
            )}
            {session.scheduled_start && (
              <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>
                Scheduled for {new Date(session.scheduled_start).toLocaleString()}
              </span>
            )}
          </div>
        </div>

        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>AI Evidence Score</div>
          <div style={{ fontSize: 32, fontWeight: 800, color: (session.final_score || 0) >= 7 ? 'var(--success)' : 'var(--warning)' }}>
            {session.final_score !== null && session.final_score !== undefined ? `${session.final_score} / 10` : 'Pending completion'}
          </div>
          <span className="badge badge-info" style={{ marginTop: 6 }}>
            {session.final_recommendation || 'Assessment In Progress'}
          </span>
        </div>
      </div>

      {/* Intelligence Modules: 4-Tier Skill Gap & Proctor Integrity */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24, marginBottom: 24 }}>
        {/* Module 1: 4-Tier Skill Gap Intelligence */}
        <div className="card">
          <h3 style={{ fontSize: 16, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
            <BarChart3 size={18} color="var(--sage-accent)" /> Resume-to-Interview Skill Gap Analysis
          </h3>
          {session.skill_gap_analysis ? (
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 14, paddingBottom: 10, borderBottom: '1px solid var(--border-light)' }}>
                <span style={{ fontSize: 14, color: 'var(--text-secondary)' }}>Overall Demonstrated Match:</span>
                <span style={{ fontWeight: 700, color: 'var(--sage-accent)', fontSize: 16 }}>{session.skill_gap_analysis.match_percentage}%</span>
              </div>

              {/* Demonstrated */}
              <div style={{ marginBottom: 12 }}>
                <div style={{ fontSize: 12, color: 'var(--success)', fontWeight: 600, marginBottom: 4 }}>
                  ● Demonstrated in Interview:
                </div>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {session.skill_gap_analysis.demonstrated?.length > 0 
                    ? session.skill_gap_analysis.demonstrated.map((s, i) => (
                        <span key={i} className="badge badge-success" style={{ fontSize: 11 }}>{s}</span>
                      ))
                    : <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>None recorded yet</span>}
                </div>
              </div>

              {/* Claimed / Unvalidated */}
              <div style={{ marginBottom: 12 }}>
                <div style={{ fontSize: 12, color: 'var(--warning)', fontWeight: 600, marginBottom: 4 }}>
                  ● Claimed on Resume / Unvalidated:
                </div>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {session.skill_gap_analysis.claimed_unvalidated?.length > 0 
                    ? session.skill_gap_analysis.claimed_unvalidated.map((s, i) => (
                        <span key={i} className="badge badge-warning" style={{ fontSize: 11 }}>{s}</span>
                      ))
                    : <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>None</span>}
                </div>
              </div>

              {/* Not Demonstrated / Gaps */}
              <div style={{ marginBottom: 12 }}>
                <div style={{ fontSize: 12, color: 'var(--danger)', fontWeight: 600, marginBottom: 4 }}>
                  ● Not Demonstrated / Skill Gap:
                </div>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {session.skill_gap_analysis.not_demonstrated?.length > 0 
                    ? session.skill_gap_analysis.not_demonstrated.map((s, i) => (
                        <span key={i} className="badge badge-danger" style={{ fontSize: 11 }}>{s}</span>
                      ))
                    : <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>None</span>}
                </div>
              </div>

              {/* Not Assessed */}
              <div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', fontWeight: 600, marginBottom: 4 }}>
                  ● Not Assessed:
                </div>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {session.skill_gap_analysis.not_assessed?.length > 0 
                    ? session.skill_gap_analysis.not_assessed.map((s, i) => (
                        <span key={i} style={{ backgroundColor: 'var(--bg-subtle)', border: '1px solid var(--border-light)', padding: '2px 8px', borderRadius: 4, fontSize: 11 }}>{s}</span>
                      ))
                    : <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>None</span>}
                </div>
              </div>
            </div>
          ) : (
            <div style={{ color: 'var(--text-muted)', fontSize: 13, padding: '16px 0' }}>
              Skill-gap analysis generates upon interview completion.
            </div>
          )}
        </div>

        {/* Module 2: Proctor Integrity Telemetry */}
        <div className="card">
          <h3 style={{ fontSize: 16, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
            <ShieldAlert size={18} color="var(--danger)" /> Proctor Integrity Telemetry ({session.integrity_events.length})
          </h3>
          {session.integrity_events.length === 0 ? (
            <div style={{ color: 'var(--success)', display: 'flex', alignItems: 'center', gap: 8, fontSize: 14, padding: '16px 0' }}>
              <CheckCircle size={18} /> No integrity anomalies logged. Candidate maintained camera and window focus throughout.
            </div>
          ) : (
            <div style={{ maxHeight: 220, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 8 }}>
              {session.integrity_events.map((ev) => (
                <div key={ev.id} style={{ fontSize: 12, padding: '10px 12px', background: '#ffebee', border: '1px solid #ffcdd2', borderRadius: 6, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <span style={{ color: 'var(--danger)', fontWeight: 700, display: 'block' }}>
                      {ev.event_type.replace('_', ' ').toUpperCase()} (Severity: {ev.severity})
                    </span>
                    <span style={{ color: 'var(--text-secondary)', fontSize: 11 }}>
                      {ev.metadata_info?.reason || 'Event timestamped during questioning'}
                    </span>
                  </div>
                  <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>{new Date(ev.timestamp).toLocaleTimeString()}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Adaptive Questions & Evidence Quotes Breakdown */}
      <div className="card" style={{ marginBottom: 24 }}>
        <h3 style={{ fontSize: 18, fontWeight: 700, marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
          <Award size={18} color="var(--sage-accent)" /> Adaptive Questions & Evidence Log
        </h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
          {session.questions.map((q) => (
            <div key={q.id} style={{ border: '1px solid var(--border-light)', borderRadius: 10, padding: 20, backgroundColor: 'var(--bg-subtle)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                <span style={{ fontWeight: 700, color: 'var(--sage-accent)' }}>
                  Question {q.order_index} • Competency: {q.competency_tested}
                </span>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  {q.rubric_scores?.is_real_llm ? (
                    <span className="badge badge-success" style={{ fontSize: 11 }}>
                      ✓ {q.rubric_scores.evaluator || 'Live Gemini'}
                    </span>
                  ) : (
                    <span className="badge badge-warning" style={{ fontSize: 11 }} title="Configure GEMINI_API_KEY in backend/.env for real Gemini evaluation">
                      Algorithmic Baseline
                    </span>
                  )}
                  <span className="badge badge-info">{q.difficulty_level}</span>
                  {q.score !== null && q.score !== undefined && (
                    <span className="badge badge-success">Score: {q.score}/10</span>
                  )}
                </div>
              </div>
              <p style={{ fontSize: 15, marginBottom: 14, lineHeight: 1.5, color: 'var(--text-primary)' }}>{q.question_text}</p>
              
              <div style={{ background: '#ffffff', border: '1px solid var(--border-light)', padding: 14, borderRadius: 8, marginBottom: 12, fontSize: 13 }}>
                <div style={{ color: 'var(--text-muted)', fontSize: 11, marginBottom: 4, letterSpacing: '0.05em' }}>CANDIDATE RESPONSE:</div>
                <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.5, color: 'var(--text-primary)' }}>{q.candidate_answer || '<Pending Candidate Response>'}</div>
              </div>

              {q.evidence_quote && (
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, color: 'var(--sage-hover)', fontSize: 13, marginTop: 8 }}>
                  <Quote size={15} style={{ flexShrink: 0, marginTop: 2 }} />
                  <div><strong>Evidence Quote:</strong> "{q.evidence_quote}"</div>
                </div>
              )}

              {q.adaptation_reason && (
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 6 }}>
                  Engine Rationale: {q.adaptation_reason} (Confidence: {q.confidence_level || 'High'})
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Human Recruiter Review & Decision */}
      <div className="card" style={{ border: '1px solid var(--sage-accent)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
          <UserCheck size={22} color="var(--sage-accent)" />
          <h3 style={{ fontSize: 18, fontWeight: 700 }}>Human Recruiter Final Hiring Decision</h3>
        </div>
        <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 20 }}>
          All AI evaluations provide evidence-based recommendations, but final hiring authority is exclusively reserved for you. Record your final decision below.
        </p>

        {decisionNotice && (
          <div style={{
            padding: 14,
            borderRadius: 8,
            marginBottom: 20,
            fontSize: 13,
            backgroundColor: decisionNotice.type === 'success' ? '#e8f5e9' : decisionNotice.type === 'warning' ? '#fff3e0' : '#ffebee',
            border: `1px solid ${decisionNotice.type === 'success' ? '#c8e6c9' : decisionNotice.type === 'warning' ? '#ffe0b2' : '#ffcdd2'}`,
            color: decisionNotice.type === 'success' ? 'var(--success)' : decisionNotice.type === 'warning' ? 'var(--warning)' : 'var(--danger)'
          }}>
            {decisionNotice.text}
          </div>
        )}

        <form onSubmit={handleSaveDecision} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div>
            <label style={{ display: 'block', fontSize: 13, marginBottom: 6, color: 'var(--text-secondary)' }}>Final Decision</label>
            <select value={decision} onChange={(e) => setDecision(e.target.value)} style={{ width: '100%', maxWidth: 320 }}>
              <option value="Selected">Selected (Extend Offer)</option>
              <option value="Rejected">Rejected</option>
              <option value="Under Review">Under Review (Committee Review)</option>
              <option value="On Hold">On Hold (Pending Pool Evaluation)</option>
            </select>
          </div>
          <div>
            <label style={{ display: 'block', fontSize: 13, marginBottom: 6, color: 'var(--text-secondary)' }}>
              Approved Candidate Feedback <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>(Shared with candidate on their dashboard & email)</span>
            </label>
            <textarea
              rows={3}
              value={candidateFeedback}
              onChange={(e) => setCandidateFeedback(e.target.value)}
              placeholder="Constructive feedback to share directly with the candidate..."
              style={{ width: '100%' }}
            />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: 13, marginBottom: 6, color: 'var(--text-secondary)' }}>
              Internal Recruiter Notes & Justification <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>(Confidential — visible only to recruiters)</span>
            </label>
            <textarea
              rows={4}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Record internal justification, interviewer observations, or confidential notes..."
              style={{ width: '100%' }}
            />
          </div>
          <button type="submit" disabled={savingDecision} className="btn btn-primary" style={{ alignSelf: 'flex-start' }}>
            {savingDecision ? 'Saving...' : 'Record Final Decision'}
          </button>
        </form>
      </div>
    </div>
  );
};
