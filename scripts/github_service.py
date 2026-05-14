# github_service.py

import requests
import re
from config import GITHUB_TOKEN

HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

IGNORE_PATTERNS = [
    r'.*\.lock$',
    r'.*-lock\.yaml$',
    r'.*\.svg$',
    r'.*\.png$|.*\.jpg$',
    r'.*\.min\.(js|css)$',
    r'.*/dist/.*',
    r'.*/build/.*',
    r'.*\.map$'
]


# =========================
# PR METADATA
# =========================

def get_pr_details(repo_full_name: str, pr_number: int):
    url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    data = response.json()

    return {
        "title": data.get("title", "No Title"),
        "body": data.get("body", "No Description"),
        "author": data.get("user", {}).get("login", "Unknown"),
        "commits_count": data.get("commits", 1),
        "review_comments_count": data.get("review_comments", 0),
        "changed_files_count": data.get("changed_files", 1)
    }


# =========================
# DIFF PROCESSING
# =========================

def tag_file(file_name: str) -> str:
    name = file_name.lower()

    if "test" in name:
        return "[TEST FILE]"
    if "config" in name or ".env" in name:
        return "[CONFIG]"
    if "core" in name or "service" in name:
        return "[CORE LOGIC]"
    return "[CODE]"


def get_pr_diff(repo_full_name: str, pr_number: int):
    url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}.diff?w=1"

    diff_headers = HEADERS.copy()
    diff_headers["Accept"] = "application/vnd.github.v3.diff"

    response = requests.get(url, headers=diff_headers)
    response.raise_for_status()

    raw_diff = response.text
    return clean_raw_diff(raw_diff)


def clean_raw_diff(raw_diff: str, max_length: int = 20000) -> str:
    if not raw_diff:
        return ""

    files = raw_diff.split("diff --git ")
    blocks = []

    for file_diff in files:
        if not file_diff.strip():
            continue

        first_line = file_diff.split('\n')[0]
        file_name = first_line.split(' b/')[-1] if ' b/' in first_line else first_line

        should_ignore = any(
            re.match(pattern, file_name, re.IGNORECASE)
            for pattern in IGNORE_PATTERNS
        )

        tag = tag_file(file_name)

        if should_ignore:
            blocks.append(
                f"{tag}\n"
                f"diff --git {first_line}\n"
                f"# [OMITTED: auto-generated or binary]"
            )
        else:
            blocks.append(f"{tag}\n" + f"diff --git {file_diff}")

    cleaned = "\n".join(blocks)

    # Smart truncation: keep head + tail
    if len(cleaned) > max_length:
        half = max_length // 2
        cleaned = (
            cleaned[:half] +
            "\n\n...[TRUNCATED]...\n\n" +
            cleaned[-half:]
        )

    return cleaned