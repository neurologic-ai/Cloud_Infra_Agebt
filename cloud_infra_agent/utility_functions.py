from __future__ import annotations

import statistics
from collections import defaultdict, Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Iterable


def p50(values: Iterable[float]) -> float:
    vals = sorted([v for v in values if v is not None])
    return statistics.median(vals) if vals else 0.0


def p95(values: Iterable[float]) -> float:
    vals = sorted([v for v in values if v is not None])
    if not vals:
        return 0.0
    k = int(round(0.95 * (len(vals) - 1)))
    return vals[k]


def avg_numeric(values: Iterable[float]) -> float:
    vals = [v for v in values if isinstance(v, (int, float))]
    return (sum(vals) / len(vals)) if vals else 0.0


def aggregate_by_kind(resource_lists: List[List[Dict[str, Any]]]) -> Dict[str, int]:
    counter = Counter()
    for lst in resource_lists:
        for r in lst:
            kind = r.get("kind") or r.get("type")
            if kind:
                counter[kind] += 1
    return dict(counter)


def sample_missing_tags(
    resources: List[Dict[str, Any]], required: Iterable[str]
) -> List[Dict[str, Any]]:
    required = list(required)
    out = []
    for r in resources:
        tags = r.get("tags", {}) or {}
        missing = [
            t for t in required if t not in tags or tags.get(t) in ("", None)
        ]
        if missing:
            out.append({"id": r.get("id"), "missing": missing})
    return out


def bytes_stale_in_hot(objects: List[Dict[str, Any]], stale_days: int = 90) -> int:
    """Count bytes in STANDARD/Hot class where last_modified is older than stale_days."""
    now = datetime.now(timezone.utc)
    total = 0
    hot_classes = {"STANDARD", "STANDARD_IA", "HOT", "MULTI_REGIONAL", "REGIONAL"}

    for obj in objects:
        cls = (obj.get("storage_class") or "").upper()
        if cls not in hot_classes:
            continue

        lm = obj.get("last_modified")
        if isinstance(lm, str):
            try:
                lm_dt = datetime.fromisoformat(lm.replace("Z", "+00:00"))
            except Exception:
                continue
        elif isinstance(lm, datetime):
            lm_dt = lm
        else:
            continue

        age_days = (now - lm_dt).days
        if age_days is not None and age_days > stale_days:
            total += int(obj.get("size", 0))

    return int(total)


def lifecycle_rule_coverage(
    lifecycle_rules: List[Dict[str, Any]], objects: List[Dict[str, Any]]
) -> float:
    """% objects whose bucket has at least one lifecycle rule."""
    buckets_with_rules = {
        r.get("bucket") for r in lifecycle_rules if r.get("bucket")
    }
    if not objects:
        return 0.0

    covered = sum(1 for o in objects if o.get("bucket") in buckets_with_rules)
    return covered / max(1, len(objects))


def bytes_eligible_for_cold(
    objects: List[Dict[str, Any]], rules: List[Dict[str, Any]]
) -> int:
    """For demo: bytes older than min(transition_after_days) among provided rules, in hot classes."""
    if not rules:
        return 0
    min_days = min(
        int(r.get("transition_after_days", 90)) for r in rules
    )
    return bytes_stale_in_hot(objects, stale_days=min_days)


def pct_encrypted_at_rest(resources: List[Dict[str, Any]]) -> float:
    relevant = [
        r
        for r in resources
        if r.get("type")
        in ("block_volume", "object_bucket", "database", "disk", "snapshot")
    ]
    if not relevant:
        return 1.0  # assume good if nothing to check

    enc = sum(
        1
        for r in relevant
        if r.get("encrypted_at_rest") in (True, "true", "enabled")
    )
    return enc / len(relevant)


def pct_strong_tls_policies(resources: List[Dict[str, Any]]) -> float:
    lbs = [
        r for r in resources
        if r.get("type") in ("load_balancer", "application_gateway")
    ]
    if not lbs:
        return 1.0

    strong = 0
    for lb in lbs:
        policy = (lb.get("tls_policy") or "").upper()
        if "TLS1.2" in policy or "TLS1_2" in policy or "TLSV1.2" in policy:
            strong += 1

    return strong / len(lbs)


def rule_allows_world(rule: Dict[str, Any]) -> bool:
    text = (rule.get("rule") or "").lower()
    return "0.0.0.0/0" in text or "any/any" in text


def bucket_public(b: Dict[str, Any]) -> bool:
    if "public" in b:
        return bool(b.get("public"))

    acl = (b.get("acl") or "").lower()
    pol = (b.get("policy") or "").lower()
    return ("allusers" in acl) or ("public" in pol)


def overly_permissive_principals(
    iam_dump: Dict[str, Any]
) -> List[Dict[str, Any]]:
    perms = []
    for p in iam_dump.get("policies", []):
        acts = p.get("actions", [])
        res = p.get("resources", [])
        if any(a == "*" for a in acts) and any(r == "*" for r in res):
            perms.append(p)
    return perms


def mttr_hours(incidents: List[Dict[str, Any]]) -> float:
    if not incidents:
        return 0.0

    dur_hours = []
    for i in incidents:
        opened = i.get("opened")
        resolved = i.get("resolved")

        if isinstance(opened, str):
            opened_dt = datetime.fromisoformat(opened.replace("Z", "+00:00"))
        else:
            opened_dt = opened

        if isinstance(resolved, str):
            resolved_dt = datetime.fromisoformat(resolved.replace("Z", "+00:00"))
        else:
            resolved_dt = resolved

        if opened_dt and resolved_dt:
            dur = (resolved_dt - opened_dt).total_seconds() / 3600.0
            if dur >= 0:
                dur_hours.append(dur)

    return avg_numeric(dur_hours)


def commitment_coverage_percent(
    commit_inventory: List[Dict[str, Any]], usage: List[Dict[str, Any]]
) -> float:
    """Simple family-based coverage: min(commit, used) / used."""
    used_by_family = defaultdict(float)
    commit_by_family = defaultdict(float)

    for u in usage:
        used_by_family[u.get("family")] += float(u.get("used_usd_hour", 0.0))

    for c in commit_inventory:
        commit_by_family[c.get("family")] += float(c.get("commit_usd_hour", 0.0))

    covered = 0.0
    total = 0.0
    for fam, used in used_by_family.items():
        total += used
        covered += min(used, commit_by_family.get(fam, 0.0))

    return (covered / total) if total > 0 else 0.0


def realized_savings_usd(
    commit_inventory: List[Dict[str, Any]], usage: List[Dict[str, Any]]
) -> float:
    """Toy model: coverage * 20% discount * total used spend."""
    coverage = commitment_coverage_percent(commit_inventory, usage)
    total_used = sum(
        float(u.get("used_usd_hour", 0.0)) * float(u.get("hours", 0)) for u in usage
    )
    return coverage * 0.20 * total_used


def commitment_waste_usd(
    commit_inventory: List[Dict[str, Any]], usage: List[Dict[str, Any]]
) -> float:
    """Unused commitment * hours_in_month (inferred from usage entries) -> USD."""
    hours_candidates = [float(u.get("hours", 0)) for u in usage if u.get("hours")]
    hours = hours_candidates[0] if hours_candidates else 720.0

    commit_by_family = defaultdict(float)
    used_by_family = defaultdict(float)

    for c in commit_inventory:
        commit_by_family[c.get("family")] += float(c.get("commit_usd_hour", 0.0))

    for u in usage:
        used_by_family[u.get("family")] += float(u.get("used_usd_hour", 0.0))

    waste_per_hour = 0.0
    for fam, commit_hr in commit_by_family.items():
        diff = max(0.0, commit_hr - used_by_family.get(fam, 0.0))
        waste_per_hour += diff

    return waste_per_hour * hours


def cost_per_gpu_hour(cost_rows: List[Dict[str, Any]]) -> float:
    total_cost = 0.0
    total_hours = 0.0
    for r in cost_rows:
        total_cost += float(r.get("usd_per_hour", 0.0)) * float(r.get("hours", 0.0))
        total_hours += float(r.get("hours", 0.0))
    return (total_cost / total_hours) if total_hours > 0 else 0.0


def rollup_cost(
    cost_rows: List[Dict[str, Any]], dims: List[str]
) -> Dict[str, Any]:
    """Nested dict rollup by provided dimensions."""

    def nested_set(d, keys, value):
        for k in keys[:-1]:
            d = d.setdefault(k, {})
        d[keys[-1]] = d.get(keys[-1], 0.0) + value

    out: Dict[str, Any] = {}
    for r in cost_rows:
        key_path = [str(r.get(dim, "unknown")) for dim in dims]
        nested_set(out, key_path, float(r.get("cost", 0.0)))

    return out


def detect_month(cost_rows: List[Dict[str, Any]]) -> str:
    months = [r.get("month") for r in cost_rows if r.get("month")]
    return months[0] if months else ""


def rollup_egress(cost_rows: List[Dict[str, Any]]) -> Dict[str, float]:
    out = defaultdict(float)
    for r in cost_rows:
        t = r.get("type") or r.get("egress_type") or "unknown"
        out[str(t)] += float(r.get("usd", 0.0))
    return dict(out)


def detect_spikes(net_metrics: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Simple: find hour-to-hour delta > p95 of deltas."""
    if len(net_metrics) < 2:
        return []

    def to_ts(s):
        return datetime.fromisoformat(s.replace("Z", "+00:00"))

    sorted_rows = sorted(net_metrics, key=lambda m: to_ts(m["ts"]))
    deltas = [
        float(curr.get("egress_gb", 0.0)) - float(prev.get("egress_gb", 0.0))
        for prev, curr in zip(sorted_rows, sorted_rows[1:])
    ]

    threshold = p95(deltas) if deltas else 0.0
    spikes = []

    for prev, curr in zip(sorted_rows, sorted_rows[1:]):
        delta = float(curr.get("egress_gb", 0.0)) - float(prev.get("egress_gb", 0.0))
        if delta >= threshold and delta > 0:
            spikes.append({"ts": curr["ts"], "delta_gb": round(delta, 3)})

    return spikes
