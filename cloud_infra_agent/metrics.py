import json
from loguru import logger

"""
Metric Prompt Builder (optimized for Cloud Infra Agent)
- Universal preamble and unified response format for all metrics
- Optimized rubrics with clear 1-5 thresholds
- Example outputs now use 'evidence' (not 'details')
- build_prompt prints RESPONSE FORMAT before EXAMPLES (reduces anchoring)
"""

# =========================
# Universal scoring contract
# =========================
UNIVERSAL_PREAMBLE = (
    "You are a Cloud Infra Assessor. Score exactly one metric on a 1-5 scale:\n"
    "5 = Excellent (exceeds target, no material risks)\n"
    "4 = Good (meets target, minor risks)\n"
    "3 = Fair (near target, clear risks to address)\n"
    "2 = Poor (misses target, material risks)\n"
    "1 = Critical (significant failure, urgent action)\n\n"
    "Rules:\n"
    "- Use only provided data. If required inputs are missing, put those as numbered items inside 'gaps', reduce 'confidence', and adjust the score downward.\n"
    "- Prefer normalized rates (0..1), p95/p99, and denominators. Cite exact numbers under 'evidence'.\n"
    "- Keep recommended next steps concrete (≤5) and put them INSIDE 'gaps' as numbered items (no 'actions' field).\n"
    "- Return ONLY the specified JSON. No extra text.\n"
    "- Do NOT reuse numbers from EXAMPLE OUTPUT; recompute everything from TASK INPUT."
)

# Actions are now embedded within 'gaps' as plain numbered steps
UNIVERSAL_RESPONSE_FORMAT = (
    '{"metric_id":"<id>",'
    '"score":<1-5>,'
    '"rationale":"<2-4 sentences, human-readable>",'
    '"evidence":{},'
    '"gaps":["1. <missing-data or action step>", "2. <next step>"],'
    '"confidence":<0.0-1.0>}'
)

# Helper note appended to every metric prompt to reinforce the contract
APPEND_TO_ALL_METRICS = (
    "\nOUTPUT NOTE: Put ALL missing-data notes and recommended next steps inside 'gaps' "
    "as a numbered list like ['1. ...','2. ...']. Do NOT include a top-level 'actions' field."
)

# =========================
# Metric definitions
# =========================
# Each metric has:
# - system: the full prompt (universal preamble + rubric + output note)
# - example_input: canonical JSON example
# - input_key_meanings: friendly meanings
# - response_format: always UNIVERSAL_RESPONSE_FORMAT
# - example_output: example JSON response (with numbered 'gaps', no 'actions')

METRIC_PROMPTS = {
    # 1) Tagging coverage
    "tagging.coverage": {
        "system": (
            f"{UNIVERSAL_PREAMBLE}\n\n"
            "RUBRIC:\n"
            "- 5: ≥95% fully tagged AND all critical tags present (env, owner)\n"
            "- 4: 85-94% fully tagged; critical tags >90%\n"
            "- 3: 70-84% fully tagged; some gaps in critical tags\n"
            "- 2: 50-69% fully tagged; many missing critical tags\n"
            "- 1: <50% fully tagged OR critical tags absent on >25% of prod resources"
            f"{APPEND_TO_ALL_METRICS}"
        ),
        "example_input": {
            "resources": [
                {"id": "x", "tags": {"env": "prod", "owner": "team", "cost-center": "CC1", "service": "api"}},
                {"id": "y", "tags": {"env": "prod", "owner": "team"}}
            ],
            "required_tags": ["env", "owner", "cost-center", "service"]
        },
        "input_key_meanings": {
            "resources": "List of resources to evaluate",
            "resources[].id": "Unique resource identifier",
            "resources[].tags": "Key/value tags on the resource",
            "required_tags": "Array of tag keys that are mandatory for full coverage"
        },
        "response_format": UNIVERSAL_RESPONSE_FORMAT,
        "example_output": {
            "metric_id": "tagging.coverage",
            "score": 3,
            "rationale": "About half the resources are fully tagged. Missing critical tags on production items make ownership and cost attribution harder.",
            "evidence": {"coverage_pct": 0.5, "missing_examples": [{"id": "y", "missing": ["cost-center", "service"]}]},
            "gaps": [
                "1. Enforce env/owner/cost-center/service tags in CI & provisioning"
            ],
            "confidence": 0.8
        }
    },

    # 2) Compute utilization
    "compute.utilization": {
        "system": (
            f"{UNIVERSAL_PREAMBLE}\n\n"
            "RUBRIC:\n"
            "- 5: ≥80% instances at 40-70% CPU/mem; <10% low-util outliers\n"
            "- 4: 65-79% instances at 40-70% CPU/mem; 10-20% low-util outliers\n"
            "- 3: 50-64% instances at 40-70% CPU/mem; 20-35% low-util\n"
            "- 2: 30-49% instances at 40-70% CPU/mem; 36-50% low-util\n"
            "- 1: <30% instances at 40-70% CPU/mem OR >50% low-util (fleet largely idle)"
            f"{APPEND_TO_ALL_METRICS}"
        ),
        "example_input": {
            "instances": [
                {"id": "a", "cpu_p95": 0.55, "mem_p95": 0.6, "low_util_hours_30d": 5},
                {"id": "b", "cpu_p95": 0.1,  "mem_p95": 0.2, "low_util_hours_30d": 200}
            ]
        },
        "input_key_meanings": {
            "instances": "List of compute instances",
            "instances[].id": "Instance identifier",
            "instances[].cpu_p95": "95th percentile CPU utilization (0..1)",
            "instances[].mem_p95": "95th percentile memory utilization (0..1)",
            "instances[].low_util_hours_30d": "Hours in last 30d where instance was below low-util threshold"
        },
        "response_format": UNIVERSAL_RESPONSE_FORMAT,
        "example_output": {
            "metric_id": "compute.utilization",
            "score": 2,
            "rationale": "A large share of capacity is idle. One instance shows prolonged low utilization, pulling down overall efficiency.",
            "evidence": {"idle_pct": 0.5, "worst_idle_hours": 200, "fleet_cpu_p95": 0.325, "fleet_mem_p95": 0.40},
            "gaps": [
                "1. Rightsize or stop idle instance 'b' and implement off-hours schedules"
            ],
            "confidence": 0.9
        }
    },

    # 3) K8s utilization
    "k8s.utilization": {
        "system": (
            f"{UNIVERSAL_PREAMBLE}\n\n"
            "RUBRIC (nodes, requests vs usage, packing, pending):\n"
            "- 5: Nodes 50-70%, req≈used (>80%), binpack >0.8, pending <1\n"
            "- 4: Nodes 40-75%, req≈used 70-79%, binpack >0.7, pending <3\n"
            "- 3: Moderate imbalance: binpack 0.6-0.7 OR pending 3-5\n"
            "- 2: Severe imbalance: binpack 0.5-0.59 OR pending 6-10\n"
            "- 1: Chronic inefficiency: binpack <0.5 OR >10 pending pods"
            f"{APPEND_TO_ALL_METRICS}"
        ),
        "example_input": {
            "nodes": {"cpu_p95": 0.6, "mem_p95": 0.58},
            "pods": {"cpu_req_vs_used": 0.8},
            "binpack_efficiency": 0.82,
            "pending_pods_p95": 1
        },
        "input_key_meanings": {
            "nodes.cpu_p95": "Aggregated 95th percentile node CPU utilization (0..1)",
            "nodes.mem_p95": "Aggregated 95th percentile node memory utilization (0..1)",
            "pods.cpu_req_vs_used": "Ratio of requested to actually used CPU (0..1)",
            "binpack_efficiency": "Packing/fragmentation efficiency (0..1)",
            "pending_pods_p95": "95th percentile of pending pods count"
        },
        "response_format": UNIVERSAL_RESPONSE_FORMAT,
        "example_output": {
            "metric_id": "k8s.utilization",
            "score": 5,
            "rationale": "Requests closely match actual usage, packing is efficient, and pending work is minimal. The cluster is using resources well.",
            "evidence": {"binpack_efficiency": 0.82, "pending_pods_p95": 1, "nodes_cpu_p95": 0.60, "pods_cpu_req_vs_used": 0.80},
            "gaps": [
                "1. Maintain current request/limit ratios and re-verify quarterly"
            ],
            "confidence": 0.85
        }
    },

    # 4) Scaling effectiveness
    "scaling.effectiveness": {
        "system": (
            f"{UNIVERSAL_PREAMBLE}\n\n"
            "RUBRIC (reaction, target adherence, thrash, delta adequacy):\n"
            "- 5: Reaction median <1 min; violations <5%; thrash <5%; delta error <10%\n"
            "- 4: Reaction median 1-2 min; violations 5-10%; thrash <10%; delta error 10-20%\n"
            "- 3: Reaction median 2-5 min; violations 10-20%; thrash <20% (mild); delta error 20-35%\n"
            "- 2: Reaction median 5-10 min; violations 20-35%; thrash 20-35% (frequent); delta error 35-60%\n"
            "- 1: Reaction median >10 min; violations >35%; thrash >35% (severe); delta error >60%\n\n"
            "DEFINITIONS (using only provided inputs):\n"
            "- Preprocessing: sort ts_metrics by ts ascending; sort scale_events by ts ascending.\n"
            "- Target violation: |actual_cpu - target_cpu| / target_cpu > 0.05 (STRICT '>'). Violation rate = (#violating samples / #ts_metrics) * 100.\n"
            "- Reaction time: Identify each breach start (a violating sample whose previous sample is non-violating or absent). Reaction for a breach = seconds from breach start to the first corrective scale_event. If none after breach start, use 601s. Use MEDIAN across breaches.\n"
            "- Thrash: Adjacent event direction flips under 300s count as thrash.\n"
            "- Delta adequacy (error%): Compare applied_delta to needed_delta computed from first breach.\n\n"
            "SCORING STEPS: compute metrics, map to tiers, average, round; populate evidence; return ONLY JSON."
            f"{APPEND_TO_ALL_METRICS}"
        ),
        "example_input": {
            "ts_metrics": [
                {"ts": "2025-08-10T12:00:00Z", "target_cpu": 0.6, "actual_cpu": 0.9},
                {"ts": "2025-08-10T12:01:00Z", "target_cpu": 0.6, "actual_cpu": 0.62},
                {"ts": "2025-08-10T12:02:00Z", "target_cpu": 0.6, "actual_cpu": 0.60}
            ],
            "scale_events": [
                {"ts": "2025-08-10T12:00:40Z", "action": "scale_out", "delta": 5},
                {"ts": "2025-08-10T12:11:00Z", "action": "scale_in", "delta": 1}
            ]
        },
        "input_key_meanings": {
            "ts_metrics": "Time series of target vs actual metric (e.g., CPU)",
            "ts_metrics[].ts": "Timestamp or sequence marker",
            "ts_metrics[].target_cpu": "Autoscaler target (0..1)",
            "ts_metrics[].actual_cpu": "Observed utilization (0..1)",
            "scale_events": "List of scaling actions",
            "scale_events[].ts": "Timestamp of the scaling action",
            "scale_events[].action": "Action type (scale_out/scale_in)",
            "scale_events[].delta": "Change in replica count or capacity"
        },
        "response_format": UNIVERSAL_RESPONSE_FORMAT,
        "example_output": {
            "metric_id": "scaling.effectiveness",
            "score": 5,
            "rationale": "The system reacted quickly to overload, kept violations rare, avoided oscillation, and applied the right scale step.",
            "evidence": {
                "median_reaction_s": 40,
                "target_violation_pct": 4.76,
                "thrash_rate": 0.0,
                "delta_error_pct": 0.0,
                "events": 2,
                "total_samples": 3,
                "violating_samples": 1,
                "first_breach_ts": "2025-08-10T12:00:00Z",
                "first_corrective_ts": "2025-08-10T12:00:40Z",
                "needed_delta": 5,
                "applied_delta": 5
            },
            "gaps": [
                "1. Maintain current step sizing; monitor for oscillation under changing traffic patterns"
            ],
            "confidence": 0.8
        }
    },

    # 5) DB utilization
    "db.utilization": {
        "system": (
            f"{UNIVERSAL_PREAMBLE}\n\n"
            "RUBRIC (CPU, connections, IOPS balance):\n"
            "- 5: 40-70% CPU, balanced connections, IOPS within limits\n"
            "- 4: 30-75% CPU, mostly balanced, occasional spikes\n"
            "- 3: 20-85% CPU with connection/IOPS imbalance at times\n"
            "- 2: <20% or >85% CPU frequently; recurring bottlenecks\n"
            "- 1: Chronically idle (<10%) or saturated (>90%) across fleet"
            f"{APPEND_TO_ALL_METRICS}"
        ),
        "example_input": {
            "databases": [
                {"id": "a", "cpu_p95": 0.6, "connections_p95": 0.5},
                {"id": "b", "cpu_p95": 0.1, "connections_p95": 0.1}
            ]
        },
        "input_key_meanings": {
            "databases": "List of database instances",
            "databases[].id": "Database identifier",
            "databases[].cpu_p95": "95th percentile CPU utilization (0..1)",
            "databases[].connections_p95": "95th percentile connection load (0..1)"
        },
        "response_format": UNIVERSAL_RESPONSE_FORMAT,
        "example_output": {
            "metric_id": "db.utilization",
            "score": 3,
            "rationale": "The fleet mixes idle and moderately loaded databases, suggesting uneven sizing.",
            "evidence": {"low_util_count": 1, "high_util_count": 0, "fleet_cpu_p95_avg": 0.35},
            "gaps": [
                "1. Downsize or consolidate idle DB 'b' and validate connection limits"
            ],
            "confidence": 0.82
        }
    },

    # 6) Load balancer performance
    "lb.performance": {
        "system": (
            f"{UNIVERSAL_PREAMBLE}\n\n"
            "RUBRIC (latency & 5xx vs SLO):\n"
            "- 5: p95/p99 well under SLO; 5xx rare; minimal unhealthy time\n"
            "- 4: Near SLO with small spikes; rare 5xx\n"
            "- 3: Periodic SLO breaches or elevated 5xx\n"
            "- 2: Frequent breaches or sustained 5xx\n"
            "- 1: Chronic SLO failures and/or major instability"
            f"{APPEND_TO_ALL_METRICS}"
        ),
        "example_input": {
            "load_balancers": [
                {"id": "alb-1", "lat_p95": 130, "lat_p99": 260, "r5xx": 0.003, "unhealthy_minutes": 2, "requests": 1200000}
            ],
            "slo": {"p95_ms": 200, "p99_ms": 400, "5xx_rate_max": 0.005}
        },
        "input_key_meanings": {
            "load_balancers": "List of LBs with health/latency/5xx metrics",
            "load_balancers[].id": "Load balancer identifier",
            "load_balancers[].lat_p95": "p95 latency in ms",
            "load_balancers[].lat_p99": "p99 latency in ms",
            "load_balancers[].r5xx": "5xx error rate (0..1)",
            "load_balancers[].unhealthy_minutes": "Minutes marked unhealthy",
            "slo.p95_ms": "SLO threshold for p95 latency",
            "slo.p99_ms": "SLO threshold for p99 latency",
            "slo.5xx_rate_max": "Maximum acceptable 5xx rate"
        },
        "response_format": UNIVERSAL_RESPONSE_FORMAT,
        "example_output": {
            "metric_id": "lb.performance",
            "score": 5,
            "rationale": "Latency and error rates are comfortably within SLO, and the load balancer stayed healthy almost the entire time.",
            "evidence": {"breaches": 0, "worst_lb": "alb-1", "p95_ms": 130, "p99_ms": 260, "r5xx": 0.003, "requests": 1200000},
            "gaps": [
                "1. Maintain capacity and SLO thresholds; review monthly"
            ],
            "confidence": 0.86
        }
    },

    # 7) Storage efficiency
    "storage.efficiency": {
        "system": (
            f"{UNIVERSAL_PREAMBLE}\n\n"
            "RUBRIC (unattached/orphaned/stale hot data):\n"
            "- 5: No obvious waste\n"
            "- 4: Minor waste\n"
            "- 3: Noticeable but not severe\n"
            "- 2: Significant avoidable cost\n"
            "- 1: Systemic waste across tiers"
            f"{APPEND_TO_ALL_METRICS}"
        ),
        "example_input": {
            "block_volumes": [{"id": "v", "attached": False}],
            "snapshots": [{"id": "s", "source_volume": None}],
            "objects": [{"storage_class": "STANDARD", "last_modified": "2024-01-01T00:00:00Z"}]
        },
        "input_key_meanings": {
            "block_volumes": "List of block volumes and their attachment state",
            "block_volumes[].id": "Volume identifier",
            "block_volumes[].attached": "Boolean attachment flag",
            "snapshots": "List of snapshots and their source volume linkage",
            "snapshots[].source_volume": "Volume ID if snapshot has a valid source, else null",
            "objects": "Object storage items",
            "objects[].storage_class": "Storage tier/class",
            "objects[].last_modified": "Timestamp of last modification/access"
        },
        "response_format": UNIVERSAL_RESPONSE_FORMAT,
        "example_output": {
            "metric_id": "storage.efficiency",
            "score": 2,
            "rationale": "There are unattached volumes, orphaned snapshots, and stale objects kept on the hot tier — all adding avoidable cost.",
            "evidence": {"unattached": 1, "orphaned_snaps": 1, "hot_stale_objects": 1},
            "gaps": [
                "1. Delete orphaned snapshots",
                "2. Reattach or remove unattached volumes",
                "3. Apply lifecycle policies to move stale objects to infrequent access"
            ],
            "confidence": 0.85
        }
    },

    # 8) IaC coverage & drift
    "iac.coverage_drift": {
        "system": (
            f"{UNIVERSAL_PREAMBLE}\n\n"
            "RUBRIC (coverage & drift severity):\n"
            "- 5: ≥95% IaC-managed; no high/critical drift\n"
            "- 4: 85-94% IaC-managed; minor drift\n"
            "- 3: 70-84% IaC-managed OR some high drifts\n"
            "- 2: 50-69% IaC-managed OR multiple high/critical drifts\n"
            "- 1: <50% IaC-managed OR widespread critical drift"
            f"{APPEND_TO_ALL_METRICS}"
        ),
        "example_input": {
            "inventory": [{"id": "a"}, {"id": "b"}],
            "iac_index": {"a": True, "b": False},
            "policy_findings": [{"severity": "high"}]
        },
        "input_key_meanings": {
            "inventory": "List of resources in scope",
            "inventory[].id": "Resource identifier",
            "iac_index": "Map of resource id → whether managed by IaC",
            "policy_findings": "List of drift/security/policy issues",
            "policy_findings[].severity": "Severity level (e.g., high, critical)"
        },
        "response_format": UNIVERSAL_RESPONSE_FORMAT,
        "example_output": {
            "metric_id": "iac.coverage_drift",
            "score": 3,
            "rationale": "IaC coverage is near half, and there is at least one high-severity drift to address.",
            "evidence": {"coverage_pct": 0.5, "high_critical": 1},
            "gaps": [
                "1. Onboard unmanaged resources to Terraform",
                "2. Remediate high-severity drift findings first"
            ],
            "confidence": 0.8
        }
    },

    # 9) Availability incidents
    "availability.incidents": {
        "system": (
            f"{UNIVERSAL_PREAMBLE}\n\n"
            "RUBRIC (Sev1/2, MTTR, SLO breach hours):\n"
            "- 5: 0 Sev1/2, MTTR <1h, no SLO breaches\n"
            "- 4: ≤1 Sev2, MTTR 1-2h, minor breach hours\n"
            "- 3: Some incidents, MTTR 2-4h, breaches present\n"
            "- 2: Frequent incidents or MTTR 4-8h\n"
            "- 1: Severe/frequent incidents, MTTR >8h"
            f"{APPEND_TO_ALL_METRICS}"
        ),
        "example_input": {
            "incidents": [{"sev": 2, "opened": "t0", "resolved": "t1"}],
            "slo_breaches": [{"hours": 1.0}],
            "slo": {"objective": "availability", "target": 0.995}
        },
        "input_key_meanings": {
            "incidents": "Array of incident records in the scoring window",
            "incidents[].sev": "Severity level (1=critical, 2=major, 3=minor, etc.)",
            "incidents[].opened": "Timestamp when incident started",
            "incidents[].resolved": "Timestamp when incident was resolved",
            "slo_breaches": "Array of SLO violations observed",
            "slo_breaches[].hours": "Total hours of breach for that occurrence",
            "slo": "Definition of the service-level objective applied",
            "slo.objective": "The type of objective (e.g., 'availability', 'latency')",
            "slo.target": "Numerical target for compliance (e.g., 0.995 = 99.5%)"
        },
        "response_format": UNIVERSAL_RESPONSE_FORMAT,
        "example_output": {
            "metric_id": "availability.incidents",
            "score": 4,
            "rationale": "There was a single major incident that was resolved quickly with limited SLO breach time.",
            "evidence": {"sev12_30d": 1, "mttr_h": 1.0, "slo_breach_hours": 1.0, "slo_target": 0.995},
            "gaps": [
                "1. Review post-mortem for mitigations and confirm alert thresholds"
            ],
            "confidence": 0.85
        }
    },

    # 10) Cost — idle underutilized
    "cost.idle_underutilized": {
        "system": (
            f"{UNIVERSAL_PREAMBLE}\n\n"
            "RUBRIC (idle spend share):\n"
            "- 5: Idle <2% of total spend\n"
            "- 4: Idle 2-5% of total spend\n"
            "- 3: Idle 5-10% of total spend\n"
            "- 2: Idle 10-20% of total spend\n"
            "- 1: Idle >20%"
            f"{APPEND_TO_ALL_METRICS}"
        ),
        "example_input": {
            "cost_rows": [
                {"resource_id": "a", "cost": 100},
                {"resource_id": "b", "cost": 100}
            ],
            "instances": [
                {"id": "a", "cpu_p95": 0.05, "mem_p95": 0.07},
                {"id": "b", "cpu_p95": 0.6,  "mem_p95": 0.5}
            ]
        },
        "input_key_meanings": {
            "cost_rows": "List of resource-level cost entries",
            "cost_rows[].resource_id": "ID matching an instance or resource",
            "cost_rows[].cost": "Cost amount (currency units)",
            "instances": "List of instances with utilization",
            "instances[].id": "Instance identifier",
            "instances[].cpu_p95": "95th percentile CPU (0..1)",
            "instances[].mem_p95": "95th percentile memory (0..1)"
        },
        "response_format": UNIVERSAL_RESPONSE_FORMAT,
        "example_output": {
            "metric_id": "cost.idle_underutilized",
            "score": 2,
            "rationale": "Idle resources account for a large share of spend, driven by persistently underutilized instances.",
            "evidence": {"idle_cost": 100, "idle_pct": 0.5, "total_cost": 200},
            "gaps": [
                "1. Stop or downsize idle instance 'a' and apply off-hours schedules"
            ],
            "confidence": 0.88
        }
    },

    # 11) Cost — commit coverage
    "cost.commit_coverage": {
        "system": (
            f"{UNIVERSAL_PREAMBLE}\n\n"
            "RUBRIC (coverage & unused %):\n"
            "- 5: ≥95% coverage AND <5% unused commitment\n"
            "- 4: 85-94% coverage AND 5-10% unused commitment\n"
            "- 3: 70-84% coverage AND 11-20% unused commitment\n"
            "- 2: 50-69% coverage OR 21-30% unused commitment\n"
            "- 1: <50% coverage OR >30% unused commitment"
            f"{APPEND_TO_ALL_METRICS}"
        ),
        "example_input": {
            "commit_inventory": [{"commit_usd_hour": 2.0}],
            "usage": [{"used_usd_hour": 1.8, "hours": 720}]
        },
        "input_key_meanings": {
            "commit_inventory": "List of commitment SKUs/terms",
            "commit_inventory[].commit_usd_hour": "Hourly committed spend capacity",
            "usage": "List of usage entries for coverage calc",
            "usage[].used_usd_hour": "Hourly spend that was actually used",
            "usage[].hours": "Hours in the period"
        },
        "response_format": UNIVERSAL_RESPONSE_FORMAT,
        "example_output": {
            "metric_id": "cost.commit_coverage",
            "score": 4,
            "rationale": "Commitment coverage is around ninety percent with a small amount of unused capacity.",
            "evidence": {"coverage_pct": 0.90, "waste_usd": 144},
            "gaps": [
                "1. Refine commitment mix to reduce ~10% unused commitments"
            ],
            "confidence": 0.9
        }
    },

    # 12) Cost — allocation quality
    "cost.allocation_quality": {
        "system": (
            f"{UNIVERSAL_PREAMBLE}\n\n"
            "RUBRIC (cost-weighted attribution):\n"
            "- 5: ≥95% costs attributable\n"
            "- 4: 90-94% costs attributable\n"
            "- 3: 75-89% costs attributable\n"
            "- 2: 50-74% costs attributable\n"
            "- 1: <50% costs attributable"
            f"{APPEND_TO_ALL_METRICS}"
        ),
        "example_input": {
            "cost_rows": [
                {"cost": 100, "tags": {"env": "prod", "owner": "search"}},
                {"cost": 100, "tags": {}}
            ]
        },
        "input_key_meanings": {
            "cost_rows": "List of cost line items",
            "cost_rows[].cost": "Cost amount (currency units)",
            "cost_rows[].tags": "Tag dictionary on the cost row used for attribution"
        },
        "response_format": UNIVERSAL_RESPONSE_FORMAT,
        "example_output": {
            "metric_id": "cost.allocation_quality",
            "score": 3,
            "rationale": "Only half of the spend can be attributed due to missing tags on many cost lines.",
            "evidence": {"attributable_pct": 0.5},
            "gaps": [
                "1. Enforce owner/env tagging on all cost lines and backfill missing owners"
            ],
            "confidence": 0.87
        }
    },

    # 13) Security — public exposure
    "security.public_exposure": {
        "system": (
            f"{UNIVERSAL_PREAMBLE}\n\n"
            "RUBRIC (open ingress, public IPs/buckets):\n"
            "- 5: No public buckets; no 0.0.0.0/0 on sensitive ports; minimal public IPs\n"
            "- 4: Minor/properly approved exceptions in non-prod\n"
            "- 3: Some risky rules or public buckets with controls\n"
            "- 2: Multiple unnecessary exposures\n"
            "- 1: Widespread exposure of sensitive prod assets"
            f"{APPEND_TO_ALL_METRICS}"
        ),
        "example_input": {
            "network_policies": [{"rule": "0.0.0.0/0:22"}],
            "storage_acls": [{"bucket": "ml-prod", "public": True}],
            "inventory": [{"id": "i-9zzz", "public_ip": True}]
        },
        "input_key_meanings": {
            "network_policies": "Array of ingress/SG/firewall rules in scope.",
            "network_policies[].rule": "CIDR:port or CIDR:port-range",
            "network_policies[].proto": "Optional protocol (default tcp).",
            "network_policies[].env": "Optional environment tag for risk weighting.",
            "storage_acls": "Array of object-storage ACLs/policies evaluated for public access.",
            "storage_acls[].bucket": "Bucket/container identifier.",
            "storage_acls[].public": "True if bucket/objects are publicly listable or readable.",
            "storage_acls[].exception_approved": "True if a documented exception exists.",
            "inventory": "Array of assets with exposure attributes.",
            "inventory[].id": "Asset identifier.",
            "inventory[].public_ip": "True if asset has a public IP.",
            "inventory[].sensitive": "True if asset handles prod/PII/regulated data."
        },
        "response_format": UNIVERSAL_RESPONSE_FORMAT,
        "example_output": {
            "metric_id": "security.public_exposure",
            "score": 2,
            "rationale": "Public SSH access, a public bucket, and exposed public IPs increase the attack surface and risk.",
            "evidence": {"open_fw_rules": 1, "public_buckets": 1, "public_ips": 1},
            "gaps": [
                "1. Restrict SSH to corporate CIDRs",
                "2. Make the public bucket private or enforce tighter object ACLs",
                "3. Remove public IPs from production workloads where not required"
            ],
            "confidence": 0.88
        }
    },

    # 14) Security — encryption
    "security.encryption": {
        "system": (
            f"{UNIVERSAL_PREAMBLE}\n\n"
            "RUBRIC (at-rest encryption & TLS policy):\n"
            "- 5: ~100% encrypted; all endpoints TLS 1.2+ modern\n"
            "- 4: 90-99% encrypted; minor TLS gaps\n"
            "- 3: 70-89% encrypted; some legacy TLS\n"
            "- 2: 50-69% encrypted; several legacy endpoints\n"
            "- 1: <50% encrypted; widespread legacy TLS"
            f"{APPEND_TO_ALL_METRICS}"
        ),
        "example_input": {
            "resources": [
                {"id": "vol-1", "type": "block_volume", "encrypted_at_rest": True},
                {"id": "alb-1", "type": "load_balancer", "tls_policy": "TLS1.2-2019-Modern"}
            ]
        },
        "input_key_meanings": {
            "resources": "Array of storage or network resources to check for encryption/TLS compliance.",
            "resources[].id": "Unique identifier for the resource.",
            "resources[].type": "Type of resource (e.g., 'block_volume', 'object_bucket', 'load_balancer').",
            "resources[].encrypted_at_rest": "True if data is encrypted at rest (for storage resources).",
            "resources[].tls_policy": "TLS/SSL security policy enforced on endpoints."
        },
        "response_format": UNIVERSAL_RESPONSE_FORMAT,
        "example_output": {
            "metric_id": "security.encryption",
            "score": 2,
            "rationale": "Encryption is inconsistent and at least one endpoint uses legacy TLS, which elevates risk.",
            "evidence": {"at_rest_pct": 0.66, "legacy_tls_endpoints": 1},
            "gaps": [
                "1. Enable encryption on remaining volumes",
                "2. Upgrade LB security policy to modern TLS 1.2+"
            ],
            "confidence": 0.86
        }
    },

    # 15) Security — IAM risk
    "security.iam_risk": {
        "system": (
            f"{UNIVERSAL_PREAMBLE}\n\n"
            "RUBRIC (MFA, key age, permissive policies):\n"
            "- 5: 0 users without MFA; no keys >90d; no wildcard admin\n"
            "- 4: Minor exceptions in non-prod\n"
            "- 3: Some exceptions across accounts\n"
            "- 2: Many exceptions; several wildcard policies\n"
            "- 1: Systemic issues (no MFA, wildcard admin in prod)"
            f"{APPEND_TO_ALL_METRICS}"
        ),
        "example_input": {
            "users": [{"name": "a","mfa_enabled": False}],
            "keys": [{ "user": "user","age_days": 120}],
            "policies": [{"actions": ["*"], "resources": ["*"]}]
        },
        "input_key_meanings": {
            "users": "IAM user accounts in scope.",
            "users[].name": "Username or identifier.",
            "users[].mfa_enabled": "True if MFA is enabled.",
            "keys": "IAM access keys or service keys.",
            "keys[].user": "User/service account the key belongs to.",
            "keys[].age_days": "Age of the key in days.",
            "policies": "IAM policies being evaluated.",
            "policies[].actions": "List of actions permitted.",
            "policies[].resources": "List of resources covered."
        },
        "response_format": UNIVERSAL_RESPONSE_FORMAT,
        "example_output": {
            "metric_id": "security.iam_risk",
            "score": 2,
            "rationale": "Several basic controls are missing: some users lack MFA, old keys are still active, and a wildcard admin policy exists.",
            "evidence": {"users_without_mfa": 1, "old_keys": 1, "overly_permissive_principals": 1},
            "gaps": [
                "1. Enforce MFA for all users immediately",
                "2. Replace wildcard admin with least-privilege roles"
            ],
            "confidence": 0.87
        }
    },

    # 16) Security — vulnerability & patch hygiene
    "security.vuln_patch": {
        "system": (
            f"{UNIVERSAL_PREAMBLE}\n\n"
            "RUBRIC (coverage, patch latency, criticals):\n"
            "- 5: ≥95% coverage, avg patch age <14d, 0 critical open\n"
            "- 4: ≥90% coverage, avg age <21d, few highs\n"
            "- 3: Some criticals open OR avg age 21-35d\n"
            "- 2: Multiple criticals; coverage <85% OR age 35-60d\n"
            "- 1: Chronic exposure; coverage <70% OR age >60d"
            f"{APPEND_TO_ALL_METRICS}"
        ),
        "example_input": {
            "findings": [{"severity": "CRITICAL", "resolved": False}],
            "patch_status": {
                "agent_coverage_pct": 0.9,
                "avg_patch_age_days": 30,
                "sla": {"critical_days": 7, "high_days": 30}
            },
            "denominators": {"total_assets": 420, "scanned_assets": 403}
        },
        "input_key_meanings": {
            "findings": "Vulnerability findings in scope.",
            "findings[].severity": "Severity (CRITICAL, HIGH, MEDIUM, LOW).",
            "findings[].resolved": "True if remediated.",
            "patch_status": "Patch coverage/latency metrics.",
            "patch_status.agent_coverage_pct": "Fraction of assets with patch agent reporting (0..1).",
            "patch_status.avg_patch_age_days": "Average age (days) of applied patches since release.",
            "patch_status.sla": "Patch SLAs for severity classes.",
            "denominators.total_assets": "Total assets in environment.",
            "denominators.scanned_assets": "Assets successfully scanned/covered."
        },
        "response_format": UNIVERSAL_RESPONSE_FORMAT,
        "example_output": {
            "metric_id": "security.vuln_patch",
            "score": 3,
            "rationale": "One critical vulnerability remains open. Coverage is close to target but patching is somewhat delayed.",
            "evidence": {
                "critical_open": 1,
                "agent_coverage_pct": 0.90,
                "avg_patch_age_days": 30,
                "sla": {"critical_days": 7, "high_days": 30},
                "scanned_assets": 403,
                "total_assets": 420
            },
            "gaps": [
                "1. Patch critical CVEs on internet-exposed assets within 48 hours",
                "2. Increase patch agent coverage from 90% to 95% across missing subnets"
            ],
            "confidence": 0.78
        }
    }
}


# =========================
# Prompt builder
# =========================
def build_prompt(metric_id: str, task_input: dict) -> str:
    """Generate a complete prompt for the given metric.

    Output format:
    SYSTEM: ... (includes universal preamble + rubric)
    INPUT JSON KEYS AND MEANINGS: ...
    TASK INPUT: <your JSON>
    RESPONSE FORMAT (JSON only): ...
    EXAMPLE INPUT: ...
    EXAMPLE OUTPUT: ...
    """
    meta = METRIC_PROMPTS.get(metric_id)
    if not meta:
        raise ValueError(f"Unknown metric_id: {metric_id}")

    meanings = meta.get("input_key_meanings", {})
    key_meanings_str = "\n".join([f"- {k}: {v}" for k, v in meanings.items()]) if meanings else ""

    prompt = (
        f"SYSTEM:\n{meta['system']}\n\n"
        f"INPUT JSON KEYS AND MEANINGS:\n{key_meanings_str}\n\n"
        f"TASK INPUT:\n{json.dumps(task_input, indent=2)}\n\n"
        f"RESPONSE FORMAT (JSON only):\n{meta['response_format']}\n\n"
        f"EXAMPLE INPUT:\n{json.dumps(meta['example_input'], indent=2)}\n\n"
        f"EXAMPLE OUTPUT:\n{json.dumps(meta['example_output'], indent=2)}"
    )
    logger.debug(prompt)
    # --- add these 3 lines ---
    # try:
    #     existing = json.load(open("all_metric_prompts.json"))  # load if exists
    # except FileNotFoundError:
    #     existing = {}
    # existing[metric_id] = prompt
    # with open("all_metric_prompts.json", "w") as f:
    #     json.dump(existing, f, indent=2)
    # -------------------------
    return prompt


# # Demo
# if __name__ == "__main__":
#     demo = {
#         "resources": [
#             {"id": "y", "tags": {"env": "prod", "owner": "team"}}
#         ],
#         "required_tags": ["env", "owner", "cost-center", "service"]
#     }
#     print(build_prompt("tagging.coverage", demo))
