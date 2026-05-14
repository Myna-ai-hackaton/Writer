import json
import re
from typing import Optional, Any
from datetime import datetime
from openai import OpenAI
from google import genai
from config import OPENAI_API_KEY, OPENROUTER_API_KEY, GEMINI_API_KEY

ALPHA = 0.18  # The learning rate for rolling metrics (EWMA)


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
        return client, "openrouter", "google/gemini-2.5-flash"

    if GEMINI_API_KEY:
        print("Using Google Gemini (Direct) as the LLM provider.")
        client = genai.Client(api_key=GEMINI_API_KEY)
        return client, "gemini", "gemini-2.5-flash"

    raise ValueError(
        "No AI API keys found. Please set OPENAI_API_KEY, OPENROUTER_API_KEY, or GEMINI_API_KEY."
    )


def clean_json_response(raw_text: str) -> str:
    """Removes markdown code blocks and whitespace from LLM response."""
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)
    return cleaned.strip()


def summarize_pr(
    full_context: dict,
    existing_profile: Optional[dict] = None,
) -> dict:
    """
    Acts as the 'Sensor'. Sends consolidated PR context to the LLM to extract
    raw engineering signals (scores, skills, focus) and generate technical release notes.
    """
    client, provider, model = get_llm_client()
    client_any: Any = client
    meta = full_context["metadata"]

    system_instruction = (
        "You are an Elite Engineering Mentor and a Technical Auditor. "
        "Extract raw engineering signals from the PR. DO NOT perform any math or averages. "
        "Return a valid JSON object."
    )

    developer_context = ""
    if existing_profile:
        developer_context = f"--- DEVELOPER CONTEXT ---\n{json.dumps(existing_profile.get('projects', {}), indent=2)}"

    prompt = f"""
    Analyze this PR and output JSON.

    --- PR METADATA ---
    Title: {meta['title']}
    Author: {meta['author']}
    Repo: {meta['repo']}
    Status: {meta['status']}
    Description: {meta['body']}

    --- STATS & FEEDBACK ---
    {json.dumps(full_context['stats'])}
    {json.dumps(full_context['test_stats'])}
    {json.dumps(full_context['feedback_loop'])}

    --- CODE DIFF ---
    {full_context['diff']}

    {developer_context}

    --- INSTRUCTIONS ---
    1. Extract Signals (1-10): complexity, documentation, resilience, quality.
    2. Identify Archetype: architect (structure), plumber (logic), janitor (maintenance), bug_squasher (fixes).
    3. Identify: skills_used[].
    4. Generate Summary: Categorized release notes (business vs. technical impact).

    OUTPUT SCHEMA (Strict JSON):
    {{
      "signals": {{
        "complexity": int,
        "documentation": int,
        "resilience": int,
        "quality": int,
        "primary_archetype": "architect|plumber|janitor|bug_squasher",
        "skills_used": ["string"]
      }},
      "pr_summary": {{
        "pr_overview": "string",
        "changes": [{{ "category": "string", "impact": "string" }}],
        "risk_assessment": {{ "level": "Low|Medium|High", "reasoning": "string" }},
        "core_files_touched": ["string"]
      }}
    }}
    """

    raw_json_string = ""
    try:
        if provider in ["openai", "openrouter"]:
            completion = client_any.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
            )
            raw_json_string = completion.choices[0].message.content or ""

        elif provider == "gemini":
            response = client_any.models.generate_content(
                model=model,
                contents=f"{system_instruction}\n\n{prompt}",
                config={"response_mime_type": "application/json", "temperature": 0.2},
            )
            raw_json_string = response.text

        if not raw_json_string:
            return {"error": "No output received from LLM"}

        return json.loads(clean_json_response(raw_json_string))

    except Exception as e:
        print(f"LLM Error: {e}")
        return {"error": str(e), "raw_output": raw_json_string}


def evaluate_pr_and_update_profile(
    llm_signals: dict,
    full_context: dict,
    profile: Optional[dict] = None
) -> dict:
    """
    Acts as the 'Brain'. Uses deterministic Python logic to update the developer profile
    based on raw signals from the LLM and hard stats from GitHub.
    """
    meta = full_context["metadata"]
    status = meta["status"]
    repo_name = meta["repo"]
    project_name = repo_name.split("/")[-1]

    if not profile:
        profile = {
            "github_handle": meta["author"],
            "python_managed_state": {
                "activity_counters": {"merged": 0, "denied": 0},
                "rolling_metrics": {"complexity": 5.0, "docs": 5.0, "resilience": 5.0, "quality": 5.0},
                "temporal_history": [],
                "archetype_distribution": {"architect": 0, "plumber": 0, "janitor": 0, "bug_squasher": 0},
                "skills_matrix": {}
            },
            "projects": {}
        }

    p_state = profile.setdefault("python_managed_state", {
        "activity_counters": {"merged": 0, "denied": 0},
        "rolling_metrics": {"complexity": 5.0, "docs": 5.0, "resilience": 5.0, "quality": 5.0},
        "temporal_history": [],
        "archetype_distribution": {"architect": 0, "plumber": 0, "janitor": 0, "bug_squasher": 0},
        "skills_matrix": {}
    })

    if status != "open":
        signals = llm_signals.get("signals", {})
        
        metric_map = [
            ("complexity", "complexity"),
            ("docs", "documentation"),
            ("resilience", "resilience"),
            ("quality", "quality")
        ]
        for p_key, s_key in metric_map:
            old_val = float(p_state["rolling_metrics"].get(p_key, 5.0))
            try:
                new_signal = float(signals.get(s_key, 5))
            except (ValueError, TypeError):
                new_signal = 5.0
            p_state["rolling_metrics"][p_key] = round((1 - ALPHA) * old_val + ALPHA * new_signal, 2)

        if status == "accepted_merged":
            p_state["activity_counters"]["merged"] += 1
        elif status == "denied_abandoned":
            p_state["activity_counters"]["denied"] += 1

        p_state["temporal_history"].append({
            "date": datetime.now().strftime("%Y-%m-%d"),
            "quality": p_state["rolling_metrics"]["quality"],
            "pr_number": full_context.get("pr_number")
        })
        p_state["temporal_history"] = p_state["temporal_history"][-20:]

        archetype = str(signals.get("primary_archetype", "plumber"))
        if archetype in p_state["archetype_distribution"]:
            p_state["archetype_distribution"][archetype] += 1
        
        for skill in signals.get("skills_used", []):
            if skill not in p_state["skills_matrix"]:
                p_state["skills_matrix"][skill] = {"xp": 0, "level": "Junior"}
            
            p_state["skills_matrix"][skill]["xp"] += 1
            xp = p_state["skills_matrix"][skill]["xp"]
            if xp > 15: p_state["skills_matrix"][skill]["level"] = "Senior"
            elif xp > 5: p_state["skills_matrix"][skill]["level"] = "Mid"

        if project_name not in profile["projects"]:
            profile["projects"][project_name] = {"prs_analyzed": 0, "primary_archetype": archetype}
        
        profile["projects"][project_name]["prs_analyzed"] += 1
        profile["projects"][project_name]["last_contribution"] = datetime.now().strftime("%Y-%m-%d")

    return profile
