from attendance_inference import compute_embedding, cosine_sim, load_model
import soundfile as sf
import numpy as np
import os

# 1️⃣ Load model
model, inv_labels = load_model("cpu")

# 2️⃣ Paths to your known and test audio files
# (use actual WAV files you uploaded through voice profile)
ref_path = "Purit/backend/uploads/1GV22CS084_20251112_052413.wav"  # registered voice
test_path = "Purit/backend/tmp_audio/1GV22CS084_20251112_052730.wav" # another student's or your own second sample

# 3️⃣ Compute embeddings
ref_emb = compute_embedding(ref_path, model)
test_emb = compute_embedding(test_path, model)

# 4️⃣ Compare
similarity = cosine_sim(ref_emb, test_emb)
print(f"Cosine similarity: {similarity:.4f} | Confidence: {similarity*100:.2f}%")
