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
    def __init__(self, mode="text"):
        """Initialize the virtual therapist in text or audio mode."""
        self.mode = mode
        instruction_text = (
            "You are an empathetic and supportive virtual therapist. "
            "Listen actively, respond with empathy, ask open-ended questions, "
            "and provide supportive feedback. Maintain a professional and approachable tone, "
            "and use evidence-based therapeutic approaches."
            "If the user says just 'goodbye' or 'end session', Just say 'Hope I was able to help you, you can always come back to me for help' and end the session."
        )
        system_instruction = types.Content(parts=[types.Part(text=instruction_text)])
        if mode == "text":
            self.config = types.LiveConnectConfig(
                response_modalities=["text"],
                system_instruction=system_instruction
            )
        elif mode == "audio":
            self.config = types.LiveConnectConfig(
                response_modalities=["audio"],
                system_instruction=system_instruction,
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Kore")
                    )
                )
            )
        else:
            raise ValueError("Mode must be either 'text' or 'audio'")
        self.recognizer = sr.Recognizer()
    
    async def start_session(self):
        print(f"\n=== Virtual Therapist Session ({self.mode.upper()} MODE) ===")
        print("Share your thoughts and I'll respond. Type 'goodbye' or 'end session' to finish.\n")
        try:
            async with client.aio.live.connect(model=MODEL, config=self.config) as session:
                await session.send(input="Hello, I'm here as your virtual therapist. How are you feeling?", end_of_turn=True)
                await self.handle_response(session)
                while True:
                    user_input = input("\nYou> ") if self.mode == "text" else await self.get_audio_input()
                    if user_input and any(term in user_input.lower() for term in ["goodbye", "end session", "exit", "quit"]):
                        await session.send(input="The client wants to end our session.", end_of_turn=True)
                        await self.handle_response(session)
                        break
                    if user_input:
                        await session.send(input=user_input, end_of_turn=True)
                        await self.handle_response(session)
                    else:
                        print("I didn't catch that. Please try again.")
        except Exception as e:
            print(f"\nError: {e}")
        finally:
            self.cleanup_audio_directory()
            print("\n=== Session Ended ===")
    
    def cleanup_audio_directory(self):
        """Remove all files in the user audio directory."""
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
        """Delegate response handling based on mode."""
        if self.mode == "text":
            await self.display_text_response(session)
        else:
            await self.play_audio_response(session)
    
    async def display_text_response(self, session):
        """Display text response from the model."""
        print("\nTherapist> ", end="")
        full_response = ""
        try:
            async for response in session.receive():
                if getattr(response, "text", None):
                    print(response.text, end="", flush=True)
                    full_response += response.text
                if getattr(getattr(response, "server_content", None), "turn_complete", False):
                    break
        except Exception as e:
            print(f"\nError processing response: {e}")
        return full_response
            
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
        """Record audio input and transcribe it."""
        print("Listening... (Recording will start automatically)\nPress Enter to stop.")
        frames = []
        recording_active = threading.Event()
        recording_active.set()
        
        def record_audio():
            stream = p.open(format=FORMAT, channels=CHANNELS, rate=SEND_SAMPLE_RATE, input=True, frames_per_buffer=CHUNK_SIZE)
            try:
                while recording_active.is_set():
                    data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
                    frames.append(data)
                    if len(frames) % 5 == 0:
                        vol = int(min(30, np.abs(np.frombuffer(data, dtype=np.int16)).mean() / 100))
                        sys.stdout.write(f"\rRecording: [{'|' * vol}{' ' * (30 - vol)}] Press Enter to stop")
                        sys.stdout.flush()
            finally:
                stream.stop_stream()
                stream.close()
        
        threading.Thread(target=record_audio, daemon=True).start()
        await asyncio.to_thread(input, "")
        recording_active.clear()
        await asyncio.sleep(0.5)
        print("\nRecording stopped. Transcribing...")
        if not frames:
            return "I didn't hear anything."
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

async def main():
    list_audio_devices()
    while True:
        choice = input("\nChoose mode:\n1. Text\n2. Audio\nEnter 1 or 2: ")
        if choice == "1":
            mode = "text"
            break
        elif choice == "2":
            mode = "audio"
            break
        else:
            print("Invalid choice. Please try again.")
    therapist = VirtualTherapist(mode=mode)
    await therapist.start_session()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        p.terminate()
