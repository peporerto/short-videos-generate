import subprocess
import wave
import numpy as np

# Convert to wav
wav_path = "output/temp_pop.wav"
subprocess.run([
    "ffmpeg", "-y", "-i", "input/audio/dragon-studio-clean-minimal-pop-467466.mp3",
    wav_path
], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

with wave.open(wav_path, "r") as f:
    frames = f.readframes(f.getnframes())
    rate = f.getframerate()
    # convert to numpy array
    data = np.frombuffer(frames, dtype=np.int16)
    # check channels
    if f.getnchannels() == 2:
        data = data.reshape(-1, 2)
        amplitude = np.abs(data).max(axis=1)
    else:
        amplitude = np.abs(data)
    
    # Find first sample above threshold
    threshold = 100 # arbitrary small number
    indices = np.where(amplitude > threshold)[0]
    if len(indices) > 0:
        first_sound_sec = indices[0] / rate
        print(f"First sound starts at: {first_sound_sec:.4f}s")
    else:
        print("No sound found above threshold")
