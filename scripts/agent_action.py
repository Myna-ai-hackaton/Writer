import os
import json
import sys
from github_service import fetch_full_pr_context
from llm_service import summarize_pr, evaluate_pr_and_update_profile
from storage_service import (
    save_summary,
    summary_exists,
    get_developer_profile,
    update_developer_profile,
)


def run():
    # --- 1. FIREBASE SETUP: Create key file from GitHub Secret ---
    fb_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "firebase-key.json")

    # Check if key file exists (local) or needs creation (GitHub Action)
    if not os.path.exists(fb_path):
        json_content = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")

        if json_content:
            print("Initializing Firebase credentials from secret...")
            with open(fb_path, "w") as f:
                f.write(json_content)
        else:
            print("CRITICAL ERROR: 'FIREBASE_SERVICE_ACCOUNT_JSON' secret is missing!")
            print("Please add your Firebase Service Account JSON to GitHub Secrets.")
            sys.exit(1)

    if not os.getenv("GH_PAT"):
        print("CRITICAL ERROR: GH_PAT is missing.")
        sys.exit(1)

    # --- 2. GITHUB PAYLOAD: Identify the triggering event ---
    event_path = os.getenv("GITHUB_EVENT_PATH")
    if not event_path or not os.path.exists(event_path):
        print("Error: GITHUB_EVENT_PATH not found. (Expected in GitHub Actions)")
        sys.exit(1)

    with open(event_path, "r") as f:
        payload = json.load(f)

    # --- 3. VERIFICATION: Process only closed Pull Requests ---
    action = payload.get("action")
    if action != "closed":
        print(f"Action is '{action}', not 'closed'. Skipping.")
        sys.exit(0)

    pr_number = payload["pull_request"]["number"]
    repo_name = payload["repository"]["full_name"]
    project_name = repo_name.split("/")[-1]
    author_handle = payload["pull_request"]["user"]["login"]
    is_merged = payload["pull_request"].get("merged", False)

    status_label = "Merged" if is_merged else "Closed (Not Merged)"
    print(
        f"Analyzing {status_label} PR #{pr_number} in {repo_name} (@{project_name}) by @{author_handle}..."
    )

    # --- 4. IDEMPOTENCY: Avoid duplicate AI calls ---
    try:
        if summary_exists(repo_name, pr_number):
            print(f"PR #{pr_number} already summarized in Firebase. Skipping.")
            sys.exit(0)
    except Exception as e:
        print(f"Error checking Firebase: {e}")
        sys.exit(1)

    # --- 5. CORE PIPELINE: Fetch -> Summarize -> Brain -> Save ---
    try:
        print(f"1/4: Fetching consolidated context for PR #{pr_number}...")
        full_context = fetch_full_pr_context(repo_name, pr_number)
        full_context["pr_number"] = pr_number

        # Fetch the existing developer profile (repo-specific)
        existing_profile = get_developer_profile(repo_name, author_handle)

        print("2/4: Running 'Sensor' (LLM) to extract engineering signals...")
        ai_response = summarize_pr(full_context, existing_profile)

        if "error" in ai_response:
            print(f"AI Failure: {ai_response['error']}")
            save_summary(repo_name, pr_number, ai_response)
            sys.exit(1)

        print("3/4: Running 'Brain' (Python) to evolve developer profile...")
        updated_profile = evaluate_pr_and_update_profile(
            ai_response, full_context, existing_profile
        )

        print(f"4/4: Syncing PR Summary and Profile to {project_name}...")
        # Include author for the summary
        pr_summary = ai_response.get("pr_summary", {})
        pr_summary["author"] = author_handle
        
        save_summary(repo_name, pr_number, pr_summary)
        update_developer_profile(repo_name, author_handle, updated_profile)

        print("Done! Agent finished successfully.")

    except Exception as e:
        print(f"Pipeline Error: {e}")
        # Log failure to Firebase if possible
        try:
            save_summary(repo_name, pr_number, {"error": str(e)})
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    run()
