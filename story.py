import os
import json
import re
from dotenv import load_dotenv


# Load environment variables
load_dotenv()


def initialize_client():
    """Initializes the appropriate client based on the .env configuration."""
    api_provider = os.getenv("API_PROVIDER", "OPENAI").upper()


    if api_provider == "NVIDIA":
        from openai import OpenAI
        print("Using NVIDIA NIM API")
        return OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=os.getenv("NVIDIA_API_KEY")
        )
    elif api_provider == "G4F":
        import g4f
        print("Using G4F API")
        return g4f.client.Client()
    else: # Default to OpenAI
        from openai import OpenAI
        print("Using OpenAI API")
        return OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL")
        )


client = initialize_client()


def load_ideas(file_path="ideas.json"):
    """Load ideas from JSON file"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_ideas(ideas, file_path="ideas.json"):
    """Save updated ideas back to JSON file"""
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(ideas, f, indent=2, ensure_ascii=False)


def extract_json_from_response(response_text):
    """Extract JSON from response that might be wrapped in markdown or have extra text"""
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        pass
    
    json_match = re.search(r'``````', response_text)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass
            
    array_match = re.search(r'(\[[\s\S]*?\])', response_text)
    if array_match:
        try:
            return json.loads(array_match.group(1))
        except json.JSONDecodeError:
            pass
            
    raise ValueError(f"Could not extract valid JSON from response. Response content:\n{response_text[:500]}")


def generate_storyboard(idea_title, idea_description, caption):
    """Generate storyboard using the configured API"""
    api_provider = os.getenv("API_PROVIDER", "OPENAI").upper()
    
    system_prompt = """You are a dialogue-first content generator for short-form videos on any topic.


The user will provide:
- video_title (string)
- video_description (string)
- Optional: genre_tone (string), target_audience (string), language (string), pacing (string)


Your task:
Create a structured, dialogue-only storyboard in JSON array format for 5-8 sequential scenes that tell a single, coherent story. Lines must alternate strictly between "Person 1" and "Person 2".


**CRITICAL: Your primary goal is to create a logical NARRATIVE FLOW. Each scene must directly and logically follow from the one before it. Do not jump between unrelated examples. Build a single, focused story from start to finish.**


Narration style:
- Spoken dialogue only—no stage directions, camera notes, or other text.
- Use a dynamic storytelling rhythm. Person 1 is the storyteller, revealing facts. Person 2 is the audience proxy, asking logical follow-up questions ("But how does that work?", "So what happened next?", "Why does that matter?") that guide the story forward.
- **Focus on a single narrative thread.** For example, if the topic is quantum tunneling, don't just list where it's used. Instead, explain the concept, then how it solves a specific problem (like fusion in the sun), and then how that same solution is used elsewhere (like in computer chips).
- Keep each line concise and punchy (5–12 words).
- Use only simple, common words. Explain any complex term immediately.


New Narrative Structure (5-8 Scenes):
1.  Scene 1 = **The Hook.** Introduce the core, mind-bending concept or event.
2.  Scenes 2-3 = **The Unfolding.** Explain the "how" or "why" of the hook. Reveal the immediate consequence or problem this creates.
3.  Scenes 4-6 = **The Escalation.** Introduce a surprising twist or a powerful application that builds on the previous scenes. Show the incredible scale or impact.
4.  Scene 7-8 = **The Final Reveal.** A final, powerful connection that brings the story to a satisfying close, often linking back to the viewer's everyday life.


Continuity and Flow Rules:
-   **Chain of Logic:** The end of one scene must be the natural starting point for the next. The dialogue must explicitly bridge the two scenes.
-   **One Story:** Do not treat this as a list of facts. Treat it as a short story with a beginning, middle, and end.
-   **Logical Questions:** Person 2's lines are crucial for flow. They should ask the question the audience is thinking, leading Person 1 to the next part of the story.


Each scene must include:
-   scene_id: integer (1 to 8 maximum)
-   topic_focus: A short phrase describing this specific step in the story.
-   audio_style: A mood for the delivery (e.g., suspenseful, shocking, intense, dramatic, epic). Must vary between scenes.
-   dialogue_lines: An array of 2 exchanges that strictly alternate, starting with Person 1.
    -   Each exchange has:
        -   speaker: "Person 1" or "Person 2"
        -   line: The spoken line (simple, punchy, and contributes to the narrative).


Content Quality Checklist:
-   Does the script tell one single, focused story?
-   Does each scene logically connect to the previous one?
-   Is there a clear beginning (hook), middle (escalation), and end (reveal)?
-   Are Person 2's questions guiding the narrative logically?
-   Are all generic "lesson" or "moral" dialogues removed?


Language:
-   Mirror the user's input language. Prioritize simple vocabulary.


Output format:
-   Return ONLY a JSON array of 5-8 scene objects. No explanations or headers.
"""


    user_prompt = f"""video_title: {idea_title}
video_description: {idea_description}
caption: {caption}
genre_tone: educational, fast-paced
target_audience: general audience
language: English
pacing: fast"""


    try:
        if api_provider == "NVIDIA":
            model = os.getenv("NVIDIA_MODEL", "meta/llama3-70b-instruct")
        elif api_provider == "G4F":
            model = os.getenv("G4F_MODEL", "gpt-4")
        else: # OpenAI
            model = os.getenv("OPENAI_MODEL", "gpt-4")


        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7
        )
        
        storyboard_text = response.choices[0].message.content
        
        # For NVIDIA provider, parse JSON directly without extraction logic
        if api_provider == "NVIDIA":
            try:
                storyboard = json.loads(storyboard_text)
                print("✓ NVIDIA: Using raw JSON output directly")
            except json.JSONDecodeError as e:
                raise Exception(f"NVIDIA API returned invalid JSON: {str(e)}\nResponse: {storyboard_text[:500]}")
        else:
            # For other providers, use the extraction logic
            storyboard = extract_json_from_response(storyboard_text)
        
        return storyboard
    
    except Exception as e:
        raise Exception(f"Error generating storyboard: {str(e)}")


def save_storyboard(storyboard, filename):
    """Save storyboard to a JSON file"""
    os.makedirs("story_board", exist_ok=True)
    file_path = os.path.join("story_board", filename)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(storyboard, f, indent=2, ensure_ascii=False)
        
    return file_path


def process_first_pending_idea():
    """Process only the first idea with smallest ID and pending status"""
    ideas = load_ideas()
    ideas.sort(key=lambda x: x['id'])
    
    for idea in ideas:
        if idea.get('publishing_status') != 'pending':
            print(f"Skipping ID {idea['id']}: Status is '{idea.get('publishing_status')}'")
            continue
            
        print(f"\nProcessing ID {idea['id']}: {idea['idea']}")
        
        try:
            print("Generating storyboard...")
            storyboard = generate_storyboard(
                idea_title=idea['idea'],
                idea_description=idea['caption'],
                caption=idea['caption']
            )
            
            filename = f"{idea['idea'].replace(' ', '_').replace('/', '_')}.json"
            saved_path = save_storyboard(storyboard, filename)
            
            idea['final_output'] = saved_path
            idea['publishing_status'] = 'storyboard_generated'
            idea['error_log'] = ''
            
            save_ideas(ideas)
            
            print(f"✓ Storyboard saved: {saved_path}")
            print(f"✓ Status updated to 'storyboard_generated'")
            print(f"\n{'='*50}")
            print(f"Processing complete!")
            print(f"{'='*50}")
            return True
            
        except Exception as e:
            error_message = str(e)
            idea['error_log'] = error_message
            save_ideas(ideas)
            
            print(f"✗ Error processing ID {idea['id']}: {error_message}")
            print(f"\n{'='*50}")
            print(f"Processing failed!")
            print(f"{'='*50}")
            return False
            
    print("\nNo ideas with 'pending' status found.")
    print(f"{'='*50}")
    return False


if __name__ == "__main__":
    process_first_pending_idea()
