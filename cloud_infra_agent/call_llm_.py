# llm_caller.py
from typing import Any, Dict

from cloud_infra_agent.base_agents import BaseMicroAgent
from cloud_infra_agent.metrics import build_prompt
from loguru import logger
import traceback

def call_llm(agent: BaseMicroAgent, metric_id: str, task_input: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build the complete prompt for the given metric, call the LLM,
    and parse the JSON response.

    Args:
        agent: An initialized BaseMicroAgent (already has model + API key).
        metric_id: Metric id string (must exist in METRIC_PROMPTS).
        task_input: Dict payload (either raw input or compute_* output).

    Returns:
        Parsed JSON (dict). If LLM response could not be parsed, returns {}.
    """
    try:
        # Step 1: build prompt (this already embeds SYSTEM, EXAMPLEs, etc.)
        prompt = build_prompt(metric_id, task_input)

        # Step 2: run the call (we only pass the full prompt as user content)
        raw_response = agent._call_llm(prompt)

        # Step 3: parse into JSON dict
        return agent._parse_json_response(raw_response)
    except:
        logger.debug(traceback.format_exc())
        return {}
