import google.generativeai as genai
import json
from config import GEMINI_API_KEY

# Configure the Gemini API
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

def summarize_pr(pr_metadata: dict, diff: str) -> dict:
    """Sends the PR data to the AI and gets a structured JSON summary."""
    
    prompt = f"""
    You are an expert Git Project Manager. Analyze the following Pull Request and summarize it.
    
    PR Title: {pr_metadata['title']}
    PR Description: {pr_metadata['body']}
    PR Author: {pr_metadata['author']}
    
    Code Diff:
    {diff[:10000]} # Truncating to avoid hitting context limits on massive PRs
    
    Return a STRICT JSON object with exactly these keys:
    - "business_reason": A 1-sentence explanation of what feature/fix this introduces for non-technical users.
    - "files_affected": A brief list or summary of core files changed.
    - "risk_level": "Low", "Medium", or "High" (High if database, auth, or core payments are changed).
    - "technical_summary": A 2-sentence summary for developers.
    """

    # Forcing the model to output valid JSON
    response = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json",
        )
    )
    
    try:
        return json.loads(response.text)
    except json.JSONDecodeError:
        print("Failed to parse LLM response.")
        return {"error": "Invalid JSON returned by LLM", "raw_text": response.text}
