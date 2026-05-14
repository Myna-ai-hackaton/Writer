import os
import json
import base64
import sys
from github_service import get_pr_details, get_pr_diff
from llm_service import summarize_pr
from storage_service import save_summary, summary_exists

def run():
    # --- 1. SECURITY: Decode Firebase JSON from Base64 ---
    # GitHub Secrets often break raw JSON formatting. We use Base64 to bypass this.
    b64_firebase_content = os.getenv("FIREBASE_SERVICE_ACCOUNT_B64")
    fb_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "firebase-key.json")

    if b64_firebase_content and not os.path.exists(fb_path):        
        print(f"Decoding Firebase key to {fb_path}...")
        try:
            decoded_json = base64.b64decode(b64_firebase_content).decode('utf-8')
            with open(fb_path, "w") as f:
                f.write(decoded_json)
        except Exception as e:
            print(f"Critical Error: Failed to decode Firebase secret. {e}")
            sys.exit(1)

    # --- 2. GITHUB PAYLOAD: Read the event that triggered this action ---
    event_path = os.getenv("GITHUB_EVENT_PATH")
    if not event_path or not os.path.exists(event_path):
        print("Error: GITHUB_EVENT_PATH not found. Are you running this in GitHub Actions?")
        sys.exit(1)

    with open(event_path, "r") as f:
        payload = json.load(f)

    # --- 3. EVENT VERIFICATION: We only care about merged PRs ---  
    action = payload.get("action")
    is_merged = payload.get("pull_request", {}).get("merged") == True

    # If a PR is just opened, or closed without merging, we do nothing.
    if action != "closed" or not is_merged:
        print("Event is not a merged Pull Request. Skipping execution.")
        sys.exit(0) # Exit with 0 so the GitHub Action turns green  

    pr_number = payload["pull_request"]["number"]
    repo_name = payload["repository"]["full_name"]
    print(f"Triggered for Merged PR #{pr_number} in {repo_name}...")

    # --- 4. IDEMPOTENCY: Check if we already did this ---
    if summary_exists(repo_name, pr_number):
        print(f"Success: PR #{pr_number} has already been summarized.")
        print("Skipping LLM execution to save OpenRouter tokens.")  
        sys.exit(0)

    # --- 5. CORE PIPELINE: Execute the flow with Graceful Degradation ---
    try:
        print("Fetching PR metadata and code diff...")
        pr_meta = get_pr_details(repo_name, pr_number)
        pr_diff = get_pr_diff(repo_name, pr_number)

        print("Sending to OpenRouter for AI analysis...")
        ai_summary = summarize_pr(pr_meta, pr_diff)

        print("Saving results to Firebase...")
        save_summary(repo_name, pr_number, ai_summary)

        print("Writer Agent completed successfully!")

    except Exception as e:
        # Fallback error handling: If the GitHub API crashes or the network drops,
        # we catch it here and write a "failed" state to Firebase instead of vanishing.
        print(f"System Failure: {e}")
        error_data = {
            "error": f"Agent crashed before completing summary: {str(e)}"
        }
        save_summary(repo_name, pr_number, error_data)
        sys.exit(1) # Exit 1 so the developers see a red 'X' in GitHub Actions

if __name__ == "__main__":
    run()
