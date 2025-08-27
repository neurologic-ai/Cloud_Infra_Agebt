from typing import List, Dict

# Level 0 (parallel)
LEVEL0 = [
    "score_tagging_coverage",
    "score_compute_utilization",
    "score_k8s_utilization",
    "score_db_utilization",
    "score_storage_efficiency",
    "score_lb_performance",
    "score_availability_incidents",
    "score_commitment_coverage",
    "score_iac_coverage_drift",
    "score_security_encryption",
    "score_security_iam",
    "score_security_public_exposure",
    "score_security_vuln_patch",
]

# Level 1 (depends on Level 0)
LEVEL1_DEPS: Dict[str, List[str]] = {
    "score_cost_allocation_quality": ["score_tagging_coverage"],
    "score_cost_idle_underutilized": ["score_compute_utilization", "score_k8s_utilization"],
    "score_autoscaling_effectiveness": ["score_compute_utilization"],
}

CATEGORIES: Dict[str, Dict] = {
    "cost": {
        "weight": 0.35,
        "metrics": {
            "score_commitment_coverage":       0.34,
            "score_cost_allocation_quality":   0.33,
            "score_cost_idle_underutilized":   0.33,
        }
    },
    "efficiency": {
        "weight": 0.25,
        "metrics": {
            "score_compute_utilization":       0.22,
            "score_k8s_utilization":           0.22,
            "score_db_utilization":            0.18,
            "score_storage_efficiency":        0.18,
            "score_autoscaling_effectiveness": 0.20,
        }
    },
    "reliability": {
        "weight": 0.15,
        "metrics": {
            "score_availability_incidents":    0.60,
            "score_lb_performance":            0.40,
        }
    },
    "security": {
        "weight": 0.25,
        "metrics": {
            "score_security_encryption":       0.25,
            "score_security_iam":              0.25,
            "score_security_public_exposure":  0.25,
            "score_security_vuln_patch":       0.25,
        }
    },
}
