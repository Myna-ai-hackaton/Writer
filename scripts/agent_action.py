import os
import json
import base64
import sys

def run():
    # --- 1. SECURITY: Decode Firebase JSON FIRST ---
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

    # --- 2. DELAYED IMPORTS ---
    # We import these only AFTER the firebase key file is written to disk
    from github_service import get_pr_details, get_pr_diff
    from llm_service import summarize_pr, engine_check_pr
    from storage_service import save_summary, summary_exists

    # --- 3. GITHUB PAYLOAD ---
    event_path = os.getenv("GITHUB_EVENT_PATH")
    if not event_path or not os.path.exists(event_path):
        print("Error: GITHUB_EVENT_PATH not found.")
        sys.exit(1)

    with open(event_path, "r") as f:
        payload = json.load(f)

    # --- 4. EVENT VERIFICATION ---
    action = payload.get("action")
    is_merged = payload.get("pull_request", {}).get("merged") == True
    
    if action != "closed" or not is_merged:
        print("Event is not a merged Pull Request. Skipping.")
        sys.exit(0)

    pr_number = payload["pull_request"]["number"]
    repo_name = payload["repository"]["full_name"]

    # --- 5. IDEMPOTENCY ---
    if summary_exists(repo_name, pr_number):
        print(f"PR #{pr_number} already processed. Skipping.")
        sys.exit(0)

    # --- 6. CORE PIPELINE ---
    try:
        print("Fetching metadata and diff...")
        pr_meta = get_pr_details(repo_name, pr_number)
        pr_diff = get_pr_diff(repo_name, pr_number)
        
        print("Running Physics Engine check...")
        engine_results = engine_check_pr(pr_meta, pr_diff)
        
        print("Generating AI Summary...")
        ai_summary = summarize_pr(pr_meta, pr_diff)
        
        # Attach engine results to the main summary
        ai_summary["engine_check"] = engine_results
        
        print("Saving to Firebase...")
        save_summary(repo_name, pr_number, ai_summary)
        print("Writer Agent completed successfully!")
        
    except Exception as e:
        print(f"System Failure: {e}")
        save_summary(repo_name, pr_number, {"error": str(e)})
        sys.exit(1)

if __name__ == "__main__":
    run()