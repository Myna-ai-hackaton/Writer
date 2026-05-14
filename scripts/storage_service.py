import firebase_admin
from firebase_admin import credentials, firestore
from config import FIREBASE_SERVICE_ACCOUNT_PATH

# Initialize Firebase
# This only needs to happen once
if not firebase_admin._apps:
    cred = credentials.Certificate(FIREBASE_SERVICE_ACCOUNT_PATH)
    firebase_admin.initialize_app(cred)

db = firestore.client()

def save_summary(repo_name: str, pr_number: int, summary_data: dict):
    """Saves the AI summary to Firebase Firestore."""
    
    # We use repo_name + pr_number as a unique ID to avoid duplicates
    doc_id = f"{repo_name.replace('/', '_')}_pr_{pr_number}"
    
    doc_ref = db.collection("summaries").document(doc_id)
    
    data = {
        "repository": repo_name,
        "pr_number": pr_number,
        "business_reason": summary_data.get("business_reason"),
        "files_affected": summary_data.get("files_affected"),
        "risk_level": summary_data.get("risk_level"),
        "technical_summary": summary_data.get("technical_summary"),
        "timestamp": firestore.SERVER_TIMESTAMP # Good for the Reader to sort by latest
    }

    doc_ref.set(data)
    
    print(f"Successfully synced PR #{pr_number} to Firebase Cloud!")
