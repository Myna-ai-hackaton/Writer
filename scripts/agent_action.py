import os
import json
from github_service import get_pr_details, get_pr_diff
from llm_service import summarize_pr
from storage_service import save_summary

def run():
    # GitHub Actions provides the path to the event payload
    event_path = os.getenv("GITHUB_EVENT_PATH")
    
    with open(event_path, "r") as f:
        payload = json.load(f)

    # Verify this is a merged PR
    if payload.get("pull_request", {}).get("merged") == True:
        pr_number = payload["pull_request"]["number"]
        repo_name = payload["repository"]["full_name"]
        
        print(f"Processing Merged PR #{pr_number} in {repo_name}...")
        
        try:
            # 1. Fetch Data
            pr_meta = get_pr_details(repo_name, pr_number)
            pr_diff = get_pr_diff(repo_name, pr_number)
            
            # 2. Summarize
            ai_summary = summarize_pr(pr_meta, pr_diff)
            
            # 3. Save to Firebase
            save_summary(repo_name, pr_number, ai_summary)
            
            print("Done!")
            
        except Exception as e:
            print(f"Error: {e}")
            exit(1)
    else:
        print("Not a merged PR. Skipping.")

if __name__ == "__main__":
    run()
