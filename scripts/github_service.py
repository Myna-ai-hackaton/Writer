import requests
import re
from config import GH_PAT

HEADERS = {
    "Authorization": f"Bearer {GH_PAT}",
    "Accept": "application/vnd.github.v3+json"
}

# --- List of noisy/junk files we do NOT want to send to the LLM ---
IGNORE_PATTERNS = [
    r'.*\.lock$',             # package-lock.json, yarn.lock        
    r'.*-lock\.yaml$',        # pnpm-lock.yaml
    r'.*\.svg$',              # SVG images (massive math arrays)    
    r'.*\.png$|.*\.jpg$',     # Binary images
    r'.*\.min\.(js|css)$',    # Minified code
    r'.*/dist/.*',            # Compiled output folders
    r'.*/build/.*',           # Build artifacts
    r'.*\.map$'               # Source maps
]

def get_pr_details(repo_full_name: str, pr_number: int):
    """Fetches the PR title, description, and rich engineering stats."""
    url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    data = response.json()
    
    # Calculate time to merge
    created_at = data.get("created_at")
    merged_at = data.get("merged_at")
    
    return {
        "title": data.get("title", "No Title"),
        "body": data.get("body", "No Description"),
        "author": data.get("user", {}).get("login", "Unknown"),
        "stats": {
            "additions": data.get("additions", 0),
            "deletions": data.get("deletions", 0),
            "changed_files": data.get("changed_files", 0),
            "created_at": created_at,
            "merged_at": merged_at
        }
    }

def get_test_ratio(repo_full_name: str, pr_number: int):
    """Calculates what percentage of the PR is testing code."""
    url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}/files"
    response = requests.get(url, headers=HEADERS)
    files = response.json()
    
    test_files = 0
    logic_files = 0
    
    test_patterns = [r'.*test.*', r'.*spec.*', r'.*mock.*']
    
    for f in files:
        filename = f.get("filename", "").lower()
        if any(re.match(p, filename) for p in test_patterns):
            test_files += 1
        else:
            logic_files += 1
            
    total = test_files + logic_files
    return {
        "test_file_count": test_files,
        "logic_file_count": logic_files,
        "test_ratio_percent": round((test_files / total * 100), 2) if total > 0 else 0
    }

def get_pr_diff(repo_full_name: str, pr_number: int):
    """Fetches the raw code changes, ignoring pure whitespace changes."""
    # Added ?w=1 so GitHub ignores lines where only whitespace/indentation changed!
    url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}.diff?w=1"

    diff_headers = HEADERS.copy()
    diff_headers["Accept"] = "application/vnd.github.v3.diff"       

    response = requests.get(url, headers=diff_headers)
    response.raise_for_status()

    raw_diff = response.text
    return clean_raw_diff(raw_diff) # We pass the diff through our cleaner before returning it

def get_pr_feedback(repo_full_name: str, pr_number: int):
    """
    Fetches metadata about the PR process:
    - Number of review comments
    - Number of commits (to see how many iterations were needed)
    - If there were any change requests
    """
    # Fetch general PR info for commit count
    pr_url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}"
    pr_data = requests.get(pr_url, headers=HEADERS).json()
    
    # Fetch review comments
    reviews_url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}/reviews"
    reviews_data = requests.get(reviews_url, headers=HEADERS).json()
    
    change_requests = [r for r in reviews_data if r.get("state") == "CHANGES_REQUESTED"]
    review_comments = [r.get("body") for r in reviews_data if r.get("body")]

    return {
        "commit_count": pr_data.get("commits", 0),
        "review_comment_count": len(review_comments),
        "had_change_requests": len(change_requests) > 0,
        "review_summaries": review_comments[:5] # Send a few snippets to the AI
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
        first_line = file_diff.split('\n')[0]

        # Extract the file name (the part after ' b/')
        file_name = first_line.split(' b/')[-1] if ' b/' in first_line else first_line

        # Check if this file matches any of our junk patterns       
        should_ignore = any(re.match(pattern, file_name, re.IGNORECASE) for pattern in IGNORE_PATTERNS)

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
        cleaned_diff = cleaned_diff[:max_length] + "\n\n... [DIFF TRUNCATED DUE TO LENGTH LIMIT] ..."

    return cleaned_diff
