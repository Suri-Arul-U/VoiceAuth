// AttendanceDashboard.jsx
import React, { useState, useEffect, useRef } from "react";
import axios from "axios";
import "../styles/AttendanceDashboard.css";

const API = "http://127.0.0.1:8000";

const AttendanceDashboard = () => {
  const [classes, setClasses] = useState([]);
  const [expandedClass, setExpandedClass] = useState(null);
  const [classStudents, setClassStudents] = useState({});
  const [showAddClass, setShowAddClass] = useState(false);
  const [newClass, setNewClass] = useState({ class_name: "", department: "" });
  const [recordingStatus, setRecordingStatus] = useState("");
  const [activeClass, setActiveClass] = useState(null);
  const [updates, setUpdates] = useState([]);
  const [recordStates, setRecordStates] = useState({});
  const [currentHighlight, setCurrentHighlight] = useState(null);  // 🔥 highlight active voices
  const pollIntervalRef = useRef(null);
  const highlightTimerRef = useRef(null);
  const [highlightIndex, setHighlightIndex] = useState(0);


  
  useEffect(() => {
    fetchClasses();
  }, []);

  const fetchClasses = async () => {
    try {
      const res = await axios.get(`${API}/classes`);
      setClasses(res.data || []);
    } catch (err) {
      console.error("Error fetching classes:", err);
    }
  };

  const toggleClassExpand = async (classId) => {
    if (expandedClass === classId) {
      setExpandedClass(null);
      return;
    }
    try {
      const res = await axios.get(`${API}/classes/${classId}/students`);
      const students = res.data.students || [];
      setClassStudents((prev) => ({ ...prev, [classId]: students }));
      setExpandedClass(classId);
    } catch (err) {
      console.error("Error loading class students:", err);
    }
  };

  const handleAddClass = async () => {
    try {
      await axios.post(`${API}/classes`, newClass);
      setShowAddClass(false);
      setNewClass({ class_name: "", department: "" });
      await fetchClasses();
    } catch (err) {
      console.error("Error adding class:", err);
    }
  };

  // ---------------------------
  // Record / Pause / Resume / Finish Attendance
  // ---------------------------
const handleRecordControl = async (className, classId) => {
  if (!className) return alert("Class name missing!");
  setActiveClass(classId);

  const currentState = recordStates[classId] || "idle";

  try {
    // ---------------- START RECORDING ----------------
    if (currentState === "idle") {
      setRecordStates((prev) => ({ ...prev, [classId]: "recording" }));
      setRecordingStatus(`🎙️ Recording started for ${className}...`);
      await axios.post(`${API}/attendance/start/${className}`);

      // reset highlight index for that class
      setHighlightIndex(0);

      // --- clear any existing poll ---
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }

      // --- start backend polling every 1s ---
      pollIntervalRef.current = setInterval(async () => {
        try {
          const statusRes = await axios.get(`${API}/attendance/status/${className}`);
          const sessionStatus = statusRes.data.status;

          if (sessionStatus === "completed") {
            clearInterval(pollIntervalRef.current);
            pollIntervalRef.current = null;

            // final finish call
            let results = [];
            try {
              const finishRes = await axios.post(`${API}/attendance/finish/${className}`);
              results = finishRes.data.results || [];
            } catch (finishErr) {
              console.error("Finish failed:", finishErr);
            }

            if (results.length > 0) {
              const updatedStudents = results.map((stu) => ({
                ...stu,
                status: stu.status || (stu.confidence >= 85 ? "Present" : "Absent"),
                checkins: (stu.checkins || 0) + 1,
                date: new Date().toLocaleDateString(),
                time: new Date().toLocaleTimeString(),
                feedback: "",
              }));
              setClassStudents((prev) => ({ ...prev, [classId]: updatedStudents }));
              setUpdates(updatedStudents);
            }

            setRecordStates((prev) => ({ ...prev, [classId]: "completed" }));
            setRecordingStatus(`✅ Attendance completed for ${className}`);

            // stop highlight timer too
            if (highlightTimerRef.current) {
              clearInterval(highlightTimerRef.current);
              highlightTimerRef.current = null;
            }
            setHighlightIndex(0);
            await fetchClasses();
            return;
          } else if (sessionStatus === "paused") {
            setRecordingStatus(`⏸️ Attendance paused for ${className}`);
          } else {
            // polling partials
            try {
              const tempRes = await axios.get(`${API}/attendance/temp/${className}`);
              const partial = tempRes.data.results || [];

              if (partial.length > 0) {
                setClassStudents((prev) => {
                  const prevClass = prev[classId] || [];
                  const merged = prevClass.map((s) => {
                    const update = partial.find((p) => p.student_id === s.student_id);
                    return update ? { ...s, ...update } : s;
                  });
                  return { ...prev, [classId]: merged };
                });
              }
            } catch (tempErr) {
              console.warn("Temp fetch failed:", tempErr);
            }
            setRecordingStatus(`🎙️ Attendance in progress for ${className}...`);
          }
        } catch (err) {
          console.error("Polling error:", err);
          if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current);
            pollIntervalRef.current = null;
          }
        }
      }, 1000); // poll every 1 second

      // --- start highlight timer (sequential every 4s) ---
      if (highlightTimerRef.current) {
        clearInterval(highlightTimerRef.current);
        highlightTimerRef.current = null;
      }

      // Immediately highlight the first student
      setHighlightIndex(1);

      highlightTimerRef.current = setInterval(() => {
        setHighlightIndex((prev) => {
          const students = classStudents[classId] || [];
          if (students.length === 0) return 0;
          if (prev >= students.length) {
            clearInterval(highlightTimerRef.current);
            highlightTimerRef.current = null;
            return prev;
          }
          return prev + 1;
        });
      }, 7400);
    }

    // ---------------- PAUSE ----------------
    else if (currentState === "recording") {
      setRecordStates((prev) => ({ ...prev, [classId]: "paused" }));
      setRecordingStatus(`⏸️ Paused attendance for ${className}`);
      await axios.post(`${API}/attendance/pause/${className}`);

      // pause both timers
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
      if (highlightTimerRef.current) {
        clearInterval(highlightTimerRef.current);
        highlightTimerRef.current = null;
      }
    }

    // ---------------- RESUME ----------------
    else if (currentState === "paused") {
      setRecordStates((prev) => ({ ...prev, [classId]: "recording" }));
      setRecordingStatus(`▶️ Resumed attendance for ${className}`);
      await axios.post(`${API}/attendance/resume/${className}`);

      // restart polling
      if (!pollIntervalRef.current) {
        pollIntervalRef.current = setInterval(async () => {
          try {
            const statusRes = await axios.get(`${API}/attendance/status/${className}`);
            const sessionStatus = statusRes.data.status;

            if (sessionStatus === "completed") {
              clearInterval(pollIntervalRef.current);
              pollIntervalRef.current = null;
            } else {
              try {
                const tempRes = await axios.get(`${API}/attendance/temp/${className}`);
                const partial = tempRes.data.results || [];
                if (partial.length > 0) {
                  setClassStudents((prev) => {
                    const prevClass = prev[classId] || [];
                    const merged = prevClass.map((s) => {
                      const update = partial.find((p) => p.student_id === s.student_id);
                      return update ? { ...s, ...update } : s;
                    });
                    return { ...prev, [classId]: merged };
                  });
                }
              } catch (tempErr) {
                console.warn("Temp fetch failed:", tempErr);
              }
            }
          } catch (err) {
            console.error("Polling error:", err);
            if (pollIntervalRef.current) {
              clearInterval(pollIntervalRef.current);
              pollIntervalRef.current = null;
            }
          }
        }, 1000);
      }

      // restart highlight timer
      if (!highlightTimerRef.current) {
        highlightTimerRef.current = setInterval(() => {
          setHighlightIndex((prev) => {
            const students = classStudents[classId] || [];
            if (students.length === 0) return 0;
            if (prev >= students.length) {
              clearInterval(highlightTimerRef.current);
              highlightTimerRef.current = null;
              return prev;
            }
            return prev + 1;
          });
        }, 4000);
      }
    }

    // ---------------- COMPLETED ----------------
    else if (currentState === "completed") {
      // ensure timers cleared
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
      if (highlightTimerRef.current) {
        clearInterval(highlightTimerRef.current);
        highlightTimerRef.current = null;
      }
      setHighlightIndex(0);
      await handleUpdate();
    }
  } catch (err) {
    console.error("❌ Attendance control error:", err);
    setRecordingStatus("❌ Failed to perform action");
  }
};



// ---------------------------
// Handle feedback dropdown (added back)
// ---------------------------
const handleFeedbackChange = async (studentId, value) => {
  try {
    // 1️⃣ Immediately update UI feedback state
    setClassStudents((prev) => {
      const copy = { ...prev };
      for (const classKey of Object.keys(copy)) {
        copy[classKey] = copy[classKey].map((s) =>
          s.student_id === studentId ? { ...s, feedback: value, _feedbackAck: value } : s
        );
      }
      return copy;
    });

    setUpdates((prev) =>
      prev.map((u) => (u.student_id === studentId ? { ...u, feedback: value } : u))
    );

    // 2️⃣ Send feedback to backend
    const res = await axios.post(`${API}/feedback`, {
      student_id: studentId,
      audio_path: "",
      verified: value === "Correct",
    });

    // 3️⃣ Show success message briefly
    if (res?.data?.message) {
      setRecordingStatus(`📩 ${res.data.message}`);
    } else {
      setRecordingStatus("✅ Feedback recorded successfully!");
    }

    // Keep visible for a few seconds
    setTimeout(() => setRecordingStatus(""), 4000);
  } catch (err) {
    console.error("❌ Feedback error:", err);
    alert("❌ Failed to send feedback");
  }
};




  // ---------------------------
  // Send attendance updates to backend
  // ---------------------------
  const handleUpdate = async () => {
    if (!updates || updates.length === 0) return alert("No updates to send!");

    try {
      const res = await axios.post(`${API}/attendance/update`, updates, {
        headers: { "Content-Type": "application/json" },
      });

      if (res.status === 200 || res.data?.message) {
        alert("✅ Attendance successfully updated in database!");
        setUpdates([]);
        setActiveClass(null);
        setRecordStates((prev) => ({ ...prev, [activeClass]: "idle" }));
        await fetchClasses();
        if (expandedClass) await toggleClassExpand(expandedClass);
      } else {
        throw new Error("Update failed");
      }
    } catch (err) {
      console.error("❌ Failed to update attendance:", err);
      alert("❌ Failed to update attendance on server");
    }
  };

  const getButtonLabel = (classId) => {
    const state = recordStates[classId] || "idle";
    switch (state) {
      case "recording":
        return "Pause";
      case "paused":
        return "Resume";
      case "completed":
        return "Update";
      default:
        return "Record";
    }
  };

  // ---------------------------
  // Render UI
  // ---------------------------
  return (
    <div className="dashboard-container">
      <h1 className="dashboard-title">Attendance Tracking</h1>
      <p className="dashboard-subtitle">Voice-based automated attendance for each class</p>

      {/* Stats */}
      <div className="stats-grid">
        <div className="stat-card">
          <p className="stat-title">Recorded Classes</p>
          <h2 className="stat-value purple">
            {classes.filter((c) => c.status === "Recorded").length}
          </h2>
        </div>
        <div className="stat-card">
          <p className="stat-title">Avg Confidence</p>
          <h2 className="stat-value green">
            {Math.round(
              classes.reduce((sum, c) => sum + (c.confidence || 0), 0) / (classes.length || 1)
            )}
            %
          </h2>
        </div>
        <div className="stat-card">
          <p className="stat-title">System</p>
          <h2 className="stat-value blue">Online</h2>
        </div>
      </div>

      {/* Actions */}
      <div className="action-buttons">
        <button className="btn btn-green" onClick={() => setShowAddClass(true)}>
          Add Class
        </button>
        <button className="btn btn-purple" onClick={fetchClasses}>
          Refresh
        </button>
      </div>

      {/* Recording status */}
      {recordingStatus && (
        <div className="record-status" style={{ marginTop: 10 }}>
          <strong>{recordingStatus}</strong>
        </div>
      )}

      {/* --- Class Cards + Student Cards --- */}
      <div className="class-list">
        {classes.length > 0 ? (
          classes.map((cls) => {
            const isExpanded = expandedClass === cls._id;
            return (
              <div key={cls._id} className="class-card-row">
                <div
                  className={`class-header-card ${
                    activeClass === cls._id ? "active-row" : ""
                  }`}
                  onClick={() => toggleClassExpand(cls._id)}
                >
                  <div className="class-left">
                    <div className="class-title-block">
                      <h3 className="class-title">{cls.class_name}</h3>
                      <span className="class-dept-tag">{cls.department}</span>
                    </div>
                    <div className="class-subinfo">
                      <div className="info-item">📅 {cls.date || "-"}</div>
                      <div className="info-item">⏰ {cls.time || "-"}</div>
                      <div className="info-item">
                        🎯 {cls.confidence ? `${cls.confidence.toFixed(0)}%` : "N/A"}
                      </div>
                    </div>
                  </div>
                  <div className="class-right">
                    <button
                      className="btn btn-purple"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleRecordControl(cls.class_name, cls._id);
                      }}
                    >
                      {getButtonLabel(cls._id)}
                    </button>
                  </div>
                </div>

                {isExpanded && classStudents[cls._id] && (
  <div className="student-list">
    {/* <div className="student-list-label">
      🎤 <strong>Voice Profiles Detected</strong>
    </div> */}
        {/* Fixed Header Row */}
    <div className="student-list-header">
      <div className="student-field sno">#</div>
      <div className="student-field name">Name</div>
      <div className="student-field usn">USN</div>
      <div className="student-field date">Date</div>
      <div className="student-field time">Time</div>
      <div className="student-field checkins">Check-ins</div>
      <div className="student-field confidence">Confidence</div>
      <div className="student-field status">Status</div>
      <div className="student-field feedback">Feedback</div>
    </div>

    {/* Student Cards */}

    {classStudents[cls._id].map((stu, idx) => {

                      const isHighlighted = idx === highlightIndex - 1 || currentHighlight === stu.student_id;
                      return (
                        <div
                          key={stu.student_id}
                          className={`student-card ${isHighlighted ? "highlighted" : ""}`}
                        >
                          <div className="student-card-row">
                            <div className="student-field sno">{idx + 1}</div>
                            <div className="student-field name">{stu.name}</div>
                            <div className="student-field usn">{stu.student_id}</div>
                            <div className="student-field date">{stu.date || "-"}</div>
                            <div className="student-field time">{stu.time || "-"}</div>
                            <div className="student-field checkins">{stu.checkins || 0}</div>
                            <div className="student-field confidence">
                              {stu.confidence ? `${stu.confidence.toFixed(2)}%` : "0%"}
                            </div>
                            <div
                              className={`student-field status ${
                                stu.status === "Present" ? "present" : "absent"
                              }`}
                            >
                              {stu.status || "Not Marked"}
                            </div>
                            <div className="student-field feedback">
                              <select
                                value={stu.feedback || ""}
                                onChange={(e) =>
                                  handleFeedbackChange(stu.student_id, e.target.value)
                                }
                              >
                                <option value="">Select</option>
                                <option value="Correct">Correct</option>
                                <option value="Incorrect">Incorrect</option>
                              </select>
                              {stu._feedbackAck && (
                                <span
                                  className={
                                    stu._feedbackAck === "Correct"
                                      ? "feedback-correct"
                                      : "feedback-incorrect"
                                  }
                                >
                                  {stu._feedbackAck === "Correct"
                                    ? "✅ Verified"
                                    : "❌ Incorrect"}
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })
        ) : (
          <p className="no-classes">No classes available.</p>
        )}
      </div>

{showAddClass && (
  <div className="add-class-overlay">
    <div className="add-class-modal">
      <h2 className="add-class-title">Create a New Class</h2>
      <p className="add-class-subtitle">
        Enter details below to register a new class for attendance tracking.
      </p>

      <div className="add-class-form">
        <label>Class Name</label>
        <input
          type="text"
          placeholder="e.g. 3rd Year Section A"
          value={newClass.class_name}
          onChange={(e) =>
            setNewClass({ ...newClass, class_name: e.target.value })
          }
        />

<label>Department</label>
<select
  value={newClass.department}
  onChange={(e) =>
    setNewClass({ ...newClass, department: e.target.value })
  }
  className="add-class-select"
>
  <option value="">Select Department</option>
  <option value="CSE">Computer Science and Engineering</option>
  <option value="AI">Artificial Intelligence</option>
  <option value="ECE">Electronics and Communication Engineering</option>
  <option value="EEE">Electrical and Electronics Engineering</option>
  <option value="MECH">Mechanical Engineering</option>
  <option value="MINING">Mining Engineering</option>
</select>

      </div>

      <div className="add-class-actions">
        <button className="btn-create" onClick={handleAddClass}>
          Create Class
        </button>
        <button className="btn-cancel" onClick={() => setShowAddClass(false)}>
          Cancel
        </button>
      </div>
    </div>
  </div>
)}

    </div>
  );
};

export default AttendanceDashboard;
