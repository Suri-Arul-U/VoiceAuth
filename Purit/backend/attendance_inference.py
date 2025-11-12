import os
import threading
import torch
import numpy as np
import librosa
import soundfile as sf
import sounddevice as sd
import wavio
import pyttsx3
import time
from datetime import datetime, timedelta
from pymongo import MongoClient

from model import SpeakerRecognitionCNN
from dataset import wav_to_logmelspec

# -----------------------------
# Configuration
# -----------------------------
MODEL_PATH = "speaker_cnn.pt"
SAMPLE_RATE = 16000
DURATION = 4  # seconds
TMP_AUDIO_DIR = "./tmp_audio"
os.makedirs(TMP_AUDIO_DIR, exist_ok=True)

# RMS threshold for detecting voice activity
RMS_THRESHOLD = 0.01
# Confidence thresholds for marking present/absent
CONF_THRESHOLD = 0.93
MARGIN_THRESHOLD = 0.08

# -----------------------------
# Database
# -----------------------------
def get_db(uri="mongodb://localhost:27017", db_name="purit_db"):
    client = MongoClient(uri)
    return client[db_name]

# -----------------------------
# Load CNN model
# -----------------------------
def load_model(device="cpu"):
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(f"Model not found at {MODEL_PATH}")
    ckpt = torch.load(MODEL_PATH, map_location=device)
    model_state = ckpt.get("model_state_dict") or ckpt
    labels = ckpt.get("labels", None)
    inv_labels = {v: k for k, v in labels.items()} if labels else None
    n_classes = len(labels) if labels else 2

    model = SpeakerRecognitionCNN(n_classes=n_classes)
    model.load_state_dict(model_state, strict=False)
    model.to(device).eval()
    return model, inv_labels

# -----------------------------
# Compute embedding
# -----------------------------
def compute_embedding(audio_path, model, device="cpu"):
    wav, sr = sf.read(audio_path, dtype="float32")
    if wav.ndim > 1:
        wav = wav.mean(axis=1)
    if sr != SAMPLE_RATE:
        wav = librosa.resample(wav, orig_sr=sr, target_sr=SAMPLE_RATE)
    mel = wav_to_logmelspec(wav)
    mel = np.expand_dims(mel, (0, 1))
    x = torch.tensor(mel, dtype=torch.float32).to(device)

    with torch.no_grad():
        emb = model.embed(x).cpu().numpy()[0]
    emb = emb / (np.linalg.norm(emb) + 1e-9)
    return emb

# -----------------------------
# Cosine similarity
# -----------------------------
def cosine_sim(a, b):
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))

# -----------------------------
# Audio recording & checks
# -----------------------------
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

def is_speech_present(audio_path, thresh_rms=RMS_THRESHOLD):
    wav, sr = sf.read(audio_path, dtype="float32")
    if wav.ndim > 1:
        wav = wav.mean(axis=1)
    rms = float(np.sqrt(np.mean(wav ** 2)))
    return rms >= thresh_rms, rms

# -----------------------------
# Reference Embedding (Averages verified or voice samples)
# -----------------------------
def get_student_reference_embedding(db, student_id, model, device="cpu"):
    student = db.students.find_one({"student_id": student_id})
    if not student:
        return None
    sources = student.get("verified_samples") or student.get("voice_samples") or []
    embeddings = []
    for path in sources:
        if path and os.path.exists(path):
            try:
                emb = compute_embedding(path, model, device)
                embeddings.append(emb)
            except Exception as e:
                print(f"⚠️ Failed embedding for {path}: {e}")
    if not embeddings:
        return None
    avg = np.mean(np.stack(embeddings), axis=0)
    avg = avg / (np.linalg.norm(avg) + 1e-9)
    return avg

# -----------------------------
# Attendance Session
# -----------------------------
active_sessions = {}

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
    print(f"🎧 Starting attendance session for {class_name}")
    session["results"] = []

    # Precompute reference embeddings
    ref_embeddings = {}
    for s in students:
        sid = s["student_id"]
        emb = get_student_reference_embedding(db, sid, model, device)
        if emb is not None:
            ref_embeddings[sid] = emb
        else:
            print(f"⚠️ No reference embeddings for {sid}")

    for student in students:
        if session["stop"]:
            break
        while session["paused"]:
            print("⏸️ Attendance paused...")
            time.sleep(1)
            if session["stop"]:
                break
        if session["stop"]:
            break

        name = student.get("name", "Unknown")
        sid = student["student_id"]
        print(f"\n🎧 Listening for {name} ({sid})...")
        announce_student(name)

        # 🟡 Mark as 'Not Marked' before recording (to avoid confusion)
        db.temp_attendance.update_one(
            {"class_name": class_name, "student_id": sid},
            {"$set": {
                "status": "Not Marked",
                "confidence": 0.0,
                "timestamp": datetime.utcnow()
            }},
            upsert=True,
        )

        # Record new voice sample
        filename = f"{sid}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.wav"
        filepath = os.path.join(TMP_AUDIO_DIR, filename)
        record_audio(filepath, duration=DURATION)


        speech, rms = is_speech_present(filepath)
        if not speech:
            status = "No Speech"
            confidence_pct = 0.0
            print(f"→ {sid} | {name} | No Speech | RMS={rms:.6f}")
        else:
            emb = compute_embedding(filepath, model, device)
            sims = {}
            for sid_ref, ref_emb in ref_embeddings.items():
                sims[sid_ref] = cosine_sim(emb, ref_emb)
            sorted_sims = sorted(sims.items(), key=lambda x: x[1], reverse=True)
            best_match_id, best_sim = sorted_sims[0]
            second_best_sim = sorted_sims[1][1] if len(sorted_sims) > 1 else 0.0
            confidence_pct = round(best_sim * 100.0, 2)
            margin = best_sim - second_best_sim

            if best_match_id == sid and best_sim >= CONF_THRESHOLD and margin >= MARGIN_THRESHOLD:
                status = "Present"
            else:
                status = "Absent"

            print(f"→ {sid} | {name} | {status} | {confidence_pct:.2f}% | Margin={margin:.3f}")

        temp_doc = {
            "class_name": class_name,
            "student_id": sid,
            "name": name,
            "confidence": confidence_pct,
            "status": status,
            "timestamp": datetime.utcnow(),
            "audio_path": filepath,
        }

        db.temp_attendance.update_one(
            {"class_name": class_name, "student_id": sid},
            {"$set": temp_doc},
            upsert=True,
        )
        session["results"].append(temp_doc)
        time.sleep(1.5)

    session["stop"] = True
    print(f"✅ Attendance session finished for {class_name}")

# -----------------------------
# Session Control
# -----------------------------
def start_class_attendance(class_name):
    if class_name in active_sessions and not active_sessions[class_name]["stop"]:
        return f"⚠️ Session already running for {class_name}"
    active_sessions[class_name] = {"paused": False, "stop": False, "results": []}
    thread = threading.Thread(target=_run_attendance_session, args=(class_name,), daemon=True)
    active_sessions[class_name]["thread"] = thread
    thread.start()
    return f"🎙️ Started attendance session for {class_name}"

def pause_class_attendance(class_name):
    session = active_sessions.get(class_name)
    if not session:
        return f"No active session for {class_name}"
    session["paused"] = True
    return f"⏸️ Paused session for {class_name}"

def resume_class_attendance(class_name):
    session = active_sessions.get(class_name)
    if not session:
        return f"No active session for {class_name}"
    if not session["paused"]:
        return f"Session for {class_name} is not paused"
    session["paused"] = False
    return f"▶️ Resumed session for {class_name}"

def finish_class_attendance(class_name):
    db = get_db()
    session = active_sessions.get(class_name)
    if not session:
        return []
    session["stop"] = True
    results = session.get("results", [])
    if not results:
        results = list(db.temp_attendance.find({"class_name": class_name}, {"_id": 0}))
    if not results:
        print(f"⚠️ No results found for {class_name}")
        return []

    for r in results:
        db.attendance.update_one(
            {
                "class_name": class_name,
                "student_id": r["student_id"],
                "timestamp": {"$gte": datetime.utcnow() - timedelta(hours=24)},
            },
            {"$set": r},
            upsert=True,
        )

    presents = [r for r in results if r["status"] == "Present"]
    avg_conf = round(sum(r.get("confidence", 0) for r in results) / max(len(results), 1), 2)
    now = datetime.utcnow()
    db.classes.update_one(
        {"class_name": class_name},
        {"$push": {
            "attendance_dates": {
                "date": now.strftime("%Y-%m-%d"),
                "time": now.strftime("%H:%M:%S"),
                "avg_confidence": avg_conf,
                "checkin_count": len(presents),
                "students": results,
            }
        }},
        upsert=True,
    )

    # ✅ Preserve last known snapshot until next midnight
    db.temp_attendance.delete_many({"class_name": class_name})
    if results:
        for r in results:
            r["expires_at"] = (datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                           + timedelta(days=1))
        db.temp_attendance.insert_many(results)

    del active_sessions[class_name]
    print(f"✅ Finalized {class_name} — {len(results)} records | Avg={avg_conf}% | Checkins={len(presents)}")
    return results

# -----------------------------
# Single inference (fallback)
# -----------------------------
def process_attendance(audio_path):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, inv_labels = load_model(device)
    try:
        wav, sr = sf.read(audio_path, dtype="float32")
        if wav.ndim > 1:
            wav = wav.mean(axis=1)
        if sr != SAMPLE_RATE:
            wav = librosa.resample(wav, orig_sr=sr, target_sr=SAMPLE_RATE)
        mel = wav_to_logmelspec(wav)
        mel = np.expand_dims(mel, (0, 1))
        x = torch.tensor(mel, dtype=torch.float32).to(device)
        with torch.no_grad():
            logits = model(x)
            probs = torch.softmax(logits, dim=1)[0].cpu().numpy()
            idx = int(np.argmax(probs))
            conf = float(probs[idx])
    except Exception:
        idx = None
        conf = 0.0
    student_id = inv_labels.get(idx) if inv_labels else None
    return {"student_id": student_id, "confidence": float(conf * 100.0)}
