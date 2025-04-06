import pyaudio
import numpy as np
import time

# Audio settings
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000  # Adjust as needed
CHUNK = 1024

p = pyaudio.PyAudio()

# Open the stream for recording
stream = p.open(format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK)

print("Recording... Press Ctrl+C to stop.")

try:
    while True:
        data = stream.read(CHUNK, exception_on_overflow=False)
        # Convert byte data to numpy array and cast to float32 to avoid overflow
        audio_data = np.frombuffer(data, dtype=np.int16).astype(np.float32)
        # Compute RMS only if audio_data is not empty
        if audio_data.size > 0:
            rms = np.sqrt(np.mean(audio_data ** 2))
        else:
            rms = 0
        print(f"RMS: {rms:.2f}")
        time.sleep(0.1)  # Delay to make the output readable
except KeyboardInterrupt:
    print("Recording stopped.")
finally:
    stream.stop_stream()
    stream.close()
    p.terminate()
