"""
Demo inputs for Cloud Infra Agent metrics (all 16).
Each metric has GOOD / MEDIUM / BAD cases to demonstrate rubric-driven scoring.

Usage:
    from demo_inputs import DEMO_INPUTS
    from metrics_optimized import build_prompt

    for level in ("good", "medium", "bad"):
        task_input = DEMO_INPUTS["compute.utilization"][level]
        print(build_prompt("compute.utilization", task_input))
"""

import json

DEMO_INPUTS = {
    # 1) tagging.coverage
    "tagging.coverage": {
        "good": {
            "resources": [
                {"id": "r1", "tags": {"env": "prod", "owner": "team", "cost-center": "C1", "service": "api"}},
                {"id": "r2", "tags": {"env": "dev", "owner": "ops", "cost-center": "C2", "service": "db"}},
                {"id": "r3", "tags": {"env": "prod", "owner": "ml", "cost-center": "C3", "service": "trainer"}}
            ],
            "required_tags": ["env", "owner", "cost-center", "service"]
        },
        "medium": {
            "resources": [
                {"id": "r1", "tags": {"env": "prod", "owner": "team"}},                     # missing cost-center, service
                {"id": "r2", "tags": {"env": "dev", "owner": "ops", "cost-center": "C2"}},   # missing service
                {"id": "r3", "tags": {"env": "prod", "owner": "ml", "service": "trainer"}}   # missing cost-center
            ],
            "required_tags": ["env", "owner", "cost-center", "service"]
        },
        "bad": {
            "resources": [
                {"id": "r1", "tags": {"env": "prod"}},  
                {"id": "r2", "tags": {}},               
                {"id": "r3", "tags": {"owner": "ml"}}
            ],
            "required_tags": ["env", "owner", "cost-center", "service"]
        },
    },

    # 2) compute.utilization
    "compute.utilization": {
        "good": {
            "instances": [
                {"id": "a", "cpu_p95": 0.55, "mem_p95": 0.60},
                {"id": "b", "cpu_p95": 0.45, "mem_p95": 0.50},
                {"id": "c", "cpu_p95": 0.62, "mem_p95": 0.41}
            ]
        },
        "medium": {
            "instances": [
                {"id": "a", "cpu_p95": 0.25, "mem_p95": 0.30},  # underutilized
                {"id": "b", "cpu_p95": 0.65, "mem_p95": 0.70},  # in healthy band
                {"id": "c", "cpu_p95": 0.35, "mem_p95": 0.38}   # slightly low
            ]
        },
        "bad": {
            "instances": [
                {"id": "a", "cpu_p95": 0.05, "mem_p95": 0.07},
                {"id": "b", "cpu_p95": 0.10, "mem_p95": 0.08},
                {"id": "c", "cpu_p95": 0.02, "mem_p95": 0.04}
            ]
        },
    },

    # 3) k8s.utilization
    "k8s.utilization": {
        "good": {
            "nodes": {"cpu_p95": 0.60, "mem_p95": 0.58},
            "pods": {"cpu_req_vs_used": 0.82},
            "binpack_efficiency": 0.85,
            "pending_pods_p95": 0
        },
        "medium": {
            "nodes": {"cpu_p95": 0.55, "mem_p95": 0.60},
            "pods": {"cpu_req_vs_used": 0.70},
            "binpack_efficiency": 0.65,
            "pending_pods_p95": 4
        },
        "bad": {
            "nodes": {"cpu_p95": 0.30, "mem_p95": 0.30},
            "pods": {"cpu_req_vs_used": 0.50},
            "binpack_efficiency": 0.45,
            "pending_pods_p95": 12
        },
    },

    # 4) scaling.effectiveness
    "scaling.effectiveness": {
        "good": {
            "ts_metrics": [
                {"ts": "t0", "target_cpu": 0.60, "actual_cpu": 0.90},
                {"ts": "t1", "target_cpu": 0.60, "actual_cpu": 0.65}
            ],
            "scale_events": [
                {"ts": "t0+30s", "action": "scale_out", "delta": 5}
            ]
        },
        "medium": {
            "ts_metrics": [
                {"ts": "t0", "target_cpu": 0.60, "actual_cpu": 0.90},  # breach start
                {"ts": "t1", "target_cpu": 0.60, "actual_cpu": 0.85},
                {"ts": "t2", "target_cpu": 0.60, "actual_cpu": 0.70}
            ],
            "scale_events": [
                {"ts": "t1+3m", "action": "scale_out", "delta": 2}  # slower & smaller correction
            ]
        },
        "bad": {
            "ts_metrics": [
                {"ts": "t0", "target_cpu": 0.60, "actual_cpu": 0.90},
                {"ts": "t1", "target_cpu": 0.60, "actual_cpu": 0.95},
                {"ts": "t2", "target_cpu": 0.60, "actual_cpu": 0.90}
            ],
            "scale_events": []
        },
    },

    # 5) db.utilization
    "db.utilization": {
        "good": {
            "databases": [
                {"id": "db1", "cpu_p95": 0.60, "connections_p95": 0.60},
                {"id": "db2", "cpu_p95": 0.55, "connections_p95": 0.50},
                {"id": "db3", "cpu_p95": 0.47, "connections_p95": 0.45}
            ]
        },
        "medium": {
            "databases": [
                {"id": "db1", "cpu_p95": 0.75, "connections_p95": 0.40},  # near high CPU, moderate conns
                {"id": "db2", "cpu_p95": 0.35, "connections_p95": 0.90},  # low CPU, high connections (pooling issue)
                {"id": "db3", "cpu_p95": 0.28, "connections_p95": 0.25}
            ]
        },
        "bad": {
            "databases": [
                {"id": "db1", "cpu_p95": 0.90, "connections_p95": 0.95},  # saturated
                {"id": "db2", "cpu_p95": 0.05, "connections_p95": 0.05}   # idle
            ]
        },
    },

    # 6) lb.performance
    "lb.performance": {
        "good": {
            "load_balancers": [
                {"id": "alb1", "lat_p95": 150, "lat_p99": 250, "r5xx": 0.002, "unhealthy_minutes": 1, "requests": 100000}
            ],
            "slo": {"p95_ms": 200, "p99_ms": 400, "5xx_rate_max": 0.005}
        },
        "medium": {
            "load_balancers": [
                {"id": "alb1", "lat_p95": 210, "lat_p99": 420, "r5xx": 0.006, "unhealthy_minutes": 8, "requests": 120000}
            ],
            "slo": {"p95_ms": 200, "p99_ms": 400, "5xx_rate_max": 0.005}
        },
        "bad": {
            "load_balancers": [
                {"id": "alb1", "lat_p95": 300, "lat_p99": 600, "r5xx": 0.020, "unhealthy_minutes": 30, "requests": 50000}
            ],
            "slo": {"p95_ms": 200, "p99_ms": 400, "5xx_rate_max": 0.005}
        },
    },

    # 7) storage.efficiency
    "storage.efficiency": {
        "good": {
            "block_volumes": [{"id": "v1", "attached": True}, {"id": "v2", "attached": True}],
            "snapshots": [{"id": "s1", "source_volume": "v1"}],
            "objects": [{"storage_class": "STANDARD", "last_modified": "2025-07-15T00:00:00Z"}]
        },
        "medium": {
            "block_volumes": [{"id": "v1", "attached": True}, {"id": "v2", "attached": False}],  # 1 unattached
            "snapshots": [{"id": "s1", "source_volume": None}],                                   # 1 orphan
            "objects": [{"storage_class": "STANDARD", "last_modified": "2025-03-01T00:00:00Z"}]  # ~180d old
        },
        "bad": {
            "block_volumes": [{"id": "v1", "attached": False}, {"id": "v2", "attached": False}],
            "snapshots": [{"id": "s1", "source_volume": None}, {"id": "s2", "source_volume": None}],
            "objects": [{"storage_class": "STANDARD", "last_modified": "2024-01-01T00:00:00Z"}]
        },
    },

    # 8) iac.coverage_drift
    "iac.coverage_drift": {
        "good": {
            "inventory": [{"id": "a"}, {"id": "b"}, {"id": "c"}],
            "iac_index": {"a": True, "b": True, "c": True},
            "policy_findings": []
        },
        "medium": {
            "inventory": [{"id": "a"}, {"id": "b"}, {"id": "c"}, {"id": "d"}],
            "iac_index": {"a": True, "b": True, "c": True, "d": False},  # 75% coverage
            "policy_findings": [{"severity": "high"}]                    # 1 high
        },
        "bad": {
            "inventory": [{"id": "a"}, {"id": "b"}, {"id": "c"}],
            "iac_index": {"a": True, "b": False, "c": False},            # 33% coverage
            "policy_findings": [{"severity": "critical"}]
        },
    },

    # 9) availability.incidents
    "availability.incidents": {
        "good": {
            "incidents": [],
            "slo_breaches": [],
            "slo": {"objective": "availability", "target": 0.995}
        },
        "medium": {
            "incidents": [{"sev": 2, "opened": "t0", "resolved": "t3h"}, {"sev": 2, "opened": "t5d", "resolved": "t8h"}],
            "slo_breaches": [{"hours": 3.0}],
            "slo": {"objective": "availability", "target": 0.995}
        },
        "bad": {
            "incidents": [{"sev": 1, "opened": "t0", "resolved": "t10h"}],
            "slo_breaches": [{"hours": 15.0}],
            "slo": {"objective": "availability", "target": 0.995}
        },
    },

    # 10) cost.idle_underutilized
    "cost.idle_underutilized": {
        "good": {
            "cost_rows": [{"resource_id": "a", "cost": 100}, {"resource_id": "b", "cost": 300}],
            "instances": [
                {"id": "a", "cpu_p95": 0.60, "mem_p95": 0.60},
                {"id": "b", "cpu_p95": 0.55, "mem_p95": 0.52}
            ]
        },
        "medium": {
            "cost_rows": [{"resource_id": "a", "cost": 40}, {"resource_id": "b", "cost": 460}],
            "instances": [
                {"id": "a", "cpu_p95": 0.06, "mem_p95": 0.07},  # idle, cost 40 → ~8% idle
                {"id": "b", "cpu_p95": 0.55, "mem_p95": 0.50}
            ]
        },
        "bad": {
            "cost_rows": [{"resource_id": "a", "cost": 200}, {"resource_id": "b", "cost": 200}],
            "instances": [
                {"id": "a", "cpu_p95": 0.05, "mem_p95": 0.05},  # idle 200/400 = 50%
                {"id": "b", "cpu_p95": 0.60, "mem_p95": 0.55}
            ]
        },
    },

    # 11) cost.commit_coverage
    "cost.commit_coverage": {
        "good": {
            "commit_inventory": [{"commit_usd_hour": 2.0}],
            "usage": [{"used_usd_hour": 1.95, "hours": 720}]
        },
        "medium": {
            "commit_inventory": [{"commit_usd_hour": 5.0}],
            "usage": [{"used_usd_hour": 3.90, "hours": 720}]  # coverage 0.78, unused 0.22
        },
        "bad": {
            "commit_inventory": [{"commit_usd_hour": 5.0}],
            "usage": [{"used_usd_hour": 2.0, "hours": 720}]   # coverage 0.40, unused 0.60
        },
    },

    # 12) cost.allocation_quality
    "cost.allocation_quality": {
        "good": {
            "cost_rows": [
                {"cost": 100, "tags": {"env": "prod", "owner": "team"}},
                {"cost": 200, "tags": {"env": "dev", "owner": "ops"}},
                {"cost": 150, "tags": {"env": "stage", "owner": "ml"}}
            ]
        },
        "medium": {
            "cost_rows": [
                {"cost": 100, "tags": {"env": "prod", "owner": "team"}},
                {"cost": 200, "tags": {}},                                # unattributed
                {"cost": 150, "tags": {"env": "dev"}}                     # partial tags (owner missing)
            ]
        },
        "bad": {
            "cost_rows": [
                {"cost": 100, "tags": {}},
                {"cost": 200, "tags": {}},
                {"cost": 150, "tags": {}}
            ]
        },
    },

    # 13) security.public_exposure
    "security.public_exposure": {
        "good": {
            "network_policies": [],
            "storage_acls": [],
            "inventory": [{"id": "i1", "public_ip": False}, {"id": "i2", "public_ip": False}]
        },
        "medium": {
            "network_policies": [{"rule": "0.0.0.0/0:8080", "env": "dev"}],      # risky but non-prod
            "storage_acls": [{"bucket": "logs-dev", "public": True, "exception_approved": True}],
            "inventory": [{"id": "i1", "public_ip": True, "sensitive": False}]
        },
        "bad": {
            "network_policies": [{"rule": "0.0.0.0/0:22", "env": "prod"}],
            "storage_acls": [{"bucket": "prod-ml", "public": True}],
            "inventory": [{"id": "i1", "public_ip": True, "sensitive": True}]
        },
    },

    # 14) security.encryption
    "security.encryption": {
        "good": {
            "resources": [
                {"id": "v1", "type": "block_volume", "encrypted_at_rest": True},
                {"id": "v2", "type": "object_bucket", "encrypted_at_rest": True},
                {"id": "alb1", "type": "load_balancer", "tls_policy": "TLS1.2-2019-Modern"}
            ]
        },
        "medium": {
            "resources": [
                {"id": "v1", "type": "block_volume", "encrypted_at_rest": True},
                {"id": "v2", "type": "object_bucket", "encrypted_at_rest": False},      # one unencrypted
                {"id": "alb1", "type": "load_balancer", "tls_policy": "TLS1.1"}        # legacy in non-prod implied
            ]
        },
        "bad": {
            "resources": [
                {"id": "v1", "type": "block_volume", "encrypted_at_rest": False},
                {"id": "v2", "type": "object_bucket", "encrypted_at_rest": False},
                {"id": "alb1", "type": "load_balancer", "tls_policy": "TLS1.0"}
            ]
        },
    },

    # 15) security.iam_risk
    "security.iam_risk": {
        "good": {
            "users": [{"name": "a", "mfa_enabled": True}, {"name": "b", "mfa_enabled": True}],
            "keys": [{"user": "a", "age_days": 10}, {"user": "b", "age_days": 15}],
            "policies": [{"actions": ["ec2:StartInstances"], "resources": ["i-123"]}]
        },
        "medium": {
            "users": [{"name": "a", "mfa_enabled": False}, {"name": "b", "mfa_enabled": True}],   # 1 without MFA
            "keys": [{"user": "a", "age_days": 120}],                                            # old key
            "policies": [{"actions": ["s3:*"], "resources": ["*"]}]                              # overly broad (not full admin)
        },
        "bad": {
            "users": [{"name": "a", "mfa_enabled": False}, {"name": "b", "mfa_enabled": False}],
            "keys": [{"user": "a", "age_days": 200}, {"user": "b", "age_days": 300}],
            "policies": [{"actions": ["*"], "resources": ["*"]}]                                 # wildcard admin
        },
    },

    # 16) security.vuln_patch
    "security.vuln_patch": {
        "good": {
            "findings": [],
            "patch_status": {"agent_coverage_pct": 0.97, "avg_patch_age_days": 10, "sla": {"critical_days": 7, "high_days": 30}},
            "denominators": {"total_assets": 100, "scanned_assets": 97}
        },
        "medium": {
            "findings": [{"severity": "HIGH", "resolved": False}],
            "patch_status": {"agent_coverage_pct": 0.87, "avg_patch_age_days": 28, "sla": {"critical_days": 7, "high_days": 30}},
            "denominators": {"total_assets": 120, "scanned_assets": 104}
        },
        "bad": {
            "findings": [{"severity": "CRITICAL", "resolved": False}],
            "patch_status": {"agent_coverage_pct": 0.60, "avg_patch_age_days": 70, "sla": {"critical_days": 7, "high_days": 30}},
            "denominators": {"total_assets": 100, "scanned_assets": 60}
        },
    },
}

def main():
    print(json.dumps(DEMO_INPUTS, indent=2))

if __name__ == "__main__":
    main()
