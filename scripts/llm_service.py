import json
import os
from openai import OpenAI
from google import genai
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
        # Using a more standard ID for OpenRouter
        return client, "openrouter", "google/gemini-2.5-flash"
    
    if GEMINI_API_KEY:
        print("Using Google Gemini (Direct) as the LLM provider.")
        client = genai.Client(api_key=GEMINI_API_KEY)
        return client, "gemini", "gemini-2.5-flash"
    
    raise ValueError("No AI API keys found. Please set OPENAI_API_KEY, OPENROUTER_API_KEY, or GEMINI_API_KEY.")

def summarize_pr(pr_metadata: dict, diff: str, existing_profile: dict = None, feedback_data: dict = None) -> dict:
    """
    Sends the PR data and cleaned diff to the chosen LLM provider.
    Also evolves the developer profile if provided, considering PR feedback.
    """
    client, provider, model = get_llm_client()

    system_instruction = (
        "You are an Elite Engineering Mentor and a Technical Auditor. "
        "Your role is to perform two critical tasks for every Pull Request: "
        "1. Technical Summarization: Generate accurate, categorized release notes for stakeholders. "
        "2. Talent Analytics: Act as an analytical engine that quantifies developer growth. "
        "You evaluate code quality, structural impact, and technical proficiency to maintain a 'Developer Profile' "
        "that reflects an engineer's true technical trajectory and core competencies."
    )

    # Prepare the context for the developer
    developer_context = ""
    if existing_profile:
        developer_context = f"""
        --- CURRENT DEVELOPER ANALYTICS ---
        {json.dumps(existing_profile, indent=2)}
        """

    feedback_context = ""
    if feedback_data:
        feedback_context = f"""
        --- PR VELOCITY & QUALITY METRICS ---
        Commits in this PR: {feedback_data.get('commit_count')}
        Review Comments: {feedback_data.get('review_comment_count')}
        Had Change Requests: {feedback_data.get('had_change_requests')}
        Reviewer Feedback Snippets: {json.dumps(feedback_data.get('review_summaries'))}
        """

    prompt = f"""
    Analyze the following Pull Request data to generate release notes and update developer competency metrics:

    --- PR METADATA ---
    Title: {pr_metadata.get('title', 'No Title')}
    Author: {pr_metadata.get('author', 'Unknown')}
    Repo: {pr_metadata.get('repo', 'Unknown')}
    Description: {pr_metadata.get('body', 'No Description')}        

    --- CODE DIFF ---
    {diff}

    {developer_context}
    {feedback_context}

    --- INSTRUCTIONS ---
    1. Generate PR Summary: Categorize changes (Feature, Bugfix, etc.) and explain business vs. technical impact.
    2. Quantify Competency Growth: Based on the diff and process feedback, evolve the developer's profile.
       - Complexity Score: 1-10 (Technical depth of the solution).
       - Documentation Score: 1-10 (Clarity of PR description and code intent).
       - Review Resilience: 1-10 (Ability to incorporate feedback and iterate effectively).
       - Initial Quality: 1-10 (Clarity and correctness of the first submission vs. subsequent revisions).
       - Proficiency (Skills): Identify tech used and award 'Competency Points' (10-50).
       - Archetypes: 'architect' (structure), 'plumber' (logic), 'janitor' (maintenance), 'bug_squasher' (fixes).
       - Performance Summary: Update the specific project narrative.

    You MUST return a STRICT, valid JSON object matching this exact schema:
    {{
      "pr_summary": {{
        "pr_overview": "1-2 sentence summary.",
        "changes": [
          {{
            "category": "Feature|Bugfix|Refactor|Performance|Security|Chore|Docs",
            "business_description": "Non-technical impact.",
            "technical_description": "Developer-focused impact."
          }}
        ],
        "risk_assessment": {{ "level": "Low|Medium|High", "reasoning": "..." }},
        "core_files_touched": ["file1", "file2"]
      }},
      "updated_profile": {{
        "github_handle": "handle",
        "overall_metrics": {{
          "total_prs_merged": "incremented count",
          "average_complexity_score": "running average",
          "documentation_habit_score": "running average",
          "review_resilience_score": "running average",
          "initial_quality_score": "running average"
        }},
        "archetype_distribution": {{ "architect": 0-100, "plumber": 0-100, "janitor": 0-100, "bug_squasher": 0-100 }},
        "skills": {{ "SkillName": {{ "xp": 0, "level": "Junior|Mid|Senior" }} }},
        "projects": {{
            "repo_name": {{
                "prs_contributed": "incremented count",
                "primary_role": "Calculated role",
                "performance_summary": "Evolved summary."
            }}
        }}
      }}
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
            full_prompt = f"{system_instruction}\n\n{prompt}"
            response = client.models.generate_content(
                model=model,
                contents=full_prompt,
                config={
                    'response_mime_type': 'application/json',
                    'temperature': 0.2
                }
            )
            raw_json_string = response.text

        return json.loads(raw_json_string)

    except json.JSONDecodeError:
        print("Failed to parse LLM response into valid JSON.")
        return {"error": "Invalid JSON returned by LLM", "raw_output": raw_json_string if 'raw_json_string' in locals() else "No output"}
    except Exception as e:
        print(f"Failed to get summary from {provider}: {e}")
        return {"error": str(e)}
