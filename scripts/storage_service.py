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


def save_summary(repo_name: str, pr_number: int, summary_data: dict):
    """
    Saves the rich, categorized AI summary to Firebase Firestore.
    """
    db = get_db()
    project_name = repo_name.split("/")[-1]

    # New Hierarchical Path: myna_ai_info -> {Writer} -> prs -> {doc_id}
    doc_id = f"{project_name}_pr_{pr_number}"
    doc_ref = (
        db.collection("myna_ai_info")
        .document(project_name)
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
        # This maps directly to the new structured JSON array we requested from OpenRouter
        data = {
            "repository": repo_name,
            "pr_number": pr_number,
            "status": "success",
            "pr_overview": summary_data.get("pr_overview", ""),
            "changes": summary_data.get(
                "changes", []
            ),  # This is our new categorized array
            "risk_assessment": summary_data.get("risk_assessment", {}),
            "core_files_touched": summary_data.get("core_files_touched", []),
            "timestamp": google_firestore.SERVER_TIMESTAMP,
        }

    # Save to Firestore
    doc_ref.set(data)
    print(f"Successfully synced PR #{pr_number} to {project_name}/prs")


def summary_exists(repo_name: str, pr_number: int) -> bool:
    """
    Checks if a summary for this PR already exists in Firebase.
    Used for Idempotency to prevent duplicate LLM calls.
    """
    db = get_db()
    project_name = repo_name.split("/")[-1]

    doc_id = f"{project_name}_pr_{pr_number}"
    doc_ref = (
        db.collection("myna_ai_info")
        .document(project_name)
        .collection("prs")
        .document(doc_id)
    )

    doc = doc_ref.get()

    # We only consider it "existing" if it was a success.
    # If it failed previously, we might want to let it try again.
    if doc.exists and doc.to_dict().get("status") == "success":
        return True
    return False


def get_developer_profile(project_name: str, github_handle: str):
    """
    Fetches the existing developer profile from Firestore under the project branch.
    Returns a dict or an empty template if not found.
    """
    db = get_db()
    doc_ref = (
        db.collection("myna_ai_info")
        .document(project_name)
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
        "overall_metrics": {
            "total_prs_merged": 0,
            "average_complexity_score": 0,
            "documentation_habit_score": 0,
            "review_resilience_score": 0,
            "initial_quality_score": 0,
        },
        "archetype_distribution": {
            "architect": 0,
            "plumber": 0,
            "janitor": 0,
            "bug_squasher": 0,
        },
        "skills": {},
        "projects": {},
    }


def update_developer_profile(project_name: str, github_handle: str, profile_data: dict):
    """
    Saves/Updates the evolved developer profile in Firestore under the project branch.
    """
    db = get_db()
    doc_ref = (
        db.collection("myna_ai_info")
        .document(project_name)
        .collection("developers")
        .document(github_handle)
    )

    # Ensure handle is in the data
    profile_data["github_handle"] = github_handle
    profile_data["last_active"] = google_firestore.SERVER_TIMESTAMP

    doc_ref.set(profile_data, merge=True)
    print(
        f"Successfully evolved profile for @{github_handle} in {project_name}/developers"
    )
