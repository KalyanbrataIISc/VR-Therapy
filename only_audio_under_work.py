import asyncio
import os
import sys
import pyaudio
import wave
import time
import numpy as np
from dotenv import load_dotenv
from google import genai
from google.genai import types

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
THRESHOLD = 1500  # Adjust based on your microphone sensitivity
TIMEOUT = 2.0  # Seconds of silence to detect end of input

# Initialize PyAudio
p = pyaudio.PyAudio()

class VirtualTherapist:
    def __init__(self, mode="text"):
        """Initialize the virtual therapist.
        
        Args:
            mode: Either "text" or "audio" (can't be both due to API limitations)
        """
        self.mode = mode
        
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
    
    async def start_session(self):
        """Start a therapy session"""
        print(f"\n=== Virtual Therapist Session ({self.mode.upper()} MODE) ===")
        print("Share your thoughts and feelings, and I'll respond as a virtual therapist.")
        print("Type 'goodbye' or 'end session' to finish.\n")
        
        try:
            async with client.aio.live.connect(model=MODEL, config=self.config) as session:
                # Send an initial greeting
                initial_greeting = "Hello, I'm here as your virtual therapist today. How are you feeling?"
                await session.send(input=initial_greeting, end_of_turn=True)
                
                # Process the initial response
                await self.handle_response(session)
                
                # Main conversation loop
                while True:
                    # Get user input (text input for both modes for now)
                    if self.mode == "text":
                        user_input = input("\nYou> ")
                    else:  # audio mode
                        print("\nYou> ", end="")
                        user_input = await self.get_audio_input()
                        print(f"{user_input}")
                    
                    # Check for exit commands
                    if user_input.lower() in ["goodbye", "end session", "exit", "quit"]:
                        await session.send(input="The client wants to end our session now.", end_of_turn=True)
                        await self.handle_response(session)
                        break
                    
                    # Send user input to the model
                    await session.send(input=user_input, end_of_turn=True)
                    
                    # Handle the response
                    await self.handle_response(session)
                    
        except Exception as e:
            print(f"\nError in session: {e}")
            import traceback
            traceback.print_exc()
        finally:
            print("\n=== Session Ended ===")
    
    async def handle_response(self, session):
        """Handle the response from the model based on mode"""
        if self.mode == "text":
            await self.display_text_response(session)
        else:  # audio mode
            await self.play_audio_response(session)
            
    async def display_text_response(self, session):
        """Display text response"""
        print("\nTherapist> ", end="")
        full_response = ""
        
        try:
            async for response in session.receive():
                # Process text responses
                if hasattr(response, 'text') and response.text is not None:
                    print(response.text, end="", flush=True)
                    full_response += response.text
                
                # Check for turn completion
                if hasattr(response, 'server_content') and response.server_content:
                    if hasattr(response.server_content, 'turn_complete') and response.server_content.turn_complete:
                        break
        except Exception as e:
            print(f"\nError processing response: {e}")
        
        return full_response
            
    async def play_audio_response(self, session):
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
            async for response in session.receive():
                # Process audio data
                if hasattr(response, 'data') and response.data is not None:
                    try:
                        output_stream.write(response.data)
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
    
    async def get_audio_input(self):
        """Record audio input from the user"""
        # For simplicity in this initial version, we'll use text input
        # This can be replaced with real audio recording later
        # user_input = input("(Text input for now) ")
        # return user_input
        
        # Uncomment this code to implement actual audio recording:
        
        print("Listening... (speak now)")
        
        # Open input stream
        stream = p.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=SEND_SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK_SIZE
        )
        
        frames = []
        silent_chunks = 0
        is_speaking = False
        
        try:
            while True:
                data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
                frames.append(data)
                
                # Convert audio chunk to numpy array and calculate volume
                audio_data = np.frombuffer(data, dtype=np.int16)
                volume_norm = np.abs(audio_data).mean()
                
                # Detect if user is speaking
                if volume_norm > THRESHOLD:
                    is_speaking = True
                    silent_chunks = 0
                elif is_speaking:
                    silent_chunks += 1
                    
                # If silence for TIMEOUT seconds after speaking, stop recording
                if is_speaking and silent_chunks > int(SEND_SAMPLE_RATE / CHUNK_SIZE * TIMEOUT):
                    break
                    
        finally:
            stream.stop_stream()
            stream.close()
        
        if not is_speaking:
            return ""
            
        # Create temporary WAV file for the audio
        temp_filename = "temp_user_input.wav"
        with wave.open(temp_filename, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(p.get_sample_size(FORMAT))
            wf.setframerate(SEND_SAMPLE_RATE)
            wf.writeframes(b''.join(frames))
            
        # Here you would add code to send the audio to a speech-to-text service
        # For now, let's use text input as a placeholder
        user_input = input("For development: Please type what you said: ")
        
        # Clean up temp file
        try:
            os.remove(temp_filename)
        except:
            pass
            
        return user_input
        

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