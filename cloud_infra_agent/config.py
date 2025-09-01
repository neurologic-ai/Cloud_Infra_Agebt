import os
from dotenv import load_dotenv

# from cloud_infra_agent.compute_functions import (
#     compute_inventory_snapshot,
#     compute_tagging_coverage,
#     compute_compute_utilization,
#     compute_k8s_utilization,
#     compute_autoscaling_effectiveness,
#     compute_lb_performance,
#     compute_storage_waste,
#     compute_iac_coverage_and_drift,
#     compute_availability_incident_rate,
#     compute_monthly_cost_breakdown,
#     compute_reserved_commit_coverage,
#     compute_rightsizing_opportunities,
#     compute_storage_lifecycle_optimization,
#     compute_data_egress_costs,
#     compute_cost_allocation_quality,
#     compute_public_exposure,
#     compute_encryption_compliance,
#     compute_iam_risk_indicators,
#     compute_vuln_patch_posture,
# )


load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CLOUD_INFRA_DATA_DIR = os.getenv("CLOUD_INFRA_DATA_DIR")

# FN_MAP = {
#     "tagging.coverage": compute_tagging_coverage,
#     "compute.utilization": compute_compute_utilization,
#     "k8s.utilization": compute_k8s_utilization,
#     "scaling.effectiveness": compute_autoscaling_effectiveness,
#     "lb.performance": compute_lb_performance,
#     "storage.efficiency": compute_storage_waste,
#     "iac.coverage_drift": compute_iac_coverage_and_drift,
#     "availability.incidents": compute_availability_incident_rate,
#     "cost.commit_coverage": compute_reserved_commit_coverage,
#     "cost.allocation_quality": compute_cost_allocation_quality,
#     "security.public_exposure": compute_public_exposure,
#     "security.encryption": compute_encryption_compliance,
#     "security.iam_risk": compute_iam_risk_indicators,
#     "security.vuln_patch": compute_vuln_patch_posture,
# }

DEFAULT_METRICS = [
    "tagging.coverage",
    "compute.utilization",
    "k8s.utilization",
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
    "security.vuln_patch",
]

Input_File_For_Metric_map={
  "tagging.coverage": "tagging_coverage.json",
  "compute.utilization": "compute_utilization.json",
  "k8s.utilization": "k8s_utilization.json",
  "scaling.effectiveness": "scaling_effectiveness.json",
  "db.utilization": "db_utilization.json",
  "lb.performance": "lb_performance.json",
  "storage.efficiency": "storage_efficiency.json",
  "iac.coverage_drift": "iac_coverage_drift.json",
  "availability.incidents": "availability_incidents.json",
  "cost.idle_underutilized": "cost_idle_underutilized.json",
  "cost.commit_coverage": "cost_commit_coverage.json",
  "cost.allocation_quality": "cost_allocation_quality.json",
  "security.public_exposure": "security_public_exposure.json",
  "security.encryption": "security_encryption.json",
  "security.iam_risk": "security_iam_risk.json",
  "security.vuln_patch": "security_vuln_patch.json"
}