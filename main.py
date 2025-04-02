import os
from dotenv import load_dotenv
import speech_recognition as sr
from pydub import AudioSegment
from google import genai
from gtts import gTTS

def main():
    # Load your API key from the .env file
    load_dotenv()
    API_KEY = os.getenv('API_KEY')
    if not API_KEY:
        print("Please set your API_KEY in the .env file.")
        return

    # Specify your input audio file (can be mp3 or wav)
    input_file = "input_audio.mp3"  # change this to your file path

    # If the file isn't a WAV, convert it using pydub
    file_ext = os.path.splitext(input_file)[1].lower()
    temp_wav = "temp.wav"
    if file_ext != ".wav":
        audio = AudioSegment.from_file(input_file)
        audio.export(temp_wav, format="wav")
        wav_file = temp_wav
    else:
        wav_file = input_file

    # Speech-to-text using SpeechRecognition with Google's API
    recognizer = sr.Recognizer()
    with sr.AudioFile(wav_file) as source:
        audio_data = recognizer.record(source)
    try:
        recognized_text = recognizer.recognize_google(audio_data)
    except Exception as e:
        print("Error during speech recognition:", e)
        return

    print("Recognized text:", recognized_text)

    # Create a Gemini prompt that instructs it to act as a therapist
    prompt = f"""As a caring therapist, please respond helpfully to the following message: {recognized_text}.
    Please provide a thoughtful and empathetic response. And also to remind you, the text you generate will
    be used to create an audio file, so please keep it short and concise, and real speechlike."""

    # Call Gemini (assuming you have access and the package installed)
    client = genai.Client(api_key=API_KEY)
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
    )
    output_text = response.text
    print("Therapist response:", output_text)

    # Convert Gemini's text response to speech using gTTS
    tts = gTTS(output_text)
    output_audio_file = "output_audio.mp3"
    tts.save(output_audio_file)
    print("Output audio saved as:", output_audio_file)

    # Clean up the temporary wav file if it was created
    if file_ext != ".wav" and os.path.exists(temp_wav):
        os.remove(temp_wav)

if __name__ == "__main__":
    main()