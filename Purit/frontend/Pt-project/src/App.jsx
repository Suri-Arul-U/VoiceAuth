import React from "react";
import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import AttendanceDashboard from "./pages/AttendanceDashboard";
import VoiceProfiles from "./pages/VoiceProfiles";
import "./App.css";

export default function App() {
  return (
    <BrowserRouter>
      <div className="nav-header">
        <Link to="/attendance-dashboard" className="nav-link">Dashboard</Link>
        <Link to="/voice-profiles" className="nav-link">Voice Profiles</Link>
      </div>

      <Routes>
        <Route path="/" element={<AttendanceDashboard />} />
        <Route path="/attendance-dashboard" element={<AttendanceDashboard />} />
        <Route path="/voice-profiles" element={<VoiceProfiles />} />
      </Routes>
    </BrowserRouter>
  );
}
