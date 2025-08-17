from dataclasses import dataclass
from typing import Any, Dict, List

from cloud_infra_agent.compute_functions import (
    compute_autoscaling_effectiveness,
    compute_availability_incident_rate,
    compute_change_velocity_iac,
    compute_compute_utilization,
    compute_cost_allocation_quality,
    compute_cspm_findings_summary,
    compute_data_egress_costs,
    compute_encryption_compliance,
    compute_gpu_cost_efficiency,
    compute_iac_coverage_and_drift,
    compute_iam_risk_indicators,
    compute_inventory_snapshot,
    compute_k8s_utilization,
    compute_key_secret_rotation,
    compute_lb_performance,
    compute_monthly_cost_breakdown,
    compute_public_exposure,
    compute_reserved_commit_coverage,
    compute_rightsizing_opportunities,
    compute_storage_lifecycle_optimization,
    compute_storage_waste,
    compute_tagging_coverage,
    compute_vuln_patch_posture,
)


@dataclass
class Inputs:
    inventory_adapters: Dict[str, Any]
    resources: List[Dict[str, Any]]
    compute_instances: List[Dict[str, Any]]
    k8s_rows: Dict[str, Any]
    ts_metrics: List[Dict[str, Any]]
    scale_events: List[Dict[str, Any]]
    db_metrics: List[Dict[str, Any]]
    lb_metrics: List[Dict[str, Any]]
    block_volumes: List[Dict[str, Any]]
    snapshots: List[Dict[str, Any]]
    objects: List[Dict[str, Any]]
    lifecycle_rules: List[Dict[str, Any]]
    iac_index: Dict[str, Any]
    policy_findings: List[Dict[str, Any]]
    incidents: List[Dict[str, Any]]
    slo_breaches: List[Dict[str, Any]]
    cost_rows: List[Dict[str, Any]]
    commit_inventory: List[Dict[str, Any]]
    usage: List[Dict[str, Any]]
    rightsizing: List[Dict[str, Any]]
    egress_costs: List[Dict[str, Any]]
    net_metrics: List[Dict[str, Any]]
    network_policies: List[Dict[str, Any]]
    storage_acls: List[Dict[str, Any]]
    security_resources_crypto_tls: List[Dict[str, Any]]
    iam_dump: Dict[str, Any]
    vuln_findings: List[Dict[str, Any]]
    patch_status: Dict[str, Any]
    cspm_findings: List[Dict[str, Any]]
    kms_keys: List[Dict[str, Any]]
    secrets: List[Dict[str, Any]]
    gpu_metrics: List[Dict[str, Any]]
    gpu_cost_rows: List[Dict[str, Any]]
    iac_runs: List[Dict[str, Any]]


class CloudEvalAgent:
    def run_all(
        self,
        inputs: Inputs,
        since: int = 1690848000,
        until: int = 1693440000,
    ) -> List[Dict[str, Any]]:
        """Run all cloud evaluation computations and return results."""

        results = []

        results.append(
            compute_inventory_snapshot(inputs.inventory_adapters, since, until)
        )
        results.append(compute_tagging_coverage(inputs.resources))
        results.append(compute_compute_utilization(inputs.compute_instances))
        results.append(compute_k8s_utilization(inputs.k8s_rows))
        results.append(
            compute_autoscaling_effectiveness(inputs.ts_metrics, inputs.scale_events)
        )
        results.append(compute_lb_performance(inputs.lb_metrics))
        results.append(
            compute_storage_waste(
                inputs.block_volumes,
                inputs.snapshots,
                inputs.objects,
            )
        )
        results.append(
            compute_iac_coverage_and_drift(
                inputs.resources,
                inputs.iac_index,
                inputs.policy_findings,
            )
        )
        results.append(
            compute_availability_incident_rate(inputs.incidents, inputs.slo_breaches)
        )

        results.append(compute_monthly_cost_breakdown(inputs.cost_rows))
        results.append(
            compute_reserved_commit_coverage(inputs.commit_inventory, inputs.usage)
        )
        results.append(compute_rightsizing_opportunities(inputs.rightsizing))
        results.append(
            compute_storage_lifecycle_optimization(
                inputs.objects,
                inputs.lifecycle_rules,
            )
        )
        # Use egress_costs rows for by_type; net_metrics for spikes
        results.append(
            compute_data_egress_costs(inputs.egress_costs, inputs.net_metrics)
        )
        results.append(compute_cost_allocation_quality(inputs.cost_rows))

        results.append(
            compute_public_exposure(
                inputs.resources,
                inputs.network_policies,
                inputs.storage_acls,
            )
        )
        results.append(compute_encryption_compliance(inputs.security_resources_crypto_tls))
        results.append(compute_iam_risk_indicators(inputs.iam_dump))
        results.append(
            compute_vuln_patch_posture(inputs.vuln_findings, inputs.patch_status)
        )
        results.append(compute_cspm_findings_summary(inputs.cspm_findings))
        results.append(compute_key_secret_rotation(inputs.kms_keys, inputs.secrets))

        results.append(
            compute_gpu_cost_efficiency(inputs.gpu_metrics, inputs.gpu_cost_rows)
        )
        results.append(compute_change_velocity_iac(inputs.iac_runs))

        return results
