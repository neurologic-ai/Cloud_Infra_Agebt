import json
from loguru import logger

"""
Metric Prompt Builder (optimized for Cloud Infra Agent)
- Universal preamble and unified response format for all metrics
- Optimized rubrics with clear 1-5 thresholds + concise descriptions
- Example outputs use 'evidence' (not 'details')
- build_prompt prints RESPONSE FORMAT before EXAMPLES (reduces anchoring)
- Added CONSTRAINTS and SELF-AUDIT blocks (no I/O change)
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
    "- Return ONLY the specified JSON. No extra text.\n"
    "- Do NOT reuse numbers from EXAMPLE OUTPUT; recompute everything from TASK INPUT."
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

# Extra guardrails
CONSTRAINTS_BLOCK = (
    "CONSTRAINTS:\n"
    "- Output must be valid JSON only (no prose outside JSON).\n"
    "- Never invent numbers; use only TASK INPUT.\n"
    "- If required inputs are missing, list them under 'gaps', lower 'confidence' (≤0.6), and bias the score down by one level.\n"
    "- Prefer normalized rates (0..1), p95/p99, and include denominators in 'evidence'.\n"
    "- Provide ≤5 concrete 'actions' with P0/P1/P2, each verifiable within the next sprint.\n"
)

SELF_AUDIT_BLOCK = (
    "SELF-AUDIT (check silently before returning JSON):\n"
    "- 'score' ∈ {1,2,3,4,5}; 'confidence' ∈ [0.0,1.0].\n"
    "- 'evidence' cites exact figures (e.g., 53/240=0.221, p95=0.62).\n"
    "- 'gaps' lists any missing inputs referenced by the rubric.\n"
)

# =========================
# Metric definitions
# =========================
METRIC_PROMPTS = {
    # 1) Tagging coverage
    "tagging.coverage": {
        "system": (
            f"{UNIVERSAL_PREAMBLE}\n\n"
            "RUBRIC (f = fully-tagged fraction; c = prod critical tags {env,owner}):\n"
            "- 5: f ≥ 0.95 AND c ≥ 0.98 → near-perfect hygiene; negligible allocation risk.\n"
            "- 4: 0.85–0.94 AND c ≥ 0.90 → minor gaps; manageable operational risk.\n"
            "- 3: 0.70–0.84 OR c 0.80–0.89 → noticeable holes; owners/cost centers sometimes unclear.\n"
            "- 2: 0.50–0.69 OR c 0.60–0.79 → material risk of unowned spend and audit friction.\n"
            "- 1: f < 0.50 OR c < 0.60 OR ≥25% prod missing env/owner → systemic tagging breakdown.\n\n"
            "Compute: f = (# fully tagged) / total; c = (prod with env+owner) / prod total."
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
            "RUBRIC (healthy band = 0.40–0.70 for cpu_p95 & mem_p95):\n"
            "- 5: ≥80% instances in band; ≤10% idle (cpu+mem<0.10) → well-sized fleet.\n"
            "- 4: 65–79% in band; 10–20% idle → minor inefficiency.\n"
            "- 3: 50–64% in band OR 20–35% idle → moderate imbalance.\n"
            "- 2: 30–49% in band OR 36–50% idle → significant waste.\n"
            "- 1: <30% in band OR >50% idle → systemic underutilization.\n\n"
            "Compute: within_band%, low_util%, fleet_cpu_p95_avg, fleet_mem_p95_avg."
        ),
        "example_input": {
            "instances": [
                {"id": "a", "cpu_p95": 0.55, "mem_p95": 0.6, "low_util_hours_30d": 5},
                {"id": "b", "cpu_p95": 0.1, "mem_p95": 0.2, "low_util_hours_30d": 200}
            ]
        },
        "input_key_meanings": {
            "instances": "List of compute instances",
            "instances[].id": "Instance identifier",
            "instances[].cpu_p95": "95th percentile CPU utilization (0..1)",
            "instances[].mem_p95": "95th percentile memory utilization (0..1)",
            "instances[].low_util_hours_30d": "Hours below low-util threshold in last 30d"
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
            "RUBRIC (nodes, requests≈usage, packing, pending):\n"
            "- 5: nodes 50–70%; req≈used ≥0.80; binpack >0.80; pending <1 → excellent packing.\n"
            "- 4: nodes 40–75%; req≈used 0.70–0.79; binpack >0.70; pending <3 → minor room to improve.\n"
            "- 3: binpack 0.60–0.70 OR pending 3–5 → moderate imbalance.\n"
            "- 2: binpack 0.50–0.59 OR pending 6–10 → severe inefficiency.\n"
            "- 1: binpack <0.50 OR pending >10 → chronic inefficiency.\n"
        ),
        "example_input": {
            "nodes": {"cpu_p95": 0.6, "mem_p95": 0.58},
            "pods": {"cpu_req_vs_used": 0.8},
            "binpack_efficiency": 0.82,
            "pending_pods_p95": 1
        },
        "input_key_meanings": {
            "nodes.cpu_p95": "Aggregated node CPU utilization (0..1)",
            "nodes.mem_p95": "Aggregated node memory utilization (0..1)",
            "pods.cpu_req_vs_used": "Ratio of requested to used CPU",
            "binpack_efficiency": "Packing efficiency (0..1)",
            "pending_pods_p95": "95th percentile of pending pods"
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
            "RUBRIC (reaction, violations, thrash, delta adequacy):\n"
            "- 5: reaction <1m; violations <5%; thrash <5%; delta error <10% → excellent.\n"
            "- 4: 1–2m; 5–10%; <10%; 10–20% → good.\n"
            "- 3: 2–5m; 10–20%; <20%; 20–35% → fair.\n"
            "- 2: 5–10m; 20–35%; 20–35%; 35–60% → poor.\n"
            "- 1: >10m; >35%; >35%; >60% → critical.\n\n"
            "Definitions: violation = |actual-target|/target>0.05; reaction=breach→scale_event; thrash=flip<300s; delta adequacy=needed vs applied."
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
            "ts_metrics[].target_cpu": "Autoscaler target",
            "ts_metrics[].actual_cpu": "Observed utilization",
            "scale_events[].action": "scale_out/scale_in",
            "scale_events[].delta": "Capacity change"
        },
        "response_format": UNIVERSAL_RESPONSE_FORMAT,
        "example_output": {
            "metric_id": "scaling.effectiveness",
            "score": 5,
            "rationale": "Very fast reaction (~40s), violation rate under 5%, no thrash, and delta matched the overload.",
            "evidence": {"median_reaction_s": 40, "target_violation_pct": 4.76, "thrash_rate": 0.0, "delta_error_pct": 0.0},
            "gaps": [],
            "actions": [{"priority": "P2", "action": "Maintain step sizing; monitor for oscillation"}],
            "confidence": 0.8
        }
    },
        "db.utilization": {
        "system": (
            f"{UNIVERSAL_PREAMBLE}\n\n"
            "RUBRIC (CPU p95 band 0.40–0.70; imbalance if connections_p95 >0.85 or <0.10 while CPU mid-band):\n"
            "- 5: fleet avg CPU 0.40–0.70 AND imbalance ≤10% → healthy sizing and pooling.\n"
            "- 4: avg 0.30–0.75 AND imbalance 10–20% → minor hotspots or idles.\n"
            "- 3: avg 0.20–0.85 OR imbalance 20–35% → uneven sizing or connection limits.\n"
            "- 2: frequent <0.20 or >0.85 OR imbalance 35–50% → sustained bottlenecks/overprovisioning.\n"
            "- 1: chronic <0.10 or >0.90 OR imbalance >50% → severe sizing or connection policy issues."
        ),
        "example_input": {
            "databases": [
                {"id": "a", "cpu_p95": 0.6, "connections_p95": 0.5},
                {"id": "b", "cpu_p95": 0.1, "connections_p95": 0.1}
            ]
        },
        "input_key_meanings": {
            "databases[].cpu_p95": "95th percentile CPU utilization (0..1)",
            "databases[].connections_p95": "95th percentile connection load (0..1)"
        },
        "response_format": UNIVERSAL_RESPONSE_FORMAT,
        "example_output": {
            "metric_id": "db.utilization",
            "score": 3,
            "rationale": "Fleet shows a mix of idle and moderately loaded databases; sizing is uneven.",
            "evidence": {"low_util_count": 1, "high_util_count": 0, "fleet_cpu_p95_avg": 0.35},
            "gaps": [],
            "actions": [{"priority": "P1", "action": "Downsize or consolidate idle DB 'b'; validate connection limits"}],
            "confidence": 0.82
        }
    },
        "lb.performance": {
        "system": (
            f"{UNIVERSAL_PREAMBLE}\n\n"
            "RUBRIC (compare latency/error vs SLO):\n"
            "- 5: p95/p99 < SLO, 5xx ≤ SLO, unhealthy ≤5 min → excellent.\n"
            "- 4: p95/p99 near SLO, rare 5xx (≤1.2× SLO), unhealthy ≤15 min → minor spikes.\n"
            "- 3: periodic breaches 1–5% of requests OR 5xx ≤1.5× SLO → moderate.\n"
            "- 2: frequent breaches 5–15% OR 5xx ≤2× SLO → noticeable degradation.\n"
            "- 1: chronic breaches >15% OR 5xx >2× SLO → systemic instability."
        ),
        "example_input": {
            "load_balancers": [
                {"id": "alb-1", "lat_p95": 130, "lat_p99": 260, "r5xx": 0.003, "unhealthy_minutes": 2, "requests": 1200000}
            ],
            "slo": {"p95_ms": 200, "p99_ms": 400, "5xx_rate_max": 0.005}
        },
        "input_key_meanings": {
            "load_balancers[].lat_p95": "p95 latency in ms",
            "load_balancers[].lat_p99": "p99 latency in ms",
            "load_balancers[].r5xx": "5xx error rate",
            "load_balancers[].unhealthy_minutes": "Minutes marked unhealthy"
        },
        "response_format": UNIVERSAL_RESPONSE_FORMAT,
        "example_output": {
            "metric_id": "lb.performance",
            "score": 5,
            "rationale": "Latency and error-rate SLOs met with margin; negligible unhealthy time.",
            "evidence": {"breaches": 0, "worst_lb": "alb-1", "p95_ms": 130, "p99_ms": 260, "r5xx": 0.003},
            "gaps": [],
            "actions": [{"priority": "P2", "action": "Maintain capacity & SLO thresholds; review monthly"}],
            "confidence": 0.86
        }
    },
        "storage.efficiency": {
        "system": (
            f"{UNIVERSAL_PREAMBLE}\n\n"
            "RUBRIC (waste% = unattached volumes + orphaned snaps + stale hot objects):\n"
            "- 5: <2% → negligible waste.\n"
            "- 4: 2–5% → minor inefficiency.\n"
            "- 3: 5–10% → noticeable waste needing cleanup.\n"
            "- 2: 10–20% → significant avoidable cost.\n"
            "- 1: >20% → systemic waste; urgent action."
        ),
        "example_input": {
            "block_volumes": [{"id": "v", "attached": False}],
            "snapshots": [{"id": "s", "source_volume": None}],
            "objects": [{"storage_class": "STANDARD", "last_modified": "2024-01-01T00:00:00Z"}]
        },
        "input_key_meanings": {
            "block_volumes[].attached": "Boolean attachment flag",
            "snapshots[].source_volume": "Volume ID if valid, else null",
            "objects[].storage_class": "Storage tier",
            "objects[].last_modified": "Last modified timestamp"
        },
        "response_format": UNIVERSAL_RESPONSE_FORMAT,
        "example_output": {
            "metric_id": "storage.efficiency",
            "score": 2,
            "rationale": "Unattached volumes and orphaned snapshots indicate avoidable spend; hot tier holds stale objects.",
            "evidence": {"unattached": 1, "orphaned_snaps": 1, "hot_stale_objects": 1},
            "gaps": [],
            "actions": [{"priority": "P1", "action": "Delete orphaned snapshots; reattach/remove volume; set lifecycle policy"}],
            "confidence": 0.85
        }
    },
        "iac.coverage_drift": {
        "system": (
            f"{UNIVERSAL_PREAMBLE}\n\n"
            "RUBRIC (coverage fraction + drift severity):\n"
            "- 5: ≥95% IaC-managed AND 0 high/critical drift → excellent.\n"
            "- 4: 85–94% managed; ≤2 high drift (0 critical) → good.\n"
            "- 3: 70–84% OR ≥1 critical OR >2 high drift → moderate risk.\n"
            "- 2: 50–69% OR multiple criticals → significant unmanaged changes.\n"
            "- 1: <50% OR widespread critical drift → systemic lack of control."
        ),
        "example_input": {
            "inventory": [{"id": "a"}, {"id": "b"}],
            "iac_index": {"a": True, "b": False},
            "policy_findings": [{"severity": "high"}]
        },
        "input_key_meanings": {
            "inventory[].id": "Resource identifier",
            "iac_index": "Map resource→bool if under IaC",
            "policy_findings[].severity": "Severity (high/critical)"
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
        "availability.incidents": {
        "system": (
            f"{UNIVERSAL_PREAMBLE}\n\n"
            "RUBRIC (sev1/2 counts, MTTR, SLO breach hours):\n"
            "- 5: sev1=0, sev2=0, MTTR < 1h, breach_hours = 0 → excellent reliability.\n"
            "- 4: sev1=0, sev2 ≤ 1, MTTR 1–2h, breach ≤ 2h → strong with minor impact.\n"
            "- 3: sev1 ≤ 1 or sev2 ≤ 3, MTTR 2–4h, breach 2–6h → moderate incident burden.\n"
            "- 2: sev1 ≥ 2 or sev2 > 3 or MTTR 4–8h or breach 6–12h → significant reliability risk.\n"
            "- 1: frequent sev1 or MTTR > 8h or breach > 12h → chronic instability."
        ),
        "example_input": {
            "incidents": [{"sev": 2, "opened": "t0", "resolved": "t1"}],
            "slo_breaches": [{"hours": 1.0}],
            "slo": {"objective": "availability", "target": 0.995}
        },
        "input_key_meanings": {
            "incidents": "Array of incident records in the scoring window",
            "incidents[].sev": "Severity (1=critical, 2=major, 3=minor, ...)",
            "incidents[].opened": "Start time (ISO 8601 recommended)",
            "incidents[].resolved": "Resolve time (ISO 8601 recommended)",
            "slo_breaches": "Array of SLO violations observed",
            "slo_breaches[].hours": "Breach duration in hours",
            "slo.objective": "Type of objective (availability/latency/etc.)",
            "slo.target": "Numerical target (e.g., 0.995 = 99.5%)"
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
        "cost.idle_underutilized": {
        "system": (
            f"{UNIVERSAL_PREAMBLE}\n\n"
            "RUBRIC (idle_cost / total_cost; idle = cpu_p95 < 0.10 AND mem_p95 < 0.10):\n"
            "- 5: < 2% idle spend → fleet very efficient.\n"
            "- 4: 2–5% idle → minor inefficiency; small savings possible.\n"
            "- 3: 5–10% idle → moderate waste; right-sizing recommended.\n"
            "- 2: 10–20% idle → significant waste; clear savings opportunity.\n"
            "- 1: > 20% idle → systemic idle spend; urgent remediation required."
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
            "rationale": "Idle cost forms a significant share of spend with persistently underutilized instances.",
            "evidence": {"idle_cost": 100, "idle_pct": 0.5, "total_cost": 200},
            "gaps": [],
            "actions": [{"priority": "P1", "action": "Stop or downsize idle instance 'a'; apply off-hours schedules"}],
            "confidence": 0.88
        }
    },
        "cost.commit_coverage": {
        "system": (
            f"{UNIVERSAL_PREAMBLE}\n\n"
            "RUBRIC (coverage% and unused% of commitments):\n"
            "- 5: coverage ≥ 0.95 AND unused < 0.05 → near-perfect alignment.\n"
            "- 4: 0.85–0.94 AND 0.05–0.10 → good fit with minor breakage.\n"
            "- 3: 0.70–0.84 AND 0.11–0.20 → moderate breakage; tune commitment mix.\n"
            "- 2: 0.50–0.69 OR 0.21–0.30 → significant mismatch or waste.\n"
            "- 1: coverage < 0.50 OR unused > 0.30 → poor fit; large waste.\n\n"
            "Compute: coverage = used_usd_hour / commit_usd_hour (clip to 1.0); unused = 1 - coverage (hours-weighted)."
        ),
        "example_input": {
            "commit_inventory": [{"commit_usd_hour": 2.0}],
            "usage": [{"used_usd_hour": 1.8, "hours": 720}]
        },
        "input_key_meanings": {
            "commit_inventory": "List of commitment SKUs/terms",
            "commit_inventory[].commit_usd_hour": "Hourly committed spend capacity",
            "usage": "List of usage entries for coverage calc",
            "usage[].used_usd_hour": "Hourly spend actually used",
            "usage[].hours": "Hours in the period"
        },
        "response_format": UNIVERSAL_RESPONSE_FORMAT,
        "example_output": {
            "metric_id": "cost.commit_coverage",
            "score": 4,
            "rationale": "Coverage at ~90% with ~10% unused commitments.",
            "evidence": {"coverage_pct": 0.90, "waste_usd": 144},
            "gaps": [],
            "actions": [{"priority": "P1", "action": "Refine commitment mix to reduce ~10% unused commitments."}],
            "confidence": 0.9
        }
    },
        "cost.allocation_quality": {
        "system": (
            f"{UNIVERSAL_PREAMBLE}\n\n"
            "RUBRIC (cost-weighted attributable fraction via tags/owner/env/bu):\n"
            "- 5: ≥ 0.95 → almost all spend attributable.\n"
            "- 4: 0.90–0.94 → minor unattributed spend.\n"
            "- 3: 0.75–0.89 → meaningful unattributed share; fix gaps.\n"
            "- 2: 0.50–0.74 → substantial unattributed cost.\n"
            "- 1: < 0.50 → majority unattributed; urgent tagging/chargeback fixes.\n\n"
            "Notes: attribute a row if tags are sufficient for ownership and environment mapping."
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
            "cost_rows[].tags": "Tag dictionary used for attribution"
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
        "security.public_exposure": {
        "system": (
            f"{UNIVERSAL_PREAMBLE}\n\n"
            "RUBRIC (open SG rules, public buckets, prod exposure):\n"
            "- 5: no public buckets; no 0.0.0.0/0 on sensitive ports; ≤2 non-prod public IPs → very low exposure.\n"
            "- 4: ≤1 approved exception; no prod-critical exposure → low risk.\n"
            "- 3: some risky rules OR 1 public bucket with guardrails → moderate exposure.\n"
            "- 2: multiple unnecessary exposures OR any prod 0.0.0.0/0 on SSH/RDP/DB → high risk.\n"
            "- 1: widespread prod exposure OR anonymous read/write on prod buckets → critical exposure."
        ),
        "example_input": {
            "network_policies": [{"rule": "0.0.0.0/0:22"}],
            "storage_acls": [{"bucket": "ml-prod", "public": True}],
            "inventory": [{"id": "i-9zzz", "public_ip": True}]
        },
        "input_key_meanings": {
            "network_policies[].rule": "CIDR:port or CIDR:port-range",
            "storage_acls[].bucket": "Bucket identifier",
            "storage_acls[].public": "True if bucket public",
            "inventory[].public_ip": "True if asset has public IP"
        },
        "response_format": UNIVERSAL_RESPONSE_FORMAT,
        "example_output": {
            "metric_id": "security.public_exposure",
            "score": 2,
            "rationale": "Public SSH access and a publicly readable bucket raise material exposure risk.",
            "evidence": {"open_fw_rules": 1, "public_buckets": 1, "public_ips": 1},
            "gaps": [],
            "actions": [{"priority": "P0", "action": "Restrict SSH to corp CIDRs; make bucket private; remove public IPs from prod"}],
            "confidence": 0.88
        }
    },
        "security.encryption": {
        "system": (
            f"{UNIVERSAL_PREAMBLE}\n\n"
            "RUBRIC (at-rest encryption & TLS policy):\n"
            "- 5: ≥99% encrypted; all endpoints TLS1.2+ modern → excellent.\n"
            "- 4: 90–98% encrypted; only minor non-prod TLS gaps → good.\n"
            "- 3: 70–89% encrypted OR some legacy TLS in non-prod → moderate.\n"
            "- 2: 50–69% encrypted OR several legacy TLS endpoints in prod → poor.\n"
            "- 1: <50% encrypted OR widespread legacy TLS → critical."
        ),
        "example_input": {
            "resources": [
                {"id": "vol-1", "type": "block_volume", "encrypted_at_rest": True},
                {"id": "alb-1", "type": "load_balancer", "tls_policy": "TLS1.2-2019-Modern"}
            ]
        },
        "input_key_meanings": {
            "resources[].type": "Type of resource",
            "resources[].encrypted_at_rest": "True if storage encrypted",
            "resources[].tls_policy": "TLS policy string"
        },
        "response_format": UNIVERSAL_RESPONSE_FORMAT,
        "example_output": {
            "metric_id": "security.encryption",
            "score": 2,
            "rationale": "Encryption gaps and legacy TLS1.0 indicate elevated risk.",
            "evidence": {"at_rest_pct": 0.66, "legacy_tls_endpoints": 1},
            "gaps": [],
            "actions": [{"priority": "P1", "action": "Enable encryption on remaining volumes; upgrade LB TLS policy"}],
            "confidence": 0.86
        }
    },
        "security.iam_risk": {
        "system": (
            f"{UNIVERSAL_PREAMBLE}\n\n"
            "RUBRIC (users w/o MFA, old keys, wildcard policies):\n"
            "- 5: 0 users without MFA; no keys >90d; no wildcard admin → excellent.\n"
            "- 4: few non-prod exceptions (≤3 total issues) → minor risk.\n"
            "- 3: scattered issues (4–10 total) → moderate.\n"
            "- 2: many issues (11–20) or several wildcard policies → poor.\n"
            "- 1: systemic issues; wildcard admin in prod or >20 total issues → critical."
        ),
        "example_input": {
            "users": [{"name": "a","mfa_enabled": False}],
            "keys": [{ "user": "user","age_days": 120}],
            "policies": [{"actions": ["*"], "resources": ["*"]}]
        },
        "input_key_meanings": {
            "users[].mfa_enabled": "True if MFA enabled",
            "keys[].age_days": "Age of key in days",
            "policies[].actions": "List of allowed actions",
            "policies[].resources": "List of covered resources"
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
        "security.vuln_patch": {
        "system": (
            f"{UNIVERSAL_PREAMBLE}\n\n"
            "RUBRIC (coverage, patch latency, criticals):\n"
            "- 5: ≥95% coverage, avg patch age <14d, 0 critical open → excellent hygiene.\n"
            "- 4: ≥90% coverage, avg age <21d, few highs → good.\n"
            "- 3: some criticals open OR avg age 21–35d OR coverage 80–89% → moderate.\n"
            "- 2: multiple criticals OR coverage 70–79% OR age 35–60d → poor.\n"
            "- 1: coverage <70% OR age >60d → critical backlog.\n"
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
            "findings[].severity": "Severity of the finding",
            "patch_status.agent_coverage_pct": "Fraction of assets with patch agent reporting",
            "patch_status.avg_patch_age_days": "Average patch age (days)",
            "denominators.total_assets": "Total assets in environment",
            "denominators.scanned_assets": "Scanned/covered assets"
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
                "scanned_assets": 403,
                "total_assets": 420
            },
            "gaps": [],
            "actions": [
                {"priority": "P0", "action": "Patch critical CVEs on internet-exposed assets within 48 hours"},
                {"priority": "P1", "action": "Increase patch agent coverage from 90%→95%"}
            ],
            "confidence": 0.78
        }
    },
}

# =========================
# Prompt builder
# =========================
def build_prompt(metric_id: str, task_input: dict) -> str:
    """Generate a complete prompt for the given metric."""

    meta = METRIC_PROMPTS.get(metric_id)
    if not meta:
        raise ValueError(f"Unknown metric_id: {metric_id}")

    meanings = meta.get("input_key_meanings", {})
    key_meanings_str = "\n".join([f"- {k}: {v}" for k, v in meanings.items()]) if meanings else ""

    prompt = (
        f"SYSTEM:\n{meta['system']}\n\n"
        f"{CONSTRAINTS_BLOCK}\n"
        f"{SELF_AUDIT_BLOCK}\n\n"
        f"INPUT JSON KEYS AND MEANINGS:\n{key_meanings_str}\n\n"
        f"TASK INPUT:\n{json.dumps(task_input, indent=2)}\n\n"
        f"RESPONSE FORMAT (JSON only):\n{meta['response_format']}\n\n"
        f"EXAMPLE INPUT:\n{json.dumps(meta['example_input'], indent=2)}\n\n"
        f"EXAMPLE OUTPUT:\n{json.dumps(meta['example_output'], indent=2)}"
    )
    logger.debug(prompt)
    return prompt
