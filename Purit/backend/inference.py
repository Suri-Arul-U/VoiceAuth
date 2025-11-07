# # inference.py
# import torch
# import numpy as np
# import sounddevice as sd
# import wavio
# import os
# import librosa
# import soundfile as sf
# from model import SmallCNN
# from dataset import wav_to_logmelspec

# MODEL_PATH = "speaker_cnn.pt"
# SAMPLE_RATE = 16000
# DURATION = 4  # seconds to record

# # -----------------------------
# # Load model
# # -----------------------------
# def load_model(device="cpu"):
#     checkpoint = torch.load(MODEL_PATH, map_location=device)
#     label_map = checkpoint["labels"]
#     inv_labels = {v: k for k, v in label_map.items()}

#     model = SmallCNN(n_classes=len(label_map))
#     model.load_state_dict(checkpoint["model_state"])
#     model.to(device)
#     model.eval()

#     return model, inv_labels

# # -----------------------------
# # Predict from wav
# # -----------------------------
# def predict(audio_path, device="cpu"):
#     wav, sr = sf.read(audio_path, dtype='float32')
#     if wav.ndim > 1:
#         wav = wav.mean(axis=1)
#     if sr != SAMPLE_RATE:
#         wav = librosa.resample(wav, sr, SAMPLE_RATE)

#     mel = wav_to_logmelspec(wav)
#     mel = np.expand_dims(mel, axis=(0, 1))  # shape (1, 1, n_mels, time)
#     tensor = torch.tensor(mel, dtype=torch.float32).to(device)

#     model, inv_labels = load_model(device)
#     with torch.no_grad():
#         logits = model(tensor)
#         probs = torch.softmax(logits, dim=1)[0].cpu().numpy()
#         idx = int(np.argmax(probs))
#         label = inv_labels[idx]
#         confidence = float(probs[idx])

#     return label, confidence

# # -----------------------------
# # Record from microphone
# # -----------------------------
# def record_audio(filename="mic_input.wav", duration=DURATION, sr=SAMPLE_RATE):
#     print(f"🎙️ Recording for {duration} seconds... Speak now!")
#     audio = sd.rec(int(duration * sr), samplerate=sr, channels=1, dtype='float32')
#     sd.wait()
#     wavio.write(filename, audio, sr, sampwidth=2)
#     print(f"✅ Recording saved as {filename}")
#     return filename

# # -----------------------------
# # Main
# # -----------------------------
# if __name__ == "__main__":
#     print("🎧 Purit Voice Verification - Live Mode")
#     temp_file = "mic_input.wav"
#     record_audio(temp_file)

#     label, conf = predict(temp_file)
#     os.remove(temp_file)  # clean up

#     print(f"\n✅ Predicted Speaker ID: {label}")
#     print(f"🔹 Confidence: {conf:.2f}")

#     if label.lower() == "suri_Arul".lower() or label.lower() == "suriarul".lower() or label.lower() == "suri".lower():
#         print("🎉 Verified: This is Suri Arul ✅")
#     else:
#         print("❌ Voice does not match Suri Arul.")







# # inference.py (replace)
# import os
# import torch
# import numpy as np
# import soundfile as sf
# import librosa
# from dataset import wav_to_logmelspec, SAMPLE_RATE, TARGET_DURATION
# from model import SmallCNN

# MODEL_PATH = "speaker_cnn.pt"
# DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# def load_model(device=DEVICE, model_path=MODEL_PATH):
#     ckpt = torch.load(model_path, map_location=device)
#     label_map = ckpt["labels"]
#     inv_labels = {v: k for k, v in label_map.items()}
#     model = SmallCNN(len(label_map)).to(device)
#     model.load_state_dict(ckpt["model_state"])
#     model.eval()
#     return model, inv_labels

# def predict_file(path, model, inv_labels, device=DEVICE, window_sec=3.0, hop_sec=1.5):
#     wav, sr = sf.read(path, dtype='float32')
#     if wav.ndim > 1:
#         wav = wav.mean(axis=1)
#     if sr != SAMPLE_RATE:
#         wav = librosa.resample(wav, sr, SAMPLE_RATE)

#     win_len = int(window_sec * SAMPLE_RATE)
#     hop_len = int(hop_sec * SAMPLE_RATE)
#     if len(wav) < win_len:
#         # pad to at least one window
#         pad_len = win_len - len(wav)
#         wav = np.pad(wav, (0, pad_len), mode='constant')

#     probs_list = []
#     for start in range(0, max(1, len(wav) - win_len + 1), hop_len):
#         chunk = wav[start:start+win_len]
#         mel = wav_to_logmelspec(chunk)   # (n_mels, frames)
#         x = torch.tensor(mel, dtype=torch.float32).unsqueeze(0).unsqueeze(0).to(device)
#         with torch.no_grad():
#             logits = model(x)
#             probs = torch.softmax(logits, dim=1)[0].cpu().numpy()
#             probs_list.append(probs)

#     if len(probs_list) == 0:
#         return None, 0.0, []

#     avg = np.mean(probs_list, axis=0)
#     idx = int(np.argmax(avg))
#     label = inv_labels[idx]
#     confidence = float(avg[idx])
#     # top-3
#     top_idx = np.argsort(avg)[::-1][:3]
#     topk = [(inv_labels[int(i)], float(avg[int(i)])) for i in top_idx]
#     return label, confidence, topk

# if __name__ == "__main__":
#     # quick test
#     if not os.path.exists(MODEL_PATH):
#         print("No model found at", MODEL_PATH)
#     else:
#         m, inv = load_model()
#         test_file = input("Path to .wav to test: ").strip()
#         lab, conf, topk = predict_file(test_file, m, inv)
#         print("Predicted:", lab, "conf:", conf)
#         print("Topk:", topk)

# this should be the new inference.py file


# import torch
# import numpy as np
# import sounddevice as sd
# import librosa
# from model import SmallCNN
# from dataset import wav_to_logmelspec  # your existing preprocessing function

# # -----------------------------
# # Config
# # -----------------------------
# MODEL_PATH = "speaker_cnn.pt"
# SAMPLE_RATE = 16000
# DURATION = 4  # seconds to record
# DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# # -----------------------------
# # Load model
# # -----------------------------
# def load_model():
#     model = SmallCNN(n_classes=2)  # Make sure n_classes matches your trained model
#     checkpoint = torch.load(MODEL_PATH, map_location=DEVICE)
#     model.load_state_dict(checkpoint["model_state"])  # <-- extract model_state
#     model.to(DEVICE)
#     model.eval()
#     return model


# # -----------------------------
# # Record audio from mic
# # -----------------------------
# def record_audio(duration=DURATION, sr=SAMPLE_RATE):
#     print(f"Recording for {duration} seconds...")
#     audio = sd.rec(int(duration * sr), samplerate=sr, channels=1, dtype='float32')
#     sd.wait()
#     audio = audio.flatten()  # convert to 1D array
#     print("Recording complete!")
#     return audio

# # -----------------------------
# # Main inference
# # -----------------------------
# def main():
#     model = load_model()
#     audio = record_audio()

#     # Preprocess audio
#     features = wav_to_logmelspec(audio, sr=SAMPLE_RATE)
#     features = torch.tensor(features, dtype=torch.float32).unsqueeze(0).unsqueeze(0).to(DEVICE)  # shape [1,1,feat, time]

#     # Predict
#     with torch.no_grad():
#         outputs = model(features)
#         pred = torch.argmax(outputs, dim=1).item()
    
#     print(f"Predicted Speaker ID: {pred}")

# if __name__ == "__main__":
#     main()
