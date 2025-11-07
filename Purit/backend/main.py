# main.py
import os
import subprocess
from datetime import datetime
from typing import Optional
from bson import ObjectId
from fastapi import (
    FastAPI,
    UploadFile,
    File,
    HTTPException,
    Query,
    Form
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Internal modules (ensure these exist in your project)
from mongodb import get_db, seed_students
from attendance_inference import (
    process_attendance,
    process_class_attendance,
    start_class_attendance,
    pause_class_attendance,
    resume_class_attendance,
    finish_class_attendance
)
# train.py is optional; import if present
try:
    from train import train_model, get_records_from_mongo
except Exception:
    train_model = None
    get_records_from_mongo = None

# -------------------------------------------------------------------
# FastAPI app setup
# -------------------------------------------------------------------
app = FastAPI(title="PureTone Voice Recognition Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------------------------
# Startup (seed MongoDB only if empty)
# -------------------------------------------------------------------
@app.on_event("startup")
def startup():
    try:
        db = get_db()
        seed_students()
        print("✅ MongoDB seed checked (seed_students executed).")
    except Exception as e:
        print(f"⚠️ MongoDB seed failed/skipped: {e}")

# -------------------------------------------------------------------
# Helper: run model training in background
# -------------------------------------------------------------------
def trigger_retrain_background():
    python = "python"
    try:
        if os.path.exists("train.py"):
            subprocess.Popen(
                [python, "train.py"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            print("🔁 Background model retraining started.")
        else:
            print("⚠️ train.py not found — skipping retrain trigger.")
    except Exception as e:
        print("❌ Background training failed:", e)

# -------------------------------------------------------------------
# Utilities
# -------------------------------------------------------------------
def stringify_id(m):
    try:
        if isinstance(m.get("_id"), ObjectId):
            m["_id"] = str(m["_id"])
    except Exception:
        pass
    return m

# -------------------------------------------------------------------
# Root
# -------------------------------------------------------------------
@app.get("/")
def root():
    return {"message": "✅ PureTone Backend running successfully"}

# -------------------------------------------------------------------
# CLASS MANAGEMENT
# -------------------------------------------------------------------
@app.get("/classes")
def get_classes(date: Optional[str] = Query(None, description="Filter by date YYYY-MM-DD")):
    db = get_db()
    query = {"date": date} if date else {}
    classes = list(db.classes.find(query))
    classes = [stringify_id(c) for c in classes]
    return classes

@app.post("/classes")
def create_class(class_data: dict):
    db = get_db()
    class_id = str(ObjectId())
    cls = {
        "_id": class_id,
        "class_name": class_data.get("class_name"),
        "department": class_data.get("department"),
        "students": [],
        "attendance_dates": [],
        "confidence": 0,
        "status": "Not Recorded",
        "date": None,
        "time": None,
    }
    db.classes.insert_one(cls)
    return {"message": "Class added successfully", "class_id": class_id}

@app.get("/classes/{class_id}/students")
def get_class_students(class_id: str):
    db = get_db()
    cls = db.classes.find_one({"_id": class_id})
    if not cls:
        cls = db.classes.find_one({"class_name": class_id})
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")
    students = list(db.students.find({"class_name": cls.get("class_name")}, {"_id": 0}))
    return {"class": stringify_id(cls), "students": students}

# -------------------------------------------------------------------
# ATTENDANCE CONTROL ROUTES (New)
# -------------------------------------------------------------------
@app.post("/attendance/start/{class_name}")
def start_attendance(class_name: str):
    """Start a live attendance session for a class."""
    try:
        result = start_class_attendance(class_name)
        return {"status": "started", "class_name": class_name, "message": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/attendance/pause/{class_name}")
def pause_attendance(class_name: str):
    """Pause an ongoing attendance session."""
    try:
        result = pause_class_attendance(class_name)
        return {"status": "paused", "class_name": class_name, "message": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/attendance/resume/{class_name}")
def resume_attendance(class_name: str):
    """Resume a paused attendance session."""
    try:
        result = resume_class_attendance(class_name)
        return {"status": "resumed", "class_name": class_name, "message": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/attendance/finish/{class_name}")
def finish_attendance(class_name: str):
    """Finish attendance and finalize results."""
    try:
        results = finish_class_attendance(class_name)
        return {"status": "completed", "class_name": class_name, "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# -------------------------------------------------------------------
# OLD ATTENDANCE ROUTES (Still supported for direct audio uploads)
# -------------------------------------------------------------------
@app.post("/attendance/{class_id}")
async def attendance_upload(class_id: str, audio: UploadFile = File(...)):
    tmp_dir = "./tmp"
    os.makedirs(tmp_dir, exist_ok=True)
    filename = f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{audio.filename}"
    filepath = os.path.join(tmp_dir, filename)

    with open(filepath, "wb") as f:
        f.write(await audio.read())

    try:
        result = process_attendance(filepath)
        student_id = result.get("student_id")
        confidence = float(result.get("confidence", 0))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inference failed: {e}")

    db = get_db()
    now = datetime.now()
    date_now = now.strftime("%Y-%m-%d")
    time_now = now.strftime("%H:%M:%S")

    if not student_id:
        raise HTTPException(status_code=404, detail="Unknown or forged voice detected")

    cls = db.classes.find_one({"_id": class_id}) or db.classes.find_one({"class_name": class_id})
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")

    date_entry = None
    for d in cls.get("attendance_dates", []):
        if d.get("date") == date_now:
            date_entry = d
            break

    if date_entry:
        db.classes.update_one(
            {"_id": cls["_id"], "attendance_dates.date": date_now},
            {
                "$push": {
                    "attendance_dates.$.entries": {
                        "student_id": student_id,
                        "confidence": confidence,
                        "timestamp": now,
                        "audio_path": filepath,
                    }
                },
                "$inc": {"attendance_dates.$.checkin_count": 1},
            },
        )
        updated = db.classes.find_one(
            {"_id": cls["_id"], "attendance_dates.date": date_now}, {"attendance_dates.$": 1}
        )
        entries = updated["attendance_dates"][0].get("entries", [])
        avg_conf = sum(e.get("confidence", 0) for e in entries) / (len(entries) or 1)
        db.classes.update_one(
            {"_id": cls["_id"], "attendance_dates.date": date_now},
            {"$set": {"attendance_dates.$.avg_confidence": avg_conf}},
        )
    else:
        new_date_obj = {
            "date": date_now,
            "time": time_now,
            "entries": [
                {
                    "student_id": student_id,
                    "confidence": confidence,
                    "timestamp": now,
                    "audio_path": filepath,
                }
            ],
            "avg_confidence": confidence,
            "checkin_count": 1,
        }
        db.classes.update_one({"_id": cls["_id"]}, {"$push": {"attendance_dates": new_date_obj}})

    db.classes.update_one(
        {"_id": cls["_id"]},
        {
            "$set": {
                "confidence": confidence,
                "status": "Recorded",
                "date": date_now,
                "time": time_now,
            }
        },
    )
    db.students.update_one(
        {"student_id": student_id},
        {
            "$push": {f"stats.{date_now}.confidences": confidence},
            "$inc": {f"stats.{date_now}.checkins": 1},
        },
    )
    return {
        "message": "✅ Attendance recorded successfully",
        "student_id": student_id,
        "confidence": confidence,
        "date": date_now,
        "time": time_now,
    }

@app.post("/attendance/class/{class_name}")
def record_class_attendance(class_name: str):
    try:
        results = process_class_attendance(class_name)
        if not results:
            raise HTTPException(status_code=404, detail="No students found for this class.")
        return {"message": "Attendance completed", "class_name": class_name, "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# -------------------------------------------------------------------
# FEEDBACK
# -------------------------------------------------------------------
class FeedbackIn(BaseModel):
    student_id: str
    audio_path: str
    verified: bool

@app.post("/feedback")
def feedback(feedback_in: FeedbackIn):
    db = get_db()
    student = db.students.find_one({"student_id": feedback_in.student_id})
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    update_data = {"$push": {"voice_samples": feedback_in.audio_path}}
    if feedback_in.verified:
        update_data["$push"]["verified_samples"] = feedback_in.audio_path
    db.students.update_one({"student_id": feedback_in.student_id}, update_data)

    verified_count = len(
        db.students.find_one({"student_id": feedback_in.student_id}).get("verified_samples", [])
    )
    if verified_count >= 5:
        trigger_retrain_background()

    return {"status": "ok", "verified_count": verified_count}

# -------------------------------------------------------------------
# VOICE PROFILES
# -------------------------------------------------------------------
UPLOAD_DIR = "./uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.get("/profiles")
def get_profiles():
    db = get_db()
    students = list(
        db.students.find(
            {},
            {
                "_id": 0,
                "student_id": 1,
                "name": 1,
                "department": 1,
                "class_name": 1,
                "verified_samples": 1,
                "voice_samples": 1,
                "stats": 1,
            },
        )
    )
    profiles = []
    for s in students:
        profiles.append(
            {
                "voiceId": s["student_id"],
                "name": s["name"],
                "department": s.get("department", "N/A"),
                "class_name": s.get("class_name", "N/A"),
                "lastUpdated": datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
                "voice_samples": s.get("voice_samples", []),
                "verified_samples": s.get("verified_samples", []),
                "stats": s.get("stats", {}),
            }
        )
    return profiles

@app.post("/profiles")
async def create_profile(
    fullName: str = Form(...),
    usn: str = Form(...),
    department: str = Form(""),
    class_name: str = Form(...),
    audio: UploadFile = File(None),
):
    db = get_db()
    audio_path = None

    if db.students.find_one({"student_id": usn}):
        raise HTTPException(status_code=400, detail="Profile already exists for this USN")

    if audio:
        audio_filename = f"{usn}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.wav"
        audio_path = os.path.join(UPLOAD_DIR, audio_filename)
        with open(audio_path, "wb") as f:
            f.write(await audio.read())

    student = {
        "student_id": usn,
        "name": fullName,
        "department": department,
        "class_name": class_name,
        "voice_samples": [audio_path] if audio_path else [],
        "verified_samples": [],
        "stats": {},
        "created_at": datetime.now(),
    }
    db.students.insert_one(student)

    db.classes.update_one(
        {"class_name": class_name, "department": department},
        {
            "$addToSet": {"students": usn},
            "$setOnInsert": {
                "class_name": class_name,
                "department": department,
                "attendance_dates": [],
                "status": "Not Recorded",
                "confidence": 0,
            },
        },
        upsert=True,
    )
    return {
        "message": "✅ Voice profile created successfully",
        "student_id": usn,
        "audio_path": audio_path,
    }

# -------------------------------------------------------------------
# Run
# -------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
