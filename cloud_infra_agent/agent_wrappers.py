# Bridges the 16  metrics to  backbone.
# It either:
#  - uses "params" passed from the API, OR
#  - loads the sample JSON files via  existing loader (Data/SampleX/inputs/*.json)
# Then it calls  standard LLM flow: metrics.py + call_llm_.py

from typing import Dict, Any, Optional
import os
from pathlib import Path

from .metric_input_loader import load_metric_input
from .base_agents import BaseMicroAgent
from .call_llm_ import call_llm

# Map agent names ->  backbone metric IDs (as used in metrics.py/build_prompt)
NAME_TO_BACKBONE_ID = {
    # Level 0
    "score_tagging_coverage": "tagging.coverage",
    "score_compute_utilization": "compute.utilization",
    "score_k8s_utilization": "k8s.utilization",
    "score_db_utilization": "db.utilization",
    "score_storage_efficiency": "storage.efficiency",
    "score_lb_performance": "lb.performance",
    "score_availability_incidents": "availability.incidents",
    "score_commitment_coverage": "cost.commit_coverage",
    "score_iac_coverage_drift": "iac.coverage_drift",
    "score_security_encryption": "security.encryption",
    "score_security_iam": "security.iam_risk",
    "score_security_public_exposure": "security.public_exposure",
    "score_security_vuln_patch": "security.vuln_patch",
    # Level 1
    "score_cost_allocation_quality": "cost.allocation_quality",
    "score_cost_idle_underutilized": "cost.idle_underutilized",
    "score_autoscaling_effectiveness":"scaling.effectiveness",
}

def _agent() -> BaseMicroAgent:
    return BaseMicroAgent(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        temperature=0.0,
        api_key=os.getenv("OPENAI_API_KEY")
    )

def _resolve_task_input(metric_name: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
    params = (ctx or {}).get("params")
    if isinstance(params, dict) and params:
        return params

    sample = (ctx or {}).get("sample_name", "Sample2")
    backbone_id = NAME_TO_BACKBONE_ID[metric_name]

    # ✅ Pass the Data ROOT; the loader will append Sample/inputs internally
    data_root = Path(__file__).resolve().parent / "Data"
    return load_metric_input(sample_name=sample, metric_id=backbone_id, base_dir=data_root)


def _run(metric_name: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
    backbone_id = NAME_TO_BACKBONE_ID[metric_name]
    task_input = _resolve_task_input(metric_name, ctx)
    out = call_llm(_agent(), backbone_id, task_input) or {}
    # ensure metric_id is set for consistency
    out.setdefault("metric_id", metric_name)
    return out

# ---- export the 16 functions the orchestrator calls ----
def score_tagging_coverage(input: Dict[str, Any]) -> Dict[str, Any]:
    return _run("score_tagging_coverage", input)

def score_compute_utilization(input: Dict[str, Any]) -> Dict[str, Any]:      
    return _run("score_compute_utilization", input)

def score_k8s_utilization(input: Dict[str, Any]) -> Dict[str, Any]:          
    return _run("score_k8s_utilization", input)

def score_db_utilization(input: Dict[str, Any]) -> Dict[str, Any]:           
    return _run("score_db_utilization", input)

def score_storage_efficiency(input: Dict[str, Any]) -> Dict[str, Any]:
    return _run("score_storage_efficiency", input)

def score_lb_performance(input: Dict[str, Any]) -> Dict[str, Any]:           
    return _run("score_lb_performance", input)

def score_availability_incidents(input: Dict[str, Any]) -> Dict[str, Any]:   
    return _run("score_availability_incidents", input)

def score_commitment_coverage(input: Dict[str, Any]) -> Dict[str, Any]:      
    return _run("score_commitment_coverage", input)

def score_iac_coverage_drift(input: Dict[str, Any]) -> Dict[str, Any]:       
    return _run("score_iac_coverage_drift", input)

def score_security_encryption(input: Dict[str, Any]) -> Dict[str, Any]:      
    return _run("score_security_encryption", input)

def score_security_iam(input: Dict[str, Any]) -> Dict[str, Any]:             
    return _run("score_security_iam", input)

def score_security_public_exposure(input: Dict[str, Any]) -> Dict[str, Any]: 
    return _run("score_security_public_exposure", input)

def score_security_vuln_patch(input: Dict[str, Any]) -> Dict[str, Any]:      
    return _run("score_security_vuln_patch", input)

def score_cost_allocation_quality(input: Dict[str, Any]) -> Dict[str, Any]:  
    return _run("score_cost_allocation_quality", input)

def score_cost_idle_underutilized(input: Dict[str, Any]) -> Dict[str, Any]:  
    return _run("score_cost_idle_underutilized", input)

def score_autoscaling_effectiveness(input: Dict[str, Any]) -> Dict[str, Any]:
    return _run("score_autoscaling_effectiveness", input)
