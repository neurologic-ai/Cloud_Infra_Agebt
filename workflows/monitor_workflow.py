from typing import Dict, Any, Tuple, List
from concurrent.futures import ThreadPoolExecutor, as_completed
from agent_layer.registry import LEVEL0, LEVEL1_DEPS, CATEGORIES
from agent_layer.tool_loader import load_function
import os
import json
import time


# ---- Stages (mirrors your notebook) ----
def setup(config: Dict[str, Any]) -> Dict[str, Any]:
    return config or {}

def ingest(context: Dict[str, Any]) -> Dict[str, Any]:
    # later want to fetch live data, do it here and inject into context
    return context or {}

# -------- Metric selection plan --------
def resolve_plan(requested: Any) -> Tuple[List[str], List[str]]:
    """
    Decide which LEVEL0 and LEVEL1 metrics to run based on `requested`.

    - requested='all' or None  -> run all LEVEL0 and all LEVEL1.
    - requested=<str>          -> run only that metric (L0 or L1). If L1, include its deps.
    - requested=[...] list     -> run only specified metrics; include L1 deps automatically.
    """
    if requested is None or requested == "all":
        return list(LEVEL0), list(LEVEL1_DEPS.keys())

    if isinstance(requested, str):
        requested_list = [requested]
    elif isinstance(requested, list):
        requested_list = [str(x) for x in requested]
    else:
        return list(LEVEL0), list(LEVEL1_DEPS.keys())

    req_set = set(requested_list)
    l1_all = set(LEVEL1_DEPS.keys())

    # L0 explicitly requested
    l0_from_req = [m for m in LEVEL0 if m in req_set]
    # L1 explicitly requested
    l1_from_req = [m for m in requested_list if m in l1_all]

    # Ensure L0 deps for requested L1
    needed_l0 = set(l0_from_req)
    for m in l1_from_req:
        for d in LEVEL1_DEPS.get(m, []):
            if d in LEVEL0:
                needed_l0.add(d)

    l0_to_run = [m for m in LEVEL0 if m in needed_l0]
    l1_to_run = l1_from_req
    return l0_to_run, l1_to_run

def run_parallel(context: Dict[str, Any], metrics: List[str], max_workers: int = 8) -> Dict[str, Any]:
    out: Dict[str, Any] = {}

    def _run(name: str):
        fn = load_function(name)
        return name, fn(context.get(name, {}))

    if not metrics:
        return out

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futs = {pool.submit(_run, m): m for m in metrics}   # only selected metrics
        for fut in as_completed(futs):
            m = futs[fut]                                  # metric name for this future
            try:
                name, res = fut.result()
                out[name] = res
            except Exception as e:
                out[m] = {"metric_id": m, "score": 0.0, "rationale": f"runner exception: {e}"}
    return out

def run_dependent(context: Dict[str, Any], prev: Dict[str, Any], metrics: List[str]) -> Dict[str, Any]:
    out = dict(prev)
    for m in metrics:
        # inject deps as-is (simple): downstream LLM can read them if prompts use it
        slice_ctx = dict(context.get(m, {}))
        deps = LEVEL1_DEPS.get(m, [])
        slice_ctx["deps"] = {d: out.get(d) for d in deps}
        try:
            fn = load_function(m)
            out[m] = fn(slice_ctx)
        except Exception as e:
            out[m] = {"metric_id": m, "score": 0.0, "rationale": f"runner exception: {e}"}
    return out

# ---- Weighted roll-up (categories + overall) ----
def _normalize(weights: Dict[str, float]) -> Dict[str, float]:
    total = sum([w for w in weights.values() if isinstance(w, (int, float))])
    if total <= 0:  # equal if all zero/missing
        n = len(weights) or 1
        return {k: 1.0/n for k in weights}
    return {k: float(w)/total for k, w in weights.items()}

def _score_of(v: Any):
    return v.get("score") if isinstance(v, dict) else None

def aggregate(results: Dict[str, Any], config: Dict[str, Any] | None = None) -> Dict[str, Any]:
    cfg = config or {}
    # Apply optional runtime overrides
    cat_cfg = {k: dict(v) for k, v in CATEGORIES.items()}
    if "category_weights" in cfg:
        for c, w in cfg["category_weights"].items():
            if c in cat_cfg: cat_cfg[c]["weight"] = w
    if "metric_weights" in cfg:
        for c, mws in cfg["metric_weights"].items():
            if c in cat_cfg and isinstance(mws, dict):
                cat_cfg[c]["metrics"] = {**cat_cfg[c].get("metrics", {}), **mws}

    cat_w_norm = _normalize({c: meta.get("weight", 0.0) for c, meta in cat_cfg.items()})
    breakdown = []
    category_scores = {}
    overall_acc = overall_used = 0.0

    for c, meta in cat_cfg.items():
        mw = meta.get("metrics", {})
        mw_norm = _normalize(mw) if mw else {}
        parts = []
        acc = used = 0.0
        for m, w in mw_norm.items():
            sc = _score_of(results.get(m))
            parts.append({"metric": m, "weight": w, "score": sc})
            if isinstance(sc, (int, float)):
                acc += w * sc
                used += w
        cat_score = (acc/used) if used > 0 else None
        category_scores[c] = cat_score
        cw = cat_w_norm.get(c, 0.0)
        breakdown.append({"name": c, "weight": cw, "effective_weight_sum": used, "metrics": parts})
        if isinstance(cat_score, (int, float)) and cw > 0:
            overall_acc += cw * cat_score
            overall_used += cw

    overall_score = (overall_acc/overall_used) if overall_used > 0 else None
    # simple debug stats
    simple_scores = [v.get("score") for v in results.values() if isinstance(v, dict) and isinstance(v.get("score"), (int, float))]
    simple_avg = (sum(simple_scores)/len(simple_scores)) if simple_scores else None

    return {
        "overall_score": overall_score,
        "category_scores": category_scores,
        "breakdown": breakdown,
        "simple_average_debug": simple_avg,
        "count_metrics": len(results),
        "scored_metrics": len(simple_scores),
    }

def report(results: Dict[str, Any], summary: Dict[str, Any]) -> Dict[str, Any]:
    return {"metrics": results, "summary": summary}

def _save_json(path: str, data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def run_workflow(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    cfg = setup(config)
    ctx = ingest(context)

    # plan: default 'all' if not provided
    l0_to_run, l1_to_run = resolve_plan(cfg.get("metrics", "all"))

    # execute
    max_workers = int(cfg.get("max_workers", 8))
    l0 = run_parallel(ctx, l0_to_run, max_workers=max_workers)
    l1 = run_dependent(ctx, l0, l1_to_run)

    # aggregate
    summ = aggregate(l1, cfg)
    final = report(l1, summ)

    # save
    output_path = cfg.get("output_path")
    save_dir = cfg.get("save_dir") or "./runs"
    if output_path:
        _save_json(output_path, final)
    else:
        ts = int(time.time())
        os.makedirs(save_dir, exist_ok=True)
        default_path = os.path.join(save_dir, f"run-{ts}.json")
        _save_json(default_path, final)

    return final
