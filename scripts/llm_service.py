import json
import os
from openai import OpenAI
import google.generativeai as genai
from config import OPENAI_API_KEY, OPENROUTER_API_KEY, GEMINI_API_KEY

def get_llm_client():
    """
    Determines which LLM provider to use based on available API keys.
    Returns (client, provider_type, model_name)
    """
    if OPENAI_API_KEY:
        print("Using OpenAI (ChatGPT) as the LLM provider.")
        client = OpenAI(api_key=OPENAI_API_KEY)
        return client, "openai", "gpt-4o-mini"
    
    if OPENROUTER_API_KEY:
        print("Using OpenRouter as the LLM provider.")
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY,
        )
        return client, "openrouter", "google/gemini-flash-1.5"
    
    if GEMINI_API_KEY:
        print("Using Google Gemini (Direct) as the LLM provider.")
        genai.configure(api_key=GEMINI_API_KEY)
        client = genai.GenerativeModel('gemini-1.5-flash')
        return client, "gemini", "gemini-1.5-flash"
    
    raise ValueError("No AI API keys found. Please set OPENAI_API_KEY, OPENROUTER_API_KEY, or GEMINI_API_KEY.")

def summarize_pr(pr_metadata: dict, diff: str) -> dict:
    """
    Sends the PR data and cleaned diff to the chosen LLM provider.
    """
    client, provider, model = get_llm_client()

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
        if provider in ["openai", "openrouter"]:
            completion = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt},
                ],
                response_format={ "type": "json_object" },
                temperature=0.2
            )
            raw_json_string = completion.choices[0].message.content
        
        elif provider == "gemini":
            # Gemini-specific call
            full_prompt = f"{system_instruction}\n\n{prompt}"
            response = client.generate_content(
                full_prompt,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                )
            )
            raw_json_string = response.text

        return json.loads(raw_json_string)

    except json.JSONDecodeError:
        print("Failed to parse LLM response into valid JSON.")
        return {"error": "Invalid JSON returned by LLM", "raw_output": raw_json_string if 'raw_json_string' in locals() else "No output"}
    except Exception as e:
        print(f"Failed to get summary from {provider}: {e}")
        return {"error": str(e)}
