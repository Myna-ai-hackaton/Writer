import firebase_admin
from firebase_admin import credentials, firestore
from config import FIREBASE_SERVICE_ACCOUNT_PATH
import os
import json

# Initialize Firebase
# This only needs to happen once
if not firebase_admin._apps:
    # Ensure the path exists, otherwise we can't initialize
    if not os.path.exists(FIREBASE_SERVICE_ACCOUNT_PATH):
        raise FileNotFoundError(f"Firebase key file not found at: {FIREBASE_SERVICE_ACCOUNT_PATH}")
        
    cred = credentials.Certificate(FIREBASE_SERVICE_ACCOUNT_PATH)
    firebase_admin.initialize_app(cred)

db = firestore.client()

def save_summary(repo_name: str, pr_number: int, summary_data: dict):
    """
    Saves the rich, categorized AI summary to Firebase Firestore.
    """
    
    # We use repo_name + pr_number as a unique ID to avoid duplicates
    doc_id = f"{repo_name.replace('/', '_')}_pr_{pr_number}"
    doc_ref = db.collection("summaries").document(doc_id)
    
    # We check if the summary_data contains an error first
    if "error" in summary_data:
        data = {
            "repository": repo_name,
            "pr_number": pr_number,
            "status": "failed_summary",
            "error_message": summary_data["error"],
            "raw_output": summary_data.get("raw_output", ""),
            "timestamp": firestore.SERVER_TIMESTAMP
        }
    else:
        # This maps directly to the new structured JSON array we requested from OpenRouter
        data = {
            "repository": repo_name,
            "pr_number": pr_number,
            "status": "success",
            "pr_overview": summary_data.get("pr_overview", ""),
            "changes": summary_data.get("changes", []), # This is our new categorized array
            "risk_assessment": summary_data.get("risk_assessment", {}),
            "core_files_touched": summary_data.get("core_files_touched", []),
            "timestamp": firestore.SERVER_TIMESTAMP
        }

    # Save to Firestore
    doc_ref.set(data)
    print(f"Successfully synced PR #{pr_number} to Firebase Cloud!")

def summary_exists(repo_name: str, pr_number: int) -> bool:
    """
    Checks if a summary for this PR already exists in Firebase.
    Used for Idempotency to prevent duplicate LLM calls.
    """
    doc_id = f"{repo_name.replace('/', '_')}_pr_{pr_number}"
    doc_ref = db.collection("summaries").document(doc_id)
    
    doc = doc_ref.get()
    
    # We only consider it "existing" if it was a success. 
    # If it failed previously, we might want to let it try again.
    if doc.exists and doc.to_dict().get("status") == "success":
        return True
    return False