import axios from 'axios';
import type {
  HealthStatus,
  AuthResponse,
  User,
  JobDescription,
  CandidateSummary,
  CandidateApplication,
  CandidateInterviewScheduleItem,
  InterviewSessionSummary,
  InterviewSessionDetail,
  CandidateInterviewView
} from '../types';

const getBaseUrl = (): string => {
  if (import.meta.env.VITE_API_URL) {
    return import.meta.env.VITE_API_URL;
  }
  // When hosted on Render or any external cloud host, point to the live Render backend API
  if (typeof window !== 'undefined' && window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
    return 'https://adaptive-interview-learning.onrender.com/api';
  }
  // Local development default (Vite proxy)
  return '/api';
};

const api = axios.create({
  baseURL: getBaseUrl(),
  headers: {
    'Content-Type': 'application/json'
  }
});

// Intercept to add token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const apiClient = {
  // Health
  getHealth: async (): Promise<HealthStatus> => {
    const res = await api.get<HealthStatus>('/health');
    return res.data;
  },

  // Auth
  register: async (userData: { email: string; password: string; full_name: string; role?: string }): Promise<AuthResponse> => {
    const res = await api.post<AuthResponse>('/auth/register', userData);
    return res.data;
  },

  login: async (credentials: { email: string; password: string }): Promise<AuthResponse> => {
    const res = await api.post<AuthResponse>('/auth/login', credentials);
    return res.data;
  },

  getMe: async (): Promise<User> => {
    const res = await api.get<User>('/auth/me');
    return res.data;
  },

  // Candidate Portal Operations
  getCandidateProfile: async (): Promise<CandidateApplication> => {
    const res = await api.get<CandidateApplication>('/candidate-portal/profile');
    return res.data;
  },

  submitCandidateApplication: async (formData: FormData): Promise<{ message: string; candidate: CandidateApplication }> => {
    const res = await api.post<{ message: string; candidate: CandidateApplication }>('/candidate-portal/application', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    return res.data;
  },

  enrollFace: async (faceImageBase64: string): Promise<{ status: string; message: string; metadata: any }> => {
    const res = await api.post('/candidate-portal/enroll-face', { face_image_base64: faceImageBase64 });
    return res.data;
  },

  getCandidateInterviews: async (): Promise<CandidateInterviewScheduleItem[]> => {
    const res = await api.get<CandidateInterviewScheduleItem[]>('/candidate-portal/interviews');
    return res.data;
  },

  // Recruiter Portal Operations
  createJob: async (jobData: { title: string; department?: string; raw_text: string; experience_level?: string }): Promise<JobDescription> => {
    const res = await api.post<JobDescription>('/recruitment/jobs', jobData);
    return res.data;
  },

  getJobs: async (): Promise<JobDescription[]> => {
    const res = await api.get<JobDescription[]>('/recruitment/jobs');
    return res.data;
  },

  getCandidates: async (): Promise<CandidateSummary[]> => {
    const res = await api.get<CandidateSummary[]>('/recruitment/candidates');
    return res.data;
  },

  scheduleInterview: async (data: { candidate_id: number; job_description_id: number; scheduled_start: string }): Promise<any> => {
    const res = await api.post('/recruitment/sessions/schedule', data);
    return res.data;
  },

  getSessions: async (): Promise<InterviewSessionSummary[]> => {
    const res = await api.get<InterviewSessionSummary[]>('/recruitment/sessions');
    return res.data;
  },

  getSessionDetail: async (id: number): Promise<InterviewSessionDetail> => {
    const res = await api.get<InterviewSessionDetail>(`/recruitment/sessions/${id}`);
    return res.data;
  },

  updateDecision: async (sessionId: number, decision: { recruiter_decision: string; recruiter_notes?: string; candidate_feedback?: string }): Promise<{ message: string; decision: string; decision_at?: string; candidate_feedback?: string; email_delivery?: any }> => {
    const res = await api.patch(`/recruitment/sessions/${sessionId}/decision`, decision);
    return res.data;
  },

  rescheduleInterview: async (sessionId: number, newScheduledStart: string): Promise<any> => {
    const res = await api.patch(`/recruitment/sessions/${sessionId}/reschedule`, { new_scheduled_start: newScheduledStart });
    return res.data;
  },

  deleteInterview: async (sessionId: number): Promise<{ message: string; session_id: number }> => {
    const res = await api.delete(`/recruitment/sessions/${sessionId}`);
    return res.data;
  },

  // Candidate Interview Engine Client
  getCandidateInterview: async (token: string): Promise<CandidateInterviewView> => {
    const res = await api.get<CandidateInterviewView>(`/interview/${token}`);
    return res.data;
  },

  verifyIdentityProbe: async (token: string, probeFrameBase64: string, idCardFrameBase64?: string): Promise<{ verified: boolean; message: string; similarity_score?: number; verification_details?: any; first_question?: any }> => {
    const res = await api.post(`/interview/${token}/verify-identity`, { 
      probe_frame_base64: probeFrameBase64,
      id_card_frame_base64: idCardFrameBase64 
    });
    return res.data;
  },

  submitAnswer: async (
    token: string,
    answerText: string,
    options?: {
      answerMode?: 'typed' | 'voice' | 'mcq' | string;
      selectedOption?: string;
      voiceTranscript?: string;
    }
  ): Promise<any> => {
    const res = await api.post(`/interview/${token}/submit-answer`, {
      answer_text: answerText,
      answer_mode: options?.answerMode || 'typed',
      selected_option: options?.selectedOption,
      voice_transcript: options?.voiceTranscript
    });
    return res.data;
  },

  logIntegrityEvent: async (
    token: string,
    eventType: string,
    severity?: string,
    confidence?: number,
    metadata?: any,
    frameBase64?: string
  ): Promise<any> => {
    const res = await api.post(`/interview/${token}/integrity-event`, {
      event_type: eventType,
      severity: severity || 'low',
      confidence: confidence || 1.0,
      metadata_info: metadata,
      frame_base64: frameBase64
    });
    return res.data;
  },

  // Recruiter System Diagnostics
  getSystemStatus: async (): Promise<{ database_connected: boolean; llm_provider: string; llm_configured: boolean; llm_status_message: string }> => {
    const res = await api.get('/system/status');
    return res.data;
  }
};
