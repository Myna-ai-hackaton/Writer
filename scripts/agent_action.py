import os
import json
import sys
from github_service import get_pr_details, get_pr_diff
from llm_service import summarize_pr
from storage_service import save_summary, summary_exists

def run():
    # --- 1. FIREBASE SETUP: Create key file from GitHub Secret ---
    fb_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "firebase-key.json")
    
    # Check if key file exists (local) or needs creation (GitHub Action)
    if not os.path.exists(fb_path):
        json_content = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")

        if json_content:
            print(f"Initializing Firebase credentials from secret...")
            with open(fb_path, "w") as f:
                f.write(json_content)
        else:
            print("CRITICAL ERROR: 'FIREBASE_SERVICE_ACCOUNT_JSON' secret is missing!")
            print("Please add your Firebase Service Account JSON to GitHub Secrets.")
            sys.exit(1)

    # --- 2. GITHUB PAYLOAD: Identify the triggering event ---
    event_path = os.getenv("GITHUB_EVENT_PATH")
    if not event_path or not os.path.exists(event_path):
        print("Error: GITHUB_EVENT_PATH not found. (Expected in GitHub Actions)")
        sys.exit(1)

    with open(event_path, "r") as f:
        payload = json.load(f)

    # --- 3. VERIFICATION: Process only merged Pull Requests ---  
    action = payload.get("action")
    is_merged = payload.get("pull_request", {}).get("merged") == True

    if action != "closed" or not is_merged:
        print("Event is not a merged PR. Skipping.")
        sys.exit(0)

    pr_number = payload["pull_request"]["number"]
    repo_name = payload["repository"]["full_name"]
    print(f"Analyzing Merged PR #{pr_number} in {repo_name}...")

    # --- 4. IDEMPOTENCY: Avoid duplicate AI calls ---
    try:
        if summary_exists(repo_name, pr_number):
            print(f"PR #{pr_number} already summarized in Firebase. Skipping.")
            sys.exit(0)
    except Exception as e:
        print(f"Error checking Firebase: {e}")
        sys.exit(1)

    # --- 5. CORE PIPELINE: Fetch -> Summarize -> Save ---
    try:
        print("1/3: Fetching PR data and code changes...")
        pr_meta = get_pr_details(repo_name, pr_number)
        pr_diff = get_pr_diff(repo_name, pr_number)

        print("2/3: Summarizing with AI...")
        ai_summary = summarize_pr(pr_meta, pr_diff)

        if "error" in ai_summary:
            print(f"AI Failure: {ai_summary['error']}")
            sys.exit(1)

        print("3/3: Syncing to Cloud Memory...")
        save_summary(repo_name, pr_number, ai_summary)

        print("Done! Agent finished successfully.")

    except Exception as e:
        print(f"Pipeline Error: {e}")
        # Log failure to Firebase if possible
        try:
            save_summary(repo_name, pr_number, {"error": str(e)})
        except:
            pass
        sys.exit(1)

if __name__ == "__main__":
    run()
