import json

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
    "- Use only provided data. If required inputs are missing, list them in 'gaps', reduce 'confidence', and adjust the score downward.\n"
    "- Prefer normalized rates (0..1), p95/p99, and denominators. Cite exact numbers under 'evidence'.\n"
    "- Keep actions concrete (≤5), prioritized (P0/P1/P2), and focused on the next step.\n"
    "- Return ONLY the specified JSON. No extra text."
)

UNIVERSAL_RESPONSE_FORMAT = (
    '{"metric_id":"<id>",'
    '"score":<1-5>,'
    '"rationale":"<2-4 sentences>",'
    '"evidence":{},'
    '"gaps":[],'
    '"actions":[{"priority":"P0|P1|P2","action":"..."}],'
    '"confidence":<0.0-1.0>'
)

# =========================
# Metric definitions
# =========================
# Each metric has:
# - system: the full prompt (universal preamble + rubric)
# - example_input: canonical JSON example
# - response_format: always UNIVERSAL_RESPONSE_FORMAT
# - example_output: example JSON response

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
        ),
        "example_input": {
            "resources": [
                {"id": "x", "tags": {"env": "prod", "owner": "team", "cost-center": "CC1", "service": "api"}},
                {"id": "y", "tags": {"env": "prod", "owner": "team"}}
            ],
            "required_tags": ["env", "owner", "cost-center", "service"]
        },
        "response_format": UNIVERSAL_RESPONSE_FORMAT,
        "example_output": {
            "metric_id": "tagging.coverage",
            "score": 3,
            "rationale": "~50% fully tagged; missing critical tags on prod resources increases allocation and ownership risk.",
            "evidence": {"coverage_pct": 0.5, "missing_examples": [{"id": "y", "missing": ["cost-center", "service"]}]},
            "gaps": [],
            "actions": [{"priority": "P1", "action": "Enforce env/owner/cost-center/service tags in CI & provisioning"}],
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
        ),
        "example_input": {
            "instances": [
                {"id": "a", "cpu_p95": 0.55, "mem_p95": 0.6, "low_util_hours_30d": 5},
                {"id": "b", "cpu_p95": 0.1,  "mem_p95": 0.2, "low_util_hours_30d": 200}
            ]
        },
        "response_format": UNIVERSAL_RESPONSE_FORMAT,
        "example_output": {
            "metric_id": "compute.utilization",
            "score": 2,
            "rationale": "Significant idle capacity; half the fleet shows persistent low utilization.",
            "evidence": {"idle_pct": 0.5, "worst_idle_hours": 200, "fleet_cpu_p95": 0.325, "fleet_mem_p95": 0.40},
            "gaps": [],
            "actions": [{"priority": "P1", "action": "Rightsize or stop idle instance 'b' and set off-hours schedules"}],
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
        ),
        "example_input": {
            "nodes": {"cpu_p95": 0.6, "mem_p95": 0.58},
            "pods": {"cpu_req_vs_used": 0.8},
            "binpack_efficiency": 0.82,
            "pending_pods_p95": 1
        },
        "response_format": UNIVERSAL_RESPONSE_FORMAT,
        "example_output": {
            "metric_id": "k8s.utilization",
            "score": 5,
            "rationale": "Requests closely match usage with strong bin-packing and minimal pending pods.",
            "evidence": {"binpack_efficiency": 0.82, "pending_pods_p95": 1, "nodes_cpu_p95": 0.60, "pods_cpu_req_vs_used": 0.80},
            "gaps": [],
            "actions": [{"priority": "P2", "action": "Maintain current request/limit ratios; re-verify quarterly"}],
            "confidence": 0.85
        }
    },

    # 4) Scaling effectiveness
    "scaling.effectiveness": {
        "system": (
            f"{UNIVERSAL_PREAMBLE}\n\n"
            "RUBRIC (reaction, target adherence, thrash):\n"
            "- 5: Reaction <1 min; <5% target violations; thrash <5%\n"
            "- 4: Reaction 1-2 min; 5-10% violations; thrash <10%\n"
            "- 3: Reaction 2-5 min; 10-20% violations; mild thrash\n"
            "- 2: Reaction 5-10 min; >20% violations; frequent thrash\n"
            "- 1: Reaction >10 min; sustained violations; severe thrash"
        ),
        "example_input": {
            "ts_metrics": [
                {"ts": "t0", "target_cpu": 0.6, "actual_cpu": 0.9},
                {"ts": "t2", "target_cpu": 0.6, "actual_cpu": 0.61}
            ],
            "scale_events": [{"ts": "t1", "action": "scale_out", "delta": 1}],
            "window": "2025-08-10T12:00Z..2025-08-10T14:00Z",
            "sample_size": 240
        },
        "response_format": UNIVERSAL_RESPONSE_FORMAT,
        "example_output": {
            "metric_id": "scaling.effectiveness",
            "score": 4,
            "rationale": "Autoscaler reacted within ~1 minute with brief target violation and no oscillation.",
            "evidence": {"median_reaction_s": 60, "target_violation_pct": 0.10, "thrash_rate": 0.0, "events": 1},
            "gaps": [],
            "actions": [{"priority": "P2", "action": "Tighten cooldown only if future thrash appears; currently acceptable"}],
            "confidence": 0.8,
            "window": "2025-08-10T12:00Z..2025-08-10T14:00Z",
            "sample_size": 240
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
        ),
        "example_input": {
            "databases": [
                {"id": "a", "cpu_p95": 0.6, "connections_p95": 0.5},
                {"id": "b", "cpu_p95": 0.1, "connections_p95": 0.1}
            ],
            "window": "2025-07-20..2025-08-19",
            "sample_size": 2
        },
        "response_format": UNIVERSAL_RESPONSE_FORMAT,
        "example_output": {
            "metric_id": "db.utilization",
            "score": 3,
            "rationale": "Fleet shows a mix of idle and moderately loaded databases; sizing is uneven.",
            "evidence": {"low_util_count": 1, "high_util_count": 0, "fleet_cpu_p95_avg": 0.35},
            "gaps": [],
            "actions": [{"priority": "P1", "action": "Downsize or consolidate idle DB 'b'; validate connection limits"}],
            "confidence": 0.82,
            "window": "2025-07-20..2025-08-19",
            "sample_size": 2
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
        ),
        "example_input": {
            "load_balancers": [
                {"id": "alb-1", "lat_p95": 130, "lat_p99": 260, "r5xx": 0.003, "unhealthy_minutes": 2, "requests": 1200000}
            ],
            "slo": {"p95_ms": 200, "p99_ms": 400, "5xx_rate_max": 0.005}
        },
        "response_format": UNIVERSAL_RESPONSE_FORMAT,
        "example_output": {
            "metric_id": "lb.performance",
            "score": 5,
            "rationale": "Latency and error‑rate SLOs met with margin; negligible unhealthy time.",
            "evidence": {"breaches": 0, "worst_lb": "alb-1", "p95_ms": 130, "p99_ms": 260, "r5xx": 0.003, "requests": 1200000},
            "gaps": [],
            "actions": [{"priority": "P2", "action": "Maintain capacity & SLO thresholds; review monthly"}],
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
        ),
        "example_input": {
            "block_volumes": [{"id": "v", "attached": False}],
            "snapshots": [{"id": "s", "source_volume": None}],
            "objects": [{"storage_class": "STANDARD", "last_modified": "2024-01-01T00:00:00Z"}]
        },
        "response_format": UNIVERSAL_RESPONSE_FORMAT,
        "example_output": {
            "metric_id": "storage.efficiency",
            "score": 2,
            "rationale": "Unattached volumes and orphaned snapshots indicate avoidable spend; hot tier holds stale objects.",
            "evidence": {"unattached": 1, "orphaned_snaps": 1, "hot_stale_objects": 1},
            "gaps": [],
            "actions": [{"priority": "P1", "action": "Delete orphaned snapshots; reattach or remove volume; set S3 lifecycle to infrequent access"}],
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
        ),
        "example_input": {
            "inventory": [{"id": "a"}, {"id": "b"}],
            "iac_index": {"a": True, "b": False},
            "policy_findings": [{"severity": "high"}]
        },
        "response_format": UNIVERSAL_RESPONSE_FORMAT,
        "example_output": {
            "metric_id": "iac.coverage_drift",
            "score": 3,
            "rationale": "Coverage sits near 50% with high-severity drift present; unmanaged resources increase change risk.",
            "evidence": {"coverage_pct": 0.5, "high_critical": 1},
            "gaps": [],
            "actions": [{"priority": "P1", "action": "Onboard unmanaged resources to Terraform; remediate high-severity drift"}],
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
        ),
        "example_input": {
            "incidents": [{"sev": 2, "opened": "t0", "resolved": "t1"}],
            "slo_breaches": [{"hours": 1.0}],
            "slo": {"objective": "availability", "target": 0.995}
        },
        "response_format": UNIVERSAL_RESPONSE_FORMAT,
        "example_output": {
            "metric_id": "availability.incidents",
            "score": 4,
            "rationale": "A single Sev2 was resolved quickly with limited SLO breach time.",
            "evidence": {"sev12_30d": 1, "mttr_h": 1.0, "slo_breach_hours": 1.0, "slo_target": 0.995},
            "gaps": [],
            "actions": [{"priority": "P2", "action": "Review post-mortem for mitigations; confirm alert thresholds"}],
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
        "response_format": UNIVERSAL_RESPONSE_FORMAT,
        "example_output": {
            "metric_id": "cost.idle_underutilized",
            "score": 2,
            "rationale": "Idle cost forms a significant share of spend with persistently underutilized instances.",
            "evidence": {"idle_cost": 100, "idle_pct": 0.5, "total_cost": 200},
            "gaps": [],
            "actions": [{"priority": "P1", "action": "Stop or downsize idle instance 'a'; apply off‑hours schedules"}],
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
        ),
        "example_input": {
            "commit_inventory": [{"commit_usd_hour": 2.0}],
            "usage": [{"used_usd_hour": 1.8, "hours": 720}]
        },
        "response_format": UNIVERSAL_RESPONSE_FORMAT,
        "example_output": {
            "metric_id": "cost.commit_coverage",
            "score": 4,
            "rationale": "Coverage at ~90% with ~10% unused commitments.",
            "evidence": {"coverage_pct": 0.90, "waste_usd": 144},
            "gaps": [],
            "actions": [
                {
                    "priority": "P1",
                    "action": "Refine commitment mix to reduce ~10% unused commitments."
                }
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
            "- 1: <50%"
        ),
        "example_input": {
            "cost_rows": [
                {"cost": 100, "tags": {"env": "prod", "owner": "search"}},
                {"cost": 100, "tags": {}}
            ]
        },
        "response_format": UNIVERSAL_RESPONSE_FORMAT,
        "example_output": {
            "metric_id": "cost.allocation_quality",
            "score": 3,
            "rationale": "Only half of spend is attributable due to missing tags.",
            "evidence": {"attributable_pct": 0.5},
            "gaps": [],
            "actions": [{"priority": "P1", "action": "Enforce owner/env tagging on all cost lines; backfill missing owners"}],
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
        ),
        "example_input": {
            "network_policies": [{"rule": "0.0.0.0/0:22"}],
            "storage_acls": [{"bucket": "ml-prod", "public": True}],
            "inventory": [{"id": "i-9zzz", "public_ip": True}]
        },
        "response_format": UNIVERSAL_RESPONSE_FORMAT,
        "example_output": {
            "metric_id": "security.public_exposure",
            "score": 2,
            "rationale": "Public SSH access and a publicly readable bucket raise material exposure risk.",
            "evidence": {"open_fw_rules": 1, "public_buckets": 1, "public_ips": 1},
            "gaps": [],
            "actions": [{"priority": "P0", "action": "Restrict SSH to corporate CIDRs; make bucket private; remove public IPs from prod"}],
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
        ),
        "example_input": {
            "resources": [
                {"id": "vol-1", "type": "block_volume", "encrypted_at_rest": True},
                {"id": "alb-1", "type": "load_balancer", "tls_policy": "TLS1.2-2019-Modern"}
            ]
        },
        "response_format": UNIVERSAL_RESPONSE_FORMAT,
        "example_output": {
            "metric_id": "security.encryption",
            "score": 2,
            "rationale": "Encryption gaps and legacy TLS1.0 indicate elevated risk.",
            "evidence": {"at_rest_pct": 0.66, "legacy_tls_endpoints": 1},
            "gaps": [],
            "actions": [{"priority": "P1", "action": "Enable encryption on remaining volumes; upgrade LB security policy to TLS1.2+ modern"}],
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
        ),
        "example_input": {
            "users": [{"name": "a","mfa_enabled": False}],
            "keys": [{ "user": "user","age_days": 120}],
            "policies": [{"actions": ["*"], "resources": ["*"]}]
        },
        "response_format": UNIVERSAL_RESPONSE_FORMAT,
        "example_output": {
            "metric_id": "security.iam_risk",
            "score": 2,
            "rationale": "Users without MFA and a wildcard admin policy present elevated compromise risk.",
            "evidence": {"users_without_mfa": 1, "old_keys": 1, "overly_permissive_principals": 1},
            "gaps": [],
            "actions": [
                {"priority": "P0", "action": "Enforce MFA for all users immediately"},
                {"priority": "P0", "action": "Replace wildcard admin with least-privilege roles"}
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
        ),
        "example_input": {
            "findings": [{"severity": "CRITICAL", "resolved": False}],
            "patch_status": {"agent_coverage_pct": 0.9, "avg_patch_age_days": 30, "sla": {"critical_days": 7, "high_days": 30}},
            "denominators": {"total_assets": 420, "scanned_assets": 403},
        },
        "response_format": UNIVERSAL_RESPONSE_FORMAT,
        "example_output": {
            "metric_id": "security.vuln_patch",
            "score": 3,
            "rationale": "One critical remains open; patch agent coverage is near target with moderate patch latency.",
            "evidence": {
                "critical_open": 1,
                "agent_coverage_pct": 0.90,
                "avg_patch_age_days": 30,
                "sla": {"critical_days": 7, "high_days": 30},
                "scanned_assets": 403,
                "total_assets": 420
            },
            "gaps": [],
            "actions": [
                {"priority": "P0", "action": "Patch critical CVEs on internet-exposed assets within 48 hours"},
                {"priority": "P1", "action": "Increase patch agent coverage from 90%→95% across missing subnets"}
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

    meanings = meta.get("key_meanings", {})
    key_meanings_str = "\n".join([f"- {k}: {v}" for k, v in meanings.items()]) if meanings else ""

    prompt = (
        f"SYSTEM:\n{meta['system']}\n\n"
        f"INPUT JSON KEYS AND MEANINGS:\n{key_meanings_str}\n\n"
        f"TASK INPUT:\n{json.dumps(task_input, indent=2)}\n\n"
        f"RESPONSE FORMAT (JSON only):\n{meta['response_format']}\n\n"
        f"EXAMPLE INPUT:\n{json.dumps(meta['example_input'], indent=2)}\n\n"
        f"EXAMPLE OUTPUT:\n{json.dumps(meta['example_output'], indent=2)}"
    )
    return prompt


# # Demo
# if __name__ == "__main__":
#     demo = {
#         "resources": [
#             {"id": "y", "tags": {"env": "prod", "owner": "team"}}
#         ],
#         "required_tags": ["env", "owner", "cost-center", "service"],
#         "window": "2025-07-20..2025-08-19",
#         "sample_size": 1
#     }
#     print(build_prompt("tagging.coverage", demo))
