import firebase_admin
from firebase_admin import credentials, firestore
from config import FIREBASE_SERVICE_ACCOUNT_PATH
import os

def get_db():
    """Initializes Firebase only when needed."""
    if not firebase_admin._apps:
        if not os.path.exists(FIREBASE_SERVICE_ACCOUNT_PATH):
            raise FileNotFoundError(f"Key not found at: {FIREBASE_SERVICE_ACCOUNT_PATH}")
        cred = credentials.Certificate(FIREBASE_SERVICE_ACCOUNT_PATH)
        firebase_admin.initialize_app(cred)
    return firestore.client()

def save_summary(repo_name: str, pr_number: int, summary_data: dict):
    db = get_db()
    doc_id = f"{repo_name.replace('/', '_')}_pr_{pr_number}"
    doc_ref = db.collection("summaries").document(doc_id)
    
    if "error" in summary_data:
        data = {
            "repository": repo_name,
            "pr_number": pr_number,
            "status": "failed_summary",
            "error_message": summary_data["error"],
            "timestamp": firestore.SERVER_TIMESTAMP
        }
    else:
        data = {
            "repository": repo_name,
            "pr_number": pr_number,
            "status": "success",
            "pr_overview": summary_data.get("pr_overview", ""),
            "changes": summary_data.get("changes", []),
            "risk_assessment": summary_data.get("risk_assessment", {}),
            "engine_check": summary_data.get("engine_check", {}),
            "timestamp": firestore.SERVER_TIMESTAMP
        }
    doc_ref.set(data)

def summary_exists(repo_name: str, pr_number: int) -> bool:
    try:
        db = get_db()
        doc_id = f"{repo_name.replace('/', '_')}_pr_{pr_number}"
        doc = db.collection("summaries").document(doc_id).get()
        return doc.exists and doc.to_dict().get("status") == "success"
    except:
        return False