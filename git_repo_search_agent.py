import os
import json
import re
import asyncio
import urllib.parse
from datetime import datetime, timezone
import requests
from dotenv import load_dotenv

from google.adk.sessions import InMemorySessionService
from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.runners import Runner
from google.genai import types
from google.adk.tools import google_search, FunctionTool
from loguru import logger

# =========================================================
# Config
# =========================================================
load_dotenv()

APP_NAME = "repo_search_app"
USER_ID = "user_123"
SESSION_ID = "session_01"

# =========================================================
# Utilities
# =========================================================
def strip_code_fences(text: str) -> str:
    """
    Remove ```json ... ``` or ``` ... ``` fences if the model added them.
    """
    text = text.strip()
    if text.startswith("```"):
        # remove first fence
        text = re.sub(r"^```(?:json|JSON)?\s*", "", text, flags=re.IGNORECASE)
        # remove trailing fence
        text = re.sub(r"\s*```$", "", text)
    return text.strip()

def safe_json_array(text: str):
    """
    Try very hard to parse a JSON array from the text.
    1) Strip code fences
    2) If it's a valid array -> return it
    3) Otherwise, extract the first top-level JSON array by bracket matching
    """
    raw = strip_code_fences(text)
    # quick path
    try:
        obj = json.loads(raw)
        if isinstance(obj, list):
            return obj
    except Exception:
        pass

    # bracket-scan for the first top-level array […]
    start = raw.find("[")
    if start == -1:
        raise ValueError("No JSON array start '[' found in text")

    depth = 0
    for i in range(start, len(raw)):
        ch = raw[i]
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                candidate = raw[start:i + 1]
                try:
                    return json.loads(candidate)
                except Exception:
                    continue
    # if we reach here, parsing failed
    raise ValueError("Could not extract a valid JSON array from model output")

def iso_to_dt(iso: str):
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except Exception:
        return None

def compute_activity_level(stars: int | None, last_update_iso: str | None) -> str:
    stars = stars or 0
    dt = iso_to_dt(last_update_iso) if last_update_iso else None
    months_recent = False
    if dt:
        months_recent = (datetime.now(timezone.utc) - dt).days <= 180
    if stars >= 5000 and months_recent:
        return "High"
    if stars >= 1000 and (months_recent or stars >= 3000):
        return "Medium"
    return "Low"

# =========================================================
# Metadata fetch tool (GitHub + GitLab)
# =========================================================
def fetch_repo_metadata(repo_url: str) -> dict:
    """
    Fetch metadata (description, stars, forks, last update, topics) from
    GitHub or GitLab. Requires GITHUB_TOKEN/GITLAB_TOKEN for higher rate limits
    but works without (limited).
    """
    try:
        if "github.com" in repo_url:
            parts = repo_url.rstrip("/").split("/")
            if len(parts) < 5:
                return {"error": "Invalid GitHub repo URL"}
            owner, repo = parts[-2], parts[-1]

            api_url = f"https://api.github.com/repos/{owner}/{repo}"
            headers = {"Accept": "application/vnd.github+json"}
            token = os.getenv("GITHUB_TOKEN")
            if token:
                headers["Authorization"] = f"Bearer {token}"
            r = requests.get(api_url, headers=headers, timeout=20)
            if r.status_code != 200:
                return {"error": f"GitHub API error {r.status_code}"}
            data = r.json()

            # topics: separate endpoint requires preview, but many clients include it
            topics = data.get("topics") or []
            return {
                "platform": "GitHub",
                "description": data.get("description"),
                "stars": data.get("stargazers_count"),
                "forks": data.get("forks_count"),
                "last_update": data.get("pushed_at"),
                "topics": topics,
            }

        if "gitlab.com" in repo_url:
            # e.g. https://gitlab.com/gitlab-org/gitlab
            path_parts = repo_url.rstrip("/").split("/")
            if len(path_parts) < 5:
                return {"error": "Invalid GitLab repo URL"}
            path = "/".join(path_parts[-2:])
            encoded_path = urllib.parse.quote_plus(path)

            api_url = f"https://gitlab.com/api/v4/projects/{encoded_path}"
            headers = {"Accept": "application/json"}
            token = os.getenv("GITLAB_TOKEN")
            if token:
                headers["PRIVATE-TOKEN"] = token
            r = requests.get(api_url, headers=headers, timeout=20)
            if r.status_code != 200:
                return {"error": f"GitLab API error {r.status_code}"}
            data = r.json()
            # topics -> "tag_list"
            return {
                "platform": "GitLab",
                "description": data.get("description"),
                "stars": data.get("star_count"),
                "forks": data.get("forks_count"),
                "last_update": data.get("last_activity_at"),
                "topics": data.get("tag_list") or [],
            }

        return {"error": "Only GitHub and GitLab repos supported"}

    except Exception as e:
        return {"error": str(e)}

fetch_repo_metadata_tool = FunctionTool(fetch_repo_metadata)

# =========================================================
# Agents
# =========================================================
search_agent = LlmAgent(
    name="search_agent",
    model="gemini-2.0-flash",
    tools=[google_search],
    instruction="""
You are a smart research agent.

GOAL
- Find high-quality, active, relevant repositories from GitHub AND GitLab for the user's query.

STRATEGY
1) Reason about the query and derive 2–4 strong keyword variations.
2) Use the google_search tool for those variations.
3) Normalize/merge results.
4) Keep ONLY repository root pages on github.com or gitlab.com (exclude issues, pulls, discussions, docs, wiki, releases, gists).
5) Return STRICT JSON (no text outside JSON): an array of objects with keys: title, url.
   Example:
   [
     {"title": "scikit-learn", "url": "https://github.com/scikit-learn/scikit-learn"},
     {"title": "gitlab", "url": "https://gitlab.com/gitlab-org/gitlab"}
   ]
""",
)

analysis_agent = LlmAgent(
    name="analysis_agent",
    model="gemini-2.0-flash",
    tools=[fetch_repo_metadata_tool],
    instruction="""
You are an expert open-source analyst.

INPUT
- A JSON array: [{ "title": string, "url": string }]

TOOLS
- You can call fetch_repo_metadata(url) for each repo to get:
  { platform, description, stars, forks, last_update, topics }

OUTPUT (STRICT JSON ONLY — NO prose, NO code fences)
{
      "title": "repo name",
      "url": "https://...",
      "research_summary": "Brief description of purpose, features, use cases",
      "activity_level": "High | Medium | Low (based on stars, forks, commits)",
      "relevance_score": "1-10 (based on match to query)",
      "key_features": "Main highlights"
    }
    Always return valid JSON. No explanations outside JSON.

RULES
- Always call fetch_repo_metadata(url) before scoring.
- If metadata fetch fails, set platform to "GitHub" or "GitLab" based on URL, set missing fields to null, and continue.
- Sort results by relevance_score descending BEFORE returning.
- Output must be ONLY a JSON array (no surrounding text).
""",
)

seq_agent = SequentialAgent(
    name="github_gitlab_repo_search_agent",
    sub_agents=[search_agent, analysis_agent],
)

# =========================================================
# Runner (fully async; no sync calls)
# =========================================================
async def run_agent(query: str) -> str:
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID
    )
    runner = Runner(
        app_name=APP_NAME,
        agent=seq_agent,
        session_service=session_service,
    )

    content = types.Content(role="user", parts=[types.Part(text=query)])

    final_text = ""
    async for event in runner.run_async(
        user_id=USER_ID, session_id=SESSION_ID, new_message=content
    ):
        # Capture last final response, but DO NOT break—consume stream to completion
        if event.is_final_response():
            final_text = event.content.parts[0].text

    return final_text

# =========================================================
# Save functions
# =========================================================
def save_repo_analysis(agent_output_text: str,
                       full_file: str = "repos_full.json",
                       urls_file: str = "repos.json"):
    try:
        repos = safe_json_array(agent_output_text)
    except Exception as e:
        logger.error("Agent output not valid JSON. Raw output saved to repos_raw.txt")
        with open("repos_raw.txt", "w", encoding="utf-8") as f:
            f.write(agent_output_text)
        raise

    # Optional: ensure relevance_score is numeric and sort again here
    def score(x):
        try:
            return int(str(x.get("relevance_score", "0")).strip())
        except Exception:
            return 0

    repos = sorted(repos, key=score, reverse=True)

    with open(full_file, "w", encoding="utf-8") as f:
        json.dump(repos, f, indent=2, ensure_ascii=False)

    urls = [r["url"] for r in repos if isinstance(r, dict) and r.get("url")]
    with open(urls_file, "w", encoding="utf-8") as f:
        json.dump(urls, f, indent=2, ensure_ascii=False)

    print(f"💾 Saved {len(repos)} repos to {full_file} and {len(urls)} URLs to {urls_file}")
    return repos

# =========================================================
# Main
# =========================================================
async def main():
    # Example query; customize as needed
    query = "most relevant machine learning repositories on GitHub and GitLab"
    final_text = await run_agent(query)
    print("=== RAW AGENT OUTPUT (truncated) ===")
    print(final_text[:1000] + ("..." if len(final_text) > 1000 else ""))

    # Save files
    repos = save_repo_analysis(final_text)

if __name__ == "__main__":
    asyncio.run(main())
