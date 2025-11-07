// VoiceProfiles.jsx
import React, { useEffect, useState } from "react";
import axios from "axios";
import "./VoiceProfiles.css";

const API_BASE = "http://127.0.0.1:8000";

const VoiceProfiles = () => {
  const [profiles, setProfiles] = useState([]);
  const [form, setForm] = useState({
    fullName: "",
    usn: "",
    department: "",
    class_name: "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showModal, setShowModal] = useState(false);
  const [recording, setRecording] = useState(false);
  const [audioBlob, setAudioBlob] = useState(null);
  const [recorder, setRecorder] = useState(null);

  // Fetch existing profiles
  const fetchProfiles = async () => {
    try {
      const res = await axios.get(`${API_BASE}/profiles`);
      setProfiles(res.data);
    } catch (err) {
      console.error("Failed to fetch profiles:", err);
      setError("Failed to load profiles");
    }
  };

  useEffect(() => {
    fetchProfiles();
  }, []);

  // Handle input change
  const handleChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  // Recording logic
  const handleRecord = async () => {
    try {
      if (recording && recorder) {
        recorder.stop();
        setRecording(false);
        return;
      }

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      const chunks = [];

      mediaRecorder.ondataavailable = (e) => chunks.push(e.data);
      mediaRecorder.onstop = () => {
        const blob = new Blob(chunks, { type: "audio/wav" });
        setAudioBlob(blob);
        stream.getTracks().forEach((t) => t.stop());
      };

      mediaRecorder.start();
      setRecorder(mediaRecorder);
      setRecording(true);

      // auto-stop after 5s
      setTimeout(() => {
        if (mediaRecorder.state === "recording") {
          mediaRecorder.stop();
          setRecording(false);
        }
      }, 5000);
    } catch (err) {
      console.error("Recording error:", err);
      alert("Microphone access denied or not available.");
    }
  };

  // Submit profile (FormData)
  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.fullName || !form.usn || !form.department || !form.class_name) {
      setError("⚠️ Please fill all fields before submitting.");
      return;
    }

    try {
      setLoading(true);
      const formData = new FormData();
      formData.append("fullName", form.fullName);
      formData.append("usn", form.usn);
      formData.append("department", form.department);
      formData.append("class_name", form.class_name);
      if (audioBlob) {
        formData.append("audio", audioBlob, `${form.usn}.wav`);
      }

      await axios.post(`${API_BASE}/profiles`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      setForm({ fullName: "", usn: "", department: "", class_name: "" });
      setAudioBlob(null);
      setShowModal(false);
      fetchProfiles();
      alert("✅ Voice profile created successfully!");
    } catch (err) {
      console.error("Error creating profile:", err);
      setError(err.response?.data?.detail || "Error creating profile");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="voice-container">
      <div className="voice-wrapper">
        <div className="voice-header">
          <div>
            <h2>Voice Profile Management</h2>
            <p>Manage user voice profiles and link them with class records</p>
          </div>
          <button className="add-btn" onClick={() => setShowModal(true)}>
            + Add Profile
          </button>
        </div>

        <div className="voice-cards">
          {profiles.length === 0 ? (
            <p className="no-profiles">No voice profiles found.</p>
          ) : (
            <div className="voice-grid">
              {profiles.map((p, idx) => (
                <div key={idx} className="voice-card">
                  <div className="voice-card-header">
                    <h3>{p.name}</h3>
                    <span className="voice-status">Active</span>
                  </div>
                  <div className="voice-details">
                    <p>🏫 Class: {p.class_name || "N/A"}</p>
                    <p>🎓 Department: {p.department}</p>
                    <p>🆔 Voice ID: {p.voiceId}</p>
                    <small>⏰ Last Updated: {p.lastUpdated}</small>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {showModal && (
        <div className="modal-overlay">
          <div className="modal">
            <span className="close" onClick={() => setShowModal(false)}>
              ✖
            </span>

            <div className="modal-content-split">
              <div className="modal-left">
                <h3 className="modal-title">Create New Voice Profile</h3>
                <p className="modal-subtitle">
                  Add a new user voice profile for authentication and attendance tracking.
                </p>

                <button
                  type="button"
                  className={`record-btn ${recording ? "recording" : ""}`}
                  onClick={handleRecord}
                >
                  {recording ? "🎙 Recording..." : "🎤 Record Voice"}
                </button>

                {audioBlob && (
                  <audio controls src={URL.createObjectURL(audioBlob)} />
                )}
              </div>

              <div className="modal-vertical-line" />

              <div className="modal-right">
                <form onSubmit={handleSubmit}>
                  <label>Full Name</label>
                  <input
                    type="text"
                    name="fullName"
                    value={form.fullName}
                    onChange={handleChange}
                    placeholder="Enter name"
                  />

                  <label>USN</label>
                  <input
                    type="text"
                    name="usn"
                    value={form.usn}
                    onChange={handleChange}
                    placeholder="1GV22CS001"
                  />

                  <label>Department</label>
                  <input
                    type="text"
                    name="department"
                    value={form.department}
                    onChange={handleChange}
                    placeholder="e.g., CSE"
                  />

                  <label>Class Name</label>
                  <input
                    type="text"
                    name="class_name"
                    value={form.class_name}
                    onChange={handleChange}
                    placeholder="e.g., 6th Sem A"
                  />

                  {error && <p className="error-text">{error}</p>}

                  <button type="submit" className="submit" disabled={loading}>
                    {loading ? "Creating..." : "Create Profile"}
                  </button>
                </form>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default VoiceProfiles;
