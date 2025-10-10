import os
import json
import random
from dotenv import load_dotenv
from moviepy.editor import (
    VideoFileClip, AudioFileClip, ImageClip, CompositeVideoClip,
    CompositeAudioClip, concatenate_videoclips
)
from moviepy.video.fx.all import speedx
from PIL import Image, ImageDraw, ImageFont
import numpy as np


# Load environment variables
load_dotenv()


# Configuration
BACKGROUND_VIDEO_PATH = "assets/background.mp4"
BACKGROUND_MUSIC_PATH = "assets/background.mp3"
PERSON_1_IMAGE_PATH = "assets/person_1.png"
PERSON_2_IMAGE_PATH = "assets/person_2.png"


# From .env
USE_CHARACTER_IMAGES = os.getenv("USE_CHARACTER_IMAGES", "yes").lower() == "yes"
VIDEO_SPEED = 2.0
BACKGROUND_MUSIC_VOLUME = 0.5  # 50% volume for background music
WORDS_PER_LINE = 4  # Number of words to show at once


def load_audio_metadata(audio_folder):
    """Load audio metadata from the audio output folder"""
    metadata_path = os.path.join(audio_folder, "audio_metadata.json")
    
    if not os.path.exists(metadata_path):
        raise FileNotFoundError(f"Metadata not found: {metadata_path}")
    
    with open(metadata_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def resize_image_pil(image_path, target_height):
    """Resize image using PIL to avoid moviepy compatibility issues"""
    img = Image.open(image_path)
    
    # Convert to RGBA if not already
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    
    # Calculate new width maintaining aspect ratio
    aspect_ratio = img.width / img.height
    new_width = int(target_height * aspect_ratio)
    
    # Resize using PIL (LANCZOS is the new name for ANTIALIAS)
    img_resized = img.resize((new_width, target_height), Image.LANCZOS)
    
    return np.array(img_resized)


def create_line_image(text, video_size, font_size=20):
    """Create an image with one line of text"""
    # Try to use a nice font, fallback to default if not available
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
    except:
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", font_size)
        except:
            font = ImageFont.load_default()
    
    # Create temporary image for measuring
    temp_img = Image.new('RGBA', (1, 1), (0, 0, 0, 0))
    temp_draw = ImageDraw.Draw(temp_img)
    
    # Get text dimensions
    text_bbox = temp_draw.textbbox((0, 0), text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    
    # Make sure text doesn't exceed 80% of video width
    max_width = int(video_size[0] * 0.8)
    if text_width > max_width:
        # Reduce font size if text is too wide
        while text_width > max_width and font_size > 12:
            font_size -= 1
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
            except:
                try:
                    font = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", font_size)
                except:
                    font = ImageFont.load_default()
            text_bbox = temp_draw.textbbox((0, 0), text, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
    
    padding_horizontal = 15
    padding_vertical = 8
    stroke_width = 2
    
    # Create compact image
    img_width = text_width + (padding_horizontal * 2) + (stroke_width * 2)
    img_height = text_height + (padding_vertical * 2) + (stroke_width * 2)
    
    # Create image
    img = Image.new('RGBA', (img_width, img_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Center the text
    x = padding_horizontal + stroke_width
    y = padding_vertical + stroke_width
    
    # Draw stroke (black outline)
    for adj_x in range(-stroke_width, stroke_width + 1):
        for adj_y in range(-stroke_width, stroke_width + 1):
            draw.text((x + adj_x, y + adj_y), text, font=font, fill='black')
    
    # Draw main text in yellow
    draw.text((x, y), text, font=font, fill='yellow')
    
    return img


def create_animated_subtitle_clips(text, duration, video_size):
    """Create animated subtitle clips showing chunks of words that change"""
    words = text.split()
    num_words = len(words)
    
    if num_words == 0:
        return []
    
    # Create chunks of words
    chunks = []
    for i in range(0, num_words, WORDS_PER_LINE):
        chunk = " ".join(words[i:i + WORDS_PER_LINE])
        chunks.append(chunk)
    
    # Calculate time per chunk
    time_per_chunk = duration / len(chunks)
    
    clips = []
    
    for chunk in chunks:
        # Create image with this line of text
        pil_img = create_line_image(chunk, video_size, font_size=20)
        
        # Convert PIL image to numpy array
        img_array = np.array(pil_img)
        
        # Create ImageClip
        clip = ImageClip(img_array).set_duration(time_per_chunk)
        
        # Position in center of screen
        clip = clip.set_position('center')
        
        clips.append(clip)
    
    return clips


def create_video_with_audio(audio_folder, output_filename="final_video.mp4"):
    """Create the final video with all elements"""
    
    print(f"\n{'='*60}")
    print("Starting video creation...")
    print(f"{'='*60}\n")
    
    # Load metadata
    print("Loading audio metadata...")
    metadata = load_audio_metadata(audio_folder)
    
    # Load background video
    print("Loading background video...")
    background_video = VideoFileClip(BACKGROUND_VIDEO_PATH)
    
    # Get the total duration of the background video
    background_duration = background_video.duration
    print(f"Background video duration: {background_duration:.2f}s")
    
    # Calculate total audio duration
    total_audio_duration = 0
    audio_clips = []
    
    for item in metadata:
        audio_path = os.path.join(audio_folder, item['audio_file'])
        audio_clip = AudioFileClip(audio_path)
        audio_clips.append(audio_clip)
        total_audio_duration += audio_clip.duration
    
    print(f"Total audio duration: {total_audio_duration:.2f}s")
    
    # Calculate how much video we need
    video_needed_duration = total_audio_duration / VIDEO_SPEED
    
    # Calculate the maximum possible random start time
    max_start_time = background_duration - video_needed_duration
    
    # Generate a random start time (ensure it's not negative)
    if max_start_time > 0:
        random_start_time = random.randint(0, int(max_start_time))
    else:
        random_start_time = 0
        print("Warning: Audio duration exceeds available background video!")
    
    print(f"Randomly selected start time: {random_start_time}s at {VIDEO_SPEED}x speed")
    print(f"Using video segment from {random_start_time}s to {random_start_time + video_needed_duration:.2f}s")
    
    # Extract and speed up background video from random position
    background_video = background_video.subclip(random_start_time, random_start_time + video_needed_duration)
    background_video = speedx(background_video, VIDEO_SPEED)
    background_video = background_video.set_duration(total_audio_duration)
    
    video_size = background_video.size
    print(f"Video size: {video_size[0]}x{video_size[1]}")
    
    # Load and resize character images if enabled
    character_images = {}
    if USE_CHARACTER_IMAGES:
        print("\nLoading character images...")
        
        char_height = int(video_size[1] * 0.25)  # 25% of video height
        
        if os.path.exists(PERSON_1_IMAGE_PATH):
            # Resize with PIL
            resized_img = resize_image_pil(PERSON_1_IMAGE_PATH, char_height)
            character_images["Person 1"] = resized_img
            print(f"✓ Loaded Person 1: {PERSON_1_IMAGE_PATH}")
        else:
            print(f"✗ Person 1 image not found: {PERSON_1_IMAGE_PATH}")
        
        if os.path.exists(PERSON_2_IMAGE_PATH):
            # Resize with PIL
            resized_img = resize_image_pil(PERSON_2_IMAGE_PATH, char_height)
            character_images["Person 2"] = resized_img
            print(f"✓ Loaded Person 2: {PERSON_2_IMAGE_PATH}")
        else:
            print(f"✗ Person 2 image not found: {PERSON_2_IMAGE_PATH}")
    
    # Create video segments with subtitles and character images
    print("\nCreating video segments...")
    current_time = 0
    all_clips = [background_video]
    
    for idx, item in enumerate(metadata):
        audio_path = os.path.join(audio_folder, item['audio_file'])
        audio_clip = AudioFileClip(audio_path)
        duration = audio_clip.duration
        
        speaker = item['speaker']
        text = item['text']
        
        print(f"[{idx + 1}/{len(metadata)}] Scene {item['scene_id']}, {speaker}: {text[:50]}...")
        
        # Create animated subtitle clips (chunks of words)
        subtitle_clips = create_animated_subtitle_clips(text, duration, video_size)
        
        # Add each subtitle clip with proper timing
        subtitle_current_time = current_time
        for subtitle_clip in subtitle_clips:
            subtitle_clip = subtitle_clip.set_start(subtitle_current_time)
            all_clips.append(subtitle_clip)
            subtitle_current_time += subtitle_clip.duration
        
        # Add character image if enabled
        if USE_CHARACTER_IMAGES and speaker in character_images:
            char_img_array = character_images[speaker]
            
            # Create character image clip from numpy array
            char_clip = ImageClip(char_img_array).set_duration(duration)
            
            # Position based on speaker
            if speaker == "Person 1":
                # Lower-left corner
                x_pos = 50
                y_pos = video_size[1] - char_img_array.shape[0] - 50
            else:  # Person 2
                # Lower-right corner
                x_pos = video_size[0] - char_img_array.shape[1] - 50
                y_pos = video_size[1] - char_img_array.shape[0] - 50
            
            char_clip = char_clip.set_position((x_pos, y_pos))
            char_clip = char_clip.set_start(current_time)
            all_clips.append(char_clip)
        
        current_time += duration
    
    # Composite all video clips
    print("\nCompositing video clips...")
    final_video = CompositeVideoClip(all_clips, size=video_size)
    
    # Concatenate all audio clips
    print("Concatenating audio clips...")
    concatenated_audio = concatenate_audioclips(audio_clips)
    
    # Add background music
    print("Adding background music...")
    background_music = AudioFileClip(BACKGROUND_MUSIC_PATH)
    background_music = background_music.volumex(BACKGROUND_MUSIC_VOLUME)
    
    # Loop background music if needed
    if background_music.duration < total_audio_duration:
        loops_needed = int(total_audio_duration / background_music.duration) + 1
        background_music = concatenate_audioclips([background_music] * loops_needed)
    
    background_music = background_music.subclip(0, total_audio_duration)
    
    # Mix audio: dialogue + background music
    final_audio = CompositeAudioClip([concatenated_audio, background_music])
    final_video = final_video.set_audio(final_audio)
    
    # Set duration
    final_video = final_video.set_duration(total_audio_duration)
    
    # Create output folder
    output_folder = os.path.join("final_videos", os.path.basename(audio_folder))
    os.makedirs(output_folder, exist_ok=True)
    output_path = os.path.join(output_folder, output_filename)
    
    # Write video
    print(f"\nWriting final video to: {output_path}")
    print("This may take a few minutes...")
    
    final_video.write_videofile(
        output_path,
        fps=24,
        codec='libx264',
        audio_codec='aac',
        temp_audiofile='temp-audio.m4a',
        remove_temp=True,
        threads=4
    )
    
    # Cleanup
    print("\nCleaning up...")
    for clip in audio_clips:
        clip.close()
    background_video.close()
    final_video.close()
    
    print(f"\n{'='*60}")
    print(f"✓ Video creation complete!")
    print(f"✓ Output: {output_path}")
    print(f"✓ Duration: {total_audio_duration:.2f}s")
    print(f"{'='*60}\n")
    
    return output_path


def find_latest_audio_folder(base_folder="audio_output"):
    """Find the most recently created audio folder"""
    if not os.path.exists(base_folder):
        return None
    
    folders = [f for f in os.listdir(base_folder) if os.path.isdir(os.path.join(base_folder, f))]
    
    if not folders:
        return None
    
    latest_folder = max(
        folders,
        key=lambda f: os.path.getmtime(os.path.join(base_folder, f))
    )
    
    return os.path.join(base_folder, latest_folder)


def concatenate_audioclips(clips):
    """Concatenate audio clips sequentially"""
    if not clips:
        return None
    
    current_time = 0
    audio_clips_with_timing = []
    
    for clip in clips:
        clip_with_start = clip.set_start(current_time)
        audio_clips_with_timing.append(clip_with_start)
        current_time += clip.duration
    
    return CompositeAudioClip(audio_clips_with_timing)


if __name__ == "__main__":
    # Find latest audio folder
    print("Finding latest audio folder...")
    latest_audio = find_latest_audio_folder()
    
    if latest_audio:
        print(f"Found: {latest_audio}\n")
        create_video_with_audio(latest_audio)
    else:
        print("No audio folders found in 'audio_output' folder.")
        print("\nTo process a specific folder, use:")
        print("create_video_with_audio('audio_output/your_folder_name')")
