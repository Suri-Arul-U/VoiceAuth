# train.py
import torch
from torch.utils.data import DataLoader
from dataset import StudentAudioDataset
from model import SpeakerRecognitionCNN
from pymongo import MongoClient
import os
import pathlib
from tqdm import tqdm
import argparse

# -----------------------------
# Config (can be overridden by args)
# -----------------------------
EPOCHS = 100
BATCH_SIZE = 4
LR = 5e-4
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
MODEL_OUT = "speaker_cnn.pt"


# -----------------------------
# Fetch training data from MongoDB
# -----------------------------
def get_records_from_mongo(uri="mongodb://localhost:27017", db_name="purit_db"):
    client = MongoClient(uri)
    db = client[db_name]
    records = list(db.students.find({}))
    if not records:
        raise RuntimeError("❌ No student records found in MongoDB. Run mongodb.py first.")

    # ✅ Extract all usable file paths for each student
    clean_records = []
    for r in records:
        student_paths = []

        # Add verified samples first (preferred)
        for path in r.get("verified_samples", []):
            if not path:
                continue
            norm_path = str(pathlib.Path(path))  # ✅ normalize slashes for Windows/Linux
            if os.path.exists(norm_path):
                student_paths.append(norm_path)
            else:
                print(f"⚠️ WARNING: Missing verified file for {r['student_id']}: {norm_path}")

        # Add voice_samples if verified ones are empty
        if not student_paths:
            for path in r.get("voice_samples", []):
                if not path:
                    continue
                norm_path = str(pathlib.Path(path))
                if os.path.exists(norm_path):
                    student_paths.append(norm_path)
                else:
                    print(f"⚠️ WARNING: Missing voice file for {r['student_id']}: {norm_path}")

        if not student_paths:
            print(f"⚠️ WARNING: No valid audio for {r['student_id']}")
            continue

        # Build a simplified record for dataset
        clean_records.append({
            "student_id": r["student_id"],
            "name": r.get("name", ""),
            "paths": student_paths
        })

    if not clean_records:
        raise RuntimeError("❌ No valid audio files found in database. Check uploads/tmp_audio paths.")

    print(f"✅ Loaded {len(clean_records)} students for training.")
    for rec in clean_records:
        print(f"   → {rec['student_id']} | {len(rec['paths'])} samples")

    return clean_records


# -----------------------------
# Train the speaker recognition model
# -----------------------------
def train_model(records, epochs=EPOCHS, batch_size=BATCH_SIZE, lr=LR, device=DEVICE, out_path=MODEL_OUT):
    dataset = StudentAudioDataset(records)
    n_classes = len(dataset.label_map)
    total_samples = len(dataset)

    if total_samples == 0:
        raise RuntimeError("❌ Dataset is empty — no valid audio files found to train on.")

    print(f"✅ Loaded {total_samples} total samples for {n_classes} speakers.")

    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)
    model = SpeakerRecognitionCNN(n_classes=n_classes)
    model.to(device)

    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = torch.nn.CrossEntropyLoss()

    print(f"✅ Training started on {device} with {n_classes} classes")
    for epoch in range(epochs):
        model.train()
        total_loss = 0.0
        pbar = tqdm(loader, desc=f"Epoch {epoch+1}/{epochs}")
        for x, y in pbar:
            x, y = x.to(device), y.to(device)
            logits = model(x)
            loss = criterion(logits, y)

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            total_loss += loss.item() * x.size(0)
            pbar.set_postfix({"loss": loss.item()})
        avg_loss = total_loss / len(dataset)
        print(f"Epoch {epoch+1}: Average Loss = {avg_loss:.4f}")

    # Save model and label mapping
    save_dict = {
        "model_state_dict": model.state_dict(),
        "labels": dataset.label_map
    }
    torch.save(save_dict, out_path)
    print(f"✅ Model saved to {out_path}")
    return out_path


# -----------------------------
# CLI Entry Point
# -----------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=EPOCHS)
    parser.add_argument("--batch_size", type=int, default=BATCH_SIZE)
    parser.add_argument("--lr", type=float, default=LR)
    parser.add_argument("--out", type=str, default=MODEL_OUT)
    args = parser.parse_args()

    records = get_records_from_mongo()
    train_model(records, epochs=args.epochs, batch_size=args.batch_size, lr=args.lr, out_path=args.out)
