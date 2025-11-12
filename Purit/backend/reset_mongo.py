from mongodb import get_db

db = get_db()

db.students.delete_many({})
db.attendance.delete_many({})
db.temp_attendance.delete_many({})
db.classes.delete_many({})

print("✅ Cleared all MongoDB data for fresh training.")
