import json
import os
import subprocess
import sys
import time
from getpass import getpass
from pathlib import Path
from typing import Dict, List, Optional

import requests

# Early check to ensure the rest of the project files exist
try:
    import config
    import github_service
    import llm_service
    import storage_service
except ImportError as e:
    print(f"CRITICAL ERROR: Missing required local module: {e.name}.py")
    print("This script is part of a larger project and cannot be run standalone.")
    sys.exit(1)


GITHUB_API_HEADERS: Dict[str, str] = {
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "myna-writer-bootstrap",
}


def prompt_secret(env_key: str, prompt_text: str) -> str:
    value = os.getenv(env_key)
    if value:
        return value
    return getpass(prompt_text).strip()


def prompt_value(env_key: str, prompt_text: str, default: Optional[str] = None) -> str:
    value = os.getenv(env_key)
    if value:
        return value

    prompt_suffix = f" [{default}]" if default else ""
    result = input(f"{prompt_text}{prompt_suffix}: ").strip()
    if not result and default is not None:
        return default
    return result


def parse_github_repo(remote_url: str) -> Optional[str]:
    if remote_url.endswith(".git"):
        remote_url = remote_url[:-4]

    if remote_url.startswith("git@github.com:"):
        return remote_url.split(":", 1)[1]
    if remote_url.startswith("https://github.com/"):
        return remote_url.split("https://github.com/", 1)[1]
    if remote_url.startswith("ssh://git@github.com/"):
        return remote_url.split("ssh://git@github.com/", 1)[1]
    if remote_url.startswith("git://github.com/"):
        return remote_url.split("git://github.com/", 1)[1]
    if "/github.com/" in remote_url:
        return remote_url.split("github.com/", 1)[1]
    return None


def infer_repo_full_name() -> str:
    # Auto-detection removed. Forces manual input every time.
    repo = input("Enter the GitHub repository full name (owner/repo) to analyze: ").strip()
    if "/" not in repo:
        print("Invalid repository name. Expected format owner/repo.")
        sys.exit(1)
    return repo


def ensure_firebase_key() -> str:
    default_path = "firebase-key.json"
    fb_path = prompt_value(
        "FIREBASE_SERVICE_ACCOUNT_PATH",
        "Enter Firebase service account JSON path",
        default_path,
    )

    if not fb_path:
        fb_path = default_path

    fb_path_obj = Path(fb_path)
    if fb_path_obj.exists():
        return str(fb_path_obj.resolve())

    print(
        "Firebase key file was not found locally. You can either provide a path to an existing file or paste the JSON content."
    )
    existing_path = input("Enter an existing path if you have one, or press enter to paste JSON: ").strip()
    if existing_path:
        existing_obj = Path(existing_path)
        if existing_obj.exists():
            return str(existing_obj.resolve())
        print(f"Path not found: {existing_path}")

    content = getpass("Paste the Firebase service account JSON here: ")
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        print("The provided content is not valid JSON.")
        sys.exit(1)

    fb_path_obj.write_text(json.dumps(parsed, indent=2))
    print(f"Wrote Firebase service account JSON to {fb_path_obj}")
    return str(fb_path_obj.resolve())


def choose_llm_provider() -> None:
    # Fixed: Actually check if the keys are already in the environment
    openai_key = os.getenv("OPENAI_API_KEY")
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")

    if openai_key or openrouter_key or gemini_key:
        return

    print("No LLM key found in the environment. Select one provider:")
    print("1) OpenAI")
    print("2) OpenRouter")
    print("3) Google Gemini")

    choice = input("Choose 1, 2, or 3: ").strip()
    if choice == "1":
        key = prompt_secret("OPENAI_API_KEY", "Enter OPENAI_API_KEY: ")
        os.environ["OPENAI_API_KEY"] = key
    elif choice == "2":
        key = prompt_secret("OPENROUTER_API_KEY", "Enter OPENROUTER_API_KEY: ")
        os.environ["OPENROUTER_API_KEY"] = key
    elif choice == "3":
        key = prompt_secret("GEMINI_API_KEY", "Enter GEMINI_API_KEY: ")
        os.environ["GEMINI_API_KEY"] = key
    else:
        print("Invalid choice. Please run the script again.")
        sys.exit(1)


def configure_environment() -> None:
    gh_pat = os.getenv("GH_PAT")
    if not gh_pat:
        gh_pat = prompt_secret("GH_PAT", "Enter GH_PAT: ")
        os.environ["GH_PAT"] = gh_pat

    firebase_path = ensure_firebase_key()
    os.environ["FIREBASE_SERVICE_ACCOUNT_PATH"] = firebase_path

    choose_llm_provider()

    if not os.getenv("GH_PAT"):
        print("GH_PAT is required.")
        sys.exit(1)


def github_request(url: str, params: Dict[str, str]) -> dict:
    headers = GITHUB_API_HEADERS.copy()
    gh_pat = os.getenv("GH_PAT")
    if gh_pat:
        headers["Authorization"] = f"Bearer {gh_pat}"

    response = requests.get(url, headers=headers, params=params, timeout=30)
    if response.status_code == 403:
        raise RuntimeError(
            f"GitHub API rate limit or permission error: {response.status_code} {response.text}"
        )
    response.raise_for_status()
    return response.json()


def fetch_closed_pr_numbers(repo_full_name: str, limit: Optional[int] = None) -> List[int]:
    pr_numbers: List[int] = []
    page = 1

    while True:
        params = {"state": "closed", "per_page": "100", "page": str(page)}
        items = github_request(
            f"https://api.github.com/repos/{repo_full_name}/pulls", params
        )
        if not items:
            break

        for item in items:
            if item.get("number"):
                pr_numbers.append(int(item["number"]))
                # Added: Stop fetching if we hit the requested limit
                if limit and len(pr_numbers) >= limit:
                    return pr_numbers

        page += 1
        time.sleep(0.5)

    return pr_numbers


def print_progress(index: int, total: int, pr_number: int, status: str) -> None:
    print(f"[{index}/{total}] PR #{pr_number}: {status}")


def process_pr(repo_full_name: str, pr_number: int):
    # Imports moved to the top of the file for safer early failure detection
    try:
        if storage_service.summary_exists(repo_full_name, pr_number):
            return "skipped-already-summarized"

        full_context = github_service.fetch_full_pr_context(repo_full_name, pr_number)
        full_context["pr_number"] = pr_number
        author_handle = full_context["metadata"].get("author", "unknown")

        existing_profile = storage_service.get_developer_profile(repo_full_name, author_handle)
        ai_response = llm_service.summarize_pr(full_context, existing_profile)

        if "error" in ai_response:
            storage_service.save_summary(repo_full_name, pr_number, ai_response)
            return "saved-error"

        updated_profile = llm_service.evaluate_pr_and_update_profile(
            ai_response, full_context, existing_profile
        )

        pr_summary = ai_response.get("pr_summary", {})
        pr_summary["author"] = author_handle

        storage_service.save_summary(repo_full_name, pr_number, pr_summary)
        storage_service.update_developer_profile(repo_full_name, author_handle, updated_profile)
        return "saved-success"

    except Exception as exc:
        print(f"Error processing PR #{pr_number}: {exc}")
        try:
            storage_service.save_summary(
                repo_full_name,
                pr_number,
                {"error": str(exc), "raw_output": ""},
            )
        except Exception:
            pass
        return "failed"


def main() -> None:
    print("Writer bootstrap: importing closed PR history into Firebase")
    repo_full_name = infer_repo_full_name()
    print(f"Repository detected: {repo_full_name}")

    configure_environment()

    # Import modules after the environment is configured so config values are loaded correctly.
    import importlib
    importlib.reload(config)

    # Added limit prompt to prevent massive LLM bills on large repos like libOTe
    limit_input = input("Enter max number of PRs to process (press Enter for all): ").strip()
    pr_limit = int(limit_input) if limit_input.isdigit() else None

    pr_numbers = fetch_closed_pr_numbers(repo_full_name, limit=pr_limit)
    if not pr_numbers:
        print("No closed PRs found.")
        return

    print(f"Found {len(pr_numbers)} closed PR(s). This may trigger many LLM calls.")
    confirm = input("Continue and process these PRs? [y/N]: ").strip().lower()
    if confirm != "y":
        print("Aborted by user.")
        return

    summary_counts = {
        "saved-success": 0,
        "skipped-already-summarized": 0,
        "saved-error": 0,
        "failed": 0,
    }

    total = len(pr_numbers)
    for index, pr_number in enumerate(pr_numbers, start=1):
        status = process_pr(repo_full_name, pr_number)
        summary_counts[status] = summary_counts.get(status, 0) + 1
        print_progress(index, total, pr_number, status)
        time.sleep(30)

    print("\nImport complete.")
    print("Summary:")
    for key, count in summary_counts.items():
        print(f"  {key}: {count}")


if __name__ == "__main__":
    main()