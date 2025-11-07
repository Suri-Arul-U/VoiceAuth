// const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// export async function fetchProfiles() {
//   const res = await fetch(`${API}/profiles`);
//   if (!res.ok) throw new Error('Failed to fetch profiles');
//   return res.json();
// }

// export async function createProfile(data) {
//   const res = await fetch(`${API}/profiles`, {
//     method: 'POST',
//     headers: { 'Content-Type': 'application/json' },
//     body: JSON.stringify(data)
//   });
//   if (!res.ok) throw new Error('Failed to create profile');
//   return res.json();
// }

// export const recordAttendance = async (audioBlob) => {
//   const formData = new FormData();
//   formData.append('audio', audioBlob);

//   const response = await fetch(`${API}/attendance`, {
//     method: 'POST',
//     body: formData
//   });
//   if (!response.ok) throw new Error('Attendance upload failed');
//   return response.json();
// };





const API = import.meta.env.VITE_API_URL || "http://localhost:8000";

export async function fetchProfiles() {
  const res = await fetch(`${API}/profiles`);
  if (!res.ok) throw new Error("Failed to fetch profiles");
  return res.json();
}

export async function createProfile(data) {
  const res = await fetch(`${API}/profiles`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Failed to create profile");
  return res.json();
}

export async function fetchClasses() {
  const res = await fetch(`${API}/classes`);
  if (!res.ok) throw new Error("Failed to fetch classes");
  return res.json();
}

export async function fetchClassStudents(classId) {
  const res = await fetch(`${API}/classes/${classId}/students`);
  if (!res.ok) throw new Error("Failed to fetch class students");
  return res.json();
}

export async function sendFeedback(studentId, audioPath, verified) {
  const res = await fetch(`${API}/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      student_id: studentId,
      audio_path: audioPath,
      verified,
    }),
  });
  if (!res.ok) throw new Error("Failed to send feedback");
  return res.json();
}
