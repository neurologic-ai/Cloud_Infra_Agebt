import json
import argparse
from pathlib import Path
from cloud_infra_agent.base_agents import BaseMicroAgent
from cloud_infra_agent.call_llm_ import call_llm
from cloud_infra_agent.config import CLOUD_INFRA_DATA_DIR, DEFAULT_METRICS, OPENAI_API_KEY
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Tuple
from cloud_infra_agent.metric_input_loader import load_metric_input



# def _resolve_compute_fn(metric_id: str):
#     return FN_MAP.get(metric_id)

AGENT = BaseMicroAgent(model="gpt-4o-mini", temperature=0.0,api_key=OPENAI_API_KEY)

def run_metric_once(
    metric_id: str,
    *,
    sample_name: str,
    base_dir: str = CLOUD_INFRA_DATA_DIR,
) -> Dict[str, Any]:
    """
    Loads input for a single metric, optionally computes a payload via a compute_* function,
    builds the prompt, calls the LLM, and returns the parsed LLM output (dict).
    """
    task_input = load_metric_input(sample_name, metric_id, base_dir=base_dir)

    # compute_fn = _resolve_compute_fn(metric_id)
    # payload = compute_fn(**task_input) if compute_fn else task_input
    payload = task_input

    # prompt = build_prompt(metric_id, payload)
    llm_output = call_llm(AGENT,metric_id,payload)  # expected to return a dict
    return {"metric_id": metric_id, "llm_output": llm_output}


def run_metrics_threaded(
    metric_ids: List[str] = DEFAULT_METRICS,
    *,
    sample_name: str,
    base_dir: str = CLOUD_INFRA_DATA_DIR,
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
        return run_metric_once(mid,sample_name=sample_name, base_dir=base_dir)

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        future_map = {ex.submit(_task, mid): mid for mid in metric_ids}
        for fut in as_completed(future_map):
            mid = future_map[fut]
            try:
                results.append(fut.result())
            except Exception as e:
                errors.append({"metric_id": mid, "error": str(e)})

    return results, errors


def run_cli(sample_name: str, max_workers=6):
    output_path = Path(f"cloud_infra_agent/Data/{sample_name}/output.json")
    output_path = Path(f"cloud_infra_agent/Data/{sample_name}/scaling_effectiveness.json")
    metric = [
        "scaling.effectiveness"
    ]

    results, errors = run_metrics_threaded(
        metric, sample_name=sample_name, max_workers=max_workers
    )

    # organize output
    output = {}
    for r in results:
        output[r["metric_id"]] = {"llm_output": r["llm_output"]}
    for e in errors:
        output[e["metric_id"]] = {"error": e["error"]}

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"✅ Results saved to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run cloud infra metrics.")
    parser.add_argument("sample_name", help="Name of the sample folder (e.g., Sample2)")
    parser.add_argument("--workers", type=int, default=6, help="Number of worker threads")
    args = parser.parse_args()

    run_cli(args.sample_name, max_workers=args.workers)
