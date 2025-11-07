# train.py
import torch
from torch.utils.data import DataLoader
from dataset import StudentAudioDataset
from model import SpeakerRecognitionCNN
from pymongo import MongoClient
import os
from tqdm import tqdm
import argparse

# -----------------------------
# Config (can be overridden by args)
# -----------------------------
EPOCHS = 20
BATCH_SIZE = 8
LR = 1e-3
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
MODEL_OUT = "speaker_cnn.pt"

def get_records_from_mongo(uri="mongodb://localhost:27017", db_name="purit_db"):
    client = MongoClient(uri)
    db = client[db_name]
    records = list(db.students.find({}))
    if not records:
        raise RuntimeError("❌ No student records found in MongoDB. Run mongodb.py first.")
    for r in records:
        if not os.path.exists(r.get("audio_path", "")):
            print(f"⚠️ WARNING: File not found: {r.get('audio_path')}")
    return records

def train_model(records, epochs=EPOCHS, batch_size=BATCH_SIZE, lr=LR, device=DEVICE, out_path=MODEL_OUT):
    dataset = StudentAudioDataset(records)
    n_classes = len(dataset.label_map)
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

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=EPOCHS)
    parser.add_argument("--batch_size", type=int, default=BATCH_SIZE)
    parser.add_argument("--lr", type=float, default=LR)
    parser.add_argument("--out", type=str, default=MODEL_OUT)
    args = parser.parse_args()

    records = get_records_from_mongo()
    train_model(records, epochs=args.epochs, batch_size=args.batch_size, lr=args.lr, out_path=args.out)
