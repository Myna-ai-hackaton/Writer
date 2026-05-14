import requests
from config import GH_PAT

HEADERS = {
    "Authorization": f"Bearer {GH_PAT}",
    "Accept": "application/vnd.github.v3+json"
}

def get_pr_details(repo_full_name: str, pr_number: int):
    """Fetches the PR title and description."""
    url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    data = response.json()
    return {
        "title": data.get("title"),
        "body": data.get("body"),
        "author": data.get("user", {}).get("login")
    }

def get_pr_diff(repo_full_name: str, pr_number: int):
    """Fetches the raw code changes (.patch/diff format)."""
    url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}"
    
    # Custom header to tell GitHub we want the raw diff string, not JSON
    diff_headers = HEADERS.copy()
    diff_headers["Accept"] = "application/vnd.github.v3.diff"
    
    response = requests.get(url, headers=diff_headers)
    response.raise_for_status()
    return response.text # Returns the raw diff string
