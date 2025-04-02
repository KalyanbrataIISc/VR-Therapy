import asyncio
import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load API key from .env file
load_dotenv()
API_KEY = os.getenv("API_KEY")

# Configure client with API key
client = genai.Client(api_key=API_KEY, http_options={'api_version': 'v1alpha'})

# Models to test
MODELS_TO_TEST = [
    "models/gemini-1.5-pro",
    "models/gemini-1.5-flash", 
    "models/gemini-pro"
    "models/gemini-flash",
    "models/gemini-2.0-pro",
    "models/gemini-2.0-flash",
    "models/gemini-2.0-flash-exp",
]

# Configuration combinations to test
CONFIGS_TO_TEST = [
    {
        "name": "Text-only",
        "config": lambda: types.LiveConnectConfig(
            response_modalities=["text"]
        )
    },
    {
        "name": "Text with voice config but text output",
        "config": lambda: types.LiveConnectConfig(
            response_modalities=["text"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Kore")
                )
            )
        )
    },
    {
        "name": "Audio output only",
        "config": lambda: types.LiveConnectConfig(
            response_modalities=["audio"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Kore")
                )
            )
        )
    },
    {
        "name": "Audio+Text output",
        "config": lambda: types.LiveConnectConfig(
            response_modalities=["audio", "text"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Kore")
                )
            )
        )
    }
]

async def test_configuration(model, config_name, config_fn):
    """Test a specific model and configuration combination"""
    print(f"\n--- Testing {model} with {config_name} ---")
    
    try:
        config = config_fn()
        async with client.aio.live.connect(model=model, config=config) as session:
            print(f"✅ Connection successful!")
            
            # Try sending a simple message
            await session.send(input="Hello, can you hear me?", end_of_turn=True)
            print("   Message sent successfully")
            
            # Try receiving a response
            print("   Response:")
            try:
                async for response in session.receive():
                    if hasattr(response, 'text') and response.text is not None:
                        print(f"     Text: {response.text}")
                    
                    if hasattr(response, 'data') and response.data is not None:
                        data_len = len(response.data) if response.data else 0
                        print(f"     Audio data received: {data_len} bytes")
                    
                    # Check for turn completion
                    if hasattr(response, 'server_content') and response.server_content:
                        if hasattr(response.server_content, 'turn_complete') and response.server_content.turn_complete:
                            print("     Turn complete")
                            break
            except Exception as e:
                print(f"   ❌ Error receiving response: {e}")
                
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        
    print(f"--- Test for {model} with {config_name} completed ---")

async def main():
    print("\n=== Gemini Live API Compatibility Test ===")
    print(f"Testing {len(MODELS_TO_TEST)} models with {len(CONFIGS_TO_TEST)} configurations")
    
    # Verify the library version
    print(f"Google Generative AI version: {genai.__version__}")
    
    # Test each model and configuration
    for model in MODELS_TO_TEST:
        for config_info in CONFIGS_TO_TEST:
            try:
                await test_configuration(model, config_info["name"], config_info["config"])
            except Exception as e:
                print(f"Test failed with unexpected error: {e}")
    
    print("\n=== Test Complete ===")
    print("Any configurations that show '✅ Connection successful!' should work for your application.")

if __name__ == "__main__":
    asyncio.run(main())