import pyaudio
import wave
from pydub import AudioSegment
import time
import os
import signal

def handle_interrupt(signum, frame):
    global recording
    recording = False
    print("\nStopping recording...")

def record_audio():
    global recording
    recording = True
    
    # Audio recording parameters
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 44100
    
    try:
        # Set up interrupt handler
        signal.signal(signal.SIGINT, handle_interrupt)
        
        # Initialize PyAudio
        p = pyaudio.PyAudio()
        
        print("\nRecording will start in 3 seconds...")
        print("Press Ctrl+C to stop recording")
        time.sleep(3)
        
        # Open stream
        stream = p.open(format=FORMAT,
                       channels=CHANNELS,
                       rate=RATE,
                       input=True,
                       frames_per_buffer=CHUNK)
        
        print("* Recording...")
        
        frames = []
        while recording:
            data = stream.read(CHUNK, exception_on_overflow=False)
            frames.append(data)
            
        print("* Done recording")
        
        # Stop and close the stream
        stream.stop_stream()
        stream.close()
        p.terminate()
        
        if len(frames) == 0:
            print("No audio recorded!")
            return
        
        # Save as WAV first
        temp_wav = "temp_recording.wav"
        wf = wave.open(temp_wav, 'wb')
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(p.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))
        wf.close()
        
        # Convert WAV to MP3
        audio = AudioSegment.from_wav(temp_wav)
        audio.export("input_audio.mp3", format="mp3")
        
        # Clean up temporary WAV file
        if os.path.exists(temp_wav):
            os.remove(temp_wav)
        
        print("Audio saved as 'input_audio.mp3'")
        
    except Exception as e:
        print(f"An error occurred: {e}")
        if 'p' in locals():
            p.terminate()

if __name__ == "__main__":
    record_audio()