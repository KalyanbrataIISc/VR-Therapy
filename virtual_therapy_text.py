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

# Important: Note the "models/" prefix in the model name
MODEL = "models/gemini-2.0-flash-exp"

async def main():
    # Configure system instructions for the therapist
    config = types.LiveConnectConfig(
        response_modalities=["text"],
        system_instruction=types.Content(
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
    )

    print("\n=== Virtual Therapist Session Starting ===")
    print("Type your thoughts and feelings naturally.")
    print("Type 'goodbye' or 'end session' to finish.\n")
    
    try:
        async with client.aio.live.connect(model=MODEL, config=config) as session:
            # Send an initial message to start the conversation
            await session.send(input="Hello, I'm here to talk whenever you're ready. How are you feeling today?", end_of_turn=True)
            
            # Get the initial response
            print("\nTherapist> ", end="")
            async for response in session.receive():
                if hasattr(response, 'text') and response.text is not None:
                    print(response.text, end="", flush=True)
            
            # Start the conversation loop
            while True:
                # Get user input
                user_input = input("\n\nYou> ")
                
                # Check for exit commands
                if user_input.lower() in ["goodbye", "end session", "exit", "quit"]:
                    await session.send(input="The user wants to end the session.", end_of_turn=True)
                    
                    print("\nTherapist> ", end="")
                    async for response in session.receive():
                        if hasattr(response, 'text') and response.text is not None:
                            print(response.text, end="", flush=True)
                    break
                    
                # Send user input to Gemini
                await session.send(input=user_input, end_of_turn=True)
                
                # Display the response
                print("\nTherapist> ", end="")
                async for response in session.receive():
                    if hasattr(response, 'text') and response.text is not None:
                        print(response.text, end="", flush=True)
                
    except Exception as e:
        print(f"\nError in session: {e}")
    finally:
        print("\n\n=== Session Ended ===")

if __name__ == "__main__":
    asyncio.run(main())