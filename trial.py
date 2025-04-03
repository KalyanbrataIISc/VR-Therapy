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
from dotenv import load_dotenv
from google import genai
from google.genai import types
import pygame
import pygame.freetype
from PIL import Image, ImageDraw
import queue

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
AVATAR_WIDTH = 400
AVATAR_HEIGHT = 400
FPS = 30

# Audio directory
AUDIO_DIR = "user_audio"
AVATAR_DIR = "avatar_images"

# Create directories if they don't exist
for directory in [AUDIO_DIR, AVATAR_DIR]:
    if not os.path.exists(directory):
        os.makedirs(directory)

# Initialize PyAudio
p = pyaudio.PyAudio()

# Event for communication between threads
pygame_initialized = threading.Event()
animation_event_queue = queue.Queue()

# Avatar class to handle the face rendering and lip sync
class TherapistAvatar:
    def __init__(self):
        # Initialize mouth state
        self.current_mouth = 0
        self.mouth_positions = 5  # Number of different mouth positions
        self.is_speaking = False
        self.volume_threshold = 500  # Adjust based on your audio volume
        
        # Animation variables
        self.blink_timer = 0
        self.blink_interval = 4000  # 4 seconds between blinks
        self.is_blinking = False
        self.blink_duration = 200  # Blink duration in milliseconds
        
        # Prepare the avatar assets
        self.create_avatar_images()
    
    def create_avatar_images(self):
        """Create or load the avatar face images with different mouth positions"""
        self.mouth_images = []
        self.eye_open = None
        self.eye_closed = None
        
        # Check if images already exist
        if (os.path.exists(os.path.join(AVATAR_DIR, "mouth_0.png")) and 
            os.path.exists(os.path.join(AVATAR_DIR, "eyes_open.png"))):
            # Load existing images
            self.eye_open = pygame.image.load(os.path.join(AVATAR_DIR, "eyes_open.png"))
            self.eye_closed = pygame.image.load(os.path.join(AVATAR_DIR, "eyes_closed.png"))
            self.base_face = pygame.image.load(os.path.join(AVATAR_DIR, "base_face.png"))
            
            for i in range(5):  # Load 5 mouth positions
                mouth_img = pygame.image.load(os.path.join(AVATAR_DIR, f"mouth_{i}.png"))
                self.mouth_images.append(mouth_img)
        else:
            # Create new avatar images
            
            # Base face color (light beige)
            face_color = (255, 223, 196)
            
            # Create base face
            base_face = Image.new("RGBA", (AVATAR_WIDTH, AVATAR_HEIGHT), (255, 255, 255, 0))
            draw = ImageDraw.Draw(base_face)
            
            # Draw face circle
            face_radius = AVATAR_HEIGHT // 2 - 20
            face_center = (AVATAR_WIDTH // 2, AVATAR_HEIGHT // 2)
            draw.ellipse(
                (face_center[0] - face_radius, face_center[1] - face_radius,
                 face_center[0] + face_radius, face_center[1] + face_radius),
                fill=face_color
            )
            
            # Save base face
            base_face_path = os.path.join(AVATAR_DIR, "base_face.png")
            base_face.save(base_face_path)
            
            # Create eyes (open)
            eyes_image = Image.new("RGBA", (AVATAR_WIDTH, AVATAR_HEIGHT), (255, 255, 255, 0))
            draw = ImageDraw.Draw(eyes_image)
            
            # Eye parameters
            eye_y = face_center[1] - face_radius // 3
            eye_width = face_radius // 3
            eye_height = face_radius // 6
            left_eye_x = face_center[0] - face_radius // 2
            right_eye_x = face_center[0] + face_radius // 2
            
            # Draw eyes (open)
            draw.ellipse(
                (left_eye_x - eye_width//2, eye_y - eye_height//2,
                 left_eye_x + eye_width//2, eye_y + eye_height//2),
                fill=(255, 255, 255), outline=(0, 0, 0)
            )
            draw.ellipse(
                (right_eye_x - eye_width//2, eye_y - eye_height//2,
                 right_eye_x + eye_width//2, eye_y + eye_height//2),
                fill=(255, 255, 255), outline=(0, 0, 0)
            )
            
            # Draw pupils
            pupil_size = eye_height // 2
            draw.ellipse(
                (left_eye_x - pupil_size//2, eye_y - pupil_size//2,
                 left_eye_x + pupil_size//2, eye_y + pupil_size//2),
                fill=(0, 0, 0)
            )
            draw.ellipse(
                (right_eye_x - pupil_size//2, eye_y - pupil_size//2,
                 right_eye_x + pupil_size//2, eye_y + pupil_size//2),
                fill=(0, 0, 0)
            )
            
            # Save open eyes
            eyes_open_path = os.path.join(AVATAR_DIR, "eyes_open.png")
            eyes_image.save(eyes_open_path)
            
            # Create eyes (closed)
            eyes_closed = Image.new("RGBA", (AVATAR_WIDTH, AVATAR_HEIGHT), (255, 255, 255, 0))
            draw = ImageDraw.Draw(eyes_closed)
            
            # Draw closed eyes (just lines)
            draw.line(
                (left_eye_x - eye_width//2, eye_y, left_eye_x + eye_width//2, eye_y),
                fill=(0, 0, 0), width=2
            )
            draw.line(
                (right_eye_x - eye_width//2, eye_y, right_eye_x + eye_width//2, eye_y),
                fill=(0, 0, 0), width=2
            )
            
            # Save closed eyes
            eyes_closed_path = os.path.join(AVATAR_DIR, "eyes_closed.png")
            eyes_closed.save(eyes_closed_path)
            
            # Create different mouth positions
            mouth_y = face_center[1] + face_radius // 3
            mouth_width = face_radius // 2
            mouth_height = face_radius // 8
            
            for i in range(5):
                mouth_img = Image.new("RGBA", (AVATAR_WIDTH, AVATAR_HEIGHT), (255, 255, 255, 0))
                draw = ImageDraw.Draw(mouth_img)
                
                # Adjust mouth opening based on position
                opening_factor = i / 4  # 0 to 1
                mouth_open_height = int(mouth_height * opening_factor * 2)
                
                # Draw mouth
                if i == 0:  # Closed mouth (smile)
                    draw.arc(
                        (face_center[0] - mouth_width//2, mouth_y - mouth_height//2,
                         face_center[0] + mouth_width//2, mouth_y + mouth_height//2),
                        start=0, end=180, fill=(0, 0, 0), width=2
                    )
                else:  # Open mouth with varying degrees
                    draw.ellipse(
                        (face_center[0] - mouth_width//2, mouth_y - mouth_open_height//2,
                         face_center[0] + mouth_width//2, mouth_y + mouth_open_height//2),
                        fill=(10, 10, 10), outline=(0, 0, 0)
                    )
                
                # Save mouth image
                mouth_path = os.path.join(AVATAR_DIR, f"mouth_{i}.png")
                mouth_img.save(mouth_path)
    
    def update_mouth_from_audio(self, audio_data):
        """Update mouth position based on audio amplitude"""
        if audio_data:
            # Convert bytes to numpy array
            data = np.frombuffer(audio_data, dtype=np.int16)
            # Calculate volume (amplitude)
            volume = np.abs(data).mean()
            
            # Map volume to mouth position
            if volume < self.volume_threshold * 0.3:
                self.current_mouth = 1
            elif volume < self.volume_threshold * 0.6:
                self.current_mouth = 2
            elif volume < self.volume_threshold * 0.9:
                self.current_mouth = 3
            else:
                self.current_mouth = 4
            
            # Send event to main thread
            animation_event_queue.put({"type": "mouth_update", "position": self.current_mouth})
        else:
            animation_event_queue.put({"type": "mouth_update", "position": 0})
    
    def set_speaking(self, is_speaking):
        """Set the speaking state"""
        self.is_speaking = is_speaking
        animation_event_queue.put({"type": "speaking_state", "state": is_speaking})
        if not is_speaking:
            animation_event_queue.put({"type": "mouth_update", "position": 0})


# Pygame initialization function to run in main thread
def initialize_pygame():
    """Initialize pygame in the main thread"""
    pygame.init()
    screen = pygame.display.set_mode((AVATAR_WIDTH, AVATAR_HEIGHT))
    pygame.display.set_caption("Virtual Therapist")
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
            if event["type"] == "mouth_update":
                avatar.current_mouth = event["position"]
            elif event["type"] == "speaking_state":
                avatar.is_speaking = event["state"]
            elif event["type"] == "exit":
                return False
        except queue.Empty:
            break
    
    # Clear screen
    screen.fill((240, 240, 255))
    
    # Draw base face
    screen.blit(avatar.base_face, (0, 0))
    
    # Handle blinking
    avatar.blink_timer += clock.get_time()
    if not avatar.is_blinking and avatar.blink_timer >= avatar.blink_interval:
        avatar.is_blinking = True
        avatar.blink_timer = 0
    elif avatar.is_blinking and avatar.blink_timer >= avatar.blink_duration:
        avatar.is_blinking = False
        avatar.blink_timer = 0
    
    # Draw eyes based on blink state
    if avatar.is_blinking:
        screen.blit(avatar.eye_closed, (0, 0))
    else:
        screen.blit(avatar.eye_open, (0, 0))
    
    # Draw mouth based on current state
    if avatar.is_speaking:
        mouth_index = min(avatar.current_mouth, len(avatar.mouth_images) - 1)
        screen.blit(avatar.mouth_images[mouth_index], (0, 0))
    else:
        screen.blit(avatar.mouth_images[0], (0, 0))  # Closed mouth
    
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
        self.avatar = TherapistAvatar()
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
            print(f"All audio files removed from {AUDIO_DIR} directory.")
        except Exception as e:
            print(f"Error cleaning up audio directory: {e}")
    
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
                    
                    # Simulate lip movement based on text
                    # For text mode, we'll just alternate mouth positions to simulate talking
                    self.avatar.current_mouth = (self.avatar.current_mouth + 1) % self.avatar.mouth_positions
                    animation_event_queue.put({"type": "mouth_update", "position": self.avatar.current_mouth})
                    await asyncio.sleep(0.1)  # Small delay to make the animation look natural
                
                # Check for turn completion
                if hasattr(response, 'server_content') and response.server_content:
                    if hasattr(response.server_content, 'turn_complete') and response.server_content.turn_complete:
                        break
        except Exception as e:
            print(f"\nError processing response: {e}")
        
        return full_response
            
    async def play_audio_response(self, session, screen, font, clock):
        """Play audio response"""
        print("\nTherapist> [Speaking...]")
        
        # Set up audio output stream
        output_stream = p.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RECEIVE_SAMPLE_RATE,
            output=True
        )
        
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
                        
                        # Add to buffer for analysis
                        audio_buffer.append(response.data)
                        
                        # Update mouth position based on audio
                        if len(audio_buffer) >= buffer_size:
                            # Combine buffer chunks
                            combined_data = b''.join(audio_buffer[-buffer_size:])
                            self.avatar.update_mouth_from_audio(combined_data)
                            
                    except Exception as e:
                        print(f"Error playing audio: {e}")
                
                # Check for turn completion
                if hasattr(response, 'server_content') and response.server_content:
                    if hasattr(response.server_content, 'turn_complete') and response.server_content.turn_complete:
                        break
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

async def main():
    # List audio devices
    list_audio_devices()
    
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