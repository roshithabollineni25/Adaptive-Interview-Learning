import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { LandingPage } from './pages/LandingPage';
import { AuthPage } from './pages/AuthPage';
import { CandidateAuthPage } from './pages/CandidateAuthPage';
import { CandidateDashboard } from './pages/CandidateDashboard';
import { RecruiterDashboard } from './pages/RecruiterDashboard';
import { SessionDetail } from './pages/SessionDetail';
import { CandidateInterviewExperience } from './pages/CandidateInterviewExperience';

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
        <Routes>
          {/* Public Landing Page */}
          <Route path="/" element={<LandingPage />} />
          
          {/* Recruiter Portal Routes */}
          <Route path="/login" element={<AuthPage />} />
          <Route path="/recruiter" element={<RecruiterDashboard />} />
          <Route path="/recruiter/sessions/:id" element={<SessionDetail />} />

          {/* Candidate Portal Routes */}
          <Route path="/candidate/login" element={<CandidateAuthPage />} />
          <Route path="/candidate/dashboard" element={<CandidateDashboard />} />
          
          {/* Candidate Secure Interview Gateway & Active Experience */}
          <Route path="/interview/:token" element={<CandidateInterviewExperience />} />
          
          {/* Catch-all redirect to public landing */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
};

export default App;
