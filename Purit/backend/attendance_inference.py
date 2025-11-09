import os
import threading
import torch
import numpy as np
import librosa
import soundfile as sf
import sounddevice as sd
import wavio
import pyttsx3
from datetime import datetime
from pymongo import MongoClient
from model import SpeakerRecognitionCNN
from dataset import wav_to_logmelspec
import time

MODEL_PATH = "speaker_cnn.pt"
SAMPLE_RATE = 16000
DURATION = 4  # seconds to record
TMP_AUDIO_DIR = "./tmp_audio"
os.makedirs(TMP_AUDIO_DIR, exist_ok=True)

# -------------------------
# Database connection
# -------------------------
def get_db(uri="mongodb://localhost:27017", db_name="purit_db"):
    client = MongoClient(uri)
    return client[db_name]

# -------------------------
# Global session management
# -------------------------
active_sessions = {}  # {class_name: {"paused": bool, "stop": bool, "thread": thread, "results": []}}

# -------------------------
# Model utils
# -------------------------
def load_model(device="cpu"):
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(f"Model file not found: {MODEL_PATH}")
    ckpt = torch.load(MODEL_PATH, map_location=device)
    if "labels" in ckpt and "model_state" in ckpt:
        label_map = ckpt["labels"]
        model_state = ckpt["model_state"]
    elif "labels" in ckpt and "model_state_dict" in ckpt:
        label_map = ckpt["labels"]
        model_state = ckpt["model_state_dict"]
    else:
        label_map = ckpt.get("labels", None)
        model_state = ckpt.get("model_state", None) or ckpt.get("model_state_dict", ckpt)

    if label_map is None:
        db = get_db()
        students = list(db.students.find({}))
        n_classes = max(2, len(students))
        inv_labels = None
    else:
        n_classes = len(label_map)
        inv_labels = {v: k for k, v in label_map.items()}

    model = SpeakerRecognitionCNN(n_classes=n_classes)
    try:
        model.load_state_dict(model_state)
    except Exception:
        model.load_state_dict(model_state, strict=False)
    model.to(device).eval()
    return model, inv_labels


def predict(audio_path, model, inv_labels, device="cpu"):
    wav, sr = sf.read(audio_path, dtype="float32")
    if wav.ndim > 1:
        wav = wav.mean(axis=1)
    if sr != SAMPLE_RATE:
        wav = librosa.resample(wav, sr, SAMPLE_RATE)
    mel = wav_to_logmelspec(wav)
    mel = np.expand_dims(mel, (0, 1))
    x = torch.tensor(mel, dtype=torch.float32).to(device)
    with torch.no_grad():
        logits = model(x)
        probs = torch.softmax(logits, dim=1)[0].cpu().numpy()
        idx = int(np.argmax(probs))
        conf = float(probs[idx])
    student_id = None
    if inv_labels:
        student_id = inv_labels.get(idx)
    return student_id, conf


# -------------------------
# Audio recording utilities
# -------------------------
def record_audio(filename="mic_temp.wav", duration=DURATION):
    print(f"🎙️ Speak now for {duration} seconds…")
    audio = sd.rec(int(duration * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype="float32")
    sd.wait()
    wavio.write(filename, audio, SAMPLE_RATE, sampwidth=2)
    return filename


def announce_student(name):
    try:
        engine = pyttsx3.init()
        engine.setProperty("rate", 150)
        engine.say(name)
        engine.runAndWait()
    except Exception:
        pass


def mark_attendance(db, student, status, confidence, class_name):
    db.attendance.insert_one({
        "student_id": student.get("student_id"),
        "name": student.get("name"),
        "class_name": class_name,
        "timestamp": datetime.utcnow(),
        "status": status,
        "confidence": confidence,
    })


# -------------------------
# Core class attendance processing (used internally)
# -------------------------
def _run_attendance_session(class_name):
    db = get_db()
    session = active_sessions[class_name]
    students = list(db.students.find({"class_name": class_name}, {"_id": 0}))

    if not students:
        print(f"❌ No students found for {class_name}")
        session["stop"] = True
        return

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, inv_labels = load_model(device)

    print(f"🎧 Starting live attendance session for {class_name}")
    session["results"] = []

    for idx, student in enumerate(students):
        if session["stop"]:
            print("🛑 Session stopped prematurely.")
            break

        # Pause check
        while session["paused"]:
            print("⏸️ Attendance paused... waiting to resume...")
            time.sleep(1)
            if session["stop"]:
                break

        if session["stop"]:
            break

        name = student.get("name", "Unknown")
        announce_student(name)

        filename = f"{student.get('student_id')}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.wav"
        filepath = os.path.join(TMP_AUDIO_DIR, filename)
        record_audio(filepath, duration=DURATION)

        # Predict
        if not os.path.exists(filepath):
            status = "Absent"
            conf_pct = 0.0
        else:
            pred_id, conf = predict(filepath, model, inv_labels, device)
            conf_pct = float(conf * 100.0)
            status = "Present" if pred_id == student.get("student_id") and conf_pct >= 85.0 else "Absent"

        temp_doc = {
            "class_name": class_name,
            "student_id": student.get("student_id"),
            "name": name,
            "confidence": conf_pct,
            "status": status,
            "timestamp": datetime.utcnow(),
            "audio_path": filepath if os.path.exists(filepath) else None,
        }

        # ✅ Write to temp_attendance for frontend live update
        db.temp_attendance.update_one(
            {"class_name": class_name, "student_id": student.get("student_id")},
            {"$set": temp_doc},
            upsert=True,
        )

        db.temp_attendance.database.client.admin.command('fsync')  # ✅ flush write
        time.sleep(3)  # give frontend polling time to catch up


        # Add to in-memory result for session
        session["results"].append(temp_doc)

        print(f"→ {student.get('student_id')} | {name} | {status} | {conf_pct:.2f}%")

        # ✅ Give frontend time to poll this record
        time.sleep(2)

    # ✅ Mark session as complete (but don't finalize automatically)
    session["stop"] = True
    print(f"✅ Attendance session finished for {class_name}")


# -------------------------
# Control functions (for main.py endpoints)
# -------------------------
def start_class_attendance(class_name):
    """Start a threaded attendance session."""
    if class_name in active_sessions and not active_sessions[class_name]["stop"]:
        return f"⚠️ Session already running for {class_name}"

    active_sessions[class_name] = {"paused": False, "stop": False, "results": []}
    thread = threading.Thread(target=_run_attendance_session, args=(class_name,), daemon=True)
    active_sessions[class_name]["thread"] = thread
    thread.start()
    return f"🎙️ Started attendance session for {class_name}"


def pause_class_attendance(class_name):
    """Pause the current session."""
    session = active_sessions.get(class_name)
    if not session:
        return f"No active session for {class_name}"
    session["paused"] = True
    return f"⏸️ Paused session for {class_name}"


def resume_class_attendance(class_name):
    """Resume paused session."""
    session = active_sessions.get(class_name)
    if not session:
        return f"No active session for {class_name}"
    if not session["paused"]:
        return f"Session for {class_name} is not paused"
    session["paused"] = False
    return f"▶️ Resumed session for {class_name}"


def finish_class_attendance(class_name):
    """Stop session and finalize data into permanent collection."""
    db = get_db()
    session = active_sessions.get(class_name)
    if not session:
        return []

    session["stop"] = True
    results = session.get("results", [])

    if not results:
        results = list(db.temp_attendance.find({"class_name": class_name}, {"_id": 0}))

    # Move results into permanent collection
    for r in results:
        db.attendance.insert_one(r)

    # Update class summary in 'classes' collection
    if results:
        avg_conf = sum(r["confidence"] for r in results) / len(results)
        date_now = datetime.utcnow().strftime("%Y-%m-%d")
        db.classes.update_one(
            {"class_name": class_name},
            {
                "$set": {
                    "status": "Recorded",
                    "confidence": avg_conf,
                    "date": date_now,
                    "time": datetime.utcnow().strftime("%H:%M:%S"),
                }
            },
        )

    # Clean up session
    del active_sessions[class_name]
    print(f"✅ Finalized attendance for {class_name} ({len(results)} records)")
    return results


# -------------------------
# Legacy process (used by older API)
# -------------------------
def process_class_attendance(class_name: str):
    db = get_db()
    students = list(db.students.find({"class_name": class_name}, {"_id": 0}))
    if not students:
        print(f"❌ No students found for class {class_name}")
        return []

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, inv_labels = load_model(device)
    results = []

    print(f"\n🔊 Starting attendance for {class_name}\n")

    for student in students:
        name = student.get("name", "Unknown")
        announce_student(name)
        fname = f"{student.get('student_id')}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.wav"
        filepath = os.path.join(TMP_AUDIO_DIR, fname)
        record_audio(filepath, duration=DURATION)

        if not os.path.exists(filepath):
            status = "Absent"
            confidence_pct = 0.0
        else:
            pred_id, conf = predict(filepath, model, inv_labels, device)
            confidence_pct = float(conf * 100.0)
            status = "Present" if pred_id == student.get("student_id") and confidence_pct >= 85.0 else "Absent"

        temp_doc = {
            "class_name": class_name,
            "student_id": student.get("student_id"),
            "name": name,
            "confidence": confidence_pct,
            "status": status,
            "timestamp": datetime.utcnow(),
            "audio_path": filepath if os.path.exists(filepath) else None,
        }

        db.temp_attendance.update_one(
            {"class_name": class_name, "student_id": student.get("student_id")},
            {"$set": temp_doc},
            upsert=True,
        )
        results.append(temp_doc)
        print(f"→ {student.get('student_id')} | {name} | {status} | {confidence_pct:.2f}%")

    print(f"\n🎯 Attendance temp results saved for {class_name}")
    return results


# -------------------------
# Single audio inference (unchanged)
# -------------------------
def process_attendance(audio_path):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, inv_labels = load_model(device)
    pred_id, conf = predict(audio_path, model, inv_labels, device)
    return {"student_id": pred_id, "confidence": float(conf * 100.0)}


# -------------------------
# CLI Testing
# -------------------------
if __name__ == "__main__":
    cls = input("Enter class name: ").strip()
    out = process_class_attendance(cls)
    print("RESULTS:", out)
