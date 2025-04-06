import asyncio, os, sys, time, wave, threading
import pyaudio, numpy as np, speech_recognition as sr
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load API key and configure client
load_dotenv()
API_KEY = os.getenv("API_KEY")
client = genai.Client(api_key=API_KEY, http_options={'api_version': 'v1alpha'})
MODEL = "models/gemini-2.0-flash-exp"

# Audio settings
FORMAT = pyaudio.paInt16
CHANNELS = 1
SEND_SAMPLE_RATE = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE = 1024

# Audio directories
AUDIO_DIR = "user_audio"
THERAPIST_AUDIO_DIR = "therapist_audio"
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(THERAPIST_AUDIO_DIR, exist_ok=True)

# Initialize PyAudio
p = pyaudio.PyAudio()

class VirtualTherapist:
    def __init__(self):
        """Initialize the virtual therapist in audio mode only."""
        instruction_text = (
            "You are an empathetic and supportive virtual therapist. "
            "Listen actively, respond with empathy, ask open-ended questions, "
            "and provide supportive feedback. Maintain a professional and approachable tone, "
            "and use evidence-based therapeutic approaches. "
            "If the user says just 'goodbye' or 'end session', just say 'Hope I was able to help you, you can always come back to me for help' and end the session."
        )
        system_instruction = types.Content(parts=[types.Part(text=instruction_text)])
        self.config = types.LiveConnectConfig(
            response_modalities=["audio"],
            system_instruction=system_instruction,
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Kore")
                )
            )
        )
        self.recognizer = sr.Recognizer()
    
    async def send_with_retry(self, session, user_input, retries=5):
        """Attempt to send a message, retrying if an internal error occurs."""
        for attempt in range(retries):
            try:
                await session.send(input=user_input, end_of_turn=True)
                return
            except Exception as e:
                if "internal error" in str(e).lower():
                    print(f"Internal error during send, retrying... ({attempt+1}/{retries})")
                    await asyncio.sleep(1)
                else:
                    raise e
        raise Exception("Max retries reached for send.")

    async def start_session(self):
        max_session_retries = 5
        session_retry = 0
        while session_retry < max_session_retries:
            try:
                print("\n=== Virtual Therapist Session (AUDIO MODE) ===")
                print("Share your thoughts and I'll respond. Say 'goodbye' or 'end session' to finish.\n")
                async with client.aio.live.connect(model=MODEL, config=self.config) as session:
                    # Send initial greeting with retry
                    await self.send_with_retry(session, "Hello, I'm here as your virtual therapist. How are you feeling?")
                    await self.handle_response(session)
                    while True:
                        user_input = await self.get_audio_input()
                        if user_input and any(term in user_input.lower() for term in ["goodbye", "end session", "exit", "quit"]):
                            await self.send_with_retry(session, "The client wants to end our session.")
                            await self.handle_response(session)
                            return
                        if user_input:
                            try:
                                await self.send_with_retry(session, user_input)
                            except Exception as e:
                                print(f"Send error: {e}. Re-establishing session...")
                                raise e
                            await self.handle_response(session)
                        else:
                            print("I didn't catch that. Please try again.")
                break  # Exit if session completes successfully.
            except Exception as e:
                if "internal error" in str(e).lower() or "max retries reached" in str(e).lower():
                    session_retry += 1
                    print(f"Error encountered, reconnecting session... ({session_retry}/{max_session_retries})")
                    await asyncio.sleep(1)
                else:
                    print(f"Unexpected error: {e}")
                    break
        if session_retry >= max_session_retries:
            print("Session failed after maximum retries.")
        self.cleanup_audio_directory()
        print("\n=== Session Ended ===")
    
    def cleanup_audio_directory(self):
        """Remove all files in the user and therapist audio directories."""
        print("\nCleaning up audio files...")
        for filename in os.listdir(AUDIO_DIR):
            file_path = os.path.join(AUDIO_DIR, filename)
            if os.path.isfile(file_path):
                os.unlink(file_path)
        for filename in os.listdir(THERAPIST_AUDIO_DIR):
            file_path = os.path.join(THERAPIST_AUDIO_DIR, filename)
            if os.path.isfile(file_path):
                os.unlink(file_path)
        print(f"All files removed from {AUDIO_DIR} and {THERAPIST_AUDIO_DIR}.")
    
    async def handle_response(self, session):
        """Handle the audio response from the model."""
        await self.play_audio_response(session)
    
    async def play_audio_response(self, session):
        """Play and save the audio response from the model."""
        print("\nTherapist> [Speaking...]")
        output_stream = p.open(format=FORMAT, channels=CHANNELS, rate=RECEIVE_SAMPLE_RATE, output=True)
        audio_chunks = []
        try:
            async for response in session.receive():
                if getattr(response, "data", None):
                    audio_chunks.append(response.data)
                    try:
                        output_stream.write(response.data)
                    except Exception as e:
                        print(f"Error playing audio: {e}")
                if getattr(getattr(response, "server_content", None), "turn_complete", False):
                    break
        except Exception as e:
            print(f"\nError processing audio: {e}")
        finally:
            output_stream.close()
            print("[Done speaking]")
        if audio_chunks:
            file_path = os.path.join(THERAPIST_AUDIO_DIR, f"therapist_output_{int(time.time())}.wav")
            try:
                with wave.open(file_path, 'wb') as wf:
                    wf.setnchannels(CHANNELS)
                    wf.setsampwidth(p.get_sample_size(FORMAT))
                    wf.setframerate(RECEIVE_SAMPLE_RATE)
                    wf.writeframes(b''.join(audio_chunks))
                print(f"Audio saved to {file_path}")
            except Exception as e:
                print(f"Error saving audio: {e}")
    
    async def get_audio_input(self):
        """
        Record audio input and transcribe it.
        Automatically terminates recording after detecting silence once speech has started.
        """
        print("Listening... (Recording will start automatically and stop when silence is detected)")
        frames = []
        recording_active = threading.Event()
        recording_active.set()

        # Parameters for silence detection
        silence_threshold = 200         # RMS threshold; adjust based on your mic sensitivity/environment
        silence_chunk_limit = 32        # Number of consecutive silent chunks to consider as "end of speech"

        def record_audio():
            stream = p.open(format=FORMAT, channels=CHANNELS, rate=SEND_SAMPLE_RATE, input=True, frames_per_buffer=CHUNK_SIZE)
            speech_started = False
            silent_chunks = 0
            try:
                while recording_active.is_set():
                    data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
                    frames.append(data)
                    audio_data = np.frombuffer(data, dtype=np.int16).astype(np.float32)
                    rms = np.sqrt(np.mean(audio_data**2)) if audio_data.size > 0 else 0

                    if rms > silence_threshold:
                        speech_started = True
                        silent_chunks = 0
                    else:
                        if speech_started:
                            silent_chunks += 1

                    # Optional: Visual feedback on recording volume
                    vol = int(min(30, np.abs(audio_data).mean() / 100))
                    sys.stdout.write(f"\rRecording: [{'|' * vol}{' ' * (30 - vol)}]")
                    sys.stdout.flush()

                    if speech_started and silent_chunks >= silence_chunk_limit:
                        recording_active.clear()
                        break
            finally:
                stream.stop_stream()
                stream.close()

        t = threading.Thread(target=record_audio, daemon=True)
        t.start()

        while t.is_alive():
            await asyncio.sleep(0.1)
        print("\nRecording stopped. Transcribing...")

        temp_filename = os.path.join(AUDIO_DIR, f"user_input_{int(time.time())}.wav")
        with wave.open(temp_filename, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(p.get_sample_size(FORMAT))
            wf.setframerate(SEND_SAMPLE_RATE)
            wf.writeframes(b''.join(frames))
        
        text = await self.transcribe_audio(temp_filename)
        print(f"Transcript: {text}")
        return text
    
    async def transcribe_audio(self, audio_file):
        """Transcribe an audio file to text using Google Speech Recognition."""
        try:
            return await asyncio.to_thread(self._perform_transcription, audio_file)
        except Exception as e:
            print(f"Error transcribing: {e}")
            return "Transcription failed. Please try again."
    
    def _perform_transcription(self, audio_file):
        with sr.AudioFile(audio_file) as source:
            audio_data = self.recognizer.record(source)
            try:
                return self.recognizer.recognize_google(audio_data)
            except sr.UnknownValueError:
                return "Couldn't understand the audio."
            except sr.RequestError as e:
                return f"Request error: {e}"

def list_audio_devices():
    """List available audio devices."""
    print("\n=== Available Audio Devices ===")
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        print(f"Device {i}: {info['name']} | In: {info['maxInputChannels']} | Out: {info['maxOutputChannels']} | Rate: {info['defaultSampleRate']}")
    print("===============================\n")

def cleanup_audio():
    """Remove all files in the user and therapist audio directories."""
    print("\nCleaning up audio files...")
    for filename in os.listdir(AUDIO_DIR):
        file_path = os.path.join(AUDIO_DIR, filename)
        if os.path.isfile(file_path):
            os.unlink(file_path)
    for filename in os.listdir(THERAPIST_AUDIO_DIR):
        file_path = os.path.join(THERAPIST_AUDIO_DIR, filename)
        if os.path.isfile(file_path):
            os.unlink(file_path)
    print(f"All files removed from {AUDIO_DIR} and {THERAPIST_AUDIO_DIR}.")

async def main():
    list_audio_devices()
    therapist = VirtualTherapist()
    await therapist.start_session()
    cleanup_audio()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        p.terminate()