export interface HealthStatus {
  status: string;
  project_name: string;
  environment: string;
  database_connected: boolean;
  llm_configured: boolean;
  timestamp: string;
}

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: 'recruiter' | 'candidate' | 'admin';
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface CandidateApplication {
  id: number;
  full_name: string;
  email: string;
  target_role?: string;
  resume_filename?: string;
  extracted_skills: string[];
  extracted_experience: string[];
  extracted_education: string[];
  has_enrolled_face: boolean;
  enrolled_at?: string;
  created_at: string;
}

export interface CandidateInterviewScheduleItem {
  id: number;
  session_token: string;
  job_title: string;
  status: string;
  scheduled_start?: string;
  scheduled_end?: string;
  window_status: 'upcoming' | 'too_early' | 'open' | 'expired';
  identity_verified: boolean;
  interview_url: string;
  decision_status?: 'Selected' | 'Rejected' | 'Decision Pending' | 'On Hold';
  decision_at?: string;
  candidate_feedback?: string;
  created_at: string;
}

export interface JobDescription {
  id: number;
  title: string;
  department?: string;
  raw_text: string;
  required_competencies: Array<{
    name: string;
    weight: number;
    description: string;
  }>;
  experience_level: string;
  created_at: string;
}

export interface CandidateSummary {
  id: number;
  full_name: string;
  email: string;
  target_role?: string;
  resume_filename?: string;
  extracted_skills: string[];
  has_enrolled_face: boolean;
  enrolled_at?: string;
  created_at: string;
}

export interface InterviewSessionSummary {
  id: number;
  session_token: string;
  candidate_name: string;
  candidate_email: string;
  job_title: string;
  status: 'setup' | 'scheduled' | 'in_progress' | 'completed' | 'evaluated';
  scheduled_start?: string;
  scheduled_end?: string;
  invitation_email_status?: string;
  identity_verified: boolean;
  final_score?: number;
  final_recommendation?: string;
  recruiter_decision?: string;
  created_at: string;
  questions_count: number;
  integrity_events_count: number;
}

export interface QuestionDetail {
  id: number;
  order_index: number;
  question_text: string;
  competency_tested: string;
  difficulty_level: string;
  candidate_answer?: string;
  score?: number;
  rubric_scores?: {
    technical_accuracy?: number;
    depth_of_knowledge?: number;
    clarity_of_communication?: number;
    evaluator?: string;
    is_real_llm?: boolean;
    source?: string;
    notice?: string;
  };
  strengths: string[];
  weaknesses: string[];
  evidence_quote?: string;
  confidence_level?: string;
  adaptation_reason?: string;
  question_type?: 'open_ended' | 'multiple_choice' | 'fill_blank' | string;
  options?: string[];
  answer_mode?: 'typed' | 'voice' | 'mcq' | string;
  voice_transcript?: string;
  answered_at?: string;
}

export interface IntegrityEvent {
  id: number;
  event_type: string;
  severity: string;
  confidence?: number;
  metadata_info?: any;
  screenshot_base64?: string;
  timestamp: string;
}

export interface InterviewSessionDetail {
  id: number;
  session_token: string;
  status: string;
  scheduled_start?: string;
  scheduled_end?: string;
  invitation_email_status?: string;
  identity_verified: boolean;
  identity_verification_details?: any;
  current_difficulty: string;
  final_score?: number;
  final_recommendation?: string;
  recruiter_decision?: string;
  recruiter_notes?: string;
  candidate_feedback?: string;
  decision_at?: string;
  decision_notification_status?: string;
  decision_notification_error?: string;
  skill_gap_analysis?: {
    match_percentage: number;
    demonstrated: string[];
    claimed_unvalidated: string[];
    not_demonstrated: string[];
    not_assessed: string[];
    matching_skills: string[];
    missing_skills: string[];
    recommendation: string;
  };
  evidence_report?: {
    candidate_name: string;
    candidate_email: string;
    job_title: string;
    summary: string;
    recommendation: string;
    identity_verified: boolean;
    integrity_events_count: number;
    demonstrated_count: number;
    unvalidated_count: number;
    gap_count: number;
    generated_at: string;
  };
  candidate: {
    id: number;
    full_name: string;
    email: string;
    target_role?: string;
    extracted_skills: string[];
    has_enrolled_face: boolean;
  };
  job: JobDescription;
  questions: QuestionDetail[];
  integrity_events: IntegrityEvent[];
}

export interface CandidateInterviewView {
  session_token: string;
  status: string;
  scheduled_start?: string;
  scheduled_end?: string;
  time_window_check: {
    allowed: boolean;
    reason: string;
    scheduled_start?: string;
  };
  candidate_name: string;
  has_enrolled_reference: boolean;
  identity_verified: boolean;
  job_title: string;
  total_questions_completed: number;
  active_question?: {
    id: number;
    order_index: number;
    question_text: string;
    competency_tested: string;
    difficulty_level: string;
    question_type?: 'open_ended' | 'multiple_choice' | 'fill_blank' | string;
    options?: string[];
  };
}
