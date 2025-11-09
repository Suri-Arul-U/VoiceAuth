// AttendanceDashboard.jsx
import React, { useState, useEffect } from "react";
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
  const [recordStates, setRecordStates] = useState({}); // {classId: idle|recording|paused|completed}

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
      if (currentState === "idle") {
        // 🎙️ Start recording
        setRecordStates((prev) => ({ ...prev, [classId]: "recording" }));
        setRecordingStatus(`🎙️ Recording started for ${className}...`);
        await axios.post(`${API}/attendance/start/${className}`);

        // 🔁 Poll backend every 4 seconds for updates
        const pollInterval = setInterval(async () => {
          try {
            const statusRes = await axios.get(`${API}/attendance/status/${className}`);
            const sessionStatus = statusRes.data.status;

            if (sessionStatus === "completed") {
              clearInterval(pollInterval);

              // ✅ Fetch final results from /attendance/finish
              let results = [];
              try {
                const finishRes = await axios.post(`${API}/attendance/finish/${className}`);
                results = finishRes.data.results || [];
              } catch (finishErr) {
                console.error("Finish failed:", finishErr);
                results = [];
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
              await fetchClasses();
            } else if (sessionStatus === "paused") {
              setRecordingStatus(`⏸️ Attendance paused for ${className}`);
            } else {
              // Fetch partial updates
              try {
                const tempRes = await axios.get(`${API}/attendance/temp/${className}`);
                const partial = tempRes.data.results || [];
                if (partial.length > 0) {
                  setClassStudents((prev) => ({ ...prev, [classId]: partial }));
                }
              } catch (tempErr) {
                console.warn("Temp fetch failed:", tempErr);
              }
              setRecordingStatus(`🎙️ Attendance in progress for ${className}...`);
            }
          } catch (err) {
            console.error("Polling error:", err);
            clearInterval(pollInterval);
          }
        }, 4000);
      }

      // ⏸️ Pause
      else if (currentState === "recording") {
        setRecordStates((prev) => ({ ...prev, [classId]: "paused" }));
        setRecordingStatus(`⏸️ Paused attendance for ${className}`);
        await axios.post(`${API}/attendance/pause/${className}`);
      }

      // ▶️ Resume
      else if (currentState === "paused") {
        setRecordStates((prev) => ({ ...prev, [classId]: "recording" }));
        setRecordingStatus(`▶️ Resumed attendance for ${className}`);
        await axios.post(`${API}/attendance/resume/${className}`);
      }

      // ✅ After completion → update
      else if (currentState === "completed") {
        await handleUpdate();
      }
    } catch (err) {
      console.error("❌ Attendance control error:", err);
      setRecordingStatus("❌ Failed to perform action");
    }
  };

  // ---------------------------
  // Handle feedback dropdown
  // ---------------------------
  const handleFeedbackChange = async (studentId, value) => {
    try {
      // Update UI state
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

      // Send feedback to backend
      const res = await axios.post(`${API}/feedback`, {
        student_id: studentId,
        audio_path: "",
        verified: value === "Correct",
      });

      if (res?.data?.message) {
        setRecordingStatus(res.data.message);
        setTimeout(() => setRecordingStatus(""), 2500);
      }
    } catch (err) {
      console.error("Feedback error:", err);
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

  // ---------------------------
  // Dynamic Button Label
  // ---------------------------
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

      {/* Classes Table */}
      <div className="records-container">
        <div className="records-header">
          <h3 className="records-title">Class Overview</h3>
        </div>

        <table className="records-table">
          <thead>
            <tr>
              <th>Class</th>
              <th>Department</th>
              <th>Date</th>
              <th>Time</th>
              <th>Confidence</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {classes.length > 0 ? (
              classes.map((cls) => {
                const state = recordStates[cls._id] || "idle";
                return (
                  <React.Fragment key={cls._id}>
                    <tr
                      className={`class-row ${activeClass === cls._id ? "active-class" : ""}`}
                      onClick={() => toggleClassExpand(cls._id)}
                      style={{ cursor: "pointer" }}
                    >
                      <td>{cls.class_name}</td>
                      <td>{cls.department}</td>
                      <td>{cls.date || "-"}</td>
                      <td>{cls.time || "-"}</td>
                      <td>{cls.confidence ? `${cls.confidence.toFixed(2)}%` : "-"}</td>
                      <td>
                        <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
                          <button
                            className="btn btn-purple"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleRecordControl(cls.class_name, cls._id);
                            }}
                            disabled={state === "completed" && activeClass !== cls._id}
                          >
                            {getButtonLabel(cls._id)}
                          </button>

                          {state === "completed" && activeClass === cls._id && (
                            <p style={{ color: "green", marginTop: 8, fontSize: "0.9rem" }}>
                              ✅ Recording complete — verify feedback and click Update.
                            </p>
                          )}
                        </div>
                      </td>
                    </tr>

                    {/* Student Table */}
                    {expandedClass === cls._id && classStudents[cls._id] && (
                      <tr>
                        <td colSpan="6">
                          <div className="student-dropdown">
                            <table className="inner-table">
                              <thead>
                                <tr>
                                  <th>Name</th>
                                  <th>USN</th>
                                  <th>Date</th>
                                  <th>Time</th>
                                  <th>Check-ins</th>
                                  <th>Avg Confidence</th>
                                  <th>Status</th>
                                  <th>Feedback</th>
                                </tr>
                              </thead>
                              <tbody>
                                {classStudents[cls._id].map((stu) => (
                                  <tr key={stu.student_id}>
                                    <td>{stu.name}</td>
                                    <td>{stu.student_id}</td>
                                    <td>{stu.date || "-"}</td>
                                    <td>{stu.time || "-"}</td>
                                    <td>{stu.checkins || 0}</td>
                                    <td>{stu.confidence ? `${stu.confidence.toFixed(2)}%` : "0%"}</td>
                                    <td style={{ color: stu.status === "Present" ? "green" : "red" }}>
                                      {stu.status || "Not Marked"}
                                    </td>
                                    <td>
                                      <div style={{ display: "flex", flexDirection: "column" }}>
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
                                            style={{
                                              color:
                                                stu._feedbackAck === "Correct" ? "green" : "red",
                                              fontSize: "0.8rem",
                                              marginTop: 6,
                                            }}
                                          >
                                            {stu._feedbackAck === "Correct"
                                              ? "✅ Verified as correct"
                                              : "❌ Marked as incorrect"}
                                          </span>
                                        )}
                                      </div>
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })
            ) : (
              <tr>
                <td colSpan="6">No classes available.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Add Class Modal */}
      {showAddClass && (
        <div className="attendance-modal">
          <div className="attendance-modal-content">
            <h2>Add New Class</h2>
            <input
              type="text"
              placeholder="Class Name"
              value={newClass.class_name}
              onChange={(e) => setNewClass({ ...newClass, class_name: e.target.value })}
            />
            <input
              type="text"
              placeholder="Department"
              value={newClass.department}
              onChange={(e) => setNewClass({ ...newClass, department: e.target.value })}
            />
            <button className="btn btn-green" onClick={handleAddClass}>
              Create Class
            </button>
            <button className="btn btn-outline" onClick={() => setShowAddClass(false)}>
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default AttendanceDashboard;
