import os
import json
from dotenv import load_dotenv
from openai import OpenAI
import sys

# Load environment variables from .env file
load_dotenv()

class APIProviderManager:
    """Manages multiple API providers with automatic fallback"""
    
    def __init__(self):
        self.primary_provider = os.getenv('API_PROVIDER', 'NVIDIA').upper()
        self.client = None
        self.current_provider = None
        self.model = None
        
    def get_nvidia_client(self):
        """Initialize NVIDIA NIM API client"""
        api_key = os.getenv('NVIDIA_API_KEY')
        model = os.getenv('NVIDIA_MODEL', 'meta/llama-3.1-8b-instruct')
        
        if not api_key:
            raise ValueError("NVIDIA_API_KEY not found in environment variables")
        
        client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=api_key
        )
        return client, model, 'NVIDIA'
    
    def get_g4f_client(self):
        """Initialize G4F API client"""
        model = os.getenv('G4F_MODEL', 'gpt-4o-mini')
        
        client = OpenAI(
            base_url="http://localhost:1337/v1",
            api_key="secret"
        )
        return client, model, 'G4F'
    
    def get_openai_client(self):
        """Initialize custom OpenAI API client"""
        api_key = os.getenv('OPENAI_API_KEY')
        base_url = os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1')
        model = os.getenv('MODEL_NAME', 'gpt-3.5-turbo')
        
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        
        client = OpenAI(
            base_url=base_url,
            api_key=api_key
        )
        return client, model, 'OPENAI'
    
    def initialize_client(self, provider_name):
        """Initialize client for specified provider"""
        try:
            if provider_name == 'NVIDIA':
                return self.get_nvidia_client()
            elif provider_name == 'G4F':
                return self.get_g4f_client()
            elif provider_name == 'OPENAI':
                return self.get_openai_client()
            else:
                raise ValueError(f"Unknown provider: {provider_name}")
        except Exception as e:
            print(f"Failed to initialize {provider_name}: {str(e)}")
            return None, None, None
    
    def setup_with_fallback(self):
        """Setup client with fallback logic"""
        self.client, self.model, self.current_provider = self.initialize_client(self.primary_provider)
        
        if self.client:
            print(f"✓ Successfully connected to {self.current_provider}")
            return True
        
        fallback_providers = []
        if self.primary_provider == 'NVIDIA':
            fallback_providers = ['G4F']
        elif self.primary_provider == 'G4F':
            fallback_providers = ['NVIDIA']
        elif self.primary_provider == 'OPENAI':
            print("✗ OpenAI provider failed and no fallback is configured")
            return False
        
        for fallback in fallback_providers:
            print(f"⚠ Attempting fallback to {fallback}...")
            self.client, self.model, self.current_provider = self.initialize_client(fallback)
            
            if self.client:
                print(f"✓ Successfully connected to fallback provider: {self.current_provider}")
                return True
        
        print("✗ All providers failed")
        return False
    
    def chat_completion(self, messages, temperature=0.7, max_tokens=2000, stream=False):
        """Send a chat completion request (raw API, no response_format)"""
        if not self.client:
            raise Exception("No active client. Please setup client first.")
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream
            )
            return response
        except Exception as e:
            print(f"Error during API call with {self.current_provider}: {str(e)}")
            
            if self.current_provider in ['NVIDIA', 'G4F']:
                fallback = 'G4F' if self.current_provider == 'NVIDIA' else 'NVIDIA'
                print(f"⚠ Attempting fallback to {fallback} due to error...")
                
                self.client, self.model, self.current_provider = self.initialize_client(fallback)
                
                if self.client:
                    print(f"✓ Switched to fallback provider: {self.current_provider}")
                    try:
                        response = self.client.chat.completions.create(
                            model=self.model,
                            messages=messages,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            stream=stream
                        )
                        return response
                    except Exception as fallback_error:
                        print(f"Fallback provider also failed: {str(fallback_error)}")
                        raise
            raise


def load_existing_ideas(filename='ideas.json'):
    """Load existing ideas from JSON file if it exists"""
    
    print("\n" + "="*60)
    print("CHECKING FOR EXISTING IDEAS")
    print("="*60 + "\n")
    
    if not os.path.exists(filename):
        print(f"✓ No existing file found: {filename}")
        print("  Starting with empty list (IDs will start from 1)")
        return [], 0
    
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            existing_ideas = json.load(f)
        
        # Ensure it's a list
        if not isinstance(existing_ideas, list):
            print(f"⚠ Warning: Existing file is not a JSON array. Starting fresh.")
            return [], 0
        
        if len(existing_ideas) == 0:
            print(f"✓ Found empty file: {filename}")
            print("  Starting with empty list (IDs will start from 1)")
            return [], 0
        
        # Find the maximum ID
        max_id = max(idea.get('id', 0) for idea in existing_ideas)
        
        print(f"✓ Found {len(existing_ideas)} existing ideas in {filename}")
        print(f"  Highest existing ID: {max_id}")
        print(f"  New ideas will start from ID: {max_id + 1}")
        
        return existing_ideas, max_id
        
    except json.JSONDecodeError as e:
        print(f"⚠ Warning: Could not parse existing JSON file: {str(e)}")
        print("  Starting fresh with empty list")
        return [], 0
    except Exception as e:
        print(f"⚠ Warning: Error reading file: {str(e)}")
        print("  Starting fresh with empty list")
        return [], 0


def generate_initial_ideas(manager):
    """Generate initial video content ideas"""
    
    prompt = """Create a JSON array with 5–10 short-form video content ideas optimized for TikTok, Instagram Reels, and YouTube Shorts, suitable for a general knowledge or storytelling channel.

Requirements:
- Ensure diversity across science, history, unsolved mysteries, technology, surprising human-interest stories, and oddities. Cover at least 5 different categories overall.
- Each idea must be anchored in a specific interesting fact, lesser-known story, or fascinating concept that can be explained in 20–45 seconds.
- idea: Write a strong hook-style title (4–8 words), no clickbait, clear capitalization, minimal punctuation.
- caption: One compelling sentence that teases the twist or key takeaway and sets a hook-first narrative.
- channel_style_prompt: Concise, comma-separated keywords for theme and editing style suited to vertical short-form content, e.g., vertical video, fast paced, b roll, text captions, sound effects, dramatic reveal, educational, voiceover.
- character_style_prompt: A vivid, visual prompt for a key image or character tied to the idea (include age, attire, setting, lighting, mood, camera angle, color palette).
- production_status: Always set to for production.
- final_output: Leave blank (empty string).
- publishing_status: Always set to pending.
- error_log: Leave blank (empty string).
- Language: English.
- Safety: Avoid sensationalism and harmful content; keep facts accurate. If speculative, use words like theory or legend in the caption.
- IMPORTANT: Output ONLY valid JSON with proper double quotes around all keys and string values.
- Do not add any commentary before or after the JSON.

Output format: A JSON array of objects with these exact fields:
id, idea, caption, channel_style_prompt, character_style_prompt, production_status, final_output, publishing_status, error_log

Constraints:
- id is a unique integer starting at 1.
- Do not repeat the same subtopic; ensure variety across entries.
- Optimize all ideas for vertical short-form pacing with a 3–5 second hook.
- Output valid JSON only with properly escaped quotes if needed."""
    
    messages = [
        {"role": "user", "content": prompt}
    ]
    
    print("\n" + "="*60)
    print("STEP 1: GENERATING INITIAL VIDEO IDEAS")
    print("="*60)
    print(f"Using Provider: {manager.current_provider}")
    print(f"Using Model: {manager.model}")
    print("="*60 + "\n")
    
    try:
        print("Sending request to API...")
        response = manager.chat_completion(
            messages, 
            temperature=0.8, 
            max_tokens=2500
        )
        
        raw_content = response.choices[0].message.content
        
        print("\n" + "-"*60)
        print("RAW API RESPONSE:")
        print("-"*60)
        print(raw_content[:500] + "..." if len(raw_content) > 500 else raw_content)
        print("-"*60 + "\n")
        
        # Parse JSON
        print("Parsing JSON response...")
        try:
            json_data = json.loads(raw_content)
            print("✓ Successfully parsed JSON")
        except json.JSONDecodeError as e:
            print(f"✗ JSON parsing failed: {str(e)}")
            raise ValueError(f"Could not parse JSON response: {str(e)}")
        
        # Extract array if wrapped in object
        if isinstance(json_data, dict):
            print(f"Response is a dictionary with keys: {list(json_data.keys())}")
            for key, value in json_data.items():
                if isinstance(value, list) and len(value) > 0:
                    print(f"✓ Found array in key '{key}', extracting it...")
                    json_data = value
                    break
            else:
                print("No array found, wrapping single object in array...")
                json_data = [json_data]
        elif isinstance(json_data, list):
            print(f"✓ Response is already an array with {len(json_data)} items")
        else:
            json_data = [json_data]
        
        print(f"\n✓ Generated {len(json_data)} initial ideas")
        for item in json_data:
            idea_id = item.get('id', 'N/A')
            idea_title = item.get('idea', 'N/A')
            print(f"  • ID {idea_id}: {idea_title}")
        
        return json_data
        
    except Exception as e:
        print(f"\n✗ Error generating initial ideas: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def rank_and_filter_ideas(manager, initial_ideas):
    """Rank ideas and return only the best ones"""
    
    # Convert ideas to JSON string for inclusion in prompt
    ideas_json_string = json.dumps(initial_ideas, indent=2, ensure_ascii=False)
    
    ranking_prompt = f"""Analyze and rank all provided short-form video ideas based on the following criteria. Output ONLY the top-ranked ideas in JSON format matching the original input structure.

Evaluation Criteria (Score each 1-10):

1. hook_strength: Does the title and caption immediately grab attention within 3 seconds? Is the hook curiosity-driven and specific?

2. viral_potential: Likelihood of shares, saves, and rewatches based on uniqueness, emotional trigger, or surprise factor.

3. production_feasibility: Can this be produced with accessible resources? Does the character_style_prompt provide clear visual direction?

4. educational_value: Does it deliver a satisfying payoff? Is the fact or story genuinely interesting and memorable?

5. platform_optimization: Is it optimized for vertical video pacing (20-45 seconds)? Does the channel_style_prompt match short-form best practices?

6. engagement_trigger: Does it spark comments, debates, or emotional reactions (wonder, curiosity, shock)?

Ranking Process:
- Calculate total_score for each idea (sum of all 6 criteria, max 60 points)
- Rank all ideas from highest to lowest total_score
- For ties, prioritize hook_strength, then viral_potential
- Select only ideas with total_score >= 45 (top-tier ideas)
- If fewer than 3 ideas score >= 45, output the top 3 ideas regardless of score

Output Format (JSON array):
[
  {{
    "id": 1,
    "idea": "<original_idea_title>",
    "caption": "<original_caption>",
    "channel_style_prompt": "<original_channel_style_prompt>",
    "character_style_prompt": "<original_character_style_prompt>",
    "production_status": "for production",
    "final_output": "",
    "publishing_status": "pending",
    "error_log": ""
  }}
]

Requirements:
- Output ONLY valid JSON array with no additional text, markdown, or commentary
- Preserve all original field values exactly as provided in the input
- Order array from highest ranked to lowest ranked
- Include only top-performing ideas based on scoring threshold
- Ensure JSON is parseable by Python json.loads()

Here are the ideas to rank:

{ideas_json_string}"""
    
    messages = [
        {"role": "user", "content": ranking_prompt}
    ]
    
    print("\n" + "="*60)
    print("STEP 2: RANKING AND FILTERING IDEAS")
    print("="*60)
    print(f"Using Provider: {manager.current_provider}")
    print(f"Using Model: {manager.model}")
    print(f"Analyzing {len(initial_ideas)} ideas...")
    print("="*60 + "\n")
    
    try:
        print("Sending ranking request to API...")
        response = manager.chat_completion(
            messages, 
            temperature=0.3,  # Lower temperature for more consistent evaluation
            max_tokens=2500
        )
        
        raw_content = response.choices[0].message.content
        
        print("\n" + "-"*60)
        print("RANKING API RESPONSE:")
        print("-"*60)
        print(raw_content[:500] + "..." if len(raw_content) > 500 else raw_content)
        print("-"*60 + "\n")
        
        # Parse JSON
        print("Parsing ranked ideas JSON...")
        try:
            json_data = json.loads(raw_content)
            print("✓ Successfully parsed ranked ideas")
        except json.JSONDecodeError as e:
            print(f"✗ JSON parsing failed: {str(e)}")
            raise ValueError(f"Could not parse ranked ideas JSON: {str(e)}")
        
        # Extract array if wrapped in object
        if isinstance(json_data, dict):
            print(f"Response is a dictionary with keys: {list(json_data.keys())}")
            for key, value in json_data.items():
                if isinstance(value, list) and len(value) > 0:
                    print(f"✓ Found array in key '{key}', extracting it...")
                    json_data = value
                    break
            else:
                print("No array found, wrapping single object in array...")
                json_data = [json_data]
        elif isinstance(json_data, list):
            print(f"✓ Response is already an array with {len(json_data)} items")
        else:
            json_data = [json_data]
        
        print(f"\n✓ Filtered to {len(json_data)} top-ranked ideas")
        for idx, item in enumerate(json_data, 1):
            idea_id = item.get('id', 'N/A')
            idea_title = item.get('idea', 'N/A')
            print(f"  #{idx} - ID {idea_id}: {idea_title}")
        
        return json_data
        
    except Exception as e:
        print(f"\n✗ Error ranking ideas: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def renumber_and_append_ids(new_ideas, start_id):
    """Renumber IDs for new ideas starting from start_id"""
    
    print("\n" + "="*60)
    print("STEP 3: RENUMBERING NEW IDs")
    print("="*60 + "\n")
    
    print(f"Starting ID for new ideas: {start_id}")
    
    renumbered_ideas = []
    
    for idx, idea in enumerate(new_ideas, start=start_id):
        old_id = idea.get('id', 'N/A')
        idea['id'] = idx
        renumbered_ideas.append(idea)
        print(f"  New ID {idx}: '{idea.get('idea', 'N/A')}' (Old ID: {old_id})")
    
    print(f"\n✓ Successfully renumbered {len(renumbered_ideas)} new ideas")
    
    return renumbered_ideas


def save_ideas_to_file(existing_ideas, new_ideas, output_file='ideas.json'):
    """Append new ideas to existing ideas and save to JSON file"""
    
    try:
        print(f"\n{'='*60}")
        print(f"STEP 4: SAVING TO FILE: {output_file}")
        print(f"{'='*60}\n")
        
        # Combine existing and new ideas
        combined_ideas = existing_ideas + new_ideas
        
        print(f"  Existing ideas: {len(existing_ideas)}")
        print(f"  New ideas: {len(new_ideas)}")
        print(f"  Total ideas: {len(combined_ideas)}")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(combined_ideas, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ Successfully saved {len(combined_ideas)} total ideas to '{output_file}'")
        
        # Verify file
        if os.path.exists(output_file):
            file_size = os.path.getsize(output_file)
            print(f"✓ File verified: {output_file} ({file_size} bytes)")
        else:
            print(f"✗ Warning: File {output_file} was not created!")
            return False
        
        return True
        
    except Exception as e:
        print(f"✗ Error saving to file: {str(e)}")
        return False


def main():
    """Main execution function"""
    
    # Initialize the provider manager
    manager = APIProviderManager()
    
    # Setup client with fallback
    if not manager.setup_with_fallback():
        print("Failed to initialize any API provider")
        sys.exit(1)
    
    # Load existing ideas and get max ID
    existing_ideas, max_existing_id = load_existing_ideas('ideas.json')
    
    # Step 1: Generate initial ideas
    initial_ideas = generate_initial_ideas(manager)
    
    if not initial_ideas:
        print("✗ Failed to generate initial ideas. Exiting.")
        sys.exit(1)
    
    # Step 2: Rank and filter ideas
    ranked_ideas = rank_and_filter_ideas(manager, initial_ideas)
    
    if not ranked_ideas:
        print("✗ Failed to rank ideas. Using initial ideas instead...")
        ranked_ideas = initial_ideas
    
    # Step 3: Renumber IDs starting from max_existing_id + 1
    new_ideas = renumber_and_append_ids(ranked_ideas, start_id=max_existing_id + 1)
    
    # Step 4: Append to existing ideas and save to file
    if save_ideas_to_file(existing_ideas, new_ideas, output_file='ideas.json'):
        print("\n" + "="*60)
        print("SUMMARY")
        print("="*60)
        print(f"✓ Total ideas in file: {len(existing_ideas) + len(new_ideas)}")
        print(f"✓ ID range: 1 to {max_existing_id + len(new_ideas)}")
        
        print("\nFirst new idea added:")
        print("-" * 60)
        print(json.dumps(new_ideas[0], indent=2))
        print("-" * 60)
        
        print("\n✓ Script completed successfully!")
        print(f"✓ Check 'ideas.json' for all ideas")
    else:
        print("\n✗ Script completed with errors")
        sys.exit(1)


if __name__ == "__main__":
    main()
