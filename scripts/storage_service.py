import json
import os
from config import MEMORY_FILE_PATH

def save_summary(repo_name: str, pr_number: int, summary_data: dict):
    """Saves the AI summary to a local JSON file (acting as our database)."""
    
    # Create the file if it doesn't exist
    if not os.path.exists(MEMORY_FILE_PATH):
        with open(MEMORY_FILE_PATH, 'w') as f:
            json.dump([], f)

    # Read existing memory
    with open(MEMORY_FILE_PATH, 'r') as f:
        try:
            memory = json.load(f)
        except json.JSONDecodeError:
            memory = []

    # Create the new entry
    new_entry = {
        "repository": repo_name,
        "pr_number": pr_number,
        "summary": summary_data
    }

    # Append and save
    memory.append(new_entry)
    with open(MEMORY_FILE_PATH, 'w') as f:
        json.dump(memory, f, indent=4)
        
    print(f"Successfully saved PR #{pr_number} to memory!")
