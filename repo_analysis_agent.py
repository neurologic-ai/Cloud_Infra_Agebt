import os
import json
import pathlib
import asyncio
import re
from pathlib import Path
from loguru import logger
from dotenv import load_dotenv
from typing import List, Optional
from openai import OpenAI

load_dotenv()

# -------------------------
# Config
# -------------------------
APP_NAME = "cloud_infra_app"
USER_ID = "user_123"
SESSION_ID = "session_01"
MODEL_NAME = "gpt-4o-mini"

BASE_RULES = """
You are CloudInfraAnalyzer.

Goal:
From a GitHub repository, detect evidence for these metrics:
- infra_as_code_automation
- security_posture
- reliability_availability
- cost_optimization
- monitoring_alerting
- backup_dr
- deployment_maturity

Also detect:
- cloud providers in use (AWS, Azure, GCP)
- best practices
- risks
- optimization opportunities

Scoring Logic:
cloud_maturity_score (0–5) based on:
Level 0: No cloud adoption; entirely on-premise infrastructure
Level 1: Basic cloud storage usage; experimental cloud services
Level 2: Partial migration to cloud; hybrid infrastructure without optimization
Level 3: Structured cloud adoption; automated scaling; basic monitoring
Level 4: Multi-cloud strategy; advanced automation; comprehensive monitoring
Level 5: Full cloud-native architecture; optimal resource utilization; advanced orchestration


Output JSON only, following this format:
{
  "cloud_providers": { "AWS": false, "Azure": true, "GCP": false },
  "metrics": {
    "infra_as_code_automation": "string",
    "security_posture": "string",
    "reliability_availability": "string",
    "cost_optimization": "string",
    "monitoring_alerting": "string",
    "backup_dr": "string",
    "deployment_maturity": "string"
  },
  "best_practices": [ "string", "string" ],
  "risks": [ "string", "string" ],
  "optimization_opportunities": [ "string", "string" ],
  "cloud_maturity_score": 0
}
Keep all values short and clear.
"""

client = OpenAI(api_key=os.getenv("OPENAI_KEY"))

# -------------------------
# Tools
# -------------------------
def list_files_tool(repo_path: str, patterns: Optional[List[str]]) -> List[str]:
    repo = Path(repo_path)
    if patterns:
        matched = []
        for pat in patterns:
            matched.extend([str(p.relative_to(repo)) for p in repo.rglob(pat) if p.is_file()])
        return sorted(set(matched))
    else:
        return [str(p.relative_to(repo)) for p in repo.rglob("*") if p.is_file()]

def read_file_tool(repo_path: str, file_path: str) -> str:
    abs_path = Path(repo_path) / file_path
    try:
        return abs_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return f"[Error reading file: {e}]"

# -------------------------
# JSON Cleaner
# -------------------------
def clean_json_output(s: str) -> str:
    """Remove markdown fences, trailing text, and extra braces."""
    if not s:
        return ""
    s = s.strip()
    # Remove code fences like ```json ... ```
    s = re.sub(r"^```(?:json)?", "", s, flags=re.IGNORECASE | re.MULTILINE).strip()
    s = re.sub(r"```$", "", s, flags=re.MULTILINE).strip()
    # Keep only content up to last closing brace
    if "}" in s:
        s = s[:s.rfind("}")+1]
    return s

# -------------------------
# Core Analysis
# -------------------------
async def run_agent_for_repo(repo_path: str) -> dict:
    abs_path = Path(repo_path).resolve()
    files = list_files_tool(str(abs_path), None)

    sampled_files = files[:20]
    file_contents = {}
    for f in sampled_files:
        file_contents[f] = read_file_tool(str(abs_path), f)[:2000]

    prompt = f"""
{BASE_RULES}

Repository path: {abs_path}
Files found: {len(files)}

Sample file names: {sampled_files}

Sample file contents:
{json.dumps(file_contents, indent=2)}
"""

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": BASE_RULES},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )

    raw_output = response.choices[0].message.content
    cleaned_output = clean_json_output(raw_output)

    try:
        return json.loads(cleaned_output)
    except json.JSONDecodeError:
        logger.warning(f"Retrying JSON parse for {repo_path}...")
        # Retry asking for clean JSON only
        retry_response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "Return only valid JSON for the given analysis, no extra text."},
                {"role": "user", "content": raw_output}
            ],
            temperature=0
        )
        retry_cleaned = clean_json_output(retry_response.choices[0].message.content)
        try:
            return json.loads(retry_cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"Could not parse JSON output for {repo_path}: {e}")
            return {}

# -------------------------
# Main
# -------------------------
async def main():
    base = pathlib.Path("cloned_repos")
    results = []
    for repo in base.iterdir():
        if repo.is_dir():
            logger.info(f"Analyzing {repo.name}")
            results.append(await run_agent_for_repo(str(repo)))
    pathlib.Path("openai_repos_analysis.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    logger.info(f"Saved {len(results)} repos to new_repos_analysis.json")

if __name__ == "__main__":
    asyncio.run(main())
