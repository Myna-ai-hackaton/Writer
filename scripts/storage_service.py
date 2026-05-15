import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud import firestore as google_firestore
from config import FIREBASE_SERVICE_ACCOUNT_PATH
import os

# Initialize Firebase
# This only needs to happen once
if not firebase_admin._apps:
    # Ensure the path is set and exists, otherwise we can't initialize
    if not FIREBASE_SERVICE_ACCOUNT_PATH or not os.path.exists(
        FIREBASE_SERVICE_ACCOUNT_PATH
    ):
        # We don't raise an error here because the agent_action.py will create the file
        # if it's missing but provided in Base64. We'll check again in save_summary.
        pass
    else:
        cred = credentials.Certificate(FIREBASE_SERVICE_ACCOUNT_PATH)
        firebase_admin.initialize_app(cred)


def get_db():
    if not firebase_admin._apps:
        if not FIREBASE_SERVICE_ACCOUNT_PATH or not os.path.exists(
            FIREBASE_SERVICE_ACCOUNT_PATH
        ):
            raise FileNotFoundError(
                f"Firebase key file not found at: {FIREBASE_SERVICE_ACCOUNT_PATH}"
            )
        cred = credentials.Certificate(FIREBASE_SERVICE_ACCOUNT_PATH)
        firebase_admin.initialize_app(cred)
    return firestore.client()


def repo_to_project_id(repo_name: str) -> str:
    """Normalize repo names into a stable Firestore document id."""
    return repo_name.replace("/", "__")


def save_summary(repo_name: str, pr_number: int, summary_data: dict):
    """
    Saves the rich, categorized AI summary to Firebase Firestore.
    """
    db = get_db()
    project_id = repo_to_project_id(repo_name)

    # New Hierarchical Path: myna_ai_info -> Writer -> prs -> {doc_id}
    doc_id = f"{project_id}_pr_{pr_number}"
    doc_ref = (
        db.collection("myna_ai_info")
        .document("Writer")
        .collection("prs")
        .document(doc_id)
    )

    # We check if the summary_data contains an error first
    if "error" in summary_data:
        data = {
            "repository": repo_name,
            "pr_number": pr_number,
            "status": "failed_summary",
            "error_message": summary_data["error"],
            "raw_output": summary_data.get("raw_output", ""),
            "timestamp": google_firestore.SERVER_TIMESTAMP,
        }
    else:
        # Matches the new "Sensor vs. Brain" schema
        data = {
            "repository": repo_name,
            "pr_number": pr_number,
            "status": "success",
            "author": summary_data.get("author", "Unknown"),
            "pr_overview": summary_data.get("pr_overview", ""),
            "changes": summary_data.get("changes", []),
            "risk_assessment": summary_data.get("risk_assessment", {}),
            "core_files_touched": summary_data.get("core_files_touched", []),
            "time_open_hours": summary_data.get("time_open_hours"),
            "time_open_days": summary_data.get("time_open_days"),
            "timestamp": google_firestore.SERVER_TIMESTAMP,
        }

    # Save to Firestore
    doc_ref.set(data)
    print(f"Successfully synced PR #{pr_number} to {project_id}/prs")


def summary_exists(repo_name: str, pr_number: int) -> bool:
    """
    Checks if a summary for this PR already exists in Firebase.
    Used for Idempotency to prevent duplicate LLM calls.
    """
    db = get_db()
    project_id = repo_to_project_id(repo_name)

    doc_id = f"{project_id}_pr_{pr_number}"
    doc_ref = (
        db.collection("myna_ai_info")
        .document("Writer")
        .collection("prs")
        .document(doc_id)
    )

    doc = doc_ref.get()

    # We only consider it "existing" if it was a success.
    # If it failed previously, we might want to let it try again.
    if doc.exists and doc.to_dict().get("status") == "success":
        return True
    return False


def get_developer_profile(repo_name: str, github_handle: str):
    """
    Fetches the existing developer profile from Firestore under the repo branch.
    Returns a dict or an empty template if not found.
    """
    db = get_db()
    project_id = repo_to_project_id(repo_name)
    doc_ref = (
        db.collection("myna_ai_info")
        .document("Writer")
        .collection("developers")
        .document(github_handle)
    )
    doc = doc_ref.get()

    if doc.exists:
        return doc.to_dict()

    # Return empty template if new developer
    return {
        "github_handle": github_handle,
        "last_active": None,
        "python_managed_state": {
            "activity_counters": {"merged": 0, "denied": 0},
            "rolling_metrics": {
                "complexity": 5.0,
                "docs": 5.0,
                "resilience": 5.0,
                "quality": 5.0,
            },
            "temporal_history": [],
            "archetype_distribution": {
                "architect": 0,
                "plumber": 0,
                "janitor": 0,
                "bug_squasher": 0,
            },
            "skills_matrix": {},
        },
        "projects": {},
    }


def update_developer_profile(repo_name: str, github_handle: str, profile_data: dict):
    """
    Saves/Updates the evolved developer profile in Firestore under the repo branch.
    """
    db = get_db()
    project_id = repo_to_project_id(repo_name)
    doc_ref = (
        db.collection("myna_ai_info")
        .document("Writer")
        .collection("developers")
        .document(github_handle)
    )

    # Ensure handle is in the data
    profile_data["github_handle"] = github_handle
    profile_data["last_active"] = google_firestore.SERVER_TIMESTAMP

    doc_ref.set(profile_data, merge=True)
    print(
        f"Successfully evolved profile for @{github_handle} in {project_id}/developers"
    )
