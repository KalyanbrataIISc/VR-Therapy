import asyncio
import os
import sys
import pyaudio
import wave
import time
import numpy as np
import threading
import speech_recognition as sr
import shutil
import select
import subprocess
import tempfile
from dotenv import load_dotenv
from google import genai
from google.genai import types
import cv2
import pygame
import queue
from moviepy import VideoFileClip

# Load API key from .env file
load_dotenv()
API_KEY = os.getenv("API_KEY")

# Configure client with API key
client = genai.Client(api_key=API_KEY, http_options={'api_version': 'v1alpha'})

# The only model that works with Live API based on our tests
MODEL = "models/gemini-2.0-flash-exp"

# Audio settings
FORMAT = pyaudio.paInt16
CHANNELS = 1
SEND_SAMPLE_RATE = 16000  # Input must be 16kHz for Gemini
RECEIVE_SAMPLE_RATE = 24000  # Output is 24kHz from Gemini
CHUNK_SIZE = 1024

# Avatar settings
AVATAR_WIDTH = 600
AVATAR_HEIGHT = 600
FPS = 30

# Directory settings
AUDIO_DIR = "user_audio"
AVATAR_DIR = "avatar_assets"
OUTPUT_DIR = "lip_sync_output"
WAV2LIP_DIR = "Wav2Lip"  # Directory where Wav2Lip is installed

# Create directories if they don't exist
for directory in [AUDIO_DIR, AVATAR_DIR, OUTPUT_DIR]:
    if not os.path.exists(directory):
        os.makedirs(directory)

# Initialize PyAudio
p = pyaudio.PyAudio()

# Event for communication between threads
pygame_initialized = threading.Event()
animation_event_queue = queue.Queue()

class AdvancedAvatar:
    def __init__(self):
        """Initialize the advanced avatar with AI lip-syncing"""
        self.is_speaking = False
        self.current_frame = None
        self.default_face = None
        self.video_playing = False
        self.video_thread = None
        self.stop_video = threading.Event()
        
        # Load default face image
        self.load_default_face()
    
    def load_default_face(self):
        """Load or download a default face image"""
        default_face_path = os.path.join(AVATAR_DIR, "default_face.jpg")
        
        if not os.path.exists(default_face_path):
            # If the default face doesn't exist, use a placeholder
            print("Creating a placeholder face image...")
            # Create a blank image as placeholder
            blank_face = np.ones((AVATAR_HEIGHT, AVATAR_WIDTH, 3), dtype=np.uint8) * 255
            
            # Add some basic facial features
            # Draw a simple face outline
            cv2.ellipse(blank_face, 
                        (AVATAR_WIDTH//2, AVATAR_HEIGHT//2), 
                        (AVATAR_WIDTH//3, AVATAR_HEIGHT//2), 
                        0, 0, 360, (200, 200, 200), -1)
            
            # Draw eyes
            eye_size = AVATAR_WIDTH // 10
            left_eye_pos = (AVATAR_WIDTH//2 - AVATAR_WIDTH//6, AVATAR_HEIGHT//2 - AVATAR_HEIGHT//10)
            right_eye_pos = (AVATAR_WIDTH//2 + AVATAR_WIDTH//6, AVATAR_HEIGHT//2 - AVATAR_HEIGHT//10)
            
            cv2.circle(blank_face, left_eye_pos, eye_size, (255, 255, 255), -1)
            cv2.circle(blank_face, right_eye_pos, eye_size, (255, 255, 255), -1)
            cv2.circle(blank_face, left_eye_pos, eye_size//2, (0, 0, 0), -1)
            cv2.circle(blank_face, right_eye_pos, eye_size//2, (0, 0, 0), -1)
            
            # Draw mouth
            mouth_width = AVATAR_WIDTH // 4
            mouth_height = AVATAR_HEIGHT // 12
            mouth_pos = (AVATAR_WIDTH//2 - mouth_width//2, AVATAR_HEIGHT//2 + AVATAR_HEIGHT//6)
            cv2.rectangle(blank_face, 
                         mouth_pos, 
                         (mouth_pos[0] + mouth_width, mouth_pos[1] + mouth_height), 
                         (150, 100, 100), -1)
            
            # Save the placeholder
            cv2.imwrite(default_face_path, blank_face)
            
        # Load the face
        self.default_face = cv2.imread(default_face_path)
        if self.default_face is None:
            raise ValueError(f"Failed to load default face from {default_face_path}")
        
        # Resize to desired dimensions
        self.default_face = cv2.resize(self.default_face, (AVATAR_WIDTH, AVATAR_HEIGHT))
        
        # Convert to pygame surface
        self.current_frame = self.default_face.copy()
    
    def set_speaking(self, is_speaking):
        """Set the speaking state"""
        if is_speaking != self.is_speaking:
            self.is_speaking = is_speaking
            animation_event_queue.put({"type": "speaking_state", "state": is_speaking})
    
    def get_current_frame_as_surface(self):
        """Convert the current OpenCV frame to a Pygame surface"""
        if self.current_frame is None:
            return None
        
        # Convert BGR to RGB
        frame_rgb = cv2.cvtColor(self.current_frame, cv2.COLOR_BGR2RGB)
        
        # Create pygame surface
        surface = pygame.Surface((frame_rgb.shape[1], frame_rgb.shape[0]))
        pygame.surfarray.blit_array(surface, frame_rgb.swapaxes(0, 1))
        
        return surface
    
    def play_video(self, video_path):
        """Play a video file as the avatar"""
        if self.video_thread is not None and self.video_thread.is_alive():
            self.stop_video.set()
            self.video_thread.join()
        
        self.stop_video.clear()
        self.video_thread = threading.Thread(target=self._video_player_thread, args=(video_path,))
        self.video_thread.daemon = True
        self.video_thread.start()
    
    def _video_player_thread(self, video_path):
        """Thread function to play a video"""
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                print(f"Error: Could not open video {video_path}")
                return
            
            frame_rate = cap.get(cv2.CAP_PROP_FPS)
            frame_delay = 1.0 / frame_rate
            
            self.video_playing = True
            
            while not self.stop_video.is_set():
                ret, frame = cap.read()
                if not ret:
                    # Restart the video when it ends
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                
                # Resize frame to match avatar dimensions
                frame = cv2.resize(frame, (AVATAR_WIDTH, AVATAR_HEIGHT))
                
                # Update current frame
                self.current_frame = frame
                animation_event_queue.put({"type": "frame_update"})
                
                # Sleep to match frame rate
                time.sleep(frame_delay)
            
            cap.release()
            self.video_playing = False
            self.current_frame = self.default_face.copy()
            
        except Exception as e:
            print(f"Error in video playback: {e}")
            self.video_playing = False
            self.current_frame = self.default_face.copy()
    
    def generate_lip_sync(self, audio_file, output_path):
        """Generate lip-synced video using Wav2Lip"""
        # Check if Wav2Lip is installed
        if not os.path.exists(WAV2LIP_DIR):
            print(f"Error: Wav2Lip not found at {WAV2LIP_DIR}")
            print("Simulating lip-sync generation instead...")
            return self.simulate_lip_sync(audio_file, output_path)
        
        # Path to the face image
        face_path = os.path.join(AVATAR_DIR, "default_face.jpg")
        
        # Construct the command for Wav2Lip
        cmd = [
            "python", os.path.join(WAV2LIP_DIR, "inference.py"),
            "--checkpoint_path", os.path.join(WAV2LIP_DIR, "checkpoints", "wav2lip_gan.pth"),
            "--face", face_path,
            "--audio", audio_file,
            "--outfile", output_path,
            "--static"  # Use this for static images
        ]
        
        try:
            print("Generating lip-sync video...")
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                print(f"Error generating lip-sync: {stderr.decode()}")
                return self.simulate_lip_sync(audio_file, output_path)
                
            print("Lip-sync generation complete!")
            return output_path
            
        except Exception as e:
            print(f"Error running Wav2Lip: {e}")
            return self.simulate_lip_sync(audio_file, output_path)
    
    def simulate_lip_sync(self, audio_file, output_path):
        """Simulate lip-sync generation for testing"""
        print("Simulating lip-sync generation...")
        
        # Get audio duration
        with wave.open(audio_file, 'rb') as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            duration = frames / float(rate)
        
        # Create a video with simple mouth movements
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        video = cv2.VideoWriter(output_path, fourcc, FPS, (AVATAR_WIDTH, AVATAR_HEIGHT))
        
        if not video.isOpened():
            print(f"Error: Could not create video writer for {output_path}")
            return None
        
        # Number of frames based on duration and FPS
        num_frames = int(duration * FPS)
        
        # Generate simple mouth movements
        for i in range(num_frames):
            frame = self.default_face.copy()
            
            # Calculate mouth openness based on frame position
            # This creates a simple opening and closing effect
            phase = (i % 30) / 30.0
            if phase < 0.5:
                openness = phase * 2
            else:
                openness = (1 - phase) * 2
            
            # Mouth coordinates
            mouth_width = int(AVATAR_WIDTH // 4)
            mouth_height = int((AVATAR_HEIGHT // 12) * (0.5 + openness))
            mouth_x = AVATAR_WIDTH//2 - mouth_width//2
            mouth_y = AVATAR_HEIGHT//2 + AVATAR_HEIGHT//6
            
            # Draw mouth with varying height
            cv2.rectangle(frame, 
                         (mouth_x, mouth_y), 
                         (mouth_x + mouth_width, mouth_y + mouth_height), 
                         (100, 100, 150), -1)
            
            video.write(frame)
        
        video.release()
        
        # Check if the video was created successfully
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            print(f"Simulated lip-sync video created: {output_path}")
            return output_path
        else:
            print(f"Failed to create simulated lip-sync video: {output_path}")
            return None


# Pygame initialization function to run in main thread
def initialize_pygame():
    """Initialize pygame in the main thread"""
    pygame.init()
    screen = pygame.display.set_mode((AVATAR_WIDTH, AVATAR_HEIGHT))
    pygame.display.set_caption("Advanced Virtual Therapist")
    font = pygame.freetype.SysFont('Arial', 16)
    clock = pygame.time.Clock()
    
    # Signal that pygame is initialized
    pygame_initialized.set()
    
    return screen, font, clock


# Animation loop function to run in main thread
def run_pygame_animation(screen, font, clock, avatar):
    """Run animation update in main thread - called periodically"""
    # Handle events
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            return False
    
    # Check for animation events
    while not animation_event_queue.empty():
        try:
            event = animation_event_queue.get_nowait()
            if event["type"] == "speaking_state":
                avatar.is_speaking = event["state"]
            elif event["type"] == "exit":
                return False
        except queue.Empty:
            break
    
    # Clear screen
    screen.fill((240, 240, 255))
    
    # Get current frame as surface
    frame_surface = avatar.get_current_frame_as_surface()
    
    if frame_surface:
        screen.blit(frame_surface, (0, 0))
    
    # Display status
    status = "Speaking" if avatar.is_speaking else "Listening"
    font.render_to(screen, (10, 10), f"Status: {status}", (0, 0, 0))
    
    # Update display
    pygame.display.flip()
    
    # Cap the frame rate
    clock.tick(FPS)
    return True


class VirtualTherapist:
    def __init__(self, mode="text"):
        """Initialize the virtual therapist.
        
        Args:
            mode: Either "text" or "audio" (can't be both due to API limitations)
        """
        self.mode = mode
        self.avatar = AdvancedAvatar()
        self.running = True
        
        # System instructions for the therapist
        system_instruction = types.Content(
            parts=[
                types.Part(
                    text="""You are an empathetic and supportive virtual therapist. 
                    
Your role is to create a safe space where clients can explore their thoughts and feelings.
- Listen actively and respond with empathy
- Ask open-ended questions to help clients reflect
- Provide supportive, non-judgmental feedback
- Focus on helping clients develop insights and coping strategies
- Remember previous discussions to provide continuity of care
- Be warm, patient, and understanding in your tone
- Acknowledge emotions and validate experiences
- When appropriate, guide toward evidence-based therapeutic approaches
- Maintain a professional yet approachable demeanor
- Never rush clients and give them space to process their thoughts"""
                )
            ]
        )
        
        # Configure based on mode
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
        
        # Initialize speech recognizer
        self.recognizer = sr.Recognizer()
    
    async def start_session(self):
        """Start a therapy session"""
        print(f"\n=== Virtual Therapist Session ({self.mode.upper()} MODE) ===")
        print("Share your thoughts and feelings, and I'll respond as a virtual therapist.")
        print("Type 'goodbye' or 'end session' to finish.\n")
        
        # Initialize pygame in main thread before starting the session
        screen, font, clock = initialize_pygame()
        
        # Wait for pygame to initialize
        pygame_initialized.wait()
        
        try:
            async with client.aio.live.connect(model=MODEL, config=self.config) as session:
                # Send an initial greeting
                initial_greeting = "Hello, I'm here as your virtual therapist today. How are you feeling?"
                await session.send(input=initial_greeting, end_of_turn=True)
                
                # Process the initial response
                await self.handle_response(session, screen, font, clock)
                
                # Main conversation loop
                while self.running:
                    # Update avatar animation
                    if not run_pygame_animation(screen, font, clock, self.avatar):
                        self.running = False
                        break
                    
                    # Set avatar to listening mode
                    self.avatar.set_speaking(False)
                    
                    # Check if we need to get user input
                    if self.mode == "text":
                        user_input = await asyncio.to_thread(input, "\nYou> ")
                    else:  # audio mode
                        print("\nYou> ", end="")
                        user_input = await self.get_audio_input(screen, font, clock)
                        print(f"{user_input}")
                    
                    # Check for exit commands
                    if user_input and any(exit_term in user_input.lower() for exit_term in ["goodbye", "end session", "exit", "quit"]):
                        await session.send(input="The client wants to end our session now.", end_of_turn=True)
                        await self.handle_response(session, screen, font, clock)
                        break
                    
                    # Send user input to the model
                    if user_input:  # Only send if we have input
                        await session.send(input=user_input, end_of_turn=True)
                        
                        # Handle the response
                        await self.handle_response(session, screen, font, clock)
                    else:
                        print("I didn't catch that. Can you please try again?")
                    
        except Exception as e:
            print(f"\nError in session: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Clean up the audio directory when the session ends
            self.cleanup_audio_directory()
            animation_event_queue.put({"type": "exit"})
            pygame.quit()
            print("\n=== Session Ended ===")
    
    def cleanup_audio_directory(self):
        """Clean up the audio directory by removing all files"""
        try:
            print("\nCleaning up audio files...")
            for filename in os.listdir(AUDIO_DIR):
                file_path = os.path.join(AUDIO_DIR, filename)
                if os.path.isfile(file_path):
                    os.unlink(file_path)
            
            # Also clean up the output directory
            for filename in os.listdir(OUTPUT_DIR):
                file_path = os.path.join(OUTPUT_DIR, filename)
                if os.path.isfile(file_path):
                    os.unlink(file_path)
                    
            print(f"All temporary files removed.")
        except Exception as e:
            print(f"Error cleaning up directories: {e}")
    
    async def handle_response(self, session, screen, font, clock):
        """Handle the response from the model based on mode"""
        # Set avatar to speaking mode
        self.avatar.set_speaking(True)
        
        if self.mode == "text":
            await self.display_text_response(session, screen, font, clock)
        else:  # audio mode
            await self.play_audio_response(session, screen, font, clock)
        
        # Set avatar back to listening mode
        self.avatar.set_speaking(False)
            
    async def display_text_response(self, session, screen, font, clock):
        """Display text response"""
        print("\nTherapist> ", end="")
        full_response = ""
        
        try:
            async for response in session.receive():
                # Update animation
                if not run_pygame_animation(screen, font, clock, self.avatar):
                    self.running = False
                    break
                
                # Process text responses
                if hasattr(response, 'text') and response.text is not None:
                    print(response.text, end="", flush=True)
                    full_response += response.text
                
                # Check for turn completion
                if hasattr(response, 'server_content') and response.server_content:
                    if hasattr(response.server_content, 'turn_complete') and response.server_content.turn_complete:
                        break
            
            # Convert text to speech for lip-syncing
            if full_response:
                # Create temporary WAV file
                timestamp = int(time.time())
                temp_audio_path = os.path.join(AUDIO_DIR, f"response_{timestamp}.wav")
                
                # Use a TTS system to generate audio from text
                # For this example, we'll simulate TTS with a simple beep sound
                self.generate_simple_audio(temp_audio_path, len(full_response) // 5)
                
                # Generate lip-sync video
                temp_video_path = os.path.join(OUTPUT_DIR, f"lipsync_{timestamp}.mp4")
                video_path = self.avatar.generate_lip_sync(temp_audio_path, temp_video_path)
                
                if video_path and os.path.exists(video_path):
                    # Play the lip-sync video
                    self.avatar.play_video(video_path)
            
        except Exception as e:
            print(f"\nError processing response: {e}")
        
        return full_response
    
    def generate_simple_audio(self, output_path, duration_seconds):
        """Generate a simple audio file for testing"""
        # Sample rate and parameters
        sample_rate = 44100
        frequency = 440  # A4 note
        
        # Generate time array
        t = np.linspace(0, duration_seconds, int(duration_seconds * sample_rate), False)
        
        # Generate sine wave with fade in/out
        fade_duration = 0.1
        fade_samples = int(fade_duration * sample_rate)
        
        # Create raw sine wave
        wave_data = np.sin(frequency * 2 * np.pi * t)
        
        # Apply fade in
        if len(wave_data) > 2 * fade_samples:
            fade_in = np.linspace(0, 1, fade_samples)
            fade_out = np.linspace(1, 0, fade_samples)
            wave_data[:fade_samples] *= fade_in
            wave_data[-fade_samples:] *= fade_out
        
        # Convert to int16
        wave_data = (wave_data * 32767).astype(np.int16)
        
        # Save as WAV file
        with wave.open(output_path, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(sample_rate)
            wf.writeframes(wave_data.tobytes())
    
    async def play_audio_response(self, session, screen, font, clock):
        """Play audio response"""
        print("\nTherapist> [Speaking...]")
        
        # Create temporary file for the audio
        timestamp = int(time.time())
        temp_audio_path = os.path.join(AUDIO_DIR, f"response_{timestamp}.wav")
        temp_video_path = os.path.join(OUTPUT_DIR, f"lipsync_{timestamp}.mp4")
        
        # Set up audio output stream
        output_stream = p.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RECEIVE_SAMPLE_RATE,
            output=True
        )
        
        # Create temp file for saving the audio
        with wave.open(temp_audio_path, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(p.get_sample_size(FORMAT))
            wf.setframerate(RECEIVE_SAMPLE_RATE)
            
            all_audio_data = bytearray()
            
            try:
                # Create a buffer to collect audio chunks for mouth analysis
                audio_buffer = []
                buffer_size = 5  # Number of chunks to analyze at once
                
                async for response in session.receive():
                    # Update animation
                    if not run_pygame_animation(screen, font, clock, self.avatar):
                        self.running = False
                        break
                    
                    # Process audio data
                    if hasattr(response, 'data') and response.data is not None:
                        try:
                            # Play the audio
                            output_stream.write(response.data)
                            
                            # Save audio data to file
                            wf.writeframes(response.data)
                            all_audio_data.extend(response.data)
                            
                        except Exception as e:
                            print(f"Error playing audio: {e}")
                    
                    # Check for turn completion
                    if hasattr(response, 'server_content') and response.server_content:
                        if hasattr(response.server_content, 'turn_complete') and response.server_content.turn_complete:
                            break
                
                # Generate lip-sync video
                video_path = self.avatar.generate_lip_sync(temp_audio_path, temp_video_path)
                
                if video_path and os.path.exists(video_path):
                    # Play the lip-sync video
                    self.avatar.play_video(video_path)
                
            except Exception as e:
                print(f"\nError processing audio response: {e}")
            finally:
                output_stream.close()
                print("[Done speaking]")
    
    async def get_audio_input(self, screen, font, clock):
        """Record audio input and automatically transcribe it"""
        print("Listening... (Recording will automatically start)")
        print("Press Enter when you're done speaking")
        
        # Start recording in a separate thread
        frames = []
        stop_recording = threading.Event()
        recording_active = threading.Event()
        recording_active.set()  # Start as active
        
        def record_audio():
            # Open the audio stream
            stream = p.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=SEND_SAMPLE_RATE,
                input=True,
                frames_per_buffer=CHUNK_SIZE
            )
            
            try:
                while recording_active.is_set():
                    data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
                    frames.append(data)
                    
                    # Calculate volume for visualization
                    audio_data = np.frombuffer(data, dtype=np.int16)
                    volume_norm = np.abs(audio_data).mean()
                    
                    # Print volume level (but not too often to avoid console flooding)
                    if len(frames) % 5 == 0:
                        bars = int(min(30, volume_norm / 100))
                        sys.stdout.write(f"\rRecording: [{'|' * bars}{' ' * (30 - bars)}] Press Enter when done")
                        sys.stdout.flush()
            finally:
                stream.stop_stream()
                stream.close()
                stop_recording.set()
        
        # Start recording thread
        recording_thread = threading.Thread(target=record_audio)
        recording_thread.daemon = True
        recording_thread.start()
        
        # Wait for Enter key press in the main thread, while updating animation
        waiting_for_input = True
        while waiting_for_input and self.running:
            # Update animation
            if not run_pygame_animation(screen, font, clock, self.avatar):
                self.running = False
                recording_active.clear()
                break
            
            # Check if Enter was pressed (non-blocking)
            readable, _, _ = select.select([sys.stdin], [], [], 0)
            if sys.stdin in readable:
                input()  # Consume the Enter key
                waiting_for_input = False
        
        # Stop recording
        recording_active.clear()
        
        # Wait for recording thread to finish
        await asyncio.sleep(0.5)
        
        print("\nRecording stopped. Transcribing...")
        
        if not frames:
            return "I didn't hear anything."
            
        # Create temporary WAV file for speech recognition in the user_audio directory
        timestamp = int(time.time())
        temp_filename = os.path.join(AUDIO_DIR, f"user_input_{timestamp}.wav")
        with wave.open(temp_filename, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(p.get_sample_size(FORMAT))
            wf.setframerate(SEND_SAMPLE_RATE)
            wf.writeframes(b''.join(frames))
        
        # Perform speech recognition
        text = await self.transcribe_audio(temp_filename)
        
        # Notify user of the transcript
        print(f"Transcript: {text}")
            
        return text
    
    async def transcribe_audio(self, audio_file):
        """Transcribe audio file to text using Google Speech Recognition"""
        try:
            # Use asyncio.to_thread to make the synchronous speech recognition non-blocking
            return await asyncio.to_thread(self._perform_transcription, audio_file)
        except Exception as e:
            print(f"Error transcribing audio: {e}")
            return "I couldn't transcribe the audio. Please try again."
    
    def _perform_transcription(self, audio_file):
        """Performs the actual synchronous speech recognition"""
        with sr.AudioFile(audio_file) as source:
            audio_data = self.recognizer.record(source)
            try:
                # Use Google's speech recognition
                text = self.recognizer.recognize_google(audio_data)
                return text
            except sr.UnknownValueError:
                return "I couldn't understand what you said."
            except sr.RequestError as e:
                return f"Could not request results; {e}"

def list_audio_devices():
    """List available audio devices for debugging"""
    print("\n=== Available Audio Devices ===")
    for i in range(p.get_device_count()):
        dev_info = p.get_device_info_by_index(i)
        print(f"Device {i}: {dev_info['name']}")
        print(f"  Input channels: {dev_info['maxInputChannels']}")
        print(f"  Output channels: {dev_info['maxOutputChannels']}")
        print(f"  Default sample rate: {dev_info['defaultSampleRate']}")
    print("===============================\n")

def setup_wav2lip():
    """Setup Wav2Lip if not already installed"""
    if os.path.exists(WAV2LIP_DIR):
        print("Wav2Lip directory already exists.")
        return
    
    print("Setting up Wav2Lip for lip-syncing...")
    
    try:
        # Clone the Wav2Lip repository
        subprocess.run(["git", "clone", "https://github.com/Rudrabha/Wav2Lip.git", WAV2LIP_DIR], check=True)
        
        # Create checkpoints directory
        checkpoints_dir = os.path.join(WAV2LIP_DIR, "checkpoints")
        if not os.path.exists(checkpoints_dir):
            os.makedirs(checkpoints_dir)
        
        # Download the pre-trained model
        print("Downloading pre-trained model (this may take a while)...")
        model_url = "https://github.com/Rudrabha/Wav2Lip/blob/main/checkpoints/wav2lip_gan.pth?raw=true"
        model_path = os.path.join(checkpoints_dir, "wav2lip_gan.pth")
        
        try:
            subprocess.run(["curl", "-L", model_url, "-o", model_path], check=True)
            print("Pre-trained model downloaded successfully.")
        except Exception as e:
            print(f"Error downloading model: {e}")
            print("You'll need to manually download the pre-trained model.")
            print("Visit: https://github.com/Rudrabha/Wav2Lip")
        
        print("Wav2Lip setup complete!")
    except Exception as e:
        print(f"Error setting up Wav2Lip: {e}")
        print("You'll need to manually install Wav2Lip.")
        print("Visit: https://github.com/Rudrabha/Wav2Lip")

async def main():
    # List audio devices
    list_audio_devices()
    
    # Try to setup Wav2Lip
    setup_wav2lip()
    
    # Let the user choose the mode
    while True:
        print("\nChoose mode:")
        print("1. Text mode (text responses)")
        print("2. Audio mode (spoken responses)")
        choice = input("Enter 1 or 2: ")
        
        if choice == "1":
            mode = "text"
            break
        elif choice == "2":
            mode = "audio"
            break
        else:
            print("Invalid choice. Please enter 1 or 2.")
    
    # Create and start the therapist
    therapist = VirtualTherapist(mode=mode)
    await therapist.start_session()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        p.terminate()