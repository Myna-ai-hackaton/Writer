import json
from openai import OpenAI
from config import OPENROUTER_API_KEY

# Initialize OpenAI client with OpenRouter base URL
client = OpenAI(
  base_url="https://openrouter.ai/api/v1",
  api_key=OPENROUTER_API_KEY,
)

def summarize_pr(pr_metadata: dict, diff: str) -> dict:
    """Sends the PR data to OpenRouter and gets a structured JSON summary."""
    
    prompt = f"""
    You are an expert Git Project Manager. Analyze the following Pull Request and summarize it.
    
    PR Title: {pr_metadata['title']}
    PR Description: {pr_metadata['body']}
    PR Author: {pr_metadata['author']}
    
    Code Diff:
    {diff[:10000]} # Truncating to avoid hitting context limits
    
    Return a STRICT JSON object with exactly these keys:
    - "business_reason": A 1-sentence explanation of what feature/fix this introduces for non-technical users.
    - "files_affected": A brief list or summary of core files changed.
    - "risk_level": "Low", "Medium", or "High" (High if database, auth, or core payments are changed).
    - "technical_summary": A 2-sentence summary for developers.
    """

    try:
        completion = client.chat.completions.create(
          model="google/gemini-2.0-flash-001", # Or any other model available on OpenRouter
          messages=[
            {
              "role": "user",
              "content": prompt,
            },
          ],
          response_format={ "type": "json_object" }
        )
        
        return json.loads(completion.choices[0].message.content)
    except Exception as e:
        print(f"Failed to get summary from OpenRouter: {e}")
        return {"error": str(e)}
