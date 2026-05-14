from typing import Dict, Union
import requests
import re
from scripts.config import GH_PAT

HEADERS: Dict[str, Union[str, bytes]] = {
    "Authorization": f"Bearer {GH_PAT}",
    "Accept": "application/vnd.github.v3+json",
}

# --- List of noisy/junk files we do NOT want to send to the LLM ---
IGNORE_PATTERNS = [
    r".*\.lock$",  # package-lock.json, yarn.lock
    r".*-lock\.yaml$",  # pnpm-lock.yaml
    r".*\.svg$",  # SVG images (massive math arrays)
    r".*\.png$|.*\.jpg$",  # Binary images
    r".*\.min\.(js|css)$",  # Minified code
    r".*/dist/.*",  # Compiled output folders
    r".*/build/.*",  # Build artifacts
    r".*\.map$",  # Source maps
]


def fetch_full_pr_context(repo_full_name: str, pr_number: int) -> dict:
    """
    Consolidated fetcher that gathers metadata, stats, test ratios, feedback, and diffs.
    Handles pagination for files and reviews to ensure complete data.
    """
    base_url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}"
    
    # 1. Fetch Main PR Data
    pr_res = requests.get(base_url, headers=HEADERS)
    pr_res.raise_for_status()
    data = pr_res.json()

    # Determine State: 'accepted_merged', 'denied_abandoned', or 'open'
    merged_at = data.get("merged_at")
    raw_state = data.get("state")
    
    if merged_at:
        final_status = "accepted_merged"
    elif raw_state == "closed" and not merged_at:
        final_status = "denied_abandoned"
    else:
        final_status = "open"

    # 2. Fetch Feedback (Reviews and Comments) with Pagination
    review_dialogue = []
    page = 1
    while True:
        reviews_res = requests.get(f"{base_url}/reviews?page={page}&per_page=100", headers=HEADERS)
        reviews_res.raise_for_status()
        reviews = reviews_res.json()
        if not reviews:
            break
        
        for r in reviews:
            # Ignore bot comments and empty bodies
            user = r.get("user", {})
            if r.get("body") and user.get("type") != "Bot":
                review_dialogue.append({
                    "user": user.get("login"),
                    "body": r.get("body"),
                    "state": r.get("state")
                })
        page += 1

    # 3. Fetch Test Stats with Pagination
    test_files = 0
    total_files = 0
    test_patterns = [r".*test.*", r".*spec.*", r".*mock.*"]
    page = 1
    while True:
        files_res = requests.get(f"{base_url}/files?page={page}&per_page=100", headers=HEADERS)
        files_res.raise_for_status()
        files = files_res.json()
        if not files:
            break
        
        total_files += len(files)
        for f in files:
            filename = f.get("filename", "").lower()
            if any(re.match(p, filename) for p in test_patterns):
                test_files += 1
        page += 1

    # 4. Fetch Diff
    diff_headers = HEADERS.copy()
    diff_headers["Accept"] = "application/vnd.github.v3.diff"
    diff_res = requests.get(f"{base_url}.diff?w=1", headers=diff_headers)
    diff_res.raise_for_status()

    return {
        "metadata": {
            "title": data.get("title"),
            "author": data.get("user", {}).get("login"),
            "repo": repo_full_name,
            "status": final_status,
            "is_draft": data.get("draft", False),
            "body": data.get("body", "")
        },
        "stats": {
            "additions": data.get("additions", 0),
            "deletions": data.get("deletions", 0),
            "changed_files": data.get("changed_files", 0),
            "commits": data.get("commits", 0),
            "created_at": data.get("created_at"),
            "merged_at": merged_at
        },
        "test_stats": {
            "test_file_count": test_files,
            "total_files": total_files,
            "test_ratio_percent": round((test_files / total_files * 100), 2) if total_files > 0 else 0
        },
        "feedback_loop": {
            "dialogue": review_dialogue[-10:], # Last 10 human comments for context
            "comment_count": data.get("review_comments", 0)
        },
        "diff": clean_raw_diff(diff_res.text)
    }


def clean_raw_diff(raw_diff: str, max_length: int = 15000) -> str:
    """
    Parses a raw git diff, removes noisy/massive files,
    and safely truncates the final output.
    """
    if not raw_diff:
        return ""

    # GitHub separates each file in the diff with the string "diff --git "
    files = raw_diff.split("diff --git ")
    optimized_diff_blocks = []

    for file_diff in files:
        if not file_diff.strip():
            continue

        # The first line contains the file path, e.g., "a/src/main.py b/src/main.py"
        first_line = file_diff.split("\n")[0]

        # Extract the file name (the part after ' b/')
        file_name = first_line.split(" b/")[-1] if " b/" in first_line else first_line

        # Check if this file matches any of our junk patterns
        should_ignore = any(
            re.match(pattern, file_name, re.IGNORECASE) for pattern in IGNORE_PATTERNS
        )

        if should_ignore:
            # We keep the filename so the LLM knows it changed, but delete the massive code payload
            optimized_diff_blocks.append(
                f"diff --git {first_line}\n"
                f"--- a/{file_name}\n"
                f"+++ b/{file_name}\n"
                f"@@ -0,0 +0,0 @@\n"
                f"# [CONTENT OMITTED FROM AI SUMMARY: Auto-generated or binary file]"
            )
        else:
            # If the file is valid, restore its prefix and keep it
            optimized_diff_blocks.append(f"diff --git {file_diff}")

    # Rejoin everything back into a single string
    cleaned_diff = "\n".join(optimized_diff_blocks)

    # Final safety truncation: if it's still huge after cleaning, cut it safely
    if len(cleaned_diff) > max_length:
        cleaned_diff = (
            cleaned_diff[:max_length]
            + "\n\n... [DIFF TRUNCATED DUE TO LENGTH LIMIT] ..."
        )

    return cleaned_diff
