from pydub import AudioSegment

def convert_m4a_to_mp3(input_file, output_file):
    try:
        # Load the M4A file
        audio = AudioSegment.from_file(input_file, format="m4a")
        # Export as MP3
        audio.export(output_file, format="mp3")
        print(f"Conversion successful! MP3 saved at: {output_file}")
    except Exception as e:
        print(f"An error occurred: {e}")

# Example usage
if __name__ == "__main__":
    input_file = "input.m4a"  # Replace with your M4A file path
    output_file = "input_audio.mp3"  # Replace with your desired MP3 file path
    convert_m4a_to_mp3(input_file, output_file)