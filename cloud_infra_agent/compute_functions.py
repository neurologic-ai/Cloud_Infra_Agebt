from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List

from cloud_infra_agent.utility_functions import (
    aggregate_by_kind,
    avg_numeric,
    bucket_public,
    bytes_eligible_for_cold,
    bytes_stale_in_hot,
    commitment_coverage_percent,
    commitment_waste_usd,
    cost_per_gpu_hour,
    detect_month,
    detect_spikes,
    lifecycle_rule_coverage,
    mttr_hours,
    overly_permissive_principals,
    p50,
    p95,
    pct_encrypted_at_rest,
    pct_strong_tls_policies,
    realized_savings_usd,
    rollup_cost,
    rollup_egress,
    rule_allows_world,
    sample_missing_tags,
)


def compute_inventory_snapshot(adapters, since: int, until: int) -> dict:
    aws = adapters.get("aws", {}).get("resources", [])
    az = adapters.get("azure", {}).get("resources", [])
    gcp = adapters.get("gcp", {}).get("resources", [])

    return {
        "metric_id": "inventory.snapshot",
        "ts": {"from": since, "to": until},
        "counts": {"aws": len(aws), "azure": len(az), "gcp": len(gcp)},
        "by_kind": aggregate_by_kind([aws, az, gcp]),
    }


def compute_tagging_coverage(
    resources: list,
    required_tags=("env", "owner", "cost-center", "service"),
) -> dict:
    total = len(resources) or 1
    coverage = sum(
        all(t in (r.get("tags", {}) or {}) for t in required_tags)
        for r in resources
    ) / total
    missing = sample_missing_tags(resources, required_tags)

    return {
        "metric_id": "tagging.coverage",
        "required": list(required_tags),
        "coverage": coverage,
        "sample_missing": missing[:25],
    }


def compute_compute_utilization(
    metrics: List[Dict[str, Any]], threshold_low=0.1
) -> dict:
    low = [
        m
        for m in metrics
        if m.get("cpu_p95", 0.0) < threshold_low
        and m.get("mem_p95", 0.0) < threshold_low
    ]

    return {
        "metric_id": "compute.utilization",
        "fleet_p95": {
            "cpu": p95([m.get("cpu_p95", 0.0) for m in metrics]),
            "mem": p95([m.get("mem_p95", 0.0) for m in metrics]),
        },
        "low_util_count": len(low),
        "low_util_ids": [m.get("id") for m in low[:50]],
    }


def compute_k8s_utilization(
    prom_adapter: Dict[str, Any], clusters: List[str] | None = None
) -> dict:
    rows = prom_adapter  # already normalized as in sample
    return {
        "metric_id": "k8s.utilization",
        "nodes": rows.get("nodes", {}),
        "pods": rows.get("pods", {}),
        "binpack_efficiency": rows.get("binpack_efficiency"),
        "pending_pods_p95": rows.get("pending_pods_p95"),
    }


def compute_autoscaling_effectiveness(
    ts_metrics: List[Dict[str, Any]], scale_events: List[Dict[str, Any]]
) -> dict:
    """Compute autoscaling effectiveness metrics."""

    def to_ts(s):
        return datetime.fromisoformat(s.replace("Z", "+00:00"))

    events_sorted = (
        sorted(scale_events, key=lambda e: to_ts(e["ts"]))
        if scale_events
        else []
    )

    # Toy heuristic: if actual_cpu > target_cpu by >10%, consider a spike
    breaches = [
        m
        for m in ts_metrics
        if (m.get("actual_cpu", 0) - m.get("target_cpu", 0)) > 0.10
    ]

    reaction_times = []
    for b in breaches:
        b_ts = to_ts(b["ts"])
        after = [e for e in events_sorted if to_ts(e["ts"]) >= b_ts]
        if after:
            reaction_times.append(
                (to_ts(after[0]["ts"]) - b_ts).total_seconds()
            )

    ttr = statistics.median(reaction_times) if reaction_times else 0.0

    # Thrash rate: percent of adjacent opposing actions within 30m
    thrash = 0.0
    if len(events_sorted) >= 2:
        opposites = 0
        for a, b in zip(events_sorted, events_sorted[1:]):
            if a["action"] != b["action"]:
                dt = (to_ts(b["ts"]) - to_ts(a["ts"])).total_seconds()
                if dt <= 1800:
                    opposites += 1
        thrash = opposites / max(1, len(events_sorted) - 1)

    # Violations: percent of periods where |actual - target| > 10%
    violations = (
        sum(
            1
            for m in ts_metrics
            if abs(m.get("actual_cpu", 0) - m.get("target_cpu", 0)) > 0.10
        )
        / max(1, len(ts_metrics))
    )

    return {
        "metric_id": "scaling.effectiveness",
        "median_reaction_s": ttr,
        "thrash_rate": thrash,
        "target_violation_pct": violations,
    }


def compute_lb_performance(lb_metrics: List[Dict[str, Any]])->dict:
    return {"metric_id":"lb.performance",
            "latency_ms":{"p50":p50([m.get("lat_p50",0) for m in lb_metrics]),
                          "p95":p50([m.get("lat_p95",0) for m in lb_metrics]),
                          "p99":p50([m.get("lat_p99",0) for m in lb_metrics])},
            "error_rates":{"4xx":avg_numeric([m.get("r4xx",0.0) for m in lb_metrics]),
                           "5xx":avg_numeric([m.get("r5xx",0.0) for m in lb_metrics])},
            "unhealthy_host_minutes":sum(int(m.get("unhealthy_minutes",0)) for m in lb_metrics)}


def compute_storage_waste(
    block: List[Dict[str, Any]],
    snapshots: List[Dict[str, Any]],
    objects: List[Dict[str, Any]],
) -> dict:
    unattached = [v for v in block if v.get("attached") is False]
    orphan_snaps = [s for s in snapshots if not s.get("source_volume")]
    hot_stale_bytes = bytes_stale_in_hot(objects, stale_days=90)

    return {
        "metric_id": "storage.waste",
        "unattached_volumes": len(unattached),
        "orphaned_snapshots": len(orphan_snaps),
        "hot_stale_bytes": int(hot_stale_bytes),
    }


def compute_iac_coverage_and_drift(
    inventory: List[Dict[str, Any]],
    iac_index: Dict[str, Any],
    policy_findings: List[Dict[str, Any]],
) -> dict:
    managed = sum(1 for r in inventory if iac_index.get(r.get("id")))
    total = len(inventory) or 1
    drift = len(
        [f for f in policy_findings
         if f.get("severity") in ("high", "critical")]
    )

    return {
        "metric_id": "iac.coverage_drift",
        "coverage": managed / total,
        "policy_drift_count": drift,
    }


def compute_availability_incident_rate(
    incidents: List[Dict[str, Any]],
    slo_breaches: List[Dict[str, Any]],
) -> dict:
    sev12 = [i for i in incidents if i.get("sev") in (1, 2)]

    return {
        "metric_id": "availability.incidents",
        "sev12_30d": len(sev12),
        "mttr_h": mttr_hours(sev12),
        "slo_breach_hours": sum(
            float(b.get("hours", 0.0)) for b in slo_breaches
        ),
    }


def compute_monthly_cost_breakdown(cost_rows: List[Dict[str, Any]]) -> dict:
    by_dim = rollup_cost(cost_rows, dims=["cloud", "service", "env", "owner"])

    return {
        "metric_id": "cost.breakdown",
        "month": detect_month(cost_rows),
        "by_dim": by_dim,
    }


def compute_reserved_commit_coverage(
    commit_inventory: List[Dict[str, Any]],
    usage: List[Dict[str, Any]],
) -> dict:
    coverage = commitment_coverage_percent(commit_inventory, usage)
    realized = realized_savings_usd(commit_inventory, usage)
    waste = commitment_waste_usd(commit_inventory, usage)

    return {
        "metric_id": "cost.commit_coverage",
        "coverage_pct": coverage,
        "realized_savings_usd": realized,
        "waste_usd": waste,
    }


def compute_rightsizing_opportunities(reco: list) -> dict:
    monthly_save = sum(float(r.get("monthly_savings", 0.0)) for r in reco)

    return {
        "metric_id": "cost.rightsize",
        "recommendations": len(reco),
        "projected_monthly_savings_usd": monthly_save,
        "top_samples": reco[:20],
    }


def compute_storage_lifecycle_optimization(
    objects: List[Dict[str, Any]],
    lifecycle_rules: List[Dict[str, Any]],
) -> dict:
    eligible_bytes = bytes_eligible_for_cold(objects, rules=lifecycle_rules)
    has_rules_pct = lifecycle_rule_coverage(lifecycle_rules, objects)

    return {
        "metric_id": "cost.storage_lifecycle",
        "eligible_bytes": int(eligible_bytes),
        "has_rules_pct": has_rules_pct,
    }


def compute_data_egress_costs(
    cost_rows: List[Dict[str, Any]],
    net_metrics: List[Dict[str, Any]],
) -> dict:
    egress = rollup_egress(cost_rows)
    spikes = detect_spikes(net_metrics)

    return {
        "metric_id": "cost.egress",
        "by_type": egress,
        "spikes": spikes,
    }


def compute_cost_allocation_quality(cost_rows: List[Dict[str, Any]]) -> dict:
    total = sum(float(r.get("cost", 0.0)) for r in cost_rows) or 1.0
    tagged = sum(float(r.get("cost", 0.0)) for r in cost_rows if r.get("tags"))
    attributable = sum(
        float(r.get("cost", 0.0))
        for r in cost_rows if r.get("tags") or r.get("resource_id")
    )

    return {
        "metric_id": "cost.allocation_quality",
        "tagged_pct": tagged / total,
        "attributable_pct": attributable / total,
    }


def compute_public_exposure(
    inventory: List[Dict[str, Any]],
    net_policies: List[Dict[str, Any]],
    storage_acls: List[Dict[str, Any]],
) -> dict:
    public_ips = [r for r in inventory if r.get("public_ip")]
    open_fw = [n for n in net_policies if rule_allows_world(n)]
    public_buckets = [b for b in storage_acls if bucket_public(b)]

    return {
        "metric_id": "security.public_exposure",
        "public_ips": len(public_ips),
        "open_firewall_rules": len(open_fw),
        "public_buckets": len(public_buckets),
        "samples": {
            "ips": [{"id": r.get("id")} for r in public_ips[:10]],
            "rules": open_fw[:10],
            "buckets": public_buckets[:10],
        },
    }


def compute_encryption_compliance(resources: List[Dict[str, Any]]) -> dict:
    at_rest = pct_encrypted_at_rest(resources)
    tls_ok = pct_strong_tls_policies(resources)

    return {
        "metric_id": "security.encryption",
        "at_rest_pct": at_rest,
        "tls_modern_pct": tls_ok,
    }


def compute_iam_risk_indicators(iam_dump: Dict[str, Any]) -> dict:
    no_mfa = [u for u in iam_dump.get("users", []) if not u.get("mfa_enabled")]
    old_keys = [
        k for k in iam_dump.get("keys", [])
        if int(k.get("age_days", 0)) > 90
    ]
    admin_perms = overly_permissive_principals(iam_dump)

    return {
        "metric_id": "security.iam_risk",
        "users_without_mfa": len(no_mfa),
        "old_access_keys": len(old_keys),
        "overly_permissive_principals": len(admin_perms),
    }


def compute_vuln_patch_posture(
    findings: List[Dict[str, Any]],
    patch_status: Dict[str, Any],
) -> dict:
    crit_open = sum(
        1 for f in findings
        if f.get("severity") == "CRITICAL" and not f.get("resolved")
    )
    agent_cov = float(patch_status.get("agent_coverage_pct", 0.0))
    avg_patch_age = float(patch_status.get("avg_patch_age_days", 0.0))

    return {
        "metric_id": "security.vuln_patch",
        "critical_open": crit_open,
        "agent_coverage_pct": agent_cov,
        "avg_patch_age_days": avg_patch_age,
    }


def group_by_severity_and_age(findings: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Return counts per severity, and aged > 30d."""
    sev_counts = defaultdict(int)
    aged = 0
    now = datetime.now(timezone.utc)

    for f in findings:
        sev = str(f.get("severity", "UNKNOWN")).lower()

        if sev == "critical":
            sev_counts["critical"] += 1
        elif sev == "high":
            sev_counts["high"] += 1
        elif sev == "medium":
            sev_counts["medium"] += 1
        else:
            sev_counts["other"] += 1

        opened_at = f.get("opened_at")
        if opened_at:
            try:
                dt = datetime.fromisoformat(opened_at.replace("Z", "+00:00"))
                if (now - dt).days > 30:
                    aged += 1
            except Exception:
                pass

    return {
        "critical": sev_counts.get("critical", 0),
        "high": sev_counts.get("high", 0),
        "aged_30d": aged,
    }


def top_failed_controls(
    findings: List[Dict[str, Any]], top_n: int = 10
) -> List[Dict[str, Any]]:
    ctr = Counter([f.get("id") or f.get("control") for f in findings])

    return [{"control": k, "count": v} for k, v in ctr.most_common(top_n)]


def compute_cspm_findings_summary(
    cspm_findings: List[Dict[str, Any]]
) -> dict:
    grouped = group_by_severity_and_age(cspm_findings)

    return {
        "metric_id": "security.cspm_summary",
        "open": {
            "critical": grouped["critical"],
            "high": grouped["high"],
        },
        "aged_over_30d": grouped["aged_30d"],
        "top_controls": top_failed_controls(cspm_findings),
    }


def compute_key_secret_rotation(
    kms: List[Dict[str, Any]],
    secrets: List[Dict[str, Any]],
) -> dict:
    keys_no_rotation = [k for k in kms if not k.get("rotation_enabled")]
    old_secrets = [
        s for s in secrets if int(s.get("age_days", 0)) > 90
    ]

    return {
        "metric_id": "security.rotation",
        "keys_without_rotation": len(keys_no_rotation),
        "secrets_older_90d": len(old_secrets),
    }


def compute_gpu_cost_efficiency(
    gpu_metrics: List[Dict[str, Any]],
    cost_rows: List[Dict[str, Any]],
) -> dict:
    util = avg_numeric([m.get("gpu_util", 0.0) for m in gpu_metrics])
    usd_per_hour = cost_per_gpu_hour(cost_rows)

    return {
        "metric_id": "gpu.cost_efficiency",
        "gpu_util_avg": util,
        "usd_per_gpu_hour": usd_per_hour,
    }


def count_by_week(iac_runs: List[Dict[str, Any]]) -> int:
    """Total runs / number of ISO weeks spanned."""
    if not iac_runs:
        return 0

    def to_ts(s):
        return datetime.fromisoformat(s.replace("Z", "+00:00"))

    weeks = {
        to_ts(r["created"]).isocalendar()[:2]
        for r in iac_runs if r.get("created")
    }

    return int(round(len(iac_runs) / max(1, len(weeks))))


def compute_change_velocity_iac(iac_runs: List[Dict[str, Any]]) -> dict:
    p50_time_to_merge_h = (
        p50(
            [
                (
                    datetime.fromisoformat(
                        r["merged"].replace("Z", "+00:00")
                    )
                    - datetime.fromisoformat(
                        r["created"].replace("Z", "+00:00")
                    )
                ).total_seconds() / 3600.0
                for r in iac_runs
                if r.get("created") and r.get("merged")
            ]
        )
    )
    weekly = count_by_week(iac_runs)

    return {
        "metric_id": "iac.change_velocity",
        "changes_per_week": weekly,
        "p50_time_to_merge_h": p50_time_to_merge_h,
    }