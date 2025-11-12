# # dataset.py
# import os
# import torch
# import numpy as np
# import librosa
# from torch.utils.data import Dataset
# import soundfile as sf

# # -----------------------------
# # Audio Config
# # -----------------------------
# SAMPLE_RATE = 16000
# DURATION = 2.0       # seconds
# N_MELS = 64
# N_FFT = 512
# HOP_LENGTH = 256

# # -----------------------------
# # Helper functions
# # -----------------------------
# def load_wav(path, sr=SAMPLE_RATE, duration=DURATION):
#     """Load a .wav file, convert to mono, resample, and pad/trim to fixed duration."""
#     if not os.path.exists(path):
#         raise FileNotFoundError(f"Audio file not found: {path}")
#     wav, file_sr = sf.read(path, dtype='float32')
#     if wav.ndim > 1:
#         wav = wav.mean(axis=1)
#     if file_sr != sr:
#         wav = librosa.resample(wav, orig_sr=file_sr, target_sr=sr)
#     # Trim or pad
#     max_len = int(sr * duration)
#     if len(wav) > max_len:
#         wav = wav[:max_len]
#     else:
#         wav = np.pad(wav, (0, max_len - len(wav)))
#     return wav

# def wav_to_logmelspec(wav, sr=SAMPLE_RATE, n_mels=N_MELS, n_fft=N_FFT, hop_length=HOP_LENGTH):
#     """Convert waveform to log-mel spectrogram."""
#     mel = librosa.feature.melspectrogram(y=wav, sr=sr, n_fft=n_fft, hop_length=hop_length, n_mels=n_mels)
#     log_mel = librosa.power_to_db(mel, ref=np.max)
#     # Normalize
#     log_mel = (log_mel - np.mean(log_mel)) / (np.std(log_mel) + 1e-9)
#     return log_mel.astype(np.float32)

# # -----------------------------
# # Dataset class
# # -----------------------------
# class StudentAudioDataset(Dataset):
#     """Loads student audio samples and returns spectrogram tensors."""
#     def __init__(self, records):
#         """
#         records: list of dicts from MongoDB [{ 'student_id': 's01', 'name': 'Arya', 'audio_path': '../samples/student_arya.wav' }]
#         """
#         self.records = records
#         # Label mapping (e.g. s01 -> 0, s02 -> 1, ...)
#         self.label_map = {}
#         for rec in records:
#             sid = rec['student_id']
#             if sid not in self.label_map:
#                 self.label_map[sid] = len(self.label_map)

#         # Flatten all items
#         self.items = []
#         for rec in records:
#             self.items.append({
#                 "path": rec["audio_path"],
#                 "label": self.label_map[rec["student_id"]],
#                 "student_id": rec["student_id"],
#                 "name": rec.get("name", "")
#             })

#     def __len__(self):
#         return len(self.items)

#     def __getitem__(self, idx):
#         item = self.items[idx]
#         wav = load_wav(item["path"])
#         mel = wav_to_logmelspec(wav)  # (n_mels, time_frames)
#         mel = np.expand_dims(mel, axis=0)  # (1, n_mels, time_frames)
#         return torch.tensor(mel, dtype=torch.float32), torch.tensor(item["label"], dtype=torch.long)












# dataset.py
import os
import torch
import numpy as np
import librosa
from torch.utils.data import Dataset
import soundfile as sf
import pathlib

SAMPLE_RATE = 16000
DURATION = 2.0       # seconds
N_MELS = 64
N_FFT = 512
HOP_LENGTH = 256


# ---------------------------
# Audio Loading Utility
# ---------------------------
def load_wav(path, sr=SAMPLE_RATE, duration=DURATION):
    norm_path = str(pathlib.Path(path))
    if not os.path.exists(norm_path):
        raise FileNotFoundError(f"Audio file not found: {norm_path}")
    wav, file_sr = sf.read(norm_path, dtype='float32')
    if wav.ndim > 1:
        wav = wav.mean(axis=1)
    if file_sr != sr:
        wav = librosa.resample(y=wav, orig_sr=file_sr, target_sr=sr)

    max_len = int(sr * duration)
    if len(wav) > max_len:
        wav = wav[:max_len]
    else:
        wav = np.pad(wav, (0, max_len - len(wav)))
    return wav


# ---------------------------
# Convert WAV to Mel Spectrogram
# ---------------------------
def wav_to_logmelspec(wav, sr=SAMPLE_RATE, n_mels=N_MELS, n_fft=N_FFT, hop_length=HOP_LENGTH):
    mel = librosa.feature.melspectrogram(y=wav, sr=sr, n_fft=n_fft, hop_length=hop_length, n_mels=n_mels)
    log_mel = librosa.power_to_db(mel, ref=np.max)
    log_mel = (log_mel - np.mean(log_mel)) / (np.std(log_mel) + 1e-9)
    return log_mel.astype(np.float32)


# ---------------------------
# Custom Dataset Class
# ---------------------------
class StudentAudioDataset(Dataset):
    def __init__(self, records):
        self.samples = []
        self.label_map = {}
        label_id = 0

        for rec in records:
            sid = rec["student_id"]
            if sid not in self.label_map:
                self.label_map[sid] = label_id
                label_id += 1

            # each record now has a list of valid paths
            for p in rec.get("paths", []):
                norm_path = str(pathlib.Path(p))
                if os.path.exists(norm_path):
                    self.samples.append((norm_path, self.label_map[sid]))
                else:
                    print(f"⚠️ Skipping missing file: {norm_path}")

        if not self.samples:
            print("⚠️ No valid audio samples found in dataset!")

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        path, label = self.samples[idx]
        try:
            wav = load_wav(path)
        except Exception as e:
            print(f"⚠️ Error loading {path}: {e}")
            wav = np.zeros(int(SAMPLE_RATE * DURATION), dtype=np.float32)

        mel = wav_to_logmelspec(wav)  # (n_mels, time_frames)
        mel = np.expand_dims(mel, axis=0)  # (1, n_mels, time_frames)
        return torch.tensor(mel, dtype=torch.float32), torch.tensor(label, dtype=torch.long)
