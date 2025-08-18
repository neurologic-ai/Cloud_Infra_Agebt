import json
import os
import sys
from cloud_infra_agent.base_agents import BaseMicroAgent
from cloud_infra_agent.call_llm_ import call_llm
from cloud_infra_agent.compute_functions import (
    compute_inventory_snapshot,
    compute_tagging_coverage,
    compute_compute_utilization,
    compute_k8s_utilization,
    compute_autoscaling_effectiveness,
    compute_lb_performance,
    compute_storage_waste,
    compute_iac_coverage_and_drift,
    compute_availability_incident_rate,
    compute_monthly_cost_breakdown,
    compute_reserved_commit_coverage,
    compute_rightsizing_opportunities,
    compute_storage_lifecycle_optimization,
    compute_data_egress_costs,
    compute_cost_allocation_quality,
    compute_public_exposure,
    compute_encryption_compliance,
    compute_iam_risk_indicators,
    compute_vuln_patch_posture,
)
from cloud_infra_agent.metrics import build_prompt, METRIC_PROMPTS
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple
from dotenv import load_dotenv
from cloud_infra_agent.metric_input_loader import load_metric_input, DEFAULT_BASE_DIR
load_dotenv()
api_key = os.getenv("OPENAI_KEY")

FN_MAP = {
    # "tagging.coverage": compute_tagging_coverage,
    # "compute.utilization": compute_compute_utilization,
    # "k8s.utilization": compute_k8s_utilization,
    # "scaling.effectiveness": compute_autoscaling_effectiveness,
    # "lb.performance": compute_lb_performance,
    # "storage.efficiency": compute_storage_waste,
    # "iac.coverage_drift": compute_iac_coverage_and_drift,
    # "availability.incidents": compute_availability_incident_rate,
    # "cost.commit_coverage": compute_reserved_commit_coverage,
    # "cost.allocation_quality": compute_cost_allocation_quality,
    # "security.public_exposure": compute_public_exposure,
    # "security.encryption": compute_encryption_compliance,
    # "security.iam_risk": compute_iam_risk_indicators,
    # "security.vuln_patch": compute_vuln_patch_posture,
}

def _resolve_compute_fn(metric_id: str):
    return FN_MAP.get(metric_id)

AGENT = BaseMicroAgent(model="gpt-4o-mini", temperature=0.0,api_key=api_key)
def run_metric_once(
    map_file: str,
    metric_id: str,
    *,
    base_dir: str = DEFAULT_BASE_DIR,
) -> Dict[str, Any]:
    """
    Loads input for a single metric, optionally computes a payload via a compute_* function,
    builds the prompt, calls the LLM, and returns the parsed LLM output (dict).
    """
    task_input = load_metric_input(map_file, metric_id, base_dir=base_dir)

    compute_fn = _resolve_compute_fn(metric_id)
    # payload = compute_fn(**task_input) if compute_fn else task_input
    payload = task_input

    # prompt = build_prompt(metric_id, payload)
    llm_output = call_llm(AGENT,metric_id,payload)  # expected to return a dict
    return {"metric_id": metric_id, "llm_output": llm_output}


def run_metrics_threaded(
    map_file: str,
    metric_ids: List[str],
    *,
    base_dir: str = DEFAULT_BASE_DIR,
    max_workers: int = 6,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Runs a batch of metrics concurrently in a thread pool.

    Returns:
        (results, errors)
        results: [{ "metric_id": str, "llm_output": Any }, ...]
        errors:  [{ "metric_id": str, "error": str }, ...]
    """
    results: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    def _task(mid: str):
        return run_metric_once(map_file, mid, base_dir=base_dir)

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        future_map = {ex.submit(_task, mid): mid for mid in metric_ids}
        for fut in as_completed(future_map):
            mid = future_map[fut]
            try:
                results.append(fut.result())
            except Exception as e:
                errors.append({"metric_id": mid, "error": str(e)})

    return results, errors


# # --- Backward-compatible single-metric entry point (optional) ---
# def main(input_file: str, metric_id: str):
#     """
#     Legacy-style runner if you still want a single-metric CLI.
#     Note: 'input_file' kept for compatibility; we ignore it and load via map.json.
#     """
#     # If you want to keep using a direct file path, uncomment below and remove map usage.
#     # with open(input_file) as f:
#     #     task_input = json.load(f)
#     # compute_fn = _resolve_compute_fn(metric_id)
#     # payload = compute_fn(**task_input) if compute_fn else task_input

#     # Preferred: load from the map file and 'inputs/' directory
#     map_file = "map.json"  # adjust if you pass a different map via CLI
#     out = run_metric_once(map_file, metric_id)
#     print(json.dumps(out, indent=2))

if __name__ == "__main__":
    # Example: run a batch with threads
    MAP = "cloud_infra_agent/map.json"
    METRICS = [
        "tagging.coverage",
        "compute.utilization",
        "security.encryption",
        "scaling.effectiveness",
        "db.utilization",
        "lb.performance",
        "storage.efficiency",
        "iac.coverage_drift",
        "availability.incidents",
        "cost.idle_underutilized",
        "cost.commit_coverage",
        "cost.allocation_quality",
        "security.public_exposure",
        "security.encryption",
        "security.iam_risk",
        "security.vuln_patch"
    ]

    results, errors = run_metrics_threaded(MAP, METRICS, max_workers=6)

    # organize output by metric_id
    output = {}
    for r in results:
        output[r["metric_id"]] = {"llm_output": r["llm_output"]}
    for e in errors:
        output[e["metric_id"]] = {"error": e["error"]}

    # save to file
    with open("cloud_infra_agent/metrics_output.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print("✅ Results saved to metrics_output.json")
