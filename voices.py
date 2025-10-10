import os
import json
from gradio_client import Client, handle_file
import shutil
from dotenv import load_dotenv
from pathlib import Path
import time  # Added for retry delays



# Load environment variables
load_dotenv()



# TTS Engine Selection (set in .env file)
# Options: "kokoro" or "chatterbox"
TTS_ENGINE = os.getenv("TTS_ENGINE", "kokoro").lower()



print(f"🔊 TTS Engine: {TTS_ENGINE.upper()}")



# Initialize TTS clients based on selection
kokoro_client = None
unified_tts_client = None



if TTS_ENGINE == "kokoro":
    try:
        kokoro_client = Client("RobinsAIWorld/Kokoro-TTS-cpu")
        print("✓ Kokoro TTS initialized")
    except Exception as e:
        print(f"⚠️  Kokoro TTS failed to initialize: {e}")
        print("Falling back to Chatterbox TTS...")
        TTS_ENGINE = "chatterbox"



if TTS_ENGINE == "chatterbox":
    try:
        # Initialize unified client with fallback
        class UnifiedTTSClient:
            """Simplified TTS client with automatic fallback"""
            
            PRIMARY_SPACE = "obake2ai/CCBTSuperSoberShamanism_AudioSyncDemo_BU"
            PRIMARY_ENDPOINT = "/generate_tts_audio"
            BACKUP_SPACE = "Echo-AI-official/Chatterbox-TTS"
            BACKUP_ENDPOINT = "/tts_and_save"
            
            def __init__(self):
                self.current_api = None
                self.primary_client = None
                self.backup_client = None
                self._connect()
            
            def _connect(self):
                """Connect to available API"""
                # Try backup first (Chatterbox - more reliable)
                try:
                    self.backup_client = Client(self.BACKUP_SPACE)
                    self.current_api = "backup"
                    print("✓ Chatterbox TTS connected")
                    return
                except:
                    pass
                
                # Try primary
                try:
                    self.primary_client = Client(self.PRIMARY_SPACE)
                    self.current_api = "primary"
                    print("✓ Multilingual TTS connected")
                    return
                except:
                    pass
                
                raise ConnectionError("Failed to connect to any TTS API")
            
            def _retry_predict(self, client, predict_args, max_retries=3):
                """Helper for retrying predict calls with exponential backoff"""
                for attempt in range(max_retries):
                    try:
                        return client.predict(**predict_args)
                    except Exception as e:
                        if attempt == max_retries - 1:
                            raise e
                        wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                        print(f"    Retry {attempt + 1}/{max_retries} after {wait_time}s delay: {str(e)[:50]}...")
                        time.sleep(wait_time)
                
                raise RuntimeError("All retry attempts failed")
            
            def generate(self, text, reference_audio=None, language="en"):
                """Generate speech with automatic fallback"""
                audio_input = handle_file(reference_audio) if reference_audio else handle_file(
                    'https://github.com/gradio-app/gradio/raw/main/test/test_files/audio_sample.wav'
                )
                
                if self.current_api == "backup" and self.backup_client:
                    try:
                        predict_args = {
                            "text": text,
                            "ref_wav": audio_input,
                            "exaggeration": 0.5,
                            "temperature": 0.8,
                            "seed": 0,
                            "cfg_weight": 0.5,
                            "api_name": self.BACKUP_ENDPOINT
                        }
                        result = self._retry_predict(self.backup_client, predict_args)
                        return result[0]  # audio_path
                    except Exception as e:
                        # Try primary if backup fails
                        if self.primary_client:
                            predict_args = {
                                "text_input": text,
                                "language_id": language,
                                "audio_prompt_path_input": audio_input,
                                "exaggeration_input": 0.5,
                                "temperature_input": 0.8,
                                "seed_num_input": 0,
                                "cfgw_input": 0.5,
                                "api_name": self.PRIMARY_ENDPOINT
                            }
                            result = self._retry_predict(self.primary_client, predict_args)
                            return result
                        raise e
                
                elif self.current_api == "primary" and self.primary_client:
                    try:
                        predict_args = {
                            "text_input": text,
                            "language_id": language,
                            "audio_prompt_path_input": audio_input,
                            "exaggeration_input": 0.5,
                            "temperature_input": 0.8,
                            "seed_num_input": 0,
                            "cfgw_input": 0.5,
                            "api_name": self.PRIMARY_ENDPOINT
                        }
                        result = self._retry_predict(self.primary_client, predict_args)
                        return result
                    except Exception as e:
                        # Try backup if primary fails
                        if self.backup_client:
                            predict_args = {
                                "text": text,
                                "ref_wav": audio_input,
                                "exaggeration": 0.5,
                                "temperature": 0.8,
                                "seed": 0,
                                "cfg_weight": 0.5,
                                "api_name": self.BACKUP_ENDPOINT
                            }
                            result = self._retry_predict(self.backup_client, predict_args)
                            return result[0]
                        raise e
                
                raise RuntimeError("No TTS API available")
        
        unified_tts_client = UnifiedTTSClient()
        
    except Exception as e:
        print(f"⚠️  Chatterbox TTS failed to initialize: {e}")
        if not kokoro_client:
            raise Exception("No TTS engine available!")



# Voice mapping for Kokoro TTS
KOKORO_VOICE_MAP = {
    "Person 1": "bm_lewis",
    "Person 2": "bm_george"
}



# Voice cloning reference audio for Chatterbox TTS
CHATTERBOX_VOICE_MAP = {
    "Person 1": "assets/person_1.mp3",
    "Person 2": "assets/person_2.mp3"
}




def load_storyboard(file_path):
    """Load storyboard from JSON file"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)




def generate_audio_kokoro(text, voice, speed=1.0):
    """Generate audio using Kokoro TTS API"""
    if not kokoro_client:
        raise Exception("Kokoro TTS not initialized")
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            result = kokoro_client.predict(
                text=text,
                voice=voice,
                speed=speed,
                api_name="/generate_first"
            )
            
            # Result is a tuple: (audio_path, phonemes)
            audio_path = result[0]
            phonemes = result[1]
            
            return audio_path, phonemes
        
        except Exception as e:
            if attempt == max_retries - 1:
                raise Exception(f"Kokoro TTS generation failed after {max_retries} attempts: {str(e)}")
            wait_time = 2 ** attempt  # Exponential backoff
            print(f"    Kokoro retry {attempt + 1}/{max_retries} after {wait_time}s: {str(e)[:50]}...")
            time.sleep(wait_time)




def generate_audio_chatterbox(text, reference_audio):
    """Generate audio using Chatterbox TTS with voice cloning"""
    if not unified_tts_client:
        raise Exception("Chatterbox TTS not initialized")
    
    try:
        # Check if reference audio exists
        if not os.path.exists(reference_audio):
            print(f"⚠️  Reference audio not found: {reference_audio}")
            print(f"   Using default voice...")
            reference_audio = None
        
        # ========== FIXED: generate() returns a single value, not a tuple ==========
        audio_path = unified_tts_client.generate(
            text=text,
            reference_audio=reference_audio,
            language="en"
        )
        # ===========================================================================
        
        return audio_path, None  # No phonemes from Chatterbox
    
    except Exception as e:
        raise Exception(f"Chatterbox TTS generation failed: {str(e)}")




def generate_audio(text, speaker, speed=1.0):
    """
    Universal audio generation function that works with both TTS engines
    
    Args:
        text: Text to convert to speech
        speaker: Speaker name (e.g., "Person 1", "Person 2")
        speed: Speed multiplier (only for Kokoro)
    
    Returns:
        tuple: (audio_path, metadata)
    """
    if TTS_ENGINE == "kokoro":
        voice = KOKORO_VOICE_MAP.get(speaker, "bm_daniel")
        audio_path, phonemes = generate_audio_kokoro(text, voice, speed)
        metadata = {"phonemes": phonemes, "voice": voice, "engine": "kokoro"}
        return audio_path, metadata
    
    elif TTS_ENGINE == "chatterbox":
        reference_audio = CHATTERBOX_VOICE_MAP.get(speaker)
        audio_path, _ = generate_audio_chatterbox(text, reference_audio)
        metadata = {"reference_audio": reference_audio, "engine": "chatterbox"}
        return audio_path, metadata
    
    else:
        raise ValueError(f"Unknown TTS engine: {TTS_ENGINE}")




def process_storyboard_audio(storyboard_path, output_folder="audio_output"):
    """Process storyboard and generate audio for all dialogue lines"""
    
    # Load storyboard
    print(f"Loading storyboard: {storyboard_path}")
    storyboard = load_storyboard(storyboard_path)
    
    # Get base name for output folder
    storyboard_name = os.path.splitext(os.path.basename(storyboard_path))[0]
    specific_output_folder = os.path.join(output_folder, storyboard_name)
    
    # Create output folder
    os.makedirs(specific_output_folder, exist_ok=True)
    
    # Ensure assets folder exists if using Chatterbox
    if TTS_ENGINE == "chatterbox":
        os.makedirs("assets", exist_ok=True)
            
        # Check if reference audio files exist
        for speaker, ref_audio in CHATTERBOX_VOICE_MAP.items():
            if not os.path.exists(ref_audio):
                print(f"⚠️  Warning: Reference audio missing for {speaker}: {ref_audio}")
                print(f"   Place voice samples in the 'assets' folder:")
                print(f"   - assets/person_1.mp3")
                print(f"   - assets/person_2.mp3")
    
    audio_metadata = []
    total_lines = sum(len(scene.get('dialogue_lines', [])) for scene in storyboard)
    current_line = 0
    
    print(f"\n{'='*60}")
    print(f"Processing {len(storyboard)} scenes with {total_lines} dialogue lines")
    print(f"TTS Engine: {TTS_ENGINE.upper()}")
    print(f"{'='*60}\n")
    
    # Process each scene
    for scene in storyboard:
        scene_id = scene.get('scene_id')
        topic_focus = scene.get('topic_focus', 'unknown')
        audio_style = scene.get('audio_style', 'neutral')
        dialogue_lines = scene.get('dialogue_lines', [])
        
        print(f"Scene {scene_id}: {topic_focus} ({audio_style})")
        
        # Process each dialogue line
        for line_idx, dialogue in enumerate(dialogue_lines):
            current_line += 1
            speaker = dialogue.get('speaker')
            text = dialogue.get('line')
            
            print(f"  [{current_line}/{total_lines}] {speaker}: {text[:50]}{'...' if len(text) > 50 else ''}")
            
            try:
                # Generate audio using universal function
                audio_path, metadata = generate_audio(text, speaker, speed=1.0)
                
                # Create meaningful filename
                filename = f"scene_{scene_id:02d}_line_{line_idx + 1:02d}_{speaker.replace(' ', '_').lower()}.wav"
                destination = os.path.join(specific_output_folder, filename)
                
                # Copy audio file to output folder
                shutil.copy(audio_path, destination)
                
                # Store metadata
                audio_metadata.append({
                    "scene_id": scene_id,
                    "topic_focus": topic_focus,
                    "audio_style": audio_style,
                    "line_number": line_idx + 1,
                    "speaker": speaker,
                    "text": text,
                    "audio_file": filename,
                    "tts_engine": TTS_ENGINE,
                    **metadata  # Include engine-specific metadata
                })
                
                print(f"      ✓ Saved: {filename}")
                
            except Exception as e:
                print(f"      ✗ Error after retries: {str(e)}")
                continue
        
        print()  # Empty line between scenes
    
    # Save metadata
    metadata_path = os.path.join(specific_output_folder, "audio_metadata.json")
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(audio_metadata, f, indent=2, ensure_ascii=False)
    
    print(f"{'='*60}")
    print(f"Audio generation complete!")
    print(f"TTS Engine: {TTS_ENGINE.upper()}")
    print(f"Total files generated: {len(audio_metadata)}")
    print(f"Output folder: {specific_output_folder}")
    print(f"Metadata saved: {metadata_path}")
    print(f"{'='*60}")
    
    return specific_output_folder, audio_metadata




def find_latest_storyboard(storyboard_folder="story_board"):
    """Find the most recently modified storyboard file"""
    if not os.path.exists(storyboard_folder):
        return None
    
    json_files = [f for f in os.listdir(storyboard_folder) if f.endswith('.json')]
    
    if not json_files:
        return None
    
    # Get the most recent file
    latest_file = max(
        json_files,
        key=lambda f: os.path.getmtime(os.path.join(storyboard_folder, f))
    )
    
    return os.path.join(storyboard_folder, latest_file)




def process_specific_storyboard(storyboard_name):
    """Process a specific storyboard by name"""
    storyboard_path = os.path.join("story_board", f"{storyboard_name}.json")
    
    if not os.path.exists(storyboard_path):
        print(f"Error: Storyboard not found at {storyboard_path}")
        return False
    
    try:
        process_storyboard_audio(storyboard_path)
        return True
    except Exception as e:
        print(f"Error processing storyboard: {str(e)}")
        return False




def test_tts_engine():
    """Test the current TTS engine with sample text"""
    print(f"\n{'='*60}")
    print(f"Testing TTS Engine: {TTS_ENGINE.upper()}")
    print(f"{'='*60}\n")
    
    test_speakers = ["Person 1", "Person 2"]
    test_text = "Hello! This is a test of the text to speech system."
    
    os.makedirs("test_audio", exist_ok=True)
    
    for speaker in test_speakers:
        print(f"Testing {speaker}...")
        try:
            audio_path, metadata = generate_audio(test_text, speaker)
            
            # Save test audio
            destination = f"test_audio/{speaker.replace(' ', '_').lower()}_test.wav"
            shutil.copy(audio_path, destination)
            
            print(f"  ✓ Success: {destination}")
            print(f"  Metadata: {metadata}\n")
            
        except Exception as e:
            print(f"  ✗ Failed after retries: {e}\n")
    
    print(f"Test audio saved in 'test_audio' folder")
    print(f"{'='*60}\n")




if __name__ == "__main__":
    import sys
    
    # Check for test mode
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        test_tts_engine()
        sys.exit(0)
    
    # Option 1: Process the latest storyboard automatically
    print("Finding latest storyboard...")
    latest_storyboard = find_latest_storyboard()
    
    if latest_storyboard:
        print(f"Found: {latest_storyboard}\n")
        process_storyboard_audio(latest_storyboard)
    else:
        print("No storyboard files found in 'story_board' folder.")
        print("\nTo process a specific storyboard, use:")
        print("process_specific_storyboard('your_storyboard_name')")
        print("\nTo test TTS engine, run:")
        print("python voice.py --test")
    
    # Option 2: Uncomment to process a specific storyboard by name
    # process_specific_storyboard("Mystery_of_Dyatlov_Pass_Theory")
