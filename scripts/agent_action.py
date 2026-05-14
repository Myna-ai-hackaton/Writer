import os
import json
import sys
from github_service import (
    get_pr_details,
    get_pr_diff,
    get_test_ratio,
    get_pr_feedback,
)
from llm_service import summarize_pr
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

    # --- 2. GITHUB PAYLOAD: Identify the triggering event ---
    event_path = os.getenv("GITHUB_EVENT_PATH")
    if not event_path or not os.path.exists(event_path):
        print("Error: GITHUB_EVENT_PATH not found. (Expected in GitHub Actions)")
        sys.exit(1)

    with open(event_path, "r") as f:
        payload = json.load(f)

    # --- 3. VERIFICATION: Process only merged Pull Requests ---
    action = payload.get("action")
    is_merged = payload.get("pull_request", {}).get("merged") is True

    if action != "closed" or not is_merged:
        print("Event is not a merged PR. Skipping.")
        sys.exit(0)

    pr_number = payload["pull_request"]["number"]
    repo_name = payload["repository"]["full_name"]
    project_name = repo_name.split("/")[-1]
    author_handle = payload["pull_request"]["user"]["login"]

    print(
        f"Analyzing Merged PR #{pr_number} in {repo_name} (@{project_name}) by @{author_handle}..."
    )

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
        print(
            f"1/4: Fetching PR data, feedback, and engineering stats for @{author_handle}..."
        )
        pr_meta = get_pr_details(repo_name, pr_number)
        pr_meta["repo"] = repo_name
        pr_diff = get_pr_diff(repo_name, pr_number)

        # New: Fetch Test-to-Code ratio
        test_stats = get_test_ratio(repo_name, pr_number)
        pr_meta["test_stats"] = test_stats

        # Fetch PR iteration metadata (commits, comments, etc)
        pr_feedback = get_pr_feedback(repo_name, pr_number)

        # Fetch the existing developer profile (Project-specific)
        existing_profile = get_developer_profile(project_name, author_handle)

        print(
            "2/4: Summarizing PR and evolving developer profile (with deep analytics)..."
        )
        ai_response = summarize_pr(pr_meta, pr_diff, existing_profile, pr_feedback)

        if "error" in ai_response:
            print(f"AI Failure: {ai_response['error']}")
            sys.exit(1)

        pr_summary = ai_response.get("pr_summary", {})
        updated_profile = ai_response.get("updated_profile", {})

        print(f"3/4: Syncing PR Summary to {project_name}/prs...")
        save_summary(repo_name, pr_number, pr_summary)

        print(
            f"4/4: Saving evolved profile for @{author_handle} in {project_name}/developers..."
        )
        update_developer_profile(project_name, author_handle, updated_profile)

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
