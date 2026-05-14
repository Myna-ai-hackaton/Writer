import json
from openai import OpenAI
from config import OPENROUTER_API_KEY

# Initialize OpenAI client with OpenRouter base URL
client = OpenAI(
  base_url="https://openrouter.ai/api/v1",
  api_key=OPENROUTER_API_KEY,
)

def summarize_pr(pr_metadata: dict, diff: str) -> dict:
    """
    Sends the PR data and cleaned diff to OpenRouter.
    Returns a highly structured JSON object categorizing every change.
    """

    # We use a system-level persona to ground the model's behavior. 
    system_instruction = (
        "You are a Staff Software Engineer and an Expert Product Manager. "
        "Your job is to analyze raw Git Pull Requests and translate them into structured, "
        "categorized, and highly accurate release summaries. "      
        "You separate business value from technical implementation."
    )

    prompt = f"""
    Analyze the following Pull Request data:

    --- PR METADATA ---
    Title: {pr_metadata.get('title', 'No Title')}
    Author: {pr_metadata.get('author', 'Unknown')}
    Description: {pr_metadata.get('body', 'No Description')}        

    --- CODE DIFF ---
    {diff}

    --- INSTRUCTIONS ---
    Break down the Pull Request into specific, categorized changes. 
    Ignore trivial files (like version bumps or auto-generated content) unless they are the only change.

    You MUST return a STRICT, valid JSON object matching this exact schema:
    {{
      "pr_overview": "A 1-2 sentence high-level summary of the entire PR's purpose.",
      "changes": [
        {{
          "category": "Must be exactly one of: [Feature, Bugfix, Refactor, Performance, Security, Chore, Docs]",
          "business_description": "How this specific change affects the user or business (non-technical).",
          "technical_description": "What was actually changed in the code (developer-focused)."
        }}
      ],
      "risk_assessment": {{
        "level": "Low", "Medium", or "High",
        "reasoning": "Why this risk level was assigned (e.g., 'Modifies database schema' = High)."
      }},
      "core_files_touched": ["List of the 2-5 most important files changed. Omit minor config files."]
    }}
    """

    try:
        completion = client.chat.completions.create(
          model="google/gemini-2.0-flash-001",
          messages=[
            {"role": "system", "content": system_instruction},      
            {"role": "user", "content": prompt},
          ],
          response_format={ "type": "json_object" },
          temperature=0.2 # Low temperature for factual, analytical output
        )

        raw_json_string = completion.choices[0].message.content     
        return json.loads(raw_json_string)

    except json.JSONDecodeError:
        print("Failed to parse LLM response into valid JSON.")      
        return {"error": "Invalid JSON returned by LLM", "raw_output": raw_json_string}
    except Exception as e:
        print(f"Failed to get summary from OpenRouter: {e}")        
        return {"error": str(e)}
