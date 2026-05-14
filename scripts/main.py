from fastapi import FastAPI, Request
from github_service import get_pr_details, get_pr_diff
from llm_service import summarize_pr
from storage_service import save_summary
import uvicorn

app = FastAPI()

@app.post("/webhook")
async def github_webhook(request: Request):
    """Listens for GitHub Webhook events."""
    payload = await request.json()
    
    # 1. We only care if a Pull Request was CLOSED and MERGED
    if payload.get("action") == "closed" and payload.get("pull_request", {}).get("merged") == True:
        pr_number = payload["pull_request"]["number"]
        repo_name = payload["repository"]["full_name"]
        
        print(f"Detected Merged PR #{pr_number} in {repo_name}. Processing...")
        
        try:
            # 2. Fetch Data (The Hands)
            pr_meta = get_pr_details(repo_name, pr_number)
            pr_diff = get_pr_diff(repo_name, pr_number)
            
            # 3. Process with AI (The Brain)
            print("Sending to LLM for summarization...")
            ai_summary = summarize_pr(pr_meta, pr_diff)
            
            # 4. Save to Memory (The Memory)
            save_summary(repo_name, pr_number, ai_summary)
            
            return {"status": "success", "message": f"Processed PR #{pr_number}"}
            
        except Exception as e:
            print(f"Error processing PR: {e}")
            return {"status": "error", "message": str(e)}

    # Ignore other events (opened PRs, comments, etc.)
    return {"status": "ignored", "message": "Not a merged PR event."}

if __name__ == "__main__":
    # Run the server locally on port 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)
