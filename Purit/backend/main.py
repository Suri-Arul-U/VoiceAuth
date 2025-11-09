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
    Form,
    Request
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi import Request

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




def clean_mongo_ids(data):
    """Recursively convert ObjectIds to strings for JSON safety."""
    if isinstance(data, list):
        return [clean_mongo_ids(item) for item in data]
    elif isinstance(data, dict):
        return {k: clean_mongo_ids(v) for k, v in data.items()}
    elif isinstance(data, ObjectId):
        return str(data)
    return data
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



@app.get("/attendance/status/{class_name}")
def check_attendance_status(class_name: str):
    from attendance_inference import active_sessions
    session = active_sessions.get(class_name)
    if not session:
        return {"status": "completed"}
    elif session.get("paused"):
        return {"status": "paused"}
    elif session.get("stop"):
        return {"status": "completed"}
    else:
        return {"status": "running"}

    

# newly added this temp

@app.get("/attendance/temp/{class_name}")
def get_temp_results(class_name: str):
    db = get_db()
    data = list(db.temp_attendance.find({"class_name": class_name}, {"_id": 0}))
    return {"results": data}




@app.post("/attendance/finish/{class_name}")
def finish_attendance(class_name: str):
    try:
        results = finish_class_attendance(class_name)
        results = clean_mongo_ids(results)  # ✅ Convert ObjectIds to strings
        return {"status": "completed", "results": results}
    except Exception as e:
        print("❌ Error finishing attendance:", e)
        raise HTTPException(status_code=500, detail=str(e))




@app.post("/attendance/update")
async def update_attendance(request: Request):
    """Apply feedback and status updates from frontend"""
    db = get_db()
    updates = await request.json()

    if not isinstance(updates, list):
        raise HTTPException(status_code=400, detail="Invalid format — expected list")

    for u in updates:
        db.attendance.update_one(
            {"student_id": u.get("student_id"), "class_name": u.get("class_name")},
            {"$set": {
                "status": u.get("status"),
                "feedback": u.get("feedback", ""),
                "confidence": u.get("confidence", 0),
                "updated_at": datetime.utcnow()
            }},
            upsert=True
        )

    return {"message": "✅ Attendance updated successfully"}


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

    # Store audio_path only if it's valid
    if feedback_in.verified:
        # Add to verified samples
        db.students.update_one(
            {"student_id": feedback_in.student_id},
            {"$addToSet": {"verified_samples": feedback_in.audio_path}},
        )
        message = "✅ Voice sample verified as correct."
    else:
        # Move to invalid samples (ignored in training)
        db.students.update_one(
            {"student_id": feedback_in.student_id},
            {"$addToSet": {"invalid_samples": feedback_in.audio_path}},
        )
        message = "❌ Voice sample marked as incorrect (ignored in future checks)."

    # Retrain if verified_samples ≥ 5
    verified_count = len(
        db.students.find_one({"student_id": feedback_in.student_id}).get("verified_samples", [])
    )
    if verified_count >= 5:
        trigger_retrain_background()

    return {"status": "ok", "message": message, "verified_count": verified_count}


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
