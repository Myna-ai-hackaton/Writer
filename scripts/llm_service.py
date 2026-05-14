import json
from typing import Optional
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

    raise ValueError(
        "No AI API keys found. Please set OPENAI_API_KEY, OPENROUTER_API_KEY, or GEMINI_API_KEY."
    )


def summarize_pr(
    pr_metadata: dict,
    diff: str,
    existing_profile: Optional[dict] = None,
    feedback_data: Optional[dict] = None,
) -> dict:
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

    --- HARD ENGINEERING STATS ---
    Lines Added: {pr_metadata.get('stats', {}).get('additions')}
    Lines Deleted: {pr_metadata.get('stats', {}).get('deletions')}
    Files Changed: {pr_metadata.get('stats', {}).get('changed_files')}
    Test Coverage Impact: {json.dumps(pr_metadata.get('test_stats'))}
    PR Lifetime: Created at {pr_metadata.get('stats', {}).get('created_at')} -> Merged at {pr_metadata.get('stats', {}).get('merged_at')}

    --- CODE DIFF ---
    {diff}

    {developer_context}
    {feedback_context}
    --- INSTRUCTIONS ---
    1. Generate PR Summary: Categorize changes (Feature, Bugfix, etc.) and explain business vs. technical impact.
    2. Quantify Competency Growth: Based on the diff, process feedback, and hard stats, evolve the developer's profile.
       - Complexity Score: 1-10.
       - Documentation Score: 1-10.
       - Review Resilience: 1-10.
       - Initial Quality: 1-10 (Heavily penalize if Test-to-Code ratio is 0% for logical changes).
       - Proficiency (Skills): Identify tech used and award 'Competency Points'.
       - Archetypes:
         - 'architect': Weighted towards high deletions (refactoring) and pattern changes.
         - 'plumber': Weighted towards high additions in core logic files.
         - 'janitor': Weighted towards cleanup, docs, and test ratio.
         - 'bug_squasher': Focused on remediating defects.
       - Performance Summary: Update the specific project narrative. Use the 'Hard Engineering Stats' to justify your assessment (e.g., "Refined core logic while removing 200 lines of dead code").

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

    raw_json_string = ""
    try:
        if provider in ["openai", "openrouter"]:
            completion = client.chat.completions.create(  # type: ignore
                model=model,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
            )
            content = completion.choices[0].message.content
            if content is None:
                return {"error": "LLM returned empty content"}
            raw_json_string = content

        elif provider == "gemini":
            full_prompt = f"{system_instruction}\n\n{prompt}"
            response = client.models.generate_content(  # type: ignore
                model=model,
                contents=full_prompt,
                config={"response_mime_type": "application/json", "temperature": 0.2},
            )
            raw_json_string = response.text

        if not raw_json_string:
            return {"error": "No output received from LLM"}

        return json.loads(raw_json_string)

    except json.JSONDecodeError:
        print("Failed to parse LLM response into valid JSON.")
        return {
            "error": "Invalid JSON returned by LLM",
            "raw_output": (
                raw_json_string if "raw_json_string" in locals() else "No output"
            ),
        }
    except Exception as e:
        print(f"Failed to get summary from {provider}: {e}")
        return {"error": str(e)}
