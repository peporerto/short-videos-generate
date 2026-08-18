import os
from pydub import AudioSegment

audio_path = "output/audio.mp3"
if os.path.exists(audio_path):
    sound = AudioSegment.from_file(audio_path)
    print(f"Duration: {len(sound)/1000.0}s")
    print(f"DBFS (volume): {sound.dbfs}")
    print(f"Max DBFS: {sound.max_dbfs}")
else:
    print("File not found")
