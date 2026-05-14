# llm_service.py

import json
from typing import Optional, Dict, Any
from openai import OpenAI
from config import OPENROUTER_API_KEY


client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

MODEL = "google/gemini-2.0-flash-001"
ALPHA = 0.18


# =========================
# EXISTING: PR SUMMARY
# =========================

def summarize_pr(pr_metadata: dict, diff: str) -> dict:

    system_instruction = (
        "You are a Staff Software Engineer and Product Manager. "
        "Summarize PRs into structured business + technical insights."
    )

    prompt = f"""
--- PR METADATA ---
Title: {pr_metadata.get('title')}
Author: {pr_metadata.get('author')}
Description: {pr_metadata.get('body')}

--- CODE DIFF ---
{diff}

--- OUTPUT JSON ---
{{
  "pr_overview": "string",
  "changes": [
    {{
      "category": "Feature | Bugfix | Refactor | Performance | Security | Chore | Docs",
      "business_description": "string",
      "technical_description": "string"
    }}
  ],
  "risk_assessment": {{
    "level": "Low | Medium | High",
    "reasoning": "string"
  }},
  "core_files_touched": []
}}
"""

    completion = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )

    return json.loads(completion.choices[0].message.content)


# =========================
# PROFILE SYSTEM
# =========================

def init_profile():
    return {
        "quality_score": 50,
        "ownership_score": 50,
        "debugging_score": 50,
        "testing_score": 50,
        "architecture_score": 50,
        "backend_score": 50,
        "frontend_score": 50,
        "code_fail_rate": 0,
        "rework_rate": 0,
        "overall_score": 50,
        "pr_count": 0,
        "trend": "Stable",
        "confidence": {"overall": "Low", "reason": "No data"},
        "last_signals": [],
        "latest_pr": {}
    }


def ewma(old, new):
    return round((1 - ALPHA) * old + ALPHA * new, 2)


def compute_overall(profile):
    return round(
        0.22 * profile["quality_score"] +
        0.16 * profile["ownership_score"] +
        0.14 * profile["debugging_score"] +
        0.14 * profile["testing_score"] +
        0.12 * profile["architecture_score"] +
        0.11 * (100 - profile["code_fail_rate"]) +
        0.11 * (100 - profile["rework_rate"]),
        2
    )


def confidence(profile):
    n = profile["pr_count"]
    if n < 3:
        return {"overall": "Low", "reason": "Low data"}
    if n < 10:
        return {"overall": "Medium", "reason": "Moderate data"}
    return {"overall": "High", "reason": "Strong history"}


# =========================
# LLM EVALUATION
# =========================

def evaluate_pr_with_llm(pr_metadata, diff):

    prompt = f"""
Analyze this PR and return JSON ONLY.

Title: {pr_metadata.get('title')}
Description: {pr_metadata.get('body')}
Commits: {pr_metadata.get('commits_count')}
Comments: {pr_metadata.get('review_comments_count')}
Files: {pr_metadata.get('changed_files_count')}

Diff:
{diff}

{{
  "pr_profile": {{
    "change_type": "Feature | Bugfix | Refactor | Mixed",
    "scope": "Small | Medium | Large",
    "risk_level": "Low | Medium | High"
  }},
  "iteration_analysis": {{
    "estimated_rework_rounds": 1,
    "rework_severity": "Low | Medium | High",
    "first_pass_quality": "Low | Medium | High"
  }},
  "quality_analysis": {{
    "design_quality_score": 1,
    "test_signal": "Low | Medium | High"
  }},
  "skill_signals": {{
    "backend": 50,
    "frontend": 50,
    "testing": 50,
    "architecture": 50,
    "debugging": 50,
    "ownership": 50
  }},
  "developer_update": {{
    "short_note": "string"
  }}
}}
"""

    completion = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.2,
    )

    return json.loads(completion.choices[0].message.content)


# =========================
# MAIN ENTRY
# =========================

def evaluate_pr_and_update_profile(
    pr_metadata: dict,
    diff: str,
    existing_profile: Optional[dict] = None
) -> Dict[str, Any]:

    profile = existing_profile.copy() if existing_profile else init_profile()
    prev_score = profile["overall_score"]

    result = evaluate_pr_with_llm(pr_metadata, diff)

    skill = result["skill_signals"]
    quality = result["quality_analysis"]
    iteration = result["iteration_analysis"]
    prp = result["pr_profile"]

    # Update
    profile["quality_score"] = ewma(profile["quality_score"], quality["design_quality_score"] * 10)
    profile["testing_score"] = ewma(profile["testing_score"], skill["testing"])
    profile["debugging_score"] = ewma(profile["debugging_score"], skill["debugging"])
    profile["architecture_score"] = ewma(profile["architecture_score"], skill["architecture"])
    profile["backend_score"] = ewma(profile["backend_score"], skill["backend"])
    profile["frontend_score"] = ewma(profile["frontend_score"], skill["frontend"])
    profile["ownership_score"] = ewma(profile["ownership_score"], skill["ownership"])

    profile["code_fail_rate"] = ewma(profile["code_fail_rate"],
        {"High": 0, "Medium": 50, "Low": 100}[quality["test_signal"]])

    profile["rework_rate"] = ewma(profile["rework_rate"],
        {"Low": 0, "Medium": 50, "High": 100}[iteration["rework_severity"]])

    profile["pr_count"] += 1
    profile["last_signals"] = (profile["last_signals"] + [result])[-10:]

    profile["overall_score"] = compute_overall(profile)

    # Trend
    delta = profile["overall_score"] - prev_score
    profile["trend"] = "Improving" if delta > 2 else "Declining" if delta < -2 else "Stable"

    profile["confidence"] = confidence(profile)

    profile["latest_pr"] = {
        "type": prp["change_type"],
        "risk": prp["risk_level"],
        "scope": prp["scope"],
        "quality": iteration["first_pass_quality"],
        "rework_rounds": iteration["estimated_rework_rounds"]
    }

    return {
        "profile": profile,
        "analysis": result
    }