import os
import json
import base64
import sys
from github_service import get_pr_details, get_pr_diff
from llm_service import summarize_pr
from storage_service import save_summary, summary_exists

def run():
    # --- 1. SECURITY: Decode/Create Firebase JSON ---
    fb_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "firebase-key.json")
    
    # Check if we already have the file (local test)
    if not os.path.exists(fb_path):
        b64_content = os.getenv("FIREBASE_SERVICE_ACCOUNT_B64")
        raw_json_content = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")

        if b64_content:
            print(f"Decoding Firebase key from Base64 to {fb_path}...")
            try:
                decoded_json = base64.b64decode(b64_content).decode('utf-8')
                with open(fb_path, "w") as f:
                    f.write(decoded_json)
            except Exception as e:
                print(f"Critical Error: Failed to decode FIREBASE_SERVICE_ACCOUNT_B64. {e}")
                sys.exit(1)
        elif raw_json_content:
            print(f"Creating Firebase key from JSON string to {fb_path}...")
            with open(fb_path, "w") as f:
                f.write(raw_json_content)
        else:
            print(f"Error: Firebase credentials not found. Ensure either FIREBASE_SERVICE_ACCOUNT_B64 or FIREBASE_SERVICE_ACCOUNT_JSON is set in GitHub Secrets.")
            # We don't exit here yet, because storage_service might have its own fallback or we might want the error to be caught later.
            # But in your case, it will fail in summary_exists.

    # --- 2. GITHUB PAYLOAD: Read the event ---
    event_path = os.getenv("GITHUB_EVENT_PATH")
    if not event_path or not os.path.exists(event_path):
        print("Error: GITHUB_EVENT_PATH not found. Are you running this in GitHub Actions?")
        sys.exit(1)

    with open(event_path, "r") as f:
        payload = json.load(f)

    # --- 3. EVENT VERIFICATION ---  
    action = payload.get("action")
    is_merged = payload.get("pull_request", {}).get("merged") == True

    if action != "closed" or not is_merged:
        print("Event is not a merged Pull Request. Skipping execution.")
        sys.exit(0)

    pr_number = payload["pull_request"]["number"]
    repo_name = payload["repository"]["full_name"]
    print(f"Triggered for Merged PR #{pr_number} in {repo_name}...")

    # --- 4. IDEMPOTENCY ---
    try:
        if summary_exists(repo_name, pr_number):
            print(f"Success: PR #{pr_number} has already been summarized. Skipping.")
            sys.exit(0)
    except Exception as e:
        print(f"Warning: Could not check idempotency (Firebase connection issue): {e}")
        # We continue anyway to try and summarize

    # --- 5. CORE PIPELINE ---
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
        print(f"System Failure: {e}")
        # Try to save error to Firebase if possible
        try:
            error_data = {"error": f"Agent crashed: {str(e)}"}
            save_summary(repo_name, pr_number, error_data)
        except:
            pass
        sys.exit(1)

if __name__ == "__main__":
    run()
