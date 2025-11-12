import soundfile as sf

try:
    info = sf.info("./uploads/1GV22CS084_20251111_103000.wav")
    print(info)
except Exception as e:
    print("❌ Error:", e)
