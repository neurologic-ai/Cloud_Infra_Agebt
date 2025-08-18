import json

"""
Metric Prompt Builder (corrected)
- Matches the exact 16 metrics and prompt shapes you marked as correct
- Adds an "Input JSON Keys and Meanings" section inline in the prompt
- Use build_prompt(metric_id, task_input) to generate a complete prompt

Valid metric_id values:
  tagging.coverage, compute.utilization, k8s.utilization, scaling.effectiveness,
  db.utilization, lb.performance, storage.efficiency, iac.coverage_drift,
  availability.incidents, cost.idle_underutilized, cost.commit_coverage,
  cost.allocation_quality, security.public_exposure, security.encryption,
  security.iam_risk, security.vuln_patch
"""

METRIC_PROMPTS = {
    # 1) Tagging coverage — note: sample shows double "SYSTEM:" prefix
    "tagging.coverage": {
        "system": (
            "You are a Cloud FinOps assessor. Score 1–5 (5=excellent) the tagging coverage quality.\n\n"
            "RUBRIC:\n"
            "- 5: ≥95% resources have ALL required tags\n"
            "- 4: 85–94%\n"
            "- 3: 70–84%\n"
            "- 2: 50–69%\n"
            "- 1: <50%\n"
            "Also judge risk if key tags (env/owner) are missing even when % is high."
        ),
        "example_input": {
            "resources": [
                {"id": "x", "tags": {"env": "prod", "owner": "team", "cost-center": "CC1", "service": "api"}},
                {"id": "y", "tags": {"env": "prod", "owner": "team"}}
            ],
            "required_tags": ["env", "owner", "cost-center", "service"]
        },
        "example_output": {
            "metric_id": "tagging.coverage",
            "score": 3,
            "rationale": "~50% fully tagged; cost-center/service missing on some prod nodes.",
            "details": {"coverage_pct": 0.5, "missing_examples": [{"id": "y", "missing": ["cost-center", "service"]}]}
        },
        "response_format": '{"metric_id":"tagging.coverage","score":<1-5>,"rationale":"...","details":{"coverage_pct":<0..1>,"missing_examples":[...]}}',
        "key_meanings": {
            "resources": "List of resources to evaluate",
            "resources[].id": "Unique resource identifier",
            "resources[].tags": "Key/value tags on the resource",
            "required_tags": "Array of tag keys that are mandatory for full coverage"
        }
    },

    # 2) Compute utilization
    "compute.utilization": {
        "system": (
            "You are a reliability and cost-efficiency assessor. Score how effectively compute capacity is utilized.\n\n"
            "RUBRIC (heuristic guidance; you may adjust slightly by context):\n"
            "- 5: Fleet p95 CPU/mem in 40–70%, <10% low-util hours; minimal waste\n"
            "- 4: Mostly healthy; 10–20% low-util outliers\n"
            "- 3: Mixed; 20–35% low-util or frequent skew\n"
            "- 2: Significant waste; 35–50% low-util\n"
            "- 1: Largely idle or badly overprovisioned; >50% low-util"
        ),
        "example_input": {
            "instances": [
                {"id": "a", "cpu_p95": 0.55, "mem_p95": 0.51, "low_util_hours_30d": 0},
                {"id": "b", "cpu_p95": 0.1, "mem_p95": 0.09, "low_util_hours_30d": 200}
            ]
        },
        "example_output": {
            "metric_id": "compute.utilization",
            "score": 3,
            "rationale": "Half the fleet well-utilized, half persistently idle.",
            "details": {"low_util_count": 1, "fleet_cpu_p95": 0.325, "fleet_mem_p95": 0.30}
        },
        "response_format": '{"metric_id":"compute.utilization","score":<1-5>,"rationale":"...","details":{"low_util_count":<int>,"fleet_cpu_p95":<0..1>,"fleet_mem_p95":<0..1>}}',
        "key_meanings": {
            "instances": "List of compute instances",
            "instances[].id": "Instance identifier",
            "instances[].cpu_p95": "95th percentile CPU utilization (0..1)",
            "instances[].mem_p95": "95th percentile memory utilization (0..1)",
            "instances[].low_util_hours_30d": "Hours in last 30d where instance was below low-util threshold"
        }
    },

    # 3) K8s utilization
    "k8s.utilization": {
        "system": (
            "Score k8s capacity efficiency & scheduling.\n\n"
            "RUBRIC:\n"
            "- 5: CPU/mem p95 ~60–80%, req_vs_used ~0.7–0.9, binpack ≥0.8, low pending\n"
            "- 4: Minor headroom waste; binpack ≥0.7\n"
            "- 3: Mixed signals; binpack 0.6–0.7 or high pending intermittently\n"
            "- 2: Under-requesting/over-requesting common; binpack <0.6\n"
            "- 1: Chronic mismatch; many pending pods or extreme overprovision"
        ),
        "example_input": {
            "nodes": {"cpu_p95": 0.6, "mem_p95": 0.58},
            "pods": {"cpu_req_vs_used": 0.8},
            "binpack_efficiency": 0.82,
            "pending_pods_p95": 1
        },
        "example_output": {
            "metric_id": "k8s.utilization",
            "score": 5,
            "rationale": "Efficient requests and packing.",
            "details": {"binpack_efficiency": 0.82}
        },
        "response_format": '{"metric_id":"k8s.utilization","score":<1-5>,"rationale":"...","details":{"binpack_efficiency":<0..1>,"pending_pods_p95":<int>}}',
        "key_meanings": {
            "nodes.cpu_p95": "Aggregated 95th percentile node CPU utilization (0..1)",
            "nodes.mem_p95": "Aggregated 95th percentile node memory utilization (0..1)",
            "pods.cpu_req_vs_used": "Ratio of requested to actually used CPU (0..1)",
            "binpack_efficiency": "Packing/fragmentation efficiency (0..1)",
            "pending_pods_p95": "95th percentile of pending pods count"
        }
    },

    # 4) Scaling effectiveness
    "scaling.effectiveness": {
        "system": (
            "Evaluate autoscaling health (reaction time, target adherence, thrash).\n\n"
            "RUBRIC:\n"
            "- 5: Reacts within 1–2 mins; minimal target violations; no thrash\n"
            "- 4: Reacts <5 mins; rare violations\n"
            "- 3: Mixed; noticeable delays or occasional thrash\n"
            "- 2: Slow (>10 mins) or frequent oscillations\n"
            "- 1: Chronically late or incorrect scaling"
        ),
        "example_input": {
            "ts_metrics": [
                {"ts": "t0", "target_cpu": 0.6, "actual_cpu": 0.9},
                {"ts": "t2", "target_cpu": 0.6, "actual_cpu": 0.61}
            ],
            "scale_events": [{"ts": "t1", "action": "scale_out", "delta": 1}]
        },
        "example_output": {
            "metric_id": "scaling.effectiveness",
            "score": 4,
            "rationale": "Scaled in ~1 min; brief overshoot only.",
            "details": {"median_reaction_s": 60, "target_violation_pct": 0.1, "thrash_rate": 0.0}
        },
        "response_format": '{"metric_id":"scaling.effectiveness","score":<1-5>,"rationale":"...","details":{"median_reaction_s":<number>,"target_violation_pct":<0..1>,"thrash_rate":<0..1>}}',
        "key_meanings": {
            "ts_metrics": "Time series of target vs actual metric (e.g., CPU)",
            "ts_metrics[].ts": "Timestamp or sequence marker",
            "ts_metrics[].target_cpu": "Autoscaler target (0..1)",
            "ts_metrics[].actual_cpu": "Observed utilization (0..1)",
            "scale_events": "List of scaling actions",
            "scale_events[].ts": "Timestamp of the scaling action",
            "scale_events[].action": "Action type (scale_out/scale_in)",
            "scale_events[].delta": "Change in replica count or capacity"
        }
    },

    # 5) DB utilization
    "db.utilization": {
        "system": (
            "Score DB fleet efficiency & risk (hotspots vs idle waste).\n\n"
            "RUBRIC:\n"
            "- 5: Most DBs 40–70% CPU, healthy IOPS, capacity aligned\n"
            "- 4: Minor outliers\n"
            "- 3: Mix of idle and hot instances\n"
            "- 2: Many idle or several saturated\n"
            "- 1: Widespread saturation or waste"
        ),
        "example_input": {
            "databases": [
                {"id": "a", "cpu_p95": 0.6, "connections_p95": 0.5},
                {"id": "b", "cpu_p95": 0.1, "connections_p95": 0.1}
            ]
        },
        "example_output": {
            "metric_id": "db.utilization",
            "score": 3,
            "rationale": "One hot, one idle; uneven sizing.",
            "details": {"low_util_count": 1, "high_util_count": 0}
        },
        "response_format": '{"metric_id":"db.utilization","score":<1-5>,"rationale":"...","details":{"low_util_count":<int>,"high_util_count":<int>}}',
        "key_meanings": {
            "databases": "List of database instances",
            "databases[].id": "Database identifier",
            "databases[].cpu_p95": "95th percentile CPU utilization (0..1)",
            "databases[].connections_p95": "95th percentile connection load (0..1)"
        }
    },

    # 6) Load balancer performance
    "lb.performance": {
        "system": (
            "Score LB health vs provided SLOs (latency and 5xx).\n\n"
            "RUBRIC:\n"
            "- 5: p95/p99 well under SLO; 5xx rare; minimal unhealthy time\n"
            "- 4: Near SLO with small spikes\n"
            "- 3: Periodic breaches\n"
            "- 2: Frequent breaches or elevated 5xx\n"
            "- 1: Chronic SLO failures"
        ),
        "example_input": {
            "load_balancers": [
                {"id": "lb", "lat_p95": 180, "lat_p99": 350, "r5xx": 0.001, "unhealthy_minutes": 2}
            ],
            "slo": {"p95_ms": 200, "p99_ms": 400, "5xx_rate_max": 0.005}
        },
        "example_output": {
            "metric_id": "lb.performance",
            "score": 5,
            "rationale": "All SLOs met with margin.",
            "details": {"breaches": 0}
        },
        "response_format": '{"metric_id":"lb.performance","score":<1-5>,"rationale":"...","details":{"breaches":<int>,"worst_lb":"<id>"}}',
        "key_meanings": {
            "load_balancers": "List of LBs with health/latency/5xx metrics",
            "load_balancers[].id": "Load balancer identifier",
            "load_balancers[].lat_p95": "p95 latency in ms",
            "load_balancers[].lat_p99": "p99 latency in ms",
            "load_balancers[].r5xx": "5xx error rate (0..1)",
            "load_balancers[].unhealthy_minutes": "Minutes marked unhealthy",
            "slo.p95_ms": "SLO threshold for p95 latency",
            "slo.p99_ms": "SLO threshold for p99 latency",
            "slo.5xx_rate_max": "Maximum acceptable 5xx rate"
        }
    },

    # 7) Storage efficiency
    "storage.efficiency": {
        "system": (
            "Score storage efficiency (unattached disks, orphaned snapshots, hot-stale objects).\n\n"
            "RUBRIC:\n"
            "- 5: No obvious waste\n"
            "- 4: Minor waste\n"
            "- 3: Noticeable but not severe\n"
            "- 2: Significant avoidable cost\n"
            "- 1: Systemic waste"
        ),
        "example_input": {
            "block_volumes": [{"id": "v", "attached": False}],
            "snapshots": [{"id": "s", "source_volume": None}],
            "objects": [{"storage_class": "STANDARD", "last_modified": "2024-01-01T00:00:00Z"}]
        },
        "example_output": {
            "metric_id": "storage.efficiency",
            "score": 2,
            "rationale": "Unattached volumes and orphaned snaps; stale hot storage.",
            "details": {"unattached": 1, "orphaned_snaps": 1, "hot_stale_objects": 1}
        },
        "response_format": '{"metric_id":"storage.efficiency","score":<1-5>,"rationale":"...","details":{"unattached":<int>,"orphaned_snaps":<int>,"hot_stale_objects":<int>}}',
        "key_meanings": {
            "block_volumes": "List of block volumes and their attachment state",
            "block_volumes[].id": "Volume identifier",
            "block_volumes[].attached": "Boolean attachment flag",
            "snapshots": "List of snapshots and their source volume linkage",
            "snapshots[].source_volume": "Volume ID if snapshot has a valid source, else null",
            "objects": "Object storage items",
            "objects[].storage_class": "Storage tier/class",
            "objects[].last_modified": "Timestamp of last modification/access"
        }
    },

    # 8) IaC coverage & drift
    "iac.coverage_drift": {
        "system": (
            "Score IaC adoption and policy drift severity.\n\n"
            "RUBRIC:\n"
            "- 5: ≥90% IaC-managed; no high/critical drift\n"
            "- 4: 75–89%; few high drifts\n"
            "- 3: 50–74% or some high drifts\n"
            "- 2: 25–49% or multiple high/critical drifts\n"
            "- 1: <25% or widespread critical drift"
        ),
        "example_input": {
            "inventory": [{"id": "a"}, {"id": "b"}],
            "iac_index": {"a": True, "b": False},
            "policy_findings": [{"severity": "high"}]
        },
        "example_output": {
            "metric_id": "iac.coverage_drift",
            "score": 3,
            "rationale": "~50% IaC coverage with high-severity drift.",
            "details": {"coverage_pct": 0.5, "high_critical": 1}
        },
        "response_format": '{"metric_id":"iac.coverage_drift","score":<1-5>,"rationale":"...","details":{"coverage_pct":<0..1>,"high_critical":<int>}}',
        "key_meanings": {
            "inventory": "List of resources in scope",
            "inventory[].id": "Resource identifier",
            "iac_index": "Map of resource id → whether managed by IaC",
            "policy_findings": "List of drift/security/policy issues",
            "policy_findings[].severity": "Severity level (e.g., high, critical)"
        }
    },

    # 9) Availability incidents
    "availability.incidents": {
        "system": (
            "Score reliability based on Sev1/2 count, MTTR, and SLO breach hours (last 30d).\n\n"
            "RUBRIC:\n"
            "- 5: 0 Sev1/2, MTTR <1h, no SLO breaches\n"
            "- 4: ≤1 Sev2, MTTR 1–2h, minor SLO breach\n"
            "- 3: Some incidents, MTTR 2–4h, breaches present\n"
            "- 2: Frequent incidents or MTTR 4–8h\n"
            "- 1: Severe/frequent incidents, MTTR >8h"
        ),
        "example_input": {
            "incidents": [{"sev": 2, "opened": "t0", "resolved": "t1"}],
            "slo_breaches": [{"hours": 1.0}]
        },
        "example_output": {
            "metric_id": "availability.incidents",
            "score": 4,
            "rationale": "One Sev2 quickly resolved; small breach.",
            "details": {"sev12_30d": 1, "mttr_h": 1.0, "slo_breach_hours": 1.0}
        },
        "response_format": '{"metric_id":"availability.incidents","score":<1-5>,"rationale":"...","details":{"sev12_30d":<int>,"mttr_h":<number>,"slo_breach_hours":<number>}}',
        "key_meanings": {
            "incidents": "List of Sev1/Sev2 incidents in last 30d",
            "incidents[].sev": "Incident severity (1 or 2)",
            "incidents[].opened": "Incident opened timestamp",
            "incidents[].resolved": "Incident resolved timestamp",
            "slo_breaches": "List of SLO breach durations",
            "slo_breaches[].hours": "Hours of SLO breach"
        }
    },

    # 10) Cost — idle underutilized
    "cost.idle_underutilized": {
        "system": (
            "Estimate waste from idle compute (low-util VMs) and score cost hygiene.\n\n"
            "RUBRIC:\n"
            "- 5: Idle cost <2% of total\n"
            "- 4: 2–5%\n"
            "- 3: 5–10%\n"
            "- 2: 10–20%\n"
            "- 1: >20%\n"
        ),
        "example_input": {
            "cost_rows": [
                {"resource_id": "a", "cost": 100},
                {"resource_id": "b", "cost": 100}
            ],
            "instances": [
                {"id": "a", "cpu_p95": 0.05, "mem_p95": 0.07},
                {"id": "b", "cpu_p95": 0.6, "mem_p95": 0.5}
            ]
        },
        "example_output": {
            "metric_id": "cost.idle_underutilized",
            "score": 3,
            "rationale": "~50% of cost is idle.",
            "details": {"idle_cost_usd": 100, "idle_pct": 0.5}
        },
        "response_format": '{"metric_id":"cost.idle_underutilized","score":<1-5>,"rationale":"...","details":{"idle_cost_usd":<number>,"idle_pct":<0..1>}}',
        "key_meanings": {
            "cost_rows": "List of resource-level cost entries",
            "cost_rows[].resource_id": "ID matching an instance or resource",
            "cost_rows[].cost": "Cost amount (currency units)",
            "instances": "List of instances with utilization",
            "instances[].id": "Instance identifier",
            "instances[].cpu_p95": "95th percentile CPU (0..1)",
            "instances[].mem_p95": "95th percentile memory (0..1)"
        }
    },

    # 11) Cost — commit coverage
    "cost.commit_coverage": {
        "system": (
            "Score coverage of commitments vs usage and savings realization.\n\n"
            "RUBRIC:\n"
            "- 5: ≥90% coverage and high realized savings\n"
            "- 4: 75–89%\n"
            "- 3: 50–74%\n"
            "- 2: 25–49% or notable waste\n"
            "- 1: <25% or large unused commitments"
        ),
        "example_input": {
            "commit_inventory": [{"commit_usd_hour": 2.0}],
            "usage": [{"used_usd_hour": 1.8, "hours": 720}]
        },
        "example_output": {
            "metric_id": "cost.commit_coverage",
            "score": 4,
            "rationale": "~90% coverage; minor underutilization.",
            "details": {"coverage_pct": 0.9, "waste_usd": 14.4}
        },
        "response_format": '{"metric_id":"cost.commit_coverage","score":<1-5>,"rationale":"...","details":{"coverage_pct":<0..1>,"realized_savings_usd":<number>,"waste_usd":<number>}}',
        "key_meanings": {
            "commit_inventory": "List of commitment SKUs/terms",
            "commit_inventory[].commit_usd_hour": "Hourly committed spend capacity",
            "usage": "List of usage entries for coverage calc",
            "usage[].used_usd_hour": "Hourly spend that was actually used",
            "usage[].hours": "Hours in the period"
        }
    },

    # 12) Cost — allocation quality
    "cost.allocation_quality": {
        "system": (
            "Score how well spend is attributable via tags/labels/resource IDs.\n\n"
            "RUBRIC (by cost-weighted attribution %):\n"
            "- 5: ≥95%\n"
            "- 4: 90–94%\n"
            "- 3: 75–89%\n"
            "- 2: 50–74%\n"
            "- 1: <50%"
        ),
        "example_input": {"cost_rows": [{"cost": 100, "tags": {"env": "prod"}}, {"cost": 100, "tags": {}}]},
        "example_output": {
            "metric_id": "cost.allocation_quality",
            "score": 3,
            "rationale": "~50% attributable.",
            "details": {"attributable_pct": 0.5}
        },
        "response_format": '{"metric_id":"cost.allocation_quality","score":<1-5>,"rationale":"...","details":{"attributable_pct":<0..1>}}',
        "key_meanings": {
            "cost_rows": "List of cost line items",
            "cost_rows[].cost": "Cost amount (currency units)",
            "cost_rows[].tags": "Tag dictionary on the cost row used for attribution"
        }
    },

    # 13) Security — public exposure
    "security.public_exposure": {
        "system": (
            "Score exposure risk from open ingress and public storage.\n\n"
            "RUBRIC:\n"
            "- 5: No public buckets; no 0.0.0.0/0 on sensitive ports; minimal public IPs\n"
            "- 4: Minor issues in dev only\n"
            "- 3: Some risky rules or public buckets\n"
            "- 2: Multiple risky exposures\n"
            "- 1: Systemic exposures in prod"
        ),
        "example_input": {
            "network_policies": [{"rule": "0.0.0.0/0:22"}],
            "storage_acls": [{"public": True}],
            "inventory": [{"public_ip": True}]
        },
        "example_output": {
            "metric_id": "security.public_exposure",
            "score": 2,
            "rationale": "Public SSH and bucket.",
            "details": {"open_fw_rules": 1, "public_buckets": 1, "public_ips": 1}
        },
        "response_format": '{"metric_id":"security.public_exposure","score":<1-5>,"rationale":"...","details":{"open_fw_rules":<int>,"public_buckets":<int>,"public_ips":<int>}}',
        "key_meanings": {
            "network_policies": "Firewall/security group or ingress rules",
            "network_policies[].rule": "CIDR and port expression",
            "storage_acls": "Bucket/container ACLs",
            "storage_acls[].public": "Boolean: publicly readable/listable",
            "inventory": "Inventory entries with exposure attributes",
            "inventory[].public_ip": "Boolean: has public IP"
        }
    },

    # 14) Security — encryption
    "security.encryption": {
        "system": (
            "Score encryption at-rest and modern TLS adoption.\n\n"
            "RUBRIC:\n"
            "- 5: ≥98% encrypted; all LBs TLS1.2+ modern\n"
            "- 4: ≥95% encrypted; minor TLS gaps\n"
            "- 3: 85–94% or some legacy TLS\n"
            "- 2: 70–84% or several legacy endpoints\n"
            "- 1: <70% or widespread legacy"
        ),
        "example_input": {
            "resources": [
                {"encrypted_at_rest": True},
                {"encrypted_at_rest": False},
                {"type": "load_balancer", "tls_policy": "TLS1.0"}
            ]
        },
        "example_output": {
            "metric_id": "security.encryption",
            "score": 2,
            "rationale": "Encryption gaps and legacy TLS1.0.",
            "details": {"at_rest_pct": 0.66, "legacy_tls_endpoints": 1}
        },
        "response_format": '{"metric_id":"security.encryption","score":<1-5>,"rationale":"...","details":{"at_rest_pct":<0..1>,"legacy_tls_endpoints":<int>}}',
        "key_meanings": {
            "resources": "List of resources/endpoints",
            "resources[].encrypted_at_rest": "Boolean: encrypted at rest",
            "resources[].type": "Type of endpoint (e.g., load_balancer)",
            "resources[].tls_policy": "Negotiated/enforced TLS policy version"
        }
    },

    # 15) Security — IAM risk
    "security.iam_risk": {
        "system": (
            "Score IAM hygiene (MFA, key age, permissive policies).\n\n"
            "RUBRIC:\n"
            "- 5: 0 users without MFA; no keys >90d; no wildcard admin\n"
            "- 4: Minor exceptions in non-prod\n"
            "- 3: Some exceptions\n"
            "- 2: Many exceptions\n"
            "- 1: Systemic issues (no MFA, broad wildcards)"
        ),
        "example_input": {
            "users": [{"mfa_enabled": False}],
            "keys": [{"age_days": 120}],
            "policies": [{"actions": ["*"], "resources": ["*"]}]
        },
        "example_output": {
            "metric_id": "security.iam_risk",
            "score": 2,
            "rationale": "Users without MFA and wildcard admin.",
            "details": {"users_without_mfa": 1, "old_keys": 1, "overly_permissive_principals": 1}
        },
        "response_format": '{"metric_id":"security.iam_risk","score":<1-5>,"rationale":"...","details":{"users_without_mfa":<int>,"old_keys":<int>,"overly_permissive_principals":<int>}}',
        "key_meanings": {
            "users": "User accounts",
            "users[].mfa_enabled": "Boolean: MFA enabled",
            "keys": "Access keys",
            "keys[].age_days": "Key age in days",
            "policies": "IAM policies or role bindings",
            "policies[].actions": "Actions allowed (supports wildcard)",
            "policies[].resources": "Resources covered (supports wildcard)"
        }
    },

    # 16) Security — vulnerability & patch hygiene
    "security.vuln_patch": {
        "system": (
            "Score vulnerability & patch hygiene.\n\n"
            "RUBRIC:\n"
            "- 5: 0 critical open; coverage ≥95%; avg patch age <14d\n"
            "- 4: Few highs; coverage ≥90%; patch age <21d\n"
            "- 3: Some criticals or age 21–35d\n"
            "- 2: Multiple criticals; coverage <85% or age 35–60d\n"
            "- 1: Chronic exposure; coverage <70% or age >60d"
        ),
        "example_input": {
            "findings": [{"severity": "CRITICAL", "resolved": False}],
            "patch_status": {"agent_coverage_pct": 0.9, "avg_patch_age_days": 30}
        },
        "example_output": {
            "metric_id": "security.vuln_patch",
            "score": 3,
            "rationale": "One critical open; coverage 90%; patch age 30d.",
            "details": {"critical_open": 1, "agent_coverage_pct": 0.9, "avg_patch_age_days": 30}
        },
        "response_format": '{"metric_id":"security.vuln_patch","score":<1-5>,"rationale":"...","details":{"critical_open":<int>,"agent_coverage_pct":<0..1>,"avg_patch_age_days":<int>}}',
        "key_meanings": {
            "findings": "List of vulnerability findings",
            "findings[].severity": "Severity (e.g., CRITICAL, HIGH)",
            "findings[].resolved": "Boolean: has the finding been resolved",
            "patch_status.agent_coverage_pct": "Fraction of fleet with patch agent installed (0..1)",
            "patch_status.avg_patch_age_days": "Average days since last patch"
        }
    }
}


def build_prompt(metric_id: str, task_input: dict) -> str:
    """Generate a complete prompt for the given metric.

    Output format:
    SYSTEM: ... (includes rubric)
    EXAMPLE INPUT: ...
    EXAMPLE OUTPUT: ...
    INPUT JSON KEYS AND MEANINGS: ...
    TASK INPUT: <your provided JSON>
    RESPONSE FORMAT (JSON only): ...
    """
    meta = METRIC_PROMPTS.get(metric_id)
    if not meta:
        raise ValueError(f"Unknown metric_id: {metric_id}")

    # Build key meanings list
    meanings = meta.get("key_meanings", {})
    key_meanings_str = "\n".join([f"- {k}: {v}" for k, v in meanings.items()]) if meanings else ""

    prompt = (
        f"SYSTEM:\n{meta['system']}\n\n"
        f"EXAMPLE INPUT:\n{json.dumps(meta['example_input'], indent=2)}\n\n"
        f"EXAMPLE OUTPUT:\n{json.dumps(meta['example_output'], indent=2)}\n\n"
        f"INPUT JSON KEYS AND MEANINGS:\n{key_meanings_str}\n\n"
        f"TASK INPUT:\n{json.dumps(task_input, indent=2)}\n\n"
        f"RESPONSE FORMAT (JSON only):\n{meta['response_format']}"
    )
    return prompt


# Demo
if __name__ == "__main__":
    demo = {
        "resources": [
            {"id": "y", "tags": {"env": "prod", "owner": "team"}}
        ],
        "required_tags": ["env", "owner", "cost-center", "service"]
    }
    print(build_prompt("security.vuln_patch", demo))
