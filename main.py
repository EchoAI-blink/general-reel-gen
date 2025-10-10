import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv



# Load environment variables
load_dotenv()



# Import the main functions from each module
from story import process_first_pending_idea
from voices import process_storyboard_audio, find_latest_storyboard
from edit import create_video_with_audio, find_latest_audio_folder


# Import functions from ideas.py for generating new ideas
from ideas import (
    APIProviderManager, 
    load_existing_ideas, 
    generate_initial_ideas, 
    rank_and_filter_ideas, 
    renumber_and_append_ids, 
    save_ideas_to_file
)




def print_header(message):
    """Print a formatted header"""
    print(f"\n{'='*70}")
    print(f"  {message}")
    print(f"{'='*70}\n")




def print_step(step_num, total_steps, message):
    """Print a formatted step message"""
    print(f"\n[STEP {step_num}/{total_steps}] {message}")
    print(f"{'-'*70}")




def download_background_video():
    """Download background video from Google Drive if not present"""
    background_path = "assets/background.mp4"
    
    # Check if file already exists
    if os.path.exists(background_path):
        print(f"  ✓ {background_path} already exists")
        return True
    
    print(f"  ○ {background_path} not found. Downloading from Google Drive...")
    
    try:
        # Install gdown if not available
        try:
            import gdown
        except ImportError:
            print("    Installing gdown library...")
            import subprocess
            subprocess.check_call([sys.executable, "-m", "pip", "install", "gdown", "-q"])
            import gdown
        
        # Extract file ID from the Google Drive URL
        # URL format: https://drive.google.com/file/d/FILE_ID/view?usp=sharing
        drive_url = "https://drive.google.com/file/d/1zT99cDojL0r4FNylbZE06get46-njybj/view?usp=sharing"
        file_id = "1zT99cDojL0r4FNylbZE06get46-njybj"
        
        # Ensure assets folder exists
        os.makedirs("assets", exist_ok=True)
        
        # Download the file
        download_url = f"https://drive.google.com/uc?id={file_id}"
        gdown.download(download_url, background_path, quiet=False)
        
        if os.path.exists(background_path):
            print(f"  ✓ Successfully downloaded {background_path}")
            return True
        else:
            print(f"  ✗ Download failed: File not created")
            return False
            
    except Exception as e:
        print(f"  ✗ Error downloading background video: {str(e)}")
        print(f"    Please manually download from: {drive_url}")
        print(f"    And save it to: {background_path}")
        return False




def check_required_files():
    """Check if all required files and folders exist (excluding ideas.json)"""
    print_header("Checking Required Files and Folders")
    
    # ========== MODIFIED: Removed both ideas.json AND background.mp4 from required files ==========
    required_files = {
        ".env": "Environment configuration file",
        "assets/background.mp3": "Background music"
    }
    # ==============================================================================================
    
    optional_files = {
        "assets/person_1.png": "Person 1 character image",
        "assets/person_2.png": "Person 2 character image",
        "assets/person_1.mp3": "Person 1 voice reference (for Chatterbox TTS)",
        "assets/person_2.mp3": "Person 2 voice reference (for Chatterbox TTS)"
    }
    
    all_good = True
    
    # Check required files
    print("Required files:")
    for file_path, description in required_files.items():
        exists = os.path.exists(file_path)
        status = "✓" if exists else "✗"
        print(f"  {status} {file_path} - {description}")
        if not exists:
            all_good = False
    
    # Check optional files
    print("\nOptional files:")
    for file_path, description in optional_files.items():
        exists = os.path.exists(file_path)
        status = "✓" if exists else "○"
        print(f"  {status} {file_path} - {description}")
    
    # Create necessary folders
    print("\nCreating output folders...")
    folders = ["story_board", "audio_output", "final_videos", "assets"]
    for folder in folders:
        os.makedirs(folder, exist_ok=True)
        print(f"  ✓ {folder}/")
    
    # ========== NEW: Handle background video (download if needed) ==========
    print("\nChecking background video:")
    download_background_video()
    
    # Verify background video exists after download attempt
    if not os.path.exists("assets/background.mp4"):
        print("  ✗ Background video is missing and could not be downloaded")
        all_good = False
    # ========================================================================
    
    if not all_good:
        print("\n⚠️  Warning: Some required files are missing!")
        print("Please ensure all required files exist before running the pipeline.")
        return False
    
    print("\n✓ All required files found!")
    return True




def update_idea_status(idea_id, status, final_output=None, error_log=""):
    """Update the status of an idea in ideas.json"""
    try:
        with open("ideas.json", 'r', encoding='utf-8') as f:
            ideas = json.load(f)
        
        for idea in ideas:
            if idea['id'] == idea_id:
                idea['publishing_status'] = status
                if final_output:
                    idea['final_output'] = final_output
                if error_log:
                    idea['error_log'] = error_log
                break
        
        with open("ideas.json", 'w', encoding='utf-8') as f:
            json.dump(ideas, f, indent=2, ensure_ascii=False)
        
        return True
    except Exception as e:
        print(f"Error updating idea status: {e}")
        return False




def get_current_idea_id():
    """Get the ID of the current pending idea"""
    try:
        with open("ideas.json", 'r', encoding='utf-8') as f:
            ideas = json.load(f)
        
        ideas.sort(key=lambda x: x['id'])
        
        for idea in ideas:
            if idea.get('publishing_status') == 'pending':
                return idea['id']
        
        return None
    except Exception as e:
        print(f"Error reading ideas.json: {e}")
        return None




def generate_new_ideas():
    """Generate new ideas using the ideas.py module"""
    print_header("🎯 GENERATING NEW IDEAS 🎯")
    
    try:
        # Initialize the provider manager
        manager = APIProviderManager()
        
        # Setup client with fallback
        if not manager.setup_with_fallback():
            print("❌ Failed to initialize any API provider")
            return False
        
        # Load existing ideas and get max ID
        existing_ideas, max_existing_id = load_existing_ideas('ideas.json')
        
        # Step 1: Generate initial ideas
        print("\n📝 Generating initial ideas...")
        initial_ideas = generate_initial_ideas(manager)
        
        if not initial_ideas:
            print("✗ Failed to generate initial ideas.")
            return False
        
        # Step 2: Rank and filter ideas
        print("\n📊 Ranking and filtering ideas...")
        ranked_ideas = rank_and_filter_ideas(manager, initial_ideas)
        
        if not ranked_ideas:
            print("✗ Failed to rank ideas. Using initial ideas instead...")
            ranked_ideas = initial_ideas
        
        # Step 3: Renumber IDs starting from max_existing_id + 1
        print("\n🔢 Renumbering IDs...")
        new_ideas = renumber_and_append_ids(ranked_ideas, start_id=max_existing_id + 1)
        
        # Step 4: Append to existing ideas and save to file
        print("\n💾 Saving ideas to file...")
        if save_ideas_to_file(existing_ideas, new_ideas, output_file='ideas.json'):
            print(f"\n✓ Successfully generated and saved {len(new_ideas)} new ideas!")
            print(f"✓ New ideas have IDs from {max_existing_id + 1} to {max_existing_id + len(new_ideas)}")
            return True
        else:
            print("\n✗ Failed to save ideas to file")
            return False
            
    except Exception as e:
        print(f"\n✗ Error generating new ideas: {str(e)}")
        import traceback
        traceback.print_exc()
        return False




def run_pipeline():
    """Run the complete video generation pipeline"""
    
    print_header("🎬 AUTOMATED VIDEO GENERATION PIPELINE 🎬")
    
    # Step 0: Check required files (excluding ideas.json and background.mp4)
    if not check_required_files():
        print("\n❌ Pipeline aborted due to missing files.")
        return False
    
    # ========== Separate check for ideas.json ==========
    print_header("Checking Ideas File")
    
    # Check if ideas.json exists and has pending ideas
    if not os.path.exists('ideas.json'):
        print("⚠️  No 'ideas.json' file found!")
        print("🎯 Automatically generating new ideas...\n")
        
        if not generate_new_ideas():
            print("\n❌ Failed to generate new ideas. Pipeline aborted.")
            return False
        
        print("\n✓ New ideas generated successfully! Continuing with pipeline...\n")
    
    idea_id = get_current_idea_id()
    
    if idea_id is None:
        print("⚠️  No pending ideas found in ideas.json")
        print("🎯 All ideas are published or completed. Generating new ideas...\n")
        
        if not generate_new_ideas():
            print("\n❌ Failed to generate new ideas. Pipeline aborted.")
            return False
        
        print("\n✓ New ideas generated successfully! Continuing with pipeline...\n")
        
        # Get the first pending idea from newly generated ideas
        idea_id = get_current_idea_id()
        
        if idea_id is None:
            print("\n❌ No pending ideas found even after generation. Something went wrong.")
            return False
    
    print(f"✓ Found pending idea ID: {idea_id}")
    # ====================================================
    
    total_steps = 3
    print(f"\n📋 Processing Idea ID: {idea_id}")
    
    try:
        # ====================================================================
        # STEP 1: Generate Storyboard
        # ====================================================================
        print_step(1, total_steps, "Generating Storyboard")
        
        success = process_first_pending_idea()
        
        if not success:
            print("\n❌ Storyboard generation failed!")
            update_idea_status(idea_id, "error", error_log="Storyboard generation failed")
            return False
        
        print("\n✓ Storyboard generated successfully!")
        
        # Find the generated storyboard
        storyboard_path = find_latest_storyboard()
        
        if not storyboard_path:
            print("\n❌ Could not find generated storyboard!")
            update_idea_status(idea_id, "error", error_log="Storyboard file not found")
            return False
        
        print(f"✓ Storyboard location: {storyboard_path}")
        
        # ====================================================================
        # STEP 2: Generate Voice-Over
        # ====================================================================
        print_step(2, total_steps, "Generating Voice-Over")
        
        audio_folder, audio_metadata = process_storyboard_audio(storyboard_path)
        
        if not audio_folder or not audio_metadata:
            print("\n❌ Voice-over generation failed!")
            update_idea_status(idea_id, "error", error_log="Voice-over generation failed")
            return False
        
        print(f"\n✓ Voice-over generated successfully!")
        print(f"✓ Audio files location: {audio_folder}")
        print(f"✓ Total audio clips: {len(audio_metadata)}")
        
        # Update status
        update_idea_status(idea_id, "audio_generated")
        
        # ====================================================================
        # STEP 3: Create Final Video
        # ====================================================================
        print_step(3, total_steps, "Creating Final Video")
        
        video_path = create_video_with_audio(audio_folder)
        
        if not video_path or not os.path.exists(video_path):
            print("\n❌ Video creation failed!")
            update_idea_status(idea_id, "error", error_log="Video creation failed")
            return False
        
        print(f"\n✓ Video created successfully!")
        print(f"✓ Video location: {video_path}")
        
        # Update final status
        update_idea_status(idea_id, "completed", final_output=video_path)
        
        # ====================================================================
        # PIPELINE COMPLETE
        # ====================================================================
        print_header("✨ PIPELINE COMPLETED SUCCESSFULLY ✨")
        
        print("Summary:")
        print(f"  • Idea ID: {idea_id}")
        print(f"  • Storyboard: {storyboard_path}")
        print(f"  • Audio Folder: {audio_folder}")
        print(f"  • Final Video: {video_path}")
        print(f"\n🎉 Your video is ready!")
        
        return True
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Pipeline interrupted by user")
        update_idea_status(idea_id, "error", error_log="Pipeline interrupted by user")
        return False
        
    except Exception as e:
        print(f"\n\n❌ Pipeline failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        update_idea_status(idea_id, "error", error_log=f"Pipeline error: {str(e)}")
        return False




def show_menu():
    """Show interactive menu"""
    print_header("🎬 VIDEO GENERATION PIPELINE 🎬")
    
    print("Options:")
    print("  1. Run full pipeline (idea → storyboard → audio → video)")
    print("  2. Generate storyboard only")
    print("  3. Generate audio from latest storyboard")
    print("  4. Create video from latest audio")
    print("  5. Check system status")
    print("  6. Generate new ideas")
    print("  7. Exit")
    print()
    
    choice = input("Enter your choice (1-7): ").strip()
    return choice




def run_interactive():
    """Run in interactive mode"""
    while True:
        choice = show_menu()
        
        if choice == "1":
            run_pipeline()
            input("\nPress Enter to continue...")
            
        elif choice == "2":
            print_step(1, 1, "Generating Storyboard")
            success = process_first_pending_idea()
            if success:
                print("\n✓ Storyboard generated!")
            else:
                print("\n❌ Storyboard generation failed!")
            input("\nPress Enter to continue...")
            
        elif choice == "3":
            print_step(1, 1, "Generating Audio")
            storyboard_path = find_latest_storyboard()
            if storyboard_path:
                audio_folder, _ = process_storyboard_audio(storyboard_path)
                print(f"\n✓ Audio generated: {audio_folder}")
            else:
                print("\n❌ No storyboard found!")
            input("\nPress Enter to continue...")
            
        elif choice == "4":
            print_step(1, 1, "Creating Video")
            audio_folder = find_latest_audio_folder()
            if audio_folder:
                video_path = create_video_with_audio(audio_folder)
                print(f"\n✓ Video created: {video_path}")
            else:
                print("\n❌ No audio folder found!")
            input("\nPress Enter to continue...")
            
        elif choice == "5":
            check_required_files()
            input("\nPress Enter to continue...")
            
        elif choice == "6":
            if generate_new_ideas():
                print("\n✓ New ideas generated successfully!")
            else:
                print("\n❌ Failed to generate new ideas!")
            input("\nPress Enter to continue...")
            
        elif choice == "7":
            print("\nGoodbye! 👋")
            break
            
        else:
            print("\n⚠️  Invalid choice. Please try again.")
            input("\nPress Enter to continue...")




if __name__ == "__main__":
    # Check command line arguments
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        
        if arg == "--run" or arg == "-r":
            # Run full pipeline automatically
            success = run_pipeline()
            sys.exit(0 if success else 1)
            
        elif arg == "--check" or arg == "-c":
            # Check system status
            check_required_files()
            sys.exit(0)
            
        elif arg == "--generate-ideas" or arg == "-g":
            # Generate new ideas
            success = generate_new_ideas()
            sys.exit(0 if success else 1)
            
        elif arg == "--help" or arg == "-h":
            # Show help
            print("\nUsage:")
            print("  python main.py                   # Interactive mode")
            print("  python main.py --run             # Run full pipeline")
            print("  python main.py --check           # Check system status")
            print("  python main.py --generate-ideas  # Generate new ideas")
            print("  python main.py --help            # Show this help")
            print()
            sys.exit(0)
        else:
            print(f"Unknown argument: {arg}")
            print("Use --help to see available options")
            sys.exit(1)
    else:
        # Run in interactive mode
        try:
            run_interactive()
        except KeyboardInterrupt:
            print("\n\nGoodbye! 👋")
            sys.exit(0)
