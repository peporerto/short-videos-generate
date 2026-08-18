import subprocess
import wave
import numpy as np

# Convert video audio to wav
wav_path = "output/temp_final.wav"
subprocess.run([
    "ffmpeg", "-y", "-i", "output/final_video.mp4",
    "-vn", "-acodec", "pcm_s16le", wav_path
], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

with wave.open(wav_path, "r") as f:
    frames = f.readframes(f.getnframes())
    rate = f.getframerate()
    data = np.frombuffer(frames, dtype=np.int16)
    if f.getnchannels() == 2:
        data = data.reshape(-1, 2)
        amplitude = np.abs(data).max(axis=1)
    else:
        amplitude = np.abs(data)
    
    # Let's inspect the amplitude around 0.0s to 0.2s, and 1.3s to 1.6s
    # print some stats
    print("Total duration:", len(amplitude) / rate, "seconds")
    
    # 0.0s to 0.2s
    idx_0 = int(0.0 * rate)
    idx_0_end = int(0.2 * rate)
    print(f"Max amplitude around 0.0s-0.2s: {amplitude[idx_0:idx_0_end].max()}")
    
    # 1.3s to 1.6s
    idx_1 = int(1.3 * rate)
    idx_1_end = int(1.6 * rate)
    print(f"Max amplitude around 1.3s-1.6s: {amplitude[idx_1:idx_1_end].max()}")
    
    # 0.5s to 1.0s (should be just voice)
    idx_v = int(0.5 * rate)
    idx_v_end = int(1.0 * rate)
    print(f"Max amplitude around 0.5s-1.0s (voice only): {amplitude[idx_v:idx_v_end].max()}")
