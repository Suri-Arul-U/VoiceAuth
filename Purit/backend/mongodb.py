# # mongodb.py
# from pymongo import MongoClient
# from dotenv import load_dotenv
# import os

# load_dotenv()

# MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
# DB_NAME = "purit_db"

# def get_db():
#     client = MongoClient(MONGODB_URI)
#     db = client[DB_NAME]
#     return db

# def seed_students():
#     db = get_db()
#     students = db.students
#     students.delete_many({})  # clear previous entries
#     sample_docs = [
#         # { "student_id": "1GV22CS058", "name": "Priya Dharshini J", "audio_path": "../samples/AnyConv.com__Priyadharshini.wav" },
#         # { "student_id": "1GV22CS060", "name": "Raghavi V", "audio_path": "../samples/AnyConv.com__Raghavi.wav" },
#         # { "student_id": "1GV22CS061", "name": "Rakshitha V", "audio_path": "../samples/AnyConv.com__Rakshitha.wav" },
#         # { "student_id": "1GV22CS063", "name": "Rithika Roshini L R", "audio_path": "../samples/Rithika.wav" },
#         # { "student_id": "1GV22CS064", "name": "Rohith G", "audio_path": "../samples/Rohith.wav" },
#         # { "student_id": "1GV22CS065", "name": "Sahana N", "audio_path": "../samples/Sahana.wav" },
#         # { "student_id": "1GV22CS066", "name": "Sameen Parveen", "audio_path": "../samples/Sameen.wav" },
#         # { "student_id": "1GV22CS068", "name": "Seshanth N", "audio_path": "../samples/Seshanth.wav" },
#         # { "student_id": "1GV22CS069", "name": "Shabaresh T", "audio_path": "../samples/Shabresh.wav" },
#         # { "student_id": "1GV22CS072", "name": "Shaik Waheed Pasha", "audio_path": "../samples/Shaik Waheed.wav" },
#         # { "student_id": "1GV22CS073", "name": "Shashank B", "audio_path": "../samples/Shashank_.wav" },
#         # { "student_id": "1GV22CS074", "name": "Shaziya Begum M", "audio_path": "../samples/Shaziya.wav" },
#         # { "student_id": "1GV22CS075", "name": "Shevin Rozario T", "audio_path": "../samples/Shevin.wav" },
#         # { "student_id": "1GV22CS076", "name": "Shreeja G", "audio_path": "../samples/Sreeja.wav" },
#         # { "student_id": "1GV22CS077", "name": "Shreeya M", "audio_path": "../samples/Shreeya.wav" },
#         # { "student_id": "1GV22CS078", "name": "Shresta S", "audio_path": "../samples/Shresta.wav" },
#         # { "student_id": "1GV22CS079", "name": "Shyam Kumar G", "audio_path": "../samples/Shyam Kumar.wav" },
#         # { "student_id": "1GV22CS080", "name": "Sneha B", "audio_path": "../samples/Sneha.wav" },
#         # { "student_id": "1GV22CS081", "name": "Solomon Raj A", "audio_path": "../samples/Solomon .wav" },
#         # { "student_id": "1GV22CS082", "name": "Suchitra C Shantanagoudar", "audio_path": "../samples/Suchitra.wav" },
#         # { "student_id": "1GV22CS083", "name": "Sumedh", "audio_path": "../samples/Sumedh.wav" },
#         { "student_id": "1GV22CS084", "name": "Suri Arul U", "audio_path": "../samples/Suri_Arul.wav" },
#         # { "student_id": "1GV22CS085", "name": "Sushmitha N", "audio_path": "../samples/Sushmitha.wav" },
#         # { "student_id": "1GV22CS086", "name": "Swathi R", "audio_path": "../samples/swaiti.wav" },
#         # { "student_id": "1GV22CS088", "name": "Tejashwini K R", "audio_path": "../samples/Tejashwini.wav" },
#         # { "student_id": "1GV22CS089", "name": "Theertha R", "audio_path": "../samples/Theertha.wav" },
#         # { "student_id": "1GV22CS090", "name": "Umme Hani", "audio_path": "../samples/Umme hani.wav" },
#         # { "student_id": "1GV22CS091", "name": "V Harini", "audio_path": "../samples/AnyConv.com__Harini.wav" },
#         # { "student_id": "1GV22CS092", "name": "Varsha S", "audio_path": "../samples/Varsha.wav" },
#         # { "student_id": "1GV22CS093", "name": "Veena K R", "audio_path": "../samples/Veena.wav" },
#         # { "student_id": "1GV22CS094", "name": "Yashwanth B G", "audio_path": "../samples/Yashwanth.wav" },
#         # { "student_id": "1GV22CS095", "name": "Srinivas V M", "audio_path": "../samples/Srinivas.wav" },
#         # { "student_id": "1GV22CS096", "name": "Gladwin Sujith E", "audio_path": "../samples/Gladwin.wav" },
#         # { "student_id": "1GV22CS097", "name": "Shakthi Roshitha R", "audio_path": "../samples/shakti-roshitha.wav" },
#         # { "student_id": "1GV22CS098", "name": "Umme Hani", "audio_path": "../samples/White umme hani.wav" },
#         # { "student_id": "1GV23CS400", "name": "Abhishek A", "audio_path": "../samples/Abhishek.wav" },
#         # { "student_id": "1GV23CS401", "name": "Adarsha B", "audio_path": "../samples/Adharsha.wav" },
#         # { "student_id": "1GV23CS402", "name": "Avinaiya V", "audio_path": "../samples/Avinaya.wav" },
#         # { "student_id": "1GV23CS403", "name": "Bindu S", "audio_path": "../samples/AnyConv.com__Bindhu.wav" },
#         # { "student_id": "1GV23CS404", "name": "Charan Reddy S", "audio_path": "../samples/Charan Reddy.wav" },
#         # { "student_id": "1GV23CS407", "name": "Nandhini E", "audio_path": "../samples/AnyConv.com__Nandhini.wav" },
#         # { "student_id": "1GV23CS409", "name": "Prakash B", "audio_path": "../samples/Prakash.wav" },
#         # { "student_id": "1GV23CS410", "name": "Silvan Kumar K", "audio_path": "../samples/Silvan.wav" }

#     ]
#     result = students.insert_many(sample_docs)
#     print(f"Inserted student ids: {result.inserted_ids}")

# if __name__ == "__main__":
#     seed_students()







# mongodb.py
from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DB_NAME = "purit_db"

def get_db():
    client = MongoClient(MONGODB_URI)
    db = client[DB_NAME]
    return db

def seed_students():
    """
    Seed example students only if the students collection is empty.
    This prevents accidental deletion of user-created voice profiles on restart.
    """
    db = get_db()
    students = db.students

    # If there are already students, do nothing (avoid wiping user data)
    if students.count_documents({}) > 0:
        print("⏭️ students collection not empty — skipping seed.")
        return

    sample_docs = [
        {
            "student_id": "1GV22CS000",
            "name": "Suri Arul U",
            "department": "CSE",
            "class_name": "class_sample",
            "audio_path": "../samples/Suri_Arul.wav",
            "voice_samples": [],
            "verified_samples": [],
            "stats": {},
            "created_at": None,
        },
        # Add other sample docs here if needed
    ]
    result = students.insert_many(sample_docs)
    print(f"Inserted student ids: {result.inserted_ids}")

